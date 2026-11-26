from contextlib import asynccontextmanager
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from backend.api import auth_deps
from backend.core import database, report_service, target_service
from backend.core.jwks_verifier import AuthenticatedUser
from backend.core.request_owner import request_owner
from backend.main import app


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test_pusher.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_all_tables()
    token = target_service.target_scope.set(None)
    target_service.target_store._load_from_db()
    yield db_file
    target_service.target_scope.reset(token)


def _client_for_user(user_id: str) -> TestClient:
    async def _override_user():
        request_owner.set(user_id)
        return AuthenticatedUser(user_id=user_id, email=f"{user_id}@test.local", role="authenticated")

    app.dependency_overrides[auth_deps.require_operator] = _override_user
    return TestClient(app)


@pytest.mark.asyncio
async def test_detect_project_name_sandbox_short_circuit():
    res = await target_service.detect_project_name("http://127.0.0.1:8000/api/sandbox/target", is_sandbox=True)
    assert res == {"project_name": "Pusher Sandbox", "source": "sandbox"}


@pytest.mark.asyncio
async def test_detect_project_name_priority_and_8kb_cap(monkeypatch):
    bytes_yielded = 0

    class FakeResponse:
        def __init__(self, status_code, headers, chunks):
            self.status_code = status_code
            self.headers = headers
            self._chunks = chunks

        async def aiter_bytes(self, chunk_size=4096):
            nonlocal bytes_yielded
            for chunk in self._chunks:
                bytes_yielded += len(chunk)
                yield chunk

    def make_client(chunks, content_type="text/html; charset=utf-8"):
        @asynccontextmanager
        async def _ctx(*args, **kwargs):
            class _Client:
                @asynccontextmanager
                async def stream(self_c, method, url, headers=None):
                    yield FakeResponse(200, {"content-type": content_type}, chunks)

            yield _Client()

        return _ctx

    # 1. Meta og:site_name + strict 8 KB read cap on a 64 KB response
    big_tail = b"x" * 4096
    head = b'<html><head><meta property="og:site_name" content="Veribite App" /><title>Veribite | Smart Food Scanner</title></head>'
    chunks = [head] + [big_tail] * 16  # > 64 KB total
    bytes_yielded = 0
    monkeypatch.setattr(target_service, "target_client", make_client(chunks))
    res_meta = await target_service.detect_project_name("https://veribite.vercel.app")
    assert res_meta == {"project_name": "Veribite App", "source": "meta"}
    # Stream stopped cleanly well under 16 KB (at most head + 2 * 4096 chunks read)
    assert bytes_yielded <= len(head) + 8192

    # 2. <title> cleanup & >32 char suffix trimming
    monkeypatch.setattr(
        target_service,
        "target_client",
        make_client(["<html><head><title>Northstar Analytics — Real-Time Telemetry Platform</title></head></html>".encode("utf-8")]),
    )
    res_title = await target_service.detect_project_name("https://northstar.dev")
    assert res_title == {"project_name": "Northstar Analytics", "source": "title"}

    # 3. Non-HTML / JSON API hostname fallback
    monkeypatch.setattr(
        target_service,
        "target_client",
        make_client([b'{"ok":true}'], content_type="application/json"),
    )
    res_api = await target_service.detect_project_name("https://api.veribite.vercel.app")
    assert res_api == {"project_name": "Veribite", "source": "hostname"}


def test_project_name_api_persistence_and_user_isolation(isolated_db, monkeypatch):
    monkeypatch.setattr(target_service, "resolve_addresses", AsyncMock(return_value=["93.184.216.34"]))
    monkeypatch.setattr(
        target_service,
        "detect_project_name",
        AsyncMock(return_value={"project_name": "Veribite", "source": "hostname"}),
    )

    try:
        c1 = _client_for_user("operator_a")
        val_res = c1.post("/api/target/validate-url", json={"target_url": "https://api.veribite.vercel.app", "is_sandbox": False})
        assert val_res.status_code == 200
        body = val_res.json()
        assert body["detected_project_name"] == "Veribite"
        assert body["detected_project_source"] == "hostname"

        put_res = c1.put("/api/target/project-name", json={"project_name": "  Veribite   Production  "})
        assert put_res.status_code == 200
        assert put_res.json()["project_name"] == "Veribite Production"

        status_a = c1.get("/api/target/status").json()
        assert status_a["project_name"] == "Veribite Production"

        # Operator B must remain isolated
        c2 = _client_for_user("operator_b")
        status_b = c2.get("/api/target/status").json()
        assert status_b["project_name"] == ""
    finally:
        app.dependency_overrides.clear()


def test_save_run_persists_and_filters_project_name(isolated_db):
    token = request_owner.set("owner_project_1")
    try:
        saved = report_service.save_run({
            "run_id": "RUN-PROJ-001",
            "target_url": "https://api.veribite.vercel.app",
            "project_name": "Veribite Checkout",
            "mode": "Steady Crowd",
            "target_vus": 100,
            "peak_vus": 100,
            "duration_sec": 30,
            "elapsed_sec": 30,
            "total_requests": 500,
            "status_2xx": 500,
        })
        assert saved["project_name"] == "Veribite Checkout"

        hist = report_service.get_all_runs(q="veribite")
        assert len(hist["runs"]) == 1
        assert hist["runs"][0]["project_name"] == "Veribite Checkout"
    finally:
        request_owner.reset(token)


def test_crash_diagnosis_computation_and_worker_delta_merge(isolated_db):
    from backend.core.crash_diagnosis import compute_crash_diagnosis
    from backend.core.load_engine import LoadEngine

    part_records = {
        "0": {
            "part_name": "GET /api/health",
            "method": "GET",
            "path": "/api/health",
            "total_requests": 200,
            "failed_requests": 0,
            "latency_sum": 4000.0,
            "latency_samples": 200,
            "latency_hist": {20: 190, 45: 10},
            "status_codes": {},
            "first_error_at_sec": None,
            "first_error_at_vus": None,
        },
        "1": {
            "part_name": "Step 2: POST /api/checkout",
            "method": "POST",
            "path": "/api/checkout",
            "total_requests": 100,
            "failed_requests": 25,
            "latency_sum": 15000.0,
            "latency_samples": 100,
            "latency_hist": {120: 80, 950: 20},
            "status_codes": {"503": 20, "TIMEOUT": 5},
            "first_error_at_sec": 12,
            "first_error_at_vus": 180,
        },
    }
    ts = [
        {"elapsed_sec": 5, "vus": 80, "rps": 50, "p95_ms": 40.0, "error_pct": 0.0},
        {"elapsed_sec": 10, "vus": 140, "rps": 70, "p95_ms": 110.0, "error_pct": 0.0},
        {"elapsed_sec": 12, "vus": 180, "rps": 60, "p95_ms": 950.0, "error_pct": 12.5},
    ]
    breakdown, summary = compute_crash_diagnosis(
        part_records,
        timeseries=ts,
        peak_vus=180,
        target_vus=200,
        total_requests=300,
        failed_requests=25,
        overall_p95_ms=950.0,
        p95_ceiling_ms=1500.0,
    )
    # Worst failing endpoint ranked first
    assert breakdown[0]["part_name"] == "Step 2: POST /api/checkout"
    assert breakdown[0]["health_status"] == "CRASHING"
    assert breakdown[0]["first_error_at_sec"] == 12
    assert breakdown[0]["first_error_at_vus"] == 180
    assert breakdown[0]["status_codes"] == {"503": 20, "TIMEOUT": 5}
    assert "overloaded" in breakdown[0]["plain_reason"].lower()

    assert summary["status_label"] == "CRASHED / FAILING"
    assert summary["safe_max_vus"] == 140
    assert summary["first_error_vus"] == 180
    assert summary["first_error_sec"] == 12
    assert summary["primary_error_code"] == "503"
    assert "180 users" in summary["plain_english_verdict"]

    # Also verify LoadEngine._apply_worker_delta merges earliest failure point cleanly across workers
    engine = LoadEngine()
    engine._part_stats = {}
    engine._apply_worker_delta({
        "worker_id": 0,
        "total_requests": 10,
        "failed_requests": 2,
        "part_deltas": {
            "0": {
                "part_name": "GET /",
                "method": "GET",
                "path": "/",
                "total": 10,
                "failed": 2,
                "lat_sum": 500.0,
                "lat_count": 10,
                "buckets": [(50, 8), (600, 2)],
                "codes": {"500": 2},
                "first_err_sec": 14,
                "first_err_vus": 120,
            }
        },
    })
    engine._apply_worker_delta({
        "worker_id": 1,
        "total_requests": 10,
        "failed_requests": 1,
        "part_deltas": {
            "0": {
                "part_name": "GET /",
                "method": "GET",
                "path": "/",
                "total": 10,
                "failed": 1,
                "lat_sum": 300.0,
                "lat_count": 10,
                "buckets": [(30, 9), (700, 1)],
                "codes": {"500": 1},
                "first_err_sec": 9,
                "first_err_vus": 80,
            }
        },
    })
    assert engine._part_stats["0"]["first_error_at_sec"] == 9
    assert engine._part_stats["0"]["first_error_at_vus"] == 80
    assert engine._part_stats["0"]["status_codes"]["500"] == 3

    # Persist into SQLite test_runs and confirm retrieval
    token = request_owner.set("owner_crash_1")
    try:
        saved = report_service.save_run({
            "run_id": "RUN-CRASH-001",
            "target_url": "https://api.veribite.vercel.app",
            "project_name": "Veribite API",
            "total_requests": 300,
            "failed_requests": 25,
            "failure_breakdown": breakdown,
            "crash_summary": summary,
        })
        fetched = report_service.get_run("RUN-CRASH-001")
        assert fetched["failure_breakdown"][0]["part_name"] == "Step 2: POST /api/checkout"
        assert fetched["crash_summary"]["safe_max_vus"] == 140
    finally:
        request_owner.reset(token)


def test_timeline_points_downsampling_and_persistence(isolated_db):
    token = request_owner.set("owner_timeline_1")
    try:
        dense_points = [
            {"t": sec, "vus": 10 + (sec % 90), "rps": 40, "p95_ms": 25.0 + sec * 0.1, "error_pct": 0.0 if sec < 900 else 6.2}
            for sec in range(1500)
        ]
        saved = report_service.save_run({
            "run_id": "RUN-TL-001",
            "target_url": "https://veribite.vercel.app",
            "project_name": "Veribite Health",
            "total_requests": 60000,
            "status_2xx": 59000,
            "timeline_points": dense_points,
        })
        assert len(saved["timeline_points"]) == 600
        assert saved["timeline_points"][0]["t"] == 0
        assert saved["timeline_points"][-1]["t"] == 1499
        assert saved["timeline_points"][-1]["error_pct"] == 6.2

        # Fallback from legacy timeseries when timeline_points omitted
        saved_legacy = report_service.save_run({
            "run_id": "RUN-TL-LEGACY",
            "target_url": "https://veribite.vercel.app",
            "total_requests": 100,
            "timeseries": [{"elapsed_sec": 1, "vus": 20, "rps": 15, "p95_ms": 30.0, "error_pct": 0.0}],
        })
        assert saved_legacy["timeline_points"] == [{"t": 1, "vus": 20, "rps": 15, "p95_ms": 30.0, "error_pct": 0.0}]
    finally:
        request_owner.reset(token)


def test_pdf_report_endpoint_returns_valid_vector_pdf_and_enforces_owner(isolated_db):
    from backend.core.crash_diagnosis import compute_crash_diagnosis

    breakdown, summary = compute_crash_diagnosis(
        [{
            "part_name": "Step 2: POST /api/checkout",
            "method": "POST",
            "path": "/api/checkout",
            "total_requests": 120,
            "failed_requests": 24,
            "latency_sum": 18000.0,
            "latency_samples": 120,
            "p95_latency_ms": 920.0,
            "status_codes": {"503": 20, "TIMEOUT": 4},
            "first_error_at_sec": 12,
            "first_error_at_vus": 150,
        }],
        timeseries=[
            {"elapsed_sec": 0, "vus": 25, "rps": 20, "p95_ms": 40.0, "error_pct": 0.0},
            {"elapsed_sec": 6, "vus": 90, "rps": 55, "p95_ms": 85.0, "error_pct": 0.0},
            {"elapsed_sec": 12, "vus": 150, "rps": 45, "p95_ms": 920.0, "error_pct": 20.0},
        ],
        peak_vus=150,
        target_vus=150,
        total_requests=120,
        failed_requests=24,
        overall_p95_ms=920.0,
    )

    try:
        owner_client = _client_for_user("pdf_owner")
        token = request_owner.set("pdf_owner")
        try:
            report_service.save_run({
                "run_id": "RUN-PDF-001",
                "target_url": "https://api.veribite.vercel.app",
                "project_name": "Veribite API",
                "mode": "Step-Ramp",
                "target_vus": 150,
                "peak_vus": 150,
                "duration_sec": 30,
                "elapsed_sec": 12,
                "peak_rps": 55,
                "avg_rps": 40,
                "p95_ms": 920.0,
                "error_pct": 20.0,
                "total_requests": 120,
                "status_2xx": 96,
                "status_5xx": 20,
                "timeout_count": 4,
                "failed_requests": 24,
                "failure_breakdown": breakdown,
                "crash_summary": summary,
                "timeline_points": [
                    {"t": 0, "vus": 25, "rps": 20, "p95_ms": 40.0, "error_pct": 0.0},
                    {"t": 6, "vus": 90, "rps": 55, "p95_ms": 85.0, "error_pct": 0.0},
                    {"t": 12, "vus": 150, "rps": 45, "p95_ms": 920.0, "error_pct": 20.0},
                ],
            })
        finally:
            request_owner.reset(token)

        res = owner_client.get("/api/reports/RUN-PDF-001/pdf")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/pdf")
        assert "pusher-veribite-api-RUN-PDF-001.pdf" in res.headers.get("content-disposition", "")
        assert res.content.startswith(b"%PDF-")
        assert len(res.content) > 3000

        # Another operator must get 404
        other_client = _client_for_user("pdf_intruder")
        res_other = other_client.get("/api/reports/RUN-PDF-001/pdf")
        assert res_other.status_code == 404
    finally:
        app.dependency_overrides.clear()

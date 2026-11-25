import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.report_service import detect_knee_of_curve, init_db, save_run, get_db_connection

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database has clean test runs for report testing."""
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM test_runs;")
    conn.close()

    run1 = {
        "run_id": "RUN-T101",
        "timestamp": "12:00:00",
        "target_url": "https://api.testsite.dev",
        "guard_id": "PG-TEST-01",
        "mode": "Step-Ramp",
        "target_vus": 100,
        "peak_vus": 100,
        "duration_sec": 30,
        "elapsed_sec": 30,
        "peak_rps": 500,
        "avg_rps": 400,
        "p95_ms": 120.0,
        "error_pct": 0.0,
        "total_requests": 15000,
        "status_2xx": 15000,
        "status_429": 0,
        "status_5xx": 0,
        "bytes_discarded_mb": 0.5,
        "ram_mb": 70.0,
        "verdict": "PASSED",
        "status_label": "PASSED (Completed 30s)",
        "knee_vus": 80,
        "knee_rps": 450,
        "knee_p95_ms": 110.0,
        "bottleneck_summary": "Optimal knee detected at 80 VUs.",
        "timeseries": [{"elapsed_sec": 10, "vus": 50, "rps": 200, "p95_ms": 80, "error_pct": 0}],
        "step_metrics": [],
    }
    run2 = {
        "run_id": "RUN-T102",
        "timestamp": "12:05:00",
        "target_url": "https://api.testsite.dev",
        "guard_id": "PG-TEST-01",
        "mode": "Steady-Crowd",
        "target_vus": 200,
        "peak_vus": 200,
        "duration_sec": 30,
        "elapsed_sec": 30,
        "peak_rps": 800,
        "avg_rps": 750,
        "p95_ms": 95.0,
        "error_pct": 0.0,
        "total_requests": 24000,
        "status_2xx": 24000,
        "status_429": 0,
        "status_5xx": 0,
        "bytes_discarded_mb": 0.8,
        "ram_mb": 90.0,
        "verdict": "PASSED",
        "status_label": "PASSED (Completed 30s)",
        "knee_vus": 180,
        "knee_rps": 780,
        "knee_p95_ms": 90.0,
        "bottleneck_summary": "Optimal knee detected at 180 VUs.",
        "timeseries": [{"elapsed_sec": 10, "vus": 100, "rps": 400, "p95_ms": 70, "error_pct": 0}],
        "step_metrics": [],
    }
    save_run(run1)
    save_run(run2)


def test_detect_knee_of_curve_mathematical_inflection():
    """Verify detect_knee_of_curve pinpoints the inflection step where latency slope spikes."""
    timeseries = [
        {"elapsed_sec": 5, "vus": 50, "rps": 150, "p95_ms": 40.0, "error_pct": 0.0},
        {"elapsed_sec": 10, "vus": 100, "rps": 300, "p95_ms": 45.0, "error_pct": 0.0},
        {"elapsed_sec": 20, "vus": 200, "rps": 600, "p95_ms": 55.0, "error_pct": 0.0},
        {"elapsed_sec": 30, "vus": 300, "rps": 900, "p95_ms": 70.0, "error_pct": 0.0},
        {"elapsed_sec": 40, "vus": 400, "rps": 1050, "p95_ms": 175.0, "error_pct": 0.5},
        {"elapsed_sec": 50, "vus": 500, "rps": 1100, "p95_ms": 380.0, "error_pct": 2.5},
    ]

    knee = detect_knee_of_curve(timeseries, target_vus=500, p95_ceiling_ms=1000.0)

    assert knee["knee_vus"] in (300, 400)
    assert knee["knee_rps"] >= 900
    assert knee["knee_p95_ms"] > 0
    assert "Optimal Knee detected" in knee["bottleneck_summary"]
    assert len(knee["ramp_steps"]) == len(timeseries)


def test_empty_state_returns_null_scorecard_and_empty_runs():
    """Verify that when test_runs is empty, /api/history returns runs: [] and scorecard: None."""
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM test_runs;")
    conn.close()

    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert data["runs"] == []
    assert data["scorecard"] is None


def test_get_history_filtering_and_scorecard():
    """Verify GET /api/history returns runs and scorecard, with mode and query filtering."""
    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert "runs" in data
    assert "scorecard" in data
    assert len(data["runs"]) == 2

    # Filter by mode
    res_mode = client.get("/api/history?mode=Step-Ramp")
    assert res_mode.status_code == 200
    runs_mode = res_mode.json()["runs"]
    assert len(runs_mode) == 1
    assert "step-ramp" in runs_mode[0]["mode"].lower()

    # Filter by query
    res_q = client.get("/api/history?q=RUN-T101")
    assert res_q.status_code == 200
    runs_q = res_q.json()["runs"]
    assert len(runs_q) == 1
    assert runs_q[0]["run_id"] == "RUN-T101"


def test_get_single_run_report():
    """An older report keeps its measurements but lacks evidence for a capacity recommendation."""
    res = client.get("/api/reports/RUN-T101")
    assert res.status_code == 200
    report = res.json()
    assert report["run_id"] == "RUN-T101"
    assert report["knee_vus"] == 0
    assert report["bottleneck_summary"] == "Capacity unavailable"
    assert report["peak_rps"] > 0
    assert "timeseries" in report
    assert len(report["timeseries"]) > 0

    # Non-existent run should 404
    res_404 = client.get("/api/reports/RUN-999999")
    assert res_404.status_code == 404


def test_compare_two_runs():
    """Verify POST /api/reports/compare computes accurate differential deltas and verdict."""
    payload = {
        "base_run_id": "RUN-T101",
        "candidate_run_id": "RUN-T102",
    }
    res = client.post("/api/reports/compare", json=payload)
    assert res.status_code == 200
    diff = res.json()
    assert diff["base_run"]["run_id"] == "RUN-T101"
    assert diff["candidate_run"]["run_id"] == "RUN-T102"
    assert "deltas" in diff
    assert diff["deltas"]["peak_rps_delta"] > 0
    assert diff["deltas"]["p95_ms_delta"] < 0
    assert "knee_vus_delta" not in diff["deltas"]
    assert diff["overall_verdict"] == "IMPROVED"
    assert "summary" in diff


def test_export_report_attachment():
    """Verify GET /api/reports/{run_id}/export returns downloadable attachment."""
    res = client.get("/api/reports/RUN-T101/export")
    assert res.status_code == 200
    assert "attachment" in res.headers.get("content-disposition", "")
    assert "report_RUN-T101.json" in res.headers.get("content-disposition", "")
    exported = res.json()
    assert exported["run_id"] == "RUN-T101"
    assert exported["knee_vus"] == 0 and exported["bottleneck_summary"] == "Capacity unavailable"


def test_load_engine_auto_persists_to_sqlite():
    """Verify completed load test run is automatically persisted into SQLite database."""
    with TestClient(app) as client:
        verify_report_persistence(client)


def verify_report_persistence(client):
    # Verify sandbox target first
    verify_res = client.post("/api/target/verify", json={
        "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        "guard_id": "PG-TEST-STAGE5",
        "is_sandbox": True
    })
    assert verify_res.status_code == 200

    # Start a quick 2-second load run
    start_res = client.post("/api/load/start", json={
        "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        "traffic_mode": "steady_crowd",
        "target_vus": 10,
        "duration_sec": 2,
        "is_sandbox": True,
    })
    assert start_res.status_code == 200
    run_id = start_res.json()["run_id"]

    # Stop run
    stop_res = client.post("/api/load/stop")
    assert stop_res.status_code == 200

    # Check history
    hist_res = client.get("/api/history")
    assert hist_res.status_code == 200
    runs = hist_res.json()["runs"]
    persisted_ids = [r["run_id"] for r in runs]
    assert run_id in persisted_ids


def test_export_strips_internal_fields_and_sets_utc_timestamp():
    save_run({
        "run_id": "RUN-EXPORT-CLEAN",
        "timestamp": "12:49:55",
        "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        "mode": "Step Ramp",
        "target_vus": 873,
        "peak_vus": 175,
        "duration_sec": 30,
        "elapsed_sec": 6,
        "peak_rps": 61,
        "avg_rps": 42,
        "p95_ms": 5344.0,
        "error_pct": 11.4,
        "metrics_scope": "whole_run",
        "total_requests": 255,
        "status_2xx": 226,
        "status_3xx": 0,
        "status_4xx": 0,
        "status_429": 0,
        "status_5xx": 0,
        "status_other": 29,
        "timeout_count": 29,
        "network_error_count": 0,
        "failed_requests": 29,
        "p95_ceiling_ms": 5000.0,
        "max_error_pct": 5.0,
        "effective_p95_ceiling_ms": 5000.0,
        "effective_max_error_pct": 5.0,
        "ram_limit_mb": 500,
        "request_timeout_sec": 5.0,
        "cache_bust": True,
        "use_journey": False,
        "is_sandbox": True,
        "latency_breakdown": {"p50_ms": 2100.0, "p90_ms": 4800.0, "p95_ms": 5344.0, "p99_ms": 5490.0, "max_ms": 5510.0},
        "verdict": "CIRCUIT_BREAKER",
        "status_label": "CIRCUIT BREAKER (TRIPPED (rolling p95 latency threshold))",
        "capacity_checked": True,
        "timeseries": [
            {"elapsed_sec": 1, "vus": 175, "rps": 59, "p95_ms": 1045.0, "error_pct": 0.0},
            {"elapsed_sec": 5, "vus": 175, "rps": 54, "p95_ms": 5376.4, "error_pct": 53.7},
        ],
        "started_at": "2026-11-25T12:49:49Z",
        "ended_at_iso": "2026-11-25T12:49:55Z",
    })
    res = client.get("/api/reports/RUN-EXPORT-CLEAN/export")
    assert res.status_code == 200
    assert res.headers["content-disposition"] == 'attachment; filename="report_RUN-EXPORT-CLEAN.json"'
    exported = res.json()
    for forbidden in (
        "user_id", "timeseries_json", "step_metrics_json", "latency_breakdown_json", "steps_json",
        "id", "target", "guardToken", "peakVus", "duration", "peakRps", "p95", "status", "verdictCategory",
    ):
        assert forbidden not in exported
    assert exported["exported_at"].endswith("Z") and "T" in exported["exported_at"]
    assert exported["exported_at"] != "12:49:55"
    assert exported["timeout_count"] == 29 and exported["status_other"] == 29 and exported["failed_requests"] == 29
    assert exported["p95_ceiling_ms"] == 5000.0 and exported["request_timeout_sec"] == 5.0
    assert exported["latency_breakdown"]["p95_ms"] == 5344.0
    assert len(exported["steps"]) == 1 and exported["steps"][0]["vus"] == 175
    assert "175 VUs" in exported["capacity_reason"]


def test_verdict_filter_aliases_and_global_scorecard():
    save_run({
        "run_id": "RUN-TRIPPED-01",
        "created_at": 9999999999.0,
        "verdict": "CIRCUIT_BREAKER",
        "status_label": "CIRCUIT BREAKER (TRIPPED (rolling p95 latency threshold))",
        "p95_ms": 5344.4,
        "error_pct": 11.4,
        "metrics_scope": "whole_run",
        "total_requests": 255,
    })
    for alias in ("CIRCUIT_TRIPPED", "CIRCUIT_BREAKER", "CIRCUIT BREAKER"):
        res = client.get(f"/api/history?verdict={alias}")
        assert res.status_code == 200
        data = res.json()
        assert [r["run_id"] for r in data["runs"]] == ["RUN-TRIPPED-01"]
        assert data["scorecard"]["run_id"] == "RUN-TRIPPED-01"
        assert data["global_scorecard"]["run_id"] == "RUN-T102"
        assert data["latest_run"]["run_id"] == "RUN-TRIPPED-01"
        assert data["latest_run"]["p95_ms"] == 5344.4


def test_compare_two_runs_regression_and_comparability_warnings():
    base = save_run({
        "run_id": "RUN-CMP-BASE",
        "target_url": "https://api.testsite.dev/v1",
        "mode": "Step-Ramp",
        "target_vus": 100,
        "peak_rps": 100,
        "p95_ms": 100.0,
        "error_pct": 0.0,
        "total_requests": 1000,
        "metrics_scope": "whole_run",
        "verdict": "PASSED",
    })
    assert base["p95_ms"] == 100.0
    # Retry returns the same normalized dict
    assert save_run({"run_id": "RUN-CMP-BASE", "peak_rps": 999}) == base

    # +500% p95 latency regression with +5% RPS jitter must NEVER be IMPROVED
    save_run({
        "run_id": "RUN-CMP-REGR",
        "target_url": "https://api.testsite.dev/v2",
        "mode": "Steady Crowd",
        "target_vus": 200,
        "peak_rps": 105,
        "p95_ms": 600.0,
        "error_pct": 5.0,
        "total_requests": 1050,
        "metrics_scope": "whole_run",
        "verdict": "CIRCUIT_BREAKER",
    })
    diff = client.post("/api/reports/compare", json={
        "base_run_id": "RUN-CMP-BASE",
        "candidate_run_id": "RUN-CMP-REGR",
    }).json()
    assert diff["overall_verdict"] == "REGRESSED"
    assert diff["deltas"]["error_pct_delta"] == 5.0
    assert diff["deltas"]["requests_delta"] == 50
    assert diff["comparable"] is False
    assert len(diff["comparability_warnings"]) == 4

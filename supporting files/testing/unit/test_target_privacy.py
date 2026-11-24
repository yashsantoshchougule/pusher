import asyncio
import importlib.util

import httpx
import pytest
from fastapi import FastAPI

from backend.core import database, load_engine as engine_module, report_service, target_service
from backend.core.config import settings
from backend.main import app


@pytest.fixture
def scratch_db(monkeypatch, tmp_path):
    path = tmp_path / "targets.sqlite"
    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_all_tables()
    return path


@pytest.mark.asyncio
async def test_verified_query_reaches_only_runtime_transport(scratch_db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "offline_dev", True)
    engine = engine_module.LoadEngine()
    monkeypatch.setattr("backend.api.load_router.load_engine", engine)
    base = "https://target.example.invalid/orders"
    secret = "synthetic-target-query"
    url = base + "?session=" + secret
    target_app = FastAPI()

    async def resolve(*args):
        return ["93.184.216.34"]

    monkeypatch.setattr(target_service, "resolve_addresses", resolve)
    monkeypatch.setattr(target_service, "target_client", lambda *a, **kw:
                        httpx.AsyncClient(transport=httpx.ASGITransport(app=target_app)))
    seen = []

    def respond(request):
        seen.append(request.url)
        return httpx.Response(200)

    monkeypatch.setattr(engine_module, "target_client", lambda *a, **kw:
                        httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        issued = (await client.post("/api/target/generate-guard", json={"target_url": url})).raise_for_status()
        assert secret not in issued.text
        assert issued.json()["target_url"] == base
        path = tmp_path / "guard_fixture.py"
        path.write_bytes(issued.json()["content"].encode())
        spec = importlib.util.spec_from_file_location("guard_fixture", path)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        guard.setup_pusher_guard(target_app)
        verify = {"guard_id": issued.json()["guard_id"], "target_url": url}
        verified = (await client.post("/api/target/verify", json=verify)).raise_for_status()
        assert verified.json()["requires_target_query"] and secret not in verified.text
        status = (await client.get("/api/target/status")).raise_for_status().json()
        assert status["target_url"] == base and status["requires_target_query"]

        start = {"target_url": base, "duration_sec": 1, "target_vus": 1, "cache_bust": False}
        assert (await client.post("/api/load/start", json=start)).status_code == 422
        assert not seen
        started = (await client.post("/api/load/start", json={**start, "target_url": url})).raise_for_status()
        await asyncio.wait_for(engine._master_task, 3)
        assert seen and all(str(item) == url for item in seen)
        run_path = "/api/reports/" + started.json()["run_id"]
        for endpoint in (run_path, run_path + "/export", "/api/history"):
            response = (await client.get(endpoint)).raise_for_status()
            assert base in response.text and secret not in response.text

        cleared = (await client.post("/api/target/verify", json={**verify, "target_url": base})).raise_for_status()
        assert not cleared.json()["requires_target_query"]
        assert (await client.post("/api/load/start", json=start)).status_code == 200
        await engine.stop()

    for path in scratch_db.parent.glob(scratch_db.name + "*"):
        assert secret.encode() not in path.read_bytes()


def test_legacy_target_reads_and_scrub(scratch_db):
    base = "https://target.example.invalid/orders"
    secret = "synthetic-target-legacy"
    url = base + "?session=" + secret
    report_service.save_run({"run_id": "legacy-target"})
    conn = database.get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE active_target_state SET target_url = ?", (url,))
            conn.execute("UPDATE test_runs SET target_url = ? WHERE run_id = 'legacy-target'", (url,))
    finally:
        conn.close()
    target = database.db_get_active_target()
    assert target["target_url"] == base and target["requires_target_query"]
    assert report_service.get_run("legacy-target")["target_url"] == base
    assert report_service.get_all_runs(q=secret)["runs"] == []
    assert report_service.get_all_runs(q="orders")["runs"][0]["target_url"] == base
    database.scrub_legacy_journey_inputs()
    assert target == database.db_get_active_target()
    for path in scratch_db.parent.glob(scratch_db.name + "*"):
        assert secret.encode() not in path.read_bytes()

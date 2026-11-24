import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from backend.core import database, load_engine as engine_module, report_service
from backend.core.config import settings
from backend.main import app


@pytest.mark.parametrize("invalid, field", [
    ({"headers": ["invalid"]}, "headers"),
    ({"headers": {"X-Test": "not\r\nsafe"}}, "headers"),
    ({"method": "invalid method"}, "method"),
    ({"expected_status": "200"}, "expected_status"),
])
def test_invalid_steps_rejected_at_each_entry_point(monkeypatch, tmp_path, invalid, field):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "journey-validation.sqlite")
    database.init_all_tables()
    monkeypatch.setattr(settings, "offline_dev", True)
    target = "http://127.0.0.1:8000/api/sandbox/target"
    steps = [{"path": "/api/sandbox/target", **invalid}]
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/target/verify", json={
            "target_url": target, "is_sandbox": True,
        }).status_code == 200
        for path, params in (
            ("/api/journey/save", {"steps": steps}),
            ("/api/journey/dry-run", {"steps": steps}),
            ("/api/load/start", {
                "target_url": target, "is_sandbox": True, "use_journey": True,
                "journey_steps": steps, "target_vus": 1, "duration_sec": 1,
            }),
        ):
            response = client.post(path, json=params)
            assert response.status_code == 422
            assert response.json()["detail"] == f"Step 1: invalid {field}."
        assert client.get("/api/journey").json()["steps"] == []
        assert not engine_module.load_engine.is_running


@pytest.mark.parametrize("worker_error", [False, True])
@pytest.mark.asyncio
async def test_zero_requests_and_worker_errors_fail_the_report(monkeypatch, worker_error):
    @asynccontextmanager
    async def mock_client(*args, **kwargs):
        yield object()

    async def worker(client, vu):
        if worker_error:
            raise RuntimeError("unexpected worker failure")

    monkeypatch.setattr(engine_module, "target_client", mock_client)
    engine = engine_module.LoadEngine()
    monkeypatch.setattr(engine, "_vu_journey_worker", worker)
    run_id = await engine.start(
        "https://example.invalid", "steady_crowd", 1, 1, use_journey=True,
        journey_steps=[{"path": "/"}],
    )
    await asyncio.wait_for(engine._master_task, 2)
    report = report_service.get_run(run_id)
    assert report["total_requests"] == 0
    assert report["verdict"] == "FAILED"
    expected = "Worker error" if worker_error else "No requests completed"
    assert expected in report["status_label"]

import asyncio

import httpx
import pytest

from backend.core import load_engine as engine_module, report_service


@pytest.mark.asyncio
@pytest.mark.parametrize("mode, cap, journey", [("step_ramp", 10, False), ("steady_crowd", 2, True)])
async def test_report_records_observed_peak_and_resets_on_restart(monkeypatch, mode, cap, journey):
    active = peak = 0
    two_active = asyncio.Event()
    release = asyncio.Event()

    async def respond(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 2:
            two_active.set()
        try:
            await release.wait()
            return httpx.Response(200)
        finally:
            active -= 1

    def target_client(*args, connections, **kwargs):
        assert connections == cap
        return httpx.AsyncClient(transport=httpx.MockTransport(respond))

    monkeypatch.setattr(engine_module, "get_os_fd_cap", lambda: cap)
    monkeypatch.setattr(engine_module, "target_client", target_client)
    engine = engine_module.LoadEngine()
    run_id = await engine.start(
        "https://example.invalid", mode, 10, 1, use_journey=journey,
        journey_steps=[{"path": "/resource"}],
    )
    try:
        await asyncio.wait_for(two_active.wait(), 1)
        assert engine.get_status()["active_vus"] == 2
        if journey:
            await engine.stop()
        else:
            release.set()
            await asyncio.wait_for(engine._master_task, 2)
        assert active == 0
        report = report_service.get_run(run_id)
        assert report["target_vus"] == 10
        assert report["peak_vus"] == report["peakVus"] == peak == 2

        restart = await engine.start("https://example.invalid", mode, 10, 1)
        await engine.stop()
        stopped = report_service.get_run(restart)
        assert stopped["peak_vus"] == stopped["knee_vus"] == 0
    finally:
        release.set()
        await engine.stop()


@pytest.mark.asyncio
async def test_step_ramp_spawns_workers_dynamically_without_idle_polling(monkeypatch):
    async def respond(request):
        await asyncio.sleep(0.02)
        return httpx.Response(200)

    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ))
    engine = engine_module.LoadEngine()
    await engine.start("https://example.invalid", "step_ramp", 100, 10)
    try:
        await asyncio.sleep(0.05)
        assert len(engine._worker_tasks) == 20
        assert engine.get_status()["active_vus"] == 20
    finally:
        await engine.stop()


def test_load_router_loopback_advisory_and_fd_cap(monkeypatch):
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from backend.api import auth_deps, load_router
    from backend.core.jwks_verifier import AuthenticatedUser
    from backend.main import app

    monkeypatch.setattr(load_router, "get_os_fd_cap", lambda: 50)
    monkeypatch.setattr(auth_deps, "resolve_operator", AsyncMock(
        return_value=AuthenticatedUser(user_id="default_test_user", email_confirmed=True)
    ))
    with TestClient(app) as client:
        assert client.post("/api/target/verify", json={
            "target_url": "http://127.0.0.1:8000/api/sandbox/target", "is_sandbox": True,
        }).status_code == 200

        too_many = client.post("/api/load/start", json={
            "target_url": "http://127.0.0.1:8000/api/sandbox/target",
            "is_sandbox": True,
            "target_vus": 60,
            "duration_sec": 5,
            "ram_limit_mb": 500,
        })
        assert too_many.status_code == 422
        assert "exceeds" in too_many.json()["detail"].lower()

        started = client.post("/api/load/start", json={
            "target_url": "http://127.0.0.1:8000/api/sandbox/target",
            "is_sandbox": True,
            "target_vus": 10,
            "duration_sec": 5,
        })
        assert started.status_code == 200
        body = started.json()
        assert body["same_process_loopback"] is True
        assert body["advisory"]
        status = client.get("/api/load/status").json()
        assert status["same_process_loopback"] is True
        assert status["advisory"]
        client.post("/api/load/stop")

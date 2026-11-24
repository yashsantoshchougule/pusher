import asyncio
from contextlib import asynccontextmanager
import math
import time

import httpx
import pytest

from backend.core import database, load_engine as engine_module
from backend.core.config import settings
from backend.main import app


@pytest.mark.asyncio
async def test_start_uses_guard_deadline_and_closes_inflight_stream(monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", True)
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(settings, "host", "127.0.0.1")
    monkeypatch.setattr(settings, "port", 8000)
    target = "http://127.0.0.1:8000/api/sandbox/target"
    started = []
    closed = asyncio.Event()

    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            closed.set()

    def respond(request):
        started.append(time.time())
        return httpx.Response(200, stream=StalledBody())

    @asynccontextmanager
    async def target_client(*args, **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            yield client

    engine = engine_module.LoadEngine()
    monkeypatch.setattr(engine_module, "target_client", target_client)
    monkeypatch.setattr("backend.api.load_router.load_engine", engine)
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        verified = await client.post("/api/target/verify", json={"target_url": target, "is_sandbox": True})
        assert verified.status_code == 200
        guard = database.db_get_active_target("offline:operator")
        deadline = math.ceil(time.time()) + 1
        database.db_save_active_target({**guard, "expires_at": deadline}, "offline:operator")
        launch = await client.post("/api/load/start", json={
            "target_url": target, "is_sandbox": True, "target_vus": 1,
            "duration_sec": 10, "traffic_mode": "steady_crowd",
        })
        assert launch.status_code == 200
        try:
            await asyncio.wait_for(asyncio.shield(engine._master_task), 4)
            assert started and max(started) < deadline
            assert closed.is_set()
            assert not engine.is_running
            result = await client.get("/api/reports/" + launch.json()["run_id"])
            assert "Guard verification expired" in result.json()["status_label"]
        finally:
            await engine.stop()

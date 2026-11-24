import asyncio
from contextlib import asynccontextmanager, suppress
from types import SimpleNamespace

import httpx
import pytest

from backend.api import auth_deps, journey_router, load_router
from backend.core import database, journey_service, target_service
from backend.core.config import settings
from backend.core.dry_run_control import active_dry_runs
from backend.core.jwks_verifier import AuthenticatedUser
from backend.core.load_engine import LoadEngine
from backend.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [None, "timeout", "guard_expired", "guard_revoked", "stopped"])
async def test_dry_run_lifetime_and_cleanup(monkeypatch, tmp_path, reason):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "dry-run.sqlite")
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(settings, "port", 8000)
    engine = LoadEngine()
    engine.owner_id = "other-operator"
    engine.run_id = "RUN-OTHER"
    engine.is_running = True
    monkeypatch.setattr(load_router, "load_engine", engine)

    now = 0.0
    epoch = 1_800_000_000
    loop = asyncio.get_running_loop()
    clock = SimpleNamespace(time=lambda: epoch + now, perf_counter=lambda: now)
    monkeypatch.setattr(loop, "time", lambda: now)
    monkeypatch.setattr(journey_service, "time", clock)
    monkeypatch.setattr(target_service, "time", clock)
    monkeypatch.setattr(journey_router, "perf_counter", lambda: now)

    async def synthetic_operator(request):
        return AuthenticatedUser(
            user_id=request.headers.get("x-test-owner", "dry-run-owner"), email_confirmed=True,
        )

    monkeypatch.setattr(auth_deps, "resolve_operator", synthetic_operator)
    calls = []
    waiting = asyncio.Event()
    drained = asyncio.Event()
    clients = []
    target = "http://127.0.0.1:8000/api/sandbox/target"

    async def stall():
        waiting.set()
        try:
            await asyncio.Event().wait()
        finally:
            drained.set()

    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await stall()
            yield b""

        async def aclose(self):
            assert drained.is_set()

    def respond(request):
        nonlocal now
        assert str(request.url) == target
        calls.append(now)
        if reason == "timeout":
            if len(calls) == 3:
                return httpx.Response(200, stream=StalledBody())
            now += 4
        if reason in {"guard_revoked", "stopped"} and len(calls) == 2:
            return httpx.Response(200, stream=StalledBody())
        return httpx.Response(200)

    class BoundaryClient(httpx.AsyncClient):
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            async with super().stream(*args, **kwargs) as response:
                yield response
            if reason == "guard_expired" and len(calls) == 2:
                await stall()

    def target_client(*args, **kwargs):
        client = BoundaryClient(transport=httpx.MockTransport(respond))
        clients.append(client)
        return client

    monkeypatch.setattr(journey_service, "target_client", target_client)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        verified = (await client.post("/api/target/verify", json={
            "target_url": target, "is_sandbox": True,
        })).raise_for_status().json()
        stale = await client.post("/api/journey/dry-run", json={
            "steps": [{"path": "/api/sandbox/target"}], "guard_id": "stale-guard",
        })
        assert stale.status_code == 409 and not clients
        if reason == "guard_expired":
            store = database.db_get_active_target("dry-run-owner")
            database.db_save_active_target({**store, "expires_at": epoch + 5}, "dry-run-owner")

        background = asyncio.all_tasks()
        draft = {
            "steps": [{"path": "/api/sandbox/target", "step_id": i} for i in range(1, 5)],
            "cache_bust": False,
            "dry_run_id": "fixture-dry-run",
            "guard_id": verified["guard_id"],
        }
        dry_run = asyncio.create_task(client.post("/api/journey/dry-run", json=draft))
        try:
            if reason:
                # Drive the event loop without a real clock timeout or sleep.
                for _ in range(100):
                    if waiting.is_set():
                        break
                    await asyncio.sleep(0)
                assert waiting.is_set()
                if reason == "timeout":
                    assert calls == [0, 4, 8]
                    now = 10
                elif reason == "guard_expired":
                    assert calls == [0, 0]
                    now = 5
                elif reason == "guard_revoked":
                    (await client.post("/api/target/kill")).raise_for_status()
                else:
                    wrong_id = await client.post("/api/load/stop", json={"run_id": "RUN-OTHER"})
                    assert wrong_id.status_code == 403 and not drained.is_set()
                    outsider = await client.post("/api/load/stop", headers={"x-test-owner": "unrelated"})
                    assert outsider.status_code == 403 and not drained.is_set()
                    assert (await client.post("/api/journey/dry-run", json=draft)).status_code == 409
                    stop = "/api/journey/dry-run/stop"
                    payload = {"dry_run_id": draft["dry_run_id"]}
                    assert (await client.post(stop, json={"dry_run_id": "different"})).status_code == 404
                    assert (await client.post(stop, json=payload, headers={"x-test-owner": "unrelated"})).status_code == 404
                    assert not drained.is_set()
                    engine.owner_id = "dry-run-owner"
                    now = 2
                    (await client.post(stop, json=payload)).raise_for_status()
                    assert clients[0].is_closed

            for _ in range(100):
                if dry_run.done():
                    break
                await asyncio.sleep(0)
            assert dry_run.done()
            outcome = (await dry_run).raise_for_status().json()
        finally:
            if not dry_run.done():
                dry_run.cancel()
                with suppress(asyncio.CancelledError):
                    await dry_run

    assert len(clients) == 1 and clients[0].is_closed
    assert not active_dry_runs
    assert asyncio.all_tasks() == background
    assert engine.is_running  # Dry-run cancellation never stopped a scheduled run.
    if reason in {"timeout", "stopped"}:
        assert outcome["total_duration_ms"] == (10_000 if reason == "timeout" else 2_000)
    if reason is None:
        assert outcome["status"] == "completed" and outcome["all_passed"]
        assert len(outcome["results"]) == len(calls) == 4
    else:
        assert outcome["status"] == "cancelled" and not outcome["all_passed"]
        assert outcome["reason"] == reason and outcome["message"]
        assert drained.is_set()
        assert len(calls) == (3 if reason == "timeout" else 2)
        assert [result["step_id"] for result in outcome["results"]] == list(range(1, len(calls)))
        assert all(result["passed"] for result in outcome["results"])

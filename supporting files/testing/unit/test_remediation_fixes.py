import asyncio
import os
import tempfile

import aiohttp.web
import pytest

from backend.core import database, load_engine as engine_module
from backend.core.config import settings
from backend.core.request_owner import request_owner


def test_ram_worker_cap_prevents_500mb_multiprocess_oversubscription():
    eng = engine_module.LoadEngine()
    eng._worker_limit = 500
    eng.ram_limit_mb = 250
    assert eng._ram_worker_cap() == 1
    assert eng._should_use_multiprocess(None) is False

    eng.ram_limit_mb = 500
    cap_500 = eng._ram_worker_cap()
    assert 2 <= cap_500 <= 4
    assert eng._should_use_multiprocess(None) is True

    eng.ram_limit_mb = 1024
    assert eng._ram_worker_cap() >= 8


@pytest.mark.asyncio
async def test_500mb_500vu_multiprocess_completes_without_ram_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "issue01.sqlite"))
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")

    async def ok_handler(_req):
        return aiohttp.web.Response(text="ok")

    app = aiohttp.web.Application()
    app.router.add_get("/api/sandbox/target", ok_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0, backlog=2048)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setenv("PUSHER_SANDBOX_ORIGINS", f'["http://127.0.0.1:{port}"]')
    monkeypatch.setattr(settings, "sandbox_origins", [f"http://127.0.0.1:{port}"])
    monkeypatch.setattr(settings, "port", port)

    token = request_owner.set("issue01_user")
    try:
        eng = engine_module.LoadEngine()
        await eng.start(
            target_url=f"http://127.0.0.1:{port}/api/sandbox/target",
            traffic_mode="steady_crowd",
            target_vus=500,
            duration_sec=3,
            ram_limit_mb=500,
            is_sandbox=True,
            use_multiprocess=True,
        )
        await asyncio.wait_for(eng._master_task, timeout=20)
        assert "RAM exceeds" not in eng.circuit_status
        assert eng.total_requests > 100
        assert eng._failed_requests == 0
    finally:
        request_owner.reset(token)
        await runner.cleanup()


def test_circuit_breaker_conn_tolerance_scales_at_high_concurrency():
    from backend.core.circuit_breakers import CircuitBreakers

    # Low VU stays strictly 5 consecutive connection drops
    b_low = CircuitBreakers(25, 8000, target_vus=1)
    assert b_low.conn_consecutive_limit == 5
    for idx in range(4):
        assert b_low.observe_status(idx * 0.1, 0, {}) is None
    assert "consecutive connection" in b_low.observe_status(0.4, 0, {})

    # High VU tolerates brief transient socket drops while rolling ratio (> 25%) still trips
    b_high = CircuitBreakers(25, 8000, target_vus=2000)
    assert b_high.conn_consecutive_limit == 40
    for idx in range(30):
        assert b_high.observe_status(idx * 0.01, 200, {}) is None
    for idx in range(10):
        assert b_high.observe_status(0.4 + idx * 0.01, 0, {}) is None
    assert b_high.observe_status(0.6, 200, {}) is None

    # True HTTP 5xx still trips strictly on 5 consecutive server crashes even at high VUs
    b_high_5xx = CircuitBreakers(25, 8000, target_vus=2000)
    for idx in range(4):
        assert b_high_5xx.observe_status(1.0 + idx * 0.01, 503, {}) is None
    assert "5 consecutive server failures" in b_high_5xx.observe_status(1.04, 503, {})


def test_cors_allows_device_id_header_and_3001_origin():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    for origin in ("http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001"):
        resp = client.options(
            "/api/load/status",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization, content-type, x-pusher-device-id",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == origin
        allowed = (resp.headers.get("access-control-allow-headers") or "").lower()
        assert "x-pusher-device-id" in allowed


@pytest.mark.asyncio
async def test_client_disconnect_guard_aborts_when_ws_drops_and_preserves_headless_and_polled_runs(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "issue05.sqlite"))
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(engine_module, "DISCONNECT_GRACE_SECONDS", 0.25)

    async def ok_handler(_req):
        return aiohttp.web.Response(text="ok")

    app = aiohttp.web.Application()
    app.router.add_get("/api/sandbox/target", ok_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0, backlog=256)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setenv("PUSHER_SANDBOX_ORIGINS", f'["http://127.0.0.1:{port}"]')
    monkeypatch.setattr(settings, "sandbox_origins", [f"http://127.0.0.1:{port}"])
    monkeypatch.setattr(settings, "port", port)

    target_url = f"http://127.0.0.1:{port}/api/sandbox/target"
    try:
        # 1. Watched run: WS disconnects without polling -> aborts within grace period
        tok1 = request_owner.set("issue05_abort_user")
        try:
            eng_abort = engine_module.LoadEngine()
            await eng_abort.start(
                target_url=target_url,
                traffic_mode="steady_crowd",
                target_vus=5,
                duration_sec=10,
                ram_limit_mb=500,
                is_sandbox=True,
                use_multiprocess=False,
            )
            engine_module.register_ws_watcher("issue05_abort_user", 5001, [eng_abort])
            await asyncio.sleep(0.05)
            engine_module.unregister_ws_watcher("issue05_abort_user", 5001, [eng_abort])
            await asyncio.wait_for(eng_abort._master_task, timeout=2.5)
            assert "CLIENT_DISCONNECTED" in eng_abort.circuit_status
        finally:
            engine_module._ACTIVE_WS_WATCHERS.pop("issue05_abort_user", None)
            request_owner.reset(tok1)

        # 2. Keepalive polling & WS reconnect prevent abort
        tok2 = request_owner.set("issue05_keepalive_user")
        try:
            eng_keep = engine_module.LoadEngine()
            await eng_keep.start(
                target_url=target_url,
                traffic_mode="steady_crowd",
                target_vus=5,
                duration_sec=10,
                ram_limit_mb=500,
                is_sandbox=True,
                use_multiprocess=False,
            )
            engine_module.register_ws_watcher("issue05_keepalive_user", 5002, [eng_keep])
            engine_module.unregister_ws_watcher("issue05_keepalive_user", 5002, [eng_keep])
            for _ in range(4):
                await asyncio.sleep(0.1)
                snap = eng_keep.get_status("issue05_keepalive_user")
                assert snap["is_running"] is True
            engine_module.register_ws_watcher("issue05_keepalive_user", 5003, [eng_keep])
            await asyncio.sleep(0.35)
            assert eng_keep.is_running is True
            await eng_keep.stop("MANUAL_ABORT")
        finally:
            engine_module._ACTIVE_WS_WATCHERS.pop("issue05_keepalive_user", None)
            request_owner.reset(tok2)

        # 3. Headless run (no WS ever connected) completes normally
        tok3 = request_owner.set("issue05_headless_user")
        try:
            eng_headless = engine_module.LoadEngine()
            await eng_headless.start(
                target_url=target_url,
                traffic_mode="steady_crowd",
                target_vus=3,
                duration_sec=1,
                ram_limit_mb=500,
                is_sandbox=True,
                use_multiprocess=False,
            )
            await asyncio.wait_for(eng_headless._master_task, timeout=3.0)
            assert eng_headless.circuit_status == "ARMED (Normal)"
        finally:
            request_owner.reset(tok3)
    finally:
        await runner.cleanup()


def test_cdn_cache_hit_header_detection():
    from backend.core.http_runner import AiohttpLoadClient

    assert AiohttpLoadClient.is_cdn_cache_hit({"CF-Cache-Status": "HIT"}) is True
    assert AiohttpLoadClient.is_cdn_cache_hit({"x-vercel-cache": "HIT"}) is True
    assert AiohttpLoadClient.is_cdn_cache_hit({"X-Cache": "Hit from cloudfront"}) is True
    assert AiohttpLoadClient.is_cdn_cache_hit({"x-fastly-request-id": "abc", "x-cache-hits": "3"}) is True
    assert AiohttpLoadClient.is_cdn_cache_hit({"CF-Cache-Status": "MISS", "x-cache": "MISS"}) is False
    assert AiohttpLoadClient.is_cdn_cache_hit({"Server": "uvicorn"}) is False


@pytest.mark.asyncio
async def test_cdn_cache_detector_flags_cached_runs_and_persists_report(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "issue06.sqlite"))
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")

    async def cdn_hit_handler(_req):
        return aiohttp.web.Response(text="cached", headers={"CF-Cache-Status": "HIT"})

    app = aiohttp.web.Application()
    app.router.add_get("/api/sandbox/target", cdn_hit_handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0, backlog=256)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    monkeypatch.setenv("PUSHER_SANDBOX_ORIGINS", f'["http://127.0.0.1:{port}"]')
    monkeypatch.setattr(settings, "sandbox_origins", [f"http://127.0.0.1:{port}"])
    monkeypatch.setattr(settings, "port", port)

    tok = request_owner.set("issue06_cdn_user")
    try:
        eng = engine_module.LoadEngine()
        run_id = await eng.start(
            target_url=f"http://127.0.0.1:{port}/api/sandbox/target",
            traffic_mode="steady_crowd",
            target_vus=5,
            duration_sec=1,
            ram_limit_mb=500,
            is_sandbox=True,
            use_multiprocess=False,
        )
        await asyncio.wait_for(eng._master_task, timeout=4.0)
        snap = eng.get_status("issue06_cdn_user")
        assert snap["total_requests"] >= 20
        assert snap["cache_hit_count"] == snap["total_requests"]
        assert snap["cache_hit_pct"] == 100.0
        assert snap["cdn_cache_warning"] is True

        from backend.core.report_service import get_all_runs, get_run
        saved = get_run(run_id)
        assert saved is not None
        assert saved["cdn_cache_warning"] is True
        assert saved["cache_hit_pct"] == 100.0
        assert saved["cache_hit_count"] == snap["total_requests"]
        history_page = get_all_runs()
        assert history_page["latest_run"]["cdn_cache_warning"] is True
        assert history_page["latest_run"]["cache_hit_pct"] == 100.0
    finally:
        request_owner.reset(tok)
        await runner.cleanup()


def test_profile_ram_floor_matches_51mb_load_minimum(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from backend.api import auth_deps
    from backend.api.auth_deps import AuthenticatedUser
    from backend.main import app
    from backend.core.profile_service import update_user_profile

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "issue07.sqlite"))
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")

    clamped = update_user_profile("issue07_user", {"default_ram_ceiling_mb": 40})
    assert clamped["default_ram_ceiling_mb"] == 51

    async def _override_user():
        request_owner.set("issue07_user")
        return AuthenticatedUser(user_id="issue07_user", email="issue07@test.local", role="authenticated")

    tok = request_owner.set("issue07_user")
    app.dependency_overrides[auth_deps.require_operator] = _override_user
    try:
        client = TestClient(app)
        bad = client.put("/api/profile", json={"default_ram_ceiling_mb": 50})
        assert bad.status_code == 422
        ok = client.put("/api/profile", json={"default_ram_ceiling_mb": 51})
        assert ok.status_code == 200
        assert ok.json()["default_ram_ceiling_mb"] == 51
    finally:
        app.dependency_overrides.clear()
        request_owner.reset(tok)





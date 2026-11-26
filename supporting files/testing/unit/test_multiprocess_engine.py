import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from backend.core import database, load_engine as engine_module, report_service
from backend.core.config import settings
from backend.core.worker_process import worker_active_target


class _SandboxMockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    fail_mode = False

    def do_GET(self):
        if _SandboxMockHandler.fail_mode or "fail=1" in self.path:
            body = b"Service Unavailable"
            self.send_response(503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = b"P" * 4096
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _start_local_server():
    _SandboxMockHandler.fail_mode = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SandboxMockHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_worker_active_target_preserves_exact_global_sum():
    for total in (1, 3, 16, 17, 100):
        summed = sum(
            worker_active_target("step_ramp", total, 30, 0.0, wid, 4, total)
            for wid in range(4)
        )
        expected = engine_module.calculate_active_vus("step_ramp", total, 30, 0.0)
        assert summed == expected


def test_should_use_multiprocess_respects_monkeypatch(monkeypatch):
    eng = engine_module.LoadEngine()
    eng._worker_limit = 64
    assert eng._should_use_multiprocess(False) is False

    monkeypatch.setattr(engine_module, "target_client", lambda *a, **kw: None)
    assert eng._should_use_multiprocess(True) is False
    assert eng._should_use_multiprocess(None) is False


@pytest.mark.asyncio
async def test_multiprocess_pool_runs_step_ramp_and_reaps_children(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "mp-runs.sqlite")
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")

    server, port = _start_local_server()
    try:
        monkeypatch.setattr(settings, "port", port)
        eng = engine_module.LoadEngine()
        run_id = await eng.start(
            f"http://127.0.0.1:{port}/api/sandbox/target",
            "step_ramp",
            16,
            2,
            is_sandbox=True,
            ram_limit_mb=1024,
            max_error_pct=15.0,
            p95_ceiling_ms=5000.0,
            use_multiprocess=True,
        )
        assert eng._use_multiprocess is True
        await asyncio.wait_for(asyncio.shield(eng._master_task), timeout=15)

        assert eng._worker_processes == []
        assert eng.is_running is False
        assert eng.total_requests > 0
        assert eng.status_2xx > 0
        assert eng.bytes_discarded >= eng.status_2xx * 4096

        saved = report_service.get_run(run_id)
        assert saved is not None
        assert saved["total_requests"] == eng.total_requests
        assert saved["verdict"] == "PASSED"
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_multiprocess_stop_and_circuit_breaker_reap_workers(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "mp-stop.sqlite")
    database.init_all_tables()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")

    server, port = _start_local_server()
    try:
        monkeypatch.setattr(settings, "port", port)
        eng = engine_module.LoadEngine()

        # 1. Manual stop cleanly terminates all spawned processes
        await eng.start(
            f"http://127.0.0.1:{port}/api/sandbox/target",
            "steady_crowd",
            8,
            10,
            is_sandbox=True,
            ram_limit_mb=1024,
            use_multiprocess=True,
        )
        for _ in range(30):
            if eng._worker_processes:
                break
            await asyncio.sleep(0.05)
        pids = eng._active_worker_pids()
        assert len(pids) >= 2
        await eng.stop(reason="MANUAL_ABORT")
        assert eng._active_worker_pids() == []
        assert eng.is_running is False

        # 2. 5xx storm triggers CIRCUIT_BREAKER and reaps children
        _SandboxMockHandler.fail_mode = True
        run_id = await eng.start(
            f"http://127.0.0.1:{port}/api/sandbox/target",
            "steady_crowd",
            8,
            10,
            is_sandbox=True,
            ram_limit_mb=1024,
            max_error_pct=5.0,
            use_multiprocess=True,
        )
        await asyncio.wait_for(asyncio.shield(eng._master_task), timeout=15)
        assert eng._active_worker_pids() == []
        saved = report_service.get_run(run_id)
        assert saved["verdict"] == "CIRCUIT_BREAKER"
    finally:
        server.shutdown()
        server.server_close()

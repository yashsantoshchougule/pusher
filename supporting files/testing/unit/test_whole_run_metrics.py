import asyncio
from contextlib import asynccontextmanager
import time
from types import SimpleNamespace

import pytest

from backend.core import load_engine as engine_module, report_service


@pytest.mark.asyncio
async def test_final_report_includes_earlier_failures(monkeypatch):
    now = 110.0
    monkeypatch.setattr(engine_module, "time", SimpleNamespace(
        time=lambda: now, strftime=time.strftime, monotonic=time.monotonic,
    ))
    engine = engine_module.LoadEngine()
    engine.run_id = "whole-run-fixture"
    engine.start_time = now
    engine.duration_sec = 360
    for _ in range(9):
        engine._record_response(200, 10, 112.1, False, passed=False)
    now += 10
    engine._record_response(200, 10, 5, False, passed=True)
    assert engine.get_status()["error_pct"] == 0
    assert engine.get_status()["p95_ms"] == 5

    await engine._finish_run()
    report = report_service.get_run(engine.run_id)
    assert report["metrics_scope"] == "whole_run"
    assert report["error_pct"] == 90
    assert report["p95_ms"] == 113
    assert report["total_requests"] == report["status_2xx"] == 10


@pytest.mark.asyncio
async def test_reset_and_simulation_have_no_measured_samples(monkeypatch):
    @asynccontextmanager
    async def target_client(*args, **kwargs):
        yield object()

    monkeypatch.setattr(engine_module, "target_client", target_client)
    engine = engine_module.LoadEngine()
    for _ in range(19):
        engine._record_response(200, 0, 0, False, True)
    engine._record_response(200, 0, 500, False, True)
    assert engine._run_p95_ms() == 0  # Nearest rank selects the nineteenth sample.

    run_id = await engine.start("https://example.invalid", "steady_crowd", 1, 1)
    assert engine._failed_requests == 0 and sum(engine._latency_counts) == 0
    await asyncio.wait_for(engine.simulate_spike(), 2)

    report = report_service.get_run(run_id)
    assert report["total_requests"] == report["status_429"] == report["status_5xx"] == 0
    assert report["p95_ms"] is None and report["error_pct"] is None
    assert report["verdict"] == "CIRCUIT_BREAKER"
    assert "Simulated" in report["status_label"]

    legacy = report_service.save_run({"run_id": "legacy-window-fixture", "p95_ms": 5.1, "error_pct": 2.0})
    old = report_service.get_run(legacy["run_id"])
    assert old["metrics_scope"] == "legacy_window" and old["p95_ms"] == 5.1
    assert report_service.compare_two_runs(old["run_id"], run_id)["overall_verdict"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_failure_accounting_breakdown_and_config_limits(monkeypatch):
    recorded = {}
    monkeypatch.setattr(report_service, "save_run", lambda data: recorded.update(data) or data)
    engine = engine_module.LoadEngine()
    engine.run_id = "accounting-fixture"
    engine.start_time = time.time() - 2.5
    engine.duration_sec = 30
    engine.p95_ceiling_ms = 9000.0
    engine.max_error_pct = 50.0
    engine.brakes = engine_module.CircuitBreakers(engine.max_error_pct, engine.p95_ceiling_ms)

    engine._record_response(200, 10, 10.0, False, True)
    engine._record_response(302, 10, 20.0, False, True)
    engine._record_response(404, 10, 30.0, False, False)
    engine._record_response(429, 10, 40.0, False, False)
    engine._record_response(503, 10, 50.0, False, False)
    engine._record_response(0, 0, 5000.0, True, False)
    engine._record_response(0, 0, 1.0, False, False)
    engine._record_response(102, 10, 60.0, False, False)

    status = engine.get_status()
    assert status["total_requests"] == 8
    assert (
        status["status_2xx"] + status["status_3xx"] + status["status_4xx"]
        + status["status_429"] + status["status_5xx"]
        + status["timeout_count"] + status["network_error_count"] + status["status_other"]
    ) == 8
    assert status["effective_p95_ceiling_ms"] == 8000
    assert status["effective_max_error_pct"] == 25
    assert "loop_lag_ms" in status

    await engine._finish_run()
    assert recorded["timeout_count"] == 1
    assert recorded["network_error_count"] == 1
    assert recorded["status_3xx"] == 1
    assert recorded["status_4xx"] == 1
    assert recorded["status_other"] == 1
    assert recorded["failed_requests"] == 6
    assert recorded["latency_breakdown"]["max_ms"] == 5000.0
    assert recorded["started_at"].endswith("Z")
    assert recorded["ended_at_iso"].endswith("Z")


def test_get_os_fd_cap_handles_rlim_infinity(monkeypatch):
    import sys
    monkeypatch.setattr(engine_module.sys, "platform", "linux")
    fake_resource = SimpleNamespace(RLIMIT_NOFILE=7, RLIM_INFINITY=-1, getrlimit=lambda _: (-1, -1))
    monkeypatch.setitem(sys.modules, "resource", fake_resource)
    assert engine_module.get_os_fd_cap() == engine_module.MAX_REQUESTED_VUS

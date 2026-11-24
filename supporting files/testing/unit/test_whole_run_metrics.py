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

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

import asyncio
import time
from types import SimpleNamespace

import pytest

from backend.core import load_engine as engine_module
from backend.core.load_engine import LoadEngine, RollingMetricsWindow


def test_rolling_window_quantiles_and_expiry():
    win = RollingMetricsWindow()
    for _ in range(19):
        win.record(100.0, False, 10.0)
    win.record(100.2, True, 41.5)

    rps, p95, err_pct = win.snapshot(100.5)
    assert rps == 20
    assert p95 == 10.0
    assert err_pct == 5.0

    # Advancing > 1.0s past old slice expires them cleanly
    win.record(102.0, False, 5.0)
    rps2, p95_2, err_pct2 = win.snapshot(102.0)
    assert rps2 == 1
    assert p95_2 == 5.0
    assert err_pct2 == 0.0


def test_rolling_window_high_volume_status_speed():
    win = RollingMetricsWindow()
    now = 500.0
    for idx in range(20_000):
        win.record(now + (idx % 10) * 0.09, (idx % 20 == 0), float((idx % 200) + 1))

    t0 = time.perf_counter()
    rps, p95, err_pct = win.snapshot(now + 0.9)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert rps == 20_000
    assert err_pct == 5.0
    assert 185.0 <= p95 <= 195.0
    assert elapsed_ms < 25.0


@pytest.mark.asyncio
async def test_dormant_vu_waits_on_wake_event_without_80ms_polling(monkeypatch):
    eng = LoadEngine()
    eng.target_vus = 10
    eng.duration_sec = 5
    eng.traffic_mode = "step_ramp"
    eng.start_time = time.time()
    eng._stop_event = asyncio.Event()
    eng._vu_wake_event = asyncio.Event()

    waited = asyncio.Event()
    proceeded = asyncio.Event()
    real_wait = eng._vu_wake_event.wait

    async def spy_wait():
        waited.set()
        return await real_wait()

    monkeypatch.setattr(eng._vu_wake_event, "wait", spy_wait)

    async def worker_probe():
        elapsed = time.time() - eng.start_time
        active = engine_module.calculate_active_vus(eng.traffic_mode, eng.target_vus, eng.duration_sec, elapsed)
        if 5 >= active:
            await eng._vu_wake_event.wait()
        proceeded.set()

    task = asyncio.create_task(worker_probe())
    await asyncio.wait_for(waited.wait(), timeout=1.0)
    await asyncio.sleep(0.05)
    assert not proceeded.is_set()
    eng._wake_workers()
    await asyncio.wait_for(proceeded.wait(), timeout=1.0)
    await task

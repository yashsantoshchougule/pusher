import asyncio
from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest

from backend.core import load_engine as load_engine_module, report_service


@pytest.mark.asyncio
async def test_stop_cancels_stalled_worker_and_closes_client_before_restart(monkeypatch):
    engine = load_engine_module.LoadEngine()
    worker_started = asyncio.Event()
    worker_canceled = asyncio.Event()
    close_started = asyncio.Event()
    allow_close = asyncio.Event()

    @asynccontextmanager
    async def target_client(*args, **kwargs):
        try:
            yield object()
        finally:
            close_started.set()
            await allow_close.wait()

    async def stalled_worker(client, index):
        worker_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            worker_canceled.set()

    save = Mock()
    monkeypatch.setattr(load_engine_module, "target_client", target_client)
    monkeypatch.setattr(engine, "_vu_worker", stalled_worker)
    monkeypatch.setattr(report_service, "save_run", save)
    first = await engine.start("https://example.invalid", "steady_crowd", 1, 5)
    try:
        await asyncio.wait_for(worker_started.wait(), 1)
        stop = asyncio.create_task(engine.stop())
        repeated = asyncio.create_task(engine.stop())
        await asyncio.wait_for(close_started.wait(), 1)
        assert worker_canceled.is_set()
        assert engine.is_running
        assert not stop.done()
        assert save.call_count == 0
        with pytest.raises(RuntimeError, match="already actively running"):
            await engine.start("https://example.invalid", "steady_crowd", 1, 5)
        allow_close.set()
        await asyncio.wait_for(asyncio.gather(stop, repeated), 1)
        assert not engine.is_running
        save.assert_called_once()
        assert save.call_args.args[0]["run_id"] == first
        assert save.call_args.args[0]["verdict"] == "MANUAL_ABORT"
        await engine.start("https://example.invalid", "steady_crowd", 1, 5)
        await asyncio.wait_for(engine.stop(), 1)
        assert save.call_count == 2
    finally:
        allow_close.set()
        await engine.stop()

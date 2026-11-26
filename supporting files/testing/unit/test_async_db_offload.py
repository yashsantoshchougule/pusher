import asyncio
import threading
import time

import pytest

from backend.core import database, report_service
from backend.core.db_async import run_db_read, run_db_write
from backend.core.request_owner import request_owner


@pytest.mark.asyncio
async def test_db_offload_keeps_event_loop_responsive():
    ticks = 0
    stop_ticker = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not stop_ticker.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    def blocking_write():
        time.sleep(0.12)
        return "ok"

    task = asyncio.create_task(ticker())
    res = await run_db_write(blocking_write)
    stop_ticker.set()
    await task

    assert res == "ok"
    assert ticks >= 5


@pytest.mark.asyncio
async def test_db_offload_preserves_request_owner_and_serializes_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "async-db.sqlite")
    database.init_all_tables()

    active_writers = 0
    max_concurrent_writers = 0
    writer_threads = set()
    seen_owners = []

    def monitored_save(run_id: str):
        nonlocal active_writers, max_concurrent_writers
        active_writers += 1
        max_concurrent_writers = max(max_concurrent_writers, active_writers)
        writer_threads.add(threading.get_ident())
        seen_owners.append(request_owner.get())
        try:
            time.sleep(0.02)
            return report_service.save_run({"run_id": run_id, "peak_rps": 100})
        finally:
            active_writers -= 1

    tok = request_owner.set("supabase:alice")
    try:
        results = await asyncio.gather(
            run_db_write(monitored_save, "RUN-ASYNC-1"),
            run_db_write(monitored_save, "RUN-ASYNC-2"),
            run_db_write(monitored_save, "RUN-ASYNC-3"),
        )
        history = await run_db_read(report_service.get_all_runs)
    finally:
        request_owner.reset(tok)

    assert max_concurrent_writers == 1
    assert len(writer_threads) == 1
    assert seen_owners == ["supabase:alice"] * 3
    assert len(results) == 3
    assert len(history["runs"]) == 3

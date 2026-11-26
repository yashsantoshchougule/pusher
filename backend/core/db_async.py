"""
Non-blocking SQLite Execution Helpers (SCALE-05).
Offloads synchronous SQLite reads to worker threads and serializes SQLite writes on a dedicated
single-writer thread while preserving request_owner ContextVars across async boundaries.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextvars
import functools
from typing import Callable, TypeVar

T = TypeVar("T")

_DB_WRITE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pusher-db-writer")


async def run_db_read(fn: Callable[..., T], *args, **kwargs) -> T:
    """Execute a synchronous read query in a thread pool without blocking the event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)


async def run_db_write(fn: Callable[..., T], *args, **kwargs) -> T:
    """Serialize synchronous write queries onto the single-writer SQLite thread cleanly."""
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    call = functools.partial(fn, *args, **kwargs)
    return await loop.run_in_executor(_DB_WRITE_EXECUTOR, ctx.run, call)

"""Final Scaling Benchmark (SCALE-01..06): High-speed aiohttp target vs LoadEngine (64 VU single vs 160 VU MP)."""

import asyncio
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT_DIR = str(Path(__file__).resolve().parents[3])
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from aiohttp import web

from backend.core import database, load_engine as engine_module
from backend.core.config import settings


def _start_aiohttp_target():
    ready = threading.Event()
    holder = {}
    payload = b"P" * 4096

    async def handle(_request):
        return web.Response(body=payload, content_type="application/octet-stream")

    def run():
        async def runner_main():
            app = web.Application()
            app.router.add_get("/api/sandbox/target", handle)
            runner = web.AppRunner(app, access_log=None)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0, backlog=2048)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            holder["port"] = port
            holder["stop"] = asyncio.Event()
            holder["loop"] = asyncio.get_running_loop()
            ready.set()
            await holder["stop"].wait()
            await runner.cleanup()

        asyncio.run(runner_main())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    ready.wait(timeout=5.0)
    return holder, t


async def main():
    holder, t = _start_aiohttp_target()
    port = holder["port"]
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            database.DB_PATH = Path(tmpdir) / "final-bench.sqlite"
            database.init_all_tables()
            settings.pusher_mode = "local_dev"
            settings.port = port
            url = f"http://127.0.0.1:{port}/api/sandbox/target"

            for label, vus, mp_flag in (
                ("scale06_64vu_single", 64, False),
                ("scale06_160vu_multiprocess", 160, True),
            ):
                eng = engine_module.LoadEngine()
                t0 = time.perf_counter()
                await eng.start(
                    url,
                    "steady_crowd",
                    vus,
                    3,
                    is_sandbox=True,
                    ram_limit_mb=1024,
                    p95_ceiling_ms=8000.0,
                    max_error_pct=25.0,
                    use_multiprocess=mp_flag,
                )
                await asyncio.wait_for(asyncio.shield(eng._master_task), timeout=25)
                dt = time.perf_counter() - t0
                print(
                    f"{label}: {{'requests': {eng.total_requests}, 'status_2xx': {eng.status_2xx}, "
                    f"'failed': {eng._failed_requests}, 'elapsed_sec': {round(dt, 2)}, "
                    f"'rps': {round(eng.total_requests / max(dt, 0.01), 1)}, "
                    f"'p95_ms': {eng._run_p95_ms()}, 'peak_vus': {eng._peak_vus}}}"
                )
    finally:
        holder["loop"].call_soon_threadsafe(holder["stop"].set)
        t.join(timeout=3.0)


if __name__ == "__main__":
    asyncio.run(main())

"""SCALE-01 Benchmark: Compare Single-Process vs Multi-Process Loopback RPS."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time

ROOT_DIR = str(Path(__file__).resolve().parents[3])
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.core import database, load_engine as engine_module
from backend.core.config import settings


class _BenchHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    payload = b"X" * 4096

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        return


async def run_bench():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        database.DB_PATH = Path(tmpdir) / "bench.sqlite"
        database.init_all_tables()
        settings.pusher_mode = "local_dev"

        server = ThreadingHTTPServer(("127.0.0.1", 0), _BenchHandler)
        port = server.server_address[1]
        settings.port = port
        threading.Thread(target=server.serve_forever, daemon=True).start()

        try:
            url = f"http://127.0.0.1:{port}/api/sandbox/target"
            results = {}
            for label, mp_flag in (("single_process", False), ("multi_process", True)):
                eng = engine_module.LoadEngine()
                t0 = time.perf_counter()
                await eng.start(
                    url,
                    "steady_crowd",
                    64,
                    3,
                    is_sandbox=True,
                    ram_limit_mb=1024,
                    p95_ceiling_ms=8000.0,
                    max_error_pct=25.0,
                    use_multiprocess=mp_flag,
                )
                await asyncio.wait_for(asyncio.shield(eng._master_task), timeout=20)
                dt = time.perf_counter() - t0
                results[label] = {
                    "requests": eng.total_requests,
                    "status_2xx": eng.status_2xx,
                    "elapsed_sec": round(dt, 2),
                    "rps": round(eng.total_requests / max(dt, 0.01), 1),
                    "p95_ms": eng._run_p95_ms(),
                }
                print(f"{label}: {results[label]}")
            return results
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    asyncio.run(run_bench())

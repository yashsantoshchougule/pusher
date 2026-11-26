import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.core.config import settings
from backend.core.http_runner import AiohttpLoadClient, SSRFPinnedResolver, get_fast_loop_factory
from backend.core.target_policy import DestinationError, parse_target


class _TargetHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "https://other.invalid/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/oversized"):
            chunk = b"Z" * (1024 * 1024)
            self.send_response(200)
            self.send_header("Content-Length", str(len(chunk) * 12))
            self.end_headers()
            for _ in range(12):
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except OSError:
                    break
            return
        body = b"A" * 4096
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


@pytest.mark.asyncio
async def test_ssrf_resolver_blocks_private_and_rebinding(monkeypatch):
    loop = asyncio.get_running_loop()
    answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    resolver_mock = AsyncMock(return_value=answer)
    monkeypatch.setattr(loop, "getaddrinfo", resolver_mock)

    resolver = SSRFPinnedResolver(is_sandbox=False, dns_cache_ttl=0.0)
    recs = await resolver.resolve("example.invalid", 443)
    assert len(recs) == 1
    assert recs[0]["host"] == "93.184.216.34"

    # DNS rebinding to loopback must fail cleanly
    resolver_mock.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    with pytest.raises(DestinationError, match="prohibited"):
        await resolver.resolve("example.invalid", 443)


@pytest.mark.asyncio
async def test_aiohttp_client_blocks_literal_ip_bypass_when_not_sandbox(monkeypatch):
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    base = parse_target("http://127.0.0.1:8000")
    async with AiohttpLoadClient(base, is_sandbox=False, timeout=1.0, connections=2) as client:
        status, received, _, timed_out = await client.execute_request(
            "GET", "http://127.0.0.1:8000/", {"User-Agent": "test"}
        )
        assert status == 0
        assert received == 0
        assert timed_out is False


@pytest.mark.asyncio
async def test_aiohttp_client_streams_4kb_no_redirects_and_enforces_10mb_cap(monkeypatch):
    server, port = _start_server()
    try:
        monkeypatch.setattr(settings, "pusher_mode", "local_dev")
        monkeypatch.setattr(settings, "port", port)
        base = parse_target(f"http://127.0.0.1:{port}")
        async with AiohttpLoadClient(base, is_sandbox=True, timeout=5.0, connections=4) as client:
            # 1. Valid 200 streaming 4 KB body
            status, received, _, timed_out = await client.execute_request(
                "GET", f"http://127.0.0.1:{port}/api/sandbox/target", {"Host": "evil.invalid"}
            )
            assert status == 200
            assert received == 4096
            assert timed_out is False

            # 2. Cross-origin blocked cleanly
            status, _, _, _ = await client.execute_request(
                "GET", "https://other.invalid/secret", {}
            )
            assert status == 0

        # 3. 302 redirect is NOT followed; 4. 10 MB infinite stream cap aborts oversized response cleanly
        monkeypatch.setattr(settings, "port", port + 1)
        monkeypatch.setattr(settings, "sandbox_origins", [f"http://127.0.0.1:{port}"])
        async with AiohttpLoadClient(base, is_sandbox=True, timeout=5.0, connections=4) as open_sandbox_client:
            status, _, _, _ = await open_sandbox_client.execute_request(
                "GET", f"http://127.0.0.1:{port}/redirect", {}
            )
            assert status == 302

            status, received, _, _ = await open_sandbox_client.execute_request(
                "GET", f"http://127.0.0.1:{port}/oversized", {}
            )
            assert status == 200
            assert received <= 10 * 1024 * 1024 + 4096
    finally:
        server.shutdown()
        server.server_close()


def test_fast_loop_factory_available_on_platform():
    factory = get_fast_loop_factory()
    assert factory is not None

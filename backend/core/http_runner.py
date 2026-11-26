"""
High-throughput aiohttp HTTP transport with strict SSRF IP pinning, 60s DNS caching,
4 KB chunk-discard streaming, 10 MB infinite-stream cap, and winloop/uvloop factory.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import ipaddress
import ssl
import socket
import sys
import time
from typing import Any

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
import httpx

from backend.core.config import settings
from backend.core.target_policy import (
    DestinationError,
    DestinationTimeoutError,
    _LOCAL_HOSTS,
    _SANDBOX_PATHS,
    bound_target,
    origin,
    parse_target,
    resolve_addresses,
)

CHUNK_SIZE_BYTES = 4096
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB infinite stream guard


def get_fast_loop_factory():
    """Return winloop (Windows) or uvloop (POSIX) event-loop factory when installed."""
    try:
        if sys.platform == "win32":
            import winloop
            return winloop.new_event_loop
        import uvloop
        return uvloop.new_event_loop
    except Exception:
        return None


def _validate_ip_address(address_str: str, is_sandbox: bool) -> None:
    try:
        ip = ipaddress.ip_address(address_str)
    except ValueError as exc:
        raise DestinationError("The target hostname could not be resolved.") from exc
    ip = getattr(ip, "ipv4_mapped", None) or ip
    if is_sandbox and ip.is_loopback:
        return
    if is_sandbox or not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, "is_site_local", False):
        raise DestinationError("The target resolves to a prohibited network address.")


class SSRFPinnedResolver(AbstractResolver):
    """Custom aiohttp resolver enforcing SSRF IP checks with optional 60s DNS cache."""

    def __init__(self, is_sandbox: bool = False, dns_cache_ttl: float = 60.0) -> None:
        self.is_sandbox = is_sandbox
        self.dns_cache_ttl = dns_cache_ttl
        self._dns_cache: dict[tuple[str, int], tuple[float, list[str]]] = {}
        self._dns_locks: dict[tuple[str, int], asyncio.Lock] = {}

    async def _resolve_ips(self, host: str, port: int) -> list[str]:
        if self.dns_cache_ttl <= 0:
            return await resolve_addresses(host, port, self.is_sandbox)
        key = (host, port)
        now = time.monotonic()
        cached = self._dns_cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]
        lock = self._dns_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._dns_locks[key] = lock
        async with lock:
            now = time.monotonic()
            cached = self._dns_cache.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]
            addresses = await resolve_addresses(host, port, self.is_sandbox)
            self._dns_cache[key] = (time.monotonic() + self.dns_cache_ttl, addresses)
            return addresses

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        try:
            addresses = await self._resolve_ips(host, port)
        except DestinationTimeoutError as exc:
            raise TimeoutError(str(exc)) from exc
        results: list[ResolveResult] = []
        for ip in addresses:
            addr_family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            if family in (socket.AF_UNSPEC, 0) or addr_family == family or addr_family in (socket.AF_INET, socket.AF_INET6):
                results.append({
                    "hostname": host,
                    "host": ip,
                    "port": port,
                    "family": addr_family,
                    "proto": socket.IPPROTO_TCP,
                    "flags": socket.AI_NUMERICHOST,
                })
        return results

    async def close(self) -> None:
        self._dns_cache.clear()
        self._dns_locks.clear()


class _SSRFCheckedTCPConnector(aiohttp.TCPConnector):
    """TCPConnector that also validates literal IPs instead of bypassing AbstractResolver."""

    def __init__(self, *, is_sandbox: bool, dns_cache_ttl: float, **kwargs: Any) -> None:
        self._ssrf_is_sandbox = is_sandbox
        self._ssrf_resolver = SSRFPinnedResolver(is_sandbox=is_sandbox, dns_cache_ttl=dns_cache_ttl)
        super().__init__(
            resolver=self._ssrf_resolver,
            use_dns_cache=dns_cache_ttl > 0,
            ttl_dns_cache=int(dns_cache_ttl) if dns_cache_ttl > 0 else None,
            **kwargs,
        )

    async def _resolve_host(
        self,
        host: str,
        port: int,
        traces: Sequence[Any] | None = None,
    ) -> list[ResolveResult]:
        stripped = host.strip("[]")
        try:
            ipaddress.ip_address(stripped)
            is_literal = True
        except ValueError:
            is_literal = False

        if is_literal:
            _validate_ip_address(stripped, self._ssrf_is_sandbox)
            addr_family = socket.AF_INET6 if ":" in stripped else socket.AF_INET
            return [{
                "hostname": host,
                "host": stripped,
                "port": port,
                "family": addr_family,
                "proto": socket.IPPROTO_TCP,
                "flags": socket.AI_NUMERICHOST,
            }]
        return await super()._resolve_host(host, port, traces=traces)


class AiohttpLoadClient:
    """Persistent aiohttp ClientSession wrapper preserving Pusher SSRF, Keep-Alive, and 4 KB discard rules."""

    def __init__(
        self,
        base: httpx.URL,
        is_sandbox: bool = False,
        *,
        timeout: float = 5.0,
        connections: int = 1,
        dns_cache_ttl: float = 60.0,
    ) -> None:
        self.base = base
        self.is_sandbox = is_sandbox
        self.timeout_sec = float(timeout)
        self.connections = max(1, int(connections))
        self.dns_cache_ttl = float(dns_cache_ttl)

        self._base_scheme = base.scheme
        self._base_raw_host = base.raw_host.lower()
        self._base_port = base.port
        self._base_origin = origin(base)
        self._base_host_header = base.netloc.decode("ascii")
        self._host_valid = (
            self._base_scheme in ("http", "https")
            and bool(self._base_raw_host)
            and b"%" not in self._base_raw_host
            and self._base_port != 0
        )

        self._sandbox_mode = settings.pusher_mode
        self._sandbox_port = settings.port
        self._sandbox_origins_tuple = tuple(settings.sandbox_origins)
        self._sandbox_allowed_origins = frozenset(
            origin(parse_target(item)) for item in self._sandbox_origins_tuple
        )
        base_host = self._base_origin[1]
        self._is_builtin_sandbox = (
            self._base_scheme == "http"
            and base_host in _LOCAL_HOSTS
            and self._base_origin[2] == self._sandbox_port
        )
        self._is_configured_sandbox = (
            base_host in _LOCAL_HOSTS
            and self._base_origin in self._sandbox_allowed_origins
        )

        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> AiohttpLoadClient:
        ssl_context: ssl.SSLContext | bool = ssl.create_default_context() if self._base_scheme == "https" else False
        connector = _SSRFCheckedTCPConnector(
            is_sandbox=self.is_sandbox,
            dns_cache_ttl=self.dns_cache_ttl,
            ssl=ssl_context,
            limit=self.connections,
            limit_per_host=self.connections,
            keepalive_timeout=30.0,
            enable_cleanup_closed=sys.version_info < (3, 13),
            force_close=False,
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            auto_decompress=False,
            trust_env=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        )
        return self

    async def __aexit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _validate_target(self, url: str) -> str:
        parsed = httpx.URL(url)
        fast_ok = (
            self._host_valid
            and parsed.scheme == self._base_scheme
            and parsed.raw_host == self._base_raw_host
            and parsed.port == self._base_port
            and not parsed.userinfo
            and not parsed.fragment
            and b"\\" not in parsed.raw_path
        )
        if fast_ok and self.is_sandbox:
            fast_ok = (
                settings.pusher_mode == "local_dev"
                and settings.port == self._sandbox_port
                and tuple(settings.sandbox_origins) == self._sandbox_origins_tuple
                and (
                    (parsed.raw_host == b"127.0.0.1" and parsed.path in _SANDBOX_PATHS)
                    if self._is_builtin_sandbox
                    else self._is_configured_sandbox
                )
            )
        if fast_ok:
            return str(parsed)
        validated = bound_target(url, self.base, self.is_sandbox)
        return str(validated)

    @staticmethod
    def is_cdn_cache_hit(headers: Any) -> bool:
        if not headers:
            return False
        fastly_id = False
        fastly_hits = 0
        items = headers.items() if hasattr(headers, "items") else ()
        for k, v in items:
            kl = str(k).lower()
            val = str(v).strip()
            if kl in {"cf-cache-status", "x-vercel-cache"}:
                if val.upper() == "HIT":
                    return True
            elif kl == "x-cache":
                if "HIT" in val.upper():
                    return True
            elif kl == "x-fastly-request-id" and val:
                fastly_id = True
            elif kl == "x-cache-hits":
                try:
                    fastly_hits = int(val.split(",")[0].strip())
                except ValueError:
                    fastly_hits = 0
        return fastly_id and fastly_hits > 0

    async def execute_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        *,
        content: bytes | None = None,
        capture: bool = False,
        deadline_sec: float | None = None,
        brakes: Any = None,
        on_trip: Any = None,
        on_cache_hit: Any = None,
    ) -> tuple[int, int, bytes, bool]:
        """
        Execute one non-redirected HTTP request with 4 KB chunk discard.
        Returns (status_code, received_bytes, first_chunk_preview, timed_out).
        """
        if self._session is None:
            raise RuntimeError("AiohttpLoadClient must be entered as an async context manager.")

        effective_timeout = self.timeout_sec if deadline_sec is None else min(self.timeout_sec, float(deadline_sec))
        timeout = aiohttp.ClientTimeout(total=effective_timeout)

        status = 0
        received = 0
        preview = b""
        timed_out = False

        try:
            target_url = self._validate_target(url)
            req_headers = dict(headers)
            req_headers["Host"] = self._base_host_header
            async with self._session.request(
                method,
                target_url,
                headers=req_headers,
                data=content,
                allow_redirects=False,
                timeout=timeout,
            ) as response:
                status = response.status
                if on_cache_hit is not None and self.is_cdn_cache_hit(response.headers):
                    on_cache_hit()
                if brakes is not None and status == 403 and brakes.is_waf_headers(response.headers):
                    if on_trip is not None:
                        on_trip("TRIPPED (firewall blocked the request)")
                else:
                    preview_tripped = False
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE_BYTES):
                        received += len(chunk)
                        if not preview and (capture or status == 403):
                            preview = chunk
                            if brakes is not None and status == 403:
                                reason = brakes.observe_preview(status, preview)
                                if reason:
                                    if on_trip is not None:
                                        on_trip(f"TRIPPED ({reason})")
                                    preview_tripped = True
                                    break
                        if received > MAX_RESPONSE_BYTES:
                            break
                    if not preview_tripped and brakes is not None:
                        reason = brakes.observe_status(time.monotonic(), status, response.headers)
                        if reason and on_trip is not None:
                            on_trip(f"TRIPPED ({reason})")
        except (TimeoutError, asyncio.TimeoutError, aiohttp.ServerTimeoutError):
            timed_out = True
            status = 0
        except (aiohttp.ClientError, DestinationError, OSError):
            status = 0
            if brakes is not None:
                reason = brakes.observe_status(time.monotonic(), 0, {})
                if reason and on_trip is not None:
                    on_trip(f"TRIPPED ({reason})")

        return status, received, preview, timed_out

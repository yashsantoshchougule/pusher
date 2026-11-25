"""Destination checks for HTTP requests made on behalf of a tester."""

import asyncio
import ipaddress
import math
import socket
import time

import httpcore
import httpx

from backend.core.config import settings

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SANDBOX_PATHS = frozenset({
    "/api/sandbox/target",
    "/api/sandbox/login",
    "/api/sandbox/items",
    "/api/sandbox/checkout",
})
_SHARD_THRESHOLD = 32
_SHARD_MAX_CONNECTIONS = 24


class DestinationError(ValueError):
    pass


class DestinationTimeoutError(DestinationError):
    pass


def parse_target(value: str) -> httpx.URL:
    try:
        if not isinstance(value, str) or "\\" in value or any(c.isspace() for c in value):
            raise DestinationError("Enter an absolute HTTP or HTTPS target URL.")
        url = httpx.URL(value)
    except httpx.InvalidURL as exc:
        raise DestinationError("Enter an absolute HTTP or HTTPS target URL.") from exc
    if url.scheme not in ("http", "https") or not url.host or url.userinfo or "%" in url.host:
        raise DestinationError("Enter an HTTP or HTTPS target URL without credentials.")
    if url.port == 0:
        raise DestinationError("The target port must be greater than zero.")
    return url.copy_with(fragment=None)


def origin(url: httpx.URL) -> tuple[str, str, int]:
    return url.scheme, url.raw_host.decode("ascii").lower(), url.port or (443 if url.scheme == "https" else 80)


def sandbox_target(value: str) -> httpx.URL:
    if settings.pusher_mode != "local_dev":
        raise DestinationError("Sandbox targets are available only in local development.")
    url = parse_target(value)
    builtin = parse_target(f"http://127.0.0.1:{settings.port}")
    if url.host in {"sandbox.pusher.local", "api.myproject.dev"} and url.port is None:
        url = builtin.copy_with(path="/api/sandbox/target", query=url.query or None)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if url.host in local_hosts and url.scheme == "http" and origin(url)[2] == settings.port:
        if url.path not in {
            "/api/sandbox/target", "/api/sandbox/login", "/api/sandbox/items", "/api/sandbox/checkout"
        }:
            raise DestinationError("Choose a built-in sandbox endpoint.")
        return url.copy_with(host="127.0.0.1")
    allowed = {origin(parse_target(item)) for item in settings.sandbox_origins}
    if url.host not in local_hosts or origin(url) not in allowed:
        raise DestinationError("The sandbox destination must match a configured loopback origin.")
    return url


def bound_target(value: str, base: httpx.URL, is_sandbox: bool) -> httpx.URL:
    url = sandbox_target(value) if is_sandbox else parse_target(value)
    if origin(url) != origin(base):
        raise DestinationError("The destination must use the verified target origin.")
    return url


def journey_target(path: str, base: httpx.URL, is_sandbox: bool) -> httpx.URL:
    if path.startswith("/") and not path.startswith("//"):
        path = str(base.copy_with(path="/", query=None)).rstrip("/") + path
    return bound_target(path, base, is_sandbox)


async def resolve_addresses(host: str, port: int, is_sandbox: bool) -> list[str]:
    try:
        async with asyncio.timeout(3):
            records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(ipaddress.ip_address(record[4][0]) for record in records))
    except TimeoutError as exc:
        raise DestinationTimeoutError("The target hostname resolution timed out.") from exc
    except (OSError, ValueError) as exc:
        raise DestinationError("The target hostname could not be resolved.") from exc

    for address in addresses:
        ip = getattr(address, "ipv4_mapped", None) or address
        if is_sandbox and ip.is_loopback:
            continue
        if is_sandbox or not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, "is_site_local", False):
            raise DestinationError("The target resolves to a prohibited network address.")
    if not addresses:
        raise DestinationError("The target hostname has no usable addresses.")
    return [str(address) for address in addresses]


class CheckedNetworkBackend(httpcore.AnyIOBackend):
    def __init__(self, is_sandbox: bool, dns_cache_ttl: float = 0.0):
        self.is_sandbox = is_sandbox
        self.dns_cache_ttl = dns_cache_ttl
        self._dns_cache: dict[tuple[str, int], tuple[float, list[str]]] = {}
        self._dns_locks: dict[tuple[str, int], asyncio.Lock] = {}

    async def _resolve(self, host: str, port: int) -> list[str]:
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

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            async with asyncio.timeout(timeout):
                addresses = await self._resolve(host, port)
                for index, address in enumerate(addresses):
                    try:
                        connect_kwargs = {
                            "local_address": local_address,
                            "socket_options": socket_options,
                        }
                        if timeout is not None:
                            connect_kwargs["timeout"] = timeout
                        return await super().connect_tcp(address, port, **connect_kwargs)
                    except (httpcore.ConnectError, httpcore.ConnectTimeout):
                        if index == len(addresses) - 1:
                            raise
        except DestinationTimeoutError as exc:
            raise httpcore.ConnectTimeout(str(exc)) from exc
        except DestinationError as exc:
            raise httpcore.ConnectError(str(exc)) from exc
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("Target connection timed out.") from exc


class _ShardedStream:
    """Wraps an httpcore response stream to release shard inflight accounting on close."""

    def __init__(self, inner, inflight: list[int], shard_idx: int) -> None:
        self._inner = inner
        self._inflight = inflight
        self._shard_idx = shard_idx
        self._released = False

    def _release(self) -> None:
        if not self._released:
            self._released = True
            self._inflight[self._shard_idx] = max(0, self._inflight[self._shard_idx] - 1)

    async def __aiter__(self):
        try:
            async for chunk in self._inner:
                yield chunk
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        try:
            if hasattr(self._inner, "aclose"):
                await self._inner.aclose()
        finally:
            self._release()


class _ShardedAsyncConnectionPool:
    """Shards high-concurrency pools into <=24-connection httpcore pools to avoid O(C^2) scans."""

    def __init__(
        self,
        *,
        ssl_context,
        network_backend: CheckedNetworkBackend,
        total_connections: int,
        max_per_shard: int = _SHARD_MAX_CONNECTIONS,
    ) -> None:
        num_shards = max(1, math.ceil(total_connections / max_per_shard))
        base_cap, remainder = divmod(total_connections, num_shards)
        self._caps: list[int] = [base_cap + (1 if i < remainder else 0) for i in range(num_shards)]
        self._inflight: list[int] = [0] * num_shards
        self._shards: list[httpcore.AsyncConnectionPool] = [
            httpcore.AsyncConnectionPool(
                ssl_context=ssl_context,
                network_backend=network_backend,
                max_connections=cap,
                max_keepalive_connections=cap,
            )
            for cap in self._caps
        ]

    @property
    def connections(self):
        conns = []
        for shard in self._shards:
            conns.extend(shard.connections)
        return conns

    def _pick_shard(self) -> int:
        for idx, (inflight, cap) in enumerate(zip(self._inflight, self._caps)):
            if inflight < cap:
                return idx
        return min(range(len(self._shards)), key=self._inflight.__getitem__)

    async def handle_async_request(self, request: httpcore.Request) -> httpcore.Response:
        idx = self._pick_shard()
        self._inflight[idx] += 1
        try:
            resp = await self._shards[idx].handle_async_request(request)
        except BaseException:
            self._inflight[idx] = max(0, self._inflight[idx] - 1)
            raise
        return httpcore.Response(
            status=resp.status,
            headers=resp.headers,
            content=_ShardedStream(resp.stream, self._inflight, idx),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await asyncio.gather(*(shard.aclose() for shard in self._shards))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        await self.aclose()


class TargetTransport(httpx.AsyncHTTPTransport):
    def __init__(self, base: httpx.URL, is_sandbox: bool, connections: int):
        self.base = base
        self.is_sandbox = is_sandbox
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

        # Pre-compute static sandbox origin validation state once per transport.
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

        ssl_context = httpx.create_ssl_context(trust_env=False)
        network_backend = CheckedNetworkBackend(is_sandbox, dns_cache_ttl=60.0)
        # HTTPX delegates pooling and TLS to HTTPCore; shard large pools to avoid O(C^2) scans.
        if connections > _SHARD_THRESHOLD:
            self._pool = _ShardedAsyncConnectionPool(
                ssl_context=ssl_context,
                network_backend=network_backend,
                total_connections=connections,
            )
        else:
            self._pool = httpcore.AsyncConnectionPool(
                ssl_context=ssl_context,
                network_backend=network_backend,
                max_connections=connections,
                max_keepalive_connections=connections,
            )

    def _fast_validate(self, url: httpx.URL) -> bool:
        if (
            not self._host_valid
            or url.scheme != self._base_scheme
            or url.raw_host != self._base_raw_host
            or url.port != self._base_port
            or url.userinfo
            or url.fragment
            or b"\\" in url.raw_path
        ):
            return False
        if not self.is_sandbox:
            return True
        if (
            settings.pusher_mode != "local_dev"
            or settings.port != self._sandbox_port
            or tuple(settings.sandbox_origins) != self._sandbox_origins_tuple
        ):
            return False
        if self._is_builtin_sandbox:
            return url.raw_host == b"127.0.0.1" and url.path in _SANDBOX_PATHS
        return self._is_configured_sandbox

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._fast_validate(request.url):
            request.headers["host"] = self._base_host_header
        else:
            try:
                request.url = bound_target(str(request.url), self.base, self.is_sandbox)
            except DestinationError as exc:
                raise httpx.ConnectError(str(exc), request=request) from exc
            request.headers["host"] = request.url.netloc.decode("ascii")
        return await super().handle_async_request(request)


def target_client(base: httpx.URL, is_sandbox: bool = False, *, timeout=5.0, connections=1) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=TargetTransport(base, is_sandbox, connections),
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )

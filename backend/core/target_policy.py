"""Destination checks for HTTP requests made on behalf of a tester."""

import asyncio
import ipaddress
import socket

import httpcore
import httpx

from backend.core.config import settings


class DestinationError(ValueError):
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
    except (OSError, TimeoutError, ValueError) as exc:
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
    def __init__(self, is_sandbox: bool):
        self.is_sandbox = is_sandbox

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            async with asyncio.timeout(timeout):
                addresses = await resolve_addresses(host, port, self.is_sandbox)
                for index, address in enumerate(addresses):
                    try:
                        return await super().connect_tcp(
                            address, port, local_address=local_address, socket_options=socket_options
                        )
                    except (httpcore.ConnectError, httpcore.ConnectTimeout):
                        if index == len(addresses) - 1:
                            raise
        except DestinationError as exc:
            raise httpcore.ConnectError(str(exc)) from exc
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout("Target connection timed out.") from exc


class TargetTransport(httpx.AsyncHTTPTransport):
    def __init__(self, base: httpx.URL, is_sandbox: bool, connections: int):
        self.base = base
        self.is_sandbox = is_sandbox
        # HTTPX delegates pooling and TLS to HTTPCore, whose pool accepts a network backend.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(trust_env=False),
            network_backend=CheckedNetworkBackend(is_sandbox),
            max_connections=connections,
            max_keepalive_connections=connections,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
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

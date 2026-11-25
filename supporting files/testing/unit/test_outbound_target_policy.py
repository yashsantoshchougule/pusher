import asyncio
import hashlib
import hmac
import json
import socket
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpcore
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api import auth_deps
from backend.core import target_policy, target_service
from backend.core.jwks_verifier import AuthenticatedUser
from backend.main import app


def test_origin_uses_scheme_host_and_effective_port():
    base = target_policy.parse_target("https://EXAMPLE.invalid:443")
    assert str(target_policy.journey_target("/orders", base, False)) == "https://example.invalid/orders"
    with pytest.raises(target_policy.DestinationError, match="verified target origin"):
        target_policy.journey_target("https://example.invalid:8443/orders", base, False)


def test_sandbox_accepts_only_configured_origins(monkeypatch):
    monkeypatch.setattr(target_policy.settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(target_policy.settings, "port", 8000)
    assert target_policy.sandbox_target("https://sandbox.pusher.local").host == "127.0.0.1"
    with pytest.raises(target_policy.DestinationError, match="configured loopback"):
        target_policy.sandbox_target("https://example.invalid/api/sandbox/items")
    with pytest.raises(target_policy.DestinationError, match="built-in sandbox endpoint"):
        target_policy.sandbox_target("http://127.0.0.1:8000/api/profile")
    monkeypatch.setattr(target_policy.settings, "pusher_mode", "production")
    with pytest.raises(target_policy.DestinationError, match="local development"):
        target_policy.sandbox_target("http://127.0.0.1:8000/api/sandbox/items")


@pytest.mark.asyncio
async def test_dns_readiness_does_not_request_ownership_challenge(monkeypatch):
    monkeypatch.setattr(target_service, "resolve_addresses", AsyncMock(return_value=["93.184.216.34"]))
    with patch.object(target_service, "target_client", side_effect=AssertionError("Unexpected HTTP request")):
        result = await target_service.validate_target_url("https://example.invalid")
    assert result["ready"] is True
    assert result["reachable"] is False
    assert result["status"] == "DNS_READY"


@pytest.mark.asyncio
async def test_connection_dials_only_resolved_public_ip(monkeypatch):
    loop = asyncio.get_running_loop()
    answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    resolver = AsyncMock(return_value=answer)
    monkeypatch.setattr(loop, "getaddrinfo", resolver)
    network = target_policy.CheckedNetworkBackend(False)
    with patch.object(httpcore.AnyIOBackend, "connect_tcp", new_callable=AsyncMock) as dial:
        await network.connect_tcp("example.invalid", 443)
        dial.assert_awaited_once_with("93.184.216.34", 443, local_address=None, socket_options=None)
        resolver.return_value = [*answer, (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with pytest.raises(httpcore.ConnectError, match="prohibited"):
            await network.connect_tcp("example.invalid", 443)
        assert dial.await_count == 1


@pytest.mark.asyncio
async def test_transport_binds_host_and_never_follows_redirect(monkeypatch):
    seen = []

    async def respond(transport, request):
        seen.append((request.url.host, request.headers["host"]))
        return httpx.Response(302, headers={"Location": "https://other.invalid/"})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", respond)
    base = target_policy.parse_target("https://example.invalid")
    async with target_policy.target_client(base) as client:
        response = await client.get(str(base), headers={"Host": "other.invalid"})
        assert response.status_code == 302
        with pytest.raises(httpx.ConnectError, match="verified target origin"):
            await client.get("https://other.invalid/")
    assert seen == [("example.invalid", "example.invalid")]


@pytest.mark.asyncio
async def test_guard_can_verify_only_its_original_origin(monkeypatch):
    store = SimpleNamespace(
        target_url="https://example.invalid/orders", guard_id="guard", bypass_secret="fixture",
        creator_device_hash="", is_sandbox=False, active_guard_active=True, revoked_guard_ids=set(),
        expires_at=time.time() + 60, bound_host_hash=None, expected_file_sha256="a" * 64,
        get_remaining_seconds=lambda: 60,
        mark_verified=lambda: None,
    )
    store.set_target_template = target_service.ActiveTargetStore.set_target_template.__get__(store)
    monkeypatch.setattr(target_service, "target_store", store)
    monkeypatch.setattr(target_service, "is_guard_burned", lambda guard_id: None)
    attempted = []
    replies = []

    def handshake(request):
        attempted.append(request.url.path)
        host_tag = "b" * 64
        message = json.dumps([
            "pusher-ownership-v2", "https://example.invalid", "guard", request.url.params["nonce"],
            store.expected_file_sha256, host_tag,
        ], separators=(",", ":")).encode()
        proof = hmac.new(b"fixture", message, hashlib.sha256).hexdigest()
        payload = {
            "status": "ACTIVE", "guard_id": "guard", "proof": proof,
            "file_sha256": store.expected_file_sha256, "host_fingerprint": host_tag,
        }
        replies.append(payload)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        target_service, "target_client", lambda url: httpx.AsyncClient(transport=httpx.MockTransport(handshake))
    )
    refused = await target_service.verify_target_handshake("https://other.invalid", "guard")
    verified = await target_service.verify_target_handshake(store.target_url, "guard")
    assert refused[0] is False
    assert verified[0] is True
    assert attempted == ["/__pusher_verify"]
    previous = replies[0]
    monkeypatch.setattr(target_service, "target_client", lambda url: httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=previous)),
    ))
    assert (await target_service.verify_target_handshake(store.target_url, "guard"))[0] is False
    previous["file_sha256"] = "c" * 64
    assert (await target_service.verify_target_handshake(store.target_url, "guard"))[0] is False


def test_execution_routes_require_current_verification(monkeypatch):
    store = SimpleNamespace(is_sandbox=False, target_url=None)
    monkeypatch.setattr(target_service, "target_store", store)
    monkeypatch.setattr(auth_deps, "resolve_operator", AsyncMock(
        return_value=AuthenticatedUser(user_id="default_test_user", email_confirmed=True)
    ))
    with TestClient(app) as client:
        for endpoint, payload in (
            ("/api/load/start", {"target_url": "https://example.invalid"}),
            ("/api/target/waf-probe", {"target_url": "https://example.invalid"}),
            ("/api/journey/dry-run", {"steps": [{"path": "/orders"}]}),
        ):
            result = client.post(endpoint, json=payload)
            assert result.status_code == 403
            assert "Verify the target" in result.json()["detail"]


@pytest.mark.asyncio
async def test_checked_network_backend_dns_cache_timeout_and_dns_timeout(monkeypatch):
    loop = asyncio.get_running_loop()
    answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    resolver = AsyncMock(return_value=answer)
    monkeypatch.setattr(loop, "getaddrinfo", resolver)

    cached_net = target_policy.CheckedNetworkBackend(False, dns_cache_ttl=60.0)
    with patch.object(httpcore.AnyIOBackend, "connect_tcp", new_callable=AsyncMock) as dial:
        await cached_net.connect_tcp("example.invalid", 443, timeout=2.5)
        await cached_net.connect_tcp("example.invalid", 443, timeout=2.5)
        assert resolver.await_count == 1
        assert dial.await_count == 2
        dial.assert_awaited_with("93.184.216.34", 443, local_address=None, socket_options=None, timeout=2.5)

    monkeypatch.setattr(loop, "getaddrinfo", AsyncMock(side_effect=TimeoutError))
    with pytest.raises(target_policy.DestinationTimeoutError):
        await target_policy.resolve_addresses("example.invalid", 443, False)
    uncached_net = target_policy.CheckedNetworkBackend(False)
    with pytest.raises(httpcore.ConnectTimeout):
        await uncached_net.connect_tcp("example.invalid", 443)


@pytest.mark.asyncio
async def test_target_transport_sharding_and_fast_origin_path(monkeypatch):
    base = target_policy.parse_target("https://example.invalid")
    transport = target_policy.TargetTransport(base, is_sandbox=False, connections=100)
    assert isinstance(transport._pool, target_policy._ShardedAsyncConnectionPool)
    assert all(shard._max_connections <= 24 for shard in transport._pool._shards)
    assert sum(shard._max_connections for shard in transport._pool._shards) == 100

    monkeypatch.setattr(target_policy, "bound_target", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("unexpected slow path")))
    seen = []

    async def respond(self_transport, request):
        seen.append(request.headers["host"])
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", respond)
    async with httpx.AsyncClient(transport=transport) as client:
        res = await client.get("https://example.invalid/fast?_cb=1")
        assert res.status_code == 200
    assert seen == ["example.invalid"]

import httpx
import pytest

from backend.core import journey_service
from backend.core.config import settings
from backend.main import app


def test_content_type_is_inferred_for_json_and_preserved_when_explicit():
    headers = {}
    assert journey_service.encode_journey_body({"token": "value"}, {}, headers) == b'{"token": "value"}'
    assert headers == {"Content-Type": "application/json"}
    explicit = {"content-type": "text/plain"}
    assert journey_service.encode_journey_body('{"ok":true}', {}, explicit) == b'{"ok":true}'
    assert explicit == {"content-type": "text/plain"}


@pytest.mark.asyncio
async def test_sandbox_journey_and_catalog_through_the_api(monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", True)
    monkeypatch.setattr(settings, "host", "127.0.0.1")
    monkeypatch.setattr(settings, "port", 8000)
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    seen_auth = []

    async def target(scope, receive, send):
        seen_auth.append(dict(scope["headers"]).get(b"authorization"))
        await app(scope, receive, send)

    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    monkeypatch.setattr(
        journey_service, "target_client",
        lambda *a, **kw: httpx.AsyncClient(transport=httpx.ASGITransport(app=target)),
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        target_check = await client.post("/api/target/verify", json={
            "target_url": "http://127.0.0.1:8000/api/sandbox/target", "is_sandbox": True,
        })
        assert target_check.status_code == 200
        steps = (await client.get("/api/journey/sandbox-defaults")).raise_for_status().json()["steps"]
        saved = await client.post("/api/journey/save", json={"steps": steps})
        assert saved.status_code == 200
        dry_run = await client.post("/api/journey/dry-run", json={"steps": steps})
        assert dry_run.status_code == 200
        assert dry_run.json()["all_passed"]
        assert len(dry_run.json()["steps"]) == 3
        assert seen_auth[1] == ("Bearer " + dry_run.json()["extracted_context"]["token"]).encode()
        catalog = await client.get("/api/sandbox/items")
        assert catalog.json()[-1]["sku"] == "LAST"
        assert len(catalog.json()) == 141


@pytest.mark.asyncio
async def test_sandbox_defaults_require_operator_and_local_mode(monkeypatch):
    from backend.api import auth_deps
    from backend.core.jwks_verifier import AuthenticatedUser

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        monkeypatch.setattr(settings, "offline_dev", False)
        assert (await client.get("/api/journey/sandbox-defaults")).status_code == 401

        async def resolve(*args):
            return AuthenticatedUser(user_id="sandbox-check", email="fixture@example.invalid", email_confirmed=True)

        monkeypatch.setattr(auth_deps, "resolve_operator", resolve)
        monkeypatch.setattr(settings, "pusher_mode", "shared")
        assert (await client.get("/api/journey/sandbox-defaults")).status_code == 404

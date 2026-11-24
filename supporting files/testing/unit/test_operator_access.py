import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from backend.core.config import settings
from backend.core.database import db_save_active_target
from backend.core.jwks_verifier import jwks_verifier
from backend.core.load_engine import load_engine
from backend.core.report_service import get_run, save_run
from backend.core.request_owner import request_owner
from backend.main import app


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", False)
    monkeypatch.setattr(settings, "supabase_url", "https://auth.example.invalid")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "isolated-operator-fixture")
    monkeypatch.setattr(jwks_verifier, "_expected_issuer", "https://auth.example.invalid/auth/v1")

    def make(subject, expires_in=60):
        return jwt.encode(dict(
            sub=subject, email=f"{subject}@example.invalid", aud="authenticated",
            iss=jwks_verifier._expected_issuer, exp=int(time.time()) + expires_in,
            email_confirmed_at="2026-01-01",
        ), settings.supabase_jwt_secret, algorithm="HS256")

    return make


def test_missing_and_expired_sessions_are_denied(token):
    with TestClient(app) as client:
        for endpoint in ("/api/profile", "/api/target/status", "/api/traffic/config", "/api/journey", "/api/history"):
            assert client.get(endpoint).status_code == 401
        response = client.get("/api/profile", headers={"Authorization": f"Bearer {token('old', -60)}"})
        assert response.status_code == 401


def test_profile_journey_traffic_and_reports_are_owner_scoped(token, monkeypatch):
    first = {"Authorization": f"Bearer {token('alice')}"}
    second = {"Authorization": f"Bearer {token('bob')}"}
    save_run({"run_id": "RUN-LEGACY-ACCESS-CHECK"})
    context = request_owner.set("supabase:alice")
    try:
        save_run({"run_id": "RUN-ALICE-ACCESS-CHECK"})
        db_save_active_target({
            "target_url": "https://alice.example.invalid",
            "guard_id": "test-alice-guard",
        }, request_owner.get())
    finally:
        request_owner.reset(context)
    with TestClient(app) as client:
        profile = client.put("/api/profile", headers=first, json={"full_name": "Alice"})
        assert profile.json()["full_name"] == "Alice"
        assert client.get("/api/profile?user_key=supabase:alice", headers=second).json()["full_name"] != "Alice"
        assert client.post("/api/journey/save", headers=first, json={"steps": [{"path": "/orders"}]}).status_code == 200
        assert client.get("/api/journey", headers=second).json()["steps"] == []
        assert client.get("/api/target/status", headers=first).json()["guard_id"] == "test-alice-guard"
        assert client.get("/api/target/status", headers=second).json()["guard_id"] is None
        assert client.post("/api/traffic/config", headers=first, json={"virtual_users": 350}).status_code == 200
        assert client.get("/api/traffic/config", headers=second).json()["virtual_users"] != 350
        assert client.get("/api/reports/RUN-ALICE-ACCESS-CHECK", headers=second).status_code == 404
        assert client.delete("/api/history", headers=second).status_code == 200
        assert client.get("/api/reports/RUN-ALICE-ACCESS-CHECK", headers=first).status_code == 200
        assert client.get("/api/reports/RUN-LEGACY-ACCESS-CHECK", headers=first).status_code == 404
        assert get_run("RUN-LEGACY-ACCESS-CHECK") is not None
        monkeypatch.setattr(load_engine, "is_running", True)
        monkeypatch.setattr(load_engine, "owner_id", "supabase:alice")
        assert client.post("/api/load/stop", headers=second).status_code == 403
        assert client.get("/api/load/status", headers=second).json()["is_running"] is False


def test_websocket_requires_valid_session(token):
    with TestClient(app) as client:
        with client.websocket_connect("/api/load/ws") as connection:
            connection.send_text(token("alice", -60))
            with pytest.raises(WebSocketDisconnect) as closed:
                connection.receive_text()
            assert closed.value.code == 1008
        with client.websocket_connect("/api/load/ws") as connection:
            connection.send_text(token("alice"))
            assert connection.receive_json()["event"] == "SNAPSHOT"


def test_stop_is_bound_to_the_current_run_and_owner(token, monkeypatch):
    owner = {"Authorization": f"Bearer {token('alice')}"}
    other = {"Authorization": f"Bearer {token('bob')}"}
    monkeypatch.setattr(load_engine, "is_running", True)
    monkeypatch.setattr(load_engine, "owner_id", "supabase:alice")
    monkeypatch.setattr(load_engine, "run_id", "RUN-CURRENT")
    monkeypatch.setattr(load_engine, "start_time", time.time())

    async def finish(**kwargs):
        load_engine.is_running = False

    stop = AsyncMock(side_effect=finish)
    monkeypatch.setattr(load_engine, "stop", stop)

    with TestClient(app) as client:
        snapshot = client.get("/api/load/status", headers=owner).json()
        assert snapshot["is_running"] and snapshot["run_id"] == "RUN-CURRENT"
        hidden = client.get("/api/load/status", headers=other).json()
        assert not hidden["is_running"] and hidden["run_id"] is None
        assert client.post("/api/load/stop", headers=other, json={"run_id": "RUN-CURRENT"}).status_code == 403
        assert client.post("/api/load/stop", headers=owner, json={"run_id": "RUN-PREVIOUS"}).status_code == 409
        stop.assert_not_awaited()
        response = client.post("/api/load/stop", headers=owner, json={"run_id": snapshot["run_id"]})

    assert response.status_code == 200
    stopped = response.json()["snapshot"]
    assert stopped["run_id"] == "RUN-CURRENT" and not stopped["is_running"]
    assert stopped["status_revision"] > snapshot["status_revision"]
    stop.assert_awaited_once_with(reason="MANUAL_ABORT")


def test_offline_is_explicit_and_loopback_only(monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", True)
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(settings, "host", "127.0.0.1")
    with TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 50000)) as local:
        assert local.get("/api/session").json()["offline"] is True
        assert local.get("/api/session", headers={"Origin": "https://example.invalid"}).status_code == 401
    with TestClient(app, base_url="http://localhost:8000", client=("192.0.2.1", 50000)) as remote:
        assert remote.get("/api/session").status_code == 401

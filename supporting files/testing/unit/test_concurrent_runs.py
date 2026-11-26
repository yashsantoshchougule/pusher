import asyncio
from contextlib import asynccontextmanager
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.api import load_router
from backend.core import database, load_engine as engine_module
from backend.core.config import settings
from backend.core.jwks_verifier import jwks_verifier
from backend.core.run_manager import run_manager
from backend.main import app


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", False)
    monkeypatch.setattr(settings, "supabase_url", "https://auth.example.invalid")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "isolated-concurrent-fixture")
    monkeypatch.setattr(jwks_verifier, "_expected_issuer", "https://auth.example.invalid/auth/v1")

    def make(subject, expires_in=60):
        return jwt.encode(
            {
                "sub": subject,
                "email": f"{subject}@example.invalid",
                "aud": "authenticated",
                "iss": jwks_verifier._expected_issuer,
                "exp": int(time.time()) + expires_in,
                "email_confirmed_at": "2026-01-01",
            },
            settings.supabase_jwt_secret,
            algorithm="HS256",
        )

    return make


def test_multiple_operators_can_run_and_stop_concurrently(token, monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "concurrent.sqlite")
    database.init_all_tables()
    run_manager.reset()
    monkeypatch.setattr(settings, "pusher_mode", "local_dev")
    monkeypatch.setattr(settings, "port", 8000)

    @asynccontextmanager
    async def slow_mock_client(*args, **kwargs):
        async def respond(request):
            await asyncio.sleep(0.05)
            return httpx.Response(200, content=b"OK" * 16)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            yield client

    monkeypatch.setattr(engine_module, "target_client", slow_mock_client)
    monkeypatch.setattr(load_router, "get_os_fd_cap", lambda: 20)

    alice_hdr = {"Authorization": f"Bearer {token('alice')}"}
    bob_hdr = {"Authorization": f"Bearer {token('bob')}"}

    for owner in ("supabase:alice", "supabase:bob"):
        database.db_save_active_target(
            {
                "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                "is_sandbox": True,
                "guard_id": f"guard-{owner}",
                "handshake_secret": "sec",
                "expected_file_sha256": "a" * 64,
                "creator_device_hash": "dev",
                "bound_host_hash": "host",
                "issued_at": time.time(),
                "expires_at": time.time() + 3600,
                "active_guard_active": True,
                "is_verified": True,
            },
            owner,
        )

    try:
        with TestClient(app) as client:
            # 1. Start Alice (12 VUs) and Bob (6 VUs) simultaneously
            r_alice = client.post(
                "/api/load/start",
                headers=alice_hdr,
                json={
                    "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                    "traffic_mode": "steady_crowd",
                    "target_vus": 12,
                    "duration_sec": 5,
                    "ram_limit_mb": 250,
                    "is_sandbox": True,
                },
            )
            assert r_alice.status_code == 200
            alice_run_id = r_alice.json()["run_id"]

            r_bob = client.post(
                "/api/load/start",
                headers=bob_hdr,
                json={
                    "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                    "traffic_mode": "steady_crowd",
                    "target_vus": 6,
                    "duration_sec": 5,
                    "ram_limit_mb": 250,
                    "is_sandbox": True,
                },
            )
            assert r_bob.status_code == 200
            bob_run_id = r_bob.json()["run_id"]
            assert alice_run_id != bob_run_id

            # 2. Same user duplicate start rejected (409)
            dup_alice = client.post(
                "/api/load/start",
                headers=alice_hdr,
                json={
                    "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                    "traffic_mode": "steady_crowd",
                    "target_vus": 2,
                    "duration_sec": 5,
                    "ram_limit_mb": 250,
                    "is_sandbox": True,
                },
            )
            assert dup_alice.status_code == 409

            # 3. Third user Charlie requesting > remaining host quota (20 - 18 = 2) rejected (409)
            charlie_hdr = {"Authorization": f"Bearer {token('charlie')}"}
            database.db_save_active_target(
                {
                    "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                    "is_sandbox": True,
                    "guard_id": "guard-charlie",
                    "handshake_secret": "sec",
                    "expected_file_sha256": "a" * 64,
                    "creator_device_hash": "dev",
                    "bound_host_hash": "host",
                    "issued_at": time.time(),
                    "expires_at": time.time() + 3600,
                    "active_guard_active": True,
                    "is_verified": True,
                },
                "supabase:charlie",
            )
            over_charlie = client.post(
                "/api/load/start",
                headers=charlie_hdr,
                json={
                    "target_url": "http://127.0.0.1:8000/api/sandbox/target",
                    "traffic_mode": "steady_crowd",
                    "target_vus": 5,
                    "duration_sec": 5,
                    "ram_limit_mb": 250,
                    "is_sandbox": True,
                },
            )
            assert over_charlie.status_code == 409

            # 4. Status isolation & explicit run_id routing
            s_alice = client.get("/api/load/status", headers=alice_hdr).json()
            s_bob = client.get("/api/load/status", headers=bob_hdr).json()
            assert s_alice["run_id"] == alice_run_id and s_alice["is_running"] is True
            assert s_bob["run_id"] == bob_run_id and s_bob["is_running"] is True

            # Cross-owner stop denied with 403
            assert client.post("/api/load/stop", headers=bob_hdr, json={"run_id": alice_run_id}).status_code == 403

            # 5. Stopping Alice keeps Bob running!
            stop_alice = client.post("/api/load/stop", headers=alice_hdr, json={"run_id": alice_run_id})
            assert stop_alice.status_code == 200
            assert stop_alice.json()["snapshot"]["is_running"] is False
            assert client.get("/api/load/status", headers=bob_hdr).json()["is_running"] is True

            stop_bob = client.post("/api/load/stop", headers=bob_hdr, json={"run_id": bob_run_id})
            assert stop_bob.status_code == 200
            assert stop_bob.json()["snapshot"]["is_running"] is False
    finally:
        run_manager.reset()

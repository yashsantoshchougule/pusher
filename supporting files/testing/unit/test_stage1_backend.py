"""
Unit Tests for Backend Stage 1:
- System Hardware & Resource Limits
- SSRF Boundary Validation
- Sealed 48h pusher_guard.py Generation & Integrity
- Challenge-Response Target Verification & Kill Revocation
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

class TestSystemLimitsEndpoint:
    def test_get_system_limits_contract(self):
        response = client.get("/api/system/limits")
        assert response.status_code == 200
        data = response.json()
        assert "total_system_ram_mb" in data
        assert data["total_system_ram_mb"] > 0
        assert data["max_safe_ram_mb"] == int(data["total_system_ram_mb"] * 0.75)
        assert data["default_ram_limit_mb"] == 500
        assert data["base_engine_ram_mb"] == 50
        assert data["ram_per_vu_mb"] == 0.20
        assert data["max_vus_at_default"] == 2250
        assert data["fd_cap_pct"] == 70


class TestSsrfValidationEndpoint:
    def test_reject_invalid_scheme(self):
        response = client.post("/api/target/validate-ssrf", json={"target_url": "ftp://malicious.org"})
        assert response.status_code == 400
        assert response.json()["valid"] is False

    def test_reject_loopback_ip(self):
        response = client.post("/api/target/validate-ssrf", json={"target_url": "http://127.0.0.1:8080/api"})
        assert response.status_code == 400
        assert response.json()["valid"] is False
        assert "loopback" in response.json()["detail"].lower() or "private" in response.json()["detail"].lower()

    def test_reject_localhost(self):
        response = client.post("/api/target/validate-ssrf", json={"target_url": "http://localhost:3000"})
        assert response.status_code == 400
        assert response.json()["valid"] is False

    def test_reject_private_network(self):
        response = client.post("/api/target/validate-ssrf", json={"target_url": "http://192.168.1.100"})
        assert response.status_code == 400
        assert response.json()["valid"] is False

    def test_reject_cloud_metadata(self):
        response = client.post("/api/target/validate-ssrf", json={"target_url": "http://169.254.169.254/latest/meta-data"})
        assert response.status_code == 400
        assert response.json()["valid"] is False

    def test_allow_sandbox_mode(self):
        response = client.post("/api/target/validate-ssrf", json={
            "target_url": "http://sandbox.pusher.local/api",
            "is_sandbox": True
        })
        assert response.status_code == 200
        assert response.json()["valid"] is True


class TestPusherGuardGenerator:
    def test_generate_sealed_48h_guard(self):
        response = client.post("/api/target/generate-guard", json={
            "target_url": "https://api.myproject.dev"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["guard_id"].startswith("PG-")
        assert data["guard_id"].endswith("-48H")
        assert data["expires_at"] - data["issued_at"] == 172800  # 48 hours in seconds
        assert "pusher_guard.py" in data["filename"]
        assert "__pusher_verify" in data["content"]
        assert "SHA-256" in data["content"] or "sha256" in data["content"]


class TestTargetVerificationLifecycle:
    def test_sandbox_verification_and_kill_lifecycle(self):
        # 1. Generate Guard
        gen_res = client.post("/api/target/generate-guard", json={"target_url": "https://api.sandbox.dev"})
        assert gen_res.status_code == 200
        guard_id = gen_res.json()["guard_id"]

        # 2. Verify in Sandbox mode
        verify_res = client.post("/api/target/verify", json={
            "target_url": "https://api.sandbox.dev",
            "guard_id": guard_id,
            "is_sandbox": True
        })
        assert verify_res.status_code == 200
        verify_data = verify_res.json()
        assert verify_data["is_verified"] is True
        assert verify_data["guard_id"] == guard_id
        assert verify_data["remaining_seconds"] > 170000

        # 3. Check status
        status_res = client.get("/api/target/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["is_verified"] is True
        assert status_data["guard_id"] == guard_id

        # 4. Kill token
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200
        kill_data = kill_res.json()
        assert kill_data["is_verified"] is False

        # 5. Check status after kill
        status_after = client.get("/api/target/status")
        assert status_after.status_code == 200
        assert status_after.json()["is_verified"] is False


class TestGuardRateLimiterAndBurnRegistry:
    def test_guard_superseding_burns_previous_id(self):
        from backend.core.target_service import target_store
        # Reset timestamps and sets for clean test run
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None

        # 1. Generate Token 1
        res1 = client.post("/api/target/generate-guard", json={"target_url": "https://api.test1.dev"})
        assert res1.status_code == 200
        token1 = res1.json()["guard_id"]

        # 2. Generate Token 2 (supersedes Token 1)
        res2 = client.post("/api/target/generate-guard", json={"target_url": "https://api.test2.dev"})
        assert res2.status_code == 200
        token2 = res2.json()["guard_id"]
        assert token2 != token1
        assert res2.json()["superseded_guard_id"] == token1

        # 3. Attempt to verify Token 1 -> must fail with HTTP 403 Forbidden
        verify_t1 = client.post("/api/target/verify", json={
            "target_url": "https://api.test1.dev",
            "guard_id": token1,
            "is_sandbox": True
        })
        assert verify_t1.status_code == 403
        assert "revoked" in verify_t1.json()["detail"].lower() or "burned" in verify_t1.json()["detail"].lower()

        # 4. Verify Token 2 -> succeeds
        verify_t2 = client.post("/api/target/verify", json={
            "target_url": "https://api.test2.dev",
            "guard_id": token2,
            "is_sandbox": True
        })
        assert verify_t2.status_code == 200
        assert verify_t2.json()["is_verified"] is True

    def test_guard_daily_rate_limiter_max_3(self):
        from backend.core.target_service import target_store
        # Reset timestamps
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None

        # Attempt 1
        r1 = client.post("/api/target/generate-guard", json={"target_url": "https://gen1.dev"})
        assert r1.status_code == 200
        assert r1.json()["daily_generations_used"] == 1
        assert r1.json()["daily_generations_remaining"] == 2

        # Attempt 2
        r2 = client.post("/api/target/generate-guard", json={"target_url": "https://gen2.dev"})
        assert r2.status_code == 200
        assert r2.json()["daily_generations_used"] == 2
        assert r2.json()["daily_generations_remaining"] == 1

        # Attempt 3
        r3 = client.post("/api/target/generate-guard", json={"target_url": "https://gen3.dev"})
        assert r3.status_code == 200
        t3_id = r3.json()["guard_id"]
        assert r3.json()["daily_generations_used"] == 3
        assert r3.json()["daily_generations_remaining"] == 0

        # Attempt 4 -> 429 Too Many Requests
        r4 = client.post("/api/target/generate-guard", json={"target_url": "https://gen4.dev"})
        assert r4.status_code == 429
        assert "24h" in r4.json()["detail"].lower() or "limit" in r4.json()["detail"].lower() or "rate" in r4.json()["detail"].lower()

        # Check that 3rd token was NOT revoked or overwritten
        status_res = client.get("/api/target/status")
        assert status_res.status_code == 200
        s_data = status_res.json()
        assert s_data["guard_id"] == t3_id
        assert s_data["daily_generations_used"] == 3
        assert s_data["daily_generations_remaining"] == 0

    def test_kill_permanently_burns_id(self):
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None

        # Generate guard
        r = client.post("/api/target/generate-guard", json={"target_url": "https://killtest.dev"})
        assert r.status_code == 200
        guard_id = r.json()["guard_id"]

        # Kill guard
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200
        assert kill_res.json()["is_verified"] is False
        assert guard_id in target_store.revoked_guard_ids

        # Attempt verify killed guard -> 403 Forbidden
        v_res = client.post("/api/target/verify", json={
            "target_url": "https://killtest.dev",
            "guard_id": guard_id,
            "is_sandbox": True
        })
        assert v_res.status_code == 403
        assert "revoked" in v_res.json()["detail"].lower() or "burned" in v_res.json()["detail"].lower()


class TestSandboxModeBypassAndKillReset:
    def test_sandbox_mode_bypasses_dns_lookup_for_api_myproject_dev(self):
        # 1. Validate SSRF with api.myproject.dev and is_sandbox: True
        ssrf_res = client.post("/api/target/validate-ssrf", json={
            "target_url": "https://api.myproject.dev",
            "is_sandbox": True,
        })
        assert ssrf_res.status_code == 200
        assert ssrf_res.json()["valid"] is True

        # 2. Verify target with api.myproject.dev without triggering getaddrinfo
        ver_res = client.post("/api/target/verify", json={
            "target_url": "https://api.myproject.dev",
            "guard_id": "PG-SNDB-48H",
            "is_sandbox": True,
        })
        assert ver_res.status_code == 200
        data = ver_res.json()
        assert data["is_verified"] is True
        assert data["remaining_seconds"] == 172800

        # 3. Kill guard resets active guard_id to None
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200
        status_res = client.get("/api/target/status")
        assert status_res.status_code == 200
        assert status_res.json()["guard_id"] is None
        assert status_res.json()["is_verified"] is False


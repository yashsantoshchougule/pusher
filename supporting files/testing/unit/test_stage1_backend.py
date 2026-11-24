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
    def test_traffic_preview_uses_the_engine_schedule_parameters(self):
        from backend.core.load_engine import calculate_active_vus

        data = client.get("/api/system/limits").json()
        schedule = data["traffic_schedule"]
        step = 30 / len(schedule["step_ratios"])
        assert [
            calculate_active_vus("step_ramp", 100, 30, step * index)
            for index in range(len(schedule["step_ratios"]))
        ] == [round(100 * ratio) for ratio in schedule["step_ratios"]]
        cutoff = schedule["rush_warmup_seconds"]
        assert calculate_active_vus("sudden_rush", 105, 30, cutoff - 0.01) == max(
            schedule["rush_warmup_min_vus"], round(105 * schedule["rush_warmup_ratio"]),
        )
        assert calculate_active_vus("sudden_rush", 105, 30, cutoff) == 105
        assert data["max_p95_ceiling_ms"] == 8000

    def test_limits_expose_the_effective_engine_worker_cap(self, monkeypatch):
        from backend.api import system_router

        monkeypatch.setattr(system_router, "get_os_fd_cap", lambda: 123)
        response = client.get("/api/system/limits")
        assert response.status_code == 200
        assert response.json()["max_worker_vus"] == 123

        monkeypatch.setattr(system_router, "get_os_fd_cap", lambda: 250_000)
        assert client.get("/api/system/limits").json()["max_worker_vus"] == 100_000

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
        assert "prohibited" in response.json()["detail"].lower()

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
        client.post("/api/target/kill")
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
    def test_sandbox_status_and_direct_verification(self, monkeypatch):
        from backend.core.config import settings

        monkeypatch.setattr(settings, "port", 8123)
        initial = client.get("/api/target/status").json()
        assert initial["sandbox_url"] == "http://127.0.0.1:8123/api/sandbox/target"
        assert initial["guard_id"] is None

        verified = client.post("/api/target/verify", json={
            "target_url": initial["sandbox_url"],
            "is_sandbox": True,
        })
        assert verified.status_code == 200
        assert verified.json()["is_verified"] is True
        status = client.get("/api/target/status").json()
        assert status["is_sandbox"] is True
        assert status["daily_generations_used"] == initial["daily_generations_used"] == 0

        monkeypatch.setattr(settings, "pusher_mode", "production")
        assert client.get("/api/target/status").json()["sandbox_url"] is None

    def test_status_reports_persisted_revocation_with_stale_target(self, monkeypatch):
        from backend.core import database, target_service

        verify = client.post("/api/target/verify", json={
            "target_url": "https://sandbox.pusher.local",
            "is_sandbox": True,
        })
        assert verify.status_code == 200
        guard_id = verify.json()["guard_id"]
        assert client.get("/api/target/status").json()["is_verified"] is True

        database.db_burn_guard(guard_id, "DEVICE_MISMATCH_VIOLATION")

        def assert_revoked_status():
            response = client.get("/api/target/status")
            assert response.status_code == 200
            status = response.json()
            assert status["guard_id"] == guard_id
            assert status["is_burned"] is True
            assert status["is_verified"] is False
            assert status["active_guard_active"] is False
            assert status["remaining_seconds"] == 0
            assert status["last_burn_reason"] == "DEVICE_MISMATCH_VIOLATION"

        assert_revoked_status()
        monkeypatch.setattr(target_service.target_store, "expires_at", 1)
        assert_revoked_status()

    def test_sandbox_verification_and_kill_lifecycle(self):
        # 1. Kill any prior guard, then generate Guard
        client.post("/api/target/kill")
        gen_res = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert gen_res.status_code == 200
        guard_id = gen_res.json()["guard_id"]

        # 2. Verify in Sandbox mode
        verify_res = client.post("/api/target/verify", json={
            "target_url": "https://sandbox.pusher.local",
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

    def test_sandbox_verification_myproject_dev_no_dns_error(self):
        client.post("/api/target/kill")
        gen_res = client.post("/api/target/generate-guard", json={
            "target_url": "https://api.myproject.dev",
            "is_sandbox": True
        })
        assert gen_res.status_code == 200
        guard_id = gen_res.json()["guard_id"]

        verify_res = client.post("/api/target/verify", json={
            "target_url": "https://api.myproject.dev",
            "guard_id": guard_id,
            "is_sandbox": True
        })
        assert verify_res.status_code == 200
        data = verify_res.json()
        assert data["is_verified"] is True
        assert data["remaining_seconds"] == 172800

        status_res = client.get("/api/target/status")
        assert status_res.status_code == 200
        assert status_res.json()["is_sandbox"] is True


class TestGuardRateLimiterAndBurnRegistry:
    def test_kill_first_rule_blocks_second_guard_with_409(self):
        from backend.core.target_service import target_store
        # Reset state for clean test run
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None
        target_store.guard_id = None

        # 1. Generate Token 1
        res1 = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert res1.status_code == 200
        token1 = res1.json()["guard_id"]

        # 2. Attempt to generate Token 2 without killing Token 1 -> MUST RETURN 409 CONFLICT!
        res_conflict = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert res_conflict.status_code == 409
        assert "kill" in res_conflict.json()["detail"].lower() or "active guard" in res_conflict.json()["detail"].lower()

        # 3. Kill Token 1
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200

        # 4. Now generate Token 2 succeeds
        res2 = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert res2.status_code == 200
        token2 = res2.json()["guard_id"]
        assert token2 != token1

        # 5. Token 1 is burned in revocation registry -> verification returns 403 Forbidden
        verify_t1 = client.post("/api/target/verify", json={
            "target_url": "https://sandbox.pusher.local",
            "guard_id": token1,
            "is_sandbox": True
        })
        assert verify_t1.status_code == 403
        assert "revoked" in str(verify_t1.json()["detail"]).lower() or "burned" in str(verify_t1.json()["detail"]).lower()

    def test_guard_daily_rate_limiter_max_3(self):
        from backend.core.target_service import target_store
        # Reset timestamps
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None
        target_store.guard_id = None

        # Attempt 1
        r1 = client.post("/api/target/generate-guard", json={"target_url": "https://gen1.dev"})
        assert r1.status_code == 200
        assert r1.json()["daily_generations_used"] == 1
        assert r1.json()["daily_generations_remaining"] == 2
        client.post("/api/target/kill")

        # Attempt 2
        r2 = client.post("/api/target/generate-guard", json={"target_url": "https://gen2.dev"})
        assert r2.status_code == 200
        assert r2.json()["daily_generations_used"] == 2
        assert r2.json()["daily_generations_remaining"] == 1
        client.post("/api/target/kill")

        # Attempt 3
        r3 = client.post("/api/target/generate-guard", json={"target_url": "https://gen3.dev"})
        assert r3.status_code == 200
        t3_id = r3.json()["guard_id"]
        assert r3.json()["daily_generations_used"] == 3
        assert r3.json()["daily_generations_remaining"] == 0
        client.post("/api/target/kill")

        # Attempt 4 -> 429 Too Many Requests
        r4 = client.post("/api/target/generate-guard", json={"target_url": "https://gen4.dev"})
        assert r4.status_code == 429
        assert "24" in r4.json()["detail"].lower() or "limit" in r4.json()["detail"].lower() or "rate" in r4.json()["detail"].lower()

    def test_tampering_with_one_character_raises_runtime_error(self, tmp_path):
        import runpy
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        target_store.guard_id = None
        r = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert r.status_code == 200
        content = r.json()["content"]

        # Intact file execution
        intact_path = tmp_path / "pusher_guard.py"
        intact_path.write_text(content, encoding="utf-8")
        mod = runpy.run_path(str(intact_path))
        assert "setup_pusher_guard" in mod

        # Tampered file execution (change single character)
        tampered_content = content.replace("Pusher", "Qusher", 1)
        tampered_path = tmp_path / "pusher_guard_tampered.py"
        tampered_path.write_text(tampered_content, encoding="utf-8")

        with pytest.raises(RuntimeError, match="PUSHER GUARD LOCKED"):
            runpy.run_path(str(tampered_path))

    def test_guard_mounts_and_preserves_protected_routes(self, tmp_path, monkeypatch):
        import hashlib
        import runpy
        import time
        from types import SimpleNamespace

        from fastapi import Depends, FastAPI, Request
        from jose import jwt
        from starlette.applications import Starlette

        from backend.api import auth_deps
        from backend.core.config import settings
        from backend.core.security import SlidingWindowRateLimiter

        response = client.post("/api/target/generate-guard", json={
            "target_url": "https://sandbox.pusher.local", "is_sandbox": True,
        })
        assert response.status_code == 200
        artifact = response.json()
        raw = artifact["content"].encode("utf-8")
        path = tmp_path / "pusher_guard.py"
        path.write_bytes(raw)
        assert hashlib.sha256(raw).hexdigest() == artifact["checksum_sha256"]
        compile(raw, str(path), "exec")
        guard = runpy.run_path(str(path))
        guard["setup_pusher_guard"].__globals__["time"] = SimpleNamespace(time=lambda: artifact["expires_at"])
        application = FastAPI()

        @application.get("/protected")
        async def protected(request: Request, actor=Depends(auth_deps.get_current_user)):
            return {"user": actor.user_id, "address": request.client.host}

        @application.get("/admin")
        async def admin(actor=Depends(auth_deps.get_admin_user)):
            return {"user": actor.user_id}

        guard["setup_pusher_guard"](application)
        starlette = Starlette()
        guard["setup_pusher_guard"](starlette)
        assert TestClient(starlette).get("/__pusher_verify").status_code == 403
        test = TestClient(application)
        assert not application.user_middleware
        assert test.get("/__pusher_verify").status_code == 403
        assert test.get("/protected", headers={"X-Pusher-Guard-ID": "invalid"}).status_code == 401
        token = jwt.encode({
            "sub": "ordinary-test-user", "email": "fixture@example.invalid",
            "aud": "authenticated", "iss": f"{settings.supabase_url}/auth/v1",
            "exp": int(time.time()) + 60,
        }, settings.supabase_jwt_secret, algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        monkeypatch.setattr(auth_deps, "auth_rate_limiter", SlidingWindowRateLimiter(max_requests=2))
        assert test.get("/admin", headers=headers).status_code == 403
        res_data = test.get("/protected", headers=headers).json()
        assert res_data["user"] == "ordinary-test-user"
        assert test.get("/protected", headers=headers).status_code == 429

    def test_kill_permanently_burns_id(self):
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None
        target_store.guard_id = None

        # Generate guard
        r = client.post("/api/target/generate-guard", json={"target_url": "https://sandbox.pusher.local", "is_sandbox": True})
        assert r.status_code == 200
        guard_id = r.json()["guard_id"]

        # Kill guard
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200
        assert kill_res.json()["is_verified"] is False
        assert guard_id in target_store.revoked_guard_ids

        # Attempt verify killed guard -> 403 Forbidden
        v_res = client.post("/api/target/verify", json={
            "target_url": "https://sandbox.pusher.local",
            "guard_id": guard_id,
            "is_sandbox": True
        })
        assert v_res.status_code == 403
        assert "revoked" in str(v_res.json()["detail"]).lower() or "burned" in str(v_res.json()["detail"]).lower()


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
        import secrets
        sandbox_guard_id = f"PG-SNDB-{secrets.token_hex(2).upper()}-48H"
        ver_res = client.post("/api/target/verify", json={
            "target_url": "https://api.myproject.dev",
            "guard_id": sandbox_guard_id,
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


class TestWafProbeEndpoint:
    def test_waf_probe_sandbox_simulation_success(self):
        assert client.post("/api/target/verify", json={
            "target_url": "https://api.myproject.dev", "is_sandbox": True,
        }).status_code == 200
        res = client.post("/api/target/waf-probe", json={
            "target_url": "https://api.myproject.dev",
            "is_sandbox": True
        })
        assert res.status_code == 200
        data = res.json()
        assert data["simulated"] is True
        assert data["status_code"] is None
        assert data["edge_hint"] is None
        assert data["latency_ms"] is None

    def test_waf_probe_rejects_unverified_destination(self):
        response = client.post("/api/target/waf-probe", json={"target_url": "https://example.invalid"})
        assert response.status_code == 403
        assert "Verify the target" in response.json()["detail"]

    def test_waf_probe_rejects_empty_target(self):
        res = client.post("/api/target/waf-probe", json={
            "target_url": "   ",
            "is_sandbox": False
        })
        assert res.status_code == 400


class TestDeviceBoundLockAndTombstoneRegistry:
    def test_same_device_success(self):
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        client.post("/api/target/kill", headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"})

        # Generate on DEV-ALPHA-001
        res_gen = client.post(
            "/api/target/generate-guard",
            json={"target_url": "https://api.myproject.dev", "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_gen.status_code == 200
        guard_id = res_gen.json()["guard_id"]

        # Verify on same device DEV-ALPHA-001
        res_verify = client.post(
            "/api/target/verify",
            json={"target_url": "https://api.myproject.dev", "guard_id": guard_id, "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_verify.status_code == 200
        assert res_verify.json()["is_verified"] is True
        assert res_verify.json()["remaining_seconds"] > 170000

    def test_cross_device_kill_and_timer_stop(self):
        from backend.core.target_service import target_store, is_guard_burned
        target_store.generation_timestamps.clear()
        client.post("/api/target/kill")

        # 1. Generate Guard on DEV-ALPHA-001
        res_gen = client.post(
            "/api/target/generate-guard",
            json={"target_url": "https://api.myproject.dev", "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_gen.status_code == 200
        guard_id = res_gen.json()["guard_id"]

        # 2. Attempt verification from foreign device DEV-BETA-002 -> MUST RETURN 403 & BURN
        res_foreign = client.post(
            "/api/target/verify",
            json={"target_url": "https://api.myproject.dev", "guard_id": guard_id, "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-BETA-002"}
        )
        assert res_foreign.status_code == 403
        f_detail = res_foreign.json()["detail"]
        f_msg = f_detail["detail"] if isinstance(f_detail, dict) else str(f_detail)
        assert "DEVICE SECURITY VIOLATION" in f_msg

        # 3. Check SQLite tombstone registry
        burned_record = is_guard_burned(guard_id)
        assert burned_record is not None
        assert burned_record["burn_reason"] == "DEVICE_MISMATCH_VIOLATION"

        # 4. Timer stopped
        status_res = client.get("/api/target/status")
        assert status_res.status_code == 200
        assert status_res.json()["remaining_seconds"] == 0
        assert status_res.json()["is_verified"] is False

        # 5. Original creator DEV-ALPHA-001 is now ALSO permanently blocked from using that ID
        res_alpha_blocked = client.post(
            "/api/target/verify",
            json={"target_url": "https://api.myproject.dev", "guard_id": guard_id, "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_alpha_blocked.status_code == 403
        a_detail = res_alpha_blocked.json()["detail"]
        a_msg = a_detail["detail"] if isinstance(a_detail, dict) else str(a_detail)
        assert "permanently burned" in a_msg or "403" in a_msg

    def test_cross_device_load_start_aborts_and_burns(self):
        from backend.core.target_service import target_store, is_guard_burned
        target_store.generation_timestamps.clear()
        client.post("/api/target/kill")

        # Generate on DEV-ALPHA-001
        res_gen = client.post(
            "/api/target/generate-guard",
            json={"target_url": "https://api.prodtest.dev"},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        guard_id = res_gen.json()["guard_id"]

        target_store.mark_verified()

        # Attempt to start load test from foreign device DEV-GAMMA-003
        res_load = client.post(
            "/api/load/start",
            json={
                "target_url": "https://api.prodtest.dev",
                "traffic_mode": "step_ramp",
                "target_vus": 10,
                "duration_sec": 10,
                "ram_limit_mb": 500,
                "is_sandbox": False
            },
            headers={"X-Pusher-Device-ID": "DEV-GAMMA-003"}
        )
        assert res_load.status_code == 403
        assert "DEVICE SECURITY VIOLATION" in str(res_load.json()["detail"])

        # Confirm burned in SQLite
        assert is_guard_burned(guard_id) is not None
        assert is_guard_burned(guard_id)["burn_reason"] == "DEVICE_MISMATCH_VIOLATION"

    def test_48h_expiry_auto_kill(self):
        import time
        from backend.core.target_service import target_store, is_guard_burned
        target_store.generation_timestamps.clear()
        client.post("/api/target/kill")

        # Generate on DEV-ALPHA-001
        res_gen = client.post(
            "/api/target/generate-guard",
            json={"target_url": "https://api.myproject.dev", "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        guard_id = res_gen.json()["guard_id"]

        # Advance expires_at into the past (expired 10 seconds ago)
        target_store.expires_at = int(time.time()) - 10

        # Verification check should auto-kill with EXPIRED_48H and return 403
        res_expired = client.post(
            "/api/target/verify",
            json={"target_url": "https://api.myproject.dev", "guard_id": guard_id, "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_expired.status_code == 403
        e_detail = res_expired.json()["detail"]
        e_msg = e_detail["detail"] if isinstance(e_detail, dict) else str(e_detail)
        assert "expired" in e_msg.lower() or "burned" in e_msg.lower()

        # Check SQLite tombstone
        burned_record = is_guard_burned(guard_id)
        assert burned_record is not None
        assert burned_record["burn_reason"] == "EXPIRED_48H"

    def test_manual_kill_burns_in_sqlite(self):
        from backend.core.target_service import target_store, is_guard_burned
        target_store.generation_timestamps.clear()
        client.post("/api/target/kill")

        # Generate on DEV-ALPHA-001
        res_gen = client.post(
            "/api/target/generate-guard",
            json={"target_url": "https://api.myproject.dev", "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        guard_id = res_gen.json()["guard_id"]

        # Manual Kill from creator
        kill_res = client.post("/api/target/kill", headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"})
        assert kill_res.status_code == 200

        # Check SQLite tombstone
        burned_record = is_guard_burned(guard_id)
        assert burned_record is not None
        assert burned_record["burn_reason"] == "MANUAL_USER_KILL"

        # Verification of burned ID now fails with 403
        res_reverify = client.post(
            "/api/target/verify",
            json={"target_url": "https://api.myproject.dev", "guard_id": guard_id, "is_sandbox": True},
            headers={"X-Pusher-Device-ID": "DEV-ALPHA-001"}
        )
        assert res_reverify.status_code == 403


class TestLiveUrlReachabilityAndDnsValidator:
    def test_nonexistent_domain_returns_dns_not_found(self):
        res = client.post("/api/target/validate-url", json={
            "target_url": "https://gitb-nonexistent-domain-9999.com/",
            "is_sandbox": False
        })
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["reachable"] is False
        assert data["status"] == "DNS_REJECTED"
        assert "could not be resolved" in data["message"]

    def test_close_domain_typo_suggests_github(self):
        res = client.post("/api/target/validate-url", json={
            "target_url": "https://gitb.com/",
            "is_sandbox": False
        })
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["reachable"] is False
        assert data["status"] == "DNS_REJECTED"
        assert any("github.com" in s for s in data["suggestions"])

    def test_ssrf_private_ip_returns_ssrf_blocked(self):
        res = client.post("/api/target/validate-url", json={
            "target_url": "http://127.0.0.1:8000",
            "is_sandbox": False
        })
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["reachable"] is False
        assert data["status"] == "DNS_REJECTED"
        assert "prohibited" in data["message"]

    def test_generate_guard_rejects_nonexistent_domain_with_422(self):
        client.post("/api/target/kill")
        res = client.post("/api/target/generate-guard", json={
            "target_url": "https://gitb-nonexistent-domain-9999.com/",
            "is_sandbox": False
        })
        assert res.status_code == 422
        detail = str(res.json()["detail"])
        assert "INCORRECT URL" in detail or "does not exist" in detail or "could not be resolved" in detail





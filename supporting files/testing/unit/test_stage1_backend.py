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
    def test_sandbox_verification_and_kill_lifecycle(self):
        # 1. Kill any prior guard, then generate Guard
        client.post("/api/target/kill")
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
    def test_kill_first_rule_blocks_second_guard_with_409(self):
        from backend.core.target_service import target_store
        # Reset state for clean test run
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None
        target_store.guard_id = None

        # 1. Generate Token 1
        res1 = client.post("/api/target/generate-guard", json={"target_url": "https://api.test1.dev"})
        assert res1.status_code == 200
        token1 = res1.json()["guard_id"]

        # 2. Attempt to generate Token 2 without killing Token 1 -> MUST RETURN 409 CONFLICT!
        res_conflict = client.post("/api/target/generate-guard", json={"target_url": "https://api.test2.dev"})
        assert res_conflict.status_code == 409
        assert "kill" in res_conflict.json()["detail"].lower() or "active guard" in res_conflict.json()["detail"].lower()

        # 3. Kill Token 1
        kill_res = client.post("/api/target/kill")
        assert kill_res.status_code == 200

        # 4. Now generate Token 2 succeeds
        res2 = client.post("/api/target/generate-guard", json={"target_url": "https://api.test2.dev"})
        assert res2.status_code == 200
        token2 = res2.json()["guard_id"]
        assert token2 != token1

        # 5. Token 1 is burned in revocation registry -> verification returns 403 Forbidden
        verify_t1 = client.post("/api/target/verify", json={
            "target_url": "https://api.test1.dev",
            "guard_id": token1,
            "is_sandbox": True
        })
        assert verify_t1.status_code == 403
        assert "revoked" in verify_t1.json()["detail"].lower() or "burned" in verify_t1.json()["detail"].lower()

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
        r = client.post("/api/target/generate-guard", json={"target_url": "https://tampertest.dev"})
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

    def test_signed_request_activates_pusher_bypass(self, tmp_path):
        import runpy, hmac, hashlib, time
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient as SubClient
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        target_store.guard_id = None
        r = client.post("/api/target/generate-guard", json={"target_url": "https://bypasstest.dev"})
        assert r.status_code == 200
        guard_id = r.json()["guard_id"]
        secret = target_store.bypass_secret

        guard_path = tmp_path / "pusher_guard.py"
        guard_path.write_text(r.json()["content"], encoding="utf-8")
        mod = runpy.run_path(str(guard_path))

        test_app = FastAPI()
        mod["setup_pusher_guard"](test_app)

        @test_app.get("/api/protected-data")
        def sample_protected(request: Request):
            return {
                "pusher_bypass": getattr(request.state, "pusher_bypass", False),
                "auth": request.headers.get("authorization"),
                "user": request.scope.get("user"),
                "client": request.scope.get("client"),
            }

        tc = SubClient(test_app)

        # 1. Unsigned request -> pusher_bypass is False, no synthetic auth injected
        un_res = tc.get("/api/protected-data")
        assert un_res.status_code == 200
        assert un_res.json()["pusher_bypass"] is False
        assert un_res.json()["auth"] is None

        # 2. Cryptographically signed request -> pusher_bypass is True, synthetic auth injected
        curr_min = str(int(time.time() // 60))
        sig = hmac.new(secret.encode("utf-8"), f"{guard_id}:{curr_min}".encode("utf-8"), hashlib.sha256).hexdigest()
        sig_res = tc.get("/api/protected-data", headers={
            "X-Pusher-Guard-ID": guard_id,
            "X-Pusher-Timestamp": curr_min,
            "X-Pusher-Signature": sig,
        })
        assert sig_res.status_code == 200
        data = sig_res.json()
        assert data["pusher_bypass"] is True
        assert f"Bearer pusher_bypass_{guard_id}" in data["auth"]
        assert data["user"]["role"] == "load_tester"
        assert data["client"][0].startswith("198.51.100.")

    def test_kill_permanently_burns_id(self):
        from backend.core.target_service import target_store
        target_store.generation_timestamps.clear()
        target_store.revoked_guard_ids.clear()
        target_store.issued_guard_ids.clear()
        target_store.last_revoked_guard_id = None
        target_store.guard_id = None

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
        res = client.post("/api/target/waf-probe", json={
            "target_url": "https://api.myproject.dev",
            "is_sandbox": True
        })
        assert res.status_code == 200
        data = res.json()
        assert data["bypass_passed"] is True
        assert data["status_code"] == 200
        assert "WAF BYPASS VERIFIED" in data["recommendation"]
        assert "X-Pusher-Guard-Token" in data["injected_headers"]
        assert data["injected_headers"]["User-Agent"] == "Pusher-LoadEngine/1.0"
        assert data["latency_ms"] >= 0

    def test_waf_probe_ssrf_rejects_private_ip(self):
        res = client.post("/api/target/waf-probe", json={
            "target_url": "http://192.168.1.1",
            "is_sandbox": False
        })
        assert res.status_code == 400
        data = res.json()
        assert "loopback" in str(data).lower() or "private" in str(data).lower()

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




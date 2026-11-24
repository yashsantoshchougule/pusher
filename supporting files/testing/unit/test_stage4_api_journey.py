"""
Unit and Integration Tests for Backend Stage 4:
- Multi-Step Sandbox Endpoints (/api/sandbox/login, /api/sandbox/items, /api/sandbox/checkout)
- Journey Storage & Same-Origin SSRF Step Validation (/api/journey, /api/journey/save)
- 1-VU Dry-Run Validator (/api/journey/dry-run)
- Sequential Multi-Step Load Engine Execution & Step Metrics
"""

import asyncio
import pytest
import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.load_engine import load_engine

client = TestClient(app)


def test_sandbox_multi_step_endpoints():
    """Verify built-in multi-step sandbox endpoints respond with expected contracts."""
    # 1. Login
    res_login = client.post("/api/sandbox/login", json={"email": "tester@pusher.dev", "password": "pass"})
    assert res_login.status_code == 200
    data_login = res_login.json()
    assert data_login["status"] == "ok"
    assert "token" in data_login
    token = data_login["token"]

    # 2. Items
    res_items = client.get("/api/sandbox/items", headers={"Authorization": f"Bearer {token}"})
    assert res_items.status_code == 200
    assert len(res_items.content) >= 4096

    # 3. Checkout
    res_checkout = client.post(
        "/api/sandbox/checkout",
        json={"item_id": "ITEM-101", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_checkout.status_code in (200, 201)
    data_checkout = res_checkout.json()
    assert data_checkout["status"] == "confirmed"
    assert "order_id" in data_checkout


def test_journey_save_and_get():
    """Verify saving a journey and retrieving it."""
    steps = [
        {
            "step_id": 1,
            "name": "Auth Login",
            "method": "POST",
            "path": "/api/sandbox/login",
            "headers": {"Content-Type": "application/json"},
            "body": '{"username": "demo", "password": "password"}',
            "expected_status": 200,
            "extract_json_key": "token",
        },
        {
            "step_id": 2,
            "name": "Catalog Query",
            "method": "GET",
            "path": "/api/sandbox/items",
            "headers": {"Authorization": "Bearer {{token}}"},
            "body": "",
            "expected_status": 200,
            "extract_json_key": None,
        },
    ]

    payload = {"steps": steps, "use_journey": True}
    res_save = client.post("/api/journey/save", json=payload)
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "saved"

    res_get = client.get("/api/journey")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["use_journey"] is True
    assert len(data["steps"]) == 2
    assert data["steps"][0]["name"] == "Auth Login"


def test_journey_ssrf_cross_origin_rejection():
    assert client.post("/api/target/verify", json={
        "is_sandbox": True, "target_url": "http://127.0.0.1:8000/api/sandbox/target",
    }).status_code == 200
    """Verify steps pointing to external/cross-origin or private loopback URLs are rejected."""
    bad_steps = [
        {
            "step_id": 1,
            "name": "Evil SSRF",
            "method": "GET",
            "path": "http://169.254.169.254/latest/meta-data",
            "expected_status": 200,
        }
    ]
    res = client.post("/api/journey/save", json={"steps": bad_steps, "use_journey": True})
    assert res.status_code in (400, 422)
    assert "ssrf" in res.json()["detail"].lower() or "origin" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_journey_dry_run_execution():
    """Verify 1-VU dry-run validator runs sequential chain and extracts {{token}}."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        verification = await ac.post("/api/target/verify", json={
            "is_sandbox": True, "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        })
        assert verification.status_code == 200
        steps = [
            {
                "step_id": 1,
                "name": "Step 1: Login",
                "method": "POST",
                "path": "/api/sandbox/login",
                "body": '{"user": "test"}',
                "expected_status": 200,
                "extract_json_key": "token",
            },
            {
                "step_id": 2,
                "name": "Step 2: Items",
                "method": "GET",
                "path": "/api/sandbox/items",
                "headers": {"Authorization": "Bearer {{token}}"},
                "expected_status": 200,
            },
            {
                "step_id": 3,
                "name": "Step 3: Checkout",
                "method": "POST",
                "path": "/api/sandbox/checkout",
                "headers": {"Authorization": "Bearer {{token}}"},
                "body": '{"item": "book"}',
                "expected_status": 201,
            },
        ]
        res = await ac.post("/api/journey/dry-run", json={"steps": steps})
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) == 3
        assert results[0]["passed"] is True
        assert results[0]["extracted_var"] == "token"
        assert results[1]["passed"] is True
        assert results[2]["passed"] is True
        assert results[2]["status_code"] == 201


@pytest.mark.asyncio
async def test_multi_step_load_engine_execution():
    """Verify launching a load test with use_journey=True populates step_metrics."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        verification = await ac.post("/api/target/verify", json={
            "is_sandbox": True, "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        })
        assert verification.status_code == 200
        start_payload = {
            "target_url": "http://127.0.0.1:8000/api/sandbox/target",
            "traffic_mode": "steady_crowd",
            "target_vus": 10,
            "duration_sec": 8,
            "ram_limit_mb": 500,
            "is_sandbox": True,
            "use_journey": True,
            "journey_steps": [{"path": "/api/sandbox/items"}],
        }
        res_start = await ac.post("/api/load/start", json=start_payload)
        assert res_start.status_code == 200
        assert load_engine.is_running is True

        await asyncio.sleep(0.05)
        res_status = await ac.get("/api/load/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["use_journey"] is True
        assert "step_metrics" in status_data
        assert len(status_data["step_metrics"]) >= 1

        # Stop test
        await ac.post("/api/load/stop")
        assert load_engine.is_running is False

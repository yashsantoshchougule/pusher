"""
Unit Tests for Backend Stage 2:
- Async Load Engine Worker Pool
- 4 KB Chunk-Discard Streaming Worker
- 3 Traffic Modes (Step-Ramp, Sudden Rush, Steady Crowd)
- Dynamic Cache-Busting (?_cb=nonce)
- Pre-flight Security & Circuit Breakers
- FastAPI Endpoints: /api/sandbox/target, /api/load/start, /api/load/stop, /api/load/status
"""

import asyncio
import time
import pytest
import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.load_engine import (
    LoadEngine,
    calculate_active_vus,
    append_cache_buster,
    calculate_max_allowed_vus,
    BASE_ENGINE_RAM_MB,
    RAM_PER_VU_MB,
)
from backend.core.target_service import target_store


client = TestClient(app)


def test_memory_and_vu_scaling_formula():
    """Verify locked contract: BASE=50MB, PER_VU=0.20MB, 500MB=2250 VUs, 250MB=1000 VUs."""
    assert calculate_max_allowed_vus(500) == 2250
    assert calculate_max_allowed_vus(250) == 1000
    assert calculate_max_allowed_vus(1024) == 4870


def test_traffic_mode_schedulers():
    """Verify traffic schedulers across duration: Step-Ramp (5 steps), Sudden Rush (3s warmup), Steady Crowd."""
    target_vus = 100
    duration = 50

    # 1. Step-Ramp: 5 equal steps (20%, 40%, 60%, 80%, 100%)
    assert calculate_active_vus("step_ramp", target_vus, duration, elapsed=5) == 20   # step 1 (0-10s)
    assert calculate_active_vus("step_ramp", target_vus, duration, elapsed=15) == 40  # step 2 (10-20s)
    assert calculate_active_vus("step_ramp", target_vus, duration, elapsed=25) == 60  # step 3 (20-30s)
    assert calculate_active_vus("step_ramp", target_vus, duration, elapsed=35) == 80  # step 4 (30-40s)
    assert calculate_active_vus("step_ramp", target_vus, duration, elapsed=45) == 100 # step 5 (40-50s)

    # 2. Sudden Rush: 3s warmup at 10% (min 10), then instant 100%
    assert calculate_active_vus("sudden_rush", target_vus, duration, elapsed=1) == 10  # warmup
    assert calculate_active_vus("sudden_rush", target_vus, duration, elapsed=2) == 10  # warmup
    assert calculate_active_vus("sudden_rush", target_vus, duration, elapsed=4) == 100 # surge
    assert calculate_active_vus("sudden_rush", target_vus, duration, elapsed=20) == 100

    # 3. Steady Crowd: 100% constant concurrency
    assert calculate_active_vus("steady_crowd", target_vus, duration, elapsed=1) == 100
    assert calculate_active_vus("steady_crowd", target_vus, duration, elapsed=25) == 100
    assert calculate_active_vus("steady_crowd", target_vus, duration, elapsed=49) == 100


def test_dynamic_cache_buster():
    """Verify ?_cb=nonce and &_cb=nonce query parameter generation."""
    url1 = "https://api.example.com/items"
    cb_url1 = append_cache_buster(url1, vu_id=3, req_seq=42)
    assert "?_cb=" in cb_url1
    assert "_3_42" in cb_url1

    url2 = "https://api.example.com/items?category=books"
    cb_url2 = append_cache_buster(url2, vu_id=1, req_seq=5)
    assert "&_cb=" in cb_url2
    assert "category=books" in cb_url2


def test_sandbox_target_endpoint():
    """Verify /api/sandbox/target returns streamable 4 KB chunked response."""
    res = client.get("/api/sandbox/target")
    assert res.status_code == 200
    assert "X-Pusher-Sandbox" in res.headers
    # Body contains at least 4 KB
    assert len(res.content) >= 4096


def test_load_start_validation_rejects_unverified_target():
    """Verify load start rejects unverified external targets with 403 Forbidden."""
    target_store.kill() # Ensure no active verified target
    payload = {
        "target_url": "https://api.external.com",
        "traffic_mode": "steady_crowd",
        "target_vus": 50,
        "duration_sec": 10,
        "is_sandbox": False,
    }
    res = client.post("/api/load/start", json=payload)
    assert res.status_code == 403
    assert "verify the target" in res.json()["detail"].lower()


def test_load_start_validation_rejects_excessive_vus():
    """Verify load start rejects VUs exceeding ram_limit_mb calculation."""
    payload = {
        "target_url": "https://sandbox.pusher.local",
        "traffic_mode": "steady_crowd",
        "target_vus": 3000, # 500 MB allows max 2250 VUs
        "duration_sec": 10,
        "ram_limit_mb": 500,
        "is_sandbox": True,
    }
    res = client.post("/api/load/start", json=payload)
    assert res.status_code == 422
    assert "exceeds" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_load_start_stop_status_lifecycle():
    """Verify full start -> status -> stop lifecycle against built-in sandbox."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        verification = await ac.post("/api/target/verify", json={
            "is_sandbox": True, "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        })
        assert verification.status_code == 200
        # 1. Start sandbox test
        start_payload = {
            "target_url": "http://127.0.0.1:8000/api/sandbox/target",
            "traffic_mode": "step_ramp",
            "target_vus": 20,
            "duration_sec": 10,
            "ram_limit_mb": 500,
            "is_sandbox": True,
        }
        res_start = await ac.post("/api/load/start", json=start_payload)
        assert res_start.status_code == 200
        data = res_start.json()
        assert data["status"] == "started"

        # 2. Check status
        res_status = await ac.get("/api/load/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["is_running"] is True
        assert status_data["traffic_mode"] == "step_ramp"
        assert status_data["target_vus"] == 20

        # 3. Stop test
        res_stop = await ac.post("/api/load/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "stopped"

        # 4. Verify status is stopped
        await asyncio.sleep(0.3)
        res_status_after = await ac.get("/api/load/status")
        assert res_status_after.status_code == 200
        assert res_status_after.json()["is_running"] is False

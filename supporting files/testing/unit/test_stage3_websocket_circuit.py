"""
Unit and WebSocket Integration Tests for Backend Stage 3:
- WebSocket Telemetry Stream (WS /api/load/ws)
- Live Circuit-Breaker Fault Injection (POST /api/load/simulate-spike)
- Clean Disconnect and Snapshot Handshake
"""

import asyncio
import time
import pytest
import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.load_engine import load_engine

client = TestClient(app)


def test_simulate_spike_rejects_when_idle():
    """Calling /api/load/simulate-spike when no test is active must return 400 Bad Request."""
    res = client.post("/api/load/simulate-spike")
    assert res.status_code == 400
    assert "no active load test" in res.json()["detail"].lower()


def test_websocket_handshake_and_snapshot():
    """Client connecting to /api/load/ws must immediately receive an initial SNAPSHOT frame."""
    with client.websocket_connect("/api/load/ws") as ws:
        ws.send_text("")
        data = ws.receive_json()
        assert data["event"] == "SNAPSHOT"
        assert "is_running" in data
        assert "active_vus" in data
        assert "live_rps" in data
        assert "circuit_status" in data
        assert "run_history" not in data


@pytest.mark.asyncio
async def test_websocket_broadcast_delivery():
    """Verify load_engine.connection_manager broadcasts structured frames to active WebSockets."""
    class MockWebSocket:
        def __init__(self):
            self.sent_frames = []

        async def send_json(self, data):
            self.sent_frames.append(data)

    mock_ws = MockWebSocket()
    load_engine.connection_manager.register(mock_ws, load_engine.owner_id)

    try:
        await load_engine.broadcast_telemetry(event="TICK")
        assert len(mock_ws.sent_frames) == 1
        frame = mock_ws.sent_frames[0]
        assert frame["event"] == "TICK"
        assert "active_vus" in frame
        assert "live_rps" in frame
    finally:
        load_engine.connection_manager.disconnect(mock_ws)


@pytest.mark.asyncio
async def test_simulate_spike_circuit_trip_lifecycle():
    """Verify active test halts immediately and trips circuit breaker upon POST /api/load/simulate-spike."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        verification = await ac.post("/api/target/verify", json={
            "is_sandbox": True, "target_url": "http://127.0.0.1:8000/api/sandbox/target",
        })
        assert verification.status_code == 200
        # 1. Start sandbox test
        start_payload = {
            "target_url": "http://127.0.0.1:8000/api/sandbox/target",
            "traffic_mode": "steady_crowd",
            "target_vus": 20,
            "duration_sec": 15,
            "ram_limit_mb": 500,
            "is_sandbox": True,
        }
        res_start = await ac.post("/api/load/start", json=start_payload)
        assert res_start.status_code == 200
        assert load_engine.is_running is True

        # 2. Inject fault spike
        res_spike = await ac.post("/api/load/simulate-spike")
        assert res_spike.status_code == 200
        spike_data = res_spike.json()
        assert spike_data["status"] == "tripped"
        assert "TRIPPED" in spike_data["circuit_status"]

        # 3. Verify engine halted
        assert load_engine.is_running is False
        status_data = load_engine.get_status()
        assert "TRIPPED" in status_data["circuit_status"]

        history = (await ac.get("/api/history")).json()
        assert history["runs"][0]["verdict"] == "CIRCUIT_BREAKER"
        assert history["runs"][0]["run_id"] == spike_data["run_id"]

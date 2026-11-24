import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from backend.core import load_engine as engine_module
from backend.core.circuit_breakers import CircuitBreakers


def test_server_failure_and_rolling_ratio_boundaries():
    brakes = CircuitBreakers(90, 9000)
    for index in range(4):
        assert brakes.observe_status(index * 0.1, 503, {}) is None
    assert "consecutive" in brakes.observe_status(0.4, 503, {})

    brakes = CircuitBreakers(25, 8000)
    for index in range(19):
        code = 503 if index % 3 == 0 else 200
        assert brakes.observe_status(index * 0.1, code, {}) is None
    assert "rolling" in brakes.observe_status(1.9, 200, {})


def test_rate_limits_expire_and_firewall_status_needs_a_signature():
    brakes = CircuitBreakers(25, 8000)
    assert brakes.observe_status(0, 429, {}) is None
    assert brakes.observe_status(3.1, 429, {}) is None
    assert brakes.observe_status(4, 429, {}) is None
    assert "rate limit" in brakes.observe_status(6.1, 429, {})
    assert brakes.observe_status(7, 403, {}) is None
    assert "firewall" in brakes.observe_status(7, 403, {"cf-ray": "synthetic"})
    assert "firewall" in brakes.observe_preview(403, b"Cloudflare Ray ID")


def test_timeout_and_latency_sample_limits():
    brakes = CircuitBreakers(25, 8000)
    for index in range(19):
        brakes.observe_timing(index * 0.1, 20, index < 7)
    assert brakes.timing_reason(1.8) is None
    brakes.observe_timing(1.9, 20, False)
    assert "timed out" in brakes.timing_reason(1.9)
    assert brakes.timing_reason(12.0) is None

    brakes = CircuitBreakers(25, 100)
    for index in range(20):
        brakes.observe_timing(index * 0.1, 110, False)
    assert "p95" in brakes.timing_reason(1.9)


@pytest.mark.asyncio
@pytest.mark.parametrize("journey", [False, True])
async def test_both_workers_stop_on_mocked_rate_limit(journey, monkeypatch):
    count = 0

    def respond(request):
        nonlocal count
        count += 1
        return httpx.Response(429)

    @asynccontextmanager
    async def mocked_client(*args, **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            yield client

    monkeypatch.setattr(engine_module, "target_client", mocked_client)
    engine = engine_module.LoadEngine()
    await engine.start(
        "https://example.invalid", "steady_crowd", 1, 3,
        use_journey=journey, journey_steps=[{"path": "/resource"}],
    )
    await asyncio.wait_for(engine._master_task, 1)
    assert count == 3
    assert engine.status_429 == 3
    assert "TRIPPED" in engine.circuit_status


@pytest.mark.asyncio
async def test_request_deadline_includes_reading_response_body():
    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b""

    engine = engine_module.LoadEngine()
    engine.request_timeout_sec = 0.02
    transport = httpx.MockTransport(lambda _: httpx.Response(200, stream=StalledBody()))
    async with httpx.AsyncClient(transport=transport) as client:
        status, _, _, _, timed_out = await asyncio.wait_for(
            engine._read_response(client, "GET", "https://example.invalid", {}), 1
        )
    assert status == 0
    assert timed_out

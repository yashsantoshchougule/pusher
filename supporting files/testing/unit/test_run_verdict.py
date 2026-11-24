import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.api.report_router import export_report_endpoint
from backend.core import load_engine as engine_module, report_service


@pytest.mark.asyncio
@pytest.mark.parametrize(("statuses", "verdict"), [
    ([200, 404], "FAILED"),
    ([200, 404, 200, 200, 200, 404], "PASSED"),
])
async def test_journey_verdict_requires_a_complete_successful_cycle(monkeypatch, statuses, verdict):
    engine = engine_module.LoadEngine()
    responses = iter(statuses)
    requests = []

    def respond(request):
        requests.append(request.url.path)
        status = next(responses)
        if len(requests) == len(statuses):
            engine.start_time -= engine.duration_sec
        return httpx.Response(status)

    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ))
    run_id = await engine.start(
        "https://example.invalid", "steady_crowd", 1, 60, use_journey=True,
        journey_steps=[{"path": "/first"}, {"path": "/second"}],
    )
    await asyncio.wait_for(engine._master_task, 2)
    assert requests == ["/first", "/second"] * (len(statuses) // 2)
    assert report_service.get_run(run_id)["verdict"] == verdict
    assert json.loads((await export_report_endpoint(run_id)).body)["verdict"] == verdict


@pytest.mark.asyncio
async def test_journey_deadline_during_last_step_does_not_count_as_success(monkeypatch):
    engine = engine_module.LoadEngine()

    async def respond(request):
        if request.url.path == "/first":
            return httpx.Response(200)
        engine.start_time -= engine.duration_sec
        await asyncio.Event().wait()

    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ))
    run_id = await engine.start(
        "https://example.invalid", "steady_crowd", 1, 60, use_journey=True,
        journey_steps=[{"path": "/first"}, {"path": "/second"}],
    )
    await asyncio.wait_for(engine._master_task, 2)
    report = report_service.get_run(run_id)
    assert report["total_requests"] == 1
    assert report["verdict"] == "FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statuses, expected_status, verdict, successes, error_pct",
    [
        pytest.param([404, 404, 404], None, "FAILED", 0, 100.0, id="all-404"),
        pytest.param([], None, "FAILED", 0, None, id="no-requests"),
        pytest.param([200, 200], None, "PASSED", 2, 0.0, id="all-successful"),
        pytest.param([404, 200], None, "PASSED", 1, 50.0, id="mixed"),
        pytest.param([302], None, "PASSED", 1, 0.0, id="single-target-redirect-status"),
        pytest.param([404], 404, "PASSED", 1, 0.0, id="journey-expected-status"),
        pytest.param([201], 201, "PASSED", 1, 0.0, id="journey-expected-created"),
        pytest.param([201], 200, "FAILED", 0, 100.0, id="journey-unexpected-created"),
    ],
)
async def test_completed_run_verdict(monkeypatch, statuses, expected_status, verdict, successes, error_pct):
    engine = engine_module.LoadEngine()
    broadcast = AsyncMock()
    monkeypatch.setattr(engine, "broadcast_telemetry", broadcast)
    responses = iter(statuses)
    remaining = len(statuses)

    def respond(request):
        nonlocal remaining
        status = next(responses)
        remaining -= 1
        if not remaining:
            engine.start_time -= engine.duration_sec
        return httpx.Response(status)

    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ))
    run_id = await engine.start(
        "https://example.invalid", "steady_crowd", 1, 60, max_error_pct=1,
        use_journey=expected_status is not None,
        journey_steps=[{"path": "/", "expected_status": expected_status}],
    )
    if not statuses:
        engine.start_time -= engine.duration_sec
    await asyncio.wait_for(engine._master_task, 2)

    assert engine.total_requests - engine._failed_requests == successes
    saved = report_service.get_run(run_id)
    exported = json.loads((await export_report_endpoint(run_id)).body)
    for report in (saved, exported):
        assert report["total_requests"] == len(statuses)
        assert report["error_pct"] == error_pct
        assert report["verdict"] == verdict
    broadcast.assert_awaited_with(event="COMPLETE")


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True], ids=["manual-stop", "engine-cancellation"])
async def test_stopped_run_without_successes_preserves_abort_verdict(monkeypatch, cancel):
    engine = engine_module.LoadEngine()
    broadcast = AsyncMock()
    monkeypatch.setattr(engine, "broadcast_telemetry", broadcast)
    request_started = asyncio.Event()

    async def respond(request):
        request_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ))
    run_id = await engine.start("https://example.invalid", "steady_crowd", 1, 60)
    try:
        await asyncio.wait_for(request_started.wait(), 2)
        if cancel:
            engine._master_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(engine._master_task, 2)
        else:
            await asyncio.wait_for(engine.stop(), 2)
    finally:
        if not engine._master_task.done():
            await asyncio.wait_for(engine.stop(), 2)

    report = report_service.get_run(run_id)
    assert report["total_requests"] == 0
    assert report["verdict"] == "MANUAL_ABORT"
    reason = "ENGINE_SHUTDOWN" if cancel else "MANUAL_ABORT"
    assert report["status_label"] == f"MANUAL ABORT (STOPPED ({reason}))"
    broadcast.assert_awaited_with(event="STOP")

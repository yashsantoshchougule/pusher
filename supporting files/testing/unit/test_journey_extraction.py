import asyncio
import json

import httpx
import pytest

from backend.core import journey_service, load_engine as engine_module, report_service


STEPS = [
    {"path": "/login", "extract_json_key": "token"},
    {"path": "/orders?id={{token}}", "headers": {"Authorization": "Bearer {{token}}"},
     "method": "POST", "body": {"token": "{{token}}"}},
]


@pytest.mark.parametrize("body", [
    {"outer": [{"name": "{{name}}"}], "count": 0},
    '{"outer":[{"name":"{{name}}"}],"count":0}',
])
def test_journey_interpolation_preserves_url_and_json_values(body):
    context = {"lookup": "A+B", "name": 'Jo "J" Lee \\ QA'}
    headers = {}
    path, content = journey_service.prepare_journey_request(
        {"path": "/search?name={{lookup}}&page=2", "body": body}, context, headers,
    )
    assert httpx.URL("https://example.invalid" + path).params["name"] == "A+B"
    assert json.loads(content) == {"outer": [{"name": context["name"]}], "count": 0}
    assert headers["Content-Type"] == "application/json"


def test_journey_body_preserves_raw_bytes_and_explicit_plain_text():
    raw = '{ "signed" : "payload" }'
    assert journey_service.encode_journey_body(raw, {}, {}) == raw.encode()
    headers = {"content-type": "text/plain"}
    assert journey_service.encode_journey_body("Hello {{name}}", {"name": "Lee"}, headers) == b"Hello Lee"
    assert headers == {"content-type": "text/plain"}


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_bust", [False, True])
async def test_scheduled_and_dry_run_requests_match(monkeypatch, cache_bust):
    engine = engine_module.LoadEngine()
    requests = {}
    step = {"path": "/fixture?mode=test", "method": "POST", "body": {"check": True}}

    def client(label):
        def respond(request):
            requests[label] = request
            if label == "load":
                engine.start_time -= engine.duration_sec
            return httpx.Response(200)
        return httpx.AsyncClient(transport=httpx.MockTransport(respond))

    base = "https://example.invalid"
    async with client("dry") as transport:
        results, _ = await journey_service.execute_dry_run([step], base, transport, cache_bust=cache_bust)
    assert results[0]["passed"] is True
    monkeypatch.setattr(engine_module, "target_client", lambda *args, **kwargs: client("load"))
    run_id = await engine.start(base, "steady_crowd", 1, 60, cache_bust=cache_bust,
                                use_journey=True, journey_steps=[step])
    await asyncio.wait_for(engine._master_task, 2)
    assert report_service.get_run(run_id)["verdict"] == "PASSED"
    dry, load = requests["dry"], requests["load"]
    assert dry.method == load.method == "POST"
    assert dry.content == load.content
    assert dry.headers == load.headers
    assert set(dry.url.params) == set(load.url.params) == ({"mode", "_cb"} if cache_bust else {"mode"})
    assert dry.url.params["mode"] == load.url.params["mode"] == "test"


@pytest.mark.asyncio
@pytest.mark.parametrize("expected,passed", [(200, False), (201, True)])
async def test_dry_run_matches_only_the_requested_status(expected, passed):
    transport = httpx.MockTransport(lambda request: httpx.Response(201))
    async with httpx.AsyncClient(transport=transport) as client:
        results, _ = await journey_service.execute_dry_run(
            [{"path": "/created", "expected_status": expected}], "https://example.invalid", client,
        )
    assert results[0]["passed"] is passed


@pytest.mark.asyncio
@pytest.mark.parametrize("preview", [
    b"", b"{}", b"bad JSON", b'{"token": null}', b'{"token": " "}', b'{"token": []}', b'{"token": NaN}',
])
async def test_dry_run_stops_on_missing_or_invalid_extraction(preview):
    def respond(request):
        assert request.url.path == "/login"
        return httpx.Response(200, content=preview)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        results, context = await journey_service.execute_dry_run(STEPS, "https://example.invalid", client)
    assert len(results) == 1 and not results[0]["passed"]
    assert "required field 'token'" in results[0]["error"]
    assert not context


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["path", "headers", "body"])
async def test_unresolved_input_stops_before_network(field):
    step = {**STEPS[1], "path": "/orders", "headers": {}, "body": None, field: STEPS[1][field]}

    def respond(_):
        pytest.fail("unresolved placeholder reached transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        results, _ = await journey_service.execute_dry_run([step], "https://example.invalid", client)
    assert not results[0]["passed"] and "unavailable" in results[0]["error"]


@pytest.mark.parametrize("value", [0, False])
def test_falsy_scalar_extraction(value):
    preview = httpx.Response(200, json={"token": value}).content
    assert journey_service.extract_journey_value("token", preview) == str(value)


@pytest.mark.asyncio
async def test_load_worker_rejects_extraction_failure_after_success(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/orders":
            assert request.url.params["id"] == "synthetic-token"
            assert request.headers["Authorization"] == "Bearer synthetic-token"
            assert request.content == b'{"token": "synthetic-token"}'
        return httpx.Response(200, json={"token": "synthetic-token"} if len(calls) == 1 else {})

    monkeypatch.setattr(engine_module, "target_client", lambda *a, **kw:
                        httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    engine = engine_module.LoadEngine()
    run_id = await engine.start(
        "https://example.invalid", "steady_crowd", 1, 2,
        use_journey=True, journey_steps=STEPS,
    )
    await asyncio.wait_for(engine._master_task, 3)
    report = report_service.get_run(run_id)
    assert calls == ["/login", "/orders", "/login"]
    assert report["verdict"] == "FAILED"
    assert "required response field" in report["status_label"]
    assert report["step_metrics"][0]["failed"] == 1

import time

import pytest

from backend.core.journey_service import (
    DEFAULT_SANDBOX_STEPS,
    JourneyInputError,
    build_journey_request,
    compile_journey_step,
)
from backend.core.target_policy import DestinationError, parse_target


def test_compiled_journey_step_matches_dynamic_builder_and_reuses_static_objects():
    base = parse_target("https://example.invalid")
    static_step = {
        "name": "Login",
        "method": "POST",
        "path": "/api/login",
        "headers": {"X-App": "pusher"},
        "body": {"username": "tester", "password": "secret"},
        "expected_status": 200,
    }
    compiled_static = compile_journey_step(static_step, base, is_sandbox=False)
    url1, h1, b1 = compiled_static.build({}, cache_bust=True, vu_id=2, req_seq=5, run_epoch_ms=1700000000000)
    url2, h2, b2 = compiled_static.build({}, cache_bust=True, vu_id=2, req_seq=6, run_epoch_ms=1700000000000)

    assert url1 == "https://example.invalid/api/login?_cb=1700000000000_2_5"
    assert url2 == "https://example.invalid/api/login?_cb=1700000000000_2_6"
    # Static headers & encoded bytes objects are reused directly without copying!
    assert h1 is h2
    assert b1 is b2
    assert h1["Content-Type"] == "application/json"

    dynamic_step = {
        "name": "Order",
        "method": "POST",
        "path": "/orders/{{order_id}}",
        "headers": {"Authorization": "Bearer {{token}}"},
        "body": {"token": "{{token}}", "qty": 1},
        "expected_status": 201,
    }
    compiled_dyn = compile_journey_step(dynamic_step, base, is_sandbox=False)
    ctx = {"order_id": "A/1", "token": "tok_9"}
    u_fast, h_fast, b_fast = compiled_dyn.build(ctx, cache_bust=False, vu_id=1, req_seq=1, run_epoch_ms=1)
    u_ref, h_ref, b_ref = build_journey_request(dynamic_step, ctx, base, False, False, 1, 1)
    assert u_fast == u_ref
    assert h_fast == h_ref
    assert b_fast == b_ref

    with pytest.raises(JourneyInputError):
        compiled_dyn.build({}, cache_bust=False, vu_id=1, req_seq=1, run_epoch_ms=1)


def test_compiled_step_preserves_ssrf_origin_rejection():
    base = parse_target("https://example.invalid")
    bad_step = {"method": "GET", "path": "https://other.invalid/steal", "headers": {}, "body": ""}
    compiled = compile_journey_step(bad_step, base, is_sandbox=False)
    with pytest.raises(DestinationError, match="verified target origin"):
        compiled.build({}, cache_bust=False, vu_id=0, req_seq=1, run_epoch_ms=1)


def test_compiled_step_is_substantially_faster_than_uncompiled():
    base = parse_target("https://example.invalid")
    step = DEFAULT_SANDBOX_STEPS[0]
    compiled = compile_journey_step(step, base, is_sandbox=False)
    # Use public origin for benchmark
    pub_step = {**step, "path": "/api/sandbox/login"}
    compiled = compile_journey_step(pub_step, base, is_sandbox=False)

    t0 = time.perf_counter()
    for i in range(2000):
        compiled.build({}, True, 1, i, 1700000000000)
    compiled_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    for i in range(2000):
        build_journey_request(pub_step, {}, base, False, True, 1, i)
    uncompiled_ms = (time.perf_counter() - t1) * 1000.0

    assert compiled_ms < uncompiled_ms

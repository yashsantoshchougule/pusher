"""
Journey Router:
- Multi-Step Sandbox Endpoints: /api/sandbox/login, /api/sandbox/items, /api/sandbox/checkout
- Journey Storage & Same-Origin SSRF Step Validator: /api/journey, /api/journey/save
- 1-VU Dry-Run Validator: /api/journey/dry-run
"""

import asyncio
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.journey_service import (
    journey_store,
    validate_journey_steps,
    execute_dry_run,
)
from backend.core.target_service import target_store

router = APIRouter(prefix="/api", tags=["API Journey"])


# 1. Multi-Step Sandbox Endpoints
@router.post("/sandbox/login")
async def sandbox_login(req: dict = None):
    """Simulates realistic authentication & JWT/bearer session token issuance."""
    await asyncio.sleep(0.015)  # 15ms simulated auth overhead
    return {
        "status": "ok",
        "token": "sbx_tok_9065_valid",
        "user_id": 416,
        "token_type": "bearer",
        "expires_in": 3600,
    }


@router.get("/sandbox/items")
async def sandbox_items(request: Request):
    """Streams 4 KB-8 KB resource catalog payload with authorization support."""
    async def chunk_streamer():
        # Yield 2 x 4096-byte chunks (8 KB total)
        for _ in range(2):
            await asyncio.sleep(0.005)
            yield b"[" + b'{"id": 101, "sku": "PUSHER-VU-ITEM", "price": 49.99},' * 70 + b'{"id": 199, "sku": "LAST", "price": 99.99}]'

    return StreamingResponse(
        chunk_streamer(),
        media_type="application/json",
        headers={
            "X-Pusher-Sandbox": "true",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.post("/sandbox/checkout", status_code=status.HTTP_201_CREATED)
async def sandbox_checkout(req: dict = None):
    """Simulates realistic high-concurrency order placement and DB commit."""
    await asyncio.sleep(0.020)  # 20ms simulated checkout/payment latency
    return {
        "status": "confirmed",
        "order_id": "ORD-9065",
        "message": "Order processed successfully.",
    }


# 2. Journey CRUD & Dry-Run Models
class SaveJourneyRequest(BaseModel):
    steps: list[dict] = Field(..., min_length=1, max_length=10)
    use_journey: bool = Field(False, description="Enable multi-step journey in load engine")


class DryRunRequest(BaseModel):
    steps: list[dict] | None = None


@router.get("/journey")
async def get_journey_endpoint():
    """Retrieve saved journey steps, use_journey toggle state, and latest dry-run results."""
    return journey_store.get_journey()


@router.post("/journey/save")
async def save_journey_endpoint(req: SaveJourneyRequest):
    """Enforces Same-Origin SSRF validation and saves the ordered step chain."""
    is_sandbox = "sandbox" in (target_store.target_url or "").lower() or any(
        "/api/sandbox/" in s.get("path", "") for s in req.steps
    )
    is_valid, err_msg = validate_journey_steps(
        req.steps,
        active_target_url=target_store.target_url,
        is_sandbox=is_sandbox,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err_msg or "Invalid journey step specification.",
        )

    journey_store.save_journey(req.steps, use_journey=req.use_journey)
    return {
        "status": "saved",
        "count": len(req.steps),
        "steps": req.steps,
        "use_journey": req.use_journey,
        "message": "Journey chain saved successfully.",
    }


@router.post("/journey/dry-run")
async def dry_run_endpoint(req: DryRunRequest, request: Request):
    """
    Executes a 1-VU dry-run through each step sequentially, extracting {{token}}
    and returning an audit report for each step.
    """
    steps = req.steps if req.steps is not None else journey_store.steps
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No steps provided for dry run.")

    # Base URL determination
    base_url = str(request.base_url).rstrip("/")
    if target_store.target_url and not any("/api/sandbox/" in s.get("path", "") for s in steps):
        base_url = target_store.target_url.rstrip("/")

    guard_id = target_store.guard_id or "PG-ACTIVE"
    client = None
    if request.base_url.hostname in ("test", "testserver"):
        import httpx
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url=base_url)

    results = await execute_dry_run(steps, base_url=base_url, guard_id=guard_id, client=client)
    context = getattr(journey_store, "last_dry_run_context", {})
    journey_store.save_dry_run(results, context)

    total_ms = round(sum(r.get("latency_ms", 0.0) for r in results), 1)
    all_passed = len(results) == len(steps) and all(r.get("passed") for r in results)

    formatted_steps = []
    for r in results:
        ext_var = {r["extracted_var"]: context.get(r["extracted_var"])} if r.get("extracted_var") else None
        formatted_steps.append({
            "step_id": r.get("step_id"),
            "name": r.get("name"),
            "method": r.get("method"),
            "url": f"{base_url}{r.get('path')}" if r.get("path", "").startswith("/") else r.get("path"),
            "status_code": r.get("status_code"),
            "latency_ms": r.get("latency_ms"),
            "passed": r.get("passed"),
            "extracted_variable": ext_var,
            "error": r.get("error"),
        })

    return {
        "status": "completed",
        "results": results,
        "all_passed": all_passed,
        "total_steps": len(steps),
        "total_duration_ms": total_ms,
        "extracted_context": context,
        "steps": formatted_steps,
    }

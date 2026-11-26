"""
Journey Router:
- Multi-Step Sandbox Endpoints: /api/sandbox/login, /api/sandbox/items, /api/sandbox/checkout
- Journey Storage & Same-Origin SSRF Step Validator: /api/journey, /api/journey/save
- 1-VU Dry-Run Validator: /api/journey/dry-run
"""

import asyncio
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from backend.api.auth_deps import require_operator
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.database import db_get_traffic_config
from backend.core.db_async import run_db_read, run_db_write
from backend.core.dry_run_control import DryRunControl, active_dry_runs
from backend.core.request_owner import request_owner
from backend.core.journey_service import (
    DEFAULT_SANDBOX_STEPS,
    journey_store,
    validate_journey_steps,
    execute_dry_run,
)
from backend.core.target_service import DestinationError, active_target, verified_destination

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
        items = b'{"id": 101, "sku": "PUSHER-VU-ITEM", "price": 49.99},' * 70
        await asyncio.sleep(0.005)
        yield b"[" + items
        await asyncio.sleep(0.005)
        yield items + b'{"id": 199, "sku": "LAST", "price": 99.99}]'

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
    cache_bust: bool | None = None
    dry_run_id: str | None = Field(None, min_length=1, max_length=100)
    guard_id: str | None = Field(None, min_length=1, max_length=100)


class StopDryRunRequest(BaseModel):
    dry_run_id: str = Field(min_length=1, max_length=100)


@router.get("/journey", dependencies=[Depends(require_operator)])
async def get_journey_endpoint():
    """Retrieve saved journey steps, use_journey toggle state, and latest dry-run results."""
    return await run_db_read(journey_store.get_journey)


@router.get("/journey/sandbox-defaults", dependencies=[Depends(require_operator)])
async def get_sandbox_journey_defaults():
    if settings.pusher_mode != "local_dev":
        raise HTTPException(status_code=404, detail="The sandbox preset is available in local development.")
    return {"steps": DEFAULT_SANDBOX_STEPS}


@router.post("/journey/save", dependencies=[Depends(require_operator)])
async def save_journey_endpoint(req: SaveJourneyRequest):
    """Enforces Same-Origin SSRF validation and saves the ordered step chain."""
    target_store = active_target()
    is_valid, err_msg = validate_journey_steps(
        req.steps, active_target_url=target_store.target_url, is_sandbox=bool(target_store.is_sandbox),
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err_msg or "Invalid journey step specification.",
        )

    saved = await run_db_write(journey_store.save_journey, req.steps, use_journey=req.use_journey)
    return {
        "status": "saved",
        "count": len(req.steps),
        "steps": saved["steps"],
        "use_journey": req.use_journey,
        "message": "Journey chain saved successfully.",
    }


@router.post("/journey/dry-run/stop", dependencies=[Depends(require_operator)])
async def stop_dry_run_endpoint(req: StopDryRunRequest):
    run = next((run for run in active_dry_runs
                if run.owner_id == request_owner.get() and run.dry_run_id == req.dry_run_id), None)
    if run is None:
        raise HTTPException(status_code=404, detail="That dry run is no longer active or has not started yet.")
    run.cancel("stopped")
    await run.done.wait()
    return {"status": "stopped"}


@router.post("/journey/dry-run", dependencies=[Depends(require_operator)])
async def dry_run_endpoint(req: DryRunRequest):
    """
    Executes a 1-VU dry-run through each step sequentially, extracting {{token}}
    and returning an audit report for each step.
    """
    steps = req.steps if req.steps is not None else journey_store.steps
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No steps provided for dry run.")

    target_store = active_target()
    is_sandbox = bool(target_store.is_sandbox)
    if req.guard_id and req.guard_id != target_store.guard_id:
        raise HTTPException(status_code=409, detail="The verified target changed. Refresh the dashboard before running.")
    try:
        base_url = str(verified_destination(target_store.target_url or "", is_sandbox))
    except DestinationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    valid, message = validate_journey_steps(steps, base_url, is_sandbox, require_runtime=True)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

    owner = request_owner.get()
    if req.dry_run_id and any(run.owner_id == owner and run.dry_run_id == req.dry_run_id for run in active_dry_runs):
        raise HTTPException(status_code=409, detail="This dry run is already active.")
    control = DryRunControl(owner, target_store.guard_id, target_store.expires_at, dry_run_id=req.dry_run_id)
    cache_bust = req.cache_bust
    if cache_bust is None:
        cache_bust = bool(db_get_traffic_config(owner)["cache_bust"])
    started = perf_counter()
    active_dry_runs.add(control)
    try:
        results, context = await execute_dry_run(
            steps, base_url=base_url, is_sandbox=is_sandbox, control=control, cache_bust=cache_bust,
        )
    finally:
        active_dry_runs.discard(control)
        control.done.set()

    total_ms = round((perf_counter() - started) * 1000.0, 1)
    all_passed = control.reason is None and len(results) == len(steps) and all(r.get("passed") for r in results)

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

    outcome = {
        "status": "cancelled" if control.reason else "completed",
        "results": results,
        "all_passed": all_passed,
        "total_steps": len(steps),
        "total_duration_ms": total_ms,
        "extracted_context": context,
        "steps": formatted_steps,
    }
    if control.reason:
        outcome["reason"] = control.reason
        outcome["message"] = {
            "timeout": "Dry run reached its overall deadline.",
            "guard_expired": "Dry run cancelled because the Guard expired.",
            "guard_revoked": "Dry run cancelled because the Guard was revoked.",
            "stopped": "Dry run stopped by the operator.",
        }[control.reason]
    return outcome

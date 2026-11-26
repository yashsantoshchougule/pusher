"""
Load Testing Engine Router:
- GET /api/sandbox/target: Built-in 4 KB-16 KB streaming sandbox target with realistic delay
- POST /api/load/start: Validates RAM, VUs, SSRF, 48h guard token, and starts async engine
- POST /api/load/stop: Halts active load test workers immediately
- GET /api/load/status: Live 1-second rolling telemetry stream and run history
"""

import asyncio
import os
import time
import psutil
from fastapi import APIRouter, Depends, HTTPException, Header, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from backend.api.auth_deps import require_operator, resolve_operator
from backend.core.config import MAX_RAM_BUDGET_MB, max_safe_ram_budget_mb, settings
from backend.core.dry_run_control import active_dry_runs
from backend.core.request_owner import request_owner
from pydantic import BaseModel, Field

from backend.core.load_engine import (
    load_engine,
    calculate_max_allowed_vus,
    get_os_fd_cap,
    DEFAULT_MAX_ERROR_PCT,
    DEFAULT_RAM_CEILING_MB,
    MAX_REQUESTED_VUS,
    CHUNK_SIZE_BYTES,
    register_ws_watcher,
    unregister_ws_watcher,
)
from backend.core.run_manager import run_manager
from backend.core.target_policy import origin
from backend.core.target_service import (
    active_target,
    verified_destination,
    DestinationError,
    hash_device_id,
    burn_guard_id,
    is_guard_burned,
)
from backend.core.database import db_get_traffic_config, db_save_traffic_config
from backend.core.db_async import run_db_read, run_db_write
from backend.core.journey_service import journey_store, validate_journey_steps

router = APIRouter(prefix="/api", tags=["Load Engine"])


class TrafficConfigRequest(BaseModel):
    mode: str = Field("step_ramp", description="Traffic generation shape")
    ram_limit_mb: int = Field(500, ge=51, le=MAX_RAM_BUDGET_MB, description="RAM ceiling in MB")
    virtual_users: int = Field(100, ge=1, le=MAX_REQUESTED_VUS, description="Virtual Users target")
    duration_sec: int = Field(30, ge=1, le=86400, description="Test duration in seconds")
    max_error_pct: float = Field(DEFAULT_MAX_ERROR_PCT, ge=1.0, le=100.0, description="Max error threshold %")
    p95_ceiling_ms: float = Field(1500.0, ge=10.0, le=60000.0, description="p95 latency ceiling in ms")
    request_timeout_sec: float = Field(5.0, ge=2.0, le=10.0, description="Per-request timeout in seconds")
    cache_bust: bool = Field(True, description="Append unique query nonce")


@router.get("/traffic/config", dependencies=[Depends(require_operator)])
async def get_traffic_config_endpoint():
    """Retrieve persisted traffic and guardrail configuration from SQLite."""
    return await run_db_read(db_get_traffic_config, request_owner.get())


@router.post("/traffic/config", dependencies=[Depends(require_operator)])
async def save_traffic_config_endpoint(cfg: TrafficConfigRequest):
    """Save traffic and guardrail configuration to SQLite."""
    saved = await run_db_write(
        db_save_traffic_config,
        {
            "mode": cfg.mode,
            "ram_limit_mb": cfg.ram_limit_mb,
            "virtual_users": cfg.virtual_users,
            "duration_sec": cfg.duration_sec,
            "max_error_pct": cfg.max_error_pct,
            "p95_ceiling_ms": cfg.p95_ceiling_ms,
            "request_timeout_sec": cfg.request_timeout_sec,
            "cache_bust": 1 if cfg.cache_bust else 0,
        },
        request_owner.get(),
    )
    return saved


class LoadStartRequest(BaseModel):
    target_url: str = Field(..., description="Target HTTP/HTTPS URL")
    traffic_mode: str = Field("step_ramp", description="step_ramp | sudden_rush | steady_crowd")
    target_vus: int = Field(50, ge=1, le=MAX_REQUESTED_VUS, description="Virtual Users concurrency target")
    duration_sec: int = Field(15, ge=1, le=86400, description="Test duration in seconds")
    cache_bust: bool = Field(True, description="Append unique query nonce to defeat CDN cache")
    ram_limit_mb: int = Field(DEFAULT_RAM_CEILING_MB, ge=51, le=MAX_RAM_BUDGET_MB, description="RAM ceiling in MB")
    max_error_pct: float = Field(DEFAULT_MAX_ERROR_PCT, ge=1.0, le=100.0, description="Circuit breaker error threshold %")
    p95_ceiling_ms: float = Field(1500.0, ge=10.0, le=60000.0, description="Circuit breaker p95 latency ceiling in ms")
    request_timeout_sec: float = Field(5.0, ge=2.0, le=10.0)
    is_sandbox: bool = Field(False, description="Sandbox testing flag")
    use_journey: bool = Field(False, description="Run sequential multi-step API journey")
    journey_steps: list[dict] | None = Field(None, description="Optional steps override")
    device_id: str | None = Field(None, description="Hardware bound device identifier")
    project_name: str = Field("", max_length=80, description="Optional operator-chosen project display name")


class LoadStopRequest(BaseModel):
    run_id: str = Field(min_length=1)


@router.get("/sandbox/target")
async def sandbox_target_endpoint():
    """
    Built-in high-performance sandbox endpoint.
    Streams 8 KB (2 x 4 KB chunks) with realistic latency simulation.
    """
    async def chunk_streamer():
        chunk = b"X" * CHUNK_SIZE_BYTES
        for _ in range(2):
            await asyncio.sleep(0.005)  # 5ms artificial network latency
            yield chunk

    return StreamingResponse(
        chunk_streamer(),
        media_type="application/octet-stream",
        headers={
            "X-Pusher-Sandbox": "true",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.post("/load/start", dependencies=[Depends(require_operator)])
async def start_load_test(
    req: LoadStartRequest,
    x_device_id: str | None = Header(None, alias="X-Pusher-Device-ID"),
):
    owner = request_owner.get()
    if run_manager.active_engine_for_owner(owner, primary_engine=load_engine) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A load test is already running for your account. Stop the current run before starting a new one.",
        )

    # 1. Enforce the effective RAM limit for this host.
    try:
        host_total_ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        host_total_ram_mb = 1024
    max_hardware_safe_ram = max_safe_ram_budget_mb(host_total_ram_mb)
    if req.ram_limit_mb > max_hardware_safe_ram:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"RAM limit ({req.ram_limit_mb} MB) exceeds maximum safe host capacity ({max_hardware_safe_ram} MB).",
        )

    # 2. Maximum VUs Invariant Check: bounded by both RAM ceiling and OS FD worker cap.
    max_allowed_vus = calculate_max_allowed_vus(req.ram_limit_mb)
    max_worker_vus = max(1, min(MAX_REQUESTED_VUS, get_os_fd_cap()))
    effective_max_vus = min(max_allowed_vus, max_worker_vus)
    if req.target_vus > effective_max_vus:
        if req.target_vus > max_allowed_vus:
            detail = (
                f"Target VUs ({req.target_vus}) exceeds maximum allowed ({max_allowed_vus} VUs) "
                f"under {req.ram_limit_mb} MB RAM ceiling."
            )
        else:
            detail = (
                f"Target VUs ({req.target_vus}) exceeds host OS file-descriptor worker limit "
                f"({max_worker_vus} VUs)."
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )

    reserved_other_vus = run_manager.total_reserved_vus(exclude_owner=owner, primary_engine=load_engine)
    if reserved_other_vus + req.target_vus > max_worker_vus:
        available_vus = max(0, max_worker_vus - reserved_other_vus)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Concurrent runs currently reserve {reserved_other_vus}/{max_worker_vus} host workers "
                f"({available_vus} VUs available)."
            ),
        )

    # Authorize the destination before inspecting or mutating the active Guard.
    is_sandbox_target = req.is_sandbox
    try:
        destination = verified_destination(req.target_url, is_sandbox_target)
    except DestinationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    target_store = active_target()
    effective_device_id = req.device_id or x_device_id

    if not is_sandbox_target:
        # Check SQLite Tombstone
        if target_store.guard_id:
            burned_record = is_guard_burned(target_store.guard_id)
            if burned_record:
                reason = burned_record.get("burn_reason", "REVOKED")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Guard ID {target_store.guard_id} is permanently burned ({reason}) and can never be used again.",
                )

            # Trigger 1: Cross-Device Load Attempt Violation
            incoming_hash = hash_device_id(effective_device_id)
            if effective_device_id and incoming_hash != target_store.creator_device_hash:
                burn_guard_id(
                    target_store.guard_id,
                    "DEVICE_MISMATCH_VIOLATION",
                    target_store.creator_device_hash,
                    incoming_hash,
                )
                target_store.expires_at = int(time.time())
                target_store.is_verified = False
                target_store.active_guard_active = False
                target_store.last_burn_reason = "DEVICE_MISMATCH_VIOLATION"
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"DEVICE SECURITY VIOLATION: Guard ID {target_store.guard_id} is locked to its creator device. Cross-device access detected — Guard ID has been permanently killed, the 48h timer stopped, and this ID can never be used again.",
                )

    steps = req.journey_steps
    if req.use_journey:
        destination = destination.copy_with(query=None)
        steps = journey_store.steps if steps is None else steps
        valid, message = validate_journey_steps(steps, str(destination), is_sandbox_target, require_runtime=True)
        if not valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    elif target_store.requires_target_query and not destination.query:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Enter the target query again or verify the URL without it.")

    dest_scheme, dest_host, dest_port = origin(destination)
    same_process_loopback = (
        is_sandbox_target
        and dest_scheme == "http"
        and dest_host in {"127.0.0.1", "localhost", "::1"}
        and dest_port == settings.port
        and destination.path.startswith("/api/sandbox/")
    )
    advisory = (
        "Target is the in-process loopback sandbox on the same event loop; high VU counts share CPU and loop scheduling with the target."
        if same_process_loopback
        else ""
    )

    # 4. Launch Async Load Engine (allocated per concurrent operator/run)
    resolved_project_name = (
        (req.project_name or "").strip()[:80]
        or (getattr(target_store, "project_name", "") or "").strip()[:80]
    )
    if resolved_project_name:
        target_store.set_project_name(resolved_project_name)
    engine = run_manager.acquire_engine_for_start(owner, primary_engine=load_engine)
    run_id = await engine.start(
        target_url=str(destination),
        traffic_mode=req.traffic_mode,
        target_vus=req.target_vus,
        duration_sec=req.duration_sec,
        cache_bust=req.cache_bust,
        active_guard_id=target_store.guard_id,
        guard_expires_at=target_store.expires_at,
        ram_limit_mb=req.ram_limit_mb,
        max_error_pct=req.max_error_pct,
        p95_ceiling_ms=req.p95_ceiling_ms,
        use_journey=req.use_journey,
        journey_steps=steps,
        is_sandbox=is_sandbox_target,
        request_timeout_sec=req.request_timeout_sec,
        same_process_loopback=same_process_loopback,
        advisory=advisory,
        project_name=resolved_project_name,
    )
    run_manager.register_run(engine, owner)

    return {
        "status": "started",
        "run_id": run_id,
        "target_vus": req.target_vus,
        "traffic_mode": req.traffic_mode,
        "duration_sec": req.duration_sec,
        "same_process_loopback": same_process_loopback,
        "advisory": advisory,
        "snapshot": engine.get_status(owner),
    }


@router.post("/load/stop", dependencies=[Depends(require_operator)])
async def stop_load_test(req: LoadStopRequest | None = None):
    owner = request_owner.get()
    dry_runs = [run for run in active_dry_runs if run.owner_id == owner] if req is None else []

    if req is not None:
        target_engine = run_manager.find_by_run_id(req.run_id, primary_engine=load_engine)
        if target_engine is None:
            raise HTTPException(status_code=409, detail="That run is no longer current. Refresh run status and try again.")
        if target_engine.owner_id != owner:
            raise HTTPException(status_code=403, detail="This run belongs to another operator.")
        stop_engine = True
    else:
        target_engine = run_manager.active_engine_for_owner(owner, primary_engine=load_engine)
        if target_engine is None:
            if not dry_runs and load_engine.is_running and load_engine.owner_id != owner:
                raise HTTPException(status_code=403, detail="This run belongs to another operator.")
            target_engine = load_engine
            stop_engine = not dry_runs
        else:
            stop_engine = True

    for run in dry_runs:
        run.cancel("stopped")
    if stop_engine:
        await target_engine.stop(reason="MANUAL_ABORT")
    if dry_runs:
        await asyncio.gather(*(run.done.wait() for run in dry_runs))
    snapshot_engine = target_engine if stop_engine else run_manager.engine_for_owner(owner, primary_engine=load_engine)
    return {"status": "stopped", "message": ("Journey dry run stopped." if dry_runs
            else "Load engine worker pool aborted successfully."), "snapshot": snapshot_engine.get_status(owner)}


@router.get("/load/status", dependencies=[Depends(require_operator)])
async def get_load_status(run_id: str | None = None):
    owner = request_owner.get()
    target_engine = run_manager.engine_for_owner(owner, primary_engine=load_engine, run_id=run_id)
    return target_engine.get_status(owner)


@router.post("/load/simulate-spike", dependencies=[Depends(require_operator)])
async def simulate_spike_endpoint(run_id: str | None = None):
    """
    Live Backend WAF/5xx Fault Injector:
    Injects 429 WAF blocks and 503 service failures into the active engine,
    tripping the safety circuit breaker and halting workers immediately.
    """
    owner = request_owner.get()
    if run_id is not None:
        target_engine = run_manager.find_by_run_id(run_id, primary_engine=load_engine)
        if target_engine is None or not target_engine.is_running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active load test is running to inject fault spike.",
            )
        if target_engine.owner_id != owner:
            raise HTTPException(status_code=403, detail="This run belongs to another operator.")
    else:
        target_engine = run_manager.active_engine_for_owner(owner, primary_engine=load_engine)
        if target_engine is None:
            check_run_owner()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active load test is running to inject fault spike.",
            )
    return await target_engine.simulate_spike()


def check_run_owner():
    if load_engine.is_running and load_engine.owner_id != request_owner.get():
        raise HTTPException(status_code=403, detail="This run belongs to another operator.")


@router.websocket("/load/ws")
async def load_telemetry_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    expected_host = websocket.url.netloc
    if origin and origin not in settings.allowed_origins and origin not in (
        f"http://{expected_host}", f"https://{expected_host}"
    ):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    actor = None
    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        actor = await resolve_operator(websocket, token or None)
        expiry = actor.claims.get("exp")
        load_engine.connection_manager.register(websocket, actor.user_id)
        register_ws_watcher(actor.user_id, id(websocket), run_manager.active_engines(load_engine))
        engine = run_manager.engine_for_owner(actor.user_id, primary_engine=load_engine)
        snapshot = engine.get_status(actor.user_id)
        snapshot["event"] = "SNAPSHOT"
        await websocket.send_json(snapshot)
        while True:
            timeout = max(0, expiry - time.time()) if expiry is not None else None
            await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except (HTTPException, TimeoutError):
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        pass
    finally:
        load_engine.connection_manager.disconnect(websocket)
        if actor is not None:
            unregister_ws_watcher(actor.user_id, id(websocket), run_manager.active_engines(load_engine))

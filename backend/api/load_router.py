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
from fastapi import APIRouter, HTTPException, Header, status, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.load_engine import (
    load_engine,
    calculate_max_allowed_vus,
    DEFAULT_RAM_CEILING_MB,
    CHUNK_SIZE_BYTES,
)
from backend.core.target_service import (
    target_store,
    validate_target_url,
    hash_device_id,
    burn_guard_id,
    is_guard_burned,
)
from backend.core.database import db_get_traffic_config, db_save_traffic_config

router = APIRouter(prefix="/api", tags=["Load Engine"])


class TrafficConfigRequest(BaseModel):
    mode: str = Field("step_ramp", description="Traffic generation shape")
    ram_limit_mb: int = Field(500, ge=51, description="RAM ceiling in MB")
    virtual_users: int = Field(100, ge=1, le=100000, description="Virtual Users target")
    duration_sec: int = Field(30, ge=1, le=86400, description="Test duration in seconds")
    max_error_pct: float = Field(5.0, ge=1.0, le=100.0, description="Max error threshold %")
    p95_ceiling_ms: float = Field(1500.0, ge=10.0, le=60000.0, description="p95 latency ceiling in ms")
    cache_bust: bool = Field(True, description="Append unique query nonce")


@router.get("/traffic/config")
async def get_traffic_config_endpoint():
    """Retrieve persisted traffic and guardrail configuration from SQLite."""
    return db_get_traffic_config()


@router.post("/traffic/config")
async def save_traffic_config_endpoint(cfg: TrafficConfigRequest):
    """Save traffic and guardrail configuration to SQLite."""
    saved = db_save_traffic_config({
        "mode": cfg.mode,
        "ram_limit_mb": cfg.ram_limit_mb,
        "virtual_users": cfg.virtual_users,
        "duration_sec": cfg.duration_sec,
        "max_error_pct": cfg.max_error_pct,
        "p95_ceiling_ms": cfg.p95_ceiling_ms,
        "cache_bust": 1 if cfg.cache_bust else 0,
    })
    return saved


class LoadStartRequest(BaseModel):
    target_url: str = Field(..., description="Target HTTP/HTTPS URL")
    traffic_mode: str = Field("step_ramp", description="step_ramp | sudden_rush | steady_crowd")
    target_vus: int = Field(50, ge=1, le=100000, description="Virtual Users concurrency target")
    duration_sec: int = Field(15, ge=1, le=86400, description="Test duration in seconds")
    cache_bust: bool = Field(True, description="Append unique query nonce to defeat CDN cache")
    ram_limit_mb: int = Field(DEFAULT_RAM_CEILING_MB, ge=51, description="RAM ceiling in MB")
    max_error_pct: float = Field(15.0, ge=1.0, le=100.0, description="Circuit breaker error threshold %")
    p95_ceiling_ms: float = Field(1500.0, ge=10.0, le=60000.0, description="Circuit breaker p95 latency ceiling in ms")
    is_sandbox: bool = Field(False, description="Sandbox testing flag")
    use_journey: bool = Field(False, description="Run sequential multi-step API journey")
    journey_steps: list[dict] | None = Field(None, description="Optional steps override")
    device_id: str | None = Field(None, description="Hardware bound device identifier")


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


@router.post("/load/start")
async def start_load_test(
    req: LoadStartRequest,
    x_device_id: str | None = Header(None, alias="X-Pusher-Device-ID"),
):
    if load_engine.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A load test is already running. Stop the current run before starting a new one.",
        )

    # 1. Host Hardware RAM Safety Limit Validation (Max 75% host RAM)
    host_total_ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    max_hardware_safe_ram = int(host_total_ram_mb * 0.75)
    if req.ram_limit_mb > max_hardware_safe_ram:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"RAM limit ({req.ram_limit_mb} MB) exceeds maximum safe host capacity ({max_hardware_safe_ram} MB).",
        )

    # 2. Maximum VUs Invariant Check: max_allowed_vus = floor((ram_limit_mb - 50) / 0.20)
    max_allowed_vus = calculate_max_allowed_vus(req.ram_limit_mb)
    if req.target_vus > max_allowed_vus:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Target VUs ({req.target_vus}) exceeds maximum allowed ({max_allowed_vus} VUs) under {req.ram_limit_mb} MB RAM ceiling.",
        )

    # 3. Target Verification, Device Lock & SSRF Enforcement
    is_sandbox_target = (
        req.is_sandbox
        or "sandbox.pusher.local" in req.target_url.lower()
        or "/api/sandbox/target" in req.target_url.lower()
    )

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

        # Check 48h guard verification
        if not target_store.is_verified or target_store.get_remaining_seconds() <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Target URL is unverified or expired. Deploy pusher_guard.py and verify before starting load test.",
            )
        active_guard_id = target_store.guard_id or "PG-ACTIVE"

        # Validate SSRF (Demo target api.myproject.dev routes safely to local sandbox endpoint)
        if "api.myproject.dev" in req.target_url:
            req.target_url = "http://127.0.0.1:8000/api/sandbox/target"
        else:
            is_valid, msg, _ = validate_target_url(req.target_url, is_sandbox=False)
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    else:
        active_guard_id = "SANDBOX-DEV"
        if "sandbox.pusher.local" in req.target_url or not req.target_url.startswith("http"):
            req.target_url = "http://127.0.0.1:8000/api/sandbox/target"

    # 4. Launch Async Load Engine
    run_id = await load_engine.start(
        target_url=req.target_url,
        traffic_mode=req.traffic_mode,
        target_vus=req.target_vus,
        duration_sec=req.duration_sec,
        cache_bust=req.cache_bust,
        active_guard_id=active_guard_id,
        handshake_secret=target_store.bypass_secret,
        ram_limit_mb=req.ram_limit_mb,
        max_error_pct=req.max_error_pct,
        p95_ceiling_ms=req.p95_ceiling_ms,
        use_journey=req.use_journey,
        journey_steps=req.journey_steps,
    )

    return {
        "status": "started",
        "run_id": run_id,
        "target_vus": req.target_vus,
        "traffic_mode": req.traffic_mode,
        "duration_sec": req.duration_sec,
    }


@router.post("/load/stop")
async def stop_load_test():
    load_engine.stop(reason="MANUAL_ABORT")
    return {"status": "stopped", "message": "Load engine worker pool aborted successfully."}


@router.get("/load/status")
async def get_load_status():
    return load_engine.get_status()


@router.post("/load/simulate-spike")
async def simulate_spike_endpoint():
    """
    Live Backend WAF/5xx Fault Injector:
    Injects 429 WAF blocks and 503 service failures into the active engine,
    tripping the safety circuit breaker and halting workers immediately.
    """
    if not load_engine.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active load test is running to inject fault spike.",
        )
    return load_engine.simulate_spike()


@router.websocket("/load/ws")
async def load_telemetry_websocket(websocket: WebSocket):
    """
    Real-Time WebSocket Telemetry Stream:
    Broadcasts live 1-second rolling telemetry and instant circuit-breaker trip events.
    """
    await load_engine.connection_manager.connect(websocket)
    # Send immediate snapshot frame upon handshake
    snapshot = load_engine.get_status()
    snapshot["event"] = "SNAPSHOT"
    await websocket.send_json(snapshot)
    try:
        while True:
            # Keep socket alive and receive client pings/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        load_engine.connection_manager.disconnect(websocket)
    except Exception:
        load_engine.connection_manager.disconnect(websocket)

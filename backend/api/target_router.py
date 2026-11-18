"""
Target Verification & Abuse Prevention API Router
Handles SSRF validation, sealed 48h guard generation, challenge-response handshake, and kill actions.
"""

from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field
from backend.core.target_service import (
    validate_target_url,
    generate_pusher_guard_file,
    verify_target_handshake,
    probe_waf_bypass,
    target_store,
    is_guard_burned,
    GuardRateLimitError,
    GuardActiveConflictError,
)

router = APIRouter(prefix="/api/target", tags=["Target Verification"])

class ValidateSsrfRequest(BaseModel):
    target_url: str = Field(..., description="The target website or API endpoint")
    is_sandbox: bool = Field(default=False, description="Enable local sandbox demo mode")

class GenerateGuardRequest(BaseModel):
    target_url: str = Field(..., description="The target domain to generate pusher_guard.py for")
    is_sandbox: bool = Field(default=False, description="Enable local sandbox demo mode")
    device_id: str | None = Field(default=None, description="Hardware bound creator device identifier")

class VerifyTargetRequest(BaseModel):
    target_url: str = Field(..., description="The target domain to verify")
    guard_id: str | None = Field(default=None, description="The unique PG-XXXX-48H token")
    is_sandbox: bool = Field(default=False, description="Demo sandbox verification")
    device_id: str | None = Field(default=None, description="Hardware bound device identifier")

class KillTargetRequest(BaseModel):
    device_id: str | None = Field(default=None, description="Device identifier executing kill")

class WafProbeRequest(BaseModel):
    target_url: str = Field(..., description="Target domain to probe for WAF bypass")
    is_sandbox: bool = Field(default=False, description="Simulate sandbox response")


@router.post("/validate-url")
async def validate_url_endpoint(payload: ValidateSsrfRequest):
    """
    Real-time 3-step validation: syntax & SSRF guard, async DNS lookup, and live HTTP reachability probe.
    Returns structured validation object with status and typo suggestions.
    """
    result = await validate_target_url(payload.target_url, payload.is_sandbox)
    return dict(result)


@router.post("/validate-ssrf")
async def validate_ssrf_endpoint(payload: ValidateSsrfRequest):
    """
    Validates the target URL against SSRF rules, rejecting loopbacks, private networks, and link-local cloud metadata.
    """
    result = await validate_target_url(payload.target_url, payload.is_sandbox)
    if not result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "valid": False,
                "detail": result["message"],
                "target_url": payload.target_url,
                "status": result["status"],
                "suggestions": result.get("suggestions", []),
            },
        )
    return {
        "valid": True,
        "detail": result["message"],
        "resolved_ip": result.get("resolved_ip"),
        "target_url": payload.target_url,
        "status": result["status"],
        "suggestions": result.get("suggestions", []),
    }


@router.post("/generate-guard")
async def generate_guard_endpoint(
    payload: GenerateGuardRequest,
    x_device_id: str | None = Header(None, alias="X-Pusher-Device-ID"),
):
    """
    Generates a sealed, 48-hour tamper-protected pusher_guard.py file with SHA-256 integrity checksum.
    Binds the Guard ID exclusively to the creator device hardware fingerprint.
    Enforces URL reachability (HTTP 422 if dead/unreachable/nonexistent),
    a strict 3-generation per rolling 24-hour limit, and Kill-First invariant.
    """
    if not payload.target_url or not payload.target_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL cannot be empty.")

    # 1. Pre-validation: URL syntax, DNS existence & live reachability check
    validation = await validate_target_url(payload.target_url.strip(), is_sandbox=payload.is_sandbox)
    if not validation["valid"] or not validation.get("reachable", False):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation["message"],
        )

    effective_device_id = payload.device_id or x_device_id or "DEV-LOCAL-CREATOR"

    try:
        guard_data = generate_pusher_guard_file(
            payload.target_url.strip(),
            is_sandbox=payload.is_sandbox,
            device_id=effective_device_id,
        )
        return guard_data
    except GuardActiveConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except GuardRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )


@router.post("/verify")
async def verify_target_endpoint(
    payload: VerifyTargetRequest,
    x_device_id: str | None = Header(None, alias="X-Pusher-Device-ID"),
):
    """
    Executes the live cryptographic challenge-response handshake on {target_url}/__pusher_verify?nonce=...
    Enforces device lock and permanently burns tokens on cross-device violations or 48h expiry.
    """
    effective_device_id = payload.device_id or x_device_id

    verified, message, remaining_seconds = await verify_target_handshake(
        target_url=payload.target_url,
        guard_id=payload.guard_id,
        is_sandbox=payload.is_sandbox,
        device_id=effective_device_id,
    )
    if not verified:
        is_forbidden = (
            "403" in message
            or "violation" in message.lower()
            or "security" in message.lower()
            or "revoked" in message.lower()
            or "burned" in message.lower()
            or "expired" in message.lower()
        )
        status_code = status.HTTP_403_FORBIDDEN if is_forbidden else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail={"is_verified": False, "detail": message, "guard_id": payload.guard_id},
        )
    return {
        "is_verified": True,
        "detail": message,
        "guard_id": payload.guard_id,
        "target_url": payload.target_url,
        "remaining_seconds": remaining_seconds,
        "creator_device_id": target_store.creator_device_id,
    }


@router.post("/kill")
async def kill_target_endpoint(
    payload: KillTargetRequest | None = None,
    x_device_id: str | None = Header(None, alias="X-Pusher-Device-ID"),
):
    """
    Immediately revokes the active Guard ID and locks load testing.
    Permanently burns the Guard ID into the SQLite tombstone registry.
    If called from an unauthorized foreign device, trips Trigger 1 (DEVICE_MISMATCH_VIOLATION).
    """
    effective_device_id = (payload.device_id if payload else None) or x_device_id
    success, msg = target_store.kill(device_id=effective_device_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "is_verified": False,
                "detail": msg,
                "last_burn_reason": target_store.last_burn_reason,
            },
        )

    return {
        "is_verified": False,
        "detail": msg,
        "remaining_seconds": 0,
        "revoked_guard_id": target_store.last_revoked_guard_id,
        "last_burn_reason": target_store.last_burn_reason,
        "revoked_count": len(target_store.revoked_guard_ids),
    }


@router.get("/status")
async def get_target_status():
    """
    Returns current active target verification status, ticking 48-hour remaining seconds,
    device binding metadata, and daily generation rate limiter quota telemetry.
    """
    remaining = target_store.get_remaining_seconds()
    burned_info = is_guard_burned(target_store.guard_id)
    return {
        "target_url": target_store.target_url,
        "is_sandbox": bool(target_store.is_sandbox),
        "guard_id": target_store.guard_id,
        "is_verified": target_store.is_verified and remaining > 0,
        "active_guard_active": target_store.active_guard_active,
        "remaining_seconds": remaining,
        "creator_device_id": target_store.creator_device_id,
        "creator_device_hash": target_store.creator_device_hash,
        "last_burn_reason": target_store.last_burn_reason or (burned_info.get("burn_reason") if burned_info else None),
        "is_burned": bool(burned_info),
        "daily_generations_used": target_store.get_daily_generations_used(),
        "daily_generations_max": target_store.MAX_DAILY_GUARD_GENERATIONS,
        "daily_generations_remaining": target_store.get_daily_generations_remaining(),
        "revoked_count": len(target_store.revoked_guard_ids),
        "last_revoked_guard_id": target_store.last_revoked_guard_id,
    }


@router.post("/waf-probe")
async def waf_probe_endpoint(payload: WafProbeRequest):
    """
    Sends a diagnostic live probe request to target origin with X-Pusher-Guard-Token
    and User-Agent: Pusher-LoadEngine/1.0, analyzing edge responses (Cloudflare/AWS/Vercel/NGINX).
    Enforces SSRF boundary checks unless in sandbox mode.
    """
    if not payload.target_url or not payload.target_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL cannot be empty.")

    # 1. SSRF Boundary Enforcement
    valid, message, _ = await validate_target_url(payload.target_url, payload.is_sandbox)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"valid": False, "detail": message, "target_url": payload.target_url},
        )

    # 2. Probe execution
    diagnosis = await probe_waf_bypass(payload.target_url.strip(), payload.is_sandbox)
    return diagnosis

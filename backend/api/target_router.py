"""
Target Verification & Abuse Prevention API Router
Handles SSRF validation, sealed 48h guard generation, challenge-response handshake, and kill actions.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from backend.core.target_service import (
    validate_target_url,
    generate_pusher_guard_file,
    verify_target_handshake,
    target_store,
    GuardRateLimitError,
)

router = APIRouter(prefix="/api/target", tags=["Target Verification"])

class ValidateSsrfRequest(BaseModel):
    target_url: str = Field(..., description="The target website or API endpoint")
    is_sandbox: bool = Field(default=False, description="Enable local sandbox demo mode")

class GenerateGuardRequest(BaseModel):
    target_url: str = Field(..., description="The target domain to generate pusher_guard.py for")
    is_sandbox: bool = Field(default=False, description="Enable local sandbox demo mode")

class VerifyTargetRequest(BaseModel):
    target_url: str = Field(..., description="The target domain to verify")
    guard_id: str = Field(..., description="The unique PG-XXXX-48H token")
    is_sandbox: bool = Field(default=False, description="Demo sandbox verification")


@router.post("/validate-ssrf")
async def validate_ssrf_endpoint(payload: ValidateSsrfRequest):
    """
    Validates the target URL against SSRF rules, rejecting loopbacks, private networks, and link-local cloud metadata.
    """
    valid, message, resolved_ip = validate_target_url(payload.target_url, payload.is_sandbox)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"valid": False, "detail": message, "target_url": payload.target_url},
        )
    return {
        "valid": True,
        "detail": message,
        "resolved_ip": resolved_ip,
        "target_url": payload.target_url,
    }


@router.post("/generate-guard")
async def generate_guard_endpoint(payload: GenerateGuardRequest):
    """
    Generates a sealed, 48-hour tamper-protected pusher_guard.py file with SHA-256 integrity checksum.
    Enforces a strict 3-generation per rolling 24-hour limit and supersedes previous Guard tokens.
    """
    if not payload.target_url or not payload.target_url.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL cannot be empty.")
    
    import urllib.parse
    parsed = urllib.parse.urlparse(payload.target_url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    try:
        guard_data = generate_pusher_guard_file(payload.target_url.strip(), is_sandbox=payload.is_sandbox)
        return guard_data
    except GuardRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )


@router.post("/verify")
async def verify_target_endpoint(payload: VerifyTargetRequest):
    """
    Executes the live cryptographic challenge-response handshake on {target_url}/__pusher_verify?nonce=...
    Rejects revoked or burned Guard IDs with HTTP 403 Forbidden.
    """
    verified, message, remaining_seconds = await verify_target_handshake(
        target_url=payload.target_url,
        guard_id=payload.guard_id,
        is_sandbox=payload.is_sandbox,
    )
    if not verified:
        is_forbidden = (
            "403" in message
            or "revoked" in message.lower()
            or "burned" in message.lower()
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
    }


@router.post("/kill")
async def kill_target_endpoint():
    """
    Immediately revokes the active Guard ID and locks load testing.
    Permanently burns the Guard ID into the revocation registry.
    """
    target_store.kill()
    return {
        "is_verified": False,
        "detail": "Active Guard ID revoked and permanently burned. Load testing locked until re-verified.",
        "remaining_seconds": 0,
        "revoked_guard_id": target_store.last_revoked_guard_id,
        "revoked_count": len(target_store.revoked_guard_ids),
    }


@router.get("/status")
async def get_target_status():
    """
    Returns current active target verification status, ticking 48-hour remaining seconds,
    and daily generation rate limiter quota telemetry.
    """
    remaining = target_store.get_remaining_seconds()
    return {
        "target_url": target_store.target_url,
        "guard_id": target_store.guard_id,
        "is_verified": target_store.is_verified and remaining > 0,
        "remaining_seconds": remaining,
        "daily_generations_used": target_store.get_daily_generations_used(),
        "daily_generations_max": target_store.MAX_DAILY_GUARD_GENERATIONS,
        "daily_generations_remaining": target_store.get_daily_generations_remaining(),
        "revoked_count": len(target_store.revoked_guard_ids),
        "last_revoked_guard_id": target_store.last_revoked_guard_id,
    }

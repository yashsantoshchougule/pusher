"""
FastAPI Authentication Router
Endpoints for user profile, token verification, and health monitoring.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any
from backend.core.jwks_verifier import AuthenticatedUser, jwks_verifier
from backend.core.supabase_admin import supabase_admin
from backend.api.auth_deps import get_current_user, get_verified_user, get_admin_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

class TokenVerifyRequest(BaseModel):
    token: str

class UserProfileResponse(BaseModel):
    user_id: str
    email: str | None
    role: str
    email_confirmed: bool
    first_name: str | None
    last_name: str | None

@router.get("/health")
async def auth_health() -> Dict[str, Any]:
    """Pings Supabase GoTrue Auth service to confirm health."""
    health_status = await supabase_admin.check_health()
    return {
        "status": "healthy" if health_status.get("status") == "healthy" else "degraded",
        "supabase_connection": health_status,
        "jwks_cache_loaded": len(jwks_verifier._keys_by_kid) > 0,
    }

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(user: AuthenticatedUser = Depends(get_current_user)):
    """Returns profile information for the authenticated bearer token."""
    first_name = user.metadata.get("first_name")
    last_name = user.metadata.get("last_name")

    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        email_confirmed=user.email_confirmed,
        first_name=first_name,
        last_name=last_name,
    )

@router.post("/verify-token")
async def verify_token_explicit(req: TokenVerifyRequest):
    """Allows programmatic token verification."""
    user = await jwks_verifier.verify_token(req.token)
    return {
        "valid": True,
        "user_id": user.user_id,
        "email": user.email,
        "email_confirmed": user.email_confirmed,
        "role": user.role,
    }

@router.get("/verified-only")
async def verified_only_check(user: AuthenticatedUser = Depends(get_verified_user)):
    """Protected test endpoint that requires confirmed email address."""
    return {
        "status": "authorized",
        "message": f"Welcome verified user {user.email}!",
        "email_confirmed": user.email_confirmed,
    }

@router.get("/admin-only")
async def admin_only_check(user: AuthenticatedUser = Depends(get_admin_user)):
    """Protected test endpoint that requires administrative privileges."""
    return {
        "status": "authorized",
        "message": "Administrative access granted.",
        "user_id": user.user_id,
    }


@router.post("/logout")
async def logout():
    """Invalidates user session."""
    return {"status": "ok", "message": "Session invalidated successfully."}

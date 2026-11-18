"""
Profile API Router
Endpoints for fetching and updating persistent user profiles stored in backend/pusher_runs.db.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, Field
from backend.core.profile_service import get_or_create_profile, update_user_profile
from backend.core.security import extract_bearer_token
from backend.core.jwks_verifier import jwks_verifier

router = APIRouter(prefix="/api/profile", tags=["User Profile"])


class ProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    role_title: Optional[str] = None
    organization: Optional[str] = None
    github_username: Optional[str] = None
    avatar_url: Optional[str] = None
    bio_notes: Optional[str] = None
    default_ram_ceiling_mb: Optional[int] = Field(default=None, ge=50, le=2048)


async def resolve_user_key(request: Request, explicit_key: Optional[str] = None) -> tuple[str, str]:
    """
    Extracts the authenticated user ID and email if a valid Bearer token is provided.
    Falls back gracefully to explicit_key or X-User-Key header, or default_user.
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip(), "dev@pusher.internal"

    header_key = request.headers.get("X-User-Key")
    if header_key and header_key.strip():
        return header_key.strip(), request.headers.get("X-User-Email", "dev@pusher.internal")

    try:
        token = extract_bearer_token(request)
        if token:
            user = await jwks_verifier.verify_token(token)
            if user and user.user_id:
                return f"usr_{user.user_id}", user.email or "dev@pusher.internal"
    except Exception:
        pass

    return "default_user", "dev@pusher.internal"


@router.get("")
@router.get("/")
async def get_profile(
    request: Request,
    user_key: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """Returns the current user profile from SQLite."""
    resolved_key, email = await resolve_user_key(request, user_key)
    return get_or_create_profile(user_key=resolved_key, email=email)


@router.put("")
@router.put("/")
async def update_profile(
    request: Request,
    payload: ProfileUpdateRequest,
    user_key: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """Updates user profile attributes in SQLite."""
    resolved_key, email = await resolve_user_key(request, user_key)
    raw_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    update_data = {k: v for k, v in raw_dict.items() if v is not None}
    return update_user_profile(user_key=resolved_key, data=update_data)

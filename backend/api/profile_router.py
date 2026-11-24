"""
Profile API Router
Endpoints for fetching and updating persistent user profiles stored in backend/pusher_runs.db.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from backend.core.profile_service import get_or_create_profile, update_user_profile
from backend.api.auth_deps import require_operator
from backend.core.jwks_verifier import AuthenticatedUser

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


@router.get("")
@router.get("/")
async def get_profile(actor: AuthenticatedUser = Depends(require_operator)) -> Dict[str, Any]:
    return get_or_create_profile(user_key=actor.user_id, email=actor.email or "")


@router.put("")
@router.put("/")
async def update_profile(
    payload: ProfileUpdateRequest, actor: AuthenticatedUser = Depends(require_operator),
) -> Dict[str, Any]:
    updates = payload.model_dump(exclude_none=True, exclude={"email"})
    updates["email"] = actor.email or ""
    return update_user_profile(user_key=actor.user_id, data=updates)

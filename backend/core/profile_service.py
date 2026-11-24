"""
Profile Service:
Business logic and persistence operations for user profiles stored in backend/pusher_runs.db.
"""

from typing import Any, Dict, Optional
from backend.core.database import db_get_profile, db_save_profile


def sanitize_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cleans and validates incoming profile data fields."""
    ram_mb = data.get("default_ram_ceiling_mb", 500)
    try:
        ram_mb = int(ram_mb)
        ram_mb = max(50, min(ram_mb, 2048))
    except (ValueError, TypeError):
        ram_mb = 500

    return {
        "email": str(data.get("email", "")).strip()[:150],
        "full_name": str(data.get("full_name", "")).strip()[:100],
        "username": str(data.get("username", "")).strip()[:50],
        "role_title": str(data.get("role_title", "")).strip()[:80],
        "organization": str(data.get("organization", "")).strip()[:100],
        "github_username": str(data.get("github_username", "")).strip()[:60],
        "avatar_url": str(data.get("avatar_url", "")).strip()[:300],
        "bio_notes": str(data.get("bio_notes", "")).strip()[:1000],
        "default_ram_ceiling_mb": ram_mb,
    }


def get_or_create_profile(
    user_key: str = "default_user",
    email: str = "dev@pusher.internal"
) -> Dict[str, Any]:
    """Retrieves an existing profile or creates a default profile if none exists."""
    profile = db_get_profile(user_key)
    if profile:
        return profile

    default_data = {
        "email": email,
        "full_name": "Lead Test Architect",
        "username": "pusher_admin",
        "role_title": "Performance Engineer",
        "organization": "Pusher Ops",
        "github_username": "pusher-eng",
        "avatar_url": "",
        "bio_notes": "Hardware load and knee-curve benchmarking lead.",
        "default_ram_ceiling_mb": 500,
    }
    return db_save_profile(user_key, default_data)


def update_user_profile(user_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitizes and persists profile updates to SQLite."""
    existing = get_or_create_profile(user_key)
    sanitized = {
        field: value for field, value in sanitize_profile_data(data).items() if field in data
    }

    # Preserve email if not explicitly provided or empty
    if "email" in sanitized and not sanitized["email"] and existing.get("email"):
        sanitized["email"] = existing["email"]

    merged = {**existing, **sanitized}
    return db_save_profile(user_key, merged)

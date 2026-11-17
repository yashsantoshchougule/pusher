"""
Server-Side Supabase Admin Client
Uses SUPABASE_SECRET_KEY strictly on the backend for administrative operations,
user validation, session verification, and privilege checks.
"""

import httpx
from typing import Optional, Dict, Any
from backend.core.config import settings

class SupabaseAdminClient:
    def __init__(self):
        self.base_url = settings.supabase_url.rstrip("/")
        self.secret_key = settings.supabase_secret_key
        self.headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves live user profile from Supabase Admin API.
        Used to verify account is still active, not banned, or deleted.
        """
        url = f"{self.base_url}/auth/v1/admin/users/{user_id}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=self.headers)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def is_user_active(self, user_id: str) -> bool:
        """
        Checks whether the user account is currently active and not banned.
        """
        user_data = await self.get_user(user_id)
        if not user_data:
            return False

        # Check banned status
        banned_until = user_data.get("banned_until")
        if banned_until:
            # If banned_until is in the future, user is banned
            return False

        return True

    async def check_health(self) -> Dict[str, Any]:
        """
        Pings Supabase GoTrue Auth service to verify backend connection.
        """
        url = f"{self.base_url}/auth/v1/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers={"apikey": settings.supabase_publishable_key})
                if resp.status_code == 200:
                    return {"status": "healthy", "service": resp.json()}
                return {"status": "degraded", "code": resp.status_code}
        except Exception as err:
            return {"status": "unreachable", "error": str(err)}

# Global admin client instance
supabase_admin = SupabaseAdminClient()

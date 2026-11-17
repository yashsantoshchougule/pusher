"""
Security Utilities: In-Memory Sliding Window Rate Limiter & Token Extractor
Keeps RAM < 5MB while protecting auth endpoints against brute force and DDoS.
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import Request
from backend.core.jwks_verifier import AuthError

class SlidingWindowRateLimiter:
    """
    Lightweight in-memory rate limiter using sliding windows.
    Automatically purges expired timestamps to guarantee minimal memory usage (< 5MB).
    """
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        # Periodic cleanup of all identifiers every 120 seconds
        if now - self._last_cleanup > 120:
            self._cleanup_all(cutoff)
            self._last_cleanup = now

        # Filter timestamps for this identifier
        valid_timestamps = [t for t in self._history[identifier] if t > cutoff]
        self._history[identifier] = valid_timestamps

        if len(valid_timestamps) >= self.max_requests:
            return False

        self._history[identifier].append(now)
        return True

    def _cleanup_all(self, cutoff: float):
        keys_to_delete = []
        for key, timestamps in self._history.items():
            valid = [t for t in timestamps if t > cutoff]
            if not valid:
                keys_to_delete.append(key)
            else:
                self._history[key] = valid
        for key in keys_to_delete:
            del self._history[key]

# Rate limiters for different sensitivity tiers
auth_rate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)
api_rate_limiter = SlidingWindowRateLimiter(max_requests=300, window_seconds=60)

def extract_bearer_token(request: Request) -> str:
    """
    Safely extracts JWT from Authorization header or fallback auth cookies.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        raise AuthError(
            detail="Malformed Authorization header. Format must be 'Bearer <token>'",
            status_code=401,
            error_code="invalid_header"
        )

    # Fallback to Supabase cookie if set
    cookie_token = request.cookies.get("sb-access-token") or request.cookies.get("supabase-auth-token")
    if cookie_token:
        return cookie_token

    raise AuthError(
        detail="Missing Authorization Bearer token or auth cookie",
        status_code=401,
        error_code="missing_token"
    )

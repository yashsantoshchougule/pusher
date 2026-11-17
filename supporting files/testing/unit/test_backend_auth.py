"""
Automated Unit Tests for Backend Supabase Authentication & Loophole Hardening
Run with: py -m pytest "supporting files/testing/unit/test_backend_auth.py" -v
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jose import jwt
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.config import settings
from backend.core.jwks_verifier import jwks_verifier, AuthError, AuthenticatedUser
from backend.core.security import SlidingWindowRateLimiter

client = TestClient(app)

# Helper to generate test tokens signed with HMAC secret
def create_test_token(
    user_id: str = "test-user-123",
    email: str = "test@pusher.dev",
    role: str = "authenticated",
    email_confirmed: bool = True,
    exp_delta: int = 3600,
    alg: str = "HS256",
    custom_secret: str = None,
    issuer: str = None,
    audience: str = "authenticated",
) -> str:
    now = int(time.time())
    claims = {
        "sub": user_id,
        "email": email,
        "role": role,
        "aud": audience,
        "iss": issuer or f"{settings.supabase_url.rstrip('/')}/auth/v1",
        "iat": now,
        "exp": now + exp_delta,
        "user_metadata": {
            "first_name": "Test",
            "last_name": "User",
        },
    }
    if email_confirmed:
        claims["email_confirmed_at"] = now - 100

    secret = custom_secret or settings.supabase_secret_key
    return jwt.encode(claims, secret, algorithm=alg)


class TestJWKSTokenVerifier:
    """Tests for cryptographic verification & loophole defenses."""

    @pytest.mark.asyncio
    async def test_valid_token_verification(self):
        token = create_test_token(user_id="user_abc_456", email="alex@example.com")
        user = await jwks_verifier.verify_token(token)

        assert user.user_id == "user_abc_456"
        assert user.email == "alex@example.com"
        assert user.email_confirmed is True
        assert user.metadata.get("first_name") == "Test"

    @pytest.mark.asyncio
    async def test_reject_none_algorithm_forgery(self):
        """Loophole Defense: Reject 'none' algorithm token bypass."""
        import base64
        import json
        now = int(time.time())
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip('=')
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "hacker_user",
            "email": "hacker@evil.com",
            "aud": "authenticated",
            "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
            "exp": now + 3600,
        }).encode()).decode().rstrip('=')
        # Insecure token without signature (alg=none)
        token = f"{header}.{payload}."

        with pytest.raises(AuthError) as exc_info:
            await jwks_verifier.verify_token(token)
        assert exc_info.value.status_code == 401
        assert "algorithm" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reject_tampered_signature(self):
        """Loophole Defense: Reject tokens signed with a different key."""
        fake_token = create_test_token(custom_secret="wrong_secret_key_12345678901234567890")
        with pytest.raises(AuthError) as exc_info:
            await jwks_verifier.verify_token(fake_token)
        assert exc_info.value.status_code == 401
        assert "signature" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reject_expired_token(self):
        """Loophole Defense: Reject expired token cleanly."""
        expired_token = create_test_token(exp_delta=-60)
        with pytest.raises(AuthError) as exc_info:
            await jwks_verifier.verify_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reject_invalid_audience(self):
        """Loophole Defense: Reject tokens with wrong audience."""
        token = create_test_token(audience="malicious_service")
        with pytest.raises(AuthError) as exc_info:
            await jwks_verifier.verify_token(token)
        assert exc_info.value.status_code == 401
        assert "audience" in exc_info.value.detail.lower()


class TestRateLimiter:
    """Tests for sliding window rate limiter memory efficiency & blocking."""

    def test_sliding_window_rate_limiting(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=2)
        ip = "192.168.1.100"

        # 5 allowed requests
        for _ in range(5):
            assert limiter.is_allowed(ip) is True

        # 6th request blocked
        assert limiter.is_allowed(ip) is False

        # Wait for window to slide
        time.sleep(2.1)
        assert limiter.is_allowed(ip) is True


class TestAPIEndpoints:
    """Tests for FastAPI endpoints and security header compliance."""

    def test_root_status(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert "Supabase" in data["auth"]

    def test_security_headers_present(self):
        """Loophole Defense: Verify security headers on all responses."""
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_missing_token_rejection(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_authenticated_profile(self):
        token = create_test_token(user_id="user_789", email="dev@pusher.io")
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user_789"
        assert data["email"] == "dev@pusher.io"
        assert data["first_name"] == "Test"

    def test_unconfirmed_email_rejection(self):
        """Loophole Defense: Unconfirmed email users cannot access verified routes."""
        token = create_test_token(email_confirmed=False)
        resp = client.get(
            "/api/v1/auth/verified-only",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        assert "email address has not been confirmed" in resp.json()["detail"]

    def test_secret_key_not_leaked(self):
        """Loophole Defense: Secret keys must NEVER appear in any endpoint response."""
        token = create_test_token()
        endpoints = ["/", "/api/v1/auth/me", "/api/v1/auth/health"]
        for ep in endpoints:
            headers = {"Authorization": f"Bearer {token}"} if "me" in ep else {}
            resp = client.get(ep, headers=headers)
            body = resp.text
            assert settings.supabase_secret_key not in body, f"Secret key found in response of {ep}!"

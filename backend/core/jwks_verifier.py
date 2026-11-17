"""
Cryptographic JWKS & JWT Token Verifier for Supabase Auth
Handles ES256 / RS256 key discovery, caching, rotation, and signature verification.
"""

import time
import httpx
from typing import Optional, Dict, Any
from jose import jwt, jwk, JWTError, ExpiredSignatureError
from pydantic import BaseModel, Field
from backend.core.config import settings

class AuthenticatedUser(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: str = "authenticated"
    email_confirmed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    app_metadata: Dict[str, Any] = Field(default_factory=dict)
    claims: Dict[str, Any] = Field(default_factory=dict)

class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 401, error_code: str = "invalid_token"):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)

class JWKSVerifier:
    def __init__(self):
        self._keys_by_kid: Dict[str, Any] = {}
        self._last_fetch_time: float = 0.0
        self._ttl_seconds: int = settings.jwks_cache_ttl_seconds
        self._jwks_url: str = settings.supabase_jwks_url
        self._expected_issuer: str = f"{settings.supabase_url.rstrip('/')}/auth/v1"

    async def fetch_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches and caches the JSON Web Key Set from Supabase Auth."""
        now = time.time()
        if not force_refresh and self._keys_by_kid and (now - self._last_fetch_time < self._ttl_seconds):
            return self._keys_by_kid

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
                data = resp.json()

            new_keys = {}
            for key_dict in data.get("keys", []):
                kid = key_dict.get("kid")
                if kid:
                    try:
                        constructed = jwk.construct(key_dict)
                        new_keys[kid] = constructed
                    except Exception as e:
                        # Log error constructing key but don't fail other valid keys
                        continue

            if new_keys:
                self._keys_by_kid = new_keys
                self._last_fetch_time = now

            return self._keys_by_kid
        except Exception as err:
            # If fetch fails but we have cached keys, fallback to cached keys
            if self._keys_by_kid:
                return self._keys_by_kid
            raise AuthError(
                detail=f"Failed to retrieve Supabase JWKS public keys: {str(err)}",
                status_code=503,
                error_code="jwks_unavailable"
            )

    async def verify_token(self, token: str) -> AuthenticatedUser:
        """
        Cryptographically verifies the Supabase access token.
        Checks signature, expiration, issuer, audience, and extracts user claims.
        """
        if not token or not isinstance(token, str):
            raise AuthError(detail="Missing or malformed authorization token", status_code=401)

        token = token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        # Step 1: Extract header to find the Key ID (kid) and Algorithm (alg)
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError:
            raise AuthError(detail="Malformed JWT token header", status_code=401)

        alg = unverified_header.get("alg")
        if not alg or alg == "none":
            # Loophole Defense: Reject 'none' algorithm forgery attacks
            raise AuthError(detail="Insecure or missing JWT algorithm", status_code=401)

        kid = unverified_header.get("kid")

        # Step 2: Fetch cached JWKS keys
        keys = await self.fetch_jwks()

        # If kid is missing or unknown, try a force refresh once to handle key rotation
        if kid and kid not in keys:
            keys = await self.fetch_jwks(force_refresh=True)

        selected_key = keys.get(kid) if kid else None

        # Step 3: Decode and cryptographically verify signature
        try:
            if selected_key:
                # Asymmetric verification (ES256 / RS256)
                claims = jwt.decode(
                    token,
                    selected_key,
                    algorithms=[alg],
                    options={
                        "verify_aud": False,  # We will check aud explicitly below
                        "verify_iss": False,  # We will check iss explicitly below
                        "verify_exp": True,
                    }
                )
            else:
                # If key is not in JWKS, attempt verification with Supabase JWT Secret if provided
                claims = jwt.decode(
                    token,
                    settings.supabase_secret_key,
                    algorithms=[alg, "HS256"],
                    options={
                        "verify_exp": True,
                        "verify_aud": False,
                        "verify_iss": False,
                    }
                )
        except ExpiredSignatureError:
            # Loophole Defense: Clean error on expired tokens
            raise AuthError(detail="Authentication token has expired. Please log in again.", status_code=401, error_code="token_expired")
        except JWTError as e:
            # Loophole Defense: Reject invalid signature or tampered payload
            raise AuthError(detail=f"Invalid token signature: {str(e)}", status_code=401, error_code="invalid_signature")

        # Step 4: Validate Audience & Issuer
        aud = claims.get("aud")
        if aud != "authenticated":
            raise AuthError(detail=f"Invalid token audience: expected 'authenticated', got '{aud}'", status_code=401)

        iss = claims.get("iss")
        if iss and self._expected_issuer not in iss:
            raise AuthError(detail="Invalid token issuer", status_code=401)

        # Step 5: Check User ID
        sub = claims.get("sub")
        if not sub:
            raise AuthError(detail="Token missing user identity subject (sub)", status_code=401)

        # Step 6: Extract verified user model
        user_metadata = claims.get("user_metadata") or {}
        app_metadata = claims.get("app_metadata") or {}
        email = claims.get("email") or user_metadata.get("email")

        # Loophole Defense: Check email confirmation status from token
        confirmed_at = claims.get("email_confirmed_at") or claims.get("confirmed_at")
        email_confirmed = confirmed_at is not None

        return AuthenticatedUser(
            user_id=sub,
            email=email,
            role=claims.get("role", "authenticated"),
            email_confirmed=email_confirmed,
            metadata=user_metadata,
            app_metadata=app_metadata,
            claims=claims,
        )

# Global verifier instance
jwks_verifier = JWKSVerifier()

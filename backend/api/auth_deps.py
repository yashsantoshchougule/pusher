"""
FastAPI Authentication Dependencies
Provides drop-in dependencies for endpoints:
  • get_current_user: Verifies cryptographic JWT signature and expiry.
  • get_verified_user: Requires confirmed email address.
  • get_admin_user: Requires administrative role.
"""

import ipaddress
from urllib.parse import urlsplit

import httpx
from fastapi import Request, Depends, HTTPException, status
from starlette.requests import HTTPConnection

from backend.core.config import settings
from backend.core.jwks_verifier import jwks_verifier, AuthenticatedUser, AuthError
from backend.core.request_owner import request_owner
from backend.core.security import extract_bearer_token, auth_rate_limiter
from backend.core.target_service import target_scope

async def get_current_user(request: Request) -> AuthenticatedUser:
    """
    Validates the bearer token against Supabase JWKS public keys.
    Enforces IP-based rate limiting to prevent brute-force attacks.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit check on auth verification
    if not auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait a minute before making more requests."
        )

    try:
        token = extract_bearer_token(request)
        user = await jwks_verifier.verify_token(token)
        return user
    except AuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail,
            headers={"WWW-Authenticate": f'Bearer error="{e.error_code}"'}
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Invalid or expired credentials.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'}
        )

async def get_verified_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """
    Loophole Defense: Prevents users who have not confirmed their email
    from launching load tests, exhausting socket pools, or executing testing operations.
    """
    if not user.email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email address has not been confirmed yet. Please verify your email before accessing testing features."
        )
    return user

async def get_admin_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """
    Ensures the user possesses administrative or service_role claims.
    """
    is_admin = (
        user.role in ("service_role", "supabase_admin") or
        user.app_metadata.get("role") == "admin" or
        user.app_metadata.get("is_admin") is True
    )

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource."
        )
    return user


def offline_connection(connection: HTTPConnection) -> bool:
    if not settings.offline_dev or settings.pusher_mode != "local_dev" or not connection.client:
        return False
    try:
        if not ipaddress.ip_address(connection.client.host).is_loopback:
            return False
        origin_header = connection.headers.get("origin")
        allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if settings.host not in allowed_hosts or connection.url.hostname not in allowed_hosts:
            return False
        return not origin_header or (
            urlsplit(origin_header).hostname in allowed_hosts and origin_header in settings.allowed_origins
        )
    except ValueError:
        return False


async def resolve_operator(connection: HTTPConnection, token: str | None = None) -> AuthenticatedUser:
    if not token and not connection.headers.get("authorization") and offline_connection(connection):
        return AuthenticatedUser(user_id="offline:operator", email="local@pusher.internal", email_confirmed=True)
    if token is None:
        auth = connection.headers.get("authorization", "").split()
        if len(auth) != 2 or auth[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="A verified session is required.",
                                headers={"WWW-Authenticate": "Bearer"})
        token = auth[1]
    try:
        user = await jwks_verifier.verify_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if not user.email_confirmed and settings.supabase_url and settings.supabase_publishable_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    settings.supabase_url.rstrip("/") + "/auth/v1/user",
                    headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_publishable_key},
                )
                response.raise_for_status()
                details = response.json()
                user.email_confirmed = details.get("id") == user.user_id and bool(details.get("email_confirmed_at"))
        except (httpx.HTTPError, ValueError):
            pass
    if not user.email_confirmed:
        raise HTTPException(status_code=403, detail="Verify your email before accessing Pusher.")
    return user.model_copy(update={"user_id": f"supabase:{user.user_id}"})


async def require_operator(request: Request):
    actor = await resolve_operator(request)
    request.state.actor = actor
    owner = request_owner.set(actor.user_id)
    target = target_scope.set(None)
    try:
        yield actor
    finally:
        target_scope.reset(target)
        request_owner.reset(owner)

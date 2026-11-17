"""
FastAPI Authentication Dependencies
Provides drop-in dependencies for endpoints:
  • get_current_user: Verifies cryptographic JWT signature and expiry.
  • get_verified_user: Requires confirmed email address.
  • get_admin_user: Requires administrative role.
"""

from fastapi import Request, Depends, HTTPException, status
from backend.core.jwks_verifier import jwks_verifier, AuthenticatedUser, AuthError
from backend.core.security import extract_bearer_token, auth_rate_limiter

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
        user.metadata.get("is_admin") is True
    )

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to access this resource."
        )
    return user

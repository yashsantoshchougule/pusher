"""
Pusher Backend Application Entry Point
FastAPI application with strict CORS, security headers, exception masking, and Supabase auth.
"""

from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.core.config import settings
from backend.core.jwks_verifier import AuthError
from backend.core.load_engine import load_engine
from backend.core.run_manager import run_manager
from backend.api.auth_router import router as auth_router
from backend.api.auth_deps import require_operator
from backend.api.system_router import router as system_router
from backend.api.target_router import router as target_router
from backend.api.load_router import router as load_router
from backend.api.journey_router import router as journey_router
from backend.api.report_router import router as report_router
from backend.api.profile_router import router as profile_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        await run_manager.stop_all(reason="ENGINE_SHUTDOWN")


app = FastAPI(
    title="Pusher Load Testing API",
    description="High-performance asynchronous load testing engine with hardened Supabase authentication.",
    version="1.0.0",
    lifespan=lifespan,
)

# 1. Strict CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "apikey", "X-Requested-With", "X-Pusher-Device-ID"],
)

# 2. Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# 3. Global Exception Handler (Loophole Defense: Never leak stack traces or internal secrets)
@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "detail": exc.detail},
        headers={"WWW-Authenticate": f'Bearer error="{exc.error_code}"'},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        content = detail
    else:
        content = {"detail": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log securely on server, but return clean sanitized JSON to client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_error", "detail": "An internal server error occurred."},
    )

# 4. Mount Routers
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(target_router)
app.include_router(load_router)
app.include_router(journey_router)
app.include_router(report_router)
app.include_router(profile_router)


@app.get("/api/session")
async def operator_session(actor=Depends(require_operator)):
    return {"offline": actor.user_id == "offline:operator", "email": actor.email, "user_id": actor.user_id}


@app.get("/")
async def root():
    return {
        "service": "Pusher Backend Engine",
        "status": "online",
        "mode": settings.pusher_mode,
        "auth": "Supabase JWT / JWKS",
    }

if __name__ == "__main__":
    import uvicorn
    dev_reload = os.environ.get("PUSHER_DEV_RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=dev_reload)

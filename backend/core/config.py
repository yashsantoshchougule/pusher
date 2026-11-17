"""
Backend Configuration & Environment Settings
Loads environment variables from .env with strict security validation.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Project root directory (where .env resides)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_secret_key: str = Field(default="", alias="SUPABASE_SECRET_KEY")
    supabase_jwks_url: str = Field(
        default="",
        alias="SUPABASE_JWKS_URL"
    )

    # Application Mode
    pusher_mode: str = Field(default="local_dev", alias="PUSHER_MODE")  # 'local_dev' | 'production'
    port: int = Field(default=8000, alias="PORT")
    host: str = Field(default="0.0.0.0", alias="HOST")

    # Allowed CORS Origins for Frontend
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Security & Rate Limits
    auth_rate_limit_per_minute: int = 60
    jwks_cache_ttl_seconds: int = 3600  # 1 hour cache

    model_config = {
        "env_file": str(ENV_FILE) if ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

settings = Settings()

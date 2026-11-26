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

MAX_RAM_BUDGET_MB = 4 * 1024


def max_safe_ram_budget_mb(total_ram_mb: int) -> int:
    return min(MAX_RAM_BUDGET_MB, int(total_ram_mb * 0.75))


class Settings(BaseSettings):
    # Supabase Configuration
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_secret_key: str = Field(default="", alias="SUPABASE_SECRET_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    supabase_jwks_url: str = Field(
        default="",
        alias="SUPABASE_JWKS_URL"
    )

    # Google OAuth Configuration
    google_client_id: str = Field(
        default="",
        alias="GOOGLE_CLIENT_ID"
    )
    google_client_secret: str = Field(
        default="",
        alias="GOOGLE_CLIENT_SECRET"
    )

    # GitHub OAuth Configuration
    github_client_id: str = Field(
        default="",
        alias="GITHUB_CLIENT_ID"
    )
    github_client_secret: str = Field(
        default="",
        alias="GITHUB_CLIENT_SECRET"
    )

    # Application Mode
    pusher_mode: str = Field(default="local_dev", alias="PUSHER_MODE")  # 'local_dev' | 'production'
    port: int = Field(default=8000, alias="PORT")
    host: str = Field(default="127.0.0.1", alias="HOST")
    database_path: Path = Field(default=ROOT_DIR / "backend" / "pusher_runs.db", alias="PUSHER_DB_PATH")
    offline_dev: bool = Field(default=False, alias="PUSHER_OFFLINE_DEV")
    sandbox_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:8080", "http://localhost:8080"],
        alias="PUSHER_SANDBOX_ORIGINS",
    )

    # Allowed CORS Origins for Frontend
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
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

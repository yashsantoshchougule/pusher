import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import pytest


if "backend.core.database" in sys.modules:
    raise pytest.UsageError("Start pytest in a fresh process so the test database is selected before imports.")

_database_directory = TemporaryDirectory(prefix="pusher-test-db-", ignore_cleanup_errors=True)
os.environ["PUSHER_DB_PATH"] = str(Path(_database_directory.name) / "test.sqlite")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.update(
    SUPABASE_URL="https://auth.example.invalid",
    SUPABASE_JWKS_URL="https://auth.example.invalid/.well-known/jwks.json",
    SUPABASE_JWT_SECRET="isolated-jwt-fixture",
    SUPABASE_SECRET_KEY="isolated-admin-fixture",
    SUPABASE_PUBLISHABLE_KEY="",
    GOOGLE_CLIENT_ID="test-oauth-client.example.invalid",
    PUSHER_MODE="local_dev",
    PUSHER_OFFLINE_DEV="false",
    HOST="127.0.0.1",
    PORT="8000",
)


@pytest.fixture(autouse=True)
def mock_provider_health(monkeypatch):
    from backend.core.supabase_admin import supabase_admin

    monkeypatch.setattr(supabase_admin, "check_health", AsyncMock(return_value={"status": "healthy"}))


@pytest.fixture(autouse=True)
def run_legacy_scenarios_as_one_operator(request, monkeypatch, tmp_path):
    """Older feature tests use one synthetic operator and an in-process sandbox."""
    filename = request.node.path.name
    if not (filename.startswith("test_stage") or filename in {
        "test_profile_backend.py", "test_database_persistence.py",
    }):
        return

    import httpx
    from backend.api import auth_deps
    from backend.core import database, journey_service, load_engine as engine_module, target_policy, target_service
    from backend.core.jwks_verifier import AuthenticatedUser
    from backend.main import app

    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy-test.sqlite")
    database.init_all_tables()
    target_service.target_store.__init__()
    engine_module.load_engine.__init__()
    from backend.core.run_manager import run_manager
    run_manager.reset()
    monkeypatch.setattr(auth_deps, "resolve_operator", AsyncMock(return_value=AuthenticatedUser(
        user_id="default_test_user", email="fixture@example.invalid", email_confirmed=True,
    )))
    # The WebSocket handler imports resolve_operator separately.
    from backend.api import load_router

    monkeypatch.setattr(load_router, "resolve_operator", auth_deps.resolve_operator)

    async def test_resolve(host, port, sandbox):
        if host.endswith(".dev"):
            return ["93.184.216.34"]
        if host in {"gitb.com", "gitb-nonexistent-domain-9999.com"}:
            raise target_policy.DestinationError("The target hostname could not be resolved.")
        return await target_policy.resolve_addresses(host, port, sandbox)

    def sandbox_client(*args, **kwargs):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app))

    monkeypatch.setattr(target_service, "resolve_addresses", test_resolve)
    monkeypatch.setattr(journey_service, "target_client", sandbox_client)
    monkeypatch.setattr(engine_module, "target_client", sandbox_client)

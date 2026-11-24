"""Verify the generated Guard on a Flask fixture without outbound network access."""

import asyncio
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from flask import Flask, abort, request, session


async def check_guard(directory: Path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    os.environ["PUSHER_DB_PATH"] = str(directory / "verification.sqlite")
    from backend.core import target_service
    from backend.core.request_owner import request_owner

    request_owner.set("flask-verification-fixture")
    origin = "https://flask-fixture.example.invalid"
    artifact = target_service.generate_pusher_guard_file(origin)
    path = directory / "pusher_guard.py"
    path.write_bytes(artifact["content"].encode("utf-8"))
    guard = runpy.run_path(str(path))

    app = Flask(__name__)
    app.secret_key = "disposable-test-session-key"
    accepted = []

    @app.post("/protected")
    def protected():
        actor = session.get("user")
        if not actor:
            abort(401)
        if request.headers.get("X-CSRF-Token") != session.get("csrf"):
            abort(403)
        if len(accepted) >= 2:
            abort(429)
        accepted.append((actor, request.remote_addr))
        return {"user": actor}

    @app.get("/admin")
    def admin():
        if session.get("role") != "admin":
            abort(403)
        return {"ok": True}

    guard["setup_pusher_guard"](app)
    with app.test_client() as client:
        assert client.get("/__pusher_verify").status_code == 400
        assert client.post("/protected", headers={"X-Pusher-Guard-ID": "invalid"}).status_code == 401

        def verified_response(outbound):
            assert outbound.method == "GET" and outbound.url.path == "/__pusher_verify"
            assert outbound.url.host == "flask-fixture.example.invalid"
            response = client.get(outbound.url.raw_path.decode("ascii"))
            return httpx.Response(response.status_code, content=response.data)

        with patch.object(target_service, "target_client", side_effect=lambda *args: httpx.AsyncClient(
            transport=httpx.MockTransport(verified_response)
        )):
            verified, _, _ = await target_service.verify_target_handshake(origin, artifact["guard_id"])
            assert verified

        with client.session_transaction() as identity:
            identity.update(user="ordinary-fixture", role="user", csrf="fixture-csrf")
        assert client.get("/admin").status_code == 403
        assert client.post("/protected").status_code == 403
        headers = {"X-CSRF-Token": "fixture-csrf"}
        source = {"REMOTE_ADDR": "192.0.2.10"}
        for _ in range(2):
            response = client.post("/protected", headers=headers, environ_overrides=source)
            assert response.status_code == 200 and response.json["user"] == "ordinary-fixture"
        assert client.post("/protected", headers=headers, environ_overrides=source).status_code == 429
        assert accepted == [("ordinary-fixture", "192.0.2.10")] * 2

        guard["setup_pusher_guard"].__globals__["time"] = SimpleNamespace(time=lambda: artifact["expires_at"])
        expired = client.get("/__pusher_verify", query_string={"nonce": "a" * 32})
        assert expired.status_code == 403 and expired.json["status"] == "EXPIRED"


if __name__ == "__main__":
    with TemporaryDirectory(prefix="pusher-flask-guard-", ignore_cleanup_errors=True) as temp:
        asyncio.run(check_guard(Path(temp)))
    print("Flask Guard ownership, expiry, and protected-route enforcement passed.")

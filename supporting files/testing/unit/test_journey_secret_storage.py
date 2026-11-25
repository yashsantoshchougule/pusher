import asyncio
import json

import httpx
import pytest

from backend.core import database, journey_service, load_engine as engine_module, report_service
from backend.core.config import settings
from backend.main import app


@pytest.fixture
def private_db(tmp_path, monkeypatch):
    path = tmp_path / "journey-privacy.sqlite"
    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_all_tables()
    return path


@pytest.mark.asyncio
async def test_private_inputs_are_required_at_runtime_and_never_written(private_db, monkeypatch):
    monkeypatch.setattr(settings, "offline_dev", True)
    outbound = []
    target = "http://127.0.0.1:8000/api/sandbox/target"
    engine = engine_module.LoadEngine()
    monkeypatch.setattr("backend.api.load_router.load_engine", engine)

    def respond(request):
        outbound.append(request)
        return httpx.Response(200)

    def target_client(*args, **kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(respond))

    monkeypatch.setattr(journey_service, "target_client", target_client)
    monkeypatch.setattr(engine_module, "target_client", target_client)
    steps = [{
        "step_id": "login", "method": "POST", "path": "/api/sandbox/login?query=synthetic-private-query",
        "headers": {
            "Authorization": "Bearer synthetic-private-token",
            "X-Custom": "synthetic-custom-secret",
            "Content-Type": "application/json",
        },
        "body": {"password": "synthetic-private-password"},
    }]
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        assert (await client.post("/api/target/verify", json={
            "target_url": target, "is_sandbox": True,
        })).status_code == 200
        saved = (await client.post("/api/journey/save", json={"steps": steps, "use_journey": True})).raise_for_status()
        reopened = (await client.get("/api/journey")).raise_for_status().json()["steps"]
        assert reopened == saved.json()["steps"]
        step = reopened[0]
        assert step["headers"] == {"Content-Type": "application/json"}
        assert step["body"] is None and step["requires_body"]
        assert step["required_headers"] == ["Authorization", "X-Custom"]
        assert step["path"] == "/api/sandbox/login" and step["requires_query"]

        start = {"target_url": target, "is_sandbox": True, "use_journey": True, "duration_sec": 1, "target_vus": 1}
        for path, payload in (("/api/journey/dry-run", {}), ("/api/load/start", start)):
            assert (await client.post(path, json=payload)).status_code == 422
        assert not outbound
        inputs = {**step, "headers": steps[0]["headers"], "body": steps[0]["body"]}
        missing_query = await client.post("/api/journey/dry-run", json={"steps": [inputs]})
        assert missing_query.status_code == 422 and "query" in missing_query.json()["detail"]
        assert not outbound
        runtime = [{**inputs, "path": steps[0]["path"]}]
        dry = (await client.post("/api/journey/dry-run", json={"steps": runtime})).raise_for_status()
        assert dry.json()["all_passed"]
        assert "synthetic-private-query" not in dry.text
        run = (await client.post("/api/load/start", json={**start, "journey_steps": runtime})).raise_for_status()
        await asyncio.wait_for(engine._master_task, 3)
        report = (await client.get("/api/reports/" + run.json()["run_id"])).raise_for_status().json()
        assert report["total_requests"] > 0
        assert report["step_metrics"][0]["path"] == "/api/sandbox/login"
        assert "synthetic-private-query" not in json.dumps(report)
        export = (await client.get("/api/reports/" + run.json()["run_id"] + "/export")).raise_for_status()
        assert "synthetic-private-query" not in export.text
        assert len(outbound) > 1
        assert all(request.headers["authorization"] == "Bearer synthetic-private-token" for request in outbound)
        assert all(json.loads(request.content) == steps[0]["body"] for request in outbound)
        assert all(request.url.params["query"] == "synthetic-private-query" for request in outbound)

    for file in private_db.parent.glob(private_db.name + "*"):
        assert b"synthetic-" not in file.read_bytes()


def test_legacy_scrub_preserves_owned_and_unowned_templates(private_db):
    report_service.save_run({"run_id": "legacy-journey-query"})
    conn = database.get_db_connection()
    try:
        with conn:
            for owner in ("default_test_user", "legacy-owner"):
                conn.execute(
                    """INSERT INTO journey_steps (user_id, step_id, step_order, name, method, path, headers_json, body_json)
                    VALUES (?, 'old', 1, 'Saved step', 'POST', '/orders?query=synthetic-legacy-query', ?, ?);""",
                    (owner, json.dumps({
                        "Authorization": "Bearer synthetic-legacy-bearer",
                        "X-Session": "{{token}}",
                    }), json.dumps({"password": "synthetic-legacy-password"})),
                )
            conn.execute(
                "UPDATE journey_settings SET last_dry_run_json = ? WHERE user_id = 'default_test_user';",
                (json.dumps([{
                    "passed": False, "error": "synthetic-legacy-error",
                    "path": "/orders?query=synthetic-legacy-query",
                }]),),
            )
            conn.execute(
                "UPDATE test_runs SET step_metrics_json = ? WHERE run_id = 'legacy-journey-query';",
                (json.dumps([{"path": "/orders?query=synthetic-legacy-query"}]),),
            )
            conn.execute(
                "UPDATE journey_steps SET headers_json = ? WHERE user_id = 'default_test_user';",
                (json.dumps(["synthetic-legacy-malformed"]),),
            )
    finally:
        conn.close()

    saved = {owner: database.db_get_journey(owner) for owner in ("default_test_user", "legacy-owner")}
    assert saved["legacy-owner"]["steps"][0]["headers"] == {"X-Session": "{{token}}"}
    assert saved["legacy-owner"]["steps"][0]["required_headers"] == ["Authorization"]
    assert saved["legacy-owner"]["steps"][0]["requires_body"]
    assert saved["legacy-owner"]["steps"][0]["requires_query"]
    assert saved["legacy-owner"]["steps"][0]["path"] == "/orders"
    assert saved["default_test_user"]["last_dry_run"] == [{"passed": False, "path": "/orders"}]
    legacy_report = report_service.get_run("legacy-journey-query")
    assert legacy_report["step_metrics"] == [{"path": "/orders"}]
    assert "synthetic-legacy-query" not in legacy_report["step_metrics_json"]
    assert journey_service.validate_journey_steps(saved["default_test_user"]["steps"]) == (
        False, "Step 1: invalid headers.",
    )
    assert b"synthetic-legacy" in private_db.read_bytes()
    database.scrub_legacy_journey_inputs()
    assert saved == {owner: database.db_get_journey(owner) for owner in saved}
    for file in private_db.parent.glob(private_db.name + "*"):
        assert b"synthetic-legacy" not in file.read_bytes()


def test_journey_step_metadata_strips_query_and_fragment():
    cleaned = database.journey_step_metadata([
        {"path": "/api/orders?token=secret#section-2", "name": "orders"},
        {"path": "/api/items#frag-secret", "name": "items"},
    ])
    assert cleaned == [
        {"path": "/api/orders", "name": "orders"},
        {"path": "/api/items", "name": "items"},
    ]

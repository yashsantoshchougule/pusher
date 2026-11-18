"""
Unit & Integration Tests for Full SQLite Database Persistence across Service Re-initialization:
- active_target_state (single-row table id=1)
- traffic_config (single-row table id=1)
- journey_steps & journey_settings
- guard_generations & 3/day rate limit persistence
- burned_guards permanent tombstone persistence
- test_runs persistence and clean empty state
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.database import (
    init_all_tables,
    get_db_connection,
    db_get_active_target,
    db_save_active_target,
    db_get_traffic_config,
    db_save_traffic_config,
    db_get_journey,
    db_save_journey,
    db_record_guard_generation,
    db_get_daily_generations_count,
    db_burn_guard,
    db_is_guard_burned,
)
from backend.core.target_service import ActiveTargetStore, target_store
from backend.core.journey_service import JourneyStore
from backend.core.report_service import save_run, get_all_runs

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean SQLite state before each persistence test."""
    init_all_tables()
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM guard_generations;")
        conn.execute("DELETE FROM issued_guards;")
        conn.execute("DELETE FROM burned_guards;")
        conn.execute("DELETE FROM journey_steps;")
        conn.execute("DELETE FROM test_runs;")
        conn.execute("""
            UPDATE active_target_state SET
                target_url = '',
                is_sandbox = 0,
                guard_id = NULL,
                handshake_secret = NULL,
                expected_file_sha256 = NULL,
                creator_device_hash = NULL,
                bound_host_hash = NULL,
                issued_at = NULL,
                expires_at = NULL,
                active_guard_active = 0,
                is_verified = 0,
                last_burn_reason = NULL
            WHERE id = 1;
        """)
        conn.execute("""
            UPDATE traffic_config SET
                mode = 'step_ramp',
                ram_limit_mb = 500,
                virtual_users = 100,
                duration_sec = 30,
                max_error_pct = 5.0,
                p95_ceiling_ms = 1500.0,
                cache_bust = 1
            WHERE id = 1;
        """)
        conn.execute("""
            UPDATE journey_settings SET
                use_journey = 0,
                last_dry_run_json = 'null'
            WHERE id = 1;
        """)
    conn.close()
    target_store._load_from_db()


def test_active_target_state_persists_across_fresh_store_init():
    """Verify target URL, guard token, and verification state persist in SQLite."""
    now = int(time.time())
    db_save_active_target({
        "target_url": "https://api.persistent-app.com",
        "is_sandbox": False,
        "guard_id": "PG-PERSIST-48H",
        "handshake_secret": "secret_abc123",
        "expected_file_sha256": "sha256_mock_hash",
        "creator_device_hash": "device_hash_xyz",
        "bound_host_hash": "host_hash_001",
        "issued_at": now,
        "expires_at": now + 172800,
        "active_guard_active": True,
        "is_verified": True,
        "last_burn_reason": None,
    })

    # Simulate fresh service re-initialization
    fresh_store = ActiveTargetStore()
    assert fresh_store.target_url == "https://api.persistent-app.com"
    assert fresh_store.guard_id == "PG-PERSIST-48H"
    assert fresh_store.is_verified is True
    assert fresh_store.active_guard_active is True
    assert fresh_store.get_remaining_seconds() > 170000


def test_traffic_config_persists_in_sqlite():
    """Verify traffic setup changes persist in SQLite and survive reload."""
    payload = {
        "mode": "sudden_rush",
        "ram_limit_mb": 750,
        "virtual_users": 350,
        "duration_sec": 45,
        "max_error_pct": 2.5,
        "p95_ceiling_ms": 800.0,
        "cache_bust": False,
    }
    post_res = client.post("/api/traffic/config", json=payload)
    assert post_res.status_code == 200
    saved = post_res.json()
    assert saved["mode"] == "sudden_rush"
    assert saved["ram_limit_mb"] == 750
    assert saved["virtual_users"] == 350
    assert saved["cache_bust"] == 0

    # Read directly from SQLite via fresh GET request
    get_res = client.get("/api/traffic/config")
    assert get_res.status_code == 200
    loaded = get_res.json()
    assert loaded["mode"] == "sudden_rush"
    assert loaded["ram_limit_mb"] == 750
    assert loaded["virtual_users"] == 350
    assert loaded["duration_sec"] == 45
    assert loaded["max_error_pct"] == 2.5
    assert loaded["p95_ceiling_ms"] == 800.0
    assert loaded["cache_bust"] == 0


def test_journey_steps_persist_in_sqlite():
    """Verify API Builder steps and use_journey settings persist in SQLite."""
    steps = [
        {
            "step_id": "step_auth",
            "name": "Auth User",
            "method": "POST",
            "path": "/api/sandbox/login",
            "headers": {"Content-Type": "application/json"},
            "body": '{"user":"test"}',
            "expected_status": 200,
            "extract_json_key": "token",
        },
        {
            "step_id": "step_data",
            "name": "Get Profile",
            "method": "GET",
            "path": "/api/sandbox/items",
            "headers": {"Authorization": "Bearer {{token}}"},
            "expected_status": 200,
            "extract_json_key": "",
        },
    ]

    save_res = client.post("/api/journey/save", json={"steps": steps, "use_journey": True})
    assert save_res.status_code == 200

    # Simulate fresh service re-initialization
    fresh_journey = JourneyStore()
    journey_data = fresh_journey.get_journey()
    assert journey_data["use_journey"] is True
    assert len(journey_data["steps"]) == 2
    assert journey_data["steps"][0]["step_id"] == "step_auth"
    assert journey_data["steps"][1]["step_id"] == "step_data"


def test_guard_generations_rate_limit_persists_in_sqlite():
    """Verify 3/day generation rate limit persists in SQLite across fresh store init."""
    now = time.time()
    device_hash = "test_dev_hash_1"

    db_record_guard_generation("PG-GEN-1", device_hash, now - 100)
    db_record_guard_generation("PG-GEN-2", device_hash, now - 50)

    # Fresh store check
    count = db_get_daily_generations_count(device_hash, now - 86400)
    assert count == 2

    # Add 3rd generation
    db_record_guard_generation("PG-GEN-3", device_hash, now)
    count3 = db_get_daily_generations_count(device_hash, now - 86400)
    assert count3 == 3


def test_burned_guards_tombstone_persists_in_sqlite():
    """Verify permanently burned guards remain locked in SQLite across fresh service init."""
    db_burn_guard(
        guard_id="PG-BURNED-PERMANENT",
        burn_reason="MANUAL_USER_KILL",
        creator_device_hash="creator_hash",
        offending_device_hash=None,
    )

    # Verify via fresh DB query
    burned = db_is_guard_burned("PG-BURNED-PERMANENT")
    assert burned is not None
    assert burned["burn_reason"] == "MANUAL_USER_KILL"

    # Non-burned ID returns None
    assert db_is_guard_burned("PG-VALID-ID") is None


def test_test_runs_sqlite_persistence_and_empty_state():
    """Verify test_runs table persists real runs and returns empty state when 0 rows exist."""
    # 1. Empty state
    hist_empty = client.get("/api/history")
    assert hist_empty.status_code == 200
    data_empty = hist_empty.json()
    assert data_empty["runs"] == []
    assert data_empty["scorecard"] is None

    # 2. Insert real test run
    save_run({
        "run_id": "RUN-PERSIST-001",
        "timestamp": "14:30:00",
        "target_url": "https://api.myrealapp.com",
        "guard_id": "PG-REAL-01",
        "mode": "Step-Ramp",
        "target_vus": 150,
        "peak_vus": 150,
        "duration_sec": 30,
        "elapsed_sec": 30,
        "peak_rps": 620,
        "avg_rps": 580,
        "p95_ms": 115.0,
        "error_pct": 0.0,
        "total_requests": 18600,
        "status_2xx": 18600,
        "status_429": 0,
        "status_5xx": 0,
        "bytes_discarded_mb": 0.6,
        "ram_mb": 75.0,
        "verdict": "PASSED",
        "status_label": "PASSED (Completed 30s)",
        "knee_vus": 120,
        "knee_rps": 600,
        "knee_p95_ms": 105.0,
        "bottleneck_summary": "Knee detected at 120 VUs.",
        "timeseries": [],
        "step_metrics": [],
    })

    # 3. Read back via API
    hist_populated = client.get("/api/history")
    assert hist_populated.status_code == 200
    data_pop = hist_populated.json()
    assert len(data_pop["runs"]) == 1
    assert data_pop["runs"][0]["run_id"] == "RUN-PERSIST-001"
    assert data_pop["scorecard"] is not None
    assert data_pop["scorecard"]["run_id"] == "RUN-PERSIST-001"
    assert data_pop["scorecard"]["peak_rps"] == 620

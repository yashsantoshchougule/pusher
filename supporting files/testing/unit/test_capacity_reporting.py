import json
import time

import pytest

from backend.api.report_router import export_report_endpoint
from backend.core import database, load_engine, report_service


def sample(vus, rps=20, p95_ms=25, error_pct=0):
    return {"vus": vus, "rps": rps, "p95_ms": p95_ms, "error_pct": error_pct}


HEALTHY = [sample(10, 100, 10), sample(20, 150, 20), sample(30, 155, 55)]
ALL_FAILED = [sample(10, 10, error_pct=100), sample(20, 20, error_pct=100)]


@pytest.mark.parametrize(
    "samples",
    [
        ALL_FAILED,
        [],
        [sample(vus, rps=0) for vus in (10, 20, 30)],
        [sample(20)] * 4,
        [sample(10), sample(20), sample(30, error_pct=2.1)],
        [*HEALTHY, sample(20, error_pct=3)],
        [sample(10), sample(20), {"vus": 30, "rps": 30, "p95_ms": 25}],
        [sample(10), sample(20), sample(30, p95_ms=float("nan"))],
        [sample(10), sample(20), sample(30, p95_ms=81)],
    ],
    ids=["all-failed", "empty", "no-requests", "one-level", "unhealthy", "failing-repeat",
         "missing-error-rate", "invalid-latency", "exceeds-latency-limit"],
)
def test_capacity_unavailable_without_three_healthy_levels(samples):
    result = report_service.detect_knee_of_curve(samples, target_vus=30, p95_ceiling_ms=100)
    assert result["knee_vus"] == result["knee_rps"] == 0
    assert result["bottleneck_summary"] == "Capacity unavailable"


def test_measured_slope_recommends_healthy_level():
    result = report_service.detect_knee_of_curve(
        [*HEALTHY, sample(40, error_pct=3), sample(50, p95_ms=81)],
        target_vus=50, p95_ceiling_ms=100,
    )
    assert result["knee_vus"] == 20
    assert result["knee_rps"] == 150
    assert "Optimal Knee detected at 20 VUs" in result["bottleneck_summary"]


def test_health_thresholds_include_boundary_values():
    result = report_service.detect_knee_of_curve(
        [sample(10, 50, 80, 2), sample(20, 100, 80, 2), sample(30, 150, 80, 2)],
        target_vus=30, p95_ceiling_ms=100,
    )
    assert result["knee_vus"] == 30
    assert "Highest healthy load observed" in result["bottleneck_summary"]


def test_migration_hides_legacy_capacity_but_preserves_the_archive(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy-capacity.sqlite")
    database.init_all_tables()
    report_service.save_run({
        "run_id": "old-capacity", "knee_vus": 20, "knee_rps": 20,
        "bottleneck_summary": "Optimal Knee detected at 20 VUs.", "timeseries": ALL_FAILED,
    })
    conn = database.get_db_connection()
    try:
        with conn:
            conn.execute("ALTER TABLE test_runs DROP COLUMN capacity_checked")
    finally:
        conn.close()
    database.init_all_tables()

    report = report_service.get_run("old-capacity")
    assert report["knee_vus"] == 0 and report["bottleneck_summary"] == "Capacity unavailable"
    assert report["timeseries"] == ALL_FAILED
    assert report_service.get_all_runs()["scorecard"]["knee_vus"] == 0
    conn = database.get_db_connection()
    try:
        assert conn.execute("SELECT knee_vus FROM test_runs").fetchone()["knee_vus"] == 20
    finally:
        conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("samples, expected_vus", [(ALL_FAILED, 0), (HEALTHY, 20)])
async def test_capacity_persists_from_run_sampling_through_export(samples, expected_vus):
    engine = load_engine.LoadEngine()
    engine.run_id = f"capacity-fixture-{expected_vus}"
    engine.start_time = time.time() - 10
    engine.duration_sec = 10
    engine.target_vus = 30
    engine.p95_ceiling_ms = 100
    for elapsed, observation in enumerate(samples, 1):
        engine._sample_run(elapsed, {
            **observation, "active_vus": observation["vus"], "live_rps": observation["rps"],
        })
    await engine._finish_run()

    saved = report_service.get_run(engine.run_id)
    exported = json.loads((await export_report_endpoint(engine.run_id)).body)
    history = report_service.get_all_runs(q=engine.run_id)
    assert history["scorecard"]["knee_vus"] == expected_vus
    for report in (saved, exported, history["runs"][0]):
        assert report["knee_vus"] == expected_vus
        assert (report["bottleneck_summary"] == "Capacity unavailable") == (expected_vus == 0)
    assert len(exported["timeseries"]) == len(samples)


def test_detect_knee_handles_floats_slow_targets_and_capacity_reason():
    # Steady Crowd (1 tier) -> unavailable with clear mode reason
    steady = report_service.detect_knee_of_curve(
        [sample(175.0, 54.0, 2951.9, 53.7)],
        target_vus=873,
        p95_ceiling_ms=5000.0,
        max_error_pct=15.0,
        mode="step_ramp",
    )
    assert steady["knee_vus"] == 0
    assert steady["bottleneck_summary"] == "Capacity unavailable"
    assert "175 VUs" in steady["capacity_reason"]
    assert len(steady["steps"]) == 1
    assert steady["steps"][0]["healthy"] is False

    # Steady Crowd with 1 healthy tier explains mode limitation
    steady_ok = report_service.detect_knee_of_curve(
        [sample(50, 120, 45, 0.0)],
        target_vus=50,
        p95_ceiling_ms=1000.0,
        mode="steady_crowd",
    )
    assert steady_ok["knee_vus"] == 0
    assert "steady_crowd" in steady_ok["capacity_reason"]

    # Slow target (0.5 RPS/VU) scaling linearly should NOT false-trigger knee on rps_gain_per_vu < 1.5
    slow_linear = [
        sample(10, 5.0, 200.0, 0.0),
        sample(20, 10.0, 210.0, 0.0),
        sample(30, 15.0, 220.0, 0.0),
        sample(40, 20.0, 230.0, 0.0),
    ]
    slow_res = report_service.detect_knee_of_curve(slow_linear, target_vus=40, p95_ceiling_ms=1000.0)
    assert slow_res["knee_vus"] == 40
    assert "Highest healthy load observed" in slow_res["bottleneck_summary"]

    # Stricter max_error_pct=1.0 rejects 1.5% tier, while looser max_error_pct=15.0 still caps healthy capacity at 2.0%
    strict_res = report_service.detect_knee_of_curve(
        [sample(10, 50, 20, 0.0), sample(20, 100, 25, 0.0), sample(30, 150, 30, 1.5)],
        target_vus=30,
        p95_ceiling_ms=1000.0,
        max_error_pct=1.0,
    )
    assert strict_res["knee_vus"] == 0
    loose_res = report_service.detect_knee_of_curve(
        [sample(10, 50, 20, 0.0), sample(20, 100, 25, 0.0), sample(30, 150, 30, 9.0)],
        target_vus=30,
        p95_ceiling_ms=1000.0,
        max_error_pct=15.0,
    )
    assert loose_res["knee_vus"] == 0
    assert "30 VUs" in loose_res["capacity_reason"]

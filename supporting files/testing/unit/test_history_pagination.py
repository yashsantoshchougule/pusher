from contextlib import asynccontextmanager
import json

import pytest

from backend.core import database, load_engine as engine_module, report_service


@pytest.fixture(autouse=True)
def isolated_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "history.sqlite")
    database.init_all_tables()


def test_history_pages_do_not_include_reports_and_keep_timestamp_ties_stable():
    large_chart = [{"elapsed_sec": index, "rps": index} for index in range(3600)]
    for index in range(30):
        report_service.save_run({
            "run_id": f"RUN-TIE-{index:02d}", "created_at": 1_000, "mode": "Step Ramp",
            "verdict": "PASSED" if index == 0 else "CIRCUIT_BREAKER",
            "timeseries": large_chart if index == 29 else [],
        })
    first = report_service.get_all_runs(mode="step-ramp")
    second = report_service.get_all_runs(mode="step-ramp", cursor=first["next_cursor"])
    assert len(first["runs"]) == 25 and len(second["runs"]) == 5
    ids = [row["run_id"] for row in first["runs"] + second["runs"]]
    assert ids == [f"RUN-TIE-{index:02d}" for index in reversed(range(30))]
    assert first["scorecard"]["run_id"] == "RUN-TIE-00"
    assert first["scorecard"] == second["scorecard"]
    assert second["next_cursor"] is None
    assert "timeseries" not in first["runs"][0] and "timeseries_json" not in first["runs"][0]
    assert len(json.dumps(first)) < 25_000
    assert report_service.get_run("RUN-TIE-29")["timeseries"] == large_chart
    assert len(report_service.get_all_runs(q="TIE-29")["runs"]) == 1
    with pytest.raises(ValueError, match="Invalid history cursor"):
        report_service.get_all_runs(cursor="invalid")
    with pytest.raises(ValueError, match="History limit"):
        report_service.get_all_runs(limit=101)


@pytest.mark.asyncio
async def test_a_synthetic_24_hour_run_keeps_bounded_chart_buckets(monkeypatch):
    @asynccontextmanager
    async def client(*args, **kwargs):
        yield object()

    monkeypatch.setattr(engine_module, "target_client", client)
    engine = engine_module.LoadEngine()
    run_id = await engine.start("https://example.invalid", "steady_crowd", 1, 86400)
    status = engine.get_status()
    for second in range(86400):
        status["live_rps"] = 95 if second == 35 else 20
        engine._sample_run(second, status)
    await engine.stop()
    report = report_service.get_run(run_id)
    assert len(report["timeseries"]) == 3600
    assert report["peak_rps"] == 95
    assert "run_history" not in engine.get_status()

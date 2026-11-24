from contextlib import asynccontextmanager
from uuid import UUID

import pytest

from backend.core import database, load_engine as engine_module, report_service


def test_legacy_reports_survive_schema_initialization(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    report_service.init_db()
    for run_id in ("RUN-101", "RUN-102", "RUN-103"):
        report_service.save_run({"run_id": run_id, "peak_rps": 80})
    conn = report_service.get_db_connection()
    try:
        conn.execute("DROP INDEX test_runs_owner_order")
        conn.execute("ALTER TABLE test_runs DROP COLUMN user_id")
        conn.commit()
    finally:
        conn.close()
    database.init_all_tables()
    database.init_all_tables()
    assert [report_service.get_run(f"RUN-{index}")["peak_rps"] for index in (101, 102, 103)] == [80, 80, 80]


@pytest.mark.asyncio
async def test_new_runs_use_distinct_ids_and_report_retry_keeps_original(monkeypatch):
    @asynccontextmanager
    async def mock_client(*args, **kwargs):
        yield object()

    monkeypatch.setattr(engine_module, "target_client", mock_client)
    engine = engine_module.LoadEngine()
    ids = []
    for _ in range(2):
        ids.append(await engine.start("https://example.invalid", "steady_crowd", 1, 2))
        await engine.stop()
    assert ids[0] != ids[1]
    assert all(UUID(run_id[4:]).version == 4 for run_id in ids)
    original = report_service.get_run(ids[0])
    assert original is not None
    assert report_service.get_run(ids[1]) is not None
    report_service.save_run({"run_id": ids[0], "peak_rps": 999})
    assert report_service.get_run(ids[0]) == original

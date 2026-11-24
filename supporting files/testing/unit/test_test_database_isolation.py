import os
from pathlib import Path
import sqlite3

from backend.core import database, report_service


def test_report_cleanup_does_not_touch_another_database(tmp_path, monkeypatch):
    assert database.DB_PATH == Path(os.environ["PUSHER_DB_PATH"]).resolve()
    untouched = tmp_path / "existing.sqlite"
    with monkeypatch.context() as separate:
        separate.setattr(database, "DB_PATH", untouched)
        database.init_all_tables()
        report_service.save_run({"run_id": "EXISTING-REPORT"})
    report_service.save_run({"run_id": "DISPOSABLE-REPORT"})
    report_service.clear_runs()
    assert report_service.get_run("DISPOSABLE-REPORT") is None
    with sqlite3.connect(untouched) as conn:
        assert conn.execute("SELECT run_id FROM test_runs").fetchall() == [("EXISTING-REPORT",)]

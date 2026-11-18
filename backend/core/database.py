"""
Centralized SQLite Database Access Layer for PUSHER Platform
Maintains persistent state in backend/pusher_runs.db:
- active_target_state (single-row table id=1)
- guard_generations (rolling 3/day rate limit tracking)
- issued_guards (ledger of issued guard tokens)
- burned_guards (permanent tombstone registry)
- traffic_config (single-row table id=1)
- journey_steps (ordered multi-step API journeys)
- journey_settings (single-row table id=1)
- test_runs (real historical load test executions)
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "pusher_runs.db"


def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-safe connection to the central SQLite database with Row factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_all_tables() -> None:
    """Initializes all required schema tables and cleans out legacy mock runs."""
    conn = get_db_connection()
    try:
        with conn:
            # 1. Active Target State (Single Row: id = 1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_target_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    target_url TEXT DEFAULT '',
                    is_sandbox INTEGER DEFAULT 0,
                    guard_id TEXT DEFAULT NULL,
                    handshake_secret TEXT DEFAULT NULL,
                    expected_file_sha256 TEXT DEFAULT NULL,
                    creator_device_hash TEXT DEFAULT NULL,
                    bound_host_hash TEXT DEFAULT NULL,
                    issued_at REAL DEFAULT NULL,
                    expires_at REAL DEFAULT NULL,
                    active_guard_active INTEGER DEFAULT 0,
                    is_verified INTEGER DEFAULT 0,
                    last_burn_reason TEXT DEFAULT NULL
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO active_target_state (
                    id, target_url, is_sandbox, guard_id, active_guard_active, is_verified
                ) VALUES (1, '', 0, NULL, 0, 0);
            """)

            # 2. Guard Generations (Multi-Row: 3/day rate limit tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS guard_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guard_id TEXT NOT NULL,
                    creator_device_hash TEXT NOT NULL,
                    generated_at REAL NOT NULL
                );
            """)

            # 3. Issued Guards Ledger
            conn.execute("""
                CREATE TABLE IF NOT EXISTS issued_guards (
                    guard_id TEXT PRIMARY KEY,
                    issued_at REAL NOT NULL
                );
            """)

            # 4. Burned Guards Tombstone Registry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS burned_guards (
                    guard_id TEXT PRIMARY KEY,
                    burn_reason TEXT NOT NULL,
                    burned_at REAL NOT NULL,
                    creator_device_hash TEXT,
                    offending_device_hash TEXT,
                    bound_host_hash TEXT
                );
            """)
            try:
                conn.execute("ALTER TABLE burned_guards ADD COLUMN offending_device_hash TEXT;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE burned_guards ADD COLUMN bound_host_hash TEXT;")
            except Exception:
                pass

            # 5. Traffic Configuration Profile (Single Row: id = 1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    mode TEXT DEFAULT 'step_ramp',
                    ram_limit_mb INTEGER DEFAULT 500,
                    virtual_users INTEGER DEFAULT 100,
                    duration_sec INTEGER DEFAULT 30,
                    max_error_pct REAL DEFAULT 5.0,
                    p95_ceiling_ms REAL DEFAULT 1500.0,
                    cache_bust INTEGER DEFAULT 1
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO traffic_config (
                    id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust
                ) VALUES (1, 'step_ramp', 500, 100, 30, 5.0, 1500.0, 1);
            """)

            # 6. Journey Steps (Multi-Step Ordered Sequence)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journey_steps (
                    step_id TEXT PRIMARY KEY,
                    step_order INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    headers_json TEXT DEFAULT '{}',
                    body_json TEXT DEFAULT '{}',
                    expected_status INTEGER DEFAULT 200,
                    extract_json_key TEXT DEFAULT ''
                );
            """)

            # 7. Journey Settings (Single Row: id = 1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journey_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    use_journey INTEGER DEFAULT 0,
                    last_dry_run_json TEXT DEFAULT 'null'
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO journey_settings (
                    id, use_journey, last_dry_run_json
                ) VALUES (1, 0, 'null');
            """)

            # 8. Test Runs (Historical load test executions)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    guard_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    target_vus INTEGER NOT NULL,
                    peak_vus INTEGER NOT NULL,
                    duration_sec INTEGER NOT NULL,
                    elapsed_sec INTEGER NOT NULL,
                    peak_rps INTEGER NOT NULL,
                    avg_rps INTEGER NOT NULL,
                    p95_ms REAL NOT NULL,
                    error_pct REAL NOT NULL,
                    total_requests INTEGER NOT NULL,
                    status_2xx INTEGER NOT NULL,
                    status_429 INTEGER NOT NULL,
                    status_5xx INTEGER NOT NULL,
                    bytes_discarded_mb REAL NOT NULL,
                    ram_mb REAL NOT NULL,
                    verdict TEXT NOT NULL,
                    status_label TEXT NOT NULL,
                    knee_vus INTEGER NOT NULL,
                    knee_rps INTEGER NOT NULL,
                    knee_p95_ms REAL NOT NULL,
                    bottleneck_summary TEXT NOT NULL,
                    timeseries_json TEXT NOT NULL,
                    step_metrics_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)

            # Eliminate legacy mock / fake seed runs completely
            conn.execute("""
                DELETE FROM test_runs WHERE run_id IN ('RUN-101', 'RUN-102', 'RUN-103');
            """)
    finally:
        conn.close()


# ==============================================================================
# Database Helper CRUD APIs
# ==============================================================================

# --- Active Target State ---
def db_get_active_target() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM active_target_state WHERE id = 1").fetchone()
        if not row:
            return {
                "target_url": "",
                "is_sandbox": False,
                "guard_id": None,
                "handshake_secret": None,
                "expected_file_sha256": None,
                "creator_device_hash": None,
                "bound_host_hash": None,
                "issued_at": None,
                "expires_at": None,
                "active_guard_active": False,
                "is_verified": False,
                "last_burn_reason": None,
            }
        return {
            "target_url": row["target_url"] or "",
            "is_sandbox": bool(row["is_sandbox"]),
            "guard_id": row["guard_id"],
            "handshake_secret": row["handshake_secret"],
            "expected_file_sha256": row["expected_file_sha256"],
            "creator_device_hash": row["creator_device_hash"],
            "bound_host_hash": row["bound_host_hash"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "active_guard_active": bool(row["active_guard_active"]),
            "is_verified": bool(row["is_verified"]),
            "last_burn_reason": row["last_burn_reason"],
        }
    finally:
        conn.close()


def db_save_active_target(state: Dict[str, Any]) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE active_target_state SET
                    target_url = ?,
                    is_sandbox = ?,
                    guard_id = ?,
                    handshake_secret = ?,
                    expected_file_sha256 = ?,
                    creator_device_hash = ?,
                    bound_host_hash = ?,
                    issued_at = ?,
                    expires_at = ?,
                    active_guard_active = ?,
                    is_verified = ?,
                    last_burn_reason = ?
                WHERE id = 1;
                """,
                (
                    state.get("target_url", ""),
                    1 if state.get("is_sandbox") else 0,
                    state.get("guard_id"),
                    state.get("handshake_secret"),
                    state.get("expected_file_sha256"),
                    state.get("creator_device_hash"),
                    state.get("bound_host_hash"),
                    state.get("issued_at"),
                    state.get("expires_at"),
                    1 if state.get("active_guard_active") else 0,
                    1 if state.get("is_verified") else 0,
                    state.get("last_burn_reason"),
                ),
            )
    finally:
        conn.close()


# --- Guard Generations & Tombstone ---
def db_record_guard_generation(guard_id: str, creator_device_hash: str, generated_at: float) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO guard_generations (guard_id, creator_device_hash, generated_at) VALUES (?, ?, ?);",
                (guard_id, creator_device_hash, generated_at),
            )
            conn.execute(
                "INSERT OR REPLACE INTO issued_guards (guard_id, issued_at) VALUES (?, ?);",
                (guard_id, generated_at),
            )
    finally:
        conn.close()


def db_get_daily_generations_count(creator_device_hash: str, since_timestamp: float) -> int:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM guard_generations WHERE creator_device_hash = ? AND generated_at >= ?;",
            (creator_device_hash, since_timestamp),
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def db_burn_guard(
    guard_id: str,
    burn_reason: str,
    creator_device_hash: Optional[str] = None,
    offending_device_hash: Optional[str] = None,
    bound_host_hash: Optional[str] = None,
) -> Dict[str, Any]:
    now = time.time()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO burned_guards (guard_id, burn_reason, burned_at, creator_device_hash, offending_device_hash, bound_host_hash)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (guard_id, burn_reason, now, creator_device_hash, offending_device_hash, bound_host_hash),
            )
        return {
            "guard_id": guard_id,
            "burn_reason": burn_reason,
            "creator_device_hash": creator_device_hash,
            "offending_device_hash": offending_device_hash,
            "burned_at": now,
        }
    finally:
        conn.close()


def db_is_guard_burned(guard_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not guard_id:
        return None
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM burned_guards WHERE guard_id = ?;", (guard_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def db_get_burned_guards_count() -> int:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM burned_guards;").fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


# --- Traffic Config ---
def db_get_traffic_config() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM traffic_config WHERE id = 1;").fetchone()
        if not row:
            return {
                "mode": "step_ramp",
                "ram_limit_mb": 500,
                "virtual_users": 100,
                "duration_sec": 30,
                "max_error_pct": 5.0,
                "p95_ceiling_ms": 1500.0,
                "cache_bust": 1,
            }
        return {
            "mode": row["mode"] or "step_ramp",
            "ram_limit_mb": int(row["ram_limit_mb"]),
            "virtual_users": int(row["virtual_users"]),
            "duration_sec": int(row["duration_sec"]),
            "max_error_pct": float(row["max_error_pct"]),
            "p95_ceiling_ms": float(row["p95_ceiling_ms"]),
            "cache_bust": int(row["cache_bust"]),
        }
    finally:
        conn.close()


def db_save_traffic_config(config: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE traffic_config SET
                    mode = ?,
                    ram_limit_mb = ?,
                    virtual_users = ?,
                    duration_sec = ?,
                    max_error_pct = ?,
                    p95_ceiling_ms = ?,
                    cache_bust = ?
                WHERE id = 1;
                """,
                (
                    config.get("mode", "step_ramp"),
                    int(config.get("ram_limit_mb", 500)),
                    int(config.get("virtual_users", 100)),
                    int(config.get("duration_sec", 30)),
                    float(config.get("max_error_pct", 5.0)),
                    float(config.get("p95_ceiling_ms", 1500.0)),
                    1 if config.get("cache_bust", 1) else 0,
                ),
            )
        return db_get_traffic_config()
    finally:
        conn.close()


# --- Journey Steps & Settings ---
def db_get_journey() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        settings_row = conn.execute("SELECT * FROM journey_settings WHERE id = 1;").fetchone()
        use_journey = bool(settings_row["use_journey"]) if settings_row else False
        last_dry_run = None
        if settings_row and settings_row["last_dry_run_json"]:
            try:
                last_dry_run = json.loads(settings_row["last_dry_run_json"])
            except Exception:
                last_dry_run = None

        steps_rows = conn.execute("SELECT * FROM journey_steps ORDER BY step_order ASC;").fetchall()
        steps = []
        for r in steps_rows:
            headers = {}
            body = {}
            try:
                if r["headers_json"]:
                    headers = json.loads(r["headers_json"])
            except Exception:
                pass
            try:
                if r["body_json"]:
                    body = json.loads(r["body_json"])
            except Exception:
                pass

            steps.append({
                "step_id": r["step_id"],
                "step_order": r["step_order"],
                "name": r["name"],
                "method": r["method"],
                "path": r["path"],
                "headers": headers,
                "body": body,
                "expected_status": r["expected_status"],
                "extract_json_key": r["extract_json_key"] or "",
            })

        return {
            "use_journey": use_journey,
            "steps": steps,
            "last_dry_run": last_dry_run,
        }
    finally:
        conn.close()


def db_save_journey(use_journey: bool, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE journey_settings SET use_journey = ? WHERE id = 1;",
                (1 if use_journey else 0,),
            )
            conn.execute("DELETE FROM journey_steps;")
            for idx, s in enumerate(steps):
                headers_json = json.dumps(s.get("headers", {}))
                body = s.get("body", {})
                body_json = json.dumps(body) if isinstance(body, (dict, list)) else str(body or "{}")
                step_id = s.get("step_id") or f"step_{idx+1}_{int(time.time()*1000)}"
                conn.execute(
                    """
                    INSERT INTO journey_steps (
                        step_id, step_order, name, method, path, headers_json, body_json, expected_status, extract_json_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        step_id,
                        idx + 1,
                        s.get("name", f"Step {idx+1}"),
                        s.get("method", "GET").upper(),
                        s.get("path", "/"),
                        headers_json,
                        body_json,
                        int(s.get("expected_status", 200)),
                        s.get("extract_json_key", ""),
                    ),
                )
        return db_get_journey()
    finally:
        conn.close()


def db_save_journey_dry_run(dry_run_data: Optional[Dict[str, Any]]) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE journey_settings SET last_dry_run_json = ? WHERE id = 1;",
                (json.dumps(dry_run_data) if dry_run_data else "null",),
            )
    finally:
        conn.close()


# Ensure tables are initialized when this module is imported
init_all_tables()

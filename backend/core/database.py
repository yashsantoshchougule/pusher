"""
Centralized SQLite Database Access Layer for PUSHER Platform
Maintains persistent, per-user partitioned state in backend/pusher_runs.db:
- users (account authentication & credentials)
- user_profiles (scoped profile metadata & defaults)
- active_target_state (scoped target URL & guard handshake)
- guard_generations (rolling 3/day rate limit tracking per user & device)
- issued_guards (ledger of issued guard tokens)
- burned_guards (permanent tombstone registry, global)
- traffic_config (scoped traffic curve & concurrency profile)
- journey_steps (scoped multi-step API journeys)
- journey_settings (scoped journey mode & dry run results)
- test_runs (scoped historical load test executions)
"""

import json
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional
from backend.core.config import settings

DB_PATH = settings.database_path.resolve()

def target_template(url: str) -> str:
    return url.split("#", 1)[0].partition("?")[0]


def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-safe connection to the central SQLite database with Row factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_all_tables() -> None:
    """Initializes all required schema tables and applies migrations."""
    conn = get_db_connection()
    try:
        with conn:
            # 0. Users Account Authentication Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, email, password_hash, full_name, created_at)
                VALUES ('default_test_user', 'dev@pusher.internal', 'default_test_hash', 'Lead Test Architect', datetime('now'));
            """)

            # 1. Active Target State (Scoped by user_id, maintains id=1 for test compatibility)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_target_state (
                    user_id TEXT PRIMARY KEY,
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
                    last_burn_reason TEXT DEFAULT NULL,
                    id INTEGER DEFAULT 1
                );
            """)
            # Check if active_target_state needs migration to user_id primary key
            ats_cols = [r["name"] for r in conn.execute("PRAGMA table_info(active_target_state);").fetchall()]
            if "user_id" not in ats_cols:
                conn.execute("ALTER TABLE active_target_state RENAME TO active_target_state_legacy;")
                conn.execute("""
                    CREATE TABLE active_target_state (
                        user_id TEXT PRIMARY KEY,
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
                        last_burn_reason TEXT DEFAULT NULL,
                        id INTEGER DEFAULT 1
                    );
                """)
                conn.execute("""
                    INSERT INTO active_target_state (
                        user_id, id, target_url, is_sandbox, guard_id, handshake_secret, expected_file_sha256,
                        creator_device_hash, bound_host_hash, issued_at, expires_at, active_guard_active,
                        is_verified, last_burn_reason
                    ) SELECT
                        'default_test_user', id, target_url, is_sandbox, guard_id, handshake_secret, expected_file_sha256,
                        creator_device_hash, bound_host_hash, issued_at, expires_at, active_guard_active,
                        is_verified, last_burn_reason
                    FROM active_target_state_legacy;
                """)
                conn.execute("DROP TABLE active_target_state_legacy;")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO active_target_state (
                        user_id, id, target_url, is_sandbox, guard_id, active_guard_active, is_verified
                    ) VALUES ('default_test_user', 1, '', 0, NULL, 0, 0);
                """)
            if "requires_target_query" not in ats_cols:
                conn.execute("ALTER TABLE active_target_state ADD COLUMN requires_target_query INTEGER DEFAULT 0;")

            # 2. Guard Generations (Multi-Row: 3/day rate limit tracking per user)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS guard_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guard_id TEXT NOT NULL,
                    creator_device_hash TEXT NOT NULL,
                    generated_at REAL NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'default_test_user'
                );
            """)
            gg_cols = [r["name"] for r in conn.execute("PRAGMA table_info(guard_generations);").fetchall()]
            if "user_id" not in gg_cols:
                conn.execute("ALTER TABLE guard_generations ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_test_user';")

            # 3. Issued Guards Ledger
            conn.execute("""
                CREATE TABLE IF NOT EXISTS issued_guards (
                    guard_id TEXT PRIMARY KEY,
                    issued_at REAL NOT NULL
                );
            """)

            # 4. Burned Guards Tombstone Registry (GLOBAL: permanently burns guard IDs for everyone)
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

            # 5. Traffic Configuration Profile (Scoped by user_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_config (
                    user_id TEXT PRIMARY KEY,
                    mode TEXT DEFAULT 'step_ramp',
                    ram_limit_mb INTEGER DEFAULT 500,
                    virtual_users INTEGER DEFAULT 100,
                    duration_sec INTEGER DEFAULT 30,
                    max_error_pct REAL DEFAULT 5.0,
                    p95_ceiling_ms REAL DEFAULT 1500.0,
                    cache_bust INTEGER DEFAULT 1,
                    id INTEGER DEFAULT 1
                );
            """)
            tc_cols = [r["name"] for r in conn.execute("PRAGMA table_info(traffic_config);").fetchall()]
            if "user_id" not in tc_cols:
                conn.execute("ALTER TABLE traffic_config RENAME TO traffic_config_legacy;")
                conn.execute("""
                    CREATE TABLE traffic_config (
                        user_id TEXT PRIMARY KEY,
                        mode TEXT DEFAULT 'step_ramp',
                        ram_limit_mb INTEGER DEFAULT 500,
                        virtual_users INTEGER DEFAULT 100,
                        duration_sec INTEGER DEFAULT 30,
                        max_error_pct REAL DEFAULT 5.0,
                        p95_ceiling_ms REAL DEFAULT 1500.0,
                        cache_bust INTEGER DEFAULT 1,
                        id INTEGER DEFAULT 1
                    );
                """)
                conn.execute("""
                    INSERT INTO traffic_config (
                        user_id, id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust
                    ) SELECT
                        'default_test_user', id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust
                    FROM traffic_config_legacy;
                """)
                conn.execute("DROP TABLE traffic_config_legacy;")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO traffic_config (
                        user_id, id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust
                    ) VALUES ('default_test_user', 1, 'step_ramp', 500, 100, 30, 5.0, 1500.0, 1);
                """)

            # 6. Journey Steps (Multi-Step Ordered Sequence scoped by user_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journey_steps (
                    user_id TEXT NOT NULL DEFAULT 'default_test_user',
                    step_id TEXT NOT NULL,
                    step_order INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    headers_json TEXT DEFAULT '{}',
                    body_json TEXT DEFAULT '{}',
                    expected_status INTEGER DEFAULT 200,
                    extract_json_key TEXT DEFAULT '',
                    PRIMARY KEY (user_id, step_id)
                );
            """)
            jstep_cols = [r["name"] for r in conn.execute("PRAGMA table_info(journey_steps);").fetchall()]
            if "user_id" not in jstep_cols:
                conn.execute("ALTER TABLE journey_steps RENAME TO journey_steps_legacy;")
                conn.execute("""
                    CREATE TABLE journey_steps (
                        user_id TEXT NOT NULL DEFAULT 'default_test_user',
                        step_id TEXT NOT NULL,
                        step_order INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        headers_json TEXT DEFAULT '{}',
                        body_json TEXT DEFAULT '{}',
                        expected_status INTEGER DEFAULT 200,
                        extract_json_key TEXT DEFAULT '',
                        PRIMARY KEY (user_id, step_id)
                    );
                """)
                conn.execute("""
                    INSERT INTO journey_steps (
                        user_id, step_id, step_order, name, method, path, headers_json, body_json, expected_status, extract_json_key
                    ) SELECT
                        'default_test_user', step_id, step_order, name, method, path, headers_json, body_json, expected_status, extract_json_key
                    FROM journey_steps_legacy;
                """)
                conn.execute("DROP TABLE journey_steps_legacy;")
            if "runtime_fields_json" not in jstep_cols:
                conn.execute("ALTER TABLE journey_steps ADD COLUMN runtime_fields_json TEXT;")

            # 7. Journey Settings (Scoped by user_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journey_settings (
                    user_id TEXT PRIMARY KEY,
                    use_journey INTEGER DEFAULT 0,
                    last_dry_run_json TEXT DEFAULT 'null',
                    id INTEGER DEFAULT 1
                );
            """)
            js_cols = [r["name"] for r in conn.execute("PRAGMA table_info(journey_settings);").fetchall()]
            if "user_id" not in js_cols:
                conn.execute("ALTER TABLE journey_settings RENAME TO journey_settings_legacy;")
                conn.execute("""
                    CREATE TABLE journey_settings (
                        user_id TEXT PRIMARY KEY,
                        use_journey INTEGER DEFAULT 0,
                        last_dry_run_json TEXT DEFAULT 'null',
                        id INTEGER DEFAULT 1
                    );
                """)
                conn.execute("""
                    INSERT INTO journey_settings (user_id, id, use_journey, last_dry_run_json)
                    SELECT 'default_test_user', id, use_journey, last_dry_run_json FROM journey_settings_legacy;
                """)
                conn.execute("DROP TABLE journey_settings_legacy;")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO journey_settings (user_id, id, use_journey, last_dry_run_json)
                    VALUES ('default_test_user', 1, 0, 'null');
                """)

            # 8. Test Runs (Historical load test executions scoped by user_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_runs (
                    run_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default_test_user',
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
            tr_cols = [r["name"] for r in conn.execute("PRAGMA table_info(test_runs);").fetchall()]
            if "user_id" not in tr_cols:
                conn.execute("ALTER TABLE test_runs ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_test_user';")
            if "metrics_scope" not in tr_cols:
                conn.execute("ALTER TABLE test_runs ADD COLUMN metrics_scope TEXT NOT NULL DEFAULT 'legacy_window';")
            if "capacity_checked" not in tr_cols:
                conn.execute("ALTER TABLE test_runs ADD COLUMN capacity_checked INTEGER NOT NULL DEFAULT 0;")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS test_runs_owner_order ON test_runs(user_id, created_at DESC, run_id DESC)"
            )

            # 9. User Profiles (Persistent Profile State)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_key TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    full_name TEXT DEFAULT '',
                    username TEXT DEFAULT '',
                    role_title TEXT DEFAULT '',
                    organization TEXT DEFAULT '',
                    github_username TEXT DEFAULT '',
                    avatar_url TEXT DEFAULT '',
                    bio_notes TEXT DEFAULT '',
                    default_ram_ceiling_mb INTEGER DEFAULT 500,
                    updated_at TEXT NOT NULL,
                    user_id TEXT
                );
            """)
            up_cols = [r["name"] for r in conn.execute("PRAGMA table_info(user_profiles);").fetchall()]
            if "user_id" not in up_cols:
                try:
                    conn.execute("ALTER TABLE user_profiles ADD COLUMN user_id TEXT;")
                except Exception:
                    pass
            conn.execute("""
                INSERT OR IGNORE INTO user_profiles (
                    user_key, email, full_name, username, role_title, organization, github_username, avatar_url, bio_notes, default_ram_ceiling_mb, updated_at, user_id
                ) VALUES (
                    'default_test_user', 'dev@pusher.internal', 'Lead Test Architect', 'pusher_admin', 'Performance Engineer', 'Pusher Ops', 'pusher-eng', '', 'Hardware load and knee-curve benchmarking lead.', 500, datetime('now'), 'default_test_user'
                );
            """)
            conn.execute("""
                INSERT OR IGNORE INTO user_profiles (
                    user_key, email, full_name, username, role_title, organization, github_username, avatar_url, bio_notes, default_ram_ceiling_mb, updated_at, user_id
                ) VALUES (
                    'default_user', 'dev@pusher.internal', 'Lead Test Architect', 'pusher_admin', 'Performance Engineer', 'Pusher Ops', 'pusher-eng', '', 'Hardware load and knee-curve benchmarking lead.', 500, datetime('now'), 'default_user'
                );
            """)

    finally:
        conn.close()


# ==============================================================================
# Database Helper CRUD APIs
# ==============================================================================

# --- User Account CRUD ---
def db_create_user(user_id: str, email: str, password_hash: str, full_name: str = "") -> Dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    email_clean = email.lower().strip()
    name_clean = full_name.strip()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO users (user_id, email, password_hash, full_name, created_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (user_id, email_clean, password_hash, name_clean, now),
            )
            # Auto-seed initial user_profiles record for this account
            conn.execute(
                """
                INSERT OR IGNORE INTO user_profiles (
                    user_key, email, full_name, username, role_title, organization, github_username, avatar_url, bio_notes, default_ram_ceiling_mb, updated_at, user_id
                ) VALUES (?, ?, ?, ?, '', '', '', '', '', 500, ?, ?);
                """,
                (user_id, email_clean, name_clean, email_clean.split("@")[0], now, user_id),
            )
            # Auto-seed initial active target state and traffic config for this account
            conn.execute(
                """
                INSERT OR IGNORE INTO active_target_state (
                    user_id, target_url, is_sandbox, guard_id, active_guard_active, is_verified, id
                ) VALUES (?, '', 0, NULL, 0, 0, 1);
                """,
                (user_id,),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO traffic_config (
                    user_id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust, id
                ) VALUES (?, 'step_ramp', 500, 100, 30, 5.0, 1500.0, 1, 1);
                """,
                (user_id,),
            )
        return {
            "user_id": user_id,
            "email": email_clean,
            "full_name": name_clean,
            "created_at": now,
        }
    finally:
        conn.close()


def db_get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?);", (email.strip(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def db_get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?;", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# --- Active Target State (Scoped by user_id) ---
def db_get_active_target(user_id: str = "default_test_user") -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM active_target_state WHERE user_id = ?;", (user_id,)
        ).fetchone()
        if not row and user_id in ("default_test_user", "default_user"):
            row = conn.execute("SELECT * FROM active_target_state WHERE id = 1 LIMIT 1;").fetchone()

        if not row:
            return {
                "target_url": "",
                "requires_target_query": False,
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
            "target_url": target_template(row["target_url"] or ""),
            "requires_target_query": bool(row["requires_target_query"])
            or bool((row["target_url"] or "").split("#", 1)[0].partition("?")[2]),
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


def db_save_active_target(state: Dict[str, Any], user_id: str = "default_test_user") -> None:
    url = state.get("target_url") or ""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO active_target_state (
                    user_id, target_url, is_sandbox, guard_id, handshake_secret, expected_file_sha256,
                    creator_device_hash, bound_host_hash, issued_at, expires_at, active_guard_active,
                    is_verified, last_burn_reason, requires_target_query, id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    target_url = excluded.target_url,
                    is_sandbox = excluded.is_sandbox,
                    guard_id = excluded.guard_id,
                    handshake_secret = excluded.handshake_secret,
                    expected_file_sha256 = excluded.expected_file_sha256,
                    creator_device_hash = excluded.creator_device_hash,
                    bound_host_hash = excluded.bound_host_hash,
                    issued_at = excluded.issued_at,
                    expires_at = excluded.expires_at,
                    active_guard_active = excluded.active_guard_active,
                    is_verified = excluded.is_verified,
                    requires_target_query = excluded.requires_target_query,
                    last_burn_reason = excluded.last_burn_reason;
                """,
                (
                    user_id,
                    target_template(url),
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
                    int(bool(state.get("requires_target_query") or url.split("#", 1)[0].partition("?")[2])),
                ),
            )
    finally:
        conn.close()


# --- Guard Generations & Tombstone ---
def db_record_guard_generation(
    guard_id: str,
    creator_device_hash: str,
    generated_at: float,
    user_id: str = "default_test_user"
) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO guard_generations (guard_id, creator_device_hash, generated_at, user_id) VALUES (?, ?, ?, ?);",
                (guard_id, creator_device_hash, generated_at, user_id),
            )
            conn.execute(
                "INSERT OR REPLACE INTO issued_guards (guard_id, issued_at) VALUES (?, ?);",
                (guard_id, generated_at),
            )
    finally:
        conn.close()


def db_get_daily_generations_count(
    creator_device_hash: str,
    cutoff: float,
    user_id: str = "default_test_user"
) -> int:
    conn = get_db_connection()
    try:
        # Check by user_id or device hash
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM guard_generations
            WHERE (creator_device_hash = ? OR user_id = ?) AND generated_at >= ?;
            """,
            (creator_device_hash, user_id, cutoff),
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def db_burn_guard(
    guard_id: str,
    burn_reason: str,
    creator_device_hash: Optional[str] = None,
    offending_device_hash: Optional[str] = None,
    bound_host_hash: Optional[str] = None
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


# --- Traffic Config (Scoped by user_id) ---
def db_get_traffic_config(user_id: str = "default_test_user") -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM traffic_config WHERE user_id = ?;", (user_id,)
        ).fetchone()
        if not row and user_id in ("default_test_user", "default_user"):
            row = conn.execute("SELECT * FROM traffic_config WHERE id = 1 LIMIT 1;").fetchone()

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


def db_save_traffic_config(config: Dict[str, Any], user_id: str = "default_test_user") -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO traffic_config (
                    user_id, mode, ram_limit_mb, virtual_users, duration_sec, max_error_pct, p95_ceiling_ms, cache_bust, id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    ram_limit_mb = excluded.ram_limit_mb,
                    virtual_users = excluded.virtual_users,
                    duration_sec = excluded.duration_sec,
                    max_error_pct = excluded.max_error_pct,
                    p95_ceiling_ms = excluded.p95_ceiling_ms,
                    cache_bust = excluded.cache_bust;
                """,
                (
                    user_id,
                    config.get("mode", "step_ramp"),
                    int(config.get("ram_limit_mb", 500)),
                    int(config.get("virtual_users", 100)),
                    int(config.get("duration_sec", 30)),
                    float(config.get("max_error_pct", 5.0)),
                    float(config.get("p95_ceiling_ms", 1500.0)),
                    1 if config.get("cache_bust", 1) else 0,
                ),
            )
        return db_get_traffic_config(user_id)
    finally:
        conn.close()


# --- Journey Steps & Settings (Scoped by user_id) ---
def journey_step_metadata(steps: list[dict]) -> list[dict]:
    if not isinstance(steps, list):
        return []
    return [
        {**step, "path": step["path"].partition("?")[0]} if isinstance(step.get("path"), str) else step
        for step in steps if isinstance(step, dict)
    ]


def _journey_inputs(step: dict) -> tuple[dict, dict]:
    safe_headers = {}
    required_headers = set(step.get("required_headers", []))
    headers = step.get("headers") or {}
    if isinstance(headers, dict):
        for name, value in headers.items():
            if isinstance(value, str) and (
                (name.lower() == "content-type" and value in {
                    "application/json", "application/x-www-form-urlencoded", "application/xml", "text/plain",
                })
                or re.fullmatch(r"(?:Bearer )?\{\{[A-Za-z0-9_.-]+\}\}", value)
            ):
                safe_headers[name] = value
                required_headers.discard(name)
            else:
                required_headers.add(name)
    return safe_headers, {
        "required_headers": sorted(required_headers),
        "requires_body": bool(step.get("requires_body")) or step.get("body") not in (None, ""),
        "requires_query": bool(step.get("requires_query")) or bool(step.get("path", "/").partition("?")[2]),
    }


def _stored_journey_inputs(row) -> dict:
    raw_headers = row["headers_json"] or "{}"
    try:
        headers = json.loads(raw_headers)
    except ValueError:
        headers = None
    if row["runtime_fields_json"] is not None:
        fields = json.loads(row["runtime_fields_json"])
        fields["requires_query"] = fields.get("requires_query", False) or bool(row["path"].partition("?")[2])
        return {"headers": headers, "body": None, **fields}

    raw_body = row["body_json"]
    try:
        body = json.loads(raw_body) if raw_body else None
    except ValueError:
        body = raw_body
    safe_headers, runtime_fields = _journey_inputs({"headers": headers, "body": body, "path": row["path"]})
    # Keep malformed legacy headers invalid without returning their raw values.
    return {"headers": safe_headers if isinstance(headers, dict) else [], "body": None, **runtime_fields}


def _dry_run_history(results):
    if not results:
        return None
    return [
        {key: value for key, value in step.items() if key != "error"}
        for step in journey_step_metadata(results)
    ]


def scrub_legacy_journey_inputs() -> None:
    """Remove old request inputs during offline SQLite maintenance."""
    conn = get_db_connection()
    try:
        conn.execute("PRAGMA secure_delete=ON;")
        with conn:
            for row in conn.execute(
                "SELECT user_id, target_url, requires_target_query FROM active_target_state WHERE instr(target_url, '?') > 0;"
            ).fetchall():
                url = row["target_url"]
                conn.execute(
                    "UPDATE active_target_state SET target_url = ?, requires_target_query = ? WHERE user_id = ?;",
                    (target_template(url), int(bool(row["requires_target_query"] or url.split("#", 1)[0].partition("?")[2])),
                     row["user_id"]),
                )
            for row in conn.execute("SELECT run_id, target_url FROM test_runs WHERE instr(target_url, '?') > 0;").fetchall():
                conn.execute("UPDATE test_runs SET target_url = ? WHERE run_id = ?;",
                             (target_template(row["target_url"]), row["run_id"]))
            rows = conn.execute(
                "SELECT * FROM journey_steps WHERE runtime_fields_json IS NULL OR instr(path, '?') > 0;"
            ).fetchall()
            for row in rows:
                safe = _stored_journey_inputs(row)
                headers, body = safe.pop("headers"), safe.pop("body")
                conn.execute(
                    """UPDATE journey_steps SET headers_json = ?, body_json = ?, runtime_fields_json = ?, path = ?
                    WHERE user_id = ? AND step_id = ?;""",
                    (json.dumps(headers), json.dumps(body), json.dumps(safe),
                     row["path"].partition("?")[0], row["user_id"], row["step_id"]),
                )
            for row in conn.execute("SELECT user_id, last_dry_run_json FROM journey_settings;").fetchall():
                try:
                    summary = _dry_run_history(json.loads(row["last_dry_run_json"] or "null"))
                except (ValueError, TypeError, AttributeError):
                    summary = None
                conn.execute(
                    "UPDATE journey_settings SET last_dry_run_json = ? WHERE user_id = ?;",
                    (json.dumps(summary), row["user_id"]),
                )
            for row in conn.execute(
                "SELECT run_id, step_metrics_json FROM test_runs WHERE instr(step_metrics_json, '?') > 0;"
            ).fetchall():
                try:
                    metrics = journey_step_metadata(json.loads(row["step_metrics_json"]))
                except (ValueError, TypeError, AttributeError):
                    continue
                conn.execute("UPDATE test_runs SET step_metrics_json = ? WHERE run_id = ?;",
                             (json.dumps(metrics), row["run_id"]))
        conn.execute("VACUUM;")
        if conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()[0]:
            raise RuntimeError("Close all backend SQLite connections before retrying the journey scrub.")
    finally:
        conn.close()


def db_get_journey(user_id: str = "default_test_user") -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        settings_row = conn.execute(
            "SELECT * FROM journey_settings WHERE user_id = ?;", (user_id,)
        ).fetchone()
        if not settings_row and user_id in ("default_test_user", "default_user"):
            settings_row = conn.execute("SELECT * FROM journey_settings WHERE id = 1 LIMIT 1;").fetchone()

        use_journey = bool(settings_row["use_journey"]) if settings_row else False
        last_dry_run = None
        if settings_row and settings_row["last_dry_run_json"]:
            try:
                last_dry_run = _dry_run_history(json.loads(settings_row["last_dry_run_json"]))
            except Exception:
                last_dry_run = None

        step_rows = conn.execute(
            "SELECT * FROM journey_steps WHERE user_id = ? ORDER BY step_order ASC;", (user_id,)
        ).fetchall()
        steps = []
        for r in step_rows:
            steps.append({
                "step_id": r["step_id"],
                "step_order": r["step_order"],
                "name": r["name"],
                "method": r["method"],
                "path": r["path"].partition("?")[0],
                **_stored_journey_inputs(r),
                "expected_status": r["expected_status"],
                "extract_json_key": r["extract_json_key"],
            })
        return {
            "use_journey": use_journey,
            "steps": steps,
            "last_dry_run": last_dry_run,
        }
    finally:
        conn.close()


def db_save_journey(
    use_journey: bool,
    steps: List[Dict[str, Any]],
    user_id: str = "default_test_user"
) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO journey_settings (user_id, use_journey, last_dry_run_json, id)
                VALUES (?, ?, 'null', 1)
                ON CONFLICT(user_id) DO UPDATE SET use_journey = excluded.use_journey;
                """,
                (user_id, 1 if use_journey else 0),
            )
            conn.execute("DELETE FROM journey_steps WHERE user_id = ?;", (user_id,))
            for idx, s in enumerate(steps):
                headers, runtime_fields = _journey_inputs(s)
                step_id = s.get("step_id") or f"step_{idx+1}_{int(time.time()*1000)}"
                conn.execute(
                    """
                    INSERT INTO journey_steps (
                        user_id, step_id, step_order, name, method, path, headers_json, body_json,
                        expected_status, extract_json_key, runtime_fields_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'null', ?, ?, ?);
                    """,
                    (
                        user_id,
                        step_id,
                        idx + 1,
                        s.get("name", f"Step {idx+1}"),
                        s.get("method", "GET").upper(),
                        s.get("path", "/").partition("?")[0],
                        json.dumps(headers),
                        int(s.get("expected_status", 200)),
                        s.get("extract_json_key", ""),
                        json.dumps(runtime_fields),
                    ),
                )
        return db_get_journey(user_id)
    finally:
        conn.close()


def db_save_journey_dry_run(
    dry_run_data: Optional[List[Dict[str, Any]]],
    user_id: str = "default_test_user"
) -> None:
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO journey_settings (user_id, use_journey, last_dry_run_json, id)
                VALUES (?, 0, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET last_dry_run_json = excluded.last_dry_run_json;
                """,
                (user_id, json.dumps(_dry_run_history(dry_run_data))),
            )
    finally:
        conn.close()


# --- User Profiles (Scoped by user_key / user_id) ---
def db_get_profile(user_key: str = "default_test_user") -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_key = ? OR user_id = ?;", (user_key, user_key)
        ).fetchone()
        if not row and user_key in ("default_test_user", "default_user"):
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE user_key IN ('default_test_user', 'default_user') LIMIT 1;"
            ).fetchone()
        if not row:
            return None
        return {
            "user_key": row["user_key"],
            "user_id": row["user_id"] or row["user_key"],
            "email": row["email"],
            "full_name": row["full_name"] or "",
            "username": row["username"] or "",
            "role_title": row["role_title"] or "",
            "organization": row["organization"] or "",
            "github_username": row["github_username"] or "",
            "avatar_url": row["avatar_url"] or "",
            "bio_notes": row["bio_notes"] or "",
            "default_ram_ceiling_mb": int(row["default_ram_ceiling_mb"] or 500),
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def db_save_profile(user_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        with conn:
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                """
                INSERT INTO user_profiles (
                    user_key, user_id, email, full_name, username, role_title, organization, github_username, avatar_url, bio_notes, default_ram_ceiling_mb, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    user_id = excluded.user_id,
                    email = excluded.email,
                    full_name = excluded.full_name,
                    username = excluded.username,
                    role_title = excluded.role_title,
                    organization = excluded.organization,
                    github_username = excluded.github_username,
                    avatar_url = excluded.avatar_url,
                    bio_notes = excluded.bio_notes,
                    default_ram_ceiling_mb = excluded.default_ram_ceiling_mb,
                    updated_at = excluded.updated_at;
                """,
                (
                    user_key,
                    user_key,
                    data.get("email", "dev@pusher.internal"),
                    data.get("full_name", ""),
                    data.get("username", ""),
                    data.get("role_title", ""),
                    data.get("organization", ""),
                    data.get("github_username", ""),
                    data.get("avatar_url", ""),
                    data.get("bio_notes", ""),
                    int(data.get("default_ram_ceiling_mb", 500)),
                    now_iso,
                ),
            )
        profile = db_get_profile(user_key)
        return profile or {}
    finally:
        conn.close()


# Ensure tables are initialized and migrated when this module is imported
init_all_tables()

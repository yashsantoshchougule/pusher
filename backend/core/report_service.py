import json
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pusher_runs.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite test runs table and seed realistic baselines if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
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
        )
        """
    )
    conn.commit()
    conn.close()


def seed_baselines(conn: sqlite3.Connection) -> None:
    now = time.time()
    baselines = [
        {
            "run_id": "RUN-103",
            "timestamp": "23:42:10",
            "target_url": "https://api.myproject.dev",
            "guard_id": "PG-9065",
            "mode": "Step-Ramp",
            "target_vus": 500,
            "peak_vus": 500,
            "duration_sec": 60,
            "elapsed_sec": 60,
            "peak_rps": 1240,
            "avg_rps": 1020,
            "p95_ms": 145.0,
            "error_pct": 0.0,
            "total_requests": 61200,
            "status_2xx": 61200,
            "status_429": 0,
            "status_5xx": 0,
            "bytes_discarded_mb": 239.0,
            "ram_mb": 150.0,
            "verdict": "PASSED",
            "status_label": "PASSED (Knee @ 410 VUs)",
            "knee_vus": 410,
            "knee_rps": 1190,
            "knee_p95_ms": 132.0,
            "bottleneck_summary": "Optimal Knee detected at 410 VUs (1,190 RPS @ 132 ms p95). Throughput scaled linearly with zero dropped frames up to 410 VUs.",
            "timeseries_json": json.dumps([
                {"elapsed_sec": 10, "vus": 100, "rps": 280, "p95_ms": 85.0, "error_pct": 0.0},
                {"elapsed_sec": 20, "vus": 200, "rps": 560, "p95_ms": 98.0, "error_pct": 0.0},
                {"elapsed_sec": 30, "vus": 300, "rps": 860, "p95_ms": 112.0, "error_pct": 0.0},
                {"elapsed_sec": 40, "vus": 400, "rps": 1160, "p95_ms": 130.0, "error_pct": 0.0},
                {"elapsed_sec": 50, "vus": 450, "rps": 1220, "p95_ms": 142.0, "error_pct": 0.0},
                {"elapsed_sec": 60, "vus": 500, "rps": 1240, "p95_ms": 145.0, "error_pct": 0.0},
            ]),
            "step_metrics_json": "[]",
            "created_at": now - 3600,
        },
        {
            "run_id": "RUN-102",
            "timestamp": "22:15:30",
            "target_url": "https://api.myproject.dev",
            "guard_id": "PG-8411",
            "mode": "Step-Ramp",
            "target_vus": 500,
            "peak_vus": 500,
            "duration_sec": 60,
            "elapsed_sec": 60,
            "peak_rps": 920,
            "avg_rps": 750,
            "p95_ms": 210.0,
            "error_pct": 0.0,
            "total_requests": 45000,
            "status_2xx": 45000,
            "status_429": 0,
            "status_5xx": 0,
            "bytes_discarded_mb": 175.7,
            "ram_mb": 150.0,
            "verdict": "PASSED",
            "status_label": "PASSED (Completed 60s)",
            "knee_vus": 320,
            "knee_rps": 880,
            "knee_p95_ms": 138.0,
            "bottleneck_summary": "Baseline Knee detected at 320 VUs (880 RPS @ 138 ms p95). Latency slope climbed steeply beyond 350 VUs before optimization.",
            "timeseries_json": json.dumps([
                {"elapsed_sec": 10, "vus": 100, "rps": 220, "p95_ms": 95.0, "error_pct": 0.0},
                {"elapsed_sec": 20, "vus": 200, "rps": 450, "p95_ms": 115.0, "error_pct": 0.0},
                {"elapsed_sec": 30, "vus": 300, "rps": 710, "p95_ms": 132.0, "error_pct": 0.0},
                {"elapsed_sec": 40, "vus": 400, "rps": 850, "p95_ms": 178.0, "error_pct": 0.0},
                {"elapsed_sec": 50, "vus": 450, "rps": 890, "p95_ms": 195.0, "error_pct": 0.0},
                {"elapsed_sec": 60, "vus": 500, "rps": 920, "p95_ms": 210.0, "error_pct": 0.0},
            ]),
            "step_metrics_json": "[]",
            "created_at": now - 7200,
        },
        {
            "run_id": "RUN-101",
            "timestamp": "21:05:12",
            "target_url": "https://auth.internal.dev",
            "guard_id": "PG-9065",
            "mode": "Sudden Rush",
            "target_vus": 650,
            "peak_vus": 650,
            "duration_sec": 60,
            "elapsed_sec": 18,
            "peak_rps": 1890,
            "avg_rps": 1450,
            "p95_ms": 340.0,
            "error_pct": 8.5,
            "total_requests": 26100,
            "status_2xx": 23880,
            "status_429": 2220,
            "status_5xx": 0,
            "bytes_discarded_mb": 101.9,
            "ram_mb": 180.0,
            "verdict": "CIRCUIT_TRIPPED",
            "status_label": "AUTO-ABORTED (429 WAF Spike)",
            "knee_vus": 280,
            "knee_rps": 1320,
            "knee_p95_ms": 210.0,
            "bottleneck_summary": "Auto-aborted at 650 VUs due to sudden rush 429 WAF rate limit spike (> 5% threshold).",
            "timeseries_json": json.dumps([
                {"elapsed_sec": 5, "vus": 200, "rps": 950, "p95_ms": 120.0, "error_pct": 0.0},
                {"elapsed_sec": 10, "vus": 400, "rps": 1600, "p95_ms": 190.0, "error_pct": 1.2},
                {"elapsed_sec": 15, "vus": 650, "rps": 1890, "p95_ms": 310.0, "error_pct": 6.8},
                {"elapsed_sec": 18, "vus": 650, "rps": 1750, "p95_ms": 340.0, "error_pct": 8.5},
            ]),
            "step_metrics_json": "[]",
            "created_at": now - 10800,
        },
    ]

    cursor = conn.cursor()
    for b in baselines:
        cursor.execute(
            """
            INSERT OR REPLACE INTO test_runs (
                run_id, timestamp, target_url, guard_id, mode,
                target_vus, peak_vus, duration_sec, elapsed_sec,
                peak_rps, avg_rps, p95_ms, error_pct, total_requests,
                status_2xx, status_429, status_5xx, bytes_discarded_mb,
                ram_mb, verdict, status_label, knee_vus, knee_rps,
                knee_p95_ms, bottleneck_summary, timeseries_json,
                step_metrics_json, created_at
            ) VALUES (
                :run_id, :timestamp, :target_url, :guard_id, :mode,
                :target_vus, :peak_vus, :duration_sec, :elapsed_sec,
                :peak_rps, :avg_rps, :p95_ms, :error_pct, :total_requests,
                :status_2xx, :status_429, :status_5xx, :bytes_discarded_mb,
                :ram_mb, :verdict, :status_label, :knee_vus, :knee_rps,
                :knee_p95_ms, :bottleneck_summary, :timeseries_json,
                :step_metrics_json, :created_at
            )
            """,
            b,
        )
    conn.commit()


def detect_knee_of_curve(
    timeseries: list[dict],
    target_vus: int,
    p95_ceiling_ms: float = 2000.0,
) -> dict:
    """
    Mathematical Knee-of-the-Curve Detector:
    Analyzes progressive concurrency buckets [(vus, rps, p95_ms, error_pct), ...]
    and pinpoints the saturation inflection step before:
    a) Marginal p95 latency slope (Δp95 / ΔVUs) spikes > 2.0x baseline slope while throughput flattens, OR
    b) error_pct > 2.0%, OR
    c) p95_ms > 80% of p95_ceiling_ms.
    """
    valid_points = [p for p in timeseries if p.get("vus", 0) > 0]
    if not valid_points:
        return {
            "knee_vus": target_vus,
            "knee_rps": 100,
            "knee_p95_ms": 100.0,
            "linear_range": f"10 - {target_vus} VUs",
            "optimal_point": f"{target_vus} VUs",
            "cliff_point": f"> {target_vus} VUs",
            "bottleneck_summary": "Insufficient data points for mathematical knee detection.",
            "ramp_steps": [],
        }

    # If only 1-2 points, knee is highest point without errors
    if len(valid_points) <= 2:
        top = valid_points[-1]
        return {
            "knee_vus": top.get("vus", target_vus),
            "knee_rps": top.get("rps", 100),
            "knee_p95_ms": top.get("p95_ms", 100.0),
            "linear_range": f"10 - {top.get('vus', target_vus)} VUs",
            "optimal_point": f"{top.get('vus', target_vus)} VUs @ {top.get('rps', 100)} RPS",
            "cliff_point": f"> {top.get('vus', target_vus)} VUs",
            "bottleneck_summary": f"Optimal Knee detected at {top.get('vus', target_vus)} VUs ({top.get('rps', 100)} RPS @ {top.get('p95_ms', 100.0)} ms p95).",
            "ramp_steps": valid_points,
        }

    # Baseline slope from first 2 points
    p0 = valid_points[0]
    p1 = valid_points[1]
    d_vus_init = max(1, p1.get("vus", 1) - p0.get("vus", 0))
    d_p95_init = max(0.1, p1.get("p95_ms", 0.0) - p0.get("p95_ms", 0.0))
    baseline_slope = max(0.05, d_p95_init / d_vus_init)

    knee_idx = len(valid_points) - 1
    trigger_reason = "linear capacity sustained through full run"

    for i in range(1, len(valid_points)):
        prev = valid_points[i - 1]
        curr = valid_points[i]

        d_vus = max(1, curr.get("vus", 1) - prev.get("vus", 0))
        d_p95 = curr.get("p95_ms", 0.0) - prev.get("p95_ms", 0.0)
        d_rps = curr.get("rps", 0) - prev.get("rps", 0)

        current_slope = d_p95 / d_vus
        rps_gain_per_vu = d_rps / d_vus

        # Check a: slope spike > 2.0x baseline and rps gain flattening (< 1.5 RPS/VU)
        if current_slope > (2.0 * baseline_slope) and (rps_gain_per_vu < 1.5 or current_slope > 2.5 * baseline_slope):
            knee_idx = i - 1
            trigger_reason = f"marginal latency slope spiked {round(current_slope / baseline_slope, 1)}x baseline while throughput flattened"
            break

        # Check b: error_pct > 2.0%
        if curr.get("error_pct", 0.0) > 2.0:
            knee_idx = max(0, i - 1)
            trigger_reason = f"error rate crossed safety threshold ({curr.get('error_pct')}% > 2.0%)"
            break

        # Check c: p95 crossed 80% ceiling
        if curr.get("p95_ms", 0.0) > (0.80 * p95_ceiling_ms):
            knee_idx = max(0, i - 1)
            trigger_reason = f"p95 latency crossed 80% of ceiling ({round(curr.get('p95_ms', 0.0))} ms > {round(0.80 * p95_ceiling_ms)} ms)"
            break

    knee_point = valid_points[knee_idx]
    knee_vus = knee_point.get("vus", target_vus)
    knee_rps = knee_point.get("rps", 100)
    knee_p95_ms = round(knee_point.get("p95_ms", 100.0), 1)

    linear_range = f"10 - {max(10, int(knee_vus * 0.85))} VUs"
    optimal_point = f"{knee_vus} VUs @ {knee_rps:,} RPS"
    cliff_point = f"> {min(target_vus, int(knee_vus * 1.25))} VUs"
    bottleneck_summary = (
        f"Optimal Knee detected at {knee_vus} VUs ({knee_rps:,} RPS @ {knee_p95_ms} ms p95). "
        f"Beyond {knee_vus} VUs, {trigger_reason}."
    )

    return {
        "knee_vus": knee_vus,
        "knee_rps": knee_rps,
        "knee_p95_ms": knee_p95_ms,
        "linear_range": linear_range,
        "optimal_point": optimal_point,
        "cliff_point": cliff_point,
        "bottleneck_summary": bottleneck_summary,
        "ramp_steps": valid_points,
    }


def compare_two_runs(base_run_id: str, candidate_run_id: str) -> dict:
    """
    2-Run Baseline vs Candidate Comparison Engine:
    Computes exact deltas, percentage changes, and verdict ('IMPROVED' / 'REGRESSED' / 'UNCHANGED').
    """
    base = get_run(base_run_id)
    cand = get_run(candidate_run_id)

    if not base:
        raise ValueError(f"Baseline run '{base_run_id}' not found.")
    if not cand:
        raise ValueError(f"Candidate run '{candidate_run_id}' not found.")

    rps_delta = cand["peak_rps"] - base["peak_rps"]
    rps_pct = round((rps_delta / max(1, base["peak_rps"])) * 100, 1)

    p95_delta = round(cand["p95_ms"] - base["p95_ms"], 1)
    p95_pct = round((p95_delta / max(0.1, base["p95_ms"])) * 100, 1)

    knee_delta = cand["knee_vus"] - base["knee_vus"]
    knee_pct = round((knee_delta / max(1, base["knee_vus"])) * 100, 1)

    error_delta = round(cand["error_pct"] - base["error_pct"], 1)

    # Determine overall verdict
    if error_delta <= 0 and (rps_pct >= 5.0 or p95_pct <= -5.0):
        verdict = "IMPROVED"
        summary = (
            f"Candidate run {candidate_run_id} demonstrated improved capacity over baseline {base_run_id}: "
            f"Throughput increased by {rps_pct}%, optimal knee expanded by {knee_delta:+d} VUs, "
            f"and p95 latency changed by {p95_pct}%."
        )
    elif error_delta > 2.0 or (p95_pct >= 15.0 and rps_pct <= 0):
        verdict = "REGRESSED"
        summary = (
            f"Candidate run {candidate_run_id} exhibited regression compared to {base_run_id}: "
            f"Latency degraded by {p95_pct}% with an error rate shift of {error_delta:+d}%."
        )
    else:
        verdict = "UNCHANGED"
        summary = (
            f"Candidate run {candidate_run_id} performed consistently with baseline {base_run_id} "
            f"within standard variance tolerance (RPS {rps_pct:+}%, p95 {p95_pct:+}%)."
        )

    return {
        "base_run": base,
        "candidate_run": cand,
        "deltas": {
            "peak_rps_delta": rps_delta,
            "peak_rps_pct_change": rps_pct,
            "p95_ms_delta": p95_delta,
            "p95_ms_pct_change": p95_pct,
            "knee_vus_delta": knee_delta,
            "knee_vus_pct_change": knee_pct,
            "error_pct_delta": error_delta,
        },
        "overall_verdict": verdict,
        "summary": summary,
    }


def get_all_runs(
    mode: str | None = None,
    verdict: str | None = None,
    q: str | None = None,
) -> dict:
    """Retrieve filtered runs list and latest capacity scorecard."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM test_runs WHERE 1=1"
    params = []

    if mode and mode.upper() != "ALL":
        query += " AND LOWER(mode) = LOWER(?)"
        params.append(mode)

    if verdict and verdict.upper() != "ALL":
        query += " AND (LOWER(verdict) = LOWER(?) OR LOWER(status_label) LIKE ?)"
        params.extend([verdict, f"%{verdict.lower()}%"])

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query += " AND (LOWER(run_id) LIKE ? OR LOWER(target_url) LIKE ?)"
        params.extend([term, term])

    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    runs = []
    for r in rows:
        runs.append(_row_to_dict(r))

    # Latest Scorecard (Clean empty state if no runs in database)
    scorecard = None
    if runs:
        # Prefer latest passed run for optimal scorecard, or top run
        passed_runs = [r for r in runs if r["verdict"] == "PASSED"]
        best = passed_runs[0] if passed_runs else runs[0]
        scorecard = {
            "knee_vus": best.get("knee_vus", 0),
            "peak_rps": best.get("peak_rps", 0),
            "p95_ms": int(best.get("p95_ms", 0)),
            "run_id": best.get("run_id"),
            "verdict": best.get("verdict"),
        }

    conn.close()
    return {"runs": runs, "scorecard": scorecard}


def get_run(run_id: str) -> dict | None:
    """Retrieve full details for a single test run."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    return _row_to_dict(row)


def save_run(data: dict) -> dict:
    """Persist or update a load test run record into SQLite."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    timeseries = data.get("timeseries", [])
    if isinstance(timeseries, list):
        timeseries_json = json.dumps(timeseries)
    else:
        timeseries_json = str(data.get("timeseries_json", "[]"))

    step_metrics = data.get("step_metrics", [])
    if isinstance(step_metrics, list):
        step_metrics_json = json.dumps(step_metrics)
    else:
        step_metrics_json = str(data.get("step_metrics_json", "[]"))

    run_record = {
        "run_id": data["run_id"],
        "timestamp": data.get("timestamp", time.strftime("%H:%M:%S")),
        "target_url": data.get("target_url", "https://api.myproject.dev"),
        "guard_id": data.get("guard_id", "PG-ACTIVE"),
        "mode": data.get("mode", "Steady Crowd"),
        "target_vus": int(data.get("target_vus", 100)),
        "peak_vus": int(data.get("peak_vus", 100)),
        "duration_sec": int(data.get("duration_sec", 60)),
        "elapsed_sec": int(data.get("elapsed_sec", 60)),
        "peak_rps": int(data.get("peak_rps", 0)),
        "avg_rps": int(data.get("avg_rps", 0)),
        "p95_ms": float(data.get("p95_ms", 0.0)),
        "error_pct": float(data.get("error_pct", 0.0)),
        "total_requests": int(data.get("total_requests", 0)),
        "status_2xx": int(data.get("status_2xx", 0)),
        "status_429": int(data.get("status_429", 0)),
        "status_5xx": int(data.get("status_5xx", 0)),
        "bytes_discarded_mb": float(data.get("bytes_discarded_mb", 0.0)),
        "ram_mb": float(data.get("ram_mb", 50.0)),
        "verdict": data.get("verdict", "PASSED"),
        "status_label": data.get("status_label", "PASSED (Completed)"),
        "knee_vus": int(data.get("knee_vus", 0)),
        "knee_rps": int(data.get("knee_rps", 0)),
        "knee_p95_ms": float(data.get("knee_p95_ms", 0.0)),
        "bottleneck_summary": data.get("bottleneck_summary", "Completed successfully."),
        "timeseries_json": timeseries_json,
        "step_metrics_json": step_metrics_json,
        "created_at": float(data.get("created_at", time.time())),
    }

    cursor.execute(
        """
        INSERT OR REPLACE INTO test_runs (
            run_id, timestamp, target_url, guard_id, mode,
            target_vus, peak_vus, duration_sec, elapsed_sec,
            peak_rps, avg_rps, p95_ms, error_pct, total_requests,
            status_2xx, status_429, status_5xx, bytes_discarded_mb,
            ram_mb, verdict, status_label, knee_vus, knee_rps,
            knee_p95_ms, bottleneck_summary, timeseries_json,
            step_metrics_json, created_at
        ) VALUES (
            :run_id, :timestamp, :target_url, :guard_id, :mode,
            :target_vus, :peak_vus, :duration_sec, :elapsed_sec,
            :peak_rps, :avg_rps, :p95_ms, :error_pct, :total_requests,
            :status_2xx, :status_429, :status_5xx, :bytes_discarded_mb,
            :ram_mb, :verdict, :status_label, :knee_vus, :knee_rps,
            :knee_p95_ms, :bottleneck_summary, :timeseries_json,
            :step_metrics_json, :created_at
        )
        """,
        run_record,
    )
    conn.commit()
    conn.close()
    return run_record


def clear_runs() -> None:
    """Clear custom test runs completely."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_runs")
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["timeseries"] = json.loads(d.get("timeseries_json", "[]"))
    except Exception:
        d["timeseries"] = []

    try:
        d["step_metrics"] = json.loads(d.get("step_metrics_json", "[]"))
    except Exception:
        d["step_metrics"] = []

    # Map frontend compatibility keys for wireframe UI table
    d["id"] = d["run_id"]
    d["target"] = d["target_url"]
    d["guardToken"] = d["guard_id"]
    d["peakVus"] = d["peak_vus"]
    d["duration"] = d["duration_sec"]
    d["peakRps"] = d["peak_rps"]
    d["p95"] = f"{int(d['p95_ms'])} ms"
    d["status"] = d["status_label"]
    d["verdictCategory"] = d["verdict"]
    return d

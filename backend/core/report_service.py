import json
import math
import sqlite3
import time

from backend.core.database import get_db_connection, init_all_tables as init_db, journey_step_metadata, target_template
from backend.core.request_owner import request_owner


CAPACITY_UNAVAILABLE = {
    "knee_vus": 0,
    "knee_rps": 0,
    "knee_p95_ms": 0.0,
    "bottleneck_summary": "Capacity unavailable",
}


def detect_knee_of_curve(
    timeseries: list[dict],
    target_vus: int,
    p95_ceiling_ms: float = 2000.0,
) -> dict:
    """Estimate capacity from at least three distinct, healthy rolling samples."""
    valid_points = []
    healthy_by_vus = {}
    unhealthy_levels = set()
    for point in timeseries:
        if not isinstance(point, dict):
            continue
        vus, rps = point.get("vus"), point.get("rps")
        p95, error_pct = point.get("p95_ms"), point.get("error_pct")
        if (type(vus) is not int or not 0 < vus <= target_vus
                or type(rps) is not int or rps <= 0
                or type(p95) not in (int, float) or not 0 <= p95 < math.inf
                or type(error_pct) not in (int, float) or not 0 <= error_pct <= 100):
            continue
        valid_points.append(point)
        # RPS is the count of requests in the same one-second window as the error rate.
        if error_pct > 2.0 or p95 > 0.80 * p95_ceiling_ms:
            unhealthy_levels.add(vus)
            continue
        previous = healthy_by_vus.get(vus)
        if previous is None or (p95, -rps) > (previous["p95_ms"], -previous["rps"]):
            healthy_by_vus[vus] = point

    levels = [healthy_by_vus[vus] for vus in sorted(healthy_by_vus) if vus not in unhealthy_levels]
    if len(levels) < 3:
        return {
            **CAPACITY_UNAVAILABLE,
            "linear_range": "Unavailable",
            "optimal_point": "Unavailable",
            "cliff_point": "Unavailable",
            "ramp_steps": valid_points,
        }

    p0, p1 = levels[:2]
    baseline_slope = max(0.05, max(0.1, p1["p95_ms"] - p0["p95_ms"]) / (p1["vus"] - p0["vus"]))

    knee_point = levels[-1]
    trigger_reason = None

    for prev, curr in zip(levels[1:], levels[2:]):
        d_vus = curr["vus"] - prev["vus"]
        current_slope = (curr["p95_ms"] - prev["p95_ms"]) / d_vus
        rps_gain_per_vu = (curr["rps"] - prev["rps"]) / d_vus

        if current_slope > 2.0 * baseline_slope and (rps_gain_per_vu < 1.5 or current_slope > 2.5 * baseline_slope):
            knee_point = prev
            trigger_reason = (
                f"Marginal latency slope increased to {current_slope / baseline_slope:.1f}x baseline."
            )
            break

    knee_vus = knee_point["vus"]
    knee_rps = knee_point["rps"]
    knee_p95_ms = round(knee_point["p95_ms"], 1)
    optimal_point = f"{knee_vus} VUs @ {knee_rps:,} RPS"
    if trigger_reason:
        summary = f"Optimal Knee detected at {knee_vus} VUs ({knee_rps:,} RPS @ {knee_p95_ms} ms p95). {trigger_reason}"
    else:
        summary = (
            f"Highest healthy load observed: {knee_vus} VUs ({knee_rps:,} RPS @ {knee_p95_ms} ms p95). "
            "No saturation point detected among healthy samples."
        )

    return {
        "knee_vus": knee_vus,
        "knee_rps": knee_rps,
        "knee_p95_ms": knee_p95_ms,
        "linear_range": f"{levels[0]['vus']} - {knee_vus} VUs",
        "optimal_point": optimal_point,
        "cliff_point": f"> {knee_vus} VUs" if trigger_reason else "Unavailable",
        "bottleneck_summary": summary,
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

    if base["metrics_scope"] != cand["metrics_scope"] or any(
        run["p95_ms"] is None for run in (base, cand)
    ):
        return {
            "base_run": base, "candidate_run": cand, "deltas": {},
            "overall_verdict": "UNAVAILABLE",
            "summary": "Choose two reports with measured latency from the same measurement window.",
        }

    rps_delta = cand["peak_rps"] - base["peak_rps"]
    rps_pct = round((rps_delta / max(1, base["peak_rps"])) * 100, 1)

    p95_delta = round(cand["p95_ms"] - base["p95_ms"], 1)
    p95_pct = round((p95_delta / max(0.1, base["p95_ms"])) * 100, 1)

    knee_deltas = {}
    knee_change = ""
    if base["knee_vus"] > 0 and cand["knee_vus"] > 0:
        knee_delta = cand["knee_vus"] - base["knee_vus"]
        knee_deltas = {
            "knee_vus_delta": knee_delta,
            "knee_vus_pct_change": round(100 * knee_delta / base["knee_vus"], 1),
        }
        knee_change = f"Recommended load changed by {knee_delta:+d} VUs. "

    error_delta = round(cand["error_pct"] - base["error_pct"], 1)

    # Determine overall verdict
    if error_delta <= 0 and (rps_pct >= 5.0 or p95_pct <= -5.0):
        verdict = "IMPROVED"
        summary = (
            f"Candidate run {candidate_run_id} improved over baseline {base_run_id}. "
            f"Throughput changed by {rps_pct:+}% and p95 latency changed by {p95_pct:+}%. {knee_change}"
        )
    elif error_delta > 2.0 or (p95_pct >= 15.0 and rps_pct <= 0):
        verdict = "REGRESSED"
        summary = (
            f"Candidate run {candidate_run_id} exhibited regression compared to {base_run_id}: "
            f"Latency changed by {p95_pct:+}% with an error rate shift of {error_delta:+}%."
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
            **knee_deltas,
            "error_pct_delta": error_delta,
        },
        "overall_verdict": verdict,
        "summary": summary,
    }


def get_all_runs(
    mode: str | None = None, verdict: str | None = None, q: str | None = None,
    limit: int = 25, cursor: str | None = None,
) -> dict:
    """Get one page of summaries without loading response charts."""
    if not 1 <= limit <= 100:
        raise ValueError("History limit must be between 1 and 100.")
    after = []
    if cursor:
        try:
            stamp, run_id = json.loads(cursor)
            if not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or not isinstance(run_id, str):
                raise ValueError
            after = [stamp, run_id]
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid history cursor.") from exc

    where = " WHERE user_id = ?"
    params = [request_owner.get()]
    if mode and mode.upper() != "ALL":
        where += " AND REPLACE(REPLACE(LOWER(mode), '-', ' '), '_', ' ') = ?"
        params.append(mode.lower().replace("-", " ").replace("_", " "))
    if verdict and verdict.upper() != "ALL":
        where += " AND (LOWER(verdict) = LOWER(?) OR LOWER(status_label) LIKE ?)"
        params.extend([verdict, f"%{verdict.lower()}%"])
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        where += """ AND (LOWER(run_id) LIKE ? OR LOWER(SUBSTR(target_url, 1,
            MIN(INSTR(target_url || '?', '?'), INSTR(target_url || '#', '#')) - 1)) LIKE ?)"""
        params.extend([term, term])

    order = " ORDER BY created_at DESC, run_id DESC"
    page = " AND (created_at, run_id) < (?, ?)" if after else ""
    fields = (
        "run_id, timestamp, target_url, guard_id, mode, target_vus, peak_vus, duration_sec, "
        "elapsed_sec, peak_rps, avg_rps, p95_ms, error_pct, total_requests, metrics_scope, verdict, "
        "status_label, knee_vus, knee_rps, knee_p95_ms, bottleneck_summary, capacity_checked, created_at"
    )
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"SELECT {fields} FROM test_runs{where}{page}{order} LIMIT ?",
            [*params, *after, limit + 1],
        ).fetchall()
        scorecard_fields = (
            "CASE WHEN capacity_checked THEN knee_vus ELSE 0 END AS knee_vus, "
            "peak_rps, CASE WHEN metrics_scope = 'whole_run' AND total_requests = 0 "
            "THEN NULL ELSE CAST(p95_ms AS INTEGER) END AS p95_ms, run_id, verdict"
        )
        scorecard = conn.execute(
            f"SELECT {scorecard_fields} FROM test_runs{where} AND verdict = 'PASSED'{order} LIMIT 1",
            params,
        ).fetchone()
        if scorecard is None:
            scorecard = conn.execute(
                f"SELECT {scorecard_fields} FROM test_runs{where}{order} LIMIT 1", params,
            ).fetchone()
    finally:
        conn.close()
    next_cursor = json.dumps([rows[limit - 1]["created_at"], rows[limit - 1]["run_id"]]) if len(rows) > limit else None
    return {"runs": [_row_to_dict(row) for row in rows[:limit]],
            "scorecard": dict(scorecard) if scorecard is not None else None, "next_cursor": next_cursor}


def get_run(run_id: str) -> dict | None:
    """Retrieve full details for a single test run."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM test_runs WHERE run_id = ? AND user_id = ?", (run_id, request_owner.get()))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    return _row_to_dict(row)


def save_run(data: dict) -> dict:
    """Persist a completed run once, retaining the original on retry."""
    conn = get_db_connection()
    cursor = conn.cursor()

    timeseries = data.get("timeseries", [])
    if isinstance(timeseries, list):
        timeseries_json = json.dumps(timeseries)
    else:
        timeseries_json = str(data.get("timeseries_json", "[]"))

    step_metrics = data.get("step_metrics", [])
    if not isinstance(step_metrics, list):
        try:
            step_metrics = json.loads(data.get("step_metrics_json", "[]"))
        except (ValueError, TypeError):
            step_metrics = []
    step_metrics_json = json.dumps(journey_step_metadata(step_metrics))

    run_record = {
        "run_id": data["run_id"],
        "user_id": request_owner.get(),
        "timestamp": data.get("timestamp", time.strftime("%H:%M:%S")),
        "target_url": target_template(data.get("target_url", "https://api.myproject.dev")),
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
        "metrics_scope": data.get("metrics_scope", "legacy_window"),
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
        "capacity_checked": int(bool(data.get("capacity_checked"))),
        "timeseries_json": timeseries_json,
        "step_metrics_json": step_metrics_json,
        "created_at": float(data.get("created_at", time.time())),
    }

    cursor.execute(
        """
        INSERT INTO test_runs (
            run_id, user_id, timestamp, target_url, guard_id, mode,
            target_vus, peak_vus, duration_sec, elapsed_sec,
            peak_rps, avg_rps, p95_ms, error_pct, total_requests,
            status_2xx, status_429, status_5xx, bytes_discarded_mb,
            ram_mb, verdict, status_label, knee_vus, knee_rps,
            knee_p95_ms, bottleneck_summary, timeseries_json,
            step_metrics_json, created_at, metrics_scope, capacity_checked
        ) VALUES (
            :run_id, :user_id, :timestamp, :target_url, :guard_id, :mode,
            :target_vus, :peak_vus, :duration_sec, :elapsed_sec,
            :peak_rps, :avg_rps, :p95_ms, :error_pct, :total_requests,
            :status_2xx, :status_429, :status_5xx, :bytes_discarded_mb,
            :ram_mb, :verdict, :status_label, :knee_vus, :knee_rps,
            :knee_p95_ms, :bottleneck_summary, :timeseries_json,
            :step_metrics_json, :created_at, :metrics_scope, :capacity_checked
        ) ON CONFLICT(run_id) DO NOTHING
        """,
        run_record,
    )
    inserted = cursor.rowcount == 1
    conn.commit()
    conn.close()
    if inserted:
        return run_record
    existing = get_run(run_record["run_id"])
    if existing is None:
        raise ValueError("A different operator already owns this run ID.")
    return existing


def clear_runs() -> None:
    """Clear custom test runs completely."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM test_runs WHERE user_id = ?", (request_owner.get(),))
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if not d.pop("capacity_checked") or not d["knee_vus"]:
        d.update(CAPACITY_UNAVAILABLE)
    for field in ("timeseries", "step_metrics"):
        key = field + "_json"
        if key in d:
            try:
                d[field] = json.loads(d[key])
            except (ValueError, TypeError):
                d[field] = []
    if "step_metrics_json" in d:
        d["step_metrics"] = journey_step_metadata(d["step_metrics"])
        d["step_metrics_json"] = json.dumps(d["step_metrics"])

    # Map frontend compatibility keys for wireframe UI table
    d["id"] = d["run_id"]
    d["target_url"] = d["target"] = target_template(d["target_url"])
    d["guardToken"] = d["guard_id"]
    d["peakVus"] = d["peak_vus"]
    d["duration"] = d["duration_sec"]
    d["peakRps"] = d["peak_rps"]
    if d["metrics_scope"] == "whole_run" and not d["total_requests"]:
        d["p95_ms"] = d["error_pct"] = None
    d["p95"] = f"{int(d['p95_ms'])} ms" if d["p95_ms"] is not None else "Unavailable"
    d["status"] = d["status_label"]
    d["verdictCategory"] = d["verdict"]
    return d

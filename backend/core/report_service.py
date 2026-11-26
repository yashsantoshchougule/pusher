import json
import math
import sqlite3
import statistics
import time

from backend.core.database import get_db_connection, init_all_tables as init_db, journey_step_metadata, target_template
from backend.core.request_owner import request_owner


CAPACITY_UNAVAILABLE = {
    "knee_vus": 0,
    "knee_rps": 0,
    "knee_p95_ms": 0.0,
    "bottleneck_summary": "Capacity unavailable",
}

_SUMMARY_FIELDS = (
    "run_id, timestamp, target_url, project_name, guard_id, mode, target_vus, peak_vus, duration_sec, "
    "elapsed_sec, peak_rps, avg_rps, p95_ms, error_pct, total_requests, "
    "status_2xx, status_429, status_5xx, status_other, timeout_count, network_error_count, "
    "p95_ceiling_ms, max_error_pct, effective_p95_ceiling_ms, "
    "metrics_scope, verdict, status_label, knee_vus, knee_rps, knee_p95_ms, "
    "bottleneck_summary, capacity_reason, capacity_checked, created_at"
)

_SCORECARD_FIELDS = (
    "CASE WHEN capacity_checked THEN knee_vus ELSE 0 END AS knee_vus, "
    "peak_rps, "
    "CASE WHEN metrics_scope = 'whole_run' AND total_requests = 0 THEN NULL ELSE ROUND(p95_ms, 1) END AS p95_ms, "
    "CASE WHEN metrics_scope = 'whole_run' AND total_requests = 0 THEN NULL ELSE ROUND(error_pct, 1) END AS error_pct, "
    "run_id, verdict, status_label, elapsed_sec, duration_sec, "
    "p95_ceiling_ms, effective_p95_ceiling_ms, capacity_reason"
)


def _is_finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _opt_float(value) -> float | None:
    if value is None:
        return None
    if _is_finite_number(value):
        return float(value)
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _opt_int(value) -> int | None:
    if value is None:
        return None
    if type(value) is bool:
        return int(value)
    if _is_finite_number(value):
        return int(round(value))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_bool_int(value) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _downsample_timeline_points(raw_points: list | None, fallback_ts: list | None = None, max_points: int = 600) -> list[dict]:
    """Normalize timeline samples to {t, vus, rps, p95_ms, error_pct} and cap at <= max_points."""
    src = raw_points if isinstance(raw_points, list) and raw_points else (fallback_ts if isinstance(fallback_ts, list) else [])
    cleaned = []
    for item in src:
        if not isinstance(item, dict):
            continue
        t_val = item.get("t", item.get("elapsed_sec", 0))
        vus_val = item.get("vus", item.get("active_vus", 0))
        rps_val = item.get("rps", item.get("live_rps", 0))
        p95_val = item.get("p95_ms", 0.0)
        err_val = item.get("error_pct", 0.0)
        cleaned.append({
            "t": max(0, int(round(float(t_val or 0)))),
            "vus": max(0, int(round(float(vus_val or 0)))),
            "rps": max(0, int(round(float(rps_val or 0)))),
            "p95_ms": round(max(0.0, float(p95_val or 0.0)), 1),
            "error_pct": round(max(0.0, float(err_val or 0.0)), 1),
        })
    n = len(cleaned)
    if n <= max_points:
        return cleaned
    if max_points <= 2:
        return [cleaned[0], cleaned[-1]][:max_points]
    step = (n - 1) / (max_points - 1)
    indices = [round(i * step) for i in range(max_points - 1)] + [n - 1]
    return [cleaned[idx] for idx in indices]


def _normalize_latency_breakdown(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    mapping = (
        ("p50_ms", ("p50_ms", "p50")),
        ("p90_ms", ("p90_ms", "p90")),
        ("p95_ms", ("p95_ms", "p95")),
        ("p99_ms", ("p99_ms", "p99")),
        ("max_ms", ("max_ms", "max")),
    )
    normalized = {}
    has_any = False
    for target_key, source_keys in mapping:
        raw = None
        for key in source_keys:
            if key in value and value[key] is not None:
                raw = value[key]
                break
        num = _opt_float(raw)
        if num is not None:
            normalized[target_key] = round(num, 1)
            has_any = True
        else:
            normalized[target_key] = None
    return normalized if has_any else None


def _aggregate_steps(
    timeseries: list[dict],
    target_vus: int = 0,
    p95_ceiling_ms: float = 2000.0,
    max_error_pct: float = 2.0,
) -> tuple[list[dict], list[dict]]:
    """Aggregate valid rolling samples into per-VU tiers and preserve valid_points."""
    if not isinstance(timeseries, list):
        return [], []
    effective_p95_ceiling = (
        float(p95_ceiling_ms)
        if _is_finite_number(p95_ceiling_ms) and p95_ceiling_ms > 0
        else 2000.0
    )
    configured_error_limit = 2.0 if max_error_pct is None else max(0.0, float(max_error_pct))
    error_limit = min(2.0, configured_error_limit)

    valid_points: list[dict] = []
    grouped: dict[int, list[dict]] = {}
    for point in timeseries:
        if not isinstance(point, dict):
            continue
        vus, rps = point.get("vus"), point.get("rps")
        p95, error_pct = point.get("p95_ms"), point.get("error_pct")
        if (
            not _is_finite_number(vus) or vus <= 0 or (target_vus > 0 and vus > target_vus)
            or not _is_finite_number(rps) or rps <= 0
            or not _is_finite_number(p95) or p95 < 0
            or not _is_finite_number(error_pct) or not 0 <= error_pct <= 100
        ):
            continue
        valid_points.append(point)
        vus_tier = int(round(vus))
        grouped.setdefault(vus_tier, []).append(point)

    steps: list[dict] = []
    for idx, vus_tier in enumerate(sorted(grouped), start=1):
        tier_samples = grouped[vus_tier]
        med_rps = int(round(statistics.median(float(s["rps"]) for s in tier_samples)))
        med_p95 = round(float(statistics.median(float(s["p95_ms"]) for s in tier_samples)), 1)
        max_err = round(float(max(float(s["error_pct"]) for s in tier_samples)), 1)
        healthy = (
            med_rps > 0
            and max_err <= error_limit
            and med_p95 <= 0.80 * effective_p95_ceiling
        )
        steps.append({
            "step": idx,
            "vus": vus_tier,
            "rps": med_rps,
            "p95_ms": med_p95,
            "error_pct": max_err,
            "samples": len(tier_samples),
            "healthy": healthy,
        })
    return steps, valid_points


def detect_knee_of_curve(
    timeseries: list[dict],
    target_vus: int = 0,
    p95_ceiling_ms: float = 2000.0,
    max_error_pct: float = 2.0,
    mode: str | None = None,
) -> dict:
    """Estimate capacity from at least three distinct, healthy rolling VU tiers."""
    effective_p95_ceiling = (
        float(p95_ceiling_ms)
        if _is_finite_number(p95_ceiling_ms) and p95_ceiling_ms > 0
        else 2000.0
    )
    configured_error_limit = 2.0 if max_error_pct is None else max(0.0, float(max_error_pct))
    error_limit = min(2.0, configured_error_limit)

    steps, valid_points = _aggregate_steps(
        timeseries,
        target_vus=target_vus,
        p95_ceiling_ms=effective_p95_ceiling,
        max_error_pct=error_limit,
    )
    levels = [step for step in steps if step["healthy"]]

    if len(levels) < 3:
        if not timeseries:
            reason = "No time-series samples were recorded during this run."
        elif not steps:
            reason = "No valid request samples with active concurrency and positive throughput were recorded."
        elif not levels:
            first = steps[0]
            reason = (
                f"All {len(steps)} observed VU tier(s) breached health limits "
                f"(first breach at {first['vus']} VUs: {first['p95_ms']} ms p95, {first['error_pct']}% errors; "
                f"healthy limit <= {0.80 * effective_p95_ceiling:.0f} ms p95 and <= {error_limit:.1f}% errors)."
            )
        else:
            mode_norm = (mode or "").lower().replace("-", "_").replace(" ", "_")
            unhealthy = [s for s in steps if not s["healthy"]]
            if mode_norm in ("steady_crowd", "sudden_rush"):
                reason = (
                    f"Traffic mode '{mode}' exercised only {len(steps)} distinct VU tier(s) "
                    f"({len(levels)} healthy); at least 3 healthy VU tiers (such as Step Ramp) are required to detect a knee."
                )
            elif unhealthy:
                first_bad = unhealthy[0]
                reason = (
                    f"Only {len(levels)} healthy VU tier(s) observed before breach at {first_bad['vus']} VUs "
                    f"({first_bad['p95_ms']} ms p95, {first_bad['error_pct']}% errors); at least 3 healthy VU tiers are required."
                )
            else:
                reason = (
                    f"Only {len(levels)} distinct healthy VU tier(s) observed; "
                    "at least 3 distinct healthy VU tiers are required to detect a knee."
                )
        return {
            **CAPACITY_UNAVAILABLE,
            "capacity_reason": reason,
            "linear_range": "Unavailable",
            "optimal_point": "Unavailable",
            "cliff_point": "Unavailable",
            "steps": steps,
            "ramp_steps": valid_points,
        }

    p0, p1 = levels[:2]
    d_vus_base = p1["vus"] - p0["vus"]
    raw_base_slope = (p1["p95_ms"] - p0["p95_ms"]) / d_vus_base
    marginal_base_rps_per_vu = (p1["rps"] - p0["rps"]) / d_vus_base
    baseline_rps_per_vu = (
        marginal_base_rps_per_vu
        if marginal_base_rps_per_vu > 0
        else (p0["rps"] / max(1, p0["vus"]))
    )

    knee_point = levels[-1]
    trigger_reason = None

    for prev, curr in zip(levels[1:], levels[2:]):
        d_vus = curr["vus"] - prev["vus"]
        delta_p95 = curr["p95_ms"] - prev["p95_ms"]
        current_slope = delta_p95 / d_vus
        rps_gain_per_vu = (curr["rps"] - prev["rps"]) / d_vus
        throughput_degraded = (rps_gain_per_vu < 0) or (rps_gain_per_vu < 0.70 * baseline_rps_per_vu)

        if raw_base_slope > 0:
            slope_ratio = current_slope / raw_base_slope
            slope_spiked = slope_ratio > 2.0 and delta_p95 >= max(1.0, 0.10 * prev["p95_ms"])
            severe_slope_spike = slope_ratio > 2.5 and delta_p95 >= max(2.0, 0.20 * prev["p95_ms"])
        else:
            slope_ratio = None
            slope_spiked = delta_p95 >= max(5.0, 0.25 * max(1.0, prev["p95_ms"]))
            severe_slope_spike = delta_p95 >= max(10.0, 0.50 * max(1.0, prev["p95_ms"]))

        if rps_gain_per_vu < 0:
            knee_point = prev
            trigger_reason = (
                f"Throughput declined from {prev['rps']:,} to {curr['rps']:,} RPS above {prev['vus']} VUs."
            )
            break
        if (slope_spiked and throughput_degraded) or severe_slope_spike:
            knee_point = prev
            if slope_ratio is not None:
                trigger_reason = (
                    f"Marginal latency slope increased to {slope_ratio:.1f}x baseline "
                    f"while throughput gain slowed to {rps_gain_per_vu:.2f} RPS/VU."
                )
            else:
                trigger_reason = (
                    f"Latency jumped by +{delta_p95:.1f} ms above {prev['vus']} VUs "
                    f"while throughput gain slowed to {rps_gain_per_vu:.2f} RPS/VU."
                )
            break

    knee_vus = knee_point["vus"]
    knee_rps = knee_point["rps"]
    knee_p95_ms = round(knee_point["p95_ms"], 1)
    optimal_point = f"{knee_vus} VUs @ {knee_rps:,} RPS"
    if trigger_reason:
        summary = f"Optimal Knee detected at {knee_vus} VUs ({knee_rps:,} RPS @ {knee_p95_ms} ms p95). {trigger_reason}"
        capacity_reason = trigger_reason
    else:
        summary = (
            f"Highest healthy load observed: {knee_vus} VUs ({knee_rps:,} RPS @ {knee_p95_ms} ms p95). "
            "No saturation point detected among healthy samples."
        )
        capacity_reason = (
            f"All {len(levels)} healthy VU tiers scaled within limits up to {knee_vus} VUs without hitting a saturation knee."
        )

    return {
        "knee_vus": knee_vus,
        "knee_rps": knee_rps,
        "knee_p95_ms": knee_p95_ms,
        "linear_range": f"{levels[0]['vus']} - {knee_vus} VUs",
        "optimal_point": optimal_point,
        "cliff_point": f"> {knee_vus} VUs" if trigger_reason else "Unavailable",
        "bottleneck_summary": summary,
        "capacity_reason": capacity_reason,
        "steps": steps,
        "ramp_steps": valid_points,
    }


def _norm_mode(mode: str | None) -> str:
    return (mode or "").strip().lower().replace("-", "_").replace(" ", "_")


def compare_two_runs(base_run_id: str, candidate_run_id: str) -> dict:
    """
    2-Run Baseline vs Candidate Comparison Engine:
    Computes exact deltas, percentage changes, comparability warnings, and verdict.
    """
    base = get_run(base_run_id)
    cand = get_run(candidate_run_id)

    if not base:
        raise ValueError(f"Baseline run '{base_run_id}' not found.")
    if not cand:
        raise ValueError(f"Candidate run '{candidate_run_id}' not found.")

    warnings: list[str] = []
    if (base.get("target_url") or "") != (cand.get("target_url") or ""):
        warnings.append(f"Different target URLs: '{base.get('target_url')}' vs '{cand.get('target_url')}'.")
    if _norm_mode(base.get("mode")) != _norm_mode(cand.get("mode")):
        warnings.append(f"Different traffic modes: '{base.get('mode')}' vs '{cand.get('mode')}'.")
    if base.get("target_vus") != cand.get("target_vus"):
        warnings.append(f"Different target VUs: {base.get('target_vus')} vs {cand.get('target_vus')}.")
    if base.get("verdict") != "PASSED" or cand.get("verdict") != "PASSED":
        warnings.append(f"Non-PASSED run verdict(s): {base.get('verdict')} vs {cand.get('verdict')}.")
    comparable = len(warnings) == 0

    if base["metrics_scope"] != cand["metrics_scope"] or any(
        run["p95_ms"] is None
        or (run.get("metrics_scope") == "whole_run" and (run.get("total_requests") or 0) == 0)
        for run in (base, cand)
    ):
        return {
            "base_run": base,
            "candidate_run": cand,
            "deltas": {},
            "overall_verdict": "UNAVAILABLE",
            "comparable": False,
            "comparability_warnings": warnings,
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

    base_error_pct = float(base.get("error_pct") or 0.0)
    cand_error_pct = float(cand.get("error_pct") or 0.0)
    error_delta = round(cand_error_pct - base_error_pct, 1)
    requests_delta = int(cand.get("total_requests") or 0) - int(base.get("total_requests") or 0)

    # Check regression BEFORE improvement so severe latency/error spikes never report IMPROVED.
    if error_delta >= 5.0 or error_delta > 2.0 or p95_pct >= 25.0 or (p95_pct >= 15.0 and rps_pct <= 0):
        verdict = "REGRESSED"
        summary = (
            f"Candidate run {candidate_run_id} exhibited regression compared to {base_run_id}: "
            f"Latency changed by {p95_pct:+}% with an error rate shift of {error_delta:+}%."
        )
    elif error_delta <= 0 and p95_pct < 25.0 and (rps_pct >= 5.0 or p95_pct <= -5.0):
        verdict = "IMPROVED"
        summary = (
            f"Candidate run {candidate_run_id} improved over baseline {base_run_id}. "
            f"Throughput changed by {rps_pct:+}% and p95 latency changed by {p95_pct:+}%. {knee_change}"
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
            "requests_delta": requests_delta,
        },
        "overall_verdict": verdict,
        "comparable": comparable,
        "comparability_warnings": warnings,
        "summary": summary,
    }


def _normalize_scorecard_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    if d.get("p95_ms") is not None:
        d["p95_ms"] = round(float(d["p95_ms"]), 1)
    if d.get("error_pct") is not None:
        d["error_pct"] = round(float(d["error_pct"]), 1)
    if "cdn_cache_warning" in d and d["cdn_cache_warning"] is not None:
        d["cdn_cache_warning"] = bool(d["cdn_cache_warning"])
    return d


def _fetch_scorecard(conn: sqlite3.Connection, where_sql: str, params: list) -> dict | None:
    order = " ORDER BY created_at DESC, run_id DESC"
    row = conn.execute(
        f"SELECT {_SCORECARD_FIELDS} FROM test_runs{where_sql} AND verdict = 'PASSED'{order} LIMIT 1",
        params,
    ).fetchone()
    if row is None:
        row = conn.execute(
            f"SELECT {_SCORECARD_FIELDS} FROM test_runs{where_sql}{order} LIMIT 1",
            params,
        ).fetchone()
    return _normalize_scorecard_row(row)


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

    owner_id = request_owner.get()
    base_where = " WHERE user_id = ?"
    base_params = [owner_id]
    where = base_where
    params = list(base_params)
    if mode and mode.upper() != "ALL":
        where += " AND REPLACE(REPLACE(LOWER(mode), '-', ' '), '_', ' ') = ?"
        params.append(mode.lower().replace("-", " ").replace("_", " "))
    if verdict and verdict.upper() != "ALL":
        verdict_norm = verdict.strip().upper().replace("-", "_").replace(" ", "_")
        if verdict_norm in ("CIRCUIT_TRIPPED", "CIRCUIT_BREAKER", "TRIPPED"):
            where += " AND (UPPER(verdict) = 'CIRCUIT_BREAKER' OR LOWER(status_label) LIKE '%circuit%' OR LOWER(status_label) LIKE '%tripped%')"
        else:
            where += " AND (REPLACE(REPLACE(UPPER(verdict), '-', '_'), ' ', '_') = ? OR LOWER(status_label) LIKE ?)"
            params.extend([verdict_norm, f"%{verdict.strip().lower().replace('_', ' ')}%"])
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        where += """ AND (LOWER(run_id) LIKE ? OR LOWER(project_name) LIKE ? OR LOWER(SUBSTR(target_url, 1,
            MIN(INSTR(target_url || '?', '?'), INSTR(target_url || '#', '#')) - 1)) LIKE ?)"""
        params.extend([term, term, term])

    order = " ORDER BY created_at DESC, run_id DESC"
    page = " AND (created_at, run_id) < (?, ?)" if after else ""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"SELECT {_SUMMARY_FIELDS} FROM test_runs{where}{page}{order} LIMIT ?",
            [*params, *after, limit + 1],
        ).fetchall()
        scorecard = _fetch_scorecard(conn, where, params)
        global_scorecard = (
            scorecard
            if where == base_where
            else _fetch_scorecard(conn, base_where, base_params)
        )
        latest_row = conn.execute(
            f"SELECT {_SCORECARD_FIELDS}, mode, target_vus, peak_vus, total_requests, timestamp, cache_hit_pct, cdn_cache_warning "
            f"FROM test_runs{base_where}{order} LIMIT 1",
            base_params,
        ).fetchone()
    finally:
        conn.close()
    next_cursor = json.dumps([rows[limit - 1]["created_at"], rows[limit - 1]["run_id"]]) if len(rows) > limit else None
    return {
        "runs": [_row_to_dict(row) for row in rows[:limit]],
        "scorecard": scorecard,
        "global_scorecard": global_scorecard,
        "latest_run": _normalize_scorecard_row(latest_row),
        "next_cursor": next_cursor,
    }


def get_run(run_id: str) -> dict | None:
    """Retrieve full details for a single test run."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM test_runs WHERE run_id = ? AND user_id = ?",
            (run_id, request_owner.get()),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return _row_to_dict(row)


def save_run(data: dict) -> dict:
    """Persist a completed run once, retaining the original on retry."""
    timeseries = data.get("timeseries")
    if not isinstance(timeseries, list):
        raw_ts = data.get("timeseries_json")
        if isinstance(raw_ts, str):
            try:
                parsed_ts = json.loads(raw_ts)
                timeseries = parsed_ts if isinstance(parsed_ts, list) else []
            except (ValueError, TypeError):
                timeseries = []
        else:
            timeseries = []
    timeseries_json = json.dumps(timeseries)

    step_metrics = data.get("step_metrics")
    if not isinstance(step_metrics, list):
        try:
            parsed_sm = json.loads(data.get("step_metrics_json") or "[]")
            step_metrics = parsed_sm if isinstance(parsed_sm, list) else []
        except (ValueError, TypeError):
            step_metrics = []
    step_metrics = journey_step_metadata(step_metrics)
    step_metrics_json = json.dumps(step_metrics)

    latency_breakdown = data.get("latency_breakdown")
    if latency_breakdown is None and "latency_breakdown_json" in data:
        raw_lb = data.get("latency_breakdown_json")
        if isinstance(raw_lb, str):
            try:
                latency_breakdown = json.loads(raw_lb)
            except (ValueError, TypeError):
                latency_breakdown = None
    latency_breakdown = _normalize_latency_breakdown(latency_breakdown)
    latency_breakdown_json = json.dumps(latency_breakdown) if latency_breakdown is not None else "null"

    target_vus = int(data.get("target_vus", 100))
    mode = data.get("mode", "Steady Crowd")
    p95_ceiling_ms = _opt_float(data.get("p95_ceiling_ms"))
    max_error_pct = _opt_float(data.get("max_error_pct"))
    effective_p95_ceiling_ms = _opt_float(data.get("effective_p95_ceiling_ms"))
    effective_max_error_pct = _opt_float(data.get("effective_max_error_pct"))
    capacity_checked = int(bool(data.get("capacity_checked")))

    steps = data.get("steps")
    if not isinstance(steps, list):
        raw_steps = data.get("steps_json")
        if isinstance(raw_steps, str):
            try:
                parsed_steps = json.loads(raw_steps)
                steps = parsed_steps if isinstance(parsed_steps, list) else None
            except (ValueError, TypeError):
                steps = None
        else:
            steps = None

    capacity_reason = str(data.get("capacity_reason") or "")
    linear_range = str(data.get("linear_range") or "")
    optimal_point = str(data.get("optimal_point") or "")
    cliff_point = str(data.get("cliff_point") or "")

    if capacity_checked and (steps is None or not capacity_reason):
        derived = detect_knee_of_curve(
            timeseries,
            target_vus=target_vus,
            p95_ceiling_ms=effective_p95_ceiling_ms or p95_ceiling_ms or 2000.0,
            max_error_pct=effective_max_error_pct if effective_max_error_pct is not None else (
                max_error_pct if max_error_pct is not None else 2.0
            ),
            mode=mode,
        )
        if steps is None:
            steps = derived["steps"]
        if not capacity_reason:
            capacity_reason = derived["capacity_reason"]
        if not linear_range:
            linear_range = derived["linear_range"]
        if not optimal_point:
            optimal_point = derived["optimal_point"]
        if not cliff_point:
            cliff_point = derived["cliff_point"]

    steps_json = json.dumps(steps if isinstance(steps, list) else [])

    failure_breakdown = data.get("failure_breakdown")
    if not isinstance(failure_breakdown, list):
        try:
            parsed_fb = json.loads(data.get("failure_breakdown_json") or "[]")
            failure_breakdown = parsed_fb if isinstance(parsed_fb, list) else []
        except (ValueError, TypeError):
            failure_breakdown = []
    failure_breakdown_json = json.dumps(failure_breakdown)

    crash_summary = data.get("crash_summary")
    if not isinstance(crash_summary, dict):
        try:
            parsed_cs = json.loads(data.get("crash_summary_json") or "null")
            crash_summary = parsed_cs if isinstance(parsed_cs, dict) else None
        except (ValueError, TypeError):
            crash_summary = None
    crash_summary_json = json.dumps(crash_summary) if crash_summary is not None else "null"

    raw_tp = data.get("timeline_points")
    if not isinstance(raw_tp, list):
        try:
            parsed_tp = json.loads(data.get("timeline_points_json") or "[]")
            raw_tp = parsed_tp if isinstance(parsed_tp, list) else []
        except (ValueError, TypeError):
            raw_tp = []
    timeline_points = _downsample_timeline_points(raw_tp, fallback_ts=timeseries, max_points=600)
    timeline_points_json = json.dumps(timeline_points)

    raw_p95 = data.get("p95_ms", 0.0)
    p95_ms_val = round(float(raw_p95), 1) if raw_p95 is not None else 0.0
    raw_err = data.get("error_pct", 0.0)
    error_pct_val = round(float(raw_err), 1) if raw_err is not None else 0.0
    raw_knee_p95 = data.get("knee_p95_ms", 0.0)
    knee_p95_val = round(float(raw_knee_p95), 1) if raw_knee_p95 is not None else 0.0

    run_record = {
        "run_id": data["run_id"],
        "user_id": request_owner.get(),
        "timestamp": data.get("timestamp", time.strftime("%H:%M:%S")),
        "target_url": target_template(data.get("target_url", "https://api.myproject.dev")),
        "project_name": str(data.get("project_name") or "").strip()[:80],
        "guard_id": data.get("guard_id", "PG-ACTIVE"),
        "mode": mode,
        "target_vus": target_vus,
        "peak_vus": int(data.get("peak_vus", 100)),
        "duration_sec": int(data.get("duration_sec", 60)),
        "elapsed_sec": int(data.get("elapsed_sec", 60)),
        "peak_rps": int(data.get("peak_rps", 0)),
        "avg_rps": int(data.get("avg_rps", 0)),
        "p95_ms": p95_ms_val,
        "error_pct": error_pct_val,
        "metrics_scope": data.get("metrics_scope", "legacy_window"),
        "total_requests": int(data.get("total_requests", 0)),
        "status_2xx": int(data.get("status_2xx", 0)),
        "status_3xx": int(data.get("status_3xx") or 0),
        "status_4xx": int(data.get("status_4xx") or 0),
        "status_429": int(data.get("status_429", 0)),
        "status_5xx": int(data.get("status_5xx", 0)),
        "status_other": int(data.get("status_other") or 0),
        "timeout_count": int(data.get("timeout_count") or 0),
        "network_error_count": int(data.get("network_error_count") or 0),
        "failed_requests": int(data.get("failed_requests") or 0),
        "p95_ceiling_ms": p95_ceiling_ms,
        "max_error_pct": max_error_pct,
        "effective_p95_ceiling_ms": effective_p95_ceiling_ms,
        "effective_max_error_pct": effective_max_error_pct,
        "ram_limit_mb": _opt_int(data.get("ram_limit_mb")),
        "request_timeout_sec": _opt_float(data.get("request_timeout_sec")),
        "cache_bust": _opt_bool_int(data.get("cache_bust")),
        "use_journey": _opt_bool_int(data.get("use_journey")),
        "is_sandbox": _opt_bool_int(data.get("is_sandbox")),
        "bytes_discarded_mb": float(data.get("bytes_discarded_mb", 0.0)),
        "cache_hit_count": int(data.get("cache_hit_count", 0) or 0),
        "cache_hit_pct": float(data.get("cache_hit_pct", 0.0) or 0.0),
        "cdn_cache_warning": _opt_bool_int(bool(data.get("cdn_cache_warning", False))),
        "ram_mb": float(data.get("ram_mb", 50.0)),
        "verdict": data.get("verdict", "PASSED"),
        "status_label": data.get("status_label", "PASSED (Completed)"),
        "knee_vus": int(data.get("knee_vus", 0)),
        "knee_rps": int(data.get("knee_rps", 0)),
        "knee_p95_ms": knee_p95_val,
        "bottleneck_summary": data.get("bottleneck_summary", "Completed successfully."),
        "capacity_reason": capacity_reason,
        "linear_range": linear_range,
        "optimal_point": optimal_point,
        "cliff_point": cliff_point,
        "latency_breakdown_json": latency_breakdown_json,
        "steps_json": steps_json,
        "started_at": data.get("started_at"),
        "ended_at_iso": data.get("ended_at_iso"),
        "capacity_checked": capacity_checked,
        "timeseries_json": timeseries_json,
        "step_metrics_json": step_metrics_json,
        "failure_breakdown_json": failure_breakdown_json,
        "crash_summary_json": crash_summary_json,
        "timeline_points_json": timeline_points_json,
        "created_at": float(data.get("created_at", time.time())),
    }

    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO test_runs (
                    run_id, user_id, timestamp, target_url, project_name, guard_id, mode,
                    target_vus, peak_vus, duration_sec, elapsed_sec,
                    peak_rps, avg_rps, p95_ms, error_pct, total_requests,
                    status_2xx, status_3xx, status_4xx, status_429, status_5xx, status_other,
                    timeout_count, network_error_count, failed_requests,
                    p95_ceiling_ms, max_error_pct, effective_p95_ceiling_ms, effective_max_error_pct,
                    ram_limit_mb, request_timeout_sec, cache_bust, use_journey, is_sandbox,
                    bytes_discarded_mb, cache_hit_count, cache_hit_pct, cdn_cache_warning, ram_mb, verdict, status_label, knee_vus, knee_rps,
                    knee_p95_ms, bottleneck_summary, capacity_reason, linear_range, optimal_point, cliff_point,
                    latency_breakdown_json, steps_json, started_at, ended_at_iso,
                    timeseries_json, step_metrics_json, failure_breakdown_json, crash_summary_json,
                    timeline_points_json, created_at, metrics_scope, capacity_checked
                ) VALUES (
                    :run_id, :user_id, :timestamp, :target_url, :project_name, :guard_id, :mode,
                    :target_vus, :peak_vus, :duration_sec, :elapsed_sec,
                    :peak_rps, :avg_rps, :p95_ms, :error_pct, :total_requests,
                    :status_2xx, :status_3xx, :status_4xx, :status_429, :status_5xx, :status_other,
                    :timeout_count, :network_error_count, :failed_requests,
                    :p95_ceiling_ms, :max_error_pct, :effective_p95_ceiling_ms, :effective_max_error_pct,
                    :ram_limit_mb, :request_timeout_sec, :cache_bust, :use_journey, :is_sandbox,
                    :bytes_discarded_mb, :cache_hit_count, :cache_hit_pct, :cdn_cache_warning, :ram_mb, :verdict, :status_label, :knee_vus, :knee_rps,
                    :knee_p95_ms, :bottleneck_summary, :capacity_reason, :linear_range, :optimal_point, :cliff_point,
                    :latency_breakdown_json, :steps_json, :started_at, :ended_at_iso,
                    :timeseries_json, :step_metrics_json, :failure_breakdown_json, :crash_summary_json,
                    :timeline_points_json, :created_at, :metrics_scope, :capacity_checked
                ) ON CONFLICT(run_id) DO NOTHING
                """,
                run_record,
            )
    finally:
        conn.close()

    existing = get_run(run_record["run_id"])
    if existing is None:
        raise ValueError("A different operator already owns this run ID.")
    return existing


def clear_runs() -> None:
    """Clear custom test runs completely."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM test_runs WHERE user_id = ?", (request_owner.get(),))
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    capacity_checked = bool(d.pop("capacity_checked", 0))
    if not capacity_checked or not d["knee_vus"]:
        d.update(CAPACITY_UNAVAILABLE)
        if "linear_range" in d and not d["linear_range"]:
            d["linear_range"] = "Unavailable"
        if "optimal_point" in d and not d["optimal_point"]:
            d["optimal_point"] = "Unavailable"
        if "cliff_point" in d and not d["cliff_point"]:
            d["cliff_point"] = "Unavailable"

    for field in ("timeseries", "step_metrics", "steps", "failure_breakdown", "timeline_points"):
        key = field + "_json"
        if key in d:
            try:
                parsed = json.loads(d[key]) if d[key] is not None else []
                d[field] = parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                d[field] = []

    if "timeline_points" in d and not d["timeline_points"] and d.get("timeseries"):
        d["timeline_points"] = _downsample_timeline_points([], fallback_ts=d["timeseries"], max_points=600)

    if "crash_summary_json" in d:
        try:
            parsed_cs = json.loads(d["crash_summary_json"]) if d["crash_summary_json"] is not None else None
        except (ValueError, TypeError):
            parsed_cs = None
        d["crash_summary"] = parsed_cs if isinstance(parsed_cs, dict) else None

    if "latency_breakdown_json" in d:
        try:
            parsed_lb = json.loads(d["latency_breakdown_json"]) if d["latency_breakdown_json"] is not None else None
        except (ValueError, TypeError):
            parsed_lb = None
        d["latency_breakdown"] = _normalize_latency_breakdown(parsed_lb)

    if "step_metrics_json" in d:
        d["step_metrics"] = journey_step_metadata(d["step_metrics"])
        d["step_metrics_json"] = json.dumps(d["step_metrics"])

    if "steps" in d and not d["steps"] and d.get("timeseries"):
        derived_steps, _ = _aggregate_steps(
            d["timeseries"],
            target_vus=d.get("target_vus", 0),
            p95_ceiling_ms=d.get("effective_p95_ceiling_ms") or d.get("p95_ceiling_ms") or 2000.0,
            max_error_pct=d.get("effective_max_error_pct") if d.get("effective_max_error_pct") is not None else (
                d.get("max_error_pct") if d.get("max_error_pct") is not None else 2.0
            ),
        )
        d["steps"] = derived_steps

    for flag in ("cache_bust", "use_journey", "is_sandbox", "cdn_cache_warning"):
        if flag in d and d[flag] is not None:
            d[flag] = bool(d[flag])

    # Map frontend compatibility keys for wireframe UI table
    d["id"] = d["run_id"]
    proj_val = str(d.get("project_name") or "").strip()
    if proj_val or "timeseries_json" in d:
        d["project_name"] = proj_val
    else:
        d.pop("project_name", None)
    d["target_url"] = d["target"] = target_template(d["target_url"])
    d["guardToken"] = d["guard_id"]
    d["peakVus"] = d["peak_vus"]
    d["duration"] = d["duration_sec"]
    d["peakRps"] = d["peak_rps"]
    if d.get("knee_p95_ms") is not None:
        d["knee_p95_ms"] = round(float(d["knee_p95_ms"]), 1)
    if d["metrics_scope"] == "whole_run" and not d["total_requests"]:
        d["p95_ms"] = d["error_pct"] = None
    else:
        if d.get("p95_ms") is not None:
            d["p95_ms"] = round(float(d["p95_ms"]), 1)
        if d.get("error_pct") is not None:
            d["error_pct"] = round(float(d["error_pct"]), 1)

    if d["p95_ms"] is not None:
        p95_val = d["p95_ms"]
        d["p95"] = f"{int(p95_val)} ms" if float(p95_val).is_integer() else f"{p95_val:.1f} ms"
    else:
        d["p95"] = "Unavailable"
    d["status"] = d["status_label"]
    d["verdictCategory"] = d["verdict"]
    return d

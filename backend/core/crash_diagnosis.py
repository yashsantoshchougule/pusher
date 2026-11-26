"""Shared crash & failure-point classification helpers for Pusher load telemetry."""

from __future__ import annotations

import math
from typing import Any


def classify_error_code(status_code: int, timed_out: bool) -> str:
    """Normalize HTTP or transport failure into a diagnostic error key."""
    if timed_out:
        return "TIMEOUT"
    if status_code == 0:
        return "CONNECTION_REFUSED"
    return str(int(status_code))


def plain_reason_for_error(
    primary_code: str | None,
    error_rate_pct: float = 0.0,
    p95_ms: float = 0.0,
) -> str:
    """Map the primary failure cause or slowness into a beginner-friendly sentence."""
    code = str(primary_code or "").upper()
    if code == "500":
        return "Server code crashed (Internal Server Error)"
    if code in {"502", "503"}:
        return "Server overloaded or ran out of memory/workers"
    if code in {"504", "TIMEOUT"}:
        return "Request timed out — server froze under load"
    if code == "429":
        return "Rate limit blocked incoming users"
    if code == "CONNECTION_REFUSED":
        return "Server stopped accepting connections"
    if code == "EXTRACTION_FAILED":
        return "Response payload missing required workflow field"
    if code.startswith("4"):
        return f"Endpoint rejected requests with HTTP {code}"
    if code.startswith("5"):
        return f"Upstream server error under load (HTTP {code})"
    if error_rate_pct >= 1.0:
        return "Elevated request failure rate observed under load"
    if p95_ms > 800.0:
        return "Response times slowed down under concurrency"
    return "Handled traffic smoothly with healthy latency"


def histogram_percentile(hist: dict[int, int], sample_count: int, pct: int = 95) -> float:
    """Compute percentile (ms) from a sparse millisecond bucket dict."""
    if sample_count <= 0 or not hist:
        return 0.0
    rank = max(1, (sample_count * pct + 99) // 100)
    seen = 0
    for bucket_ms in sorted(hist):
        seen += int(hist[bucket_ms])
        if seen >= rank:
            return round(float(bucket_ms), 1)
    return 0.0


def _part_health(error_rate_pct: float, p95_ms: float, status_codes: dict[str, int], total_requests: int) -> str:
    if total_requests <= 0:
        return "HEALTHY"
    severe_count = sum(
        count
        for code, count in status_codes.items()
        if str(code) in {"TIMEOUT", "CONNECTION_REFUSED"} or str(code).startswith("5")
    )
    severe_pct = (severe_count / total_requests) * 100.0 if total_requests else 0.0
    if error_rate_pct >= 5.0 or (severe_count >= 2 and severe_pct >= 2.0):
        return "CRASHING"
    if error_rate_pct >= 1.0 or p95_ms > 800.0 or severe_count > 0:
        return "SLOWING"
    return "HEALTHY"


def _compute_safe_max_vus(
    timeseries: list[dict[str, Any]],
    peak_vus: int,
    target_vus: int,
    first_error_vus: int | None,
    p95_ceiling_ms: float,
    status_label: str,
) -> int:
    clean_vus: list[int] = []
    for sample in timeseries or []:
        if not isinstance(sample, dict):
            continue
        vus_val = int(sample.get("vus") or sample.get("active_vus") or 0)
        err_val = float(sample.get("error_pct") or 0.0)
        p95_val = float(sample.get("p95_ms") or 0.0)
        if vus_val > 0 and err_val < 1.0 and p95_val <= max(800.0, p95_ceiling_ms):
            clean_vus.append(vus_val)

    if status_label == "SMOOTH":
        measured_max = max(peak_vus or 0, max(clean_vus, default=0))
        return measured_max if measured_max > 0 else (target_vus or 0)

    if first_error_vus is not None and first_error_vus > 0:
        below_err = [v for v in clean_vus if v < first_error_vus]
        if below_err:
            return max(below_err)
        return max(0, first_error_vus - 1)

    return max(clean_vus, default=0)


def compute_crash_diagnosis(
    part_records: dict[str, dict[str, Any]] | list[dict[str, Any]],
    *,
    timeseries: list[dict[str, Any]] | None = None,
    peak_vus: int = 0,
    target_vus: int = 0,
    total_requests: int = 0,
    failed_requests: int = 0,
    overall_p95_ms: float = 0.0,
    p95_ceiling_ms: float = 1500.0,
    circuit_status: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build ranked `failure_breakdown` list and top-level `crash_summary` verdict."""
    records = list(part_records.values()) if isinstance(part_records, dict) else list(part_records or [])
    breakdown: list[dict[str, Any]] = []

    earliest_sec: int | None = None
    earliest_vus: int | None = None
    earliest_part: str | None = None
    earliest_primary_code: str | None = None
    global_codes: dict[str, int] = {}

    for rec in records:
        tot = int(rec.get("total_requests", 0))
        fail = int(rec.get("failed_requests", 0))
        err_pct = round((fail / tot) * 100.0, 1) if tot > 0 else 0.0
        lat_sum = float(rec.get("latency_sum", 0.0))
        lat_count = int(rec.get("latency_samples", 0))
        avg_ms = (
            round(lat_sum / lat_count, 1)
            if lat_count > 0
            else round(float(rec.get("avg_latency_ms", 0.0)), 1)
        )
        p95_val = rec.get("p95_latency_ms")
        if p95_val is None:
            hist = rec.get("latency_hist") or {}
            p95_val = histogram_percentile(hist, lat_count, 95)
        else:
            p95_val = round(float(p95_val), 1)

        raw_codes = rec.get("status_codes") or {}
        status_codes = {str(k): int(v) for k, v in raw_codes.items() if int(v) > 0}
        for k, v in status_codes.items():
            global_codes[k] = global_codes.get(k, 0) + v

        primary_code = (
            max(status_codes.items(), key=lambda item: item[1])[0]
            if status_codes
            else None
        )
        health = _part_health(err_pct, p95_val, status_codes, tot)
        reason = plain_reason_for_error(primary_code, err_pct, p95_val)

        fe_sec = rec.get("first_error_at_sec")
        fe_vus = rec.get("first_error_at_vus")
        if fail > 0 and fe_sec is not None:
            fe_sec_i = int(fe_sec)
            fe_vus_i = int(fe_vus) if fe_vus is not None else 0
            if earliest_sec is None or fe_sec_i < earliest_sec or (
                fe_sec_i == earliest_sec and fe_vus_i < (earliest_vus or 0)
            ):
                earliest_sec = fe_sec_i
                earliest_vus = fe_vus_i
                earliest_part = str(rec.get("part_name") or f"{rec.get('method', 'GET')} {rec.get('path', '/')}")
                earliest_primary_code = primary_code
        else:
            fe_sec_i = fe_sec if (fail > 0 and fe_sec is not None) else None
            fe_vus_i = fe_vus if (fail > 0 and fe_vus is not None) else None

        breakdown.append({
            "part_name": str(rec.get("part_name") or f"{rec.get('method', 'GET')} {rec.get('path', '/')}"),
            "method": str(rec.get("method") or "GET").upper(),
            "path": str(rec.get("path") or "/"),
            "total_requests": tot,
            "failed_requests": fail,
            "error_rate_pct": err_pct,
            "avg_latency_ms": avg_ms,
            "p95_latency_ms": p95_val,
            "status_codes": status_codes,
            "first_error_at_sec": fe_sec_i,
            "first_error_at_vus": fe_vus_i,
            "health_status": health,
            "plain_reason": reason,
        })

    rank_order = {"CRASHING": 0, "SLOWING": 1, "HEALTHY": 2}
    breakdown.sort(
        key=lambda item: (
            rank_order.get(item["health_status"], 2),
            -float(item["error_rate_pct"]),
            -int(item["failed_requests"]),
            -float(item["p95_latency_ms"]),
        )
    )

    overall_err_pct = round((failed_requests / total_requests) * 100.0, 1) if total_requests else 0.0
    any_crashing = any(b["health_status"] == "CRASHING" for b in breakdown)
    any_slowing = any(b["health_status"] == "SLOWING" for b in breakdown)
    tripped_err = "TRIPPED" in str(circuit_status or "").upper() and failed_requests > 0

    if any_crashing or overall_err_pct >= 5.0 or tripped_err:
        status_label = "CRASHED / FAILING"
    elif any_slowing or overall_err_pct >= 1.0 or (overall_p95_ms and overall_p95_ms > 800.0):
        status_label = "SLOWED DOWN"
    else:
        status_label = "SMOOTH"

    primary_global_code = earliest_primary_code or (
        max(global_codes.items(), key=lambda item: item[1])[0]
        if global_codes
        else None
    )

    safe_max_vus = _compute_safe_max_vus(
        timeseries or [],
        peak_vus=peak_vus,
        target_vus=target_vus,
        first_error_vus=earliest_vus,
        p95_ceiling_ms=p95_ceiling_ms,
        status_label=status_label,
    )

    if total_requests == 0:
        verdict_sentence = "Waiting for requests — live crash and health diagnosis will update automatically."
    elif status_label == "SMOOTH":
        tested = safe_max_vus or max(peak_vus, 1)
        verdict_sentence = (
            f"Handled up to {tested} users smoothly with {overall_err_pct}% errors "
            f"and {round(float(overall_p95_ms or 0.0), 1)} ms p95 latency."
        )
    elif earliest_vus is not None and earliest_sec is not None:
        part_label = earliest_part or "primary endpoint"
        err_desc = _format_error_code_summary(primary_global_code)
        verdict_sentence = (
            f"Handled up to {safe_max_vus} users smoothly. "
            f"Started failing at {earliest_vus} users ({earliest_sec}s) on {part_label} due to {err_desc}."
        )
    else:
        verdict_sentence = (
            f"Slowed down under {max(peak_vus, target_vus)} users "
            f"({round(float(overall_p95_ms or 0.0), 1)} ms p95, {overall_err_pct}% errors)."
        )

    crash_summary = {
        "status_label": status_label,
        "safe_max_vus": safe_max_vus,
        "first_error_vus": earliest_vus,
        "first_error_sec": earliest_sec,
        "first_error_part": earliest_part,
        "primary_error_code": primary_global_code,
        "plain_english_verdict": verdict_sentence,
    }
    return breakdown, crash_summary


def _format_error_code_summary(code: str | None) -> str:
    if not code:
        return "elevated error responses"
    c = str(code).upper()
    if c == "TIMEOUT":
        return "Request Timeouts (Server Froze)"
    if c == "CONNECTION_REFUSED":
        return "Connection Refused (Server Dropped Connections)"
    reason = plain_reason_for_error(c)
    short_reason = reason.split(" — ")[0]
    return f"HTTP {c} ({short_reason})"

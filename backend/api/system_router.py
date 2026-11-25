"""
System Hardware & Resource Limits API Router
Reports host machine memory, CPU, and OS file descriptor limits for Pusher's engine guardrails.
"""

import os
import psutil
from fastapi import APIRouter
from backend.core.circuit_breakers import MAX_ERROR_PCT_CAP, MAX_P95_CEILING_MS
from backend.core.config import max_safe_ram_budget_mb
from backend.core.load_engine import (
    BASE_ENGINE_RAM_MB, DEFAULT_RAM_CEILING_MB, MAX_REQUESTED_VUS, RAM_PER_VU_MB,
    RUSH_WARMUP_MIN_VUS, RUSH_WARMUP_RATIO, RUSH_WARMUP_SECONDS, STEP_RAMP_MIN_SECONDS, STEP_RAMP_RATIOS,
    calculate_max_allowed_vus, get_os_fd_cap, get_os_fd_limits,
)

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/limits")
async def get_system_limits():
    """
    Returns actual physical hardware limits alongside Pusher's locked engineering constraints:
    - RAM budget capped at 4 GB or 75% of host RAM, whichever is lower
    - 70% OS File-Descriptor Cap
    - 500 MB default ceiling (2,250 VUs)
    """
    # Detect total physical RAM in MB
    ram_detected = True
    try:
        total_ram_bytes = psutil.virtual_memory().total
        total_system_ram_mb = int(total_ram_bytes / (1024 * 1024))
    except Exception:
        total_system_ram_mb = 1024  # Conservative fallback if psutil fails
        ram_detected = False

    max_safe_ram_mb = max_safe_ram_budget_mb(total_system_ram_mb)
    fd_soft, fd_hard = get_os_fd_limits()
    max_vus_at_default = calculate_max_allowed_vus(DEFAULT_RAM_CEILING_MB)
    max_worker_vus = max(1, min(MAX_REQUESTED_VUS, get_os_fd_cap()))

    return {
        "total_system_ram_mb": total_system_ram_mb,
        "ram_detected": ram_detected,
        "max_safe_ram_mb": max_safe_ram_mb,
        "default_ram_limit_mb": DEFAULT_RAM_CEILING_MB,
        "base_engine_ram_mb": BASE_ENGINE_RAM_MB,
        "ram_per_vu_mb": RAM_PER_VU_MB,
        "max_vus_at_default": max_vus_at_default,
        "effective_max_vus_at_default": min(max_vus_at_default, max_worker_vus),
        "max_worker_vus": max_worker_vus,
        "max_p95_ceiling_ms": MAX_P95_CEILING_MS,
        "max_error_pct_cap": MAX_ERROR_PCT_CAP,
        "request_timeout_bounds": {"min": 2.0, "max": 10.0, "default": 5.0},
        "cpu_count": os.cpu_count() or 1,
        "traffic_schedule": {
            "step_ratios": STEP_RAMP_RATIOS,
            "step_min_seconds": STEP_RAMP_MIN_SECONDS,
            "rush_warmup_seconds": RUSH_WARMUP_SECONDS,
            "rush_warmup_ratio": RUSH_WARMUP_RATIO,
            "rush_warmup_min_vus": RUSH_WARMUP_MIN_VUS,
        },
        "fd_cap_pct": 70,
        "open_files_soft": fd_soft,
        "open_files_hard": fd_hard,
    }

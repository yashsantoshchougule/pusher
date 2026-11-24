"""
System Hardware & Resource Limits API Router
Reports host machine memory, CPU, and OS file descriptor limits for Pusher's engine guardrails.
"""

import os
import psutil
from fastapi import APIRouter
from backend.core.circuit_breakers import MAX_P95_CEILING_MS
from backend.core.load_engine import (
    BASE_ENGINE_RAM_MB, DEFAULT_RAM_CEILING_MB, MAX_REQUESTED_VUS, RAM_PER_VU_MB,
    RUSH_WARMUP_MIN_VUS, RUSH_WARMUP_RATIO, RUSH_WARMUP_SECONDS, STEP_RAMP_MIN_SECONDS, STEP_RAMP_RATIOS,
    calculate_max_allowed_vus, get_os_fd_cap,
)

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/limits")
async def get_system_limits():
    """
    Returns actual physical hardware limits alongside Pusher's locked engineering constraints:
    - 75% Host RAM Ceiling
    - 70% OS File-Descriptor Cap
    - 500 MB default ceiling (2,250 VUs)
    """
    # Detect total physical RAM in MB
    try:
        total_ram_bytes = psutil.virtual_memory().total
        total_system_ram_mb = int(total_ram_bytes / (1024 * 1024))
    except Exception:
        total_system_ram_mb = 16384  # 16 GB fallback

    max_safe_ram_mb = int(total_system_ram_mb * 0.75)

    # Detect OS File Descriptor limits if available
    fd_soft = 2048
    fd_hard = 8192
    if hasattr(os, "getrlimit") and hasattr(os, "RLIMIT_NOFILE"):
        try:
            fd_soft, fd_hard = os.getrlimit(os.RLIMIT_NOFILE)
        except Exception:
            pass

    return {
        "total_system_ram_mb": total_system_ram_mb,
        "max_safe_ram_mb": max_safe_ram_mb,
        "default_ram_limit_mb": DEFAULT_RAM_CEILING_MB,
        "base_engine_ram_mb": BASE_ENGINE_RAM_MB,
        "ram_per_vu_mb": RAM_PER_VU_MB,
        "max_vus_at_default": calculate_max_allowed_vus(DEFAULT_RAM_CEILING_MB),
        "max_worker_vus": max(1, min(MAX_REQUESTED_VUS, get_os_fd_cap())),
        "max_p95_ceiling_ms": MAX_P95_CEILING_MS,
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

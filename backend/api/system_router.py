"""
System Hardware & Resource Limits API Router
Reports host machine memory, CPU, and OS file descriptor limits for Pusher's engine guardrails.
"""

import math
import os
import psutil
from fastapi import APIRouter

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
    default_ram_limit_mb = 500
    base_engine_ram_mb = 50
    ram_per_vu_mb = 0.20
    max_vus_at_default = int((default_ram_limit_mb - base_engine_ram_mb) / ram_per_vu_mb)  # 2,250

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
        "default_ram_limit_mb": default_ram_limit_mb,
        "base_engine_ram_mb": base_engine_ram_mb,
        "ram_per_vu_mb": ram_per_vu_mb,
        "max_vus_at_default": max_vus_at_default,
        "fd_cap_pct": 70,
        "open_files_soft": fd_soft,
        "open_files_hard": fd_hard,
    }

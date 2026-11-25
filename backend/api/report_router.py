import json
import re
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from backend.api.auth_deps import require_operator
from pydantic import BaseModel, Field

from backend.core.report_service import (
    clear_runs,
    compare_two_runs,
    get_all_runs,
    get_run,
)

router = APIRouter(prefix="/api", tags=["Reports & History"], dependencies=[Depends(require_operator)])


class CompareRequest(BaseModel):
    base_run_id: str = Field(..., description="Baseline Run ID (Before)")
    candidate_run_id: str = Field(..., description="Candidate Run ID (After)")


@router.get("/history")
async def get_history_endpoint(
    mode: str | None = Query(None, description="Filter by traffic mode"),
    verdict: str | None = Query(None, description="Filter by safety verdict"),
    q: str | None = Query(None, description="Search term for run ID or target URL"),
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = Query(None, max_length=250),
):
    """Retrieve historical load test executions and latest scorecard KPIs."""
    try:
        return get_all_runs(mode=mode, verdict=verdict, q=q, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/history")
async def delete_history_endpoint():
    """Clear test run history and reset baseline profiles."""
    clear_runs()
    return get_all_runs()


@router.get("/reports/{run_id}")
async def get_report_endpoint(run_id: str):
    """Retrieve full capacity scorecard, Knee of the Curve analysis, and ramp metrics for a run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run '{run_id}' not found.",
        )
    return run


@router.post("/reports/compare")
async def compare_reports_endpoint(req: CompareRequest):
    """Perform mathematical Before-vs-After differential comparison between two runs."""
    try:
        return compare_two_runs(req.base_run_id, req.candidate_run_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


_EXPORT_UI_ALIASES = (
    "id",
    "target",
    "guardToken",
    "peakVus",
    "duration",
    "peakRps",
    "p95",
    "status",
    "verdictCategory",
)


@router.get("/reports/{run_id}/export")
async def export_report_endpoint(run_id: str):
    """Export complete load test scorecard and time-series as downloadable JSON."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run '{run_id}' not found.",
        )

    export_payload = {
        key: value
        for key, value in run.items()
        if key != "user_id" and not key.endswith("_json") and key not in _EXPORT_UI_ALIASES
    }
    export_payload["generator"] = "Pusher Open-Source Load-Testing Platform"
    export_payload["exported_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    content = json.dumps(export_payload, indent=2)
    safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id).strip("._") or "run"
    filename = f"report_{safe_run_id}.json"

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

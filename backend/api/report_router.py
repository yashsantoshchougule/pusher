from io import BytesIO
import json
import re
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from backend.api.auth_deps import require_operator
from pydantic import BaseModel, Field

from backend.core.db_async import run_db_read, run_db_write
from backend.core.pdf_report_service import generate_run_pdf_bytes, safe_pdf_slug
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
        return await run_db_read(get_all_runs, mode=mode, verdict=verdict, q=q, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/history")
async def delete_history_endpoint():
    """Clear test run history and reset baseline profiles."""
    await run_db_write(clear_runs)
    return await run_db_read(get_all_runs)


@router.get("/reports/{run_id}")
async def get_report_endpoint(run_id: str):
    """Retrieve full capacity scorecard, Knee of the Curve analysis, and ramp metrics for a run."""
    run = await run_db_read(get_run, run_id)
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
        return await run_db_read(compare_two_runs, req.base_run_id, req.candidate_run_id)
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
    run = await run_db_read(get_run, run_id)
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


@router.get("/reports/{run_id}/pdf")
async def export_report_pdf_endpoint(run_id: str):
    """Render and stream a vector PDF capacity + crash-diagnosis report for an owned run."""
    run = await run_db_read(get_run, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run '{run_id}' not found.",
        )

    pdf_bytes = generate_run_pdf_bytes(run)
    safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id).strip("._") or "run"
    proj_slug = safe_pdf_slug(run.get("project_name") or "", fallback="project")
    filename = f"pusher-{proj_slug}-{safe_run_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

"""Lightweight job status endpoints (poll-friendly alternative to Realtime)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..models import JobStatusResponse
from ..services.supabase_service import get_supabase
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def job_status(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        id=job["id"], status=job["status"],
        progress_pct=job.get("progress_pct", 0),
        rows_migrated=job.get("rows_migrated", 0),
        rows_total=job.get("rows_total", 0))

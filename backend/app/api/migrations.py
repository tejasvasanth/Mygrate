"""Migration job endpoints."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models import JobStartResponse, MigrationCreateRequest, MigrationJobResponse
from ..services import credential_service
from ..services.migration_service import sweep_stale_jobs
from ..services.supabase_service import get_supabase
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/migrations", tags=["migrations"])


def _to_response(job: dict[str, Any]) -> MigrationJobResponse:
    return MigrationJobResponse(**{k: v for k, v in job.items()
                                   if k in MigrationJobResponse.model_fields})


async def _resolve_credential(side: str, conn_id: str | None, conn_string: str | None,
                              user_id: str) -> str:
    """Returns a vault id for the given side of the migration."""
    sb = get_supabase()
    if conn_id:
        conn = await sb.get_connection(conn_id, user_id)
        if conn is None:
            raise HTTPException(status_code=404,
                                detail=f"Saved {side} connection not found")
        return conn["credential_vault_id"]
    if conn_string:
        return await credential_service.store_credential(conn_string)
    raise HTTPException(status_code=422,
                        detail=f"Provide {side}_connection_id or {side}_connection_string")


@router.get("", response_model=list[MigrationJobResponse])
async def list_migrations(user: dict[str, Any] = Depends(get_current_user)):
    sb = get_supabase()
    jobs = await sweep_stale_jobs(sb, await sb.list_jobs(user["id"]))
    return [_to_response(j) for j in jobs]


@router.post("", response_model=MigrationJobResponse, status_code=201)
async def create_migration(body: MigrationCreateRequest,
                           user: dict[str, Any] = Depends(get_current_user)):
    source_vault = await _resolve_credential(
        "source", body.source_connection_id, body.source_connection_string, user["id"])
    target_vault = await _resolve_credential(
        "target", body.target_connection_id, body.target_connection_string, user["id"])
    job = await get_supabase().create_job({
        "user_id": user["id"],
        "name": body.name,
        "status": "pending",
        "source_db_type": body.source_db_type,
        "target_db_type": body.target_db_type,
        "source_credential_id": source_vault,
        "target_credential_id": target_vault,
        "options": body.options.model_dump(),
    })
    return _to_response(job)


@router.get("/{job_id}", response_model=MigrationJobResponse)
async def get_migration(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    sb = get_supabase()
    job = await sb.get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    await sweep_stale_jobs(sb, [job])
    return _to_response(job)


@router.post("/{job_id}/start", response_model=JobStartResponse, status_code=202)
async def start_migration(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    """Kicks off the agent pipeline as a Celery task; returns immediately."""
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job["status"] not in ("pending", "failed", "cancelled"):
        raise HTTPException(status_code=409,
                            detail=f"Job cannot start from status '{job['status']}'")
    from ..workers.migration_worker import run_migration
    run_migration.delay(job_id, False)
    return JobStartResponse(job_id=job_id, status="queued",
                            detail="Migration pipeline queued")


@router.post("/{job_id}/cancel", response_model=JobStartResponse)
async def cancel_migration(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    sb = get_supabase()
    job = await sb.get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail="Job already finished")
    await sb.update_job(job_id, {"status": "cancelled"})
    await sb.insert_log(job_id, "warning", "pipeline", "Job cancelled by user")
    return JobStartResponse(job_id=job_id, status="cancelled", detail="Job cancelled")


@router.get("/{job_id}/plan")
async def get_plan(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("migration_plan"):
        raise HTTPException(status_code=404, detail="Plan not generated yet")
    return job["migration_plan"]


@router.post("/{job_id}/approve", response_model=JobStartResponse, status_code=202)
async def approve_plan(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    """User approves the AI plan — execution proceeds."""
    sb = get_supabase()
    job = await sb.get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job["status"] != "awaiting_approval":
        raise HTTPException(status_code=409,
                            detail=f"Job is '{job['status']}', not awaiting approval")
    from ..workers.migration_worker import run_migration
    run_migration.delay(job_id, True)
    return JobStartResponse(job_id=job_id, status="queued",
                            detail="Approved — execution queued")


@router.get("/{job_id}/semantic-report")
async def get_semantic_report(job_id: str,
                              user: dict[str, Any] = Depends(get_current_user)):
    """Semantic Mismatch Report Card — computed from the stored data profile.
    Available as soon as the Data Profiler stage has finished."""
    from ..utils.semantic_report import build_semantic_report

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("data_profile"):
        raise HTTPException(status_code=404,
                            detail="Data profile not available yet — "
                                   "the profiler has not run for this job")
    return build_semantic_report(job.get("schema_snapshot") or {},
                                 job["data_profile"])


@router.get("/{job_id}/preview-diff")
async def get_preview_diff(job_id: str,
                           user: dict[str, Any] = Depends(get_current_user)):
    """Side-by-side 'schema says vs data means' diff for plan review."""
    from ..utils.semantic_report import build_preview_diff

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("data_profile"):
        raise HTTPException(status_code=404,
                            detail="Data profile not available yet")
    return build_preview_diff(job.get("schema_snapshot") or {},
                              job["data_profile"], job.get("migration_plan"))


@router.get("/{job_id}/confidence-breakdown")
async def get_confidence_breakdown(job_id: str,
                                   user: dict[str, Any] = Depends(get_current_user)):
    """Per-table and per-column confidence; columns under 90% are flagged."""
    from ..utils.semantic_report import build_confidence_breakdown

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("validation_report"):
        raise HTTPException(status_code=404,
                            detail="Validation has not run for this job yet")
    return build_confidence_breakdown(job["validation_report"],
                                      job.get("schema_snapshot") or {},
                                      job.get("data_profile") or {})


@router.get("/{job_id}/quality-report")
async def get_quality_report(job_id: str,
                             user: dict[str, Any] = Depends(get_current_user)):
    """T1-5 — what's broken in the SOURCE, computed during profiling."""
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    quality = (job.get("data_profile") or {}).get("quality")
    if not quality:
        raise HTTPException(status_code=404,
                            detail="Data profile not available yet")
    return quality


@router.post("/{job_id}/simulate", status_code=202)
async def simulate(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    """T2-1 — queue a simulation of the approved plan. Target is untouched."""
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("migration_plan"):
        raise HTTPException(status_code=409,
                            detail="Plan must be generated before simulating")
    from ..workers.migration_worker import run_simulation_task
    run_simulation_task.delay(job_id)
    return JobStartResponse(job_id=job_id, status="queued",
                            detail="Simulation queued")


@router.get("/{job_id}/simulation")
async def get_simulation(job_id: str,
                         user: dict[str, Any] = Depends(get_current_user)):
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("simulation"):
        raise HTTPException(status_code=404, detail="No simulation has been run")
    return job["simulation"]


@router.get("/{job_id}/rollback-script")
async def get_rollback_script(job_id: str,
                              user: dict[str, Any] = Depends(get_current_user)):
    """T2-2 — downloadable manual rollback guide for the target."""
    from fastapi.responses import Response

    from ..utils.rollback import generate_rollback_script

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("migration_plan"):
        raise HTTPException(status_code=404,
                            detail="No plan exists — nothing to roll back")
    script = generate_rollback_script(job)
    ext = "js" if "mongo" in (job.get("target_db_type") or "") else "sql"
    filename = f"{job['name'].replace(' ', '_')}_rollback.{ext}"
    return Response(content=script, media_type="text/plain",
                    headers={"Content-Disposition":
                             f'attachment; filename="{filename}"'})


@router.get("/{job_id}/tables")
async def get_table_plan(job_id: str,
                         user: dict[str, Any] = Depends(get_current_user)):
    """T2-4 — per-table status in FK dependency order."""
    from ..utils.rollback import _dependency_order

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    plan = job.get("migration_plan")
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not generated yet")
    schema = job.get("schema_snapshot") or {}
    # _dependency_order returns drop order (children first); load order is
    # its reverse — parents must exist before children reference them.
    load_order = list(reversed(_dependency_order(plan, schema)))
    checkpoints = job.get("checkpoints") or {}
    skipped = set((job.get("options") or {}).get("skip_tables") or [])
    specs = {t["source_table"]: t for t in plan.get("tables", [])}

    tables = []
    for i, name in enumerate(load_order):
        cp = checkpoints.get(name) or {}
        if name in skipped:
            status = "skipped"
        elif cp.get("done"):
            status = "validated" if job.get("validation_report") else "migrated"
        elif cp.get("rows_committed"):
            status = "migrating"
        else:
            status = "pending"
        tables.append({
            "table": name,
            "target_table": specs[name].get("target_table_name") or name,
            "order": i,
            "status": status,
            "rows_committed": cp.get("rows_committed", 0),
            "estimated_rows": (schema.get("tables", {})
                               .get(name, {}).get("row_count", 0)),
            "depends_on": sorted({
                fk["ref_table"] for fk in (schema.get("tables", {})
                                           .get(name, {})
                                           .get("foreign_keys", []))
                if fk["ref_table"] in specs}),
        })
    return {"tables": tables, "load_order": load_order}


class ResumeRequest(BaseModel):
    only_tables: list[str] | None = None


@router.post("/{job_id}/resume", response_model=JobStartResponse, status_code=202)
async def resume_migration(job_id: str, body: ResumeRequest = ResumeRequest(),
                           user: dict[str, Any] = Depends(get_current_user)):
    """T2-3 — continue after a crash without re-migrating committed rows."""
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job["status"] in ("executing", "validating", "analyzing", "profiling"):
        raise HTTPException(status_code=409,
                            detail=f"Job is still active ('{job['status']}') — "
                                   f"cancel it before resuming")
    if not job.get("migration_plan"):
        raise HTTPException(status_code=409, detail="No approved plan to resume")
    from ..workers.migration_worker import run_migration
    run_migration.delay(job_id, True, True, body.only_tables)
    committed = sum(int((c or {}).get("rows_committed", 0))
                    for c in (job.get("checkpoints") or {}).values())
    return JobStartResponse(
        job_id=job_id, status="queued",
        detail=f"Resuming — {committed} already-committed row(s) will be skipped")


class ShareRequest(BaseModel):
    visibility: Literal["private", "team", "public"] = "public"
    redact_names: bool = True


@router.post("/{job_id}/share")
async def share_migration(job_id: str, body: ShareRequest,
                          user: dict[str, Any] = Depends(get_current_user)):
    """T3-2/T3-5 — create (or update) the public link and README badge."""
    from ..config import get_settings
    from ..utils.public_report import badge_markdown, make_share_token

    sb = get_supabase()
    job = await sb.get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=409,
                            detail="Only completed migrations can be shared")
    token = job.get("share_token") or make_share_token(job_id)
    await sb.update_job(job_id, {
        "share_token": token,
        "share_visibility": body.visibility,
        "share_redact_names": body.redact_names,
    })
    base = get_settings().public_base_url
    score = float((job.get("validation_report") or {}).get("confidence_score", 0))
    return {
        "token": token,
        "visibility": body.visibility,
        "redact_names": body.redact_names,
        "report_url": f"{base}/r/{token}",
        "badge_url": f"{base}/api/v1/public/{token}/badge.svg",
        "badge_markdown": badge_markdown(base, token, score),
    }


@router.get("/{job_id}/report")
async def get_report(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    """Final report from the Report Writer agent (JSON)."""
    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if not job.get("final_report"):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return job["final_report"]


@router.get("/{job_id}/report/pdf")
async def get_report_pdf(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    """Final report rendered as a downloadable PDF."""
    from fastapi.responses import Response

    from ..utils.pdf_report import render_report_pdf

    job = await get_supabase().get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    report = job.get("final_report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not generated yet")
    from ..utils.semantic_report import (
        build_confidence_breakdown, build_semantic_report)
    semantic = (build_semantic_report(job.get("schema_snapshot") or {},
                                      job["data_profile"])
                if job.get("data_profile") else None)
    breakdown = (build_confidence_breakdown(job["validation_report"],
                                            job.get("schema_snapshot") or {},
                                            job.get("data_profile") or {})
                 if job.get("validation_report") else None)
    pdf = render_report_pdf(job, report, semantic=semantic,
                            confidence_breakdown=breakdown)
    filename = f"{job['name'].replace(' ', '_')}_report.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{job_id}/logs")
async def get_logs(job_id: str, user: dict[str, Any] = Depends(get_current_user)):
    sb = get_supabase()
    job = await sb.get_job(job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    return await sb.get_logs(job_id)

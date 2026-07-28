"""Unauthenticated endpoints: templates (T3-4), shared reports (T3-2),
badges (T3-5), and the free CLI audit (T3-1).

Nothing here requires a bearer token, so every handler must be explicit about
what it exposes. Shared reports are gated on the job's own visibility flag.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import get_settings
from ..utils.public_report import (
    badge_markdown,
    badge_svg,
    build_public_report,
    make_share_token,
)
from ..utils.semantic_report import build_semantic_report
from ..utils.templates import get_template, list_templates

router = APIRouter(prefix="/api/v1", tags=["public"])


@router.get("/templates")
async def templates() -> dict[str, Any]:
    """Public template library — the SEO surface."""
    return {"templates": list_templates()}


@router.get("/templates/{slug}")
async def template_detail(slug: str) -> dict[str, Any]:
    template = get_template(slug)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


async def _shared_job(token: str) -> dict[str, Any]:
    from ..services.supabase_service import get_supabase

    job = await get_supabase().get_job_by_share_token(token)
    # A private (or unknown) token is a 404, never a 403 — a 403 would confirm
    # the report exists.
    if job is None or job.get("share_visibility") not in ("public", "team"):
        raise HTTPException(status_code=404, detail="Report not found")
    return job


@router.get("/public/{token}")
async def public_report(token: str) -> dict[str, Any]:
    """Redacted, shareable migration summary."""
    job = await _shared_job(token)
    semantic = (build_semantic_report(job.get("schema_snapshot") or {},
                                      job["data_profile"])
                if job.get("data_profile") else None)
    return build_public_report(
        job, semantic, redact_names=job.get("share_redact_names", True))


@router.get("/public/{token}/badge.svg")
async def public_badge(token: str) -> Response:
    job = await _shared_job(token)
    score = float((job.get("validation_report") or {}).get("confidence_score", 0))
    return Response(
        content=badge_svg(score), media_type="image/svg+xml",
        # Short cache: the badge should follow a re-run within the hour.
        headers={"Cache-Control": "public, max-age=3600"})


@router.get("/public/{token}/badge.md")
async def public_badge_markdown(token: str) -> dict[str, str]:
    job = await _shared_job(token)
    score = float((job.get("validation_report") or {}).get("confidence_score", 0))
    base = get_settings().public_base_url
    return {"markdown": badge_markdown(base, token, score),
            "report_url": f"{base}/r/{token}",
            "badge_url": f"{base}/api/v1/public/{token}/badge.svg"}


@router.get("/public/{token}/verify")
async def verify_token(token: str) -> dict[str, Any]:
    """Cheap existence check used by the frontend before rendering a page."""
    job = await _shared_job(token)
    return {"ok": True, "job_id": job["id"],
            "expected_token": make_share_token(job["id"])}

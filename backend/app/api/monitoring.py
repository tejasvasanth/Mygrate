"""Schema drift monitoring endpoints (T4-1 … T4-4)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..services import drift_service
from ..services.supabase_service import get_supabase
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


class AlertConfig(BaseModel):
    email: str | None = None
    slack_webhook: str | None = None
    pagerduty_key: str | None = None


class MonitorCreateRequest(BaseModel):
    job_id: str = Field(min_length=1)
    alerts: AlertConfig = AlertConfig()


def _public(monitor: dict[str, Any]) -> dict[str, Any]:
    """Never return the vault id or the full baseline blob to the client."""
    alerts = monitor.get("alerts") or {}
    return {
        "id": monitor["id"],
        "job_id": monitor.get("job_id"),
        "name": monitor.get("name"),
        "target_db_type": monitor.get("target_db_type"),
        "enabled": monitor.get("enabled", True),
        "baseline_taken_at": monitor.get("baseline_taken_at"),
        "last_checked_at": monitor.get("last_checked_at"),
        "last_health_score": monitor.get("last_health_score"),
        "baseline_table_count": len(
            (monitor.get("baseline_schema") or {}).get("tables", {})),
        "alerts_configured": {
            "email": bool(alerts.get("email")),
            "slack": bool(alerts.get("slack_webhook")),
            "pagerduty": bool(alerts.get("pagerduty_key")),
        },
    }


@router.post("", status_code=201)
async def enroll_monitor(body: MonitorCreateRequest,
                         user: dict[str, Any] = Depends(get_current_user)):
    """Enroll a completed migration in daily drift monitoring."""
    job = await get_supabase().get_job(body.job_id, user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Migration not found")
    if job.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail="Only completed migrations can be monitored — the baseline "
                   "is taken from the migrated target schema")
    monitor = await drift_service.enroll(
        job, user["id"], body.alerts.model_dump(exclude_none=True))
    return _public(monitor)


@router.get("")
async def list_monitors(user: dict[str, Any] = Depends(get_current_user)):
    return [_public(m) for m in await get_supabase().list_monitors(user["id"])]


async def _owned_monitor(monitor_id: str, user_id: str) -> dict[str, Any]:
    monitor = await get_supabase().get_monitor(monitor_id, user_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.get("/{monitor_id}")
async def get_monitor(monitor_id: str,
                      user: dict[str, Any] = Depends(get_current_user)):
    return _public(await _owned_monitor(monitor_id, user["id"]))


@router.get("/{monitor_id}/drift")
async def get_drift(monitor_id: str,
                    user: dict[str, Any] = Depends(get_current_user)):
    """Latest drift report plus the timeline of previous checks."""
    await _owned_monitor(monitor_id, user["id"])
    checks = await get_supabase().list_drift_checks(monitor_id)
    latest = checks[0] if checks else None
    return {
        "latest": latest,
        "timeline": [{"id": c["id"], "checked_at": c.get("checked_at"),
                      "has_drift": c.get("has_drift"),
                      "counts": c.get("counts"),
                      "health_score": c.get("health_score"),
                      "error": c.get("error")}
                     for c in checks],
    }


@router.post("/{monitor_id}/check", status_code=202)
async def run_check_now(monitor_id: str,
                        user: dict[str, Any] = Depends(get_current_user)):
    """Run a drift check immediately instead of waiting for the daily sweep."""
    monitor = await _owned_monitor(monitor_id, user["id"])
    result = await drift_service.run_check(monitor)
    return {"has_drift": result["drift"]["has_drift"],
            "counts": result["drift"]["counts"],
            "health_score": result["health_score"],
            "events": result["drift"]["events"]}


@router.post("/{monitor_id}/rebaseline")
async def rebaseline(monitor_id: str,
                     user: dict[str, Any] = Depends(get_current_user)):
    """Accept the current schema as the new baseline (drift acknowledged)."""
    monitor = await _owned_monitor(monitor_id, user["id"])
    schema = await drift_service.rebaseline(monitor)
    return {"ok": True, "tables": len(schema.get("tables", {}))}


@router.get("/{monitor_id}/health-report")
async def health_report(monitor_id: str,
                        user: dict[str, Any] = Depends(get_current_user)):
    """T4-4 — the monthly health summary."""
    monitor = await _owned_monitor(monitor_id, user["id"])
    checks = await get_supabase().list_drift_checks(monitor_id)
    return drift_service.monthly_health_report(monitor, checks)


@router.patch("/{monitor_id}")
async def update_monitor(monitor_id: str, enabled: bool | None = None,
                         user: dict[str, Any] = Depends(get_current_user)):
    await _owned_monitor(monitor_id, user["id"])
    if enabled is not None:
        await get_supabase().update_monitor(monitor_id, {"enabled": enabled})
    return _public(await _owned_monitor(monitor_id, user["id"]))


@router.delete("/{monitor_id}", status_code=204)
async def delete_monitor(monitor_id: str,
                         user: dict[str, Any] = Depends(get_current_user)):
    await _owned_monitor(monitor_id, user["id"])
    await get_supabase().delete_monitor(monitor_id, user["id"])

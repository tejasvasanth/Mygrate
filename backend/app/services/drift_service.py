"""Drift monitoring service (T4-1/T4-2/T4-3/T4-4).

Runs a monitor's daily check: introspect the target, diff against baseline,
persist the result, and dispatch alerts when something changed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..connectors import get_connector
from ..utils.drift import diff_schemas, health_score, snapshot_for_baseline
from ..utils.logger import get_logger
from . import credential_service, notifier
from .supabase_service import get_supabase

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_baseline(job: dict[str, Any]) -> dict[str, Any]:
    """Snapshot the TARGET schema right after a successful migration."""
    cs = await credential_service.get_credential(job["target_credential_id"])
    connector = get_connector(job["target_db_type"], cs)
    try:
        await connector.connect()
        schema = await connector.get_schema()
    finally:
        await connector.close()
    return snapshot_for_baseline(schema)


async def enroll(job: dict[str, Any], user_id: str,
                 alerts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enroll a completed migration in drift monitoring."""
    baseline = await create_baseline(job)
    sb = get_supabase()
    return await sb.create_monitor({
        "user_id": user_id,
        "job_id": job["id"],
        "name": job.get("name", "monitor"),
        "target_db_type": job["target_db_type"],
        "target_credential_id": job["target_credential_id"],
        "baseline_schema": baseline,
        "baseline_taken_at": _now(),
        "alerts": alerts or {},
        "enabled": True,
        "last_checked_at": None,
        "last_health_score": 100,
    })


async def run_check(monitor: dict[str, Any]) -> dict[str, Any]:
    """Introspect the target, diff against baseline, persist, alert."""
    sb = get_supabase()
    cs = await credential_service.get_credential(monitor["target_credential_id"])
    connector = get_connector(monitor["target_db_type"], cs)
    try:
        await connector.connect()
        current = snapshot_for_baseline(await connector.get_schema())
    finally:
        await connector.close()

    drift = diff_schemas(monitor.get("baseline_schema") or {}, current)
    score = health_score(drift)
    check = await sb.insert_drift_check({
        "monitor_id": monitor["id"],
        "job_id": monitor.get("job_id"),
        "events": drift["events"],
        "counts": drift["counts"],
        "has_drift": drift["has_drift"],
        "health_score": score,
        "checked_at": _now(),
    })
    await sb.update_monitor(monitor["id"], {
        "last_checked_at": _now(), "last_health_score": score})

    if drift["has_drift"]:
        await notifier.dispatch_drift_alert(monitor, drift, score)
    return {**check, "drift": drift, "health_score": score}


async def run_all_due_checks() -> list[dict[str, Any]]:
    """Celery-beat entrypoint: check every enabled monitor."""
    sb = get_supabase()
    results = []
    for monitor in await sb.list_monitors():
        if not monitor.get("enabled", True):
            continue
        try:
            results.append(await run_check(monitor))
        except Exception as e:  # noqa: BLE001 — one bad monitor must not
            # stop the sweep; the failure is recorded and surfaced in the UI.
            logger.error(f"Drift check failed for monitor {monitor['id']}: {e}")
            await sb.insert_drift_check({
                "monitor_id": monitor["id"], "job_id": monitor.get("job_id"),
                "events": [], "counts": {}, "has_drift": False,
                "health_score": monitor.get("last_health_score", 0),
                "error": str(e), "checked_at": _now()})
    return results


async def rebaseline(monitor: dict[str, Any]) -> dict[str, Any]:
    """Accept the current schema as the new normal (drift resolved)."""
    cs = await credential_service.get_credential(monitor["target_credential_id"])
    connector = get_connector(monitor["target_db_type"], cs)
    try:
        await connector.connect()
        current = snapshot_for_baseline(await connector.get_schema())
    finally:
        await connector.close()
    await get_supabase().update_monitor(monitor["id"], {
        "baseline_schema": current, "baseline_taken_at": _now(),
        "last_health_score": 100})
    return current


def monthly_health_report(monitor: dict[str, Any],
                          checks: list[dict[str, Any]]) -> dict[str, Any]:
    """T4-4 — the monthly email payload."""
    total_events = sum(len(c.get("events") or []) for c in checks)
    criticals = sum((c.get("counts") or {}).get("critical", 0) for c in checks)
    warnings = sum((c.get("counts") or {}).get("warning", 0) for c in checks)
    scores = [c.get("health_score", 100) for c in checks] or [100]
    avg = round(sum(scores) / len(scores), 1)
    regressions = [
        {"table": e["table"], "column": e["column"],
         **(e.get("semantic_regression") or {})}
        for c in checks for e in (c.get("events") or [])
        if e.get("semantic_regression")
    ]
    recommendations: list[str] = []
    if criticals:
        recommendations.append(
            f"{criticals} critical drift event(s) need attention — these can "
            f"lose or corrupt data.")
    for r in regressions[:5]:
        recommendations.append(
            f"{r['table']}.{r['column']} looks like a "
            f"{r.get('likely_semantic_type', 'semantic')} column — consider "
            f"{r.get('recommendation', 'reviewing its type')}.")
    if not recommendations:
        recommendations.append("No action needed. Your schema is stable.")
    return {
        "monitor_id": monitor["id"],
        "name": monitor.get("name"),
        "checks_run": len(checks),
        "health_score": avg,
        "drift_events": total_events,
        "critical_events": criticals,
        "warning_events": warnings,
        "new_semantic_issues": regressions,
        "recommendations": recommendations,
        "headline": f"Your migrated database is {avg}% healthy.",
    }

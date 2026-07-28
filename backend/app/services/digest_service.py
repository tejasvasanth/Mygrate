"""Periodic health digests (T4-4)."""
from __future__ import annotations

from ..utils.logger import get_logger
from . import notifier
from .drift_service import monthly_health_report
from .supabase_service import get_supabase

logger = get_logger(__name__)


async def send_all_digests() -> int:
    """One digest per enabled monitor. Sent even when nothing drifted —
    'your database is healthy' is the message that renews subscriptions."""
    sb = get_supabase()
    sent = 0
    for monitor in await sb.list_monitors():
        if not monitor.get("enabled", True):
            continue
        checks = await sb.list_drift_checks(monitor["id"])
        report = monthly_health_report(monitor, checks)
        try:
            await notifier.send_digest(monitor, report)
            sent += 1
        except Exception as e:  # noqa: BLE001 — one failure must not stop the rest
            logger.error(f"Digest failed for monitor {monitor['id']}: {e}")
    return sent

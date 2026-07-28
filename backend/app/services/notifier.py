"""Drift alert delivery (T4-2): email, Slack webhook, PagerDuty.

Every channel is optional and configured per monitor. Delivery failures are
logged and swallowed — a broken webhook must never fail a drift check.
"""
from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from ..config import get_settings
from ..utils.drift import CRITICAL
from ..utils.logger import get_logger

logger = get_logger(__name__)

SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def format_summary(monitor: dict[str, Any], drift: dict[str, Any],
                   score: int) -> str:
    counts = drift.get("counts", {})
    lines = [
        f"Schema drift detected on '{monitor.get('name')}' "
        f"({monitor.get('target_db_type')})",
        f"Health score: {score}/100",
        f"{counts.get('critical', 0)} critical · "
        f"{counts.get('warning', 0)} warning · {counts.get('info', 0)} info",
        "",
    ]
    for e in drift.get("events", [])[:15]:
        target = f"{e['table']}.{e['column']}" if e.get("column") else e["table"]
        lines.append(f"{SEVERITY_EMOJI.get(e['severity'], '·')} "
                     f"[{e['severity'].upper()}] {target}: {e['detail']}")
    remaining = len(drift.get("events", [])) - 15
    if remaining > 0:
        lines.append(f"…and {remaining} more event(s).")
    return "\n".join(lines)


async def _post_json(url: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()


async def send_slack(webhook_url: str, text: str) -> None:
    await _post_json(webhook_url, {"text": text})


async def send_pagerduty(routing_key: str, summary: str,
                         details: dict[str, Any]) -> None:
    await _post_json("https://events.pagerduty.com/v2/enqueue", {
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {"summary": summary[:1024], "severity": "critical",
                    "source": "migrate-drift-monitor",
                    "custom_details": details},
    })


def send_email(to_address: str, subject: str, body: str) -> None:
    """Synchronous SMTP — called via asyncio.to_thread by the dispatcher."""
    settings = get_settings()
    host = getattr(settings, "smtp_host", None)
    if not host:
        logger.info(f"SMTP not configured; would have emailed {to_address}: "
                    f"{subject}")
        return
    msg = EmailMessage()
    msg["From"] = getattr(settings, "smtp_from", "migrate@localhost")
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(getattr(settings, "smtp_port", 587))) as smtp:
        user = getattr(settings, "smtp_user", None)
        if user:
            smtp.starttls()
            smtp.login(user, getattr(settings, "smtp_password", ""))
        smtp.send_message(msg)


async def dispatch_drift_alert(monitor: dict[str, Any], drift: dict[str, Any],
                               score: int) -> dict[str, bool]:
    """Fan out to every configured channel. Returns per-channel success."""
    import asyncio

    alerts = monitor.get("alerts") or {}
    summary = format_summary(monitor, drift, score)
    has_critical = (drift.get("counts") or {}).get(CRITICAL, 0) > 0
    delivered: dict[str, bool] = {}

    if alerts.get("email"):
        try:
            await asyncio.to_thread(
                send_email, alerts["email"],
                f"[Migrate] Schema drift on {monitor.get('name')}", summary)
            delivered["email"] = True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Drift email failed: {e}")
            delivered["email"] = False

    if alerts.get("slack_webhook"):
        try:
            await send_slack(alerts["slack_webhook"], summary)
            delivered["slack"] = True
        except Exception as e:  # noqa: BLE001
            logger.error(f"Slack drift alert failed: {e}")
            delivered["slack"] = False

    # PagerDuty is reserved for CRITICAL — paging on an added index is how
    # teams learn to ignore alerts.
    if alerts.get("pagerduty_key") and has_critical:
        try:
            await send_pagerduty(
                alerts["pagerduty_key"],
                f"Critical schema drift on {monitor.get('name')}",
                {"events": drift.get("events", [])[:10],
                 "health_score": score})
            delivered["pagerduty"] = True
        except Exception as e:  # noqa: BLE001
            logger.error(f"PagerDuty drift alert failed: {e}")
            delivered["pagerduty"] = False

    logger.info(f"Drift alerts dispatched for monitor {monitor.get('id')}: "
                f"{json.dumps(delivered)}")
    return delivered


async def send_digest(monitor: dict[str, Any], report: dict[str, Any]) -> None:
    """Weekly/monthly digest — sent even when nothing drifted."""
    import asyncio

    alerts = monitor.get("alerts") or {}
    if not alerts.get("email"):
        return
    body = "\n".join([
        report["headline"], "",
        f"Checks run: {report['checks_run']}",
        f"Drift events: {report['drift_events']} "
        f"({report['critical_events']} critical, "
        f"{report['warning_events']} warning)",
        "", "Recommendations:",
        *[f"  • {r}" for r in report["recommendations"]],
    ])
    try:
        await asyncio.to_thread(
            send_email, alerts["email"],
            f"[Migrate] Health report — {report.get('name')}", body)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Digest email failed: {e}")

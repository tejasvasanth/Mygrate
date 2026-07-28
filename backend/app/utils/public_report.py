"""Public shareable migration report (T3-2) + README badge (T3-5).

Redaction is the whole product here: the shared artifact must prove the
migration happened without leaking schema, credentials, or business data.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

VISIBILITY = ("private", "team", "public")

# Manual-migration estimate: what a DBA would bill for this by hand.
MANUAL_HOURS_PER_TABLE = 2.0
MANUAL_HOURS_PER_100K_ROWS = 1.5


def _duration_seconds(job: dict[str, Any]) -> float | None:
    start, end = job.get("started_at"), job.get("completed_at")
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (e - s).total_seconds())


def estimate_manual_hours(table_count: int, rows: int) -> float:
    return round(MANUAL_HOURS_PER_TABLE * table_count
                 + MANUAL_HOURS_PER_100K_ROWS * (rows / 100_000), 1)


def anonymise_table(name: str, index: int) -> str:
    """Stable, non-reversible label. Same name → same label within a report."""
    return f"table_{index + 1}"


def build_public_report(job: dict[str, Any], semantic: dict[str, Any] | None,
                        redact_names: bool = True) -> dict[str, Any]:
    """The payload served at /r/{token}. Never includes connection strings,
    credentials, vault ids, user ids, or sample values."""
    validation = job.get("validation_report") or {}
    plan = job.get("migration_plan") or {}
    table_names = [t.get("source_table", "") for t in plan.get("tables", [])]
    rows = int(job.get("rows_migrated") or 0)
    seconds = _duration_seconds(job)
    manual_hours = estimate_manual_hours(len(table_names), rows)

    tables_out = []
    for i, name in enumerate(table_names):
        check = (validation.get("tables") or {}).get(name, {})
        tables_out.append({
            "table": anonymise_table(name, i) if redact_names else name,
            "source_rows": check.get("source_rows"),
            "target_rows": check.get("target_rows"),
            "row_count_ok": check.get("row_count_ok"),
        })

    summary = (semantic or {}).get("summary", {})
    return {
        "job_id": job.get("id"),
        "source_db_type": job.get("source_db_type"),
        "target_db_type": job.get("target_db_type"),
        "completed_at": job.get("completed_at"),
        "tables_migrated": len(table_names),
        "rows_migrated": rows,
        "confidence_score": validation.get("confidence_score", 0),
        "schema_trust_score": (semantic or {}).get("schema_trust_score"),
        # Counts only — never the column names or values behind them.
        "semantic_mismatches_caught": {
            "implicit_booleans": summary.get("implicit_boolean_count", 0),
            "implicit_enums": summary.get("implicit_enum_count", 0),
            "never_null_nullables": summary.get("never_null_nullable_count", 0),
            "dangerous_type_mismatches": summary.get("dangerous_mismatch_count", 0),
            "implicit_foreign_keys": summary.get("implicit_fk_count", 0),
            "pii_columns": summary.get("pii_column_count", 0),
            "total": summary.get("total_mismatches", 0),
        },
        "tables": tables_out,
        "duration_seconds": seconds,
        "estimated_manual_hours": manual_hours,
        "names_redacted": redact_names,
    }


def make_share_token(job_id: str, salt: str = "migrate") -> str:
    """Short, unguessable, deterministic per job — regenerating a link for the
    same job yields the same token, so old shares keep working."""
    digest = hashlib.sha256(f"{salt}:{job_id}".encode()).hexdigest()
    return digest[:16]


def badge_svg(confidence: float, label: str = "Migrated with Migrate") -> str:
    """Self-contained SVG badge (T3-5) — no external fonts or images."""
    value = f"{confidence:.1f}%"
    color = "#16A34A" if confidence >= 90 else (
        "#D97706" if confidence >= 70 else "#DC2626")
    label_w = 7 * len(label) + 16
    value_w = 7 * len(value) + 16
    total = label_w + value_w
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" \
role="img" aria-label="{label}: {value}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" \
font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{label_w / 2}" y="14">{label}</text>
    <text x="{label_w + value_w / 2}" y="14">{value}</text>
  </g>
</svg>"""


def badge_markdown(base_url: str, token: str, confidence: float) -> str:
    return (f"[![Migrated with Migrate]({base_url}/api/v1/public/{token}/badge.svg)]"
            f"({base_url}/r/{token})\n"
            f"Migrated with Migrate — {confidence:.1f}% confidence")

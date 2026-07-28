"""Rollback script generation — a manual guide to undo a completed migration
in the TARGET database. Generated from the plan; never executed by Migrate."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HEADER = """\
-- ============================================================
-- Migrate — ROLLBACK SCRIPT
-- Job: {name} ({job_id})
-- Target: {target_type}
-- Generated: {ts} UTC
--
-- WARNING: This is a manual rollback GUIDE, not an automatic
-- rollback. Review every statement before running. Dropping
-- these tables permanently deletes all migrated data.
-- ============================================================
"""


def _dependency_order(plan: dict[str, Any],
                      schema_snapshot: dict[str, Any]) -> list[str]:
    """Tables ordered so children drop before parents (reverse FK deps)."""
    specs = {t["source_table"]: t for t in plan.get("tables", [])}
    tables = list(specs)
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for name in tables:
        for fk in (schema_snapshot.get("tables", {}).get(name, {})
                   .get("foreign_keys", [])):
            if fk["ref_table"] in specs:
                deps[name].add(fk["ref_table"])
    # topological order (parents first), then reversed for dropping
    ordered: list[str] = []
    remaining = set(tables)
    while remaining:
        ready = sorted(t for t in remaining if deps[t] <= set(ordered))
        if not ready:  # cycle — fall back to whatever is left
            ready = sorted(remaining)
        ordered.extend(ready)
        remaining -= set(ready)
    return list(reversed(ordered))


def generate_rollback_script(job: dict[str, Any]) -> str:
    plan = job.get("migration_plan") or {}
    schema = job.get("schema_snapshot") or {}
    target_type = (job.get("target_db_type") or "").lower()
    specs = {t["source_table"]: t for t in plan.get("tables", [])}
    order = _dependency_order(plan, schema)

    lines = [HEADER.format(
        name=job.get("name", ""), job_id=job.get("id", ""),
        target_type=target_type,
        ts=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))]

    is_mongo = "mongo" in target_type or target_type in ("documentdb",)
    if is_mongo:
        lines.append("// Run in mongosh against the target database:\n")
        for name in order:
            tgt = specs[name].get("target_table_name") or name
            lines.append(f'db.getCollection("{tgt}").drop();')
        return "\n".join(lines) + "\n"

    lines.append("-- 1. Drop migrated tables (children before parents)\n")
    for name in order:
        tgt = specs[name].get("target_table_name") or name
        if "mysql" in target_type or target_type in (
                "mariadb", "planetscale", "aurora-mysql"):
            lines.append(f"DROP TABLE IF EXISTS `{tgt}`;")
        else:
            lines.append(f'DROP TABLE IF EXISTS "{tgt}" CASCADE;')

    # Sequences: PostgreSQL-family targets get sequence cleanup hints for
    # integer PKs that were auto-increment in the source.
    if any(f in target_type for f in ("postgres", "neon", "supabase",
                                      "cockroach", "alloydb", "timescale")):
        seq_lines = []
        for name in order:
            info = schema.get("tables", {}).get(name, {})
            pk = info.get("primary_key") or []
            tgt = specs[name].get("target_table_name") or name
            if len(pk) == 1:
                seq_lines.append(
                    f'-- DROP SEQUENCE IF EXISTS "{tgt}_{pk[0]}_seq" CASCADE;')
        if seq_lines:
            lines.append("\n-- 2. Sequences (uncomment if Migrate created them)")
            lines.extend(seq_lines)

    lines.append("\n-- End of rollback script.")
    return "\n".join(lines) + "\n"

"""Migration Simulation — apply the plan's coercions to sampled rows and show
before/after, without touching the target database."""
from __future__ import annotations

from typing import Any

from ..agents.migration_executor import MigrationExecutor

PREVIEW_ROWS = 50  # rows returned to the UI per table (of up to 1000 simulated)


def _coerce_for_target(value: Any, target_type: str | None) -> Any:
    """Type-level coercion preview on top of explicit plan transformations."""
    if value is None or not target_type:
        return value
    t = target_type.upper()
    try:
        if "BOOL" in t and not isinstance(value, bool):
            return str(value).strip().lower() in ("1", "true", "t", "yes", "y")
        if any(k in t for k in ("DECIMAL", "NUMERIC")) and isinstance(value, float):
            return round(value, 2)
        if ("INT" in t and "POINT" not in t and isinstance(value, str)
                and value.strip().lstrip("-").isdigit()):
            return int(value)
    except (ValueError, TypeError):
        return value
    return value


def simulate_table(rows: list[dict[str, Any]],
                   spec: dict[str, Any]) -> dict[str, Any]:
    """Run one table's sampled rows through the plan. Returns preview rows
    with per-cell change tracking."""
    mappings = spec.get("column_mappings", [])
    executor = MigrationExecutor.__new__(MigrationExecutor)  # transform only
    out_rows: list[dict[str, Any]] = []
    changed_total = 0
    for row in rows:
        transformed = executor._transform_row(row, mappings)  # noqa: SLF001
        for m in mappings:
            transformed[m["target_column"]] = _coerce_for_target(
                transformed[m["target_column"]], m.get("target_type"))
        changed = [
            m["target_column"] for m in mappings
            if _changed(row.get(m["source_column"]),
                        transformed.get(m["target_column"]))
        ]
        changed_total += bool(changed)
        if len(out_rows) < PREVIEW_ROWS:
            out_rows.append({
                "source": {m["source_column"]: _display(row.get(m["source_column"]))
                           for m in mappings},
                "transformed": {c: _display(v) for c, v in transformed.items()},
                "changed_columns": changed,
            })
    return {
        "target_table": spec.get("target_table_name") or spec.get("source_table"),
        "columns": [{"source": m["source_column"], "target": m["target_column"],
                     "source_type": m.get("source_type"),
                     "target_type": m.get("target_type")} for m in mappings],
        "rows": out_rows,
        "rows_simulated": len(rows),
        "rows_with_changes": changed_total,
    }


def _changed(before: Any, after: Any) -> bool:
    """Type-aware comparison. Python treats 1 == True, but a TINYINT coerced
    to BOOLEAN is exactly the change an engineer needs to see, so the type
    must participate in the comparison."""
    if isinstance(before, bool) != isinstance(after, bool):
        return True
    return _display(before) != _display(after)


def _display(v: Any) -> Any:
    """JSON-safe, comparison-stable representation."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


async def run_simulation(source, plan: dict[str, Any],
                         sample_limit: int = 1000) -> dict[str, Any]:
    """Simulate every table in the plan against fresh source samples."""
    tables: dict[str, Any] = {}
    for spec in plan.get("tables", []):
        name = spec["source_table"]
        rows = await source.sample_rows(name, sample_limit)
        tables[name] = simulate_table(rows, spec)
    return {
        "tables": tables,
        "total_rows_simulated": sum(t["rows_simulated"] for t in tables.values()),
        "total_rows_with_changes": sum(t["rows_with_changes"]
                                       for t in tables.values()),
    }

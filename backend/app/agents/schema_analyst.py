"""Agent 1 — Schema Analyst: reads and maps the full source schema."""
from __future__ import annotations

from typing import Any

from ..connectors.base import BaseConnector
from ..utils.logger import job_logger

AGENT_NAME = "schema_analyst"


class SchemaAnalyst:
    def __init__(self, source: BaseConnector, job_id: str, log_sink=None):
        self.source = source
        self.job_id = job_id
        self.log = job_logger(__name__, job_id, AGENT_NAME)
        self.log_sink = log_sink  # async callable(level, agent, message, metadata)

    async def _emit(self, level: str, message: str, metadata: dict[str, Any] | None = None):
        self.log.info(message)
        if self.log_sink:
            await self.log_sink(level, AGENT_NAME, message, metadata or {})

    async def run(self) -> dict[str, Any]:
        await self._emit("info", "Reading source schema…")
        snapshot = await self.source.get_schema()
        tables = snapshot.get("tables", {})
        total_rows = sum(t.get("row_count", 0) for t in tables.values())
        snapshot["summary"] = {
            "table_count": len(tables),
            "total_rows": total_rows,
            "tables_with_fks": [n for n, t in tables.items() if t.get("foreign_keys")],
        }
        await self._emit(
            "success",
            f"Schema analysis complete: {len(tables)} tables, {total_rows} total rows",
            {"tables": list(tables.keys())},
        )
        return snapshot

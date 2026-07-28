"""Agent 4 — Migration Executor: runs the plan in chunks with progress updates."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..connectors.base import BaseConnector
from ..utils.chunker import DEFAULT_CHUNK_SIZE, memory_usage_mb
from ..utils.logger import job_logger

AGENT_NAME = "migration_executor"
MEMORY_SOFT_CEILING_MB = 512
MIN_CHUNK_SIZE = 100


class MigrationCancelled(Exception):
    """Raised when the user cancels a running job — not a failure."""


class MigrationExecutor:
    def __init__(self, source: BaseConnector, target: BaseConnector,
                 plan: dict[str, Any], job_id: str,
                 chunk_size: int = DEFAULT_CHUNK_SIZE,
                 conflict_strategy: str = "fail",
                 error_mode: str = "fail-fast",
                 log_sink=None, progress_sink=None, cancel_check=None,
                 checkpoint_sink=None, checkpoints: dict[str, Any] | None = None,
                 only_tables: list[str] | None = None):
        self.source = source
        self.target = target
        self.plan = plan
        self.job_id = job_id
        self.chunk_size = chunk_size
        self.conflict_strategy = conflict_strategy
        self.error_mode = error_mode
        self.log = job_logger(__name__, job_id, AGENT_NAME)
        self.log_sink = log_sink        # async callable(level, agent, message, metadata)
        self.progress_sink = progress_sink  # async callable(rows_migrated, rows_total, pct)
        self.cancel_check = cancel_check    # async callable() -> bool (True = stop now)
        # T2-3 checkpointing: {table: {last_pk, rows_committed, done}}
        self.checkpoint_sink = checkpoint_sink  # async callable(table, state)
        self.checkpoints = checkpoints or {}
        # T2-4 incremental: restrict this run to a subset of the plan.
        self.only_tables = only_tables

    async def _emit(self, level: str, message: str, metadata: dict[str, Any] | None = None):
        self.log.info(message)
        if self.log_sink:
            await self.log_sink(level, AGENT_NAME, message, metadata or {})

    async def _check_cancelled(self) -> None:
        if self.cancel_check and await self.cancel_check():
            raise MigrationCancelled("Job cancelled by user")

    async def run(self) -> dict[str, Any]:
        tables = {t["source_table"]: t for t in self.plan.get("tables", [])}
        order = [n for n in self.plan.get("execution_order", list(tables)) if n in tables]
        if self.only_tables is not None:
            wanted = set(self.only_tables)
            order = [n for n in order if n in wanted]

        source_schema = await self.source.get_schema()
        rows_total = sum(
            source_schema["tables"].get(n, {}).get("row_count", 0) for n in order)
        # Rows already committed by a previous attempt count toward progress.
        rows_migrated = sum(
            int((self.checkpoints.get(n) or {}).get("rows_committed", 0))
            for n in order)
        errors: list[dict[str, Any]] = []
        per_table: dict[str, Any] = {}

        for name in order:
            await self._check_cancelled()
            spec = tables[name]
            target_table = spec.get("target_table_name") or name
            mappings = spec.get("column_mappings", [])
            src_info = source_schema["tables"].get(name, {})
            checkpoint = self.checkpoints.get(name) or {}

            if checkpoint.get("done"):
                per_table[name] = {
                    "rows_migrated": int(checkpoint.get("rows_committed", 0)),
                    "target_table": target_table, "resumed": True, "skipped": True}
                await self._emit(
                    "info",
                    f"Table '{name}' already completed in an earlier attempt "
                    f"({checkpoint.get('rows_committed', 0)} rows) — skipping.")
                continue

            resuming = checkpoint.get("last_pk") is not None
            if resuming:
                await self._emit(
                    "info",
                    f"Resuming '{name}' after primary key "
                    f"{checkpoint['last_pk']!r} "
                    f"({checkpoint.get('rows_committed', 0)} rows already "
                    f"committed) — the target table is kept as-is.")
            else:
                await self._emit("info", f"Creating target table '{target_table}'…")
            try:
                # Drop first so a retry after failure/cancel never duplicates
                # rows — but NEVER when resuming, or the committed rows the
                # checkpoint promises are already there would be destroyed.
                if not resuming:
                    try:
                        await self.target.drop_table(target_table)
                    except NotImplementedError:
                        pass
                pk = src_info.get("primary_key", [])
                mapped_pk = [self._map_col(mappings, c) for c in pk]
                nullable_by_col = {c["name"]: c.get("nullable", True)
                                   for c in src_info.get("columns", [])}
                if not resuming:
                    await self.target.create_table(
                        target_table,
                        [{"name": m["target_column"],
                          "type": m.get("target_type", "TEXT"),
                          "nullable": nullable_by_col.get(m["source_column"], True)}
                         for m in mappings],
                        primary_key=[c for c in mapped_pk if c] or None,
                    )
            except Exception as e:  # noqa: BLE001
                errors.append({"table": name, "stage": "create_table", "error": str(e)})
                await self._emit("error", f"Failed to create '{target_table}': {e}")
                if self.error_mode == "fail-fast":
                    raise
                continue

            table_rows = int(checkpoint.get("rows_committed", 0))
            chunk_no = 0
            chunk_size = self.chunk_size
            # A checkpoint is a LOWER bound: a chunk can commit and the worker
            # die before the checkpoint is written, so the target may already
            # hold up to one chunk beyond what the checkpoint claims. Resumed
            # writes must therefore be idempotent, or that overlap window
            # collides with the rows it is trying to restore.
            conflict_strategy = ("skip" if resuming and
                                 self.conflict_strategy == "fail"
                                 else self.conflict_strategy)
            if resuming and conflict_strategy != self.conflict_strategy:
                await self._emit(
                    "info",
                    f"Resumed writes to '{name}' skip rows that are already "
                    f"present, so the overlap from the interrupted chunk is "
                    f"not re-inserted.")
            source_pk = (src_info.get("primary_key") or [None])[0] \
                if len(src_info.get("primary_key") or []) == 1 else None
            async for chunk in self.source.stream_rows(
                    name, chunk_size,
                    start_after=checkpoint.get("last_pk"),
                    skip_rows=int(checkpoint.get("rows_committed", 0))
                    if source_pk is None else 0):
                await self._check_cancelled()
                chunk_no += 1
                transformed = [self._transform_row(r, mappings) for r in chunk]
                try:
                    written = await self.target.insert_rows(
                        target_table, transformed, conflict_strategy)
                except Exception as e:  # noqa: BLE001
                    if self.error_mode == "fail-fast":
                        errors.append({"table": name, "chunk": chunk_no, "error": str(e)})
                        await self._emit("error",
                                         f"Chunk {chunk_no} of '{name}' failed: {e}")
                        raise
                    # skip-errors: retry row-by-row so one bad row doesn't
                    # discard the rest of the chunk.
                    written, row_errors = await self._insert_row_by_row(
                        target_table, transformed, conflict_strategy)
                    for err in row_errors[:5]:
                        errors.append({"table": name, "chunk": chunk_no, "error": err})
                    await self._emit(
                        "warning",
                        f"Chunk {chunk_no} of '{name}': {written}/{len(transformed)} "
                        f"rows salvaged row-by-row ({len(row_errors)} bad rows).")
                table_rows += written
                rows_migrated += written
                pct = int(100 * rows_migrated / rows_total) if rows_total else 100
                mem = memory_usage_mb()
                if mem > MEMORY_SOFT_CEILING_MB and chunk_size > MIN_CHUNK_SIZE:
                    chunk_size = max(MIN_CHUNK_SIZE, chunk_size // 2)
                    await self._emit(
                        "warning",
                        f"Memory {mem:.0f}MB above {MEMORY_SOFT_CEILING_MB}MB ceiling — "
                        f"reducing chunk size to {chunk_size} for remaining tables.")
                await self._emit(
                    "info",
                    f"'{name}' chunk {chunk_no}: {written} rows "
                    f"({rows_migrated}/{rows_total} total, mem {mem:.0f}MB)",
                    {"table": name, "chunk": chunk_no, "rows": written})
                if self.progress_sink:
                    await self.progress_sink(rows_migrated, rows_total, pct)
                # Checkpoint AFTER the chunk is committed, so a crash can only
                # ever lose work — never claim rows that were not written.
                if self.checkpoint_sink and chunk:
                    last_pk = chunk[-1].get(source_pk) if source_pk else None
                    await self.checkpoint_sink(name, {
                        "last_pk": last_pk, "rows_committed": table_rows,
                        "done": False})
            self.chunk_size = chunk_size
            per_table[name] = {"rows_migrated": table_rows,
                               "target_table": target_table,
                               "resumed": resuming}
            if self.checkpoint_sink:
                await self.checkpoint_sink(name, {
                    "last_pk": None, "rows_committed": table_rows, "done": True})
            await self._emit("success", f"Table '{name}' done: {table_rows} rows migrated.")

        fk_report = await self._apply_foreign_keys(order, tables, source_schema)

        report = {
            "rows_migrated": rows_migrated,
            "rows_total": rows_total,
            "tables": per_table,
            "foreign_keys": fk_report,
            "errors": errors,
        }
        await self._emit("success",
                         f"Execution complete: {rows_migrated}/{rows_total} rows migrated.",
                         {"errors": len(errors)})
        return report

    async def _insert_row_by_row(self, target_table: str,
                                 rows: list[dict[str, Any]],
                                 conflict_strategy: str | None = None
                                 ) -> tuple[int, list[str]]:
        strategy = conflict_strategy or self.conflict_strategy
        written = 0
        row_errors: list[str] = []
        for row in rows:
            try:
                written += await self.target.insert_rows(
                    target_table, [row], strategy)
            except Exception as e:  # noqa: BLE001
                row_errors.append(str(e))
        return written, row_errors

    async def _apply_foreign_keys(self, order: list[str], tables: dict[str, Any],
                                  source_schema: dict[str, Any]) -> dict[str, Any]:
        """Post-load DDL phase: recreate FK constraints in the target, mapped
        through the plan. Runs after all data so insert order/cycles don't matter."""
        applied = 0
        skipped: list[str] = []
        target_name = {n: (tables[n].get("target_table_name") or n) for n in order}
        for name in order:
            spec = tables[name]
            mappings = spec.get("column_mappings", [])
            for fk in source_schema["tables"].get(name, {}).get("foreign_keys", []):
                if fk["ref_table"] not in target_name:
                    continue  # referenced table not migrated
                col = self._map_col(mappings, fk["column"])
                ref_spec = tables[fk["ref_table"]]
                ref_col = self._map_col(ref_spec.get("column_mappings", []),
                                        fk["ref_column"])
                if not col or not ref_col:
                    continue
                label = f"{target_name[name]}.{col} -> {target_name[fk['ref_table']]}.{ref_col}"
                try:
                    await self.target.add_foreign_key(
                        target_name[name], col, target_name[fk["ref_table"]], ref_col)
                    applied += 1
                except NotImplementedError:
                    skipped.append(label)
                except Exception as e:  # noqa: BLE001
                    skipped.append(label)
                    await self._emit("warning", f"Could not add FK {label}: {e}")
        if applied or skipped:
            await self._emit("info",
                             f"Foreign keys: {applied} applied, {len(skipped)} skipped.",
                             {"skipped": skipped})
        return {"applied": applied, "skipped": skipped}

    @staticmethod
    def _map_col(mappings: list[dict[str, Any]], source_col: str) -> str | None:
        for m in mappings:
            if m["source_column"] == source_col:
                return m["target_column"]
        return None

    def _transform_row(self, row: dict[str, Any], mappings: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for m in mappings:
            value = row.get(m["source_column"])
            value = self._apply_transform(value, m.get("transformation"))
            # Serialise nested structures for relational targets.
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            out[m["target_column"]] = value
        return out

    @staticmethod
    def _apply_transform(value: Any, op: str | None) -> Any:
        """Interpreter for the closed transformation vocabulary the strategist
        emits. Unknown/free-text ops are matched loosely; failures return the
        original value rather than corrupting data."""
        if value is None or not op:
            return value
        op = op.lower()
        try:
            if "boolean" in op or op == "to_bool":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("1", "true", "t", "yes", "y")
            if op in ("to_int", "to_integer"):
                return int(float(value))
            if op == "to_float":
                return float(value)
            if op in ("to_string", "to_text"):
                return str(value)
            if "datetime" in op or op == "parse_date":
                if isinstance(value, datetime):
                    return value
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if op == "json_stringify":
                return json.dumps(value, default=str)
        except (ValueError, TypeError):
            return value
        return value

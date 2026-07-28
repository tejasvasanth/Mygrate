"""Orchestrates the 5-agent pipeline for a migration job."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..agents import (
    DataProfiler,
    MappingStrategist,
    MigrationExecutor,
    ReportWriter,
    SchemaAnalyst,
    ValidationAuditor,
)
from ..agents.migration_executor import MigrationCancelled
from ..connectors import get_connector
from ..utils.logger import get_logger
from . import credential_service
from .supabase_service import get_supabase

logger = get_logger(__name__)

# Active statuses whose updated_at hasn't moved for this long are considered
# orphaned (worker crashed / was killed) and get marked failed.
STALE_AFTER_SECONDS = 300
ACTIVE_STATUSES = ("analyzing", "profiling", "planning", "executing", "validating")


async def sweep_stale_jobs(sb, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark active jobs with a stale heartbeat (updated_at) as failed.
    The worker touches updated_at on every chunk/stage, so it doubles as a
    heartbeat. Returns the jobs list with statuses corrected in place."""
    now = datetime.now(timezone.utc)
    for job in jobs:
        if job.get("status") not in ACTIVE_STATUSES:
            continue
        ts = job.get("updated_at")
        if not ts:
            continue
        try:
            updated = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if (now - updated).total_seconds() > STALE_AFTER_SECONDS:
            errors = list(job.get("error_log") or [])
            errors.append({"at": _now(),
                           "error": "Worker heartbeat lost — job marked failed. "
                                    "Restart it to run again from a clean slate."})
            await sb.update_job(job["id"], {
                "status": "failed", "error_log": errors, "completed_at": _now()})
            await sb.insert_log(job["id"], "error", "pipeline",
                                "Worker heartbeat lost; job marked as failed.")
            job["status"] = "failed"
            job["error_log"] = errors
    return jobs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MigrationPipeline:
    """Runs analyze → profile → plan → (approval gate) → execute → validate."""

    def __init__(self, job_id: str, supabase=None):
        self.job_id = job_id
        self.sb = supabase or get_supabase()

    async def _log(self, level: str, agent: str, message: str,
                   metadata: dict[str, Any] | None = None) -> None:
        await self.sb.insert_log(self.job_id, level, agent, message, metadata)

    async def _set_status(self, status: str, **extra: Any) -> None:
        await self.sb.update_job(self.job_id, {"status": status, **extra})

    async def _progress(self, rows_migrated: int, rows_total: int, pct: int) -> None:
        await self.sb.update_job(self.job_id, {
            "rows_migrated": rows_migrated, "rows_total": rows_total,
            "progress_pct": pct,
        })

    async def _checkpoint(self, table: str, state: dict[str, Any]) -> None:
        """T2-3 — persist per-table resume state after every committed chunk."""
        job = await self.sb.get_job(self.job_id) or {}
        checkpoints = dict(job.get("checkpoints") or {})
        # last_pk must survive a JSON round-trip; anything exotic is dropped
        # and the table falls back to restarting from the beginning.
        last_pk = state.get("last_pk")
        if not isinstance(last_pk, (int, float, str, type(None))):
            last_pk = None
        checkpoints[table] = {**state, "last_pk": last_pk, "at": _now()}
        await self.sb.update_job(self.job_id, {"checkpoints": checkpoints})

    async def _resolve_connection_string(self, job: dict[str, Any], side: str) -> str:
        """side: 'source' | 'target'. Credential fetched from Vault, in-memory only."""
        vault_id = job.get(f"{side}_credential_id")
        if not vault_id:
            raise ValueError(f"Job has no {side} credential configured")
        return await credential_service.get_credential(vault_id)

    async def _is_cancelled(self) -> bool:
        job = await self.sb.get_job(self.job_id)
        return bool(job) and job.get("status") == "cancelled"

    async def run(self, execute: bool | None = None,
                  resume: bool = False,
                  only_tables: list[str] | None = None) -> dict[str, Any]:
        """Full pipeline. If the job is a dry run and not yet approved, stops
        after planning with status awaiting_approval.

        When continuing an approved job (execute=True) the stored snapshot,
        profile and plan are reused — the plan the user approved is exactly
        the plan that runs; nothing is regenerated."""
        job = await self.sb.get_job(self.job_id)
        if job is None:
            raise ValueError(f"Job {self.job_id} not found")
        options = job.get("options") or {}
        chunk_size = int(options.get("chunk_size", 1000))
        conflict_strategy = options.get("conflict_strategy", "fail")
        error_mode = options.get("error_mode", "fail-fast")
        dry_run = bool(options.get("dry_run", True)) if execute is None else not execute
        resume_approved = bool(
            execute and job.get("migration_plan") and job.get("schema_snapshot"))

        source_cs = await self._resolve_connection_string(job, "source")
        target_cs = await self._resolve_connection_string(job, "target")
        source = get_connector(job["source_db_type"], source_cs)
        target = get_connector(job["target_db_type"], target_cs)

        try:
            await source.connect()
            await target.connect()

            if resume_approved:
                schema = job["schema_snapshot"]
                profile = job.get("data_profile") or {}
                plan = job["migration_plan"]
                if resume:
                    # Keep progress and checkpoints — that is the entire point.
                    await self.sb.update_job(self.job_id, {
                        "completed_at": None, "validation_report": None})
                    await self._log("info", "pipeline",
                                    "Resuming from the last committed chunk.")
                else:
                    await self.sb.update_job(self.job_id, {
                        "progress_pct": 0, "rows_migrated": 0,
                        "checkpoints": {},
                        "completed_at": None, "validation_report": None})
                    await self._log("info", "pipeline",
                                    "Executing the approved plan (no re-planning).")
            else:
                # Reset progress so a retry after failure starts from a clean slate.
                await self._set_status("analyzing", started_at=_now(),
                                       progress_pct=0, rows_migrated=0,
                                       completed_at=None, validation_report=None)

                # 1 — Schema Analyst
                schema = await SchemaAnalyst(source, self.job_id, self._log).run()
                await self.sb.update_job(self.job_id, {"schema_snapshot": schema})
                if await self._is_cancelled():
                    raise MigrationCancelled("cancelled during analysis")

                # 2 — Data Profiler
                await self._set_status("profiling")
                profile = await DataProfiler(source, schema, self.job_id, self._log).run()
                await self.sb.update_job(self.job_id, {"data_profile": profile})
                if await self._is_cancelled():
                    raise MigrationCancelled("cancelled during profiling")

                # 3 — Mapping Strategist (AI brain)
                await self._set_status("planning")
                plan = await MappingStrategist(
                    schema, profile, job["source_db_type"], job["target_db_type"],
                    options, self.job_id, self._log).run()
                await self.sb.update_job(self.job_id, {"migration_plan": plan})

                if dry_run:
                    await self._set_status("awaiting_approval")
                    await self._log("info", "pipeline",
                                    "Plan ready — awaiting user approval before execution.")
                    return {"status": "awaiting_approval", "plan": plan}

            # 4 — Migration Executor
            await self._set_status("executing")
            job_now = await self.sb.get_job(self.job_id) or {}
            exec_report = await MigrationExecutor(
                source, target, plan, self.job_id,
                chunk_size=chunk_size, conflict_strategy=conflict_strategy,
                error_mode=error_mode, log_sink=self._log,
                progress_sink=self._progress,
                cancel_check=self._is_cancelled,
                checkpoint_sink=self._checkpoint,
                checkpoints=(job_now.get("checkpoints") or {}) if resume else {},
                only_tables=only_tables).run()

            # 5 — Validation Auditor (always runs)
            await self._set_status("validating")
            validation = await ValidationAuditor(
                source, target, plan, self.job_id, self._log).run()
            await self.sb.update_job(self.job_id, {"validation_report": validation})

            # 6 — Report Writer (explains score + flags; consumes all agent outputs)
            final_report = await ReportWriter(
                schema, profile, plan, exec_report, validation,
                self.job_id, self._log).run()
            await self.sb.update_job(self.job_id, {"final_report": final_report})

            await self._set_status("completed", completed_at=_now(), progress_pct=100)
            return {"status": "completed", "execution": exec_report,
                    "validation": validation, "report": final_report}

        except MigrationCancelled:
            await self._log("warning", "pipeline", "Migration stopped: cancelled by user.")
            await self.sb.update_job(self.job_id, {
                "status": "cancelled", "completed_at": _now()})
            return {"status": "cancelled"}
        except Exception as e:  # noqa: BLE001 — no silent failures
            await self._log("error", "pipeline", f"Migration failed: {e}")
            job_now = await self.sb.get_job(self.job_id) or {}
            errors = list(job_now.get("error_log") or [])
            errors.append({"at": _now(), "error": str(e)})
            await self._set_status("failed", error_log=errors, completed_at=_now())
            raise
        finally:
            await source.close()
            await target.close()

    async def execute_approved(self) -> dict[str, Any]:
        """Continue an approved job: plan already exists — run executor + auditor."""
        return await self.run(execute=True)

    async def resume_from_checkpoint(self,
                                     only_tables: list[str] | None = None
                                     ) -> dict[str, Any]:
        """T2-3 — continue a failed/interrupted job without re-migrating
        rows the checkpoints say are already committed."""
        return await self.run(execute=True, resume=True, only_tables=only_tables)

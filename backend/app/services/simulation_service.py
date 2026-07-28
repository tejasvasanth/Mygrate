"""Migration simulation (T2-1) — run the plan's coercions against sampled
source rows and store the before/after preview. Never touches the target."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..connectors import get_connector
from ..utils.logger import get_logger
from ..utils.simulate import run_simulation
from . import credential_service
from .supabase_service import get_supabase

logger = get_logger(__name__)


async def run_and_store_simulation(job_id: str,
                                   sample_limit: int = 1000) -> dict[str, Any]:
    sb = get_supabase()
    job = await sb.get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    plan = job.get("migration_plan")
    if not plan:
        raise ValueError("Cannot simulate before a migration plan exists")

    cs = await credential_service.get_credential(job["source_credential_id"])
    source = get_connector(job["source_db_type"], cs)
    await sb.insert_log(job_id, "info", "simulation",
                        f"Simulating the plan against up to {sample_limit} "
                        f"rows per table — the target is not touched.")
    try:
        await source.connect()
        result = await run_simulation(source, plan, sample_limit)
    finally:
        await source.close()

    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    await sb.update_job(job_id, {"simulation": result})
    await sb.insert_log(
        job_id, "success", "simulation",
        f"Simulation complete: {result['total_rows_with_changes']} of "
        f"{result['total_rows_simulated']} sampled rows are changed by the plan.")
    return result

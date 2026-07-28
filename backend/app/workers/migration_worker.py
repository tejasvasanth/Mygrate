"""Long-running migration tasks executed by the Celery worker."""
from __future__ import annotations

import asyncio

from ..services.migration_service import MigrationPipeline
from ..utils.logger import get_logger
from .celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=0, name="run_migration")
def run_migration(self, job_id: str, execute: bool = False,
                  resume: bool = False, only_tables: list[str] | None = None):
    """Runs the 5-agent pipeline. execute=False stops at the approval gate
    for dry-run jobs; execute=True continues an approved plan to completion.
    resume=True continues from the last committed chunk (T2-3);
    only_tables restricts the run to a subset of the plan (T2-4)."""
    logger.info(f"Worker picked up migration job {job_id}", extra={"job_id": job_id})
    pipeline = MigrationPipeline(job_id)
    result = asyncio.run(pipeline.run(execute=execute or None, resume=resume,
                                      only_tables=only_tables))
    logger.info(f"Job {job_id} finished with status {result.get('status')}",
                extra={"job_id": job_id})
    return {"job_id": job_id, "status": result.get("status")}


@celery_app.task(bind=True, max_retries=0, name="run_simulation")
def run_simulation_task(self, job_id: str):
    """T2-1 — simulate the approved plan against sampled source rows."""
    from ..services.simulation_service import run_and_store_simulation

    logger.info(f"Simulating job {job_id}", extra={"job_id": job_id})
    return asyncio.run(run_and_store_simulation(job_id))


@celery_app.task(bind=True, max_retries=0, name="check_all_drift")
def check_all_drift(self):
    """T4-1 — daily drift sweep across every enabled monitor (Celery beat)."""
    from ..services.drift_service import run_all_due_checks

    results = asyncio.run(run_all_due_checks())
    logger.info(f"Drift sweep finished: {len(results)} monitor(s) checked")
    return {"monitors_checked": len(results),
            "with_drift": sum(1 for r in results if r.get("drift", {}).get("has_drift"))}


@celery_app.task(bind=True, max_retries=0, name="send_health_digests")
def send_health_digests(self):
    """T4-4 — monthly health report per monitored database."""
    from ..services.digest_service import send_all_digests

    count = asyncio.run(send_all_digests())
    logger.info(f"Health digests sent: {count}")
    return {"digests_sent": count}

"""Celery configuration."""
from celery import Celery
from celery.schedules import crontab

from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "db_migration_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.migration_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Windows dev: run the worker with --pool=solo
    worker_hijack_root_logger=False,
    timezone="UTC",
    # Drift monitoring (T4-1) and health digests (T4-4). Start beat with:
    #   celery -A app.workers.celery_app beat
    beat_schedule={
        "daily-drift-sweep": {
            "task": "check_all_drift",
            "schedule": crontab(hour=3, minute=0),
        },
        "monthly-health-digest": {
            "task": "send_health_digests",
            "schedule": crontab(hour=8, minute=0, day_of_month="1"),
        },
    },
)

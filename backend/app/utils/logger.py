"""Structured logging. Every entry carries job_id, agent and level."""
import json
import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "job_id": getattr(record, "job_id", None),
            "agent": getattr(record, "agent", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class JobLogAdapter(logging.LoggerAdapter):
    """Binds job_id + agent onto every log record."""

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("job_id", self.extra.get("job_id"))
        extra.setdefault("agent", self.extra.get("agent"))
        return msg, kwargs


def job_logger(name: str, job_id: str, agent: str) -> JobLogAdapter:
    return JobLogAdapter(get_logger(name), {"job_id": job_id, "agent": agent})

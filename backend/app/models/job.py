"""Job status / log models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress_pct: int = 0
    rows_migrated: int = 0
    rows_total: int = 0


class JobLogEntry(BaseModel):
    id: str | None = None
    job_id: str
    level: str
    agent: str
    message: str
    metadata: dict[str, Any] = {}
    created_at: datetime | None = None


class JobStartResponse(BaseModel):
    job_id: str
    status: str
    detail: str

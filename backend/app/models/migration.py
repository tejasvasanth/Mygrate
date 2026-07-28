"""Request/response models for migration jobs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .connection import DBType

MigrationStatus = Literal[
    "pending", "analyzing", "profiling", "planning", "awaiting_approval",
    "executing", "validating", "completed", "failed", "cancelled",
]

ConflictStrategy = Literal["skip", "overwrite", "fail"]


class MigrationOptions(BaseModel):
    skip_tables: list[str] = []
    conflict_strategy: ConflictStrategy = "fail"
    dry_run: bool = True
    chunk_size: int = Field(default=1000, ge=1, le=100_000)
    error_mode: Literal["fail-fast", "skip-errors"] = "fail-fast"


class MigrationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_db_type: DBType
    target_db_type: DBType
    # Either a saved connection id or a raw connection string per side.
    source_connection_id: str | None = None
    source_connection_string: str | None = None
    target_connection_id: str | None = None
    target_connection_string: str | None = None
    options: MigrationOptions = MigrationOptions()


class MigrationJobResponse(BaseModel):
    id: str
    name: str
    status: str
    source_db_type: str
    target_db_type: str
    migration_plan: dict[str, Any] | None = None
    schema_snapshot: dict[str, Any] | None = None
    data_profile: dict[str, Any] | None = None
    # Carried on the job so the UI never has to poll separate endpoints for
    # things that may legitimately not exist yet (which would 404 on every
    # render). The dedicated endpoints remain for API/CLI consumers.
    simulation: dict[str, Any] | None = None
    checkpoints: dict[str, Any] = {}
    share_token: str | None = None
    share_visibility: str | None = None
    share_redact_names: bool | None = None
    options: dict[str, Any] = {}
    progress_pct: int = 0
    rows_migrated: int = 0
    rows_total: int = 0
    error_log: list[Any] = []
    validation_report: dict[str, Any] | None = None
    final_report: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

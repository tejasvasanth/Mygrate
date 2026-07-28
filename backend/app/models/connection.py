"""Request/response models for database connections."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DBType = Literal[
    # PostgreSQL wire-compatible
    "postgres", "postgresql", "aurora-postgres", "rds-postgres",
    "cloudsql-postgres", "alloydb", "azure-postgres", "neon", "supabase",
    "cockroachdb", "timescaledb", "redshift",
    # MySQL wire-compatible
    "mysql", "mariadb", "aurora-mysql", "rds-mysql", "cloudsql-mysql",
    "azure-mysql", "planetscale",
    # MongoDB wire-compatible
    "mongodb", "mongo", "documentdb", "cosmosdb-mongo",
    # Others
    "sqlite",
    "sqlserver", "mssql", "azure-sql",
    "bigquery", "dynamodb", "neo4j",
]


class ConnectionTestRequest(BaseModel):
    db_type: DBType
    connection_string: str = Field(min_length=1)


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    tables: list[str] = []
    # T2-5 — None means the privilege probe was inconclusive for this engine.
    has_write_access: bool | None = None
    privilege_evidence: str | None = None
    readonly_advice: dict | None = None


class ConnectionCreateRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    db_type: DBType
    connection_string: str = Field(min_length=1)
    host: str | None = None
    port: int | None = None
    database_name: str | None = None


class ConnectionResponse(BaseModel):
    """Never contains the credential — only metadata."""
    id: str
    nickname: str
    db_type: str
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    created_at: datetime | None = None

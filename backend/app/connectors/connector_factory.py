"""Returns the correct connector for a database type.

Cloud-managed databases that are wire-compatible with an open-source engine
(Aurora, RDS, Cloud SQL, AlloyDB, Azure Database, Neon, Supabase, DocumentDB,
Cosmos-Mongo, MariaDB, PlanetScale, …) resolve to that engine's connector via
the family map — no separate driver needed.
"""
from __future__ import annotations

from ..utils.db_families import DB_FAMILIES, resolve_family
from .base import BaseConnector
from .mongodb import MongoDBConnector
from .mysql import MySQLConnector
from .postgres import PostgresConnector
from .sqlite import SQLiteConnector

# family -> connector class. Heavy-dependency connectors import lazily so the
# app runs even when optional drivers (pyodbc, boto3, …) aren't installed.
_FAMILY_CONNECTORS: dict[str, type[BaseConnector] | str] = {
    "postgres": PostgresConnector,
    "mysql": MySQLConnector,
    "mongodb": MongoDBConnector,
    "sqlite": SQLiteConnector,
    "sqlserver": "sqlserver",
    "bigquery": "bigquery",
    "dynamodb": "dynamodb",
    "neo4j": "neo4j",
}


def _lazy(family: str) -> type[BaseConnector]:
    if family == "sqlserver":
        from .sqlserver import SQLServerConnector
        return SQLServerConnector
    if family == "bigquery":
        from .bigquery import BigQueryConnector
        return BigQueryConnector
    if family == "dynamodb":
        from .dynamodb import DynamoDBConnector
        return DynamoDBConnector
    if family == "neo4j":
        from .neo4j import Neo4jConnector
        return Neo4jConnector
    raise ValueError(f"No connector for family {family!r}")


def get_connector(db_type: str, connection_string: str) -> BaseConnector:
    family = resolve_family(db_type)
    cls = _FAMILY_CONNECTORS[family]
    if isinstance(cls, str):
        cls = _lazy(cls)
    return cls(connection_string)


SUPPORTED_DB_TYPES = sorted(DB_FAMILIES)

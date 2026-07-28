"""Maps every supported db_type slug to its engine family.

Many managed cloud databases are wire-compatible with an open-source engine —
they reuse that engine's connector and type rules. The family key is what the
connector registry and the type mapper actually operate on.
"""
from __future__ import annotations

# slug -> family (family == the connector/type-mapper key)
DB_FAMILIES: dict[str, str] = {
    # PostgreSQL wire-compatible
    "postgres": "postgres", "postgresql": "postgres",
    "aurora-postgres": "postgres", "rds-postgres": "postgres",
    "cloudsql-postgres": "postgres", "alloydb": "postgres",
    "azure-postgres": "postgres", "neon": "postgres", "supabase": "postgres",
    "cockroachdb": "postgres", "timescaledb": "postgres", "redshift": "postgres",
    # MySQL wire-compatible
    "mysql": "mysql", "mariadb": "mysql",
    "aurora-mysql": "mysql", "rds-mysql": "mysql",
    "cloudsql-mysql": "mysql", "azure-mysql": "mysql", "planetscale": "mysql",
    # MongoDB wire-compatible
    "mongodb": "mongodb", "mongo": "mongodb",
    "documentdb": "mongodb", "cosmosdb-mongo": "mongodb",
    # SQLite
    "sqlite": "sqlite",
    # SQL Server family
    "sqlserver": "sqlserver", "mssql": "sqlserver", "azure-sql": "sqlserver",
    # Cloud-native engines
    "bigquery": "bigquery",
    "dynamodb": "dynamodb",
    # Graph
    "neo4j": "neo4j",
}


def resolve_family(db_type: str) -> str:
    key = (db_type or "").strip().lower()
    if key not in DB_FAMILIES:
        raise ValueError(f"Unsupported database type: {db_type!r}. "
                         f"Supported: {', '.join(sorted(DB_FAMILIES))}")
    return DB_FAMILIES[key]

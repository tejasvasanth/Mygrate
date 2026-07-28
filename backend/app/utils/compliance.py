"""Live compliance matrix: which UI database types are actually usable on
this deployment, and what each one needs.

"Compliant" means: the slug resolves to an engine family, that family has a
connector, its driver is importable, and the type mapper has rules for it.
"""
from __future__ import annotations

import importlib.util
from typing import Any

from .db_families import DB_FAMILIES
from .type_mapper import SOURCE_TO_CANONICAL, CANONICAL_TO_TARGET

# family -> (pip package hint, module import name)
FAMILY_DRIVERS: dict[str, tuple[str, str]] = {
    "postgres": ("asyncpg", "asyncpg"),
    "mysql": ("aiomysql", "aiomysql"),
    "mongodb": ("pymongo", "pymongo"),
    "sqlite": ("aiosqlite", "aiosqlite"),
    "sqlserver": ("pyodbc", "pyodbc"),
    "bigquery": ("google-cloud-bigquery", "google.cloud.bigquery"),
    "dynamodb": ("boto3", "boto3"),
    "neo4j": ("neo4j", "neo4j"),
}

FAMILY_NOTES: dict[str, str] = {
    "postgres": "Wire-compatible slugs share the PostgreSQL connector.",
    "mysql": "Wire-compatible slugs share the MySQL connector.",
    "mongodb": "Wire-compatible slugs share the MongoDB connector.",
    "sqlite": "File-based; connection string is a file path or sqlite:/// URL.",
    "sqlserver": "Requires an ODBC driver for SQL Server on the host.",
    "bigquery": "Requires Google application credentials.",
    "dynamodb": "Requires AWS credentials (env or connection string params).",
    "neo4j": "Graph paradigm — tables map to node labels.",
}


def _driver_installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def build_compliance_matrix() -> dict[str, Any]:
    """One entry per supported db_type slug, grouped view for the UI."""
    driver_status = {fam: _driver_installed(mod)
                     for fam, (_, mod) in FAMILY_DRIVERS.items()}
    entries: list[dict[str, Any]] = []
    for slug in sorted(DB_FAMILIES):
        family = DB_FAMILIES[slug]
        pkg, _mod = FAMILY_DRIVERS[family]
        installed = driver_status[family]
        type_rules = (family in SOURCE_TO_CANONICAL
                      and family in CANONICAL_TO_TARGET)
        entries.append({
            "db_type": slug,
            "family": family,
            "driver_package": pkg,
            "driver_installed": installed,
            "type_rules": type_rules,
            "source_supported": installed and type_rules,
            "target_supported": installed and type_rules,
            "compliant": installed and type_rules,
            "notes": FAMILY_NOTES.get(family, ""),
        })
    return {
        "entries": entries,
        "families": {
            fam: {"driver_package": FAMILY_DRIVERS[fam][0],
                  "driver_installed": driver_status[fam],
                  "type_rules": fam in SOURCE_TO_CANONICAL
                  and fam in CANONICAL_TO_TARGET}
            for fam in FAMILY_DRIVERS
        },
        "compliant_count": sum(1 for e in entries if e["compliant"]),
        "total_count": len(entries),
    }

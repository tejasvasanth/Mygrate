"""Source read-only enforcement (T2-5).

Probes whether a source connection has write privileges and, when it does,
produces the exact GRANT statements for a least-privilege replacement user.
The probe never mutates anything: it asks the engine what it would allow.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from .db_families import resolve_family

RO_USER = "migrate_ro"


def _database_name(connection_string: str) -> str:
    path = urlparse(connection_string).path or ""
    return path.lstrip("/").split("?")[0] or "your_database"


def readonly_grant_sql(db_type: str, connection_string: str,
                       password: str = "<strong-password>") -> list[str]:
    """GRANT statements that create a read-only user for this database."""
    family = resolve_family(db_type)
    db = _database_name(connection_string)
    if family == "mysql":
        return [
            f"CREATE USER '{RO_USER}'@'%' IDENTIFIED BY '{password}';",
            f"GRANT SELECT ON `{db}`.* TO '{RO_USER}'@'%';",
            "FLUSH PRIVILEGES;",
        ]
    if family == "postgres":
        return [
            f"CREATE USER {RO_USER} WITH PASSWORD '{password}';",
            f"GRANT CONNECT ON DATABASE \"{db}\" TO {RO_USER};",
            f"GRANT USAGE ON SCHEMA public TO {RO_USER};",
            f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {RO_USER};",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT ON TABLES TO {RO_USER};",
        ]
    if family == "mongodb":
        return [
            "// Run in mongosh against the admin database:",
            f'db.getSiblingDB("{db}").createUser({{',
            f'  user: "{RO_USER}",',
            f'  pwd: "{password}",',
            f'  roles: [ {{ role: "read", db: "{db}" }} ]',
            "});",
        ]
    if family == "sqlserver":
        return [
            f"CREATE LOGIN {RO_USER} WITH PASSWORD = '{password}';",
            f"CREATE USER {RO_USER} FOR LOGIN {RO_USER};",
            f"ALTER ROLE db_datareader ADD MEMBER {RO_USER};",
        ]
    if family == "sqlite":
        return ["-- SQLite has no users. Open the file read-only, e.g. "
                "file:your.db?mode=ro, or copy it before migrating."]
    return [f"-- No read-only recipe available for {db_type}. "
            f"Use a credential with SELECT-only rights."]


def readonly_connection_string(connection_string: str,
                               password: str = "<strong-password>") -> str:
    """The same connection string with the read-only user substituted in."""
    parsed = urlparse(connection_string)
    if not parsed.hostname:
        return connection_string
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=f"{RO_USER}:{password}@{host}"))


# Probe statements: each is a *rejected-by-permission* check, not a write.
_PROBES: dict[str, str] = {
    # information_schema tells us what the current grantee may do.
    "postgres": """
        SELECT count(*) FROM information_schema.table_privileges
        WHERE grantee = current_user
          AND privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE')
    """,
    "mysql": "SHOW GRANTS FOR CURRENT_USER()",
    "sqlserver": """
        SELECT count(*) FROM fn_my_permissions(NULL, 'DATABASE')
        WHERE permission_name IN ('INSERT','UPDATE','DELETE')
    """,
}

WRITE_KEYWORDS = ("INSERT", "UPDATE", "DELETE", "ALL PRIVILEGES", "TRUNCATE")


async def probe_write_access(connector: Any, db_type: str) -> dict[str, Any]:
    """Returns {has_write_access: bool|None, evidence: str}.

    None means undetermined — the UI shows an advisory rather than a claim.
    Nothing is written to the source under any branch.
    """
    family = resolve_family(db_type)
    sql = _PROBES.get(family)
    if sql is None or not hasattr(connector, "fetch_all"):
        return {"has_write_access": None,
                "evidence": f"Privilege probing is not supported for "
                            f"{db_type}; verify the credential manually."}
    try:
        rows = await connector.fetch_all(sql)
    except Exception as e:  # noqa: BLE001 — probing must never fail a test
        return {"has_write_access": None,
                "evidence": f"Could not read privileges ({e})."}

    if family == "mysql":
        grants = " ".join(str(r) for r in rows).upper()
        writable = any(k in grants for k in WRITE_KEYWORDS)
        return {"has_write_access": writable,
                "evidence": "SHOW GRANTS reports write privileges"
                            if writable else
                            "SHOW GRANTS reports SELECT-only access"}
    count = 0
    if rows:
        first = rows[0]
        value = list(first.values())[0] if isinstance(first, dict) else first
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 0
    return {"has_write_access": count > 0,
            "evidence": f"{count} write privilege(s) granted to the current user"
                        if count else "no write privileges for the current user"}

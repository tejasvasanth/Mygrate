"""Neo4j graph connector (official neo4j driver, sync API in threads).

Connection string format:
  neo4j://user:password@host:7687
  neo4j+s://user:password@xxxx.databases.neo4j.io   (Aura)
  bolt://user:password@localhost:7687

Relational mapping: each node label becomes a "table"; node properties become
columns; relationships are reported as foreign-key-like links so the Mapping
Strategist can reason about them. When Neo4j is the TARGET, each table becomes
a label and each row a node.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from urllib.parse import unquote, urlparse

from .base import BaseConnector

SCHEMA_SAMPLE_SIZE = 1000
OPTIONAL_FIELD_THRESHOLD = 0.8


def _prop_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    name = type(value).__name__.lower()
    if "date" in name or "time" in name:
        return "datetime"
    return "string"


class Neo4jConnector(BaseConnector):
    db_type = "neo4j"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        u = urlparse(connection_string)
        scheme = u.scheme or "neo4j"
        host = u.hostname or "localhost"
        port = f":{u.port}" if u.port else ""
        self.uri = f"{scheme}://{host}{port}"
        self.auth = ((unquote(u.username), unquote(u.password or ""))
                     if u.username else None)
        self.database = (u.path or "/").lstrip("/") or "neo4j"
        self.driver: Any = None
        self._schema_cache: dict[str, Any] | None = None

    async def connect(self) -> None:
        if self.driver is None:
            from neo4j import GraphDatabase

            def _mk():
                d = GraphDatabase.driver(self.uri, auth=self.auth)
                d.verify_connectivity()
                return d
            self.driver = await asyncio.to_thread(_mk)

    async def close(self) -> None:
        if self.driver is not None:
            await asyncio.to_thread(self.driver.close)
            self.driver = None

    async def _run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        await self.connect()

        def _exec():
            with self.driver.session(database=self.database) as s:
                return [dict(r) for r in s.run(cypher, **params)]
        return await asyncio.to_thread(_exec)

    async def test_connection(self) -> bool:
        await self._run("RETURN 1 AS ok")
        return True

    async def get_schema(self) -> dict[str, Any]:
        if self._schema_cache is not None:
            return self._schema_cache
        tables: dict[str, Any] = {}
        labels = [r["label"] for r in await self._run(
            "CALL db.labels() YIELD label RETURN label")]
        rel_rows = await self._run(
            "MATCH (a)-[r]->(b) "
            "RETURN DISTINCT labels(a)[0] AS src, type(r) AS rel, labels(b)[0] AS dst "
            "LIMIT 200")
        for label in labels:
            count = (await self._run(
                f"MATCH (n:`{label}`) RETURN count(n) AS c"))[0]["c"]
            samples = await self._run(
                f"MATCH (n:`{label}`) RETURN properties(n) AS p LIMIT {SCHEMA_SAMPLE_SIZE}")
            field_counts: dict[str, int] = {}
            field_types: dict[str, dict[str, int]] = {}
            sampled = 0
            for row in samples:
                sampled += 1
                for k, v in (row["p"] or {}).items():
                    field_counts[k] = field_counts.get(k, 0) + 1
                    t = _prop_type(v)
                    field_types.setdefault(k, {})[t] = \
                        field_types.setdefault(k, {}).get(t, 0) + 1
            columns = [{
                "name": f, "type": max(field_types[f], key=lambda t: field_types[f][t]),
                "nullable": True, "default": None, "primary_key": False,
                "presence_pct": round(100 * c / max(sampled, 1), 1),
                "optional": c / max(sampled, 1) < OPTIONAL_FIELD_THRESHOLD,
            } for f, c in field_counts.items()]
            # Outgoing relationships reported as FK-ish links for the strategist.
            fks = [{"column": f"-[:{r['rel']}]->", "ref_table": r["dst"],
                    "ref_column": "(node)"}
                   for r in rel_rows if r["src"] == label and r["dst"]]
            tables[label] = {
                "columns": columns, "primary_key": [], "foreign_keys": fks,
                "indexes": [], "row_count": count, "sampled_docs": sampled,
                "graph_label": True,
            }
        self._schema_cache = {"db_type": self.db_type, "tables": tables}
        return self._schema_cache

    async def count_rows(self, table: str) -> int:
        return (await self._run(f"MATCH (n:`{table}`) RETURN count(n) AS c"))[0]["c"]

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        rows = await self._run(
            f"MATCH (n:`{table}`) RETURN properties(n) AS p, elementId(n) AS _id "
            f"LIMIT {int(limit)}")
        return [{**(r["p"] or {}), "_element_id": r["_id"]} for r in rows]

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        skip = max(0, int(skip_rows))
        while True:
            rows = await self._run(
                f"MATCH (n:`{table}`) RETURN properties(n) AS p "
                f"ORDER BY elementId(n) SKIP {skip} LIMIT {int(chunk_size)}")
            if not rows:
                break
            yield [dict(r["p"] or {}) for r in rows]
            skip += len(rows)
            if len(rows) < chunk_size:
                break

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        # Labels are implicit in Neo4j; create a uniqueness constraint on the PK.
        if primary_key:
            pk = primary_key[0]
            await self._run(
                f"CREATE CONSTRAINT IF NOT EXISTS "
                f"FOR (n:`{table}`) REQUIRE n.`{pk}` IS UNIQUE")

    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        """Neo4j properties: primitives and homogeneous lists only."""
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, dict):
            return json.dumps(value, default=str)  # maps not allowed as properties
        if isinstance(value, list):
            return [cls._sanitize(v) for v in value]
        return value

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        payload = [{k: self._sanitize(v) for k, v in r.items() if v is not None}
                   for r in rows]
        if conflict_strategy == "overwrite":
            # Requires a unique constraint (created via create_table) to be useful;
            # merge on all keys of the first row's PK-ish 'id'/'_id' if present.
            key = next((k for k in ("id", "_id") if k in payload[0]), None)
            if key:
                await self._run(
                    f"UNWIND $rows AS row MERGE (n:`{table}` {{`{key}`: row.`{key}`}}) "
                    f"SET n = row", rows=payload)
                return len(payload)
        await self._run(f"UNWIND $rows AS row CREATE (n:`{table}`) SET n = row",
                        rows=payload)
        return len(payload)

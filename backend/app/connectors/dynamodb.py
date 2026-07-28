"""AWS DynamoDB connector (boto3, run in threads).

Connection string format:
  dynamodb://<ACCESS_KEY>:<SECRET_KEY>@<region>
  dynamodb://<region>                       (ambient AWS credentials)
  dynamodb://key:secret@us-east-1?endpoint=http://localhost:8000  (DynamoDB Local)

Schemaless like MongoDB: the schema is inferred by scanning a sample of items.
"""
from __future__ import annotations

import asyncio
import datetime
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .base import BaseConnector

SCHEMA_SAMPLE_SIZE = 1000
OPTIONAL_FIELD_THRESHOLD = 0.8


def _dynamo_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, Decimal):
        return "number"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (dict,)):
        return "map"
    if isinstance(value, (list, set)):
        return "list"
    if isinstance(value, (bytes, bytearray)):
        return "binary"
    return "string"


class DynamoDBConnector(BaseConnector):
    db_type = "dynamodb"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        u = urlparse(connection_string)
        q = parse_qs(u.query)
        self.region = u.hostname or "us-east-1"
        self.access_key = unquote(u.username) if u.username else None
        self.secret_key = unquote(u.password) if u.password else None
        self.endpoint = (q.get("endpoint") or [None])[0]
        self.resource: Any = None
        self._schema_cache: dict[str, Any] | None = None

    async def connect(self) -> None:
        if self.resource is None:
            import boto3

            def _mk():
                kwargs: dict[str, Any] = {"region_name": self.region}
                if self.access_key:
                    kwargs["aws_access_key_id"] = self.access_key
                    kwargs["aws_secret_access_key"] = self.secret_key
                if self.endpoint:
                    kwargs["endpoint_url"] = self.endpoint
                return boto3.resource("dynamodb", **kwargs)
            self.resource = await asyncio.to_thread(_mk)

    async def close(self) -> None:
        self.resource = None  # boto3 resources hold no persistent connection

    async def test_connection(self) -> bool:
        await self.connect()
        await asyncio.to_thread(lambda: list(self.resource.tables.limit(1)))
        return True

    async def get_schema(self) -> dict[str, Any]:
        if self._schema_cache is not None:
            return self._schema_cache
        await self.connect()

        def _scan() -> dict[str, Any]:
            tables: dict[str, Any] = {}
            for t in self.resource.tables.all():
                keys = [k["AttributeName"] for k in t.key_schema]
                field_counts: dict[str, int] = {}
                field_types: dict[str, dict[str, int]] = {}
                sampled = 0
                resp = t.scan(Limit=SCHEMA_SAMPLE_SIZE)
                for item in resp.get("Items", []):
                    sampled += 1
                    for k, v in item.items():
                        field_counts[k] = field_counts.get(k, 0) + 1
                        ty = _dynamo_type(v)
                        field_types.setdefault(k, {})[ty] = \
                            field_types.setdefault(k, {}).get(ty, 0) + 1
                columns = []
                for field, count in field_counts.items():
                    types = field_types[field]
                    dominant = max(types, key=lambda x: types[x])
                    columns.append({
                        "name": field, "type": dominant,
                        "nullable": types.get("null", 0) > 0, "default": None,
                        "primary_key": field in keys,
                        "presence_pct": round(100 * count / max(sampled, 1), 1),
                        "optional": count / max(sampled, 1) < OPTIONAL_FIELD_THRESHOLD,
                    })
                tables[t.name] = {
                    "columns": columns,
                    "primary_key": keys,
                    "foreign_keys": [],
                    "indexes": [],
                    "row_count": int(t.item_count or 0),  # ~6h stale, best effort
                    "sampled_docs": sampled,
                }
            return {"db_type": self.db_type, "tables": tables}
        self._schema_cache = await asyncio.to_thread(_scan)
        return self._schema_cache

    @staticmethod
    def _plain(item: dict[str, Any]) -> dict[str, Any]:
        def conv(v: Any) -> Any:
            if isinstance(v, Decimal):
                return int(v) if v == v.to_integral_value() else float(v)
            if isinstance(v, set):
                return sorted(conv(x) for x in v)
            if isinstance(v, dict):
                return {k: conv(x) for k, x in v.items()}
            if isinstance(v, list):
                return [conv(x) for x in v]
            return v
        return {k: conv(v) for k, v in item.items()}

    async def count_rows(self, table: str) -> int:
        await self.connect()

        def _count() -> int:
            t = self.resource.Table(table)
            total = 0
            kwargs: dict[str, Any] = {"Select": "COUNT"}
            while True:
                resp = t.scan(**kwargs)
                total += resp.get("Count", 0)
                lek = resp.get("LastEvaluatedKey")
                if not lek:
                    return total
                kwargs["ExclusiveStartKey"] = lek
        return await asyncio.to_thread(_count)

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        await self.connect()

        def _sample():
            resp = self.resource.Table(table).scan(Limit=limit)
            return [self._plain(i) for i in resp.get("Items", [])]
        return await asyncio.to_thread(_sample)

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        await self.connect()
        # DynamoDB resumes from an ExclusiveStartKey, which is exactly what a
        # checkpointed LastEvaluatedKey is.
        start_key: dict[str, Any] | None = (
            start_after if isinstance(start_after, dict) else None)
        while True:
            def _page(key: dict[str, Any] | None):
                kwargs: dict[str, Any] = {"Limit": chunk_size}
                if key:
                    kwargs["ExclusiveStartKey"] = key
                return self.resource.Table(table).scan(**kwargs)
            resp = await asyncio.to_thread(_page, start_key)
            items = resp.get("Items", [])
            if items:
                yield [self._plain(i) for i in items]
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        await self.connect()
        pk = (primary_key or ["id"])[:2]  # hash key + optional range key

        def _create() -> None:
            existing = [t.name for t in self.resource.tables.all()]
            if table in existing:
                return
            key_schema = [{"AttributeName": pk[0], "KeyType": "HASH"}]
            attr_defs = [{"AttributeName": pk[0], "AttributeType": "S"}]
            if len(pk) > 1:
                key_schema.append({"AttributeName": pk[1], "KeyType": "RANGE"})
                attr_defs.append({"AttributeName": pk[1], "AttributeType": "S"})
            t = self.resource.create_table(
                TableName=table, KeySchema=key_schema,
                AttributeDefinitions=attr_defs, BillingMode="PAY_PER_REQUEST")
            t.wait_until_exists()
        await asyncio.to_thread(_create)

    @classmethod
    def _sanitize(cls, value: Any, key_fields: set[str] | None = None,
                  field: str | None = None) -> Any:
        if isinstance(value, float):
            return Decimal(str(value))  # DynamoDB rejects float, wants Decimal
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value  # binary supported natively
        if isinstance(value, dict):
            return {k: cls._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(v) for v in value]
        if value == "":
            return None  # empty strings not allowed in older-style attributes
        if not isinstance(value, (str, int, bool, Decimal, type(None))):
            return json.dumps(value, default=str)
        return value

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        await self.connect()

        def _insert() -> int:
            t = self.resource.Table(table)
            keys = {k["AttributeName"] for k in t.key_schema}
            written = 0
            # batch_writer overwrites on duplicate keys — matches "overwrite";
            # "fail"/"skip" degrade to overwrite semantics (DynamoDB puts are upserts).
            with t.batch_writer() as batch:
                for r in rows:
                    item = {k: self._sanitize(v) for k, v in r.items() if v is not None}
                    for k in keys:  # key attributes must exist and be strings-compatible
                        if k not in item:
                            item[k] = "unknown"
                        elif not isinstance(item[k], (str, Decimal, bytes)):
                            item[k] = str(item[k])
                    batch.put_item(Item=item)
                    written += 1
            return written
        return await asyncio.to_thread(_insert)

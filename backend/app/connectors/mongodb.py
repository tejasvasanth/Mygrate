"""MongoDB connector — schema inferred by sampling documents."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

from .base import BaseConnector

SCHEMA_SAMPLE_SIZE = 1000  # minimum documents scanned for schema inference
OPTIONAL_FIELD_THRESHOLD = 0.8  # fields in < 80% of docs flagged optional


def _bson_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "long"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bytes):
        return "bindata"
    name = type(value).__name__.lower()
    if name == "objectid":
        return "objectid"
    if name == "datetime":
        return "date"
    return "string"


class MongoDBConnector(BaseConnector):
    db_type = "mongodb"

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self.client: MongoClient | None = None
        self._schema_cache: dict[str, Any] | None = None

    def _db(self):
        assert self.client is not None, "connect() first"
        db = self.client.get_default_database()
        if db is None:
            raise ValueError("MongoDB connection string must include a database name")
        return db

    async def connect(self) -> None:
        if self.client is None:
            def _mk() -> MongoClient:
                # uuidRepresentation="standard": store UUIDs as RFC 4122 BSON
                # Binary — without it pymongo refuses to encode uuid.UUID.
                return MongoClient(self.connection_string,
                                   serverSelectionTimeoutMS=5000,
                                   uuidRepresentation="standard")
            self.client = await asyncio.to_thread(_mk)

    async def close(self) -> None:
        if self.client is not None:
            await asyncio.to_thread(self.client.close)
            self.client = None

    async def test_connection(self) -> bool:
        await self.connect()
        assert self.client is not None
        await asyncio.to_thread(self.client.admin.command, "ping")
        return True

    async def get_schema(self) -> dict[str, Any]:
        if self._schema_cache is not None:
            return self._schema_cache

        def _scan() -> dict[str, Any]:
            db = self._db()
            tables: dict[str, Any] = {}
            for name in db.list_collection_names():
                coll = db[name]
                total = coll.estimated_document_count()
                field_counts: dict[str, int] = {}
                field_types: dict[str, dict[str, int]] = {}
                sampled = 0
                for doc in coll.find().limit(SCHEMA_SAMPLE_SIZE):
                    sampled += 1
                    for k, v in doc.items():
                        field_counts[k] = field_counts.get(k, 0) + 1
                        t = _bson_type(v)
                        field_types.setdefault(k, {})[t] = field_types.setdefault(k, {}).get(t, 0) + 1
                columns = []
                for field, count in field_counts.items():
                    types = field_types[field]
                    dominant = max(types, key=lambda t: types[t])
                    columns.append({
                        "name": field,
                        "type": dominant,
                        "nullable": types.get("null", 0) > 0,
                        "default": None,
                        "primary_key": field == "_id",
                        "presence_pct": round(100 * count / max(sampled, 1), 1),
                        "optional": count / max(sampled, 1) < OPTIONAL_FIELD_THRESHOLD,
                    })
                tables[name] = {
                    "columns": columns,
                    "primary_key": ["_id"],
                    "foreign_keys": [],
                    "indexes": [{
                        "name": i["name"],
                        "columns": list(i["key"].keys()),
                        "unique": bool(i.get("unique", False)),
                    } for i in coll.list_indexes()],
                    "row_count": total,
                    "sampled_docs": sampled,
                }
            return {"db_type": self.db_type, "tables": tables}

        self._schema_cache = await asyncio.to_thread(_scan)
        return self._schema_cache

    async def count_rows(self, table: str) -> int:
        def _count() -> int:
            return self._db()[table].count_documents({})
        return await asyncio.to_thread(_count)

    async def sample_rows(self, table: str, limit: int = 1000) -> list[dict[str, Any]]:
        def _sample() -> list[dict[str, Any]]:
            return [self._plain(d) for d in self._db()[table].find().limit(limit)]
        return await asyncio.to_thread(_sample)

    @staticmethod
    def _plain(doc: dict[str, Any]) -> dict[str, Any]:
        out = dict(doc)
        if "_id" in out and not isinstance(out["_id"], (str, int, float)):
            out["_id"] = str(out["_id"])
        return out

    async def stream_rows(self, table: str, chunk_size: int = 1000,
                          start_after: Any = None,
                          skip_rows: int = 0) -> AsyncIterator[list[dict[str, Any]]]:
        """_id-based keyset pagination — never loads the full collection.
        start_after resumes past a checkpointed _id."""
        last_id: Any = start_after
        while True:
            def _page(after: Any) -> list[dict[str, Any]]:
                query = {"_id": {"$gt": after}} if after is not None else {}
                return list(self._db()[table].find(query).sort("_id", 1).limit(chunk_size))
            raw = await asyncio.to_thread(_page, last_id)
            if not raw:
                break
            last_id = raw[-1]["_id"]
            yield [self._plain(d) for d in raw]
            if len(raw) < chunk_size:
                break

    async def create_table(self, table: str, columns: list[dict[str, Any]],
                           primary_key: list[str] | None = None) -> None:
        def _create() -> None:
            db = self._db()
            if table not in db.list_collection_names():
                db.create_collection(table)
        await asyncio.to_thread(_create)

    async def drop_table(self, table: str) -> None:
        def _drop() -> None:
            self._db().drop_collection(table)
        await asyncio.to_thread(_drop)

    async def fetch_rows_by_key(self, table: str, key_column: str,
                                values: list[Any]) -> list[dict[str, Any]]:
        if not values:
            return []
        def _fetch() -> list[dict[str, Any]]:
            return [self._plain(d) for d in
                    self._db()[table].find({key_column: {"$in": list(values)}})]
        return await asyncio.to_thread(_fetch)

    async def add_foreign_key(self, table: str, column: str,
                              ref_table: str, ref_column: str) -> None:
        return  # documents have no FK constraints — nothing to do

    @classmethod
    def _sanitize(cls, value: Any) -> Any:
        """Coerce Python types BSON can't encode. UUIDs become plain strings —
        readable and portable regardless of the reader's UUID representation."""
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime(value.year, value.month, value.day)  # BSON has no date-only
        if isinstance(value, time):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: cls._sanitize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._sanitize(v) for v in value]
        return value

    async def insert_rows(self, table: str, rows: list[dict[str, Any]],
                          conflict_strategy: str = "fail") -> int:
        if not rows:
            return 0
        rows = [self._sanitize(r) for r in rows]

        def _insert() -> int:
            coll = self._db()[table]
            if conflict_strategy == "overwrite":
                written = 0
                for r in rows:
                    if "_id" in r:
                        coll.replace_one({"_id": r["_id"]}, r, upsert=True)
                    else:
                        coll.insert_one(r)
                    written += 1
                return written
            try:
                result = coll.insert_many(rows, ordered=(conflict_strategy == "fail"))
                return len(result.inserted_ids)
            except BulkWriteError as e:
                if conflict_strategy == "skip":
                    return e.details.get("nInserted", 0)
                raise
        return await asyncio.to_thread(_insert)

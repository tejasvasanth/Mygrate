"""Shared fixtures: seeded SQLite source DB, empty SQLite target, local supabase."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force the in-memory Supabase stand-in and fallback planner during tests.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

from app.config import get_settings  # noqa: E402
from app.connectors.sqlite import SQLiteConnector  # noqa: E402
from app.services.supabase_service import reset_supabase  # noqa: E402

get_settings.cache_clear()

SEED_SQL = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  phone TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  is_verified INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  total REAL,
  order_status TEXT DEFAULT 'placed'
);
"""


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def local_supabase():
    reset_supabase()
    from app.services.supabase_service import get_supabase
    sb = get_supabase()
    yield sb
    reset_supabase()


@pytest.fixture()
def source_db(tmp_path: Path) -> str:
    """Seeded SQLite file with users (50 rows) and orders (120 rows)."""
    import sqlite3
    path = tmp_path / "source.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SEED_SQL)
    for i in range(1, 51):
        conn.execute(
            "INSERT INTO users (id, email, phone, status, is_verified) VALUES (?,?,?,?,?)",
            (i, f"user{i}@example.com",
             None if i % 5 == 0 else f"+1555{i:07d}",
             ["active", "inactive", "banned"][i % 3], i % 2))
    for i in range(1, 121):
        conn.execute(
            "INSERT INTO orders (id, user_id, total, order_status) VALUES (?,?,?,?)",
            (i, 1 + i % 50, None if i % 13 == 0 else round(i * 1.5, 2),
             ["placed", "shipped", "delivered"][i % 3]))
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture()
def target_db(tmp_path: Path) -> str:
    return str(tmp_path / "target.sqlite")


@pytest.fixture()
async def source_connector(source_db: str):
    c = SQLiteConnector(source_db)
    await c.connect()
    yield c
    await c.close()


@pytest.fixture()
async def target_connector(target_db: str):
    c = SQLiteConnector(target_db)
    await c.connect()
    yield c
    await c.close()

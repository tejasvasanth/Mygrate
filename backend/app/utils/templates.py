"""Migration templates (T3-4) — pre-filled type quirks for common stacks.

Each template encodes what actually bites engineers migrating that stack, so
the Mapping Strategist starts from known-good rules instead of rediscovering
them. Served publicly for SEO at /api/v1/templates.
"""
from __future__ import annotations

from typing import Any

TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "laravel-mysql-to-supabase-postgres",
        "title": "Laravel MySQL → Supabase Postgres",
        "stack": "Laravel",
        "source_db_type": "mysql",
        "target_db_type": "supabase",
        "summary": "Laravel's MySQL schema conventions mapped onto Supabase "
                   "Postgres, including the boolean and timestamp quirks that "
                   "break naive migrations.",
        "quirks": [
            "Laravel declares booleans as TINYINT(1) — migrate to BOOLEAN, not "
            "SMALLINT, or every `where('is_active', true)` breaks.",
            "`created_at`/`updated_at` are DATETIME with no timezone; convert "
            "to TIMESTAMPTZ and decide explicitly whether they are UTC.",
            "`id` is UNSIGNED BIGINT AUTO_INCREMENT — Postgres has no UNSIGNED; "
            "use BIGSERIAL/GENERATED AS IDENTITY.",
            "Laravel's `json` columns are LONGTEXT in MySQL — migrate to JSONB.",
            "`deleted_at` soft deletes stay nullable TIMESTAMPTZ.",
            "Supabase applies RLS by default — migrated tables are unreadable "
            "from the client until you add policies.",
        ],
        "type_overrides": {
            "TINYINT(1)": "BOOLEAN",
            "DATETIME": "TIMESTAMPTZ",
            "LONGTEXT": "TEXT",
            "BIGINT UNSIGNED": "BIGINT",
            "DOUBLE": "DECIMAL(12,2)",
        },
        "options": {"conflict_strategy": "fail", "dry_run": True},
    },
    {
        "slug": "django-sqlite-to-railway-postgres",
        "title": "Django SQLite → Railway Postgres",
        "stack": "Django",
        "source_db_type": "sqlite",
        "target_db_type": "postgres",
        "summary": "The classic dev-to-prod move. SQLite's dynamic typing hides "
                   "problems Postgres enforces immediately.",
        "quirks": [
            "SQLite stores booleans as INTEGER 0/1 — migrate to BOOLEAN.",
            "SQLite has no native DATETIME; Django writes ISO-8601 strings that "
            "must be parsed into TIMESTAMPTZ, not copied as TEXT.",
            "SQLite permits any value in any column — Postgres will reject rows "
            "SQLite happily accepted. Run the data quality report first.",
            "Django's `AutoField` becomes SERIAL; reset the sequence after load "
            "or the next insert collides.",
            "SQLite's DECIMAL is really a float — precision may already be lost "
            "in the source.",
        ],
        "type_overrides": {
            "INTEGER": "INTEGER",
            "BOOLEAN": "BOOLEAN",
            "DATETIME": "TIMESTAMPTZ",
            "REAL": "DOUBLE PRECISION",
            "TEXT": "TEXT",
        },
        "options": {"conflict_strategy": "fail", "dry_run": True},
    },
    {
        "slug": "rails-mysql-to-neon-postgres",
        "title": "Rails MySQL → Neon Postgres",
        "stack": "Ruby on Rails",
        "source_db_type": "mysql",
        "target_db_type": "neon",
        "summary": "Rails/ActiveRecord conventions translated to Neon's "
                   "serverless Postgres.",
        "quirks": [
            "ActiveRecord booleans are TINYINT(1) in MySQL — migrate to BOOLEAN.",
            "Rails stores `type` columns for STI — keep as TEXT, never coerce "
            "to an enum, or subclassing breaks.",
            "`schema_migrations` and `ar_internal_metadata` should be skipped; "
            "let Rails recreate them.",
            "Serialized YAML/JSON columns are TEXT — inspect before converting "
            "to JSONB, since YAML will not parse as JSON.",
            "Neon suspends idle compute — the first chunk may see a cold-start "
            "delay; this is not a failure.",
        ],
        "type_overrides": {
            "TINYINT(1)": "BOOLEAN",
            "DATETIME": "TIMESTAMPTZ",
            "TEXT": "TEXT",
            "DECIMAL": "NUMERIC",
        },
        "options": {"skip_tables": ["schema_migrations", "ar_internal_metadata"],
                    "dry_run": True},
    },
    {
        "slug": "mongodb-atlas-to-supabase-postgres",
        "title": "MongoDB Atlas → Supabase Postgres",
        "stack": "MongoDB",
        "source_db_type": "mongodb",
        "target_db_type": "supabase",
        "summary": "The hardest supported path: documents to relations. "
                   "Nesting depth decides the shape of the target schema.",
        "quirks": [
            "MongoDB has no schema — the profiler samples ≥1000 documents and "
            "builds a probabilistic one. Fields present in <80% of documents "
            "are treated as optional.",
            "`_id` is an ObjectId — migrate to TEXT (24-char hex), or generate "
            "a new UUID primary key and keep `_id` as a lookup column.",
            "Arrays averaging 0–3 items become JSONB; 4+ become a child table. "
            "Override this in options if you know your access patterns.",
            "Mixed-type fields (string in some docs, number in others) must "
            "become TEXT — Postgres cannot hold both.",
            "Dates may be BSON Date, ISO string, or epoch int in the same "
            "collection; the profiler flags this as a date-format conflict.",
        ],
        "type_overrides": {
            "ObjectId": "TEXT",
            "Date": "TIMESTAMPTZ",
            "Object": "JSONB",
            "Array": "JSONB",
            "Decimal128": "NUMERIC",
        },
        "options": {"dry_run": True, "chunk_size": 500},
    },
    {
        "slug": "express-mysql-to-planetscale",
        "title": "Node/Express MySQL → PlanetScale",
        "stack": "Node.js / Express",
        "source_db_type": "mysql",
        "target_db_type": "planetscale",
        "summary": "MySQL to MySQL, but PlanetScale's Vitess layer forbids "
                   "things ordinary MySQL allows.",
        "quirks": [
            "PlanetScale does not support FOREIGN KEY constraints by default — "
            "Migrate skips FK creation and reports them as advisory.",
            "Schema changes go through deploy requests, not direct DDL; create "
            "the target schema via a branch before migrating data.",
            "`AUTO_INCREMENT` values are not guaranteed contiguous across "
            "Vitess shards — never depend on gapless ids.",
            "Very large tables should use a smaller chunk size; PlanetScale "
            "enforces per-query row and time limits.",
        ],
        "type_overrides": {
            "TINYINT(1)": "TINYINT(1)",
            "DATETIME": "DATETIME",
            "JSON": "JSON",
        },
        "options": {"chunk_size": 500, "dry_run": True},
    },
]

BY_SLUG = {t["slug"]: t for t in TEMPLATES}


def list_templates() -> list[dict[str, Any]]:
    """Summary view for the index page (no type tables)."""
    return [{k: v for k, v in t.items() if k != "type_overrides"}
            for t in TEMPLATES]


def get_template(slug: str) -> dict[str, Any] | None:
    return BY_SLUG.get(slug)

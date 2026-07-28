"""Cross-database type coercion rules.

Used by the Mapping Strategist (as reference material in the LLM prompt and as
the deterministic fallback planner) and by the Migration Executor when building
target DDL.
"""
from __future__ import annotations

# Canonical intermediate types every source type is normalised to first.
CANONICAL_TYPES = [
    "integer", "bigint", "float", "decimal", "boolean", "string", "text",
    "date", "datetime", "time", "uuid", "json", "binary", "array", "object",
]

# source-native type (lowercased, size stripped) -> canonical
SOURCE_TO_CANONICAL: dict[str, dict[str, str]] = {
    "postgres": {
        "smallint": "integer", "integer": "integer", "int": "integer", "int4": "integer",
        "bigint": "bigint", "int8": "bigint", "serial": "integer", "bigserial": "bigint",
        "real": "float", "double precision": "float", "float8": "float",
        "numeric": "decimal", "decimal": "decimal", "money": "decimal",
        "boolean": "boolean", "bool": "boolean",
        "character varying": "string", "varchar": "string", "character": "string", "char": "string",
        "text": "text", "citext": "text",
        "date": "date", "timestamp": "datetime", "timestamptz": "datetime",
        "timestamp without time zone": "datetime", "timestamp with time zone": "datetime",
        "time": "time", "time without time zone": "time",
        "uuid": "uuid", "json": "json", "jsonb": "json",
        "bytea": "binary", "array": "array",
    },
    "mysql": {
        "tinyint": "integer", "tinyint(1)": "boolean", "smallint": "integer",
        "mediumint": "integer", "int": "integer", "integer": "integer",
        "bigint": "bigint",
        "float": "float", "double": "float", "real": "float",
        "decimal": "decimal", "numeric": "decimal",
        "bit": "boolean", "boolean": "boolean", "bool": "boolean",
        "varchar": "string", "char": "string",
        "text": "text", "tinytext": "text", "mediumtext": "text", "longtext": "text",
        "date": "date", "datetime": "datetime", "timestamp": "datetime", "time": "time",
        "year": "integer",
        "json": "json",
        "blob": "binary", "tinyblob": "binary", "mediumblob": "binary", "longblob": "binary",
        "binary": "binary", "varbinary": "binary",
        "enum": "string", "set": "string",
    },
    "sqlite": {
        "integer": "bigint", "int": "bigint", "tinyint": "integer", "smallint": "integer",
        "bigint": "bigint",
        "real": "float", "double": "float", "float": "float",
        "numeric": "decimal", "decimal": "decimal",
        "boolean": "boolean", "bool": "boolean",
        "varchar": "string", "char": "string", "nvarchar": "string",
        "text": "text", "clob": "text",
        "date": "date", "datetime": "datetime", "timestamp": "datetime", "time": "time",
        "blob": "binary", "json": "json",
    },
    "mongodb": {
        "int": "integer", "long": "bigint", "double": "float", "decimal": "decimal",
        "bool": "boolean", "string": "string", "date": "datetime",
        "objectid": "string", "uuid": "uuid", "object": "object", "array": "array",
        "bindata": "binary", "null": "string",
    },
    "sqlserver": {
        "tinyint": "integer", "smallint": "integer", "int": "integer",
        "bigint": "bigint",
        "real": "float", "float": "float",
        "decimal": "decimal", "numeric": "decimal", "money": "decimal",
        "smallmoney": "decimal",
        "bit": "boolean",
        "varchar": "string", "nvarchar": "string", "char": "string", "nchar": "string",
        "text": "text", "ntext": "text",
        "date": "date", "datetime": "datetime", "datetime2": "datetime",
        "smalldatetime": "datetime", "datetimeoffset": "datetime", "time": "time",
        "uniqueidentifier": "uuid",
        "binary": "binary", "varbinary": "binary", "image": "binary",
        "xml": "text", "json": "json",
    },
    "bigquery": {
        "int64": "bigint", "integer": "bigint",
        "float64": "float", "float": "float",
        "numeric": "decimal", "bignumeric": "decimal",
        "bool": "boolean", "boolean": "boolean",
        "string": "string", "bytes": "binary",
        "date": "date", "datetime": "datetime", "timestamp": "datetime", "time": "time",
        "json": "json", "record": "object", "struct": "object",
        "geography": "string",
    },
    "dynamodb": {
        "number": "decimal", "string": "string", "bool": "boolean",
        "map": "object", "list": "array", "binary": "binary", "null": "string",
    },
    "neo4j": {
        "integer": "bigint", "float": "float", "boolean": "boolean",
        "string": "string", "datetime": "datetime", "list": "array", "null": "string",
    },
}

# canonical -> target-native DDL type
CANONICAL_TO_TARGET: dict[str, dict[str, str]] = {
    "postgres": {
        "integer": "INTEGER", "bigint": "BIGINT", "float": "DOUBLE PRECISION",
        "decimal": "NUMERIC", "boolean": "BOOLEAN", "string": "VARCHAR(255)",
        "text": "TEXT", "date": "DATE", "datetime": "TIMESTAMPTZ", "time": "TIME",
        "uuid": "UUID", "json": "JSONB", "binary": "BYTEA",
        "array": "JSONB", "object": "JSONB",
    },
    "mysql": {
        "integer": "INT", "bigint": "BIGINT", "float": "DOUBLE",
        "decimal": "DECIMAL(38,10)", "boolean": "TINYINT(1)", "string": "VARCHAR(255)",
        "text": "TEXT", "date": "DATE", "datetime": "DATETIME", "time": "TIME",
        "uuid": "CHAR(36)", "json": "JSON", "binary": "BLOB",
        "array": "JSON", "object": "JSON",
    },
    "sqlite": {
        "integer": "INTEGER", "bigint": "INTEGER", "float": "REAL",
        "decimal": "NUMERIC", "boolean": "INTEGER", "string": "TEXT",
        "text": "TEXT", "date": "TEXT", "datetime": "TEXT", "time": "TEXT",
        "uuid": "TEXT", "json": "TEXT", "binary": "BLOB",
        "array": "TEXT", "object": "TEXT",
    },
    "mongodb": {
        # MongoDB is schemaless — canonical type recorded for reference only.
        t: t for t in CANONICAL_TYPES
    },
    "sqlserver": {
        "integer": "INT", "bigint": "BIGINT", "float": "FLOAT",
        "decimal": "DECIMAL(38,10)", "boolean": "BIT", "string": "NVARCHAR(255)",
        "text": "NVARCHAR(MAX)", "date": "DATE", "datetime": "DATETIME2",
        "time": "TIME", "uuid": "UNIQUEIDENTIFIER", "json": "NVARCHAR(MAX)",
        "binary": "VARBINARY(MAX)", "array": "NVARCHAR(MAX)", "object": "NVARCHAR(MAX)",
    },
    "bigquery": {
        "integer": "INT64", "bigint": "INT64", "float": "FLOAT64",
        "decimal": "BIGNUMERIC", "boolean": "BOOL", "string": "STRING",
        "text": "STRING", "date": "DATE", "datetime": "TIMESTAMP", "time": "TIME",
        "uuid": "STRING", "json": "JSON", "binary": "BYTES",
        "array": "JSON", "object": "JSON",
    },
    "dynamodb": {
        # DynamoDB is schemaless — canonical type recorded for reference only.
        t: t for t in CANONICAL_TYPES
    },
    "neo4j": {
        # Node properties are dynamically typed — reference only.
        t: t for t in CANONICAL_TYPES
    },
}

# Flattened reference table handed to the LLM prompt.
TYPE_COERCION_MAP = {
    "canonical_types": CANONICAL_TYPES,
    "source_to_canonical": SOURCE_TO_CANONICAL,
    "canonical_to_target": CANONICAL_TO_TARGET,
}

FALLBACK_TYPE = "TEXT"


def _family(db_type: str) -> str:
    from .db_families import DB_FAMILIES
    return DB_FAMILIES.get((db_type or "").strip().lower(), db_type)


def normalise_type(db_type: str, raw_type: str) -> str:
    """Map a source-native column type to a canonical type."""
    db_type = _family(db_type)
    key = (raw_type or "").strip().lower()
    table = SOURCE_TO_CANONICAL.get(db_type, {})
    if key in table:
        return table[key]
    # Strip a size suffix, e.g. varchar(120) -> varchar; tinyint(1) is checked first.
    base = key.split("(")[0].strip()
    if key.startswith("tinyint(1)") and db_type == "mysql":
        return "boolean"
    return table.get(base, "text")


def target_type(db_type: str, canonical: str) -> str:
    """Map a canonical type to target-native DDL. Unknown -> TEXT fallback."""
    return CANONICAL_TO_TARGET.get(_family(db_type), {}).get(canonical, FALLBACK_TYPE)


def map_type(source_db: str, target_db: str, raw_type: str) -> str:
    return target_type(target_db, normalise_type(source_db, raw_type))

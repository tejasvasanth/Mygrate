"""DB Operator endpoints — natural-language / spreadsheet database operations.

Two-step flow, mirroring the migration approval gate:
  1. POST /preview  — parse the file, run the DBOperator agent, return the plan.
     Nothing is written.
  2. POST /execute  — client sends back the (possibly user-reviewed) plan with
     the same file; rows are written in chunks.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..agents.db_operator import DBOperator
from ..connectors import get_connector
from ..services import credential_service
from ..services.supabase_service import get_supabase
from ..utils.spreadsheet import parse_spreadsheet
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])

INSERT_CHUNK = 1000
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB


async def _open_connector(connection_id: str | None, db_type: str | None,
                          connection_string: str | None, user_id: str):
    """Either a saved connection id, or a raw db_type + connection string
    (used in-memory only — never stored)."""
    if connection_id:
        sb = get_supabase()
        conn = await sb.get_connection(connection_id, user_id)
        if conn is None:
            raise HTTPException(status_code=404, detail="Saved connection not found")
        cs = await credential_service.get_credential(conn["credential_vault_id"])
        db_type = conn["db_type"]
    elif db_type and connection_string:
        cs = connection_string
    else:
        raise HTTPException(status_code=422,
                            detail="Provide connection_id, or db_type + connection_string")
    connector = get_connector(db_type, cs)
    await connector.connect()
    return connector, db_type


async def _read_upload(file: UploadFile | None) -> tuple[list[str], list[dict[str, Any]]]:
    if file is None:
        return [], []
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    try:
        return parse_spreadsheet(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/preview")
async def preview_operation(
        connection_id: str | None = Form(None),
        db_type: str | None = Form(None),
        connection_string: str | None = Form(None),
        instruction: str = Form(""),
        file: UploadFile | None = File(None),
        user: dict[str, Any] = Depends(get_current_user)):
    if not instruction.strip() and file is None:
        raise HTTPException(status_code=422,
                            detail="Provide an instruction, a file, or both")
    headers, rows = await _read_upload(file)
    connector, db_type = await _open_connector(
        connection_id, db_type, connection_string, user["id"])
    try:
        schema = await connector.get_schema()
    finally:
        await connector.close()
    plan = await DBOperator(schema, db_type, instruction, headers, rows).plan()
    return {
        "plan": plan,
        "file_headers": headers,
        "file_row_count": len(rows),
        "sample_rows": rows[:5],
        "known_tables": sorted(schema.get("tables", {}).keys()),
    }


@router.post("/execute")
async def execute_operation(
        connection_id: str | None = Form(None),
        db_type: str | None = Form(None),
        connection_string: str | None = Form(None),
        plan_json: str = Form(...),
        file: UploadFile | None = File(None),
        user: dict[str, Any] = Depends(get_current_user)):
    try:
        plan = json.loads(plan_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="plan_json is not valid JSON") from None
    kind = plan.get("kind")
    if kind not in ("insert", "create_and_insert"):
        raise HTTPException(status_code=422,
                            detail=f"Operation kind '{kind}' cannot be executed")
    table = plan.get("target_table")
    if not table:
        raise HTTPException(status_code=422, detail="Plan has no target_table")

    headers, rows = await _read_upload(file)
    if not rows:
        rows = plan.get("inline_rows") or []
    if not rows:
        raise HTTPException(status_code=422, detail="No rows to write")

    mapping = {m["source"]: m["target"] for m in plan.get("column_mapping", [])}
    mapped = [({mapping.get(k, k): v for k, v in r.items() if not mapping or k in mapping}
               if mapping else dict(r)) for r in rows]

    connector, _db_type = await _open_connector(
        connection_id, db_type, connection_string, user["id"])
    written = 0
    try:
        if kind == "create_and_insert":
            cols = [{"name": c["name"],
                     "type": c.get("ddl_type") or c.get("canonical_type", "TEXT"),
                     "nullable": c.get("nullable", True)}
                    for c in plan.get("new_table_columns", [])]
            await connector.create_table(table, cols,
                                         plan.get("primary_key") or None)
        for i in range(0, len(mapped), INSERT_CHUNK):
            written += await connector.insert_rows(
                table, mapped[i:i + INSERT_CHUNK], conflict_strategy="fail")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"Operation failed after {written} rows: {e}") from e
    finally:
        await connector.close()
    return {"ok": True, "table": table, "rows_written": written,
            "created_table": kind == "create_and_insert"}

"""Connection endpoints — test, save (via Vault), list, delete."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..connectors import get_connector
from ..models import (
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
)
from ..services import credential_service
from ..services.supabase_service import get_supabase
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(body: ConnectionTestRequest,
                          user: dict[str, Any] = Depends(get_current_user)):
    """Tests connectivity and probes write privileges (T2-5).

    The probe is read-only — it asks the engine what the credential is allowed
    to do; it never attempts a write. The credential is never stored here."""
    from ..utils.readonly import (
        probe_write_access, readonly_connection_string, readonly_grant_sql,
    )

    connector = get_connector(body.db_type, body.connection_string)
    try:
        await connector.test_connection()
        schema = await connector.get_schema()
        privileges = await probe_write_access(connector, body.db_type)
        response = ConnectionTestResponse(
            ok=True, message="Connection successful",
            tables=sorted(schema.get("tables", {}).keys()),
            has_write_access=privileges["has_write_access"],
            privilege_evidence=privileges["evidence"])
        if privileges["has_write_access"]:
            response.readonly_advice = {
                "warning": "This connection has write privileges. Migrate only "
                           "reads from the source, but a read-only credential "
                           "removes the risk entirely — and protects you if the "
                           "credential leaks.",
                "grant_sql": readonly_grant_sql(body.db_type,
                                                body.connection_string),
                "connection_string": readonly_connection_string(
                    body.connection_string),
            }
        return response
    except Exception as e:  # noqa: BLE001
        return ConnectionTestResponse(ok=False, message=str(e))
    finally:
        await connector.close()


@router.post("", response_model=ConnectionResponse, status_code=201)
async def save_connection(body: ConnectionCreateRequest,
                          user: dict[str, Any] = Depends(get_current_user)):
    """Credential goes straight to Vault; only the vault id is persisted."""
    vault_id = await credential_service.store_credential(body.connection_string)
    conn = await get_supabase().create_connection({
        "user_id": user["id"],
        "nickname": body.nickname,
        "db_type": body.db_type,
        "host": body.host,
        "port": body.port,
        "database_name": body.database_name,
        "credential_vault_id": vault_id,
    })
    return ConnectionResponse(**{k: v for k, v in conn.items()
                                 if k in ConnectionResponse.model_fields})


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(user: dict[str, Any] = Depends(get_current_user)):
    conns = await get_supabase().list_connections(user["id"])
    return [ConnectionResponse(**{k: v for k, v in c.items()
                                  if k in ConnectionResponse.model_fields})
            for c in conns]


@router.delete("/{conn_id}", status_code=204)
async def delete_connection(conn_id: str,
                            user: dict[str, Any] = Depends(get_current_user)):
    sb = get_supabase()
    conn = await sb.get_connection(conn_id, user["id"])
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn.get("credential_vault_id"):
        await credential_service.delete_credential(conn["credential_vault_id"])
    await sb.delete_connection(conn_id, user["id"])

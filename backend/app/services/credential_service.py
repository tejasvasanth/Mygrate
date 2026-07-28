"""Credential handling — never plaintext at rest.

Primary path: Supabase Vault via SQL RPC helpers (see supabase_setup.sql).
Fallback path: Fernet encryption with CREDENTIAL_ENCRYPTION_KEY when Vault
RPCs are unavailable. Either way only an opaque id/ciphertext is stored in
saved_connections; the plaintext lives in memory only while a migration runs.
"""
from __future__ import annotations

from cryptography.fernet import Fernet

from ..config import get_settings
from ..utils.logger import get_logger
from .supabase_service import get_supabase

logger = get_logger(__name__)

_FERNET_PREFIX = "fernet:"


def _fernet() -> Fernet | None:
    key = get_settings().credential_encryption_key
    return Fernet(key.encode()) if key else None


async def store_credential(connection_string: str) -> str:
    """Returns a vault id (or fernet ciphertext token) — never the credential."""
    sb = get_supabase()
    try:
        vault_id = await sb.vault_create_secret(connection_string)
        return vault_id
    except Exception as e:  # noqa: BLE001
        logger.info(f"Vault unavailable ({type(e).__name__}); using Fernet fallback.")
    f = _fernet()
    if f is None:
        raise RuntimeError(
            "Cannot store credential: Supabase Vault unavailable and "
            "CREDENTIAL_ENCRYPTION_KEY is not set.")
    return _FERNET_PREFIX + f.encrypt(connection_string.encode()).decode()


async def get_credential(vault_id: str) -> str:
    """Returns plaintext for in-memory use only. Never log the result."""
    if vault_id.startswith(_FERNET_PREFIX):
        f = _fernet()
        if f is None:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is not set.")
        return f.decrypt(vault_id[len(_FERNET_PREFIX):].encode()).decode()
    sb = get_supabase()
    return await sb.vault_get_secret(vault_id)


async def delete_credential(vault_id: str) -> None:
    if vault_id.startswith(_FERNET_PREFIX):
        return  # ciphertext dies with the row that referenced it
    sb = get_supabase()
    try:
        await sb.vault_delete_secret(vault_id)
    except Exception as e:  # noqa: BLE001
        logger.info(f"Vault secret delete failed: {e}")

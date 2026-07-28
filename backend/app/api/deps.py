"""Shared FastAPI dependencies — auth via Supabase JWT."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings
from ..services.supabase_service import get_supabase

bearer = HTTPBearer(auto_error=False)

DEV_EMAIL = "dev@localhost.dev"
_dev_user_cache: dict[str, Any] | None = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, Any]:
    settings = get_settings()
    if credentials is not None:
        user = await get_supabase().get_user_from_jwt(credentials.credentials)
        if user:
            return user
    # Development convenience: anonymous access maps to a real auth user so
    # FK constraints (migration_jobs.user_id -> auth.users) are satisfied.
    if settings.environment == "development":
        global _dev_user_cache
        if _dev_user_cache is None:
            try:
                _dev_user_cache = await get_supabase().get_or_create_dev_user(DEV_EMAIL)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(
                    status_code=503,
                    detail=f"Could not provision dev user in Supabase: {e}") from e
        return _dev_user_cache
    raise HTTPException(status_code=401, detail="Invalid or missing bearer token")

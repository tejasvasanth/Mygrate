"""Supabase client singleton + job/log helpers.

When Supabase is not configured (local dev/tests) a LocalSupabaseService keeps
jobs and logs in memory so the pipeline still runs end-to-end.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SupabaseService:
    """Thin async wrapper over the (sync) supabase-py client."""

    def __init__(self, url: str, service_role_key: str):
        from supabase import Client, create_client
        self.client: Client = create_client(url, service_role_key)

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    # ── migration_jobs ────────────────────────────────────────────
    async def create_job(self, data: dict[str, Any]) -> dict[str, Any]:
        def _do():
            return self.client.table("migration_jobs").insert(data).execute()
        res = await self._run(_do)
        return res.data[0]

    async def get_job(self, job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        def _do():
            q = self.client.table("migration_jobs").select("*").eq("id", job_id)
            if user_id:
                q = q.eq("user_id", user_id)
            return q.execute()
        res = await self._run(_do)
        return res.data[0] if res.data else None

    async def list_jobs(self, user_id: str) -> list[dict[str, Any]]:
        def _do():
            return (self.client.table("migration_jobs").select("*")
                    .eq("user_id", user_id).order("created_at", desc=True).execute())
        return (await self._run(_do)).data

    async def update_job(self, job_id: str, data: dict[str, Any]) -> None:
        def _do():
            return self.client.table("migration_jobs").update(data).eq("id", job_id).execute()
        await self._run(_do)

    async def get_job_by_share_token(self, token: str) -> dict[str, Any] | None:
        """Public lookup — no user scoping by design, so visibility must be
        checked by the caller before anything is returned."""
        def _do():
            return (self.client.table("migration_jobs").select("*")
                    .eq("share_token", token).execute())
        res = await self._run(_do)
        return res.data[0] if res.data else None

    # ── drift_monitors / drift_events ─────────────────────────────
    async def create_monitor(self, data: dict[str, Any]) -> dict[str, Any]:
        def _do():
            return self.client.table("drift_monitors").insert(data).execute()
        return (await self._run(_do)).data[0]

    async def list_monitors(self, user_id: str | None = None) -> list[dict[str, Any]]:
        def _do():
            q = self.client.table("drift_monitors").select("*")
            if user_id:
                q = q.eq("user_id", user_id)
            return q.order("created_at", desc=True).execute()
        return (await self._run(_do)).data

    async def get_monitor(self, monitor_id: str,
                          user_id: str | None = None) -> dict[str, Any] | None:
        def _do():
            q = self.client.table("drift_monitors").select("*").eq("id", monitor_id)
            if user_id:
                q = q.eq("user_id", user_id)
            return q.execute()
        res = await self._run(_do)
        return res.data[0] if res.data else None

    async def update_monitor(self, monitor_id: str, data: dict[str, Any]) -> None:
        def _do():
            return (self.client.table("drift_monitors").update(data)
                    .eq("id", monitor_id).execute())
        await self._run(_do)

    async def delete_monitor(self, monitor_id: str, user_id: str) -> None:
        def _do():
            return (self.client.table("drift_monitors").delete()
                    .eq("id", monitor_id).eq("user_id", user_id).execute())
        await self._run(_do)

    async def insert_drift_check(self, data: dict[str, Any]) -> dict[str, Any]:
        def _do():
            return self.client.table("drift_events").insert(data).execute()
        return (await self._run(_do)).data[0]

    async def list_drift_checks(self, monitor_id: str,
                                limit: int = 50) -> list[dict[str, Any]]:
        def _do():
            return (self.client.table("drift_events").select("*")
                    .eq("monitor_id", monitor_id)
                    .order("created_at", desc=True).limit(limit).execute())
        return (await self._run(_do)).data

    # ── migration_logs ────────────────────────────────────────────
    async def insert_log(self, job_id: str, level: str, agent: str,
                         message: str, metadata: dict[str, Any] | None = None) -> None:
        def _do():
            return self.client.table("migration_logs").insert({
                "job_id": job_id, "level": level, "agent": agent,
                "message": message, "metadata": metadata or {},
            }).execute()
        await self._run(_do)

    async def get_logs(self, job_id: str) -> list[dict[str, Any]]:
        def _do():
            return (self.client.table("migration_logs").select("*")
                    .eq("job_id", job_id).order("created_at").execute())
        return (await self._run(_do)).data

    # ── saved_connections ─────────────────────────────────────────
    async def create_connection(self, data: dict[str, Any]) -> dict[str, Any]:
        def _do():
            return self.client.table("saved_connections").insert(data).execute()
        return (await self._run(_do)).data[0]

    async def list_connections(self, user_id: str) -> list[dict[str, Any]]:
        def _do():
            return (self.client.table("saved_connections").select(
                "id, nickname, db_type, host, port, database_name, created_at")
                .eq("user_id", user_id).execute())
        return (await self._run(_do)).data

    async def get_connection(self, conn_id: str, user_id: str) -> dict[str, Any] | None:
        def _do():
            return (self.client.table("saved_connections").select("*")
                    .eq("id", conn_id).eq("user_id", user_id).execute())
        res = await self._run(_do)
        return res.data[0] if res.data else None

    async def delete_connection(self, conn_id: str, user_id: str) -> None:
        def _do():
            return (self.client.table("saved_connections").delete()
                    .eq("id", conn_id).eq("user_id", user_id).execute())
        await self._run(_do)

    # ── auth ──────────────────────────────────────────────────────
    async def get_user_from_jwt(self, jwt: str) -> dict[str, Any] | None:
        def _do():
            return self.client.auth.get_user(jwt)
        try:
            res = await self._run(_do)
            if res and res.user:
                return {"id": res.user.id, "email": res.user.email}
        except Exception as e:  # noqa: BLE001
            logger.info(f"JWT verification failed: {e}")
        return None

    async def get_or_create_dev_user(self, email: str) -> dict[str, Any]:
        """Dev-mode fallback: a real auth.users row so FK constraints hold."""
        def _do():
            users = self.client.auth.admin.list_users()
            if hasattr(users, "users"):  # paginated response in some SDK versions
                users = users.users
            for u in users:
                if u.email == email:
                    return {"id": u.id, "email": u.email}
            created = self.client.auth.admin.create_user(
                {"email": email, "email_confirm": True})
            return {"id": created.user.id, "email": created.user.email}
        return await self._run(_do)

    # ── vault (via SQL RPC functions, see supabase_setup.sql) ─────
    async def vault_create_secret(self, value: str) -> str:
        def _do():
            return self.client.rpc("vault_create_secret", {"secret_value": value}).execute()
        res = await self._run(_do)
        return str(res.data)

    async def vault_get_secret(self, secret_id: str) -> str:
        def _do():
            return self.client.rpc("vault_get_secret", {"secret_id": secret_id}).execute()
        res = await self._run(_do)
        return str(res.data)

    async def vault_delete_secret(self, secret_id: str) -> None:
        def _do():
            return self.client.rpc("vault_delete_secret", {"secret_id": secret_id}).execute()
        await self._run(_do)


class LocalSupabaseService:
    """In-memory stand-in used when Supabase env vars are absent (dev/tests)."""

    def __init__(self):
        self.jobs: dict[str, dict[str, Any]] = {}
        self.logs: list[dict[str, Any]] = []
        self.connections: dict[str, dict[str, Any]] = {}
        self.secrets: dict[str, str] = {}
        self.monitors: dict[str, dict[str, Any]] = {}
        self.drift_checks: list[dict[str, Any]] = []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def create_job(self, data: dict[str, Any]) -> dict[str, Any]:
        job = {
            "id": str(uuid.uuid4()), "status": "pending", "progress_pct": 0,
            "rows_migrated": 0, "rows_total": 0, "error_log": [],
            "options": {}, "created_at": self._now(), "updated_at": self._now(),
            **data,
        }
        self.jobs[job["id"]] = job
        return job

    async def get_job(self, job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if job and user_id and job.get("user_id") != user_id:
            return None
        return job

    async def list_jobs(self, user_id: str) -> list[dict[str, Any]]:
        return sorted([j for j in self.jobs.values() if j.get("user_id") == user_id],
                      key=lambda j: j["created_at"], reverse=True)

    async def update_job(self, job_id: str, data: dict[str, Any]) -> None:
        if job_id in self.jobs:
            self.jobs[job_id].update(data)
            self.jobs[job_id]["updated_at"] = self._now()

    async def get_job_by_share_token(self, token: str) -> dict[str, Any] | None:
        return next((j for j in self.jobs.values()
                     if j.get("share_token") == token), None)

    async def create_monitor(self, data: dict[str, Any]) -> dict[str, Any]:
        monitor = {"id": str(uuid.uuid4()), "created_at": self._now(), **data}
        self.monitors[monitor["id"]] = monitor
        return monitor

    async def list_monitors(self, user_id: str | None = None) -> list[dict[str, Any]]:
        return [m for m in self.monitors.values()
                if user_id is None or m.get("user_id") == user_id]

    async def get_monitor(self, monitor_id: str,
                          user_id: str | None = None) -> dict[str, Any] | None:
        monitor = self.monitors.get(monitor_id)
        if monitor and user_id and monitor.get("user_id") != user_id:
            return None
        return monitor

    async def update_monitor(self, monitor_id: str, data: dict[str, Any]) -> None:
        if monitor_id in self.monitors:
            self.monitors[monitor_id].update(data)

    async def delete_monitor(self, monitor_id: str, user_id: str) -> None:
        monitor = self.monitors.get(monitor_id)
        if monitor and monitor.get("user_id") == user_id:
            del self.monitors[monitor_id]

    async def insert_drift_check(self, data: dict[str, Any]) -> dict[str, Any]:
        check = {"id": str(uuid.uuid4()), "created_at": self._now(), **data}
        self.drift_checks.append(check)
        return check

    async def list_drift_checks(self, monitor_id: str,
                                limit: int = 50) -> list[dict[str, Any]]:
        checks = [c for c in self.drift_checks if c["monitor_id"] == monitor_id]
        return sorted(checks, key=lambda c: c["created_at"], reverse=True)[:limit]

    async def insert_log(self, job_id: str, level: str, agent: str,
                         message: str, metadata: dict[str, Any] | None = None) -> None:
        self.logs.append({
            "id": str(uuid.uuid4()), "job_id": job_id, "level": level,
            "agent": agent, "message": message, "metadata": metadata or {},
            "created_at": self._now(),
        })

    async def get_logs(self, job_id: str) -> list[dict[str, Any]]:
        return [l for l in self.logs if l["job_id"] == job_id]

    async def create_connection(self, data: dict[str, Any]) -> dict[str, Any]:
        conn = {"id": str(uuid.uuid4()), "created_at": self._now(), **data}
        self.connections[conn["id"]] = conn
        return conn

    async def list_connections(self, user_id: str) -> list[dict[str, Any]]:
        return [{k: v for k, v in c.items() if k != "credential_vault_id"}
                for c in self.connections.values() if c.get("user_id") == user_id]

    async def get_connection(self, conn_id: str, user_id: str) -> dict[str, Any] | None:
        conn = self.connections.get(conn_id)
        if conn and conn.get("user_id") != user_id:
            return None
        return conn

    async def delete_connection(self, conn_id: str, user_id: str) -> None:
        conn = self.connections.get(conn_id)
        if conn and conn.get("user_id") == user_id:
            del self.connections[conn_id]

    async def get_user_from_jwt(self, jwt: str) -> dict[str, Any] | None:
        return None

    async def get_or_create_dev_user(self, email: str) -> dict[str, Any]:
        return {"id": "00000000-0000-0000-0000-000000000001", "email": email}

    async def vault_create_secret(self, value: str) -> str:
        sid = str(uuid.uuid4())
        self.secrets[sid] = value
        return sid

    async def vault_get_secret(self, secret_id: str) -> str:
        return self.secrets[secret_id]

    async def vault_delete_secret(self, secret_id: str) -> None:
        self.secrets.pop(secret_id, None)


_instance: SupabaseService | LocalSupabaseService | None = None


def get_supabase() -> SupabaseService | LocalSupabaseService:
    """Singleton accessor. Falls back to the in-memory service when unconfigured."""
    global _instance
    if _instance is None:
        settings = get_settings()
        if settings.supabase_configured:
            _instance = SupabaseService(settings.supabase_url,
                                        settings.supabase_service_role_key)
            logger.info("Supabase client initialised.")
        else:
            _instance = LocalSupabaseService()
            logger.info("Supabase not configured — using in-memory local service.")
    return _instance


def reset_supabase() -> None:
    """Test helper."""
    global _instance
    _instance = None

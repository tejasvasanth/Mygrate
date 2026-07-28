"""API tests — FastAPI TestClient with the in-memory Supabase stand-in.

Celery is not exercised here: /start queueing is covered by running the
pipeline synchronously through MigrationPipeline in test_pipeline_end_to_end.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.migration_service import MigrationPipeline


@pytest.fixture()
def client(local_supabase):
    from main import app
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestConnections:
    def test_test_endpoint_ok(self, client, source_db):
        r = client.post("/api/v1/connections/test",
                        json={"db_type": "sqlite", "connection_string": source_db})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert set(body["tables"]) == {"users", "orders"}

    def test_test_endpoint_bad(self, client):
        r = client.post("/api/v1/connections/test",
                        json={"db_type": "postgres",
                              "connection_string": "postgresql://nouser:x@127.0.0.1:1/none"})
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_save_list_delete(self, client, source_db, local_supabase):
        r = client.post("/api/v1/connections", json={
            "nickname": "my sqlite", "db_type": "sqlite",
            "connection_string": source_db, "database_name": "source"})
        assert r.status_code == 201
        conn_id = r.json()["id"]
        # credential never returned
        assert "connection_string" not in r.json()
        assert "credential_vault_id" not in r.json()

        r = client.get("/api/v1/connections")
        assert len(r.json()) == 1

        r = client.delete(f"/api/v1/connections/{conn_id}")
        assert r.status_code == 204
        assert client.get("/api/v1/connections").json() == []


class TestMigrations:
    def _create(self, client, source_db, target_db, dry_run=True):
        r = client.post("/api/v1/migrations", json={
            "name": "sqlite to sqlite",
            "source_db_type": "sqlite", "target_db_type": "sqlite",
            "source_connection_string": source_db,
            "target_connection_string": target_db,
            "options": {"dry_run": dry_run, "chunk_size": 40},
        })
        assert r.status_code == 201, r.text
        return r.json()

    def test_create_and_get(self, client, source_db, target_db):
        job = self._create(client, source_db, target_db)
        assert job["status"] == "pending"
        r = client.get(f"/api/v1/migrations/{job['id']}")
        assert r.status_code == 200
        assert r.json()["name"] == "sqlite to sqlite"
        assert client.get("/api/v1/migrations").json()[0]["id"] == job["id"]

    def test_plan_404_before_run(self, client, source_db, target_db):
        job = self._create(client, source_db, target_db)
        assert client.get(f"/api/v1/migrations/{job['id']}/plan").status_code == 404

    def test_cancel(self, client, source_db, target_db):
        job = self._create(client, source_db, target_db)
        r = client.post(f"/api/v1/migrations/{job['id']}/cancel")
        assert r.status_code == 200
        assert client.get(
            f"/api/v1/migrations/{job['id']}").json()["status"] == "cancelled"

    async def test_pipeline_end_to_end(self, client, source_db, target_db, local_supabase):
        """Dry-run stops at approval; approving executes + validates (via pipeline)."""
        job = self._create(client, source_db, target_db, dry_run=True)
        job_id = job["id"]

        result = await MigrationPipeline(job_id, local_supabase).run()
        assert result["status"] == "awaiting_approval"

        r = client.get(f"/api/v1/migrations/{job_id}/plan")
        assert r.status_code == 200
        assert {t["source_table"] for t in r.json()["tables"]} == {"users", "orders"}

        result = await MigrationPipeline(job_id, local_supabase).execute_approved()
        assert result["status"] == "completed"
        assert result["execution"]["rows_migrated"] == 170
        assert result["validation"]["passed"] is True

        stored = await local_supabase.get_job(job_id)
        assert stored["status"] == "completed"
        assert stored["progress_pct"] == 100
        assert stored["validation_report"]["confidence_score"] >= 90

        r = client.get(f"/api/v1/migrations/{job_id}/logs")
        agents_seen = {log["agent"] for log in r.json()}
        assert {"schema_analyst", "data_profiler", "mapping_strategist",
                "migration_executor", "validation_auditor"} <= agents_seen

    def test_job_status_endpoint(self, client, source_db, target_db):
        job = self._create(client, source_db, target_db)
        r = client.get(f"/api/v1/jobs/{job['id']}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

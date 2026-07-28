"""Endpoint tests for the Tier 1–4 features, using the real SQLite fixtures
and the in-memory Supabase stand-in."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.migration_service import MigrationPipeline


@pytest.fixture()
def client(local_supabase):
    from main import app
    return TestClient(app)


@pytest.fixture()
async def planned_job(client, local_supabase, source_db, target_db):
    """A job run through analyze → profile → plan (stops at approval)."""
    r = client.post("/api/v1/migrations", json={
        "name": "test job", "source_db_type": "sqlite",
        "target_db_type": "sqlite",
        "source_connection_string": source_db,
        "target_connection_string": target_db,
        "options": {"dry_run": True}})
    job_id = r.json()["id"]
    await MigrationPipeline(job_id).run()
    return job_id


class TestSavedConnectionFlow:
    """Save a connection, then run a migration that references it by id."""

    def test_saved_connection_is_usable_as_a_migration_source(
            self, client, source_db, target_db):
        saved = client.post("/api/v1/connections", json={
            "nickname": "prod sqlite", "db_type": "sqlite",
            "connection_string": source_db, "database_name": "source"})
        assert saved.status_code == 201
        conn_id = saved.json()["id"]
        # The credential must never come back to the client.
        assert "connection_string" not in saved.json()
        assert "credential_vault_id" not in saved.json()

        job = client.post("/api/v1/migrations", json={
            "name": "via saved connection",
            "source_db_type": "sqlite", "target_db_type": "sqlite",
            "source_connection_id": conn_id,
            "target_connection_string": target_db,
            "options": {"dry_run": True}})
        assert job.status_code == 201
        # The job resolved the saved connection into a vault id, not a string.
        body = job.json()
        assert "source_connection_string" not in body

    def test_migration_with_unknown_connection_id_is_404(self, client, target_db):
        r = client.post("/api/v1/migrations", json={
            "name": "bad ref", "source_db_type": "sqlite",
            "target_db_type": "sqlite",
            "source_connection_id": "00000000-0000-0000-0000-000000000999",
            "target_connection_string": target_db})
        assert r.status_code == 404

    def test_migration_requires_one_of_id_or_string(self, client, target_db):
        r = client.post("/api/v1/migrations", json={
            "name": "neither", "source_db_type": "sqlite",
            "target_db_type": "sqlite",
            "target_connection_string": target_db})
        assert r.status_code == 422


class TestJobPayloadCarriesSubResources:
    """The UI reads these off the job, so they must be in the response."""

    @pytest.mark.anyio
    async def test_job_response_includes_quality_and_simulation_fields(
            self, client, planned_job):
        body = client.get(f"/api/v1/migrations/{planned_job}").json()
        # quality rides inside data_profile
        assert body["data_profile"]["quality"]["quality_score"] is not None
        # simulation and checkpoints are present (null/empty before they run)
        assert "simulation" in body
        assert body["simulation"] is None
        assert body["checkpoints"] == {}

    @pytest.mark.anyio
    async def test_simulation_appears_on_the_job_after_running(
            self, client, planned_job):
        from app.services.simulation_service import run_and_store_simulation

        await run_and_store_simulation(planned_job, sample_limit=50)
        body = client.get(f"/api/v1/migrations/{planned_job}").json()
        assert body["simulation"]["total_rows_simulated"] > 0


class TestPublicEndpoints:
    """T3-4 / T3-2 — no auth required."""

    def test_templates_index(self, client):
        r = client.get("/api/v1/templates")
        assert r.status_code == 200
        slugs = {t["slug"] for t in r.json()["templates"]}
        assert "django-sqlite-to-railway-postgres" in slugs

    def test_template_detail_and_404(self, client):
        r = client.get("/api/v1/templates/rails-mysql-to-neon-postgres")
        assert r.status_code == 200
        assert r.json()["type_overrides"]["TINYINT(1)"] == "BOOLEAN"
        assert client.get("/api/v1/templates/nope").status_code == 404

    def test_unknown_share_token_is_404(self, client):
        assert client.get("/api/v1/public/deadbeefdeadbeef").status_code == 404
        assert client.get(
            "/api/v1/public/deadbeefdeadbeef/badge.svg").status_code == 404


class TestSemanticEndpoints:
    @pytest.mark.anyio
    async def test_semantic_report_detects_seeded_patterns(self, client,
                                                           planned_job):
        r = client.get(f"/api/v1/migrations/{planned_job}/semantic-report")
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["schema_trust_score"] <= 100
        # the seed has email + phone columns and low-cardinality status columns
        detections = {(d["table"], d["column"]): d["inferred_semantic_type"]
                      for d in body["semantic_detections"]}
        assert detections.get(("users", "email")) == "email"
        assert detections.get(("users", "phone")) == "phone"
        enums = {(e["table"], e["column"]) for e in body["implicit_enums"]}
        assert ("users", "status") in enums
        # is_verified holds only 0/1
        bools = {(b["table"], b["column"]) for b in body["implicit_booleans"]}
        assert ("users", "is_verified") in bools

    @pytest.mark.anyio
    async def test_implicit_fk_detected_between_orders_and_users(
            self, client, planned_job):
        body = client.get(
            f"/api/v1/migrations/{planned_job}/semantic-report").json()
        # orders.user_id has a declared FK in the seed, so it must NOT appear
        # as an implicit one.
        implicit = {(f["table"], f["column"])
                    for f in body["implicit_foreign_keys"]}
        assert ("orders", "user_id") not in implicit

    @pytest.mark.anyio
    async def test_preview_diff_marks_mismatches(self, client, planned_job):
        r = client.get(f"/api/v1/migrations/{planned_job}/preview-diff")
        assert r.status_code == 200
        body = r.json()
        assert body["total_count"] > 0
        assert body["differing_count"] > 0
        assert all(r["differs"] for r in body["rows"][:body["differing_count"]])

    @pytest.mark.anyio
    async def test_quality_report_available_after_profiling(self, client,
                                                            planned_job):
        r = client.get(f"/api/v1/migrations/{planned_job}/quality-report")
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["quality_score"] <= 100
        assert "issues" in body and isinstance(body["issues"], list)

    def test_semantic_report_404_before_profiling(self, client, source_db,
                                                  target_db):
        job_id = client.post("/api/v1/migrations", json={
            "name": "unprofiled", "source_db_type": "sqlite",
            "target_db_type": "sqlite",
            "source_connection_string": source_db,
            "target_connection_string": target_db}).json()["id"]
        assert client.get(
            f"/api/v1/migrations/{job_id}/semantic-report").status_code == 404
        assert client.get(
            f"/api/v1/migrations/{job_id}/quality-report").status_code == 404


class TestTablePlanAndRollback:
    @pytest.mark.anyio
    async def test_table_plan_orders_parents_before_children(self, client,
                                                             planned_job):
        r = client.get(f"/api/v1/migrations/{planned_job}/tables")
        assert r.status_code == 200
        order = r.json()["load_order"]
        # orders references users, so users must load first
        assert order.index("users") < order.index("orders")
        by_name = {t["table"]: t for t in r.json()["tables"]}
        assert by_name["orders"]["depends_on"] == ["users"]
        assert by_name["users"]["status"] == "pending"

    @pytest.mark.anyio
    async def test_rollback_script_downloads_and_drops_in_reverse(
            self, client, planned_job):
        r = client.get(f"/api/v1/migrations/{planned_job}/rollback-script")
        assert r.status_code == 200
        assert "attachment" in r.headers["content-disposition"]
        body = r.text
        assert body.index("orders") < body.index("users")
        assert "manual rollback GUIDE" in body


class TestShareAndBadge:
    @pytest.mark.anyio
    async def test_share_requires_completed_job(self, client, planned_job):
        r = client.post(f"/api/v1/migrations/{planned_job}/share",
                        json={"visibility": "public"})
        assert r.status_code == 409

    @pytest.mark.anyio
    async def test_share_then_public_report_and_badge(self, client, local_supabase,
                                                      planned_job):
        await local_supabase.update_job(planned_job, {
            "status": "completed",
            "validation_report": {"confidence_score": 99.4, "tables": {}}})
        r = client.post(f"/api/v1/migrations/{planned_job}/share",
                        json={"visibility": "public", "redact_names": True})
        assert r.status_code == 200
        token = r.json()["token"]
        assert "badge_markdown" in r.json()

        pub = client.get(f"/api/v1/public/{token}")
        assert pub.status_code == 200
        assert pub.json()["confidence_score"] == 99.4
        assert pub.json()["names_redacted"] is True

        badge = client.get(f"/api/v1/public/{token}/badge.svg")
        assert badge.status_code == 200
        assert badge.headers["content-type"].startswith("image/svg+xml")
        assert "99.4%" in badge.text

    @pytest.mark.anyio
    async def test_private_share_is_not_publicly_readable(
            self, client, local_supabase, planned_job):
        await local_supabase.update_job(planned_job, {
            "status": "completed",
            "validation_report": {"confidence_score": 90, "tables": {}}})
        token = client.post(f"/api/v1/migrations/{planned_job}/share",
                            json={"visibility": "public"}).json()["token"]
        assert client.get(f"/api/v1/public/{token}").status_code == 200
        # flipping to private must immediately close the link
        client.post(f"/api/v1/migrations/{planned_job}/share",
                    json={"visibility": "private"})
        assert client.get(f"/api/v1/public/{token}").status_code == 404


class TestMonitoring:
    @pytest.mark.anyio
    async def test_enroll_requires_completed_migration(self, client, planned_job):
        r = client.post("/api/v1/monitoring", json={"job_id": planned_job})
        assert r.status_code == 409

    @pytest.mark.anyio
    async def test_enroll_check_and_drift_timeline(self, client, local_supabase,
                                                   planned_job, target_db):
        # Complete the job so a baseline can be taken from the target.
        await MigrationPipeline(planned_job).run(execute=True)
        r = client.post("/api/v1/monitoring", json={
            "job_id": planned_job,
            "alerts": {"email": "eng@example.com"}})
        assert r.status_code == 201
        monitor = r.json()
        assert monitor["baseline_table_count"] == 2
        assert monitor["alerts_configured"] == {
            "email": True, "slack": False, "pagerduty": False}
        # the vault id must never reach the client
        assert "target_credential_id" not in monitor

        mid = monitor["id"]
        check = client.post(f"/api/v1/monitoring/{mid}/check")
        assert check.status_code == 202
        # nothing changed since the baseline
        assert check.json()["has_drift"] is False
        assert check.json()["health_score"] == 100

        drift = client.get(f"/api/v1/monitoring/{mid}/drift")
        assert drift.status_code == 200
        assert len(drift.json()["timeline"]) == 1

        report = client.get(f"/api/v1/monitoring/{mid}/health-report")
        assert report.status_code == 200
        assert "healthy" in report.json()["headline"]

    @pytest.mark.anyio
    async def test_drift_detected_after_target_schema_changes(
            self, client, local_supabase, planned_job, target_db):
        await MigrationPipeline(planned_job).run(execute=True)
        mid = client.post("/api/v1/monitoring",
                          json={"job_id": planned_job}).json()["id"]

        # Drop a column in the target behind Migrate's back.
        import sqlite3
        conn = sqlite3.connect(target_db)
        conn.execute("ALTER TABLE users DROP COLUMN phone")
        conn.commit()
        conn.close()

        check = client.post(f"/api/v1/monitoring/{mid}/check").json()
        assert check["has_drift"] is True
        assert check["counts"]["critical"] >= 1
        assert check["health_score"] < 100
        kinds = {e["kind"] for e in check["events"]}
        assert "column_dropped" in kinds

        # Re-baselining accepts the new shape as normal.
        assert client.post(f"/api/v1/monitoring/{mid}/rebaseline").status_code == 200
        assert client.post(f"/api/v1/monitoring/{mid}/check").json()["has_drift"] \
            is False

    @pytest.mark.anyio
    async def test_monitor_is_scoped_to_its_owner(self, client, local_supabase,
                                                  planned_job):
        await MigrationPipeline(planned_job).run(execute=True)
        mid = client.post("/api/v1/monitoring",
                          json={"job_id": planned_job}).json()["id"]
        await local_supabase.update_monitor(mid, {"user_id": "somebody-else"})
        assert client.get(f"/api/v1/monitoring/{mid}").status_code == 404
        assert client.get(f"/api/v1/monitoring/{mid}/drift").status_code == 404


class TestSimulationAndResume:
    @pytest.mark.anyio
    async def test_simulation_shows_before_and_after(self, client, planned_job):
        from app.services.simulation_service import run_and_store_simulation

        result = await run_and_store_simulation(planned_job, sample_limit=100)
        assert result["total_rows_simulated"] > 0
        r = client.get(f"/api/v1/migrations/{planned_job}/simulation")
        assert r.status_code == 200
        users = r.json()["tables"]["users"]
        assert users["rows"], "expected preview rows"
        row = users["rows"][0]
        assert "source" in row and "transformed" in row

    def test_simulation_404_before_run(self, client, source_db, target_db):
        job_id = client.post("/api/v1/migrations", json={
            "name": "nosim", "source_db_type": "sqlite",
            "target_db_type": "sqlite",
            "source_connection_string": source_db,
            "target_connection_string": target_db}).json()["id"]
        assert client.get(
            f"/api/v1/migrations/{job_id}/simulation").status_code == 404

    @pytest.mark.anyio
    async def test_resume_rejects_an_active_job(self, client, local_supabase,
                                                planned_job):
        await local_supabase.update_job(planned_job, {"status": "executing"})
        r = client.post(f"/api/v1/migrations/{planned_job}/resume", json={})
        assert r.status_code == 409

    @pytest.mark.anyio
    async def test_checkpoints_are_written_during_execution(
            self, client, local_supabase, planned_job):
        await MigrationPipeline(planned_job).run(execute=True)
        job = await local_supabase.get_job(planned_job)
        checkpoints = job.get("checkpoints") or {}
        assert set(checkpoints) == {"users", "orders"}
        assert all(c["done"] for c in checkpoints.values())
        assert checkpoints["orders"]["rows_committed"] == 120

    @pytest.mark.anyio
    async def test_resume_after_crash_does_not_duplicate_rows(
            self, client, local_supabase, planned_job, target_db):
        """The T2-3 guarantee: a worker that dies mid-table resumes without
        re-migrating committed rows and without dropping them."""
        from app.agents.migration_executor import MigrationExecutor
        from app.connectors.sqlite import SQLiteConnector

        job = await local_supabase.get_job(planned_job)
        plan = job["migration_plan"]
        source = SQLiteConnector(job_source(job))
        target = SQLiteConnector(target_db)
        await source.connect()
        await target.connect()

        crash_after = {"n": 0}
        saved: dict[str, dict] = {}

        async def checkpoint_sink(table, state):
            saved[table] = state

        class CrashingExecutor(MigrationExecutor):
            async def _emit(self, level, message, metadata=None):
                # Die partway through the 'orders' table, after chunks commit.
                if "chunk" in message and "orders" in message:
                    crash_after["n"] += 1
                    if crash_after["n"] == 2:
                        raise RuntimeError("worker died")

        try:
            with pytest.raises(RuntimeError):
                await CrashingExecutor(
                    source, target, plan, planned_job, chunk_size=25,
                    checkpoint_sink=checkpoint_sink).run()

            assert saved["orders"]["rows_committed"] > 0
            assert not saved["orders"]["done"]
            partial = await target.count_rows("orders")
            assert 0 < partial < 120

            # Resume with the checkpoints the crashed run left behind.
            report = await MigrationExecutor(
                source, target, plan, planned_job, chunk_size=25,
                checkpoint_sink=checkpoint_sink,
                checkpoints=saved).run()
        finally:
            await source.close()
            await target.close()

        target2 = SQLiteConnector(target_db)
        await target2.connect()
        try:
            # Every row present exactly once — no duplicates, no losses.
            assert await target2.count_rows("orders") == 120
            rows = await target2.sample_rows("orders", 200)
            ids = [r["id"] for r in rows]
            assert len(ids) == len(set(ids)) == 120
        finally:
            await target2.close()
        # 'users' finished before the crash, so the resume skipped it entirely.
        assert report["tables"]["users"]["skipped"] is True


def job_source(job: dict) -> str:
    """Source connection string straight from the in-memory vault."""
    from app.services.supabase_service import get_supabase
    return get_supabase().secrets[job["source_credential_id"]]

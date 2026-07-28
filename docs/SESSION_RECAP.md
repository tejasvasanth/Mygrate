# Migrate — session recap (2026-07-27)

Handoff document. Covers what was built, why certain decisions were made, the
bugs that surfaced, and what still needs attention.

**Final state:** 118 backend tests passing (3 skipped), frontend `tsc` clean and
building. Tiers 1–4 implemented, Tier 5 designed.

---

## 1. What was built

### Tier 1 — Core thesis (semantic detection)

| Item | Where |
|---|---|
| Extended semantic type library (T1-1) | `backend/app/utils/semantic_types.py` |
| Semantic Mismatch Report Card (T1-2) | `backend/app/utils/semantic_report.py` |
| Migration Preview Diff (T1-3) | `build_preview_diff()` in same file |
| Relationship intelligence (T1-4) | `detect_implicit_foreign_keys()` |
| Data Quality Report (T1-5) | `backend/app/utils/data_quality.py` |

**Detectors implemented** (all ≥95% match threshold on sampled non-null values):
email, phone, UUID, URL, ISO date-string, JSON-as-string, Unix timestamp
(epoch range 2000–2038, seconds and milliseconds), currency (FLOAT/DOUBLE with
≤2dp plus money-like column name), zip/postal code (leading zeros present, or
declared INT which has already lost them). Plus the pre-existing implicit
boolean and implicit enum detection.

Each detection returns `{semantic_type, confidence_pct, evidence_summary,
danger?, pii?}`. Danger flags feed the red "data loss risk" section.

**Relationship intelligence:** for every `*_id` column without a declared FK,
checks whether its sampled values are a subset of another table's sampled PK
values. Reports match percentage and whether the column name matches the
referenced table. Columns with an existing declared FK are excluded.

**Data quality checks:** duplicates in UNIQUE-indexed columns, empty strings in
NOT NULL columns, sentinel dates (`0000-00-00`, `1970-01-01`), numeric
sentinels (`-1`, `9999`, …) when they exceed 5% of rows, and orphaned rows.

### Tier 2 — Trust & safety

| Item | Where |
|---|---|
| Simulation mode (T2-1) | `utils/simulate.py`, `services/simulation_service.py` |
| Rollback script generation (T2-2) | `utils/rollback.py` |
| Checkpointing / resume (T2-3) | `agents/migration_executor.py`, `services/migration_service.py` |
| Incremental table-by-table (T2-4) | `GET /migrations/{id}/tables` |
| Source read-only enforcement (T2-5) | `utils/readonly.py` |

### Tier 3 — Virality

| Item | Where |
|---|---|
| CLI (T3-1) | `backend/cli.py` — Typer + Rich |
| Public shareable report (T3-2) | `utils/public_report.py`, `api/public.py` |
| PDF report (T3-3) | `utils/pdf_report.py` |
| Migration templates (T3-4) | `utils/templates.py` |
| README badge (T3-5) | `badge_svg()` / `badge_markdown()` |

CLI commands: `audit`, `plan`, `run`, `drift`, `templates`.

### Tier 4 — Subscription product

| Item | Where |
|---|---|
| Schema drift monitoring (T4-1) | `utils/drift.py`, `services/drift_service.py` |
| Drift alerts (T4-2) | `services/notifier.py` |
| Regression detection (T4-3) | `_semantic_regression()` in `utils/drift.py` |
| Health score / digests (T4-4) | `monthly_health_report()`, `services/digest_service.py` |

### Tier 5 — Designed, not built

`docs/TIER5_ENTERPRISE_DESIGN.md` covers team approvals, on-prem agent,
scheduling and RBAC. Each section names the one hard-to-reverse decision.

---

## 2. Key design decisions (and why)

**Reports are computed on the fly, not persisted.** `semantic_report.py`,
`data_quality.py` etc. are pure functions over the job's stored
`schema_snapshot` + `data_profile`. No new Supabase columns for reports, and
every report works retroactively on jobs that ran before the feature existed.

**Trust score counts distinct columns, not findings.** The first implementation
summed findings across buckets, so a column that was both an implicit enum and
never-null was penalised twice. The ratio could exceed 1 and every schema
pegged at 0. Now: hard mismatches weigh 1.0, never-null-but-nullable weighs
0.35, then extra deductions for dangerous mismatches (5 each), implicit FKs
(3 each) and PII (1 each). Verified curve: clean schema = 100, three problems
in twenty columns = 80, a schema where every column is mistyped ≈ 0.

**PagerDuty only fires on CRITICAL.** Paging someone at 3am because an index
was added is how teams learn to ignore alerts. Email and Slack get everything;
PagerDuty gets data-loss-risk events only.

**Drift severity follows data-loss risk, not novelty.** Dropped column, dropped
table, dropped NOT NULL, and narrowing type changes are CRITICAL. New NOT NULL
column without a default is WARNING. Added index is INFO and costs zero health
points.

**Baseline snapshots strip row counts.** Otherwise ordinary inserts would
register as "drift". Drift means *structural* drift.

**Public reports redact by default.** Table names become `table_1`, `table_2`.
Connection strings, credentials, vault IDs, user IDs and column names are never
included on any code path. A private token returns 404, never 403 — a 403
would confirm the report exists.

**Sub-resources ride on the job payload.** `simulation`, `checkpoints`,
`share_*` and `data_profile.quality` are returned with the job so the UI never
polls endpoints that legitimately 404 before the resource exists.

---

## 3. Bugs found and fixed

These were all caught by tests written alongside the features.

**1. ISO dates detected as phone numbers.** `2026-01-15` is digits and dashes,
which satisfies the phone regex. Dates are the more specific pattern, so the
ISO-date check now runs before the phone check.

**2. Simulation reported TINYINT→BOOLEAN as unchanged.** Python evaluates
`1 == True` as true, so the single most important coercion to show a user was
invisible. Comparison is now type-aware (`isinstance(x, bool)` must match on
both sides).

**3. Resume duplicated rows and crashed on UNIQUE violations.** The crash test
committed chunk 2 but only checkpointed chunk 1, so resume re-inserted rows
that were already present. Root cause: **a checkpoint is a lower bound on
progress** — a chunk can commit and the worker die before the checkpoint is
written. Fix: resumed writes are idempotent (`fail` → `skip` conflict strategy,
scoped to tables actually being resumed). Also: a resuming table is never
dropped and never re-created, or the committed rows the checkpoint promises
would be destroyed.

**4. CLI crashed on Windows.** `UnicodeEncodeError` — cp1252 can't encode the
`→` and box-drawing characters. `cli.py` now forces UTF-8 on stdout/stderr
before Rich captures the streams.

**5. Trust score pegged at 0.** See "distinct columns" above.

**6. Saved connections were a dead end.** They could be created and deleted but
never used — the New Migration wizard only accepted a pasted string, despite
the backend already supporting `source_connection_id`.

---

## 4. API surface added

```
# Tier 1
GET  /api/v1/migrations/{id}/semantic-report
GET  /api/v1/migrations/{id}/preview-diff
GET  /api/v1/migrations/{id}/quality-report
GET  /api/v1/migrations/{id}/confidence-breakdown

# Tier 2
POST /api/v1/migrations/{id}/simulate
GET  /api/v1/migrations/{id}/simulation
GET  /api/v1/migrations/{id}/rollback-script
GET  /api/v1/migrations/{id}/tables
POST /api/v1/migrations/{id}/resume

# Tier 3 (no auth)
GET  /api/v1/templates
GET  /api/v1/templates/{slug}
POST /api/v1/migrations/{id}/share
GET  /api/v1/public/{token}
GET  /api/v1/public/{token}/badge.svg
GET  /api/v1/public/{token}/badge.md
GET  /api/v1/compliance

# Tier 4
POST   /api/v1/monitoring
GET    /api/v1/monitoring
GET    /api/v1/monitoring/{id}/drift
POST   /api/v1/monitoring/{id}/check
POST   /api/v1/monitoring/{id}/rebaseline
GET    /api/v1/monitoring/{id}/health-report
PATCH  /api/v1/monitoring/{id}
DELETE /api/v1/monitoring/{id}
```

`POST /connections/test` now also returns `has_write_access`,
`privilege_evidence` and `readonly_advice` (T2-5). The probe is read-only — it
asks the engine what the credential may do, never attempts a write.

---

## 5. Frontend added

**Pages:** `Monitoring.tsx` (drift dashboard with timeline), `Templates.tsx`,
`PublicReport.tsx` (route `/r/:token`).

**Components:** `SemanticReportCard` (large gauge, red/amber/green tiles,
dangerous-mismatch panel, implicit-FK table), `PreviewDiff` (side-by-side with
acknowledgement gate), `QualityReportCard`, `SimulationView` (before/after with
changed cells highlighted), `TablePlanCard`, `SharePanel`, `ConfidenceBreakdown`,
`ComplianceMatrix`, `SaveConnectionModal`.

**Approval gate (T1-3):** the "Approve & execute" button is disabled until the
engineer ticks "I have reviewed these N mismatches" in the preview diff.

Sidebar gained *Drift monitoring* and *Templates*.

---

## 6. Things that need attention

### Run the SQL migration
`supabase/002_tier1_to_tier4.sql` must be run in the Supabase SQL editor. It
adds `checkpoints`, `simulation`, `final_report`, `share_token`,
`share_visibility`, `share_redact_names` to `migration_jobs`, and creates the
`drift_monitors` and `drift_events` tables with RLS policies. It is idempotent.

> Note: this file was edited outside the session and currently has a stray
> line at the top (`243qz`) that will cause a syntax error. Remove it before
> running.

### Restart the Celery worker after agent changes
`.env` points at a real hosted Supabase, so the API process and the Celery
worker share a database. A worker started before a code change will keep
running the old pipeline and persist its results — which looks exactly like a
frontend bug. This caused real confusion mid-session: profiles came back
without any semantic detections because a stale worker produced them.

No worker was running at the end of the session, so the next one started will
pick up current code.

### Jobs profiled before T1-5
Their `data_profile` has no `quality` key, so the quality card simply does not
render. Re-run the migration to populate it.

### New dependencies
`typer` and `rich` were added to `backend/requirements.txt`.

### Celery beat
Drift monitoring needs beat running for the daily sweep:
```
celery -A app.workers.celery_app beat
```
Schedules: drift sweep daily at 03:00 UTC, health digests on the 1st at 08:00 UTC.

---

## 7. Test coverage added

| File | Covers |
|---|---|
| `tests/test_semantic_types.py` | every detector, plus negative cases (free text, plain digits, small ints) and implicit-FK detection |
| `tests/test_data_quality.py` | all five quality checks, rollback dialects, simulation change tracking |
| `tests/test_drift.py` | drift severity rules, semantic regression, public report redaction, badges, templates, read-only grants, PDF rendering |
| `tests/test_new_endpoints.py` | endpoint integration against real SQLite fixtures — including live drift detection after an `ALTER TABLE DROP COLUMN`, the crash-and-resume guarantee, share/badge visibility, and the saved-connection flow |
| `tests/test_semantic_report.py` | report card, preview diff, confidence breakdown, compliance matrix |

The most valuable test is
`test_resume_after_crash_does_not_duplicate_rows` — it kills an executor
mid-table, resumes from the checkpoint, and asserts exactly 120 rows with no
duplicates and no losses.

---

## 8. Suggested next steps

1. **Clean up and run `002_tier1_to_tier4.sql`** (remove the stray first line).
2. **Restart the Celery worker**, re-run a migration, and confirm the semantic
   detections, quality card and implicit FKs all populate in the UI.
3. **Wire alert configuration into the UI.** The monitoring API accepts email /
   Slack / PagerDuty settings at enrollment, but the frontend currently enrolls
   with no alert channels — there is no settings form for them yet.
4. **Frontend bundle is 2.5 MB** (758 kB gzipped) and Vite warns about it.
   Route-level code splitting would help, particularly for the xterm and
   Recharts dependencies.
5. **Tier 5**: start with RBAC — everything else assumes an org boundary, and
   doing it first avoids a second backfill of `org_id`.

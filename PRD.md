# Product Requirements Document (PRD)
## Agentic Database Migration Tool

**Document version:** 1.0
**Last updated:** 2026-07-25
**Owner:** tejaswizard007@gmail.com
**Status:** In development (pre-alpha)

> This PRD is the product-and-scope companion to `CLAUDE.md` (the technical "god file"). `CLAUDE.md` governs *how* to build; this PRD governs *what* we are building, *for whom*, and *why*. Where they conflict on implementation detail, `CLAUDE.md` wins; where they conflict on product scope, this PRD wins.

---

## 1. Overview

### 1.1 Problem statement
Database migrations are slow, expensive, and error-prone. They require expert DBAs, take weeks-to-months, cost five-to-six figures in consulting, and still fail silently on semantic mismatches (e.g., a `TINYINT(1)` that was *really* a boolean, a string column that was *really* an enum, a nested document that should become a relation).

### 1.2 Solution
A fully agentic migration tool that reads an entire source database (schema + data), reasons about what the data *means* using an AI agent pipeline, produces a human-reviewable migration plan, then executes and validates the migration against any supported target database — with zero manual mapping configuration required.

### 1.3 Tagline
*"Database migrations take months and cost six figures. We do it in hours — without a DBA."*

### 1.4 Value proposition
| Stakeholder | Value |
|---|---|
| Startup / solo dev | Move dev SQLite → prod Postgres in minutes, safely. |
| Engineering team | Cross-paradigm migrations (SQL ↔ Mongo) without a specialist. |
| Data / platform team | Auditable plan + validation report for every migration. |

---

## 2. Goals & non-goals

### 2.1 Goals (v1)
- G1 — Connect to a source and target DB with just a connection string, no manual schema config.
- G2 — Auto-generate a human-reviewable migration plan using AI.
- G3 — Execute migrations in memory-safe chunks with live progress.
- G4 — Validate every migration and produce a confidence score.
- G5 — Keep user DB credentials encrypted at all times (never plaintext at rest, never in logs).
- G6 — Support the migration matrix in §9.

### 2.2 Non-goals (v1 — explicitly out of scope)
- N1 — Change Data Capture (CDC) / zero-downtime live sync. v1 recommends read-only source during migration.
- N2 — Automatic rollback of a partially migrated target. (Report + manual remediation only.)
- N3 — Schema *versioning* / ongoing sync after the one-time migration.
- N4 — Databases outside the supported matrix (Oracle, SQL Server, Cassandra, etc.).
- N5 — On-prem/air-gapped deployment. v1 is a hosted SaaS.

---

## 3. Target users & personas

| Persona | Description | Primary job-to-be-done |
|---|---|---|
| **Solo Sam** | Indie/solo developer | "Get my dev DB into production without breaking data." |
| **Team Tara** | Backend engineer at a small startup | "Migrate MySQL → Postgres for the team without hiring a DBA." |
| **Platform Priya** | Platform/data engineer | "Re-platform SQL → Mongo with an audit trail I can defend." |

Primary persona for v1: **Team Tara**.

---

## 4. User stories

- As a user, I can sign up and log in securely (Supabase Auth).
- As a user, I can enter a source DB connection and test it before saving.
- As a user, I can optionally save a connection for reuse (credentials go to the vault, never shown again).
- As a user, I can create a migration by choosing a source and target and setting options.
- As a user, I can review an AI-generated migration plan and approve it before any data moves.
- As a user, I can watch live progress (status, rows migrated, streaming logs) in real time.
- As a user, I get a validation report with a confidence score when the job completes.
- As a user, I can cancel a running migration.
- As a user, I can see a history of all my migrations and their outcomes.

---

## 5. Functional requirements

### 5.1 Connections
- FR-C1 — Support connection input via connection string per DB type (Postgres, MySQL, MongoDB, SQLite).
- FR-C2 — `Test` validates connectivity + runs a lightweight schema scan; never persists credentials.
- FR-C3 — `Save` stores the credential in Supabase Vault and persists only the vault ID.
- FR-C4 — Listing saved connections never returns credentials.
- FR-C5 — Deleting a saved connection deletes its vault secret.

### 5.2 The 5-agent pipeline (core product)
Runs in sequence; each agent consumes the previous agent's output.

1. **Schema Analyst** — reads tables, columns, types, constraints, indexes, FK relationships → `SchemaSnapshot`.
2. **Data Profiler** — samples ≥1,000 rows/collection; detects implicit booleans, implicit enums (<20 distinct), PII (name-regex), NULL %, date-format inconsistencies → `DataProfile`.
3. **Mapping Strategist (AI brain)** — consumes schema + profile + source/target types + user options + type-coercion reference; outputs a strict-JSON `MigrationPlan` (per-table target names, column mappings + coercions, transformation rules, relationship handling, warnings).
4. **Migration Executor** — executes the plan in configurable chunks (default 1,000 rows), never loading a full table into memory; logs every chunk; updates `progress_pct`/`rows_migrated`; on error follows fail-fast or skip-errors per job option.
5. **Validation Auditor** — always runs; row-count comparison, sample-hash checks, referential-integrity checks; flags any table with >0.1% row-count mismatch; writes `ValidationReport` with a 0–100% confidence score.

### 5.3 Plan approval (dry run)
- FR-P1 — A plan is always generated before execution.
- FR-P2 — When dry-run/approval is required, execution blocks until the user approves the plan.

### 5.4 Jobs & real-time
- FR-J1 — Migration jobs run asynchronously via Celery; the start endpoint returns 202 immediately.
- FR-J2 — Frontend receives live updates via Supabase Realtime on `migration_jobs` + `migration_logs` (no polling).
- FR-J3 — Users can cancel a running job.

### 5.5 History & reporting
- FR-R1 — Dashboard lists all of a user's jobs with status + outcome.
- FR-R2 — Completed jobs expose a downloadable validation report.

---

## 6. Non-functional requirements

| # | Requirement | Target |
|---|---|---|
| NFR-1 | Memory safety | A 100k-row table migrates without exceeding ~512MB worker memory. |
| NFR-2 | Credential security | Credentials never at rest in plaintext, never logged, never returned to frontend. |
| NFR-3 | Isolation | Row-Level Security ensures users only ever see their own jobs/logs/connections. |
| NFR-4 | Observability | Every log entry is structured with `job_id`, `agent`, `level`. |
| NFR-5 | Resilience | Killing a worker mid-job resumes cleanly or fails with a clear error (no silent corruption). |
| NFR-6 | Responsiveness | Realtime log/progress latency perceived as "live" (< ~2s). |
| NFR-7 | No silent failures | Every caught error is written to `migration_logs`. |

---

## 7. Architecture summary

- **Frontend:** React 18 + Vite + TypeScript, TanStack Query (server state), Zustand (UI state), Ant Design + Tailwind, Supabase JS (auth + realtime), Axios → FastAPI, xterm.js (live log), Recharts (stats).
- **Backend:** Python 3.11, FastAPI (async), SQLAlchemy 2.x + async drivers (asyncpg, aiomysql, pymongo, aiosqlite) for *user* DBs, Celery + Redis for jobs.
- **App data / auth / realtime / secrets:** Supabase (hosted Postgres, Auth, Realtime, Vault).
- **AI brain:** Google Gemini via `google-genai` (model `gemini-3.5-flash`) powering the Mapping Strategist. *(Note: this supersedes the Anthropic reference in `CLAUDE.md` §18 per current project direction.)*
- **Infra:** Docker Compose for local test DBs + Redis only; backend containerized for deploy.

Data flow:
```
UI wizard → POST /migrations → POST /migrations/{id}/start
  → 202 Accepted → Celery worker runs 5-agent pipeline
  → agents write progress/logs to Supabase
  → UI subscribes via Realtime → live status + logs
```

---

## 8. API surface (v1)

All routes under `/api/v1`, JWT-authenticated except `/health`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness. |
| GET | `/api/v1/migrations` | List user's jobs. |
| POST | `/api/v1/migrations` | Create a job. |
| GET | `/api/v1/migrations/{id}` | Job detail. |
| POST | `/api/v1/migrations/{id}/start` | Kick off Celery pipeline (202). |
| POST | `/api/v1/migrations/{id}/cancel` | Cancel a running job. |
| GET | `/api/v1/migrations/{id}/plan` | Get AI plan. |
| POST | `/api/v1/migrations/{id}/approve` | Approve plan → allow execution. |
| GET | `/api/v1/migrations/{id}/logs` | Job logs. |
| POST | `/api/v1/connections/test` | Test connection (never saved). |
| POST | `/api/v1/connections` | Save connection (vault). |
| GET | `/api/v1/connections` | List saved connections (no creds). |
| DELETE | `/api/v1/connections/{id}` | Delete a saved connection. |

---

## 9. Supported migration matrix

| Source → Target | Difficulty | Notes |
|---|---|---|
| PostgreSQL → MySQL | Low | Minor type differences. |
| MySQL → PostgreSQL | Low | Common path. |
| SQLite → PostgreSQL | Low | Dev → prod. |
| SQLite → MySQL | Low | |
| PostgreSQL → SQLite | Medium | Type downgrades. |
| PostgreSQL → MongoDB | High | Relational → document. |
| MongoDB → PostgreSQL | High | Denormalization decisions. |
| MySQL → MongoDB | High | |
| MongoDB → MySQL | High | |
| Any → same type | Low | Schema copy + data transfer. |

---

## 10. Data model (app database)

Core Supabase tables (full DDL in `CLAUDE.md` §5):
- **`migration_jobs`** — job status, source/target types, vault credential IDs, `migration_plan`, `schema_snapshot`, `data_profile`, options, progress, counts, `error_log`, `validation_report`, timestamps. RLS + Realtime enabled.
- **`migration_logs`** — per-job structured log lines (`level`, `agent`, `message`, `metadata`). RLS + Realtime enabled.
- **`saved_connections`** — reusable connections storing only a `credential_vault_id`. RLS enabled.

Job status lifecycle:
```
pending → analyzing → profiling → planning → (awaiting approval) → executing → validating → completed
                                                                              ↘ failed
```

---

## 11. Key UX flows

### 11.1 New Migration wizard (3 steps)
1. **Source** — pick DB type, enter/select connection, `Test`.
2. **Target** — same for target.
3. **Options** — name, tables to skip (populated from schema scan), conflict strategy (skip / overwrite / fail), dry-run toggle → submit + start.

### 11.2 Migration detail (real-time)
- Status badge across the lifecycle.
- On `planning`: render the AI plan with an `Approve` button.
- Progress bar (`rows_migrated / rows_total`).
- Live xterm.js log via Realtime.
- Validation report card + download on completion.

---

## 12. Security & privacy

- Service-role / API keys are backend-only, never shipped to the frontend, never logged.
- User DB credentials: test-only endpoint never persists; save flow writes immediately to Supabase Vault; runtime decrypts to memory only; deletion removes the vault secret.
- RLS enforces per-user data isolation on all app tables.
- The AI brain receives schema + data *profile* (aggregate stats, small samples) — never bulk raw customer data beyond what profiling requires.

---

## 13. Known hard problems (v1 stance)

- **Drift** — source writes during migration cause divergence; v1 UI recommends read-only source. No CDC.
- **Mongo schema inference** — probabilistic schema from ≥1,000-doc sample; fields present in <80% of docs flagged "optional".
- **Memory ceiling** — always paginate (keyset/`_id`-based); never full-table reads.
- **Cross-paradigm type decisions** — Mongo arrays → Postgres: default heuristic ≤3 avg items → JSON column, ≥4 → separate table; user can override.

---

## 14. Success metrics

| Metric | Target (v1) |
|---|---|
| Migration success rate (completed / started) | ≥ 95% on supported matrix. |
| Validation confidence on successful jobs | ≥ 99% average. |
| Row-count fidelity | 0 tables >0.1% mismatch on "completed" jobs. |
| Time-to-first-migration (signup → done, SQLite→PG seed) | < 15 min. |
| Credential incidents | 0. |

---

## 15. Release plan / priority order

1. Health endpoint + Supabase connectivity (prove plumbing).
2. Auth flow (Supabase → JWT → FastAPI).
3. Connection tester per DB type.
4. Schema Analyst (real Postgres end-to-end).
5. New Migration wizard steps 1–2.
6. Celery + job queue.
7. Data Profiler.
8. Mapping Strategist (first Gemini call).
9. Real-time progress UI (xterm.js + Realtime).
10. Migration Executor (chunked, first real data movement).
11. Validation Auditor.
12. Full E2E: SQLite → PostgreSQL with seed data.

---

## 16. Acceptance test cases (must pass before release)

1. SQLite → PostgreSQL: all rows/types migrate, row counts match.
2. PostgreSQL → MySQL: FK constraints preserved, NULLs correct.
3. MySQL → MongoDB: FK relationships become embedded documents.
4. 100k-row table: migrates without memory spike above 512MB.
5. Interrupted migration: worker killed mid-job resumes or fails cleanly with a clear error.
6. PII detection: email + phone columns flagged in the data profile.

---

## 17. Open questions / risks

- OQ-1 — Gemini strict-JSON reliability for large schemas; need JSON-repair/retry strategy and possible plan chunking per-table.
- OQ-2 — Resumability design: does a killed executor resume from last committed chunk, or restart the table? (NFR-5.)
- OQ-3 — Conflict-strategy semantics for document targets (Mongo upsert keys).
- OQ-4 — Vault quota / secret lifecycle at scale.
- OQ-5 — Cost model for AI calls per migration (token budget per schema size).

---

*Companion to `CLAUDE.md`. Update this PRD first when product scope changes, then reconcile the code.*

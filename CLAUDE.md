# CLAUDE.md — Database Migration Agent
## God File: Everything You Need to Build This Project

> This file is the single source of truth for the entire project. Read it completely before writing any code. Every architectural decision, technology choice, and design pattern is documented here.

---

## 1. WHAT WE ARE BUILDING

A fully agentic database migration tool that reads an entire source database (schema + data), reasons about it using AI, and migrates it to any target database the user specifies — with zero manual configuration required.

**The Problem:** Database migrations today require expert DBAs, take weeks, cost six figures in consulting, and still fail silently on semantic mismatches.

**The Solution:** An AI agent pipeline that understands what the data *means* — not just what it *is* — and makes intelligent transformation decisions automatically.

**The Tagline:** *"Database migrations take months and cost six figures. We do it in hours — without a DBA."*

---

## 2. TECH STACK (LOCKED — DO NOT DEVIATE)

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Primary backend language |
| FastAPI | Latest | API framework (fully async) |
| Uvicorn | Latest | ASGI server |
| Supabase Python SDK (`supabase`) | Latest | App database, auth, realtime, vault |
| Anthropic Python SDK (`anthropic`) | Latest | Claude AI agent brain |
| Celery | Latest | Background job queue for long-running migrations |
| Redis | 7+ | Celery broker and result backend |
| SQLAlchemy | 2.x | ORM for connecting to USER source/target databases |
| asyncpg | Latest | Async PostgreSQL driver (for user DBs) |
| aiomysql | Latest | Async MySQL driver (for user DBs) |
| pymongo | Latest | MongoDB driver (for user DBs) |
| aiosqlite | Latest | SQLite async driver (for user DBs) |
| Pydantic | v2 | Data validation and settings |
| python-dotenv | Latest | Environment variable loading |
| cryptography | Latest | Fernet encryption for credential handling in-transit |
| psutil | Latest | Memory monitoring during large migrations |
| pytest + pytest-asyncio | Latest | Testing |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 18+ | UI framework |
| Vite | Latest | Build tool |
| TypeScript | Latest | Type safety |
| TanStack Query (react-query) | v5 | Async state, API calls |
| Zustand | Latest | Global client state |
| React Router DOM | v6 | Page routing |
| Tailwind CSS | v3 | Utility styling (alongside antd) |
| Ant Design (antd) | v5 | Component library (replaces shadcn/ui — the built UI uses antd) |
| Supabase JS SDK (`@supabase/supabase-js`) | Latest | Auth, Realtime subscriptions, DB queries |
| Axios | Latest | HTTP client for FastAPI calls |
| React Hook Form | Latest | Form management (DB connection forms) |
| Zod | Latest | Schema validation for forms |
| xterm.js | Latest | Live terminal-style migration log in browser |
| Recharts | Latest | Progress charts and migration stats |
| Framer Motion | Latest | UI transitions and animations |

### Infrastructure
| Technology | Purpose |
|---|---|
| Supabase (hosted) | App database (PostgreSQL), Auth, Realtime, Storage, Vault |
| Redis (Docker locally, Redis Cloud in prod) | Celery job queue broker |
| Docker Compose | Local test databases ONLY (MySQL, MongoDB, PostgreSQL test instances) |
| Docker | Containerize backend for deployment |

---

## 3. PROJECT STRUCTURE (EXACT — BUILD THIS EXACTLY)

```
db-migration-agent/
│
├── CLAUDE.md                          # This file
├── docker-compose.yml                 # Spins up test DBs + Redis only
├── .env.example                       # Template for all env vars
├── .gitignore
├── README.md
│
├── backend/
│   ├── main.py                        # FastAPI app entrypoint
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env                           # Backend environment variables
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   ├── agents/                    # The 5 AI sub-agents (core of the product)
│   │   │   ├── __init__.py
│   │   │   ├── schema_analyst.py      # Agent 1: Reads and maps source schema
│   │   │   ├── data_profiler.py       # Agent 2: Samples + profiles actual data
│   │   │   ├── mapping_strategist.py  # Agent 3: AI brain — decides transformation plan
│   │   │   ├── migration_executor.py  # Agent 4: Runs migration in batches
│   │   │   └── validation_auditor.py  # Agent 5: Post-migration verification
│   │   │
│   │   ├── connectors/                # Database connection handlers
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Abstract base connector class
│   │   │   ├── postgres.py           # PostgreSQL connector
│   │   │   ├── mysql.py              # MySQL connector
│   │   │   ├── mongodb.py            # MongoDB connector
│   │   │   ├── sqlite.py             # SQLite connector
│   │   │   └── connector_factory.py  # Returns correct connector by DB type
│   │   │
│   │   ├── api/                       # FastAPI route handlers
│   │   │   ├── __init__.py
│   │   │   ├── migrations.py         # Migration CRUD + trigger endpoints
│   │   │   ├── connections.py        # Test + save DB connection strings
│   │   │   ├── jobs.py               # Job status endpoints
│   │   │   └── health.py             # Health check
│   │   │
│   │   ├── models/                    # Pydantic models (request/response shapes)
│   │   │   ├── __init__.py
│   │   │   ├── migration.py
│   │   │   ├── connection.py
│   │   │   └── job.py
│   │   │
│   │   ├── services/                  # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── migration_service.py  # Orchestrates the 5 agents
│   │   │   ├── credential_service.py # Encrypt/decrypt DB credentials via Supabase Vault
│   │   │   └── supabase_service.py   # Supabase client singleton + helpers
│   │   │
│   │   ├── workers/                   # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py         # Celery configuration
│   │   │   └── migration_worker.py   # Long-running migration task
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── type_mapper.py        # Cross-DB type coercion rules
│   │       ├── chunker.py            # Stream/batch large tables
│   │       └── logger.py             # Structured logging
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_connectors.py
│       ├── test_agents.py
│       └── test_api.py
│
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── .env                           # Frontend environment variables
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       │
│       ├── pages/
│       │   ├── Landing.tsx            # Marketing/login page
│       │   ├── Dashboard.tsx          # List of all migrations
│       │   ├── NewMigration.tsx       # Step-by-step migration wizard
│       │   ├── MigrationDetail.tsx    # Live progress view for a single migration
│       │   └── Settings.tsx           # User settings
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── Navbar.tsx
│       │   │   └── Sidebar.tsx
│       │   ├── migration/
│       │   │   ├── ConnectionForm.tsx  # DB connection input form
│       │   │   ├── MigrationPlan.tsx   # Show AI-generated plan before executing
│       │   │   ├── ProgressTerminal.tsx # xterm.js live log
│       │   │   ├── StatusBadge.tsx
│       │   │   └── MigrationCard.tsx
│       │   └── ui/                    # shadcn/ui components live here
│       │
│       ├── lib/
│       │   ├── supabase.ts            # Supabase client singleton
│       │   ├── api.ts                 # Axios instance pointing to FastAPI
│       │   └── utils.ts
│       │
│       ├── hooks/
│       │   ├── useMigration.ts        # TanStack Query hooks for migration data
│       │   ├── useMigrationRealtime.ts # Supabase Realtime subscription
│       │   └── useAuth.ts             # Supabase auth hook
│       │
│       ├── store/
│       │   └── migrationStore.ts      # Zustand global state
│       │
│       └── types/
│           └── index.ts               # All TypeScript type definitions
│
└── docker/
    ├── postgres/
    │   └── init.sql                   # Seed a test PostgreSQL DB
    ├── mysql/
    │   └── init.sql                   # Seed a test MySQL DB
    └── mongo/
        └── init.js                    # Seed a test MongoDB collection
```

---

## 4. ENVIRONMENT VARIABLES

### Backend `.env`
```env
# ── Anthropic ──────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Supabase (Backend — use SERVICE ROLE key, never expose) ─
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# ── Redis ──────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── App ────────────────────────────────────────────────────
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173

# ── Celery ─────────────────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Frontend `.env`
```env
# ── Supabase (Frontend — ANON key only, safe to expose) ────
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...

# ── FastAPI Backend ─────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:8000
```

**CRITICAL SECURITY RULES:**
- `SUPABASE_SERVICE_ROLE_KEY` → Backend ONLY. Never send to frontend. Never log it.
- `VITE_SUPABASE_ANON_KEY` → Frontend only. Safe to expose (Supabase RLS protects data).
- `ANTHROPIC_API_KEY` → Backend ONLY. Never expose.
- User database credentials → NEVER stored in plaintext. Go through Supabase Vault immediately on receipt.

---

## 5. SUPABASE SCHEMA (YOUR APP'S OWN DATABASE)

Run these in the Supabase SQL editor to initialize the app database.

### Table: `migration_jobs`
```sql
create table migration_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  name text not null,
  status text not null default 'pending',
  -- Status values: pending | analyzing | profiling | planning | executing | validating | completed | failed
  source_db_type text not null,   -- postgres | mysql | mongodb | sqlite
  target_db_type text not null,
  source_credential_id text,      -- Supabase Vault secret ID (not the credential itself)
  target_credential_id text,      -- Supabase Vault secret ID
  migration_plan jsonb,           -- AI-generated plan before execution
  schema_snapshot jsonb,          -- Full source schema map
  data_profile jsonb,             -- Data profiling results
  options jsonb default '{}',     -- User preferences (skip tables, conflict strategy, etc.)
  progress_pct integer default 0,
  rows_migrated bigint default 0,
  rows_total bigint default 0,
  error_log jsonb default '[]',
  validation_report jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Enable Row Level Security
alter table migration_jobs enable row level security;

-- Users can only see their own jobs
create policy "Users see own jobs"
  on migration_jobs for all
  using (auth.uid() = user_id);

-- Enable Realtime on this table (critical for live progress)
alter publication supabase_realtime add table migration_jobs;
```

### Table: `migration_logs`
```sql
create table migration_logs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references migration_jobs(id) on delete cascade not null,
  level text not null,  -- info | warning | error | success
  agent text not null,  -- which sub-agent wrote this log
  message text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

alter table migration_logs enable row level security;

create policy "Users see own logs"
  on migration_logs for all
  using (
    job_id in (
      select id from migration_jobs where user_id = auth.uid()
    )
  );

-- Enable Realtime for live log streaming
alter publication supabase_realtime add table migration_logs;
```

### Table: `saved_connections`
```sql
create table saved_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  nickname text not null,
  db_type text not null,
  host text,
  port integer,
  database_name text,
  credential_vault_id text not null,  -- Supabase Vault ID — never store plaintext
  created_at timestamptz default now()
);

alter table saved_connections enable row level security;

create policy "Users see own connections"
  on saved_connections for all
  using (auth.uid() = user_id);
```

### Automatic `updated_at` trigger
```sql
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger migration_jobs_updated_at
  before update on migration_jobs
  for each row execute function update_updated_at();
```

---

## 6. THE 5 AGENT PIPELINE (CORE PRODUCT LOGIC)

This is the heart of the application. Each agent is a class with an `async def run()` method. They execute in sequence, each receiving the output of the previous.

```
User submits migration job
         ↓
[1. Schema Analyst]
  → Reads all tables, columns, types, constraints, indexes, FK relationships
  → Output: SchemaSnapshot (JSON)
         ↓
[2. Data Profiler]
  → Samples up to 1,000 rows per table
  → Detects: nullability, implicit enums, date formats, PII fields, encoding issues
  → Output: DataProfile (JSON)
         ↓
[3. Mapping Strategist]  ← AI BRAIN (Claude API call)
  → Takes SchemaSnapshot + DataProfile + source_type + target_type
  → Reasons about cross-paradigm transformations
  → Outputs: MigrationPlan (JSON) — human-readable, user can review and approve
         ↓
[4. Migration Executor]
  → Executes MigrationPlan in chunks (1,000 rows per batch default)
  → Writes progress updates to Supabase migration_jobs table
  → Handles retries, partial failures, logs everything to migration_logs
  → Output: ExecutionReport
         ↓
[5. Validation Auditor]
  → Row count comparison (source vs target)
  → Sample hash checks on random rows
  → FK/referential integrity checks
  → Output: ValidationReport with confidence score (0–100%)
```

### Key Agent Implementation Rules

**Schema Analyst** must handle:
- PostgreSQL: `information_schema.columns`, `pg_constraint`, `pg_indexes`
- MySQL: `INFORMATION_SCHEMA.COLUMNS`, `SHOW CREATE TABLE`
- MongoDB: Collection scan, schema inference from document sampling
- SQLite: `PRAGMA table_info()`, `PRAGMA foreign_key_list()`

**Data Profiler** must detect:
- Columns that are implicitly boolean (only 0/1 values)
- Columns that are implicitly enum (< 20 distinct values in a string column)
- PII fields (regex match on column name: email, phone, ssn, password, etc.)
- NULL percentage per column
- Date format inconsistencies

**Mapping Strategist** Claude prompt must include:
- Full source schema (JSON)
- Full data profile (JSON)
- Source DB type and target DB type
- User preferences (skipped tables, conflict strategy)
- Type coercion reference table (from `type_mapper.py`)
- Instruction to output ONLY valid JSON — never prose

**Migration Executor** must:
- NEVER load an entire table into memory — always chunk by primary key or `_id`
- Default chunk size: 1,000 rows. Configurable per job.
- Write a log entry to `migration_logs` every chunk
- Update `progress_pct` and `rows_migrated` in `migration_jobs` every chunk
- On error: log it, continue with next chunk (configurable: fail-fast vs skip-errors)

**Validation Auditor** must:
- Always run — never skip even if execution looks clean
- Write `ValidationReport` to `migration_jobs.validation_report`
- Flag any table where row count mismatch > 0.1%

---

## 7. API ENDPOINTS (FASTAPI)

All routes are prefixed with `/api/v1`. All routes require `Authorization: Bearer <supabase_jwt>` header except `/health`.

### Health
```
GET  /health                          → 200 OK if service is running
```

### Migrations
```
GET  /api/v1/migrations               → List all jobs for authenticated user
POST /api/v1/migrations               → Create a new migration job
GET  /api/v1/migrations/{id}          → Get single job details
POST /api/v1/migrations/{id}/start    → Trigger the agent pipeline (kicks off Celery task)
POST /api/v1/migrations/{id}/cancel   → Cancel a running job
GET  /api/v1/migrations/{id}/plan     → Get AI-generated migration plan
POST /api/v1/migrations/{id}/approve  → User approves plan, allows execution to proceed
GET  /api/v1/migrations/{id}/logs     → Get all logs for a job
```

### Connections
```
POST /api/v1/connections/test         → Test a DB connection string (never save it)
POST /api/v1/connections              → Save a DB connection (stores in Vault)
GET  /api/v1/connections              → List saved connections (no credentials returned)
DELETE /api/v1/connections/{id}       → Delete a saved connection
```

`POST /connections/test` also probes write privileges (T2-5) and returns
`has_write_access`, `privilege_evidence` and, when writable, `readonly_advice`
with the GRANT statements for a least-privilege replacement user. The probe is
read-only — it asks the engine what the credential may do, never attempts a write.

### Semantic intelligence (Tier 1)
```
GET  /api/v1/migrations/{id}/semantic-report        → Semantic Mismatch Report Card
GET  /api/v1/migrations/{id}/preview-diff           → "schema says vs data means"
GET  /api/v1/migrations/{id}/quality-report         → Data Quality Report
GET  /api/v1/migrations/{id}/confidence-breakdown   → per-table/per-column confidence
```

### Trust & safety (Tier 2)
```
POST /api/v1/migrations/{id}/simulate        → queue a before/after simulation
GET  /api/v1/migrations/{id}/simulation      → simulation result
GET  /api/v1/migrations/{id}/rollback-script → downloadable manual rollback guide
GET  /api/v1/migrations/{id}/tables          → per-table status in FK load order
POST /api/v1/migrations/{id}/resume          → resume from the last committed chunk
```

### Public / virality (Tier 3) — no auth required
```
GET  /api/v1/templates                  → migration template library (SEO surface)
GET  /api/v1/templates/{slug}           → one template with its type quirks
POST /api/v1/migrations/{id}/share      → create/update the public link + badge
GET  /api/v1/public/{token}             → redacted shareable report
GET  /api/v1/public/{token}/badge.svg   → README badge
GET  /api/v1/compliance                 → which DB types this deployment supports
```

### Drift monitoring (Tier 4) — the subscription product
```
POST   /api/v1/monitoring                     → enroll a completed migration
GET    /api/v1/monitoring                     → list monitors
GET    /api/v1/monitoring/{id}/drift          → latest drift report + timeline
POST   /api/v1/monitoring/{id}/check          → run a drift check now
POST   /api/v1/monitoring/{id}/rebaseline     → accept current schema as normal
GET    /api/v1/monitoring/{id}/health-report  → monthly health summary
DELETE /api/v1/monitoring/{id}                → stop monitoring
```

Tier 5 (enterprise) is designed but not built — see
`docs/TIER5_ENTERPRISE_DESIGN.md`.

### Schema additions
The Tier 1–4 features need extra columns and two new tables. Run
`supabase/002_tier1_to_tier4.sql` in the Supabase SQL editor after the base
schema in §5. It is idempotent.

### CLI
`backend/cli.py` (Typer + Rich). `migrate audit` is the free top-of-funnel:
it profiles a database, prints the semantic and quality reports, then discards
the job — nothing is written to the audited database.
```
python cli.py audit --source "mysql://..."
python cli.py plan  --source "..." --target "..."
python cli.py run   --source "..." --target "..." [-y]
python cli.py drift --baseline-id <monitor-id>     # exit 2 when drift is found
python cli.py templates
```

---

## 8. CELERY WORKER ARCHITECTURE

Migrations are long-running. They CANNOT run inside an HTTP request (timeout). Architecture:

```
1. POST /api/v1/migrations/{id}/start
   → FastAPI validates request
   → Creates Celery task: run_migration.delay(job_id)
   → Immediately returns 202 Accepted with job_id

2. Celery worker picks up the task
   → Instantiates and runs the 5-agent pipeline
   → Each agent writes progress to Supabase

3. Frontend subscribes to Supabase Realtime on migration_jobs + migration_logs
   → Receives live updates as the worker progresses
   → No polling needed
```

### Celery task (`workers/migration_worker.py`)
```python
# The task signature — implementation is the full agent pipeline
@celery_app.task(bind=True, max_retries=0, name='run_migration')
async def run_migration(self, job_id: str):
    # 1. Fetch job from Supabase
    # 2. Decrypt credentials from Vault
    # 3. Connect to source and target DBs
    # 4. Run schema_analyst.run()
    # 5. Run data_profiler.run()
    # 6. Run mapping_strategist.run()
    # 7. Wait for user approval (if dry_run=True)
    # 8. Run migration_executor.run()
    # 9. Run validation_auditor.run()
    # 10. Update final status in Supabase
```

---

## 9. CREDENTIAL SECURITY (NON-NEGOTIABLE)

User database credentials are the most sensitive data in this application. Follow this exactly:

1. User submits connection string in frontend form
2. Frontend sends it to `POST /api/v1/connections/test` — test ONLY, never stored here
3. If user wants to save: `POST /api/v1/connections` → FastAPI receives it → **immediately** stores in Supabase Vault via `supabase.secrets.create()` → stores only the Vault ID in `saved_connections`
4. When a migration runs: Backend fetches from Vault using Vault ID → decrypts → uses in-memory → connection string is **never written to logs, never written to disk, never returned to frontend**
5. Credentials are deleted from Vault when user deletes the saved connection

```python
# credential_service.py pattern
async def store_credential(connection_string: str) -> str:
    """Returns vault_id, never the credential"""
    result = await supabase.secrets.create({"value": connection_string})
    return result.id  # Only this gets stored in our DB

async def get_credential(vault_id: str) -> str:
    """Returns plaintext for in-memory use only"""
    result = await supabase.secrets.get(vault_id)
    return result.value
```

---

## 10. TYPE COERCION REFERENCE (`type_mapper.py`)

This file must know how to map between all supported database type systems. It is used by the Mapping Strategist agent as a lookup table.

Cross-paradigm rules that must be handled:
- **MySQL → PostgreSQL:** `TINYINT(1)` → `BOOLEAN`, `DATETIME` → `TIMESTAMPTZ`, `TEXT` → `TEXT` (no size limit needed)
- **PostgreSQL → MongoDB:** Any table → document collection, FK relationships → embedded documents or `$ref`
- **MongoDB → PostgreSQL:** Nested objects → flattened columns OR separate tables (AI decides based on nesting depth)
- **Any → SQLite:** `BOOLEAN` → `INTEGER`, `JSONB` → `TEXT`, `UUID` → `TEXT`
- All types unknown to the target → `TEXT` as fallback (log a warning)

---

## 11. FRONTEND PAGE FLOWS

### New Migration Wizard (3 steps)
```
Step 1: Source Database
  - Select DB type (PostgreSQL / MySQL / MongoDB / SQLite)
  - Enter connection string OR select saved connection
  - Test connection button → POST /api/v1/connections/test

Step 2: Target Database
  - Same as Step 1 but for target

Step 3: Options
  - Migration name
  - Tables to skip (multiselect, populated after connection test runs schema scan)
  - Conflict strategy: Skip duplicates | Overwrite | Fail on conflict
  - Dry run toggle (generate plan only, don't execute)
  - Submit → POST /api/v1/migrations → POST /api/v1/migrations/{id}/start
```

### Migration Detail Page (real-time)
```
- Status badge (pending → analyzing → profiling → planning → executing → validating → completed)
- If status = "planning": Show AI-generated MigrationPlan, Approve button
- Progress bar: rows_migrated / rows_total
- xterm.js terminal showing migration_logs in real-time (Supabase Realtime)
- Validation report card when completed
- Download report button
```

---

## 12. REAL-TIME SUBSCRIPTION PATTERN (FRONTEND)

```typescript
// hooks/useMigrationRealtime.ts
// Subscribe to live updates for a specific migration job

const channel = supabase
  .channel(`migration:${jobId}`)
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',
      schema: 'public',
      table: 'migration_jobs',
      filter: `id=eq.${jobId}`
    },
    (payload) => {
      // Update job status, progress, etc.
    }
  )
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'migration_logs',
      filter: `job_id=eq.${jobId}`
    },
    (payload) => {
      // Append new log line to xterm.js terminal
    }
  )
  .subscribe()
```

---

## 13. DOCKER COMPOSE (LOCAL DEV ONLY)

This file only spins up **test databases** and **Redis**. Supabase is hosted — not in Docker.

```yaml
version: '3.8'
services:

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  test-postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpass
      POSTGRES_DB: testdb
    ports:
      - "5433:5432"  # 5433 to avoid conflict with any local postgres
    volumes:
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql

  test-mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: testpass
      MYSQL_DATABASE: testdb
      MYSQL_USER: testuser
      MYSQL_PASSWORD: testpass
    ports:
      - "3307:3306"  # 3307 to avoid conflict with local mysql
    volumes:
      - ./docker/mysql/init.sql:/docker-entrypoint-initdb.d/init.sql

  test-mongo:
    image: mongo:6
    ports:
      - "27018:27017"  # 27018 to avoid conflict with local mongo
    volumes:
      - ./docker/mongo/init.js:/docker-entrypoint-initdb.d/init.js
```

---

## 14. CODING CONVENTIONS

### Python
- **All async.** Every function that touches a database or the Anthropic API must be `async def`
- **Pydantic v2** for all data models. Use `model_validator` not `validator`
- **Never hardcode DB credentials.** Always from Vault or env vars
- **Structured logging only.** Every log entry must include `job_id`, `agent`, `level`
- **Type hints everywhere.** No `Any` unless genuinely unavoidable
- **One responsibility per file.** `schema_analyst.py` only does schema analysis

### TypeScript / React
- **No `any` types.** Ever.
- **TanStack Query for ALL server state.** No `useState` for data that comes from the API
- **Zustand only for UI state** (current wizard step, modal open/closed, etc.)
- **Every form uses React Hook Form + Zod.** No uncontrolled inputs
- **Supabase client is a singleton** in `lib/supabase.ts` — never instantiated elsewhere
- **API calls only through `lib/api.ts`** Axios instance — never raw fetch

### General
- **Dry run mode is never skipped.** Always generate a plan before executing. User must explicitly approve.
- **No silent failures.** Every caught error must be logged to `migration_logs`
- **Chunk size is always configurable.** Never hardcode 1000 rows

---

## 15. SUPPORTED DATABASE MATRIX

| Source → Target | Supported | Difficulty | Notes |
|---|---|---|---|
| PostgreSQL → MySQL | ✅ | Low | Minor type differences |
| MySQL → PostgreSQL | ✅ | Low | Common migration path |
| PostgreSQL → MongoDB | ✅ | High | Relational → Document paradigm shift |
| MongoDB → PostgreSQL | ✅ | High | Denormalization decisions needed |
| MySQL → MongoDB | ✅ | High | Same as above |
| MongoDB → MySQL | ✅ | High | Same as above |
| SQLite → PostgreSQL | ✅ | Low | Very common (dev → prod) |
| SQLite → MySQL | ✅ | Low | |
| PostgreSQL → SQLite | ✅ | Medium | Type downgrades needed |
| Any → Any (same type) | ✅ | Low | Schema copy + data transfer |

---

## 16. INITIALIZATION CHECKLIST (DO IN THIS ORDER)

```
[ ] 1. Create Supabase project at supabase.com (free tier)
[ ] 2. Run all SQL from Section 5 in Supabase SQL Editor
[ ] 3. Enable Realtime on migration_jobs and migration_logs tables
[ ] 4. Enable Supabase Vault (Dashboard → Vault)
[ ] 5. Copy Supabase URL, anon key, service role key
[ ] 6. Create monorepo folder structure (Section 3)
[ ] 7. Create backend venv: python -m venv venv && source venv/bin/activate
[ ] 8. pip install all packages from Section 2
[ ] 9. Create frontend: npm create vite@latest frontend -- --template react-ts
[ ] 10. npm install all frontend packages from Section 2
[ ] 11. Create .env files for backend and frontend (Section 4)
[ ] 12. Create docker-compose.yml (Section 13)
[ ] 13. Run: docker-compose up -d (starts Redis + test databases)
[ ] 14. Write GET /health endpoint in FastAPI — verify it returns 200
[ ] 15. Wire Supabase client in both backend and frontend
[ ] 16. Write a single test: frontend button → FastAPI → Supabase write → Realtime update received in frontend
[ ] 17. Only after step 16 passes: start writing agent code
```

---

## 17. WHAT TO BUILD FIRST (PRIORITY ORDER)

1. **Health endpoint + Supabase connection** — prove the plumbing works
2. **Auth flow** — Supabase auth in React, JWT passed to FastAPI
3. **Connection tester** — `POST /api/v1/connections/test` for each DB type
4. **Schema Analyst agent** — read a real PostgreSQL schema end to end
5. **New Migration wizard (frontend)** — steps 1 and 2 only (no execution yet)
6. **Celery + job queue** — migration job created, handed to worker
7. **Data Profiler agent**
8. **Mapping Strategist agent** — first Claude API integration
9. **Real-time progress UI** — xterm.js + Supabase Realtime
10. **Migration Executor agent** — chunked migration, first real data movement
11. **Validation Auditor agent**
12. **Full end-to-end test:** SQLite → PostgreSQL with seed data

---

## 18. THE ANTHROPIC API CALL (MAPPING STRATEGIST)

The most critical AI call in the system. Use this pattern:

```python
# mapping_strategist.py
import anthropic

client = anthropic.AsyncAnthropic()

SYSTEM_PROMPT = """
You are a database migration strategist. You will receive a source database schema,
a data profile, and source/target database types. You must output a detailed migration plan
as valid JSON only. No prose. No markdown. No explanation outside the JSON structure.

Your plan must specify for each table:
- target_table_name (or target_collection_name for MongoDB)
- column_mappings: source column → target column with type coercions
- transformation_rules: any data transformations needed
- relationship_handling: how FKs/references are handled in target
- warnings: any data quality issues or semantic uncertainties flagged
"""

async def generate_migration_plan(
    schema_snapshot: dict,
    data_profile: dict,
    source_db_type: str,
    target_db_type: str,
    user_options: dict
) -> dict:
    
    user_message = f"""
Source database type: {source_db_type}
Target database type: {target_db_type}
User options: {json.dumps(user_options)}

SOURCE SCHEMA:
{json.dumps(schema_snapshot, indent=2)}

DATA PROFILE:
{json.dumps(data_profile, indent=2)}

TYPE COERCION REFERENCE:
{json.dumps(TYPE_COERCION_MAP, indent=2)}

Generate the migration plan now. Output JSON only.
"""

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    
    raw = message.content[0].text
    return json.loads(raw)  # Always wrap in try/except
```

---

## 19. TESTING STRATEGY

### Seed data for test databases
- `docker/postgres/init.sql` — Create `users`, `orders`, `products`, `audit_logs` tables with 500 rows each. Include FK relationships. Include NULL values. Include implicit enums.
- `docker/mysql/init.sql` — Same schema, MySQL syntax, different data
- `docker/mongo/init.js` — `users` collection with embedded `orders` array. Mixed schema (some docs have extra fields).

### Test cases that must pass before any release
1. SQLite → PostgreSQL: all rows, all types, row count matches
2. PostgreSQL → MySQL: FK constraints preserved, NULL handling correct
3. MySQL → MongoDB: FK relationships become embedded documents
4. Large table: 100,000 row table migrates without memory spike above 512MB
5. Interrupted migration: Kill the worker mid-job, restart — job resumes or fails cleanly with clear error
6. PII detection: Email and phone columns are flagged in the data profile

---

## 20. KNOWN HARD PROBLEMS (READ BEFORE CODING)

**The drift problem:** If the source database is being written to while migration runs, your target will be out of sync. For v1, document this clearly in the UI: "We recommend putting your source database in read-only mode during migration." Do not try to solve CDC in v1.

**MongoDB schema inference:** MongoDB has no schema. Every document might be different. The Data Profiler must scan a sample of documents (minimum 1,000) and build a probabilistic schema. Flag columns that appear in < 80% of documents as "optional."

**Memory ceiling:** Never read an entire table. Always paginate. For PostgreSQL/MySQL use `LIMIT`/`OFFSET` or cursor-based pagination on primary key. For MongoDB use `find().skip().limit()` or `_id`-based pagination.

**Cross-paradigm type decisions:** When MongoDB arrays → PostgreSQL, the AI must decide: separate table (normalized) or JSON column (denormalized). The default heuristic: if the array has 0–3 items on average → JSON column. If 4+ → separate table. The user can override in options.

---

*This document is the single source of truth. When in doubt, follow this document. When this document is wrong, update it first, then update the code.*
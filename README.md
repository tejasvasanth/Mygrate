# DB Migration Agent

> Database migrations take months and cost six figures. We do it in hours — without a DBA.

A fully agentic database migration tool. Point it at a source and a target database
(PostgreSQL, MySQL, MongoDB or SQLite); a five-agent AI pipeline reads the schema,
profiles the real data, reasons about what it *means*, generates a reviewable migration
plan, executes it in chunks, and validates the result.

**AI brain:** Google Gemini (via `google-genai`). When no `GEMINI_API_KEY` is set, a
deterministic fallback planner keeps the pipeline working using the type-coercion tables.

## Architecture

```
FastAPI ── Celery/Redis ── 5-agent pipeline ── Supabase (jobs, logs, vault, realtime)
React + antd frontend ── Supabase Realtime for live progress ── xterm.js live log
```

The five agents: **Schema Analyst → Data Profiler → Mapping Strategist (AI) →
Migration Executor → Validation Auditor**.

## Quick start

### 1. Supabase (once)
Create a project at supabase.com, then run `backend/supabase_setup.sql` in the SQL
editor. Enable Vault. Copy the URL + service-role key into `backend/.env`, and the URL
+ anon key into `frontend/.env`.

### 2. Backend
```powershell
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\uvicorn main:app --reload          # API on :8000
```

### 3. Worker + Redis (needed for real migrations via the API)
```powershell
docker-compose up -d redis
cd backend
venv\Scripts\celery -A app.workers.celery_app worker --pool=solo --loglevel=info
```

### 4. Frontend
```powershell
cd frontend
npm install
npm run dev                                      # UI on :5173
```

### 5. Test databases (optional)
```powershell
docker-compose up -d      # seeded postgres :5433, mysql :3307, mongo :27018
```

## Tests
```powershell
cd backend
venv\Scripts\python -m pytest            # offline suite (SQLite + mocks)
venv\Scripts\python -m pytest -m docker  # requires docker-compose databases
```

## Security model
- User DB credentials go straight to Supabase Vault; only vault IDs are stored.
  (Fernet-encrypted fallback via `CREDENTIAL_ENCRYPTION_KEY` when Vault is unavailable.)
- Credentials are never logged, never written to disk, never returned to the frontend.
- Row Level Security isolates every user's jobs, logs and connections.
- Recommendation: put the source database in read-only mode during migration —
  concurrent writes are not captured (no CDC in v1).

See `CLAUDE.md` for the full specification.

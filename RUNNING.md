# Running the Backend + Celery (Windows / PowerShell)

## Prereqs (once per session)
Redis must be up (Celery broker). Start it via Docker Compose:

```powershell
cd C:\Tejas\tejas\Migration\db-migration-agent
docker-compose up -d redis
```

## 1. Activate the venv
```powershell
cd C:\Tejas\tejas\Migration\db-migration-agent\backend
.\venv\Scripts\Activate.ps1
```

## 2. Start the FastAPI backend
In one terminal (with venv activated):
```powershell
cd C:\Tejas\tejas\Migration\db-migration-agent\backend
uvicorn main:app --reload --port 8000
```
Check it's alive: http://localhost:8000/health

## 3. Start the Celery worker
In a **second** terminal (activate venv again first):
```powershell
cd C:\Tejas\tejas\Migration\db-migration-agent\backend
.\venv\Scripts\Activate.ps1
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```
> `--pool=solo` is required on Windows — Celery's default prefork pool doesn't work there.

## 4. (Optional) Frontend
In a third terminal:
```powershell
cd C:\Tejas\tejas\Migration\db-migration-agent\frontend
npm run dev
```

## Quick checklist
- [ ] `docker-compose up -d redis`
- [ ] Terminal 1: `venv activate` → `uvicorn main:app --reload --port 8000`
- [ ] Terminal 2: `venv activate` → `celery -A app.workers.celery_app worker --loglevel=info --pool=solo`
- [ ] Terminal 3 (optional): `npm run dev` in `frontend/`

## Notes
- This project uses **Gemini** (`google-genai`), not Anthropic, as the AI brain — despite what CLAUDE.md's Section 2/18 say.
- `backend/.env` already exists — verify `REDIS_URL` / `CELERY_BROKER_URL` point to `redis://localhost:6379/0` before starting.
- Supabase setup SQL (`backend/supabase_setup.sql`) has not been confirmed run yet — run it in the Supabase SQL editor before triggering real migrations.

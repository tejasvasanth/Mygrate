# Tier 5 — Enterprise features: design

Designed now, built later. Each section states the data model, the API surface,
and the one decision that is hard to reverse — so the code written today does
not foreclose it.

---

## T5-1 Team approvals

**Goal:** require N approvals before a plan executes, with a full audit trail.

### Data model
```sql
create table approval_policies (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  required_approvals integer not null default 1,
  approver_user_ids uuid[] not null default '{}',
  plan_ttl_hours integer not null default 24
);

create table migration_approvals (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references migration_jobs(id) on delete cascade not null,
  user_id uuid references auth.users(id) not null,
  decision text not null check (decision in ('approved', 'rejected')),
  comment text,
  ip_address inet,
  user_agent text,
  plan_fingerprint text not null,
  created_at timestamptz default now(),
  unique (job_id, user_id, plan_fingerprint)
);
```

### API
```
GET  /api/v1/migrations/{id}/approvals     → who approved, when, from where
POST /api/v1/migrations/{id}/approvals     → record this user's decision
GET  /api/v1/orgs/{id}/approval-policy
PUT  /api/v1/orgs/{id}/approval-policy
```

`POST /approve` changes meaning: it records one approval and only queues the
Celery task once `count(approved) >= required_approvals`.

### The hard-to-reverse decision
**`plan_fingerprint` must exist from day one.** It is a hash of the migration
plan (table list, column mappings, target types). Approvals are bound to the
exact plan that was reviewed. If the plan is regenerated — because the source
schema drifted, or the strategist was re-run — every prior approval is void and
the count resets. Without a fingerprint, an approval granted for plan A can
silently authorise plan B, which is the one failure mode that turns this
feature into a liability.

Approval expiry (24h default) follows the same reasoning: a schema can drift
between review and execution, so a stale approval is treated as no approval.

### Implementation note
`build_preview_diff` already produces the exact reviewed artifact. Hash its
`rows` (table, column, declared, inferred, recommendation) rather than the raw
plan JSON, so cosmetic plan changes do not needlessly void approvals but
semantic ones always do.

---

## T5-2 On-prem agent

**Goal:** run the full pipeline inside the customer's network. Only schema
metadata and aggregate statistics leave the perimeter; raw rows and connection
strings never do.

### Package split
```
migrate-core    # connectors, profiler, semantic_types, data_quality,
                # executor, auditor — no network calls to Migrate
migrate-agent   # CLI + local orchestrator, depends on migrate-core
migrate-cloud   # FastAPI + Supabase + Gemini (hosted, unchanged)
```

`pip install migrate-agent`, then `migrate-agent run --source ... --target ...`.

### What crosses the wire
The agent calls exactly one hosted endpoint, `POST /api/v1/plan`, with a
redacted payload:

| Sent | Never sent |
|---|---|
| Table and column names (optionally hashed) | Connection strings, credentials |
| Declared types, nullability, PK/FK structure | Row values of any kind |
| Aggregate stats: null %, distinct counts | Sample values |
| Semantic detections and confidence | The evidence rows behind them |

The response is a MigrationPlan. Execution, validation and reporting all run
locally; results are stored in the customer's own Postgres, not Supabase.

### The hard-to-reverse decision
**The Mapping Strategist must never require raw rows.** Today it receives
`schema_snapshot` + `data_profile`, and `data_profile` carries `sample_values`
for evidence display. Before shipping the agent, split the profile into
`profile.stats` (safe to transmit) and `profile.evidence` (stays local), and
make the strategist prompt read only from `stats`. If the prompt ever comes to
depend on real values, the on-prem story is dead — so this boundary is worth
enforcing with a test, not a convention.

### Offline mode
With no outbound network at all, fall back to the deterministic planner that
already exists (`mapping_strategist` fallback path used when `GEMINI_API_KEY`
is unset). The product degrades to rule-based planning rather than failing.

---

## T5-3 Migration scheduling

**Goal:** "run between 02:00 and 04:00 Sunday, in the customer's timezone, and
do not start if it cannot finish in the window."

### Data model
```sql
alter table migration_jobs
  add column schedule jsonb;
-- { cron: "0 2 * * 0", timezone: "America/New_York",
--   window_minutes: 120, on_overrun: "cancel" | "continue" }
```

### Mechanism
Celery beat already runs (added for drift monitoring). A
`dispatch_scheduled_migrations` task runs every 5 minutes, finds jobs whose
next fire time has passed, and queues them.

Duration is estimated before starting: `rows_total / observed_rows_per_second`,
where the rate comes from this job's previous run or a conservative default.
If the estimate exceeds `window_minutes`, the job is not started and the user
is notified — starting a migration that will be killed mid-flight is worse
than not starting it.

### The hard-to-reverse decision
**Store the timezone, never a UTC offset.** Offsets break twice a year at DST
boundaries; "2am Sunday" must mean 2am local in both January and July. Use
`zoneinfo` and compute fire times from the named zone at each evaluation.

If a run is killed by the window, T2-3 checkpointing means the next window
resumes rather than restarts — the two features compose.

---

## T5-4 RBAC

**Goal:** four roles, enforced at the database, not just the UI.

| Role | Migrations | Connections | Reports | Members |
|---|---|---|---|---|
| Owner | full | full | full | manage |
| Admin | full | full | full | invite |
| Migrator | create, run, resume | use existing, cannot delete | full | — |
| Viewer | read | cannot see credentials | read | — |

### Data model
```sql
create table org_members (
  org_id uuid not null,
  user_id uuid references auth.users(id) on delete cascade not null,
  role text not null check (role in ('owner','admin','migrator','viewer')),
  primary key (org_id, user_id)
);

alter table migration_jobs add column org_id uuid;
alter table saved_connections add column org_id uuid;
```

### Enforcement
RLS policies keyed on `org_members`, e.g.:

```sql
create policy "Viewers cannot see credentials"
  on saved_connections for select
  using (
    org_id in (
      select org_id from org_members
      where user_id = auth.uid() and role in ('owner','admin','migrator')
    )
  );
```

FastAPI additionally checks role in a dependency (`require_role("migrator")`)
so API errors are clear 403s rather than confusing empty result sets.

### The hard-to-reverse decision
**Ownership moves from `user_id` to `org_id`.** Every table currently scopes by
`auth.uid() = user_id`. Adding `org_id` later means backfilling every row and
rewriting every policy while live. Mitigation: when RBAC work starts, create a
personal org per existing user and set `org_id` in the same migration that adds
the column, keeping `user_id` as the creator field for the audit trail.

---

## Build order

1. **T5-4 RBAC** — everything else assumes an org boundary; doing it first
   avoids a second backfill.
2. **T5-1 Team approvals** — depends on org membership for the approver list.
3. **T5-3 Scheduling** — independent, and Celery beat already exists.
4. **T5-2 On-prem agent** — largest effort; the profile stats/evidence split
   should land early even if the agent itself ships much later.

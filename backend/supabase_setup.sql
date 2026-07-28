-- Run this whole file in the Supabase SQL Editor once per project.

-- ── Tables ──────────────────────────────────────────────────────
create table if not exists migration_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  name text not null,
  status text not null default 'pending',
  source_db_type text not null,
  target_db_type text not null,
  source_credential_id text,
  target_credential_id text,
  migration_plan jsonb,
  schema_snapshot jsonb,
  data_profile jsonb,
  options jsonb default '{}',
  progress_pct integer default 0,
  rows_migrated bigint default 0,
  rows_total bigint default 0,
  error_log jsonb default '[]',
  validation_report jsonb,
  final_report jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table migration_jobs enable row level security;

-- Clients (anon key + user JWT) may only READ their own rows. All writes go
-- through the backend with the service-role key, which bypasses RLS.
drop policy if exists "Users see own jobs" on migration_jobs;
create policy "Users read own jobs"
  on migration_jobs for select
  using (auth.uid() = user_id);

do $$ begin
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and tablename = 'migration_jobs') then
    alter publication supabase_realtime add table migration_jobs;
  end if;
end $$;

create table if not exists migration_logs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references migration_jobs(id) on delete cascade not null,
  level text not null,
  agent text not null,
  message text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

alter table migration_logs enable row level security;

drop policy if exists "Users see own logs" on migration_logs;
create policy "Users read own logs"
  on migration_logs for select
  using (
    job_id in (
      select id from migration_jobs where user_id = auth.uid()
    )
  );

do $$ begin
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and tablename = 'migration_logs') then
    alter publication supabase_realtime add table migration_logs;
  end if;
end $$;

create table if not exists saved_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  nickname text not null,
  db_type text not null,
  host text,
  port integer,
  database_name text,
  credential_vault_id text not null,
  created_at timestamptz default now()
);

alter table saved_connections enable row level security;

drop policy if exists "Users see own connections" on saved_connections;
create policy "Users read own connections"
  on saved_connections for select
  using (auth.uid() = user_id);

-- ── updated_at trigger ──────────────────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists migration_jobs_updated_at on migration_jobs;
create trigger migration_jobs_updated_at
  before update on migration_jobs
  for each row execute function update_updated_at();

-- ── Vault RPC helpers (service-role only) ───────────────────────
-- supabase-py has no native Vault API; these SECURITY DEFINER functions
-- expose create/get/delete. RLS: revoke from anon/authenticated so only
-- the backend (service role) can call them.
create or replace function vault_create_secret(secret_value text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  sid uuid;
begin
  sid := vault.create_secret(secret_value);
  return sid;
end;
$$;

create or replace function vault_get_secret(secret_id uuid)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  val text;
begin
  select decrypted_secret into val
  from vault.decrypted_secrets
  where id = secret_id;
  return val;
end;
$$;

create or replace function vault_delete_secret(secret_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  delete from vault.secrets where id = secret_id;
end;
$$;

revoke execute on function vault_create_secret(text) from anon, authenticated;
revoke execute on function vault_get_secret(uuid) from anon, authenticated;
revoke execute on function vault_delete_secret(uuid) from anon, authenticated;

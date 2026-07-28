import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { isSupabaseConfigured, supabase } from '@/lib/supabase';
import { migrationKeys } from './useMigration';
import type { MigrationJob, MigrationLog } from '@/types';

/**
 * Live updates for a single job (god.md §12). Pushes payloads straight into
 * the TanStack Query cache so no polling is needed.
 *
 * `onLog` fires for each newly inserted log line — the terminal uses it to
 * append without re-rendering the whole buffer.
 */
export function useMigrationRealtime(jobId: string | undefined, onLog?: (log: MigrationLog) => void) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!jobId || !isSupabaseConfigured) return;

    // Unique name per subscription: `supabase.channel()` returns any existing
    // channel with the same name, and calling `.on()` on an already-subscribed
    // channel throws (bites on StrictMode's double-mount in dev).
    const channel = supabase
      .channel(`migration:${jobId}:${crypto.randomUUID()}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'migration_jobs',
          filter: `id=eq.${jobId}`,
        },
        (payload) => {
          const updated = payload.new as MigrationJob;

          queryClient.setQueryData(migrationKeys.detail(jobId), updated);
          queryClient.setQueryData<MigrationJob[]>(migrationKeys.all, (jobs) =>
            jobs?.map((job) => (job.id === jobId ? updated : job)),
          );
        },
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'migration_logs',
          filter: `job_id=eq.${jobId}`,
        },
        (payload) => {
          const log = payload.new as MigrationLog;

          queryClient.setQueryData<MigrationLog[]>(migrationKeys.logs(jobId), (logs) =>
            logs ? [...logs, log] : [log],
          );
          onLog?.(log);
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
    // `onLog` is intentionally excluded — callers pass an inline callback and
    // re-subscribing on every render would drop log lines.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, queryClient]);
}

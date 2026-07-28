import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { isActive } from '@/lib/utils';
import type {
  ConnectionTestRequest,
  ConnectionTestResult,
  CreateMigrationRequest,
  MigrationJob,
  MigrationLog,
  MigrationPlanData,
  ComplianceMatrix,
  ConfidenceBreakdown,
  DataQualityReport,
  DriftResponse,
  HealthReport,
  MigrationTemplate,
  Monitor,
  PreviewDiff,
  PublicReport,
  SaveConnectionRequest,
  SavedConnection,
  SemanticReport,
  ShareResponse,
  ShareVisibility,
  SimulationResult,
  TablePlanResponse,
} from '@/types';

export const migrationKeys = {
  all: ['migrations'] as const,
  detail: (id: string) => ['migrations', id] as const,
  logs: (id: string) => ['migrations', id, 'logs'] as const,
  plan: (id: string) => ['migrations', id, 'plan'] as const,
  semanticReport: (id: string) => ['migrations', id, 'semantic-report'] as const,
  previewDiff: (id: string) => ['migrations', id, 'preview-diff'] as const,
  confidenceBreakdown: (id: string) =>
    ['migrations', id, 'confidence-breakdown'] as const,
  compliance: ['compliance'] as const,
  quality: (id: string) => ['migrations', id, 'quality'] as const,
  simulation: (id: string) => ['migrations', id, 'simulation'] as const,
  tablePlan: (id: string) => ['migrations', id, 'tables'] as const,
  monitors: ['monitors'] as const,
  drift: (id: string) => ['monitors', id, 'drift'] as const,
  healthReport: (id: string) => ['monitors', id, 'health'] as const,
  templates: ['templates'] as const,
  publicReport: (token: string) => ['public', token] as const,
  connections: ['connections'] as const,
};

/**
 * Queries poll while a job is active. Realtime (when configured AND the user
 * is signed in — RLS blocks events for anonymous sessions) delivers instant
 * pushes on top; polling is the guarantee that the UI never freezes.
 */
const POLL_MS = 2_500;

/** GET /api/v1/migrations */
export function useMigrations() {
  return useQuery({
    queryKey: migrationKeys.all,
    queryFn: async () => (await api.get<MigrationJob[]>('/migrations')).data,
    staleTime: 15_000,
    refetchInterval: (query) =>
      query.state.data?.some(
        (job) => isActive(job.status) || job.status === 'pending',
      )
        ? POLL_MS
        : false,
  });
}

/** GET /api/v1/migrations/{id} */
export function useMigrationDetail(id: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.detail(id ?? ''),
    enabled: Boolean(id),
    queryFn: async () => (await api.get<MigrationJob>(`/migrations/${id}`)).data,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && (isActive(status) || status === 'pending') ? POLL_MS : false;
    },
  });
}

/** GET /api/v1/migrations/{id}/logs */
export function useMigrationLogs(id: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.logs(id ?? ''),
    enabled: Boolean(id),
    queryFn: async () => (await api.get<MigrationLog[]>(`/migrations/${id}/logs`)).data,
    refetchInterval: POLL_MS,
  });
}

/** GET /api/v1/migrations/{id}/plan */
export function useMigrationPlan(id: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.plan(id ?? ''),
    enabled: Boolean(id),
    queryFn: async () => (await api.get<MigrationPlanData>(`/migrations/${id}/plan`)).data,
  });
}

/**
 * GET /api/v1/migrations/{id}/semantic-report
 * 404s until the Data Profiler stage finishes — callers gate with `enabled`.
 */
export function useSemanticReport(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.semanticReport(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<SemanticReport>(`/migrations/${id}/semantic-report`)).data,
    retry: false,
  });
}

/** GET /api/v1/migrations/{id}/preview-diff — schema-says vs data-means. */
export function usePreviewDiff(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.previewDiff(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<PreviewDiff>(`/migrations/${id}/preview-diff`)).data,
    retry: false,
  });
}

/** GET /api/v1/migrations/{id}/confidence-breakdown — after validation. */
export function useConfidenceBreakdown(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.confidenceBreakdown(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<ConfidenceBreakdown>(`/migrations/${id}/confidence-breakdown`))
        .data,
    retry: false,
  });
}

/** GET /api/v1/compliance — server capability matrix, rarely changes. */
export function useCompliance() {
  return useQuery({
    queryKey: migrationKeys.compliance,
    queryFn: async () => (await api.get<ComplianceMatrix>('/compliance')).data,
    staleTime: Infinity,
  });
}

/** GET /api/v1/migrations/{id}/quality-report — T1-5. */
export function useQualityReport(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.quality(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<DataQualityReport>(`/migrations/${id}/quality-report`)).data,
    retry: false,
  });
}

/** GET /api/v1/migrations/{id}/simulation — T2-1. Polls while a run is queued. */
export function useSimulation(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.simulation(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<SimulationResult>(`/migrations/${id}/simulation`)).data,
    retry: false,
  });
}

/**
 * POST /api/v1/migrations/{id}/simulate — queues a Celery simulation.
 * The worker writes the result onto the job, so refresh the job (not a
 * separate query) a moment after queueing.
 */
export function useRunSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post(`/migrations/${id}/simulate`)).data,
    onSuccess: (_data, id) => {
      const refresh = () =>
        void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
      // Poll a few times: simulation length depends on table count and size.
      [2_000, 5_000, 10_000].forEach((delay) => setTimeout(refresh, delay));
    },
  });
}

/** GET /api/v1/migrations/{id}/tables — T2-4 dependency-ordered table plan. */
export function useTablePlan(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: migrationKeys.tablePlan(id ?? ''),
    enabled: Boolean(id) && enabled,
    queryFn: async () =>
      (await api.get<TablePlanResponse>(`/migrations/${id}/tables`)).data,
    retry: false,
  });
}

/** POST /api/v1/migrations/{id}/resume — T2-3. */
export function useResumeMigration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, onlyTables }: { id: string; onlyTables?: string[] }) =>
      (await api.post(`/migrations/${id}/resume`, { only_tables: onlyTables ?? null }))
        .data,
    onSettled: (_data, _error, { id }) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
    },
  });
}

/** POST /api/v1/migrations/{id}/share — T3-2/T3-5. */
export function useShareMigration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      visibility,
      redactNames,
    }: {
      id: string;
      visibility: ShareVisibility;
      redactNames: boolean;
    }) =>
      (
        await api.post<ShareResponse>(`/migrations/${id}/share`, {
          visibility,
          redact_names: redactNames,
        })
      ).data,
    onSettled: (_data, _error, { id }) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
    },
  });
}

/** GET /api/v1/public/{token} — no auth. */
export function usePublicReport(token: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.publicReport(token ?? ''),
    enabled: Boolean(token),
    queryFn: async () => (await api.get<PublicReport>(`/public/${token}`)).data,
    retry: false,
  });
}

/** GET /api/v1/templates — no auth. */
export function useTemplates() {
  return useQuery({
    queryKey: migrationKeys.templates,
    queryFn: async () =>
      (await api.get<{ templates: MigrationTemplate[] }>('/templates')).data.templates,
    staleTime: Infinity,
  });
}

/** GET /api/v1/monitoring — T4-1. */
export function useMonitors() {
  return useQuery({
    queryKey: migrationKeys.monitors,
    queryFn: async () => (await api.get<Monitor[]>('/monitoring')).data,
  });
}

/** POST /api/v1/monitoring — enroll a completed migration. */
export function useEnrollMonitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      jobId,
      alerts,
    }: {
      jobId: string;
      alerts?: { email?: string; slack_webhook?: string; pagerduty_key?: string };
    }) => (await api.post<Monitor>('/monitoring', { job_id: jobId, alerts: alerts ?? {} })).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.monitors });
    },
  });
}

/** GET /api/v1/monitoring/{id}/drift — latest report + timeline. */
export function useDrift(monitorId: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.drift(monitorId ?? ''),
    enabled: Boolean(monitorId),
    queryFn: async () =>
      (await api.get<DriftResponse>(`/monitoring/${monitorId}/drift`)).data,
  });
}

/** POST /api/v1/monitoring/{id}/check — run a drift check now. */
export function useRunDriftCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (monitorId: string) =>
      (await api.post(`/monitoring/${monitorId}/check`)).data,
    onSettled: (_data, _error, monitorId) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.drift(monitorId) });
      void queryClient.invalidateQueries({ queryKey: migrationKeys.monitors });
    },
  });
}

/** POST /api/v1/monitoring/{id}/rebaseline — accept current schema as normal. */
export function useRebaseline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (monitorId: string) =>
      (await api.post(`/monitoring/${monitorId}/rebaseline`)).data,
    onSettled: (_data, _error, monitorId) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.drift(monitorId) });
      void queryClient.invalidateQueries({ queryKey: migrationKeys.monitors });
    },
  });
}

/** DELETE /api/v1/monitoring/{id} */
export function useDeleteMonitor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (monitorId: string) =>
      (await api.delete(`/monitoring/${monitorId}`)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.monitors });
    },
  });
}

/** GET /api/v1/monitoring/{id}/health-report — T4-4. */
export function useHealthReport(monitorId: string | undefined) {
  return useQuery({
    queryKey: migrationKeys.healthReport(monitorId ?? ''),
    enabled: Boolean(monitorId),
    queryFn: async () =>
      (await api.get<HealthReport>(`/monitoring/${monitorId}/health-report`)).data,
  });
}

/** POST /api/v1/migrations */
export function useCreateMigration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateMigrationRequest) =>
      (await api.post<MigrationJob>('/migrations', payload)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    },
  });
}

/**
 * POST /api/v1/migrations/{id}/start — also used by "Try again" on failed or
 * cancelled jobs. Optimistically resets the job so the failure state clears
 * from the screen immediately.
 */
export function useStartMigration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post(`/migrations/${id}/start`)).data,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: migrationKeys.detail(id) });
      const previous = queryClient.getQueryData<MigrationJob>(migrationKeys.detail(id));
      const optimistic = (job: MigrationJob | undefined) =>
        job && job.id === id
          ? { ...job, status: 'pending' as const, progress_pct: 0, rows_migrated: 0 }
          : job;
      queryClient.setQueryData<MigrationJob>(migrationKeys.detail(id), optimistic);
      queryClient.setQueryData<MigrationJob[]>(migrationKeys.all, (jobs) =>
        jobs?.map((job) => optimistic(job) ?? job),
      );
      return { previous };
    },
    onError: (_error, id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(migrationKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _error, id) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    },
  });
}

/**
 * POST /api/v1/migrations/{id}/approve
 * Optimistically flips the job to "executing" so the approval banner
 * disappears the moment the user clicks — no waiting on the next push/poll.
 */
export function useApprovePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post(`/migrations/${id}/approve`)).data,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: migrationKeys.detail(id) });
      const previous = queryClient.getQueryData<MigrationJob>(migrationKeys.detail(id));
      const optimistic = (job: MigrationJob | undefined) =>
        job && job.id === id ? { ...job, status: 'executing' as const } : job;
      queryClient.setQueryData<MigrationJob>(migrationKeys.detail(id), optimistic);
      queryClient.setQueryData<MigrationJob[]>(migrationKeys.all, (jobs) =>
        jobs?.map((job) => optimistic(job) ?? job),
      );
      return { previous };
    },
    onError: (_error, id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(migrationKeys.detail(id), context.previous);
      }
      void queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    },
    onSettled: (_data, _error, id) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    },
  });
}

/** POST /api/v1/migrations/{id}/cancel — optimistic, same pattern as approve. */
export function useCancelMigration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.post(`/migrations/${id}/cancel`)).data,
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: migrationKeys.detail(id) });
      const previous = queryClient.getQueryData<MigrationJob>(migrationKeys.detail(id));
      const optimistic = (job: MigrationJob | undefined) =>
        job && job.id === id ? { ...job, status: 'cancelled' as const } : job;
      queryClient.setQueryData<MigrationJob>(migrationKeys.detail(id), optimistic);
      queryClient.setQueryData<MigrationJob[]>(migrationKeys.all, (jobs) =>
        jobs?.map((job) => optimistic(job) ?? job),
      );
      return { previous };
    },
    onError: (_error, id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(migrationKeys.detail(id), context.previous);
      }
    },
    onSettled: (_data, _error, id) => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: migrationKeys.all });
    },
  });
}

/** POST /api/v1/connections/test — never persists the credential. */
export function useTestConnection() {
  return useMutation({
    mutationFn: async (payload: ConnectionTestRequest) =>
      (await api.post<ConnectionTestResult>('/connections/test', payload)).data,
  });
}

/** GET /api/v1/connections */
export function useSavedConnections() {
  return useQuery({
    queryKey: migrationKeys.connections,
    queryFn: async () => (await api.get<SavedConnection[]>('/connections')).data,
    staleTime: 60_000,
  });
}

/**
 * POST /api/v1/connections — the credential goes straight to Supabase Vault;
 * only the vault id and this metadata are persisted.
 */
export function useSaveConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SaveConnectionRequest) =>
      (await api.post<SavedConnection>('/connections', payload)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.connections });
    },
  });
}

/** DELETE /api/v1/connections/{id} */
export function useDeleteConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.delete(`/connections/${id}`)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: migrationKeys.connections });
    },
  });
}

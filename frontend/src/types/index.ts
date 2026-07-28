/**
 * Shapes mirror the Supabase schema in god.md §5 and the API contracts in §7.
 * Keep these in sync with backend/app/models/*.py.
 */

export const DB_TYPES = [
  // PostgreSQL wire-compatible
  'postgres',
  'aurora-postgres',
  'rds-postgres',
  'cloudsql-postgres',
  'alloydb',
  'azure-postgres',
  'neon',
  'supabase',
  'cockroachdb',
  'timescaledb',
  'redshift',
  // MySQL wire-compatible
  'mysql',
  'mariadb',
  'aurora-mysql',
  'rds-mysql',
  'cloudsql-mysql',
  'azure-mysql',
  'planetscale',
  // MongoDB wire-compatible
  'mongodb',
  'documentdb',
  'cosmosdb-mongo',
  // Others
  'sqlite',
  'sqlserver',
  'azure-sql',
  'bigquery',
  'dynamodb',
  'neo4j',
] as const;

export type DbType = (typeof DB_TYPES)[number];

/** Engine family — drives placeholders, badges, and paradigm logic. */
export type DbFamily =
  | 'postgres'
  | 'mysql'
  | 'mongodb'
  | 'sqlite'
  | 'sqlserver'
  | 'bigquery'
  | 'dynamodb'
  | 'neo4j';

export const DB_FAMILY: Record<DbType, DbFamily> = {
  postgres: 'postgres',
  'aurora-postgres': 'postgres',
  'rds-postgres': 'postgres',
  'cloudsql-postgres': 'postgres',
  alloydb: 'postgres',
  'azure-postgres': 'postgres',
  neon: 'postgres',
  supabase: 'postgres',
  cockroachdb: 'postgres',
  timescaledb: 'postgres',
  redshift: 'postgres',
  mysql: 'mysql',
  mariadb: 'mysql',
  'aurora-mysql': 'mysql',
  'rds-mysql': 'mysql',
  'cloudsql-mysql': 'mysql',
  'azure-mysql': 'mysql',
  planetscale: 'mysql',
  mongodb: 'mongodb',
  documentdb: 'mongodb',
  'cosmosdb-mongo': 'mongodb',
  sqlite: 'sqlite',
  sqlserver: 'sqlserver',
  'azure-sql': 'sqlserver',
  bigquery: 'bigquery',
  dynamodb: 'dynamodb',
  neo4j: 'neo4j',
};

export type MigrationStatus =
  | 'pending'
  | 'analyzing'
  | 'profiling'
  | 'planning'
  | 'awaiting_approval'
  | 'executing'
  | 'validating'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type LogLevel = 'info' | 'warning' | 'error' | 'success';

export type ConflictStrategy = 'skip' | 'overwrite' | 'fail';

export interface MigrationOptions {
  skip_tables: string[];
  conflict_strategy: ConflictStrategy;
  dry_run: boolean;
  chunk_size: number;
}

export interface ColumnMapping {
  source_column: string;
  target_column: string;
  source_type: string;
  target_type: string;
  coercion?: string;
  transformation?: string | null;
}

export interface TablePlan {
  source_table: string;
  target_table_name: string;
  column_mappings: ColumnMapping[];
  transformation_rules: string[];
  relationship_handling: string;
  warnings: string[];
  estimated_rows: number;
}

export interface MigrationPlanData {
  summary: string;
  tables: TablePlan[];
  global_warnings: string[];
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
  row_count: number;
}

export interface SchemaSnapshot {
  tables: SchemaTable[];
}

export interface ColumnProfile {
  column: string;
  null_pct: number;
  distinct_count: number;
  inferred: string;
  is_pii: boolean;
}

export interface DataProfile {
  tables: Record<string, ColumnProfile[]>;
  /** Written by the profiler from T1-5 onward; absent on older jobs. */
  quality?: DataQualityReport;
  /** T1-4 relationship intelligence; absent on older jobs. */
  inferred_foreign_keys?: ImplicitForeignKey[];
}

export interface TableValidation {
  table: string;
  source_rows: number;
  target_rows: number;
  match: boolean;
}

export interface ValidationTableCheck {
  target_table?: string;
  source_rows: number;
  target_rows: number;
  row_count_ok?: boolean;
  mismatch_pct?: number;
  fk_integrity_ok?: boolean;
  sample_hash?: { sampled: number; matched: number; match_ratio: number };
}

export interface ValidationReport {
  confidence_score: number;
  /** Backend shape (per-table map). */
  tables?: Record<string, ValidationTableCheck>;
  flagged_tables?: string[];
  passed?: boolean;
  /** Legacy/demo shape. */
  row_count_checks?: TableValidation[];
  hash_checks_passed?: number;
  hash_checks_total?: number;
  referential_integrity_ok?: boolean;
  notes?: string[];
}

/** GET /api/v1/migrations/{id}/semantic-report */
export interface SemanticFinding {
  table: string;
  column: string;
  declared_type: string | null;
  sample_size: number;
}

export interface ImplicitBooleanFinding extends SemanticFinding {
  sample_values: string[];
  confidence: number;
}

export interface ImplicitEnumFinding extends SemanticFinding {
  distinct_values: string[];
  distinct_count: number;
  confidence: number;
}

export type PiiType =
  | 'email'
  | 'phone'
  | 'government_id'
  | 'credential'
  | 'payment'
  | 'date_of_birth'
  | 'address'
  | 'name'
  | 'other';

export interface PiiFinding extends SemanticFinding {
  pii_type: PiiType;
}

export interface SemanticReport {
  implicit_booleans: ImplicitBooleanFinding[];
  implicit_enums: ImplicitEnumFinding[];
  never_null_nullables: SemanticFinding[];
  pii_columns: PiiFinding[];
  semantic_detections: SemanticDetection[];
  dangerous_type_mismatches: DangerousMismatch[];
  implicit_foreign_keys: ImplicitForeignKey[];
  summary: {
    total_columns_profiled: number;
    total_mismatches: number;
    implicit_boolean_count: number;
    implicit_enum_count: number;
    never_null_nullable_count: number;
    pii_column_count: number;
    semantic_detection_count: number;
    dangerous_mismatch_count: number;
    implicit_fk_count: number;
  };
  total_mismatches: number;
  schema_trust_score: number;
}

/** GET /api/v1/migrations/{id}/preview-diff */
export interface PreviewDiffRow {
  table: string;
  column: string;
  declared: {
    type: string | null;
    nullable: boolean | null;
    primary_key: boolean;
  };
  inferred: {
    semantic_type: string;
    not_null_in_practice: boolean;
    pii_type: PiiType | null;
    notes: string[];
  };
  recommendation: string;
  differs: boolean;
  confidence: number;
}

export interface PreviewDiff {
  rows: PreviewDiffRow[];
  differing_count: number;
  total_count: number;
  schema_trust_score: number;
}

/** GET /api/v1/migrations/{id}/confidence-breakdown */
export interface ColumnConfidence {
  column: string;
  confidence: number;
  needs_review: boolean;
  reasons: string[];
}

export interface TableConfidence {
  table: string;
  confidence: number;
  needs_review: boolean;
  components: {
    row_count: boolean;
    sample_hash_ratio: number;
    fk_integrity: boolean;
  };
  columns: ColumnConfidence[];
}

export interface ConfidenceBreakdown {
  overall_confidence: number;
  review_threshold: number;
  tables: TableConfidence[];
  flagged_columns: Array<ColumnConfidence & { table: string }>;
}

/** GET /api/v1/compliance */
export interface ComplianceEntry {
  db_type: string;
  family: DbFamily;
  driver_package: string;
  driver_installed: boolean;
  type_rules: boolean;
  source_supported: boolean;
  target_supported: boolean;
  compliant: boolean;
  notes: string;
}

export interface ComplianceMatrix {
  entries: ComplianceEntry[];
  families: Record<
    string,
    { driver_package: string; driver_installed: boolean; type_rules: boolean }
  >;
  compliant_count: number;
  total_count: number;
}

/** T1-1 — extended semantic type library. */
export type SemanticTypeName =
  | 'email'
  | 'phone'
  | 'uuid'
  | 'url'
  | 'unix_timestamp'
  | 'currency'
  | 'zip_code'
  | 'date_string'
  | 'json_string';

export interface SemanticDetection extends SemanticFinding {
  inferred_semantic_type: SemanticTypeName;
  confidence_pct: number;
  sample_values: Array<string | number | boolean | null>;
  evidence_summary: string;
}

export interface DangerousMismatch extends SemanticDetection {
  risk: string;
}

/** T1-4 — relationship intelligence. */
export interface ImplicitForeignKey {
  table: string;
  column: string;
  likely_references: string;
  match_pct: number;
  name_match: boolean;
}

/** T1-5 — data quality report. */
export type QualitySeverity = 'high' | 'medium' | 'low';

export type QualityIssueKind =
  | 'duplicate_in_unique'
  | 'empty_string_in_not_null'
  | 'sentinel_date'
  | 'numeric_sentinel'
  | 'orphaned_rows';

export interface QualityIssue {
  severity: QualitySeverity;
  kind: QualityIssueKind;
  table: string;
  column: string | null;
  detail: string;
}

export interface DataQualityReport {
  quality_score: number;
  issues: QualityIssue[];
  per_table: Record<string, QualityIssue[]>;
  counts: Partial<Record<QualitySeverity, number>>;
  tables_checked: number;
}

/** T2-1 — migration simulation. */
export type SimulationCell = string | number | boolean | null;

export interface SimulationRow {
  source: Record<string, SimulationCell>;
  transformed: Record<string, SimulationCell>;
  changed_columns: string[];
}

export interface SimulationTable {
  target_table: string;
  columns: Array<{
    source: string;
    target: string;
    source_type: string | null;
    target_type: string | null;
  }>;
  rows: SimulationRow[];
  rows_simulated: number;
  rows_with_changes: number;
}

export interface SimulationResult {
  tables: Record<string, SimulationTable>;
  total_rows_simulated: number;
  total_rows_with_changes: number;
  generated_at: string;
}

/** T2-4 — incremental table-by-table migration. */
export type TableStatus =
  | 'pending'
  | 'migrating'
  | 'migrated'
  | 'validated'
  | 'skipped';

export interface TablePlanEntry {
  table: string;
  target_table: string;
  order: number;
  status: TableStatus;
  rows_committed: number;
  estimated_rows: number;
  depends_on: string[];
}

export interface TablePlanResponse {
  tables: TablePlanEntry[];
  load_order: string[];
}

/** T3-2 / T3-5 — share links and badges. */
export type ShareVisibility = 'private' | 'team' | 'public';

export interface ShareResponse {
  token: string;
  visibility: ShareVisibility;
  redact_names: boolean;
  report_url: string;
  badge_url: string;
  badge_markdown: string;
}

export interface PublicReport {
  job_id: string;
  source_db_type: DbType;
  target_db_type: DbType;
  completed_at: string | null;
  tables_migrated: number;
  rows_migrated: number;
  confidence_score: number;
  schema_trust_score: number | null;
  semantic_mismatches_caught: {
    implicit_booleans: number;
    implicit_enums: number;
    never_null_nullables: number;
    dangerous_type_mismatches: number;
    implicit_foreign_keys: number;
    pii_columns: number;
    total: number;
  };
  tables: Array<{
    table: string;
    source_rows: number | null;
    target_rows: number | null;
    row_count_ok: boolean | null;
  }>;
  duration_seconds: number | null;
  estimated_manual_hours: number;
  names_redacted: boolean;
}

/** T3-4 — migration templates. */
export interface MigrationTemplate {
  slug: string;
  title: string;
  stack: string;
  source_db_type: DbType;
  target_db_type: DbType;
  summary: string;
  quirks: string[];
  type_overrides?: Record<string, string>;
  options: Partial<MigrationOptions>;
}

/** T4-1 … T4-4 — drift monitoring. */
export type DriftSeverity = 'critical' | 'warning' | 'info';

export type DriftKind =
  | 'table_dropped'
  | 'table_added'
  | 'column_dropped'
  | 'column_added'
  | 'type_changed'
  | 'not_null_dropped'
  | 'not_null_added'
  | 'index_dropped'
  | 'index_added';

export interface DriftEvent {
  severity: DriftSeverity;
  kind: DriftKind;
  table: string;
  column: string | null;
  detail: string;
  old_type?: string;
  new_type?: string;
  semantic_regression?: {
    likely_semantic_type: string;
    recommendation: string;
  } | null;
}

export interface DriftCheck {
  id: string;
  checked_at: string;
  has_drift: boolean;
  counts: Partial<Record<DriftSeverity, number>>;
  health_score: number;
  events?: DriftEvent[];
  error?: string;
}

export interface DriftResponse {
  latest: DriftCheck | null;
  timeline: DriftCheck[];
}

export interface Monitor {
  id: string;
  job_id: string;
  name: string;
  target_db_type: DbType;
  enabled: boolean;
  baseline_taken_at: string | null;
  last_checked_at: string | null;
  last_health_score: number | null;
  baseline_table_count: number;
  alerts_configured: { email: boolean; slack: boolean; pagerduty: boolean };
}

export interface HealthReport {
  monitor_id: string;
  name: string;
  checks_run: number;
  health_score: number;
  drift_events: number;
  critical_events: number;
  warning_events: number;
  new_semantic_issues: Array<{
    table: string;
    column: string | null;
    likely_semantic_type?: string;
    recommendation?: string;
  }>;
  recommendations: string[];
  headline: string;
}

export type FlagSeverity = 'high' | 'medium' | 'low';

export interface ReportFlag {
  severity: FlagSeverity;
  table: string | null;
  title: string;
  detail: string;
  what_to_check?: string;
}

export interface FinalReport {
  executive_summary: string;
  confidence_score: number;
  passed: boolean;
  ai_generated: boolean;
  generated_at: string;
  confidence_explanation?: {
    narrative?: string;
    breakdown?: Array<{
      component: string;
      weight: string;
      score: number;
      reason: string;
    }>;
  };
  flags: ReportFlag[];
  recommendations: string[];
}

export interface MigrationJob {
  id: string;
  user_id: string;
  name: string;
  status: MigrationStatus;
  source_db_type: DbType;
  target_db_type: DbType;
  source_credential_id: string | null;
  target_credential_id: string | null;
  migration_plan: MigrationPlanData | null;
  schema_snapshot: SchemaSnapshot | null;
  data_profile: DataProfile | null;
  options: MigrationOptions;
  progress_pct: number;
  rows_migrated: number;
  rows_total: number;
  error_log: Array<string | { at?: string; error: string }>;
  validation_report: ValidationReport | null;
  final_report: FinalReport | null;
  /** Present once a simulation has run (T2-1). */
  simulation: SimulationResult | null;
  /** Per-table resume state (T2-3). */
  checkpoints: Record<
    string,
    { last_pk: string | number | null; rows_committed: number; done: boolean }
  >;
  share_token: string | null;
  share_visibility: ShareVisibility | null;
  share_redact_names: boolean | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MigrationLog {
  id: string;
  job_id: string;
  level: LogLevel;
  agent: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SavedConnection {
  id: string;
  user_id: string;
  nickname: string;
  db_type: DbType;
  host: string | null;
  port: number | null;
  database_name: string | null;
  created_at: string;
}

/** POST /api/v1/connections/test */
export interface ConnectionTestRequest {
  db_type: DbType;
  connection_string: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  message: string;
  server_version?: string;
  latency_ms?: number;
  tables?: string[];
  /** T2-5 — null means the privilege probe was inconclusive for this engine. */
  has_write_access?: boolean | null;
  privilege_evidence?: string | null;
  readonly_advice?: {
    warning: string;
    grant_sql: string[];
    connection_string: string;
  } | null;
}

/** POST /api/v1/connections — connection_string is vaulted, never returned. */
export interface SaveConnectionRequest {
  nickname: string;
  db_type: DbType;
  connection_string: string;
  host?: string | null;
  port?: number | null;
  database_name?: string | null;
}

/**
 * POST /api/v1/migrations — supply either a saved connection id or a raw
 * connection string per side.
 */
export interface CreateMigrationRequest {
  name: string;
  source_db_type: DbType;
  target_db_type: DbType;
  source_connection_string?: string;
  target_connection_string?: string;
  source_connection_id?: string;
  target_connection_id?: string;
  options: MigrationOptions;
}

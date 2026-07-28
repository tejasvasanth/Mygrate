import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { DB_FAMILY, type DbFamily, type DbType, type MigrationStatus } from '@/types';

/** Merge Tailwind class names without style conflicts. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export const DB_LABELS: Record<DbType, string> = {
  postgres: 'PostgreSQL',
  'aurora-postgres': 'Amazon Aurora (PostgreSQL)',
  'rds-postgres': 'Amazon RDS (PostgreSQL)',
  'cloudsql-postgres': 'GCP Cloud SQL (PostgreSQL)',
  alloydb: 'GCP AlloyDB',
  'azure-postgres': 'Azure Database for PostgreSQL',
  neon: 'Neon',
  supabase: 'Supabase',
  cockroachdb: 'CockroachDB',
  timescaledb: 'TimescaleDB',
  redshift: 'Amazon Redshift',
  mysql: 'MySQL',
  mariadb: 'MariaDB',
  'aurora-mysql': 'Amazon Aurora (MySQL)',
  'rds-mysql': 'Amazon RDS (MySQL)',
  'cloudsql-mysql': 'GCP Cloud SQL (MySQL)',
  'azure-mysql': 'Azure Database for MySQL',
  planetscale: 'PlanetScale',
  mongodb: 'MongoDB',
  documentdb: 'Amazon DocumentDB',
  'cosmosdb-mongo': 'Azure Cosmos DB (Mongo API)',
  sqlite: 'SQLite',
  sqlserver: 'SQL Server',
  'azure-sql': 'Azure SQL',
  bigquery: 'Google BigQuery',
  dynamodb: 'Amazon DynamoDB',
  neo4j: 'Neo4j (graph)',
};

export const STATUS_LABELS: Record<MigrationStatus, string> = {
  pending: 'Pending',
  analyzing: 'Analyzing schema',
  profiling: 'Profiling data',
  planning: 'Planning',
  awaiting_approval: 'Awaiting approval',
  executing: 'Executing',
  validating: 'Validating',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/** Statuses where the pipeline is actively working. */
export const ACTIVE_STATUSES: MigrationStatus[] = [
  'analyzing',
  'profiling',
  'planning',
  'executing',
  'validating',
];

export function isActive(status: MigrationStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

/** 1234567 → "1.23M" */
export function formatNumber(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function formatFullNumber(value: number): string {
  return value.toLocaleString('en-US');
}

/** "3 minutes ago" style relative time. */
export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diffMs / 1000);

  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Elapsed wall-clock between two timestamps, e.g. "4m 12s". */
export function duration(startIso: string | null, endIso: string | null): string {
  if (!startIso) return '—';
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const totalSeconds = Math.max(0, Math.floor((end - new Date(startIso).getTime()) / 1000));

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Difficulty of a source→target pair, per the matrix in god.md §15. */
export function pairDifficulty(source: DbType, target: DbType): 'Low' | 'Medium' | 'High' {
  const sf = DB_FAMILY[source];
  const tf = DB_FAMILY[target];
  if (sf === tf) return 'Low';

  const paradigm = (f: DbFamily): 'relational' | 'document' | 'graph' =>
    f === 'mongodb' || f === 'dynamodb'
      ? 'document'
      : f === 'neo4j'
        ? 'graph'
        : 'relational';

  if (paradigm(sf) !== paradigm(tf)) return 'High';
  if (tf === 'sqlite') return 'Medium';
  return 'Low';
}

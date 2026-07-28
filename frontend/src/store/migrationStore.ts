import { create } from 'zustand';
import type { ConflictStrategy, DbType } from '@/types';

/**
 * UI-only state (god.md §14): wizard position, draft form values, sidebar.
 * Server data lives in TanStack Query — never here.
 */

export interface ConnectionDraft {
  db_type: DbType;
  connection_string: string;
  tested: boolean;
  discovered_tables: string[];
  /**
   * Set when a saved connection is chosen. The job is then created with
   * {side}_connection_id and the credential is read from Vault server-side —
   * the plaintext string never enters the browser.
   */
  connection_id?: string | null;
}

const emptyConnection: ConnectionDraft = {
  db_type: 'postgres',
  connection_string: '',
  tested: false,
  discovered_tables: [],
  connection_id: null,
};

interface MigrationWizardState {
  step: number;
  source: ConnectionDraft;
  target: ConnectionDraft;
  name: string;
  skipTables: string[];
  conflictStrategy: ConflictStrategy;
  dryRun: boolean;
  chunkSize: number;

  sidebarCollapsed: boolean;

  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  setSource: (patch: Partial<ConnectionDraft>) => void;
  setTarget: (patch: Partial<ConnectionDraft>) => void;
  setName: (name: string) => void;
  setSkipTables: (tables: string[]) => void;
  setConflictStrategy: (strategy: ConflictStrategy) => void;
  setDryRun: (dryRun: boolean) => void;
  setChunkSize: (size: number) => void;
  toggleSidebar: () => void;
  reset: () => void;
}

export const useMigrationStore = create<MigrationWizardState>((set) => ({
  step: 0,
  source: { ...emptyConnection },
  target: { ...emptyConnection, db_type: 'mongodb' },
  name: '',
  skipTables: [],
  conflictStrategy: 'skip',
  dryRun: true,
  chunkSize: 1000,
  sidebarCollapsed: false,

  setStep: (step) => set({ step }),
  nextStep: () => set((s) => ({ step: Math.min(s.step + 1, 2) })),
  prevStep: () => set((s) => ({ step: Math.max(s.step - 1, 0) })),

  // Editing a connection string invalidates a previous successful test.
  setSource: (patch) =>
    set((s) => ({
      source: {
        ...s.source,
        ...patch,
        tested: patch.connection_string !== undefined ? false : (patch.tested ?? s.source.tested),
      },
    })),
  setTarget: (patch) =>
    set((s) => ({
      target: {
        ...s.target,
        ...patch,
        tested: patch.connection_string !== undefined ? false : (patch.tested ?? s.target.tested),
      },
    })),

  setName: (name) => set({ name }),
  setSkipTables: (skipTables) => set({ skipTables }),
  setConflictStrategy: (conflictStrategy) => set({ conflictStrategy }),
  setDryRun: (dryRun) => set({ dryRun }),
  setChunkSize: (chunkSize) => set({ chunkSize }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  reset: () =>
    set({
      step: 0,
      source: { ...emptyConnection },
      target: { ...emptyConnection, db_type: 'mongodb' },
      name: '',
      skipTables: [],
      conflictStrategy: 'skip',
      dryRun: true,
      chunkSize: 1000,
    }),
}));

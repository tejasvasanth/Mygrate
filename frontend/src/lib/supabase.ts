import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

/**
 * True when Supabase credentials are present. The UI checks this before
 * attempting auth or Realtime so a partially-configured local env renders
 * a clear message rather than throwing.
 */
export const isSupabaseConfigured = Boolean(url && anonKey);

/**
 * Singleton client (god.md §14). Never instantiate a client elsewhere.
 * When unconfigured we still construct against a harmless placeholder so
 * imports stay side-effect free; all callers must gate on
 * `isSupabaseConfigured` before issuing requests.
 */
export const supabase: SupabaseClient = createClient(
  url || 'http://localhost:54321',
  anonKey || 'public-anon-key-placeholder',
  {
    auth: {
      persistSession: isSupabaseConfigured,
      autoRefreshToken: isSupabaseConfigured,
    },
  },
);

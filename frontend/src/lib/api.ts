import axios from 'axios';
import { isSupabaseConfigured, supabase } from './supabase';

/**
 * The single Axios instance for all FastAPI calls (god.md §14).
 * Never use raw fetch elsewhere.
 */
export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/api/v1`,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

/** Attach the Supabase JWT to every request (god.md §7). */
api.interceptors.request.use(async (config) => {
  if (isSupabaseConfigured) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

/** Normalise FastAPI error bodies into a readable message. */
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (error.code === 'ERR_NETWORK') return 'Cannot reach the migration API.';
    return error.message;
  }
  return error instanceof Error ? error.message : 'Unexpected error.';
}

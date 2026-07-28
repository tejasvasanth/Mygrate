import { useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { isSupabaseConfigured, supabase } from '@/lib/supabase';

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  configured: boolean;
}

/** Supabase auth session, kept in sync via onAuthStateChange. */
export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    session: null,
    loading: isSupabaseConfigured,
    configured: isSupabaseConfigured,
  });

  useEffect(() => {
    if (!isSupabaseConfigured) return;

    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setState({
        user: data.session?.user ?? null,
        session: data.session,
        loading: false,
        configured: true,
      });
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({
        user: session?.user ?? null,
        session,
        loading: false,
        configured: true,
      });
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  const signInWithEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  };

  const signUpWithEmail = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  return { ...state, signInWithEmail, signUpWithEmail, signOut };
}

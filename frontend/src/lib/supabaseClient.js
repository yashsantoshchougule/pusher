import { createClient } from '@supabase/supabase-js';
import { isRecoveryCallback, trackRecoverySession } from './passwordRecovery.js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

export let supabase = null;
export let supabaseConfigError = '';
export let recoverySession = null;
export const recoveryCallback = typeof window !== 'undefined' && isRecoveryCallback(window.location);

if (!supabaseUrl || !supabaseAnonKey) {
  supabaseConfigError = 'Cloud sign-in is unavailable. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in the frontend configuration.';
} else {
  try {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: !recoveryCallback,
        persistSession: !recoveryCallback,
        detectSessionInUrl: true,
      },
    });
    if (recoveryCallback) recoverySession = trackRecoverySession(supabase.auth);
  } catch {
    supabaseConfigError = 'Cloud sign-in is unavailable. The Supabase frontend configuration is invalid.';
  }
}

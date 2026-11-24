import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

export let supabase = null;
export let supabaseConfigError = '';

if (!supabaseUrl || !supabaseAnonKey) {
  supabaseConfigError = 'Cloud sign-in is unavailable. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in the frontend configuration.';
} else {
  try {
    supabase = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
      },
    });
  } catch {
    supabaseConfigError = 'Cloud sign-in is unavailable. The Supabase frontend configuration is invalid.';
  }
}

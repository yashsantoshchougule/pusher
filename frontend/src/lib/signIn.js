export async function authenticateEmail(auth, mode, credentials, redirectTo) {
  if (!auth) throw new Error('Supabase sign-in is not configured.');
  const { email, password, firstName, lastName } = credentials;
  const login = { email: email.trim(), password };
  const { data, error } = mode === 'signup'
    ? await auth.signUp({
        ...login,
        options: { emailRedirectTo: redirectTo, data: { first_name: firstName, last_name: lastName } },
      })
    : await auth.signInWithPassword(login);
  if (error) throw error;
  if (mode !== 'signup' && !data.session) throw new Error('Sign-in returned no session.');
  return data.session;
}

export async function authenticateProvider(auth, provider, redirectTo) {
  if (!auth) throw new Error('Supabase sign-in is not configured.');
  const { error } = await auth.signInWithOAuth({ provider, options: { redirectTo } });
  if (error) throw error;
}

export async function endSession(auth) {
  const { error } = await auth.signOut({ scope: 'local' });
  if (error) throw error;
}

export async function verifyOperatorSession(token, request = fetch) {
  let response;
  try {
    response = await request('/api/session', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: 'no-store',
    });
    if (response.ok) return await response.json();
  } catch {
    throw new Error('Pusher could not check your session. Make sure the backend is running and try again.');
  }
  if (!token && response.status === 401) return null;
  if (response.status === 403) throw new Error('Confirm your email before signing in to Pusher.');
  if (response.status === 401) {
    throw new Error('Pusher could not verify your sign-in. Check that the frontend and backend use the same Supabase project.');
  }
  throw new Error('Pusher could not check your session right now. Try again shortly.');
}

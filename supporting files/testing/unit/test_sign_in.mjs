import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isRecoveryCallback } from '../../../frontend/src/lib/passwordRecovery.js';
import { authenticateEmail, authenticateProvider, endSession, verifyOperatorSession } from '../../../frontend/src/lib/signIn.js';

const credentials = { email: ' operator@example.invalid ', password: 'fixture-password' };
const redirect = 'http://localhost:3000/';

function initializeBrowserAuth(env, createClient, pathname = '/', trackRecoverySession = () => null) {
  const source = readFileSync(new URL('../../../frontend/src/lib/supabaseClient.js', import.meta.url), 'utf8')
    .replace("import { createClient } from '@supabase/supabase-js';", '')
    .replace("import { isRecoveryCallback, trackRecoverySession } from './passwordRecovery.js';", '')
    .replaceAll('import.meta.env', 'env')
    .replaceAll('export ', '');
  return new Function('env', 'createClient', 'window', 'isRecoveryCallback', 'trackRecoverySession',
    source + '\nreturn { supabase, supabaseConfigError, recoverySession, recoveryCallback };')(
    env, createClient, { location: new URL(pathname, redirect) }, isRecoveryCallback, trackRecoverySession,
  );
}

test('incomplete browser configuration never creates a provider client', () => {
  for (const env of [
    {},
    { VITE_SUPABASE_URL: 'https://fixture.example.invalid' },
    { VITE_SUPABASE_ANON_KEY: 'fixture-key' },
    { VITE_SUPABASE_URL: ' ', VITE_SUPABASE_ANON_KEY: 'fixture-key' },
  ]) {
    const result = initializeBrowserAuth(env, () => assert.fail('Unexpected Supabase client'));
    assert.equal(result.supabase, null);
    assert.match(result.supabaseConfigError, /VITE_SUPABASE_URL.*VITE_SUPABASE_ANON_KEY/);
  }
});

test('explicit settings initialize the provider and an invalid configuration leaves it disabled', () => {
  const client = {};
  const env = {
    VITE_SUPABASE_URL: ' https://fixture.example.invalid ',
    VITE_SUPABASE_ANON_KEY: ' fixture-key ',
  };
  const result = initializeBrowserAuth(env, (url, key, options) => {
    assert.equal(url, 'https://fixture.example.invalid');
    assert.equal(key, 'fixture-key');
    assert.equal(options.auth.detectSessionInUrl, true);
    return client;
  });
  assert.deepEqual(result, { supabase: client, supabaseConfigError: '', recoverySession: null, recoveryCallback: false });
  const invalid = initializeBrowserAuth(env, () => { throw new Error('Invalid URL'); });
  assert.equal(invalid.supabase, null);
  assert.match(invalid.supabaseConfigError, /configuration is invalid/i);
});

test('the callback uses an in-memory session and subscribes before returning the client', () => {
  const auth = {};
  const tracker = {};
  const result = initializeBrowserAuth({
    VITE_SUPABASE_URL: 'https://fixture.example.invalid', VITE_SUPABASE_ANON_KEY: 'fixture-key',
  }, (_url, _key, options) => {
    assert.equal(options.auth.persistSession, false);
    assert.equal(options.auth.autoRefreshToken, false);
    return { auth };
  }, '/auth/recovery', client => {
    assert.equal(client, auth);
    return tracker;
  });
  assert.equal(result.recoveryCallback, true);
  assert.equal(result.recoverySession, tracker);
});

test('a recovery callback sent to the app root cannot become a saved sign-in', () => {
  const env = { VITE_SUPABASE_URL: 'https://fixture.example.invalid', VITE_SUPABASE_ANON_KEY: 'fixture-key' };
  for (const callbackUrl of ['/#type=recovery', '/?type=recovery']) {
    const client = {};
    const tracker = {};
    let options;
    const result = initializeBrowserAuth(env, (_url, _key, config) => {
      options = config;
      return client;
    }, callbackUrl, () => tracker);
    assert.equal(options.auth.persistSession, false);
    assert.equal(options.auth.autoRefreshToken, false);
    assert.equal(result.recoveryCallback, true);
    assert.equal(result.recoverySession, tracker);
  }
});

test('email login submits the password and requires a returned session', async () => {
  const session = { access_token: 'verified-session-fixture' };
  assert.equal(await authenticateEmail({
    signInWithPassword: async (input) => {
      assert.deepEqual(input, { email: 'operator@example.invalid', password: 'fixture-password' });
      return { data: { session } };
    },
  }, 'login', credentials, redirect), session);
  await assert.rejects(authenticateEmail({
    signInWithPassword: async () => ({ error: new Error('Invalid credentials') }),
  }, 'login', credentials, redirect), /Invalid credentials/);
});

test('unconfirmed email signup yields no session', async () => {
  const result = await authenticateEmail({
    signUp: async (input) => {
      assert.equal(input.options.emailRedirectTo, redirect);
      return { data: { session: null } };
    },
  }, 'signup', credentials, redirect);
  assert.equal(result, null);
});

test('Google and GitHub delegate to Supabase and propagate provider failure', async () => {
  for (const provider of ['google', 'github']) {
    await authenticateProvider({
      signInWithOAuth: async (input) => {
        assert.deepEqual(input, { provider, options: { redirectTo: redirect } });
        return { error: null };
      },
    }, provider, redirect);
  }
  await assert.rejects(authenticateProvider({
    signInWithOAuth: async () => ({ error: new Error('Canceled') }),
  }, 'google', redirect), /Canceled/);
  await assert.rejects(authenticateProvider(null, 'github', redirect), /not configured/);
});

test('sign-out clears the provider session for this browser', async () => {
  await endSession({ signOut: async (options) => {
    assert.deepEqual(options, { scope: 'local' });
    return { error: null };
  } });
});

test('session verification distinguishes sign-in rejection from normal signed-out state', async () => {
  const denied = async () => ({ ok: false, status: 401 });
  assert.equal(await verifyOperatorSession('', denied), null);
  await assert.rejects(verifyOperatorSession('fixture-session', denied), /same Supabase project/);
  await assert.rejects(verifyOperatorSession('fixture-session', async () => ({ ok: false, status: 403 })),
    /Confirm your email/);
  await assert.rejects(verifyOperatorSession('fixture-session', async () => { throw new TypeError('Offline'); }),
    /backend is running/);
});

test('accepted sessions are returned with authenticated status checks', async () => {
  const identity = { user_id: 'supabase:fixture', offline: false };
  const actual = await verifyOperatorSession('fixture-session', async (url, options) => {
    assert.equal(url, '/api/session');
    assert.equal(options.headers.Authorization, 'Bearer fixture-session');
    return { ok: true, json: async () => identity };
  });
  assert.equal(actual, identity);
});

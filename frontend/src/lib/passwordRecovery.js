import { endSession } from './signIn.js';

export const forgotPasswordPath = '/auth/forgot';
export const recoveryPath = '/auth/recovery';
export const resetRequestMessage = 'If this address has an account, you’ll receive a password reset email.';

export function isRecoveryCallback({ pathname, search, hash }) {
  // The URL only selects an isolated client. Supabase must still validate the session.
  return pathname === recoveryPath ||
    new URLSearchParams(search).get('type') === 'recovery' ||
    new URLSearchParams(hash.slice(1)).get('type') === 'recovery';
}

export async function requestPasswordReset(auth, email, origin) {
  try {
    const { error } = await auth.resetPasswordForEmail(email.trim(), { redirectTo: new URL(recoveryPath, origin).href });
    if (error && error.code !== 'user_not_found') throw error;
  } catch {
    throw new Error('The reset request could not be sent right now. Try again shortly.');
  }
  return resetRequestMessage;
}

export function trackRecoverySession(auth) {
  let snapshot = { status: 'checking', userId: null };
  const listeners = new Set();
  auth.onAuthStateChange((event, session) => {
    const userId = session?.user?.id;
    if (event === 'PASSWORD_RECOVERY' && userId) {
      snapshot = { status: 'ready', userId };
    } else if (snapshot.status === 'checking' && event === 'INITIAL_SESSION') {
      snapshot = { status: 'invalid', userId: null };
    } else if (snapshot.status === 'ready' && (event === 'SIGNED_OUT' || userId !== snapshot.userId)) {
      snapshot = { status: 'invalid', userId: null };
    } else {
      return;
    }
    for (const notify of listeners) notify();
  });
  return {
    getSnapshot: () => snapshot,
    subscribe(notify) {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
  };
}

export async function updateRecoveryPassword(auth, getRecovery, password, confirmation) {
  const recovery = getRecovery();
  if (recovery.status !== 'ready') throw new Error('Request a new password reset link.');
  if (password.length < 8) throw new Error('Use at least 8 characters for your new password.');
  if (password !== confirmation) throw new Error('The passwords do not match.');

  const { data, error: userError } = await auth.getUser();
  if (userError || data?.user?.id !== recovery.userId || getRecovery() !== recovery) {
    throw new Error('This reset link is no longer valid. Request a new link.');
  }
  const { error } = await auth.updateUser({ password });
  if (error) throw new Error('The password could not be updated. Check the password requirements or request a new link.');
}

export async function closeRecoverySession(auth, getRecovery) {
  if (getRecovery().status === 'ready') await endSession(auth);
}

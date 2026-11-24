import React, { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { closeRecoverySession, forgotPasswordPath, recoveryPath, requestPasswordReset, updateRecoveryPassword } from '../lib/passwordRecovery.js';
import { recoverySession, supabase, supabaseConfigError } from '../lib/supabaseClient.js';

const fieldClass = 'w-full rounded-lg border border-[#455230] bg-white p-2';
const buttonClass = 'w-full rounded-lg bg-[#455230] p-2 font-semibold text-white disabled:opacity-60';
const loginUrl = '/?view=login';
const unavailable = { status: 'invalid', userId: null };
const getSnapshot = recoverySession?.getSnapshot ?? (() => unavailable);
const subscribe = recoverySession?.subscribe ?? (() => () => {});

export default function AccountRecoveryPage({ requesting }) {
  const session = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!requesting && session.status !== 'checking') {
      window.history.replaceState(null, '', recoveryPath);
    }
  }, [requesting, session.status]);

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    const fields = new FormData(event.currentTarget);
    const auth = supabase?.auth;
    if (!auth) return;
    busy.current = true;
    setPending(true);
    setError('');
    try {
      if (requesting) {
        setMessage(await requestPasswordReset(auth, fields.get('email'), window.location.origin));
      } else {
        await updateRecoveryPassword(auth, getSnapshot, fields.get('password'), fields.get('confirmation'));
        try {
          await closeRecoverySession(auth, getSnapshot);
        } catch {
          // The callback client keeps this session in memory until navigation.
        }
        setMessage('Password updated. Log in with your new password.');
      }
    } catch (cause) {
      setError(cause.message || 'The request could not be completed. Try again.');
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function cancel(event) {
    if (session.status !== 'ready' || requesting) return;
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    try {
      await closeRecoverySession(supabase.auth, getSnapshot);
    } catch {
      // Navigating away also discards the in-memory recovery client.
    } finally {
      window.location.replace(loginUrl);
    }
  }

  return (
    <main className="mx-auto mt-12 w-[min(90%,28rem)] space-y-4 rounded-xl bg-[#EBEBD8] p-6 text-[#455230] shadow">
      <h1 className="text-2xl font-bold">{requesting ? 'Reset your password' : 'Choose a new password'}</h1>
      {supabaseConfigError && <p role="alert">{supabaseConfigError}</p>}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      {!requesting && !message && supabase && session.status === 'checking' && <p role="status">Checking your reset link…</p>}
      {!requesting && !message && supabase && session.status === 'invalid' && (
        <p role="alert">This reset link is invalid or has expired. <a className="underline" href={forgotPasswordPath}>Request a new link</a>.</p>
      )}
      {supabase && !message && (requesting || session.status === 'ready') && (
        <form className="space-y-4" onSubmit={submit}>
          {requesting ? (
            <label className="block">Email
              <input className={fieldClass} name="email" type="email" autoComplete="email" required />
            </label>
          ) : (
            <>
              <label className="block">New password
                <input className={fieldClass} name="password" type="password" autoComplete="new-password" minLength={8} required />
              </label>
              <label className="block">Confirm new password
                <input className={fieldClass} name="confirmation" type="password" autoComplete="new-password" minLength={8} required />
              </label>
            </>
          )}
          <button className={buttonClass} type="submit" disabled={pending}>
            {pending ? 'Please wait…' : requesting ? 'Send reset link' : 'Save new password'}
          </button>
        </form>
      )}
      <a href={message && !requesting ? loginUrl + '&fresh=1' : loginUrl}
        onClick={message ? undefined : cancel} className="inline-block underline">Back to login</a>
    </main>
  );
}

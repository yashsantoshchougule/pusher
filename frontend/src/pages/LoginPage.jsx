import React, { useState, useEffect } from 'react';
import { Activity, ArrowLeft } from 'lucide-react';
import AuthFormPanel from '../components/auth/AuthFormPanel';
import { supabase, supabaseConfigError } from '../lib/supabaseClient';
import { authenticateEmail, authenticateProvider } from '../lib/signIn';

function getTimeBasedFrameData(date = new Date()) {
  const hours = date.getHours();
  const minutes = date.getMinutes();
  let frame = 1;
  let phase = 'Morning';

  if (hours >= 5 && hours < 12) {
    phase = 'Morning';
    const elapsed = (hours - 5) * 60 + minutes;
    frame = 1 + Math.min(24, Math.floor((elapsed / 420) * 25));
  } else if (hours >= 12 && hours < 17) {
    phase = 'Afternoon';
    const elapsed = (hours - 12) * 60 + minutes;
    frame = 26 + Math.min(22, Math.floor((elapsed / 300) * 23));
  } else if (hours >= 17 && hours < 20) {
    phase = 'Evening';
    const elapsed = (hours - 17) * 60 + minutes;
    frame = 49 + Math.min(27, Math.floor((elapsed / 180) * 28));
  } else {
    phase = 'Night';
    const elapsed = hours >= 20 ? (hours - 20) * 60 + minutes : (hours + 4) * 60 + minutes;
    frame = 77 + Math.min(23, Math.floor((elapsed / 540) * 24));
  }

  const paddedFrame = String(frame).padStart(3, '0');
  return {
    frame,
    phase,
    src: `/frames/ezgif-frame-${paddedFrame}.jpg`,
  };
}

export default function LoginPage({
  onBackToWebsite, canContinueOffline, onContinueOffline, sessionError, onClearSessionError,
}) {
  const [authMode, setAuthMode] = useState(() => (
    new URLSearchParams(window.location.search).get('view') === 'login' ? 'login' : 'signup'
  ));
  const [notification, setNotification] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    return params.get('error_description') || fragment.get('error_description')
      || ((params.has('error') || fragment.has('error')) ? 'Provider sign-in was canceled or failed.' : null);
  });
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [currentFrameData, setCurrentFrameData] = useState(() => getTimeBasedFrameData());

  useEffect(() => {
    const updateFrame = () => {
      setCurrentFrameData(getTimeBasedFrameData());
    };
    updateFrame();
    const interval = setInterval(updateFrame, 60000);
    return () => clearInterval(interval);
  }, []);

  const toggleAuthMode = (targetMode) => {
    if (typeof targetMode === 'string') {
      setAuthMode(targetMode);
    } else {
      setAuthMode((prev) => (prev === 'signup' ? 'login' : 'signup'));
    }
  };

  const redirectTo = window.location.origin + '/';

  const handleProviderLogin = async (provider) => {
    onClearSessionError();
    setIsGoogleLoading(true);
    try {
      await authenticateProvider(supabase?.auth, provider, redirectTo);
    } catch (error) {
      setNotification(error.message);
      setIsGoogleLoading(false);
    }
  };

  const handleFormSubmit = async (formData) => {
    onClearSessionError();
    setIsGoogleLoading(true);
    try {
      const session = await authenticateEmail(supabase?.auth, authMode, formData, redirectTo);
      setNotification(session ? 'Checking your session…' : 'Confirm your email to finish signing up.');
    } catch (error) {
      setNotification(error.message);
    } finally {
      setIsGoogleLoading(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-10 pt-5 sm:px-8 sm:pt-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={onBackToWebsite} className="inline-flex min-h-11 items-center gap-2 font-bold text-ink">
          <Activity aria-hidden="true" className="h-5 w-5" /> Pusher
        </button>
        <button type="button" onClick={onBackToWebsite} className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-muted">
          <ArrowLeft aria-hidden="true" className="h-4 w-4" /> Back to home
        </button>
      </header>
      {(sessionError || notification) && (
        <p role={sessionError ? 'alert' : 'status'} className="mb-4 rounded-xl border border-control bg-soft px-4 py-3 text-sm font-medium">
          {sessionError || notification}
        </p>
      )}
      {canContinueOffline && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-sm">
          <span className="text-muted">Local development session</span>
          <button type="button" className="min-h-11 rounded-lg bg-accent px-4 font-semibold text-accent-ink" onClick={onContinueOffline}>
            Continue offline
          </button>
        </div>
      )}
      <div id="login-card-container" className="grid overflow-hidden rounded-[1.5rem] border border-line bg-surface md:grid-cols-2">
        <div className="relative flex min-h-40 items-end overflow-hidden bg-nav px-6 py-5 text-nav-ink sm:px-9 md:min-h-full md:pb-10">
          <img src={currentFrameData.src} alt="" className="absolute inset-0 h-full w-full object-cover opacity-40" />
          <div className="relative max-w-sm">
            <Activity aria-hidden="true" className="mb-3 h-7 w-7 text-accent" />
            <p className="text-2xl font-bold tracking-tight sm:text-4xl">Load testing with clear limits.</p>
          </div>
        </div>
        <div className="min-w-0 px-5 py-6 sm:px-10 sm:py-9">
          {supabaseConfigError ? (
            <p role="alert" className="rounded-xl border border-line bg-field p-4 text-sm font-semibold">{supabaseConfigError}</p>
          ) : <AuthFormPanel
            mode={authMode}
            onToggleMode={toggleAuthMode}
            onSubmit={handleFormSubmit}
            onGoogleClick={() => handleProviderLogin('google')}
            onGitHubClick={() => handleProviderLogin('github')}
            isGoogleLoading={isGoogleLoading}
          />}
        </div>
      </div>
    </main>
  );
}

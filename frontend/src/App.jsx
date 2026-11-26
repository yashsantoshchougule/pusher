import React, { Suspense, lazy, useState, useEffect, useRef } from 'react';
import LoginPage from './pages/LoginPage';
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const WafSetupPage = lazy(() => import('./pages/WafSetupPage'));
const AccountRecoveryPage = lazy(() => import('./pages/AccountRecoveryPage'));
const TermsPage = lazy(() => import('./pages/TermsPage'));
import { forgotPasswordPath } from './lib/passwordRecovery';
import { recoveryCallback, supabase } from './lib/supabaseClient';
import { endSession, verifyOperatorSession } from './lib/signIn';
import { Activity, ArrowRight } from 'lucide-react';

const appearanceStorageKey = 'pusher_appearance';

export default function App() {
  const [appearance, setAppearance] = useState(() => {
    try {
      return window.localStorage.getItem(appearanceStorageKey) === 'dark' ? 'dark' : 'light';
    } catch {
      return 'light';
    }
  });
  const updateAppearance = (nextAppearance) => {
    setAppearance(nextAppearance);
    try {
      window.localStorage.setItem(appearanceStorageKey, nextAppearance);
    } catch {}
  };
  const path = typeof window !== 'undefined' ? window.location.pathname : '/';
  const wrap = (node) => (
    <div className="pusher-ui" data-appearance={appearance}>
      <Suspense fallback={<main className="p-6 text-sm text-muted" role="status">Loading Pusher…</main>}>
        {node}
      </Suspense>
    </div>
  );
  if (recoveryCallback) return wrap(<AccountRecoveryPage requesting={false} />);
  if (path === forgotPasswordPath) return wrap(<AccountRecoveryPage requesting />);
  if (path === '/terms') return wrap(<TermsPage />);
  return wrap(<PusherApp appearance={appearance} updateAppearance={updateAppearance} />);
}

function PusherApp({ appearance, updateAppearance }) {
  const getInitialView = () => {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const hash = window.location.hash;
      if (path === '/waf-setup' || hash === '#/waf-setup') {
        return 'waf-setup';
      }
      if (path === '/dashboard' || hash === '#/dashboard') {
        return 'dashboard';
      }
      if (path === '/website' || hash === '#/website') {
        return 'website';
      }
    }
    return 'auth'; // 'auth' | 'website' | 'dashboard' | 'waf-setup'
  };

  const [currentView, setCurrentView] = useState(getInitialView);

  const [operator, setOperator] = useState(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState(null);
  const freshLogin = useRef(typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('fresh') === '1');

  useEffect(() => {
    let sequence = 0;
    let closed = false;
    try { window.localStorage.removeItem('pusher_auth_session'); } catch {}
    async function verifySession(token = '') {
      const attempt = ++sequence;
      let identity = null;
      let error = null;
      try {
        identity = await verifyOperatorSession(token);
      } catch (cause) {
        error = cause.message;
      }
      if (closed || sequence !== attempt) return;
      setOperator(identity);
      setSessionError(error);
      setSessionReady(true);
      if (identity && !identity.offline) {
        setCurrentView((view) => view === 'auth' ? 'dashboard' : view);
      }
    }

    const subscription = supabase?.auth.onAuthStateChange((_event, session) => {
      if (freshLogin.current) {
        setSessionReady(true);
        return;
      }
      const subject = session ? `supabase:${session.user.id}` : 'offline:operator';
      setOperator((current) => current?.user_id === subject ? current : null);
      void verifySession(session?.access_token);
    });
    if (!supabase) void verifySession();
    return () => {
      closed = true;
      subscription?.data.subscription.unsubscribe();
    };
  }, []);


  useEffect(() => {
    const handleLocationChange = () => {
      const path = window.location.pathname;
      const hash = window.location.hash;
      if (path === '/waf-setup' || hash === '#/waf-setup') {
        setCurrentView('waf-setup');
      } else if (path === '/dashboard' || hash === '#/dashboard') {
        setCurrentView('dashboard');
      } else if (path === '/website' || hash === '#/website') {
        setCurrentView('website');
      } else {
        setCurrentView('auth');
      }
    };

    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('hashchange', handleLocationChange);
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('hashchange', handleLocationChange);
    };
  }, []);

  const navigateTo = (view) => {
    setCurrentView(view);
    if (typeof window !== 'undefined') {
      const targetPath =
        view === 'waf-setup'
          ? '/waf-setup'
          : view === 'dashboard'
          ? '/dashboard'
          : view === 'website'
          ? '/website'
          : '/';
      window.history.pushState(null, '', targetPath);
      window.location.hash = `#${targetPath}`;
    }
  };

  const signOut = async () => {
    if (!operator?.offline && supabase) await endSession(supabase.auth);
    setOperator(null);
    navigateTo('auth');
  };

  if (!sessionReady && currentView !== 'website') return <main>Checking access…</main>;

  if (operator && currentView === 'waf-setup') {
    return (
      <WafSetupPage
        appearance={appearance}
        onBack={() => navigateTo('dashboard')}
        onNavigate={navigateTo}
      />
    );
  }

  if (operator && currentView === 'dashboard') {
    return (
      <DashboardPage
        key={operator.user_id}
        appearance={appearance}
        onAppearanceChange={updateAppearance}
        operator={operator}
        onLogout={signOut}
        onNavigate={navigateTo}
      />
    );
  }

  if (currentView === 'website') {
    return (
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 sm:px-8">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line py-5">
          <span className="inline-flex items-center gap-2 text-lg font-bold">
            <Activity aria-hidden="true" className="h-5 w-5" /> Pusher
          </span>
          <button type="button" onClick={() => navigateTo('auth')} className="min-h-11 rounded-xl border border-control bg-surface px-4 text-sm font-semibold">
            Sign in or register
          </button>
        </header>
        <main className="my-8 flex flex-1 items-center rounded-[1.5rem] bg-nav px-6 py-12 text-nav-ink sm:px-14">
          <div className="max-w-2xl">
            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">Safe load testing for your app</h1>
            <p className="mt-5 max-w-lg leading-relaxed">Verify your target, configure traffic, and watch how your app responds as the load grows.</p>
            <button type="button" onClick={() => navigateTo('auth')} className="mt-8 inline-flex min-h-11 items-center gap-3 rounded-xl bg-accent px-5 text-sm font-bold text-accent-ink">
              Open Pusher <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </main>
      </div>
    );
  }

  // Default view is the Split-Screen Login Page
  return (
    <LoginPage
      sessionError={sessionError}
      onClearSessionError={() => {
        if (freshLogin.current) {
          freshLogin.current = false;
          const url = new URL(window.location.href);
          url.searchParams.delete('fresh');
          window.history.replaceState(null, '', url);
        }
        setSessionError(null);
      }}
      onBackToWebsite={() => navigateTo('website')}
      canContinueOffline={Boolean(operator?.offline)}
      onContinueOffline={() => navigateTo('dashboard')}
    />
  );
}

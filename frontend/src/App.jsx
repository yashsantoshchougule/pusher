import React, { useState, useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import { Shield } from 'lucide-react';

export default function App() {
  const getInitialView = () => {
    if (typeof window !== 'undefined') {
      const path = window.location.pathname;
      const hash = window.location.hash;
      if (path === '/dashboard' || hash === '#/dashboard') {
        return 'dashboard';
      }
      if (path === '/website' || hash === '#/website') {
        return 'website';
      }
    }
    return 'auth'; // 'auth' | 'website' | 'dashboard'
  };

  const [currentView, setCurrentView] = useState(getInitialView);

  useEffect(() => {
    const handleLocationChange = () => {
      const path = window.location.pathname;
      const hash = window.location.hash;
      if (path === '/dashboard' || hash === '#/dashboard') {
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
      const targetPath = view === 'dashboard' ? '/dashboard' : view === 'website' ? '/website' : '/';
      window.history.pushState(null, '', targetPath);
    }
  };

  if (currentView === 'dashboard') {
    return <DashboardPage onLogout={() => navigateTo('auth')} />;
  }

  if (currentView === 'website') {
    return (
      <div className="min-h-screen bg-[#E8E5DF] text-[#2F2C27] flex flex-col font-sans">
        {/* Navigation Bar - Borderless */}
        <header className="bg-[#E8E5DF] px-8 py-5 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-black tracking-wider text-[#2F2C27]">
              PUSHER
            </span>
          </div>
          <button
            onClick={() => navigateTo('auth')}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-bold rounded-xl bg-[#968F83] hover:bg-[#857E72] text-[#E8E5DF] transition-colors shadow-sm"
          >
            <span>Sign In / Register</span>
          </button>
        </header>

        {/* Hero Preview - Borderless */}
        <main className="flex-1 flex flex-col items-center justify-center p-6 text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#E8E5DF] border border-[#968F83]/30 shadow-sm text-xs font-bold text-[#2F2C27] mb-6">
            <Shield className="w-4 h-4 text-[#968F83]" />
            <span>Enterprise-Grade Safe Load Testing</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-black tracking-tight mb-4 text-[#2F2C27]">
            Safe Load Testing, Zero Crash Surprises
          </h1>
          <p className="text-base text-[#2F2C27]/80 max-w-xl mb-8 font-medium">
            High-performance asynchronous load testing designed to verify server capacity under extreme traffic without overwhelming memory.
          </p>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigateTo('auth')}
              className="px-6 py-3 rounded-xl bg-[#968F83] hover:bg-[#857E72] font-bold text-sm text-[#E8E5DF] transition-all shadow-md"
            >
              Get Started Now
            </button>
            <button
              onClick={() => navigateTo('auth')}
              className="px-6 py-3 rounded-xl bg-[#E8E5DF] hover:bg-white border border-[#968F83]/30 font-bold text-sm text-[#2F2C27] transition-all shadow-md"
            >
              Sign In to Console
            </button>
          </div>
        </main>
      </div>
    );
  }

  // Default view is the Split-Screen Login Page
  return (
    <LoginPage
      onBackToWebsite={() => navigateTo('website')}
      onLoginSuccess={() => navigateTo('dashboard')}
    />
  );
}

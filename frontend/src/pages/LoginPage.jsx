import React, { useState, useEffect } from 'react';
import AuthVisualPanel from '../components/auth/AuthVisualPanel';
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
  const [scale, setScale] = useState(0.72);
  const [currentFrameData, setCurrentFrameData] = useState(() => getTimeBasedFrameData());

  // Proportional 2.06:1 Card Scaling (1320px × 640px Base Canvas)
  useEffect(() => {
    const CARD_W = 1320;
    const CARD_H = 640; // Exact 2.0625:1 wide ratio

    const computeScale = () => {
      if (typeof window === 'undefined') return 1;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      // Fill 70% of screen width on PC & Laptop (slightly smaller than 77%),
      // and 88% on narrower Tablets so text stays crisp while keeping the exact same ratio.
      const widthFill = vw < 1024 ? 0.88 : 0.70;
      const heightFill = 0.76;
      return Math.min((vw * widthFill) / CARD_W, (vh * heightFill) / CARD_H);
    };

    const updateScale = () => {
      setScale(Math.max(0.35, computeScale()));
    };

    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, []);

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
    <div className="h-screen min-h-screen w-full bg-[#EBEBD8] flex items-center justify-center overflow-hidden font-sans selection:bg-[#455230] selection:text-[#EBEBD8] relative p-0 m-0">
      {/* Toast Notification in Deep Army Olive & Cream - Borderless */}
      {(sessionError || notification) && (
        <div role={sessionError ? 'alert' : 'status'} className="fixed top-6 z-50 animate-bounce bg-[#455230] text-[#EBEBD8] px-5 py-2.5 rounded-full text-sm font-bold shadow-2xl">
          {sessionError || notification}
        </div>
      )}

      {canContinueOffline && (
        <button type="button" className="absolute z-10 top-4 right-4 rounded bg-[#455230] px-3 py-2 text-white" onClick={onContinueOffline}>
          Continue offline
        </button>
      )}

      {/* Main Canonical Fixed Dimension Login Card (1320px × 640px, Proportional 2.06:1 Ratio) */}
      <div
        id="login-card-container"
        style={{
          width: '1320px',
          minWidth: '1320px',
          maxWidth: '1320px',
          height: '640px',
          minHeight: '640px',
          maxHeight: '640px',
          flexShrink: 0,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          borderRadius: '24px',
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
        }}
        className="bg-[#9BA685] rounded-[24px] shadow-[0_20px_60px_-15px_rgba(69,82,48,0.35)] overflow-hidden grid grid-cols-2 shrink-0 select-none transition-transform duration-100 ease-out"
      >
        {/* Left Column (50% Width = 660px): Dynamic 100-Frame Synchronized Landscape */}
        <div className="w-[660px] h-[640px] p-4 flex flex-col justify-center overflow-hidden">
          <div className="relative w-full h-full overflow-hidden rounded-2xl bg-black/20">
            <img
              src={currentFrameData.src}
              alt={currentFrameData.phase}
              className="absolute inset-0 w-full h-full object-cover object-center select-none transition-all duration-700"
              style={{
                imageRendering: 'auto',
              }}
            />
            {/* Soft atmospheric smoothing layer */}
            <div className="absolute inset-0 bg-gradient-to-b from-amber-50/15 via-transparent to-black/20 pointer-events-none mix-blend-soft-light" />
            {/* Subtle bottom-only vignette */}
            <div className="absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/30 to-transparent pointer-events-none" />
            <AuthVisualPanel />
          </div>
        </div>

        {/* Right Column (50% Width = 660px): Fixed Form Panel */}
        <div className="w-[660px] h-[640px] flex flex-col justify-center bg-[#9BA685] overflow-hidden">
          {supabaseConfigError ? (
            <p role="alert" className="px-14 text-lg font-semibold text-[#455230]">{supabaseConfigError}</p>
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
    </div>
  );
}

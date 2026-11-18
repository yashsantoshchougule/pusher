import React, { useState, useEffect } from 'react';
import AuthVisualPanel from '../components/auth/AuthVisualPanel';
import AuthFormPanel from '../components/auth/AuthFormPanel';

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

export default function LoginPage({ onBackToWebsite, onLoginSuccess }) {
  const [authMode, setAuthMode] = useState('signup'); // 'signup' | 'login'
  const [notification, setNotification] = useState(null);
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

  const handleFormSubmit = (formData) => {
    const email = formData.email || 'operator@pusher.internal';
    const fullName = [formData.firstName, formData.lastName].filter(Boolean).join(' ') || (authMode === 'signup' ? 'Test Operator' : 'Account Operator');
    const userId = 'usr_' + (email.split('@')[0] || 'operator').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();

    // Preserve authenticated session in storage for dashboard multi-account isolation
    try {
      localStorage.setItem('pusher_auth_session', JSON.stringify({
        access_token: 'tok_' + Date.now(),
        user: {
          user_id: userId,
          email: email,
          full_name: fullName
        }
      }));
    } catch (e) {}

    const action = authMode === 'signup' ? 'Account created' : 'Logged in';
    setNotification(`${action} successfully! Welcome, ${formData.firstName || formData.email || 'User'}. Redirecting to dashboard...`);
    setTimeout(() => {
      setNotification(null);
      if (onLoginSuccess) {
        onLoginSuccess();
      }
    }, 600);
  };

  return (
    <div className="min-h-screen w-full bg-[#EBEBD8] flex flex-col items-center justify-center p-3 sm:p-5 md:p-6 lg:p-8 font-sans selection:bg-[#455230] selection:text-[#EBEBD8]">
      {/* Toast Notification in Deep Army Olive & Cream - Borderless */}
      {notification && (
        <div className="fixed top-6 z-50 animate-bounce bg-[#455230] text-[#EBEBD8] px-5 py-2.5 rounded-full text-sm sm:text-base font-bold shadow-2xl">
          {notification}
        </div>
      )}

      {/* Main Split-Screen Card Container - Fluid Adaptive Scaling */}
      <div className="w-full max-w-[1200px] xl:max-w-[1360px] 2xl:max-w-[1480px] bg-[#9BA685] rounded-[24px] sm:rounded-[32px] shadow-[0_20px_60px_-15px_rgba(69,82,48,0.35)] overflow-hidden grid grid-cols-1 lg:grid-cols-12 min-h-0 h-auto lg:h-[min(700px,90vh)] transition-all duration-300">
        {/* Left Column: 10px Margin Inset Around Dynamic Background Image */}
        <div className="lg:col-span-6 order-1 lg:order-1 p-2 sm:p-2.5 flex flex-col justify-center h-full min-h-[220px] sm:min-h-[280px] lg:min-h-0">
          <div className="relative w-full h-full min-h-[220px] sm:min-h-[280px] lg:min-h-0 overflow-hidden rounded-[18px] sm:rounded-[22px]">
            <img
              src={currentFrameData.src}
              alt={currentFrameData.phase}
              className="absolute inset-0 w-full h-full object-cover object-center select-none transition-all duration-700"
              style={{
                imageRendering: 'auto',
              }}
            />
            {/* Soft atmospheric smoothing layer to diffuse compression banding in the sky and mist */}
            <div className="absolute inset-0 bg-gradient-to-b from-amber-50/15 via-transparent to-black/20 pointer-events-none mix-blend-soft-light" />
            {/* Subtle bottom-only vignette so the foreground remains grounded */}
            <div className="absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-black/30 to-transparent pointer-events-none" />
            <AuthVisualPanel />
          </div>
        </div>

        {/* Right Column: Soft Sage Green for the "Create an account" form */}
        <div className="lg:col-span-6 order-2 lg:order-2 flex flex-col justify-center bg-[#9BA685] h-full overflow-y-auto">
          <AuthFormPanel
            mode={authMode}
            onToggleMode={toggleAuthMode}
            onSubmit={handleFormSubmit}
          />
        </div>
      </div>
    </div>
  );
}

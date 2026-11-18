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
    <div className="min-h-dvh w-full bg-[#031716] flex flex-col items-center justify-center p-2 sm:p-4 md:p-6 lg:p-8 font-sans selection:bg-[#0C969C] selection:text-[#031716] overflow-y-auto">
      {/* Toast Notification in Teal Palette - Borderless */}
      {notification && (
        <div className="fixed top-4 z-50 animate-bounce bg-[#0C969C] text-[#031716] px-4 py-2 sm:px-5 sm:py-2.5 rounded-full text-xs sm:text-sm md:text-base font-bold shadow-2xl">
          {notification}
        </div>
      )}

      {/* Main Split-Screen Card Container - Fluid Adaptive Scaling across Tablet, Laptop & Monitor */}
      <div className="w-full max-w-[420px] md:max-w-[760px] lg:max-w-[920px] xl:max-w-[1000px] my-auto bg-[#032F30] rounded-[20px] sm:rounded-[26px] md:rounded-[28px] shadow-[0_20px_60px_-15px_rgba(3,23,22,0.9)] border border-[#0A7075]/30 overflow-hidden grid grid-cols-1 md:grid-cols-12 min-h-0 h-auto md:h-auto lg:h-[min(590px,88vh)] max-h-[94vh] transition-all duration-300">
        {/* Left Column: Adaptive Margin Inset Around Dynamic Background Image */}
        <div className="md:col-span-5 lg:col-span-6 order-1 md:order-1 p-2 sm:p-2.5 flex flex-col justify-center h-full min-h-[160px] sm:min-h-[200px] md:min-h-0">
          <div className="relative w-full h-full min-h-[160px] sm:min-h-[200px] md:min-h-0 overflow-hidden rounded-[16px] sm:rounded-[20px]">
            <img
              src={currentFrameData.src}
              alt={currentFrameData.phase}
              className="absolute inset-0 w-full h-full object-cover object-center select-none transition-all duration-700"
              style={{
                imageRendering: 'auto',
              }}
            />
            {/* Soft atmospheric smoothing layer to diffuse compression banding in the sky and mist */}
            <div className="absolute inset-0 bg-gradient-to-b from-[#274D60]/20 via-transparent to-[#031716]/60 pointer-events-none mix-blend-soft-light" />
            {/* Subtle bottom-only vignette so the foreground remains grounded */}
            <div className="absolute inset-x-0 bottom-0 h-1/4 bg-gradient-to-t from-[#031716]/80 to-transparent pointer-events-none" />
            <AuthVisualPanel />
          </div>
        </div>

        {/* Right Column: Deep Forest Teal for the "Create an account" form */}
        <div className="md:col-span-7 lg:col-span-6 order-2 md:order-2 flex flex-col justify-center bg-[#032F30] h-full overflow-y-auto">
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

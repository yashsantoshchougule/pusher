import React, { useState } from 'react';
import { Eye, EyeOff, Check } from 'lucide-react';

export default function AuthFormPanel({ mode = 'signup', onToggleMode, onSubmit }) {
  const [showPassword, setShowPassword] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(true);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    rememberMe: true,
  });

  const isSignUp = mode === 'signup';

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) {
      onSubmit(formData);
    }
  };

  return (
    <div className="w-full h-full flex flex-col justify-center px-6 py-5 sm:px-8 sm:py-6 lg:px-9 lg:py-6 max-w-[440px] mx-auto bg-[#9BA685] text-[#455230]">
      {/* 2-Option Segmented Control: Log In / Sign Up with 1px Margin */}
      <div className="relative flex p-[1px] rounded-xl bg-[#EBEBD8]/60 backdrop-blur-sm mb-4 sm:mb-5 border-0 shadow-inner">
        {/* Sliding active indicator pill with 1px margin */}
        <div
          className={`absolute top-[1px] bottom-[1px] w-[calc(50%-1px)] rounded-[11px] bg-[#455230] shadow-md transition-all duration-300 ease-in-out ${
            isSignUp ? 'left-[calc(50%+0.5px)]' : 'left-[1px]'
          }`}
        />

        {/* Tab 1: Log In */}
        <button
          type="button"
          onClick={() => onToggleMode && onToggleMode('login')}
          className={`relative z-10 flex-1 py-2 sm:py-2.5 text-center text-sm sm:text-base font-bold transition-colors duration-200 cursor-pointer select-none ${
            !isSignUp ? 'text-[#EBEBD8]' : 'text-[#455230] hover:text-black'
          }`}
        >
          Log In
        </button>

        {/* Tab 2: Sign Up */}
        <button
          type="button"
          onClick={() => onToggleMode && onToggleMode('signup')}
          className={`relative z-10 flex-1 py-2 sm:py-2.5 text-center text-sm sm:text-base font-bold transition-colors duration-200 cursor-pointer select-none ${
            isSignUp ? 'text-[#EBEBD8]' : 'text-[#455230] hover:text-black'
          }`}
        >
          Sign Up
        </button>
      </div>

      {/* Header Section with comfortable spacing */}
      <div className="mb-3 sm:mb-4">
        <h1 className="text-2xl sm:text-3xl lg:text-[32px] font-black tracking-tight text-[#455230] transition-all duration-300">
          {isSignUp ? 'Create an account' : 'Welcome back'}
        </h1>
      </div>

      {/* Main Authentication Form */}
      <form onSubmit={handleSubmit} autoComplete="off" className="space-y-2.5 sm:space-y-3">
        {/* Name Fields (Shown smoothly in Sign Up mode) */}
        <div
          className={`grid grid-cols-2 gap-3 transition-all duration-300 overflow-hidden ${
            isSignUp ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0 pointer-events-none'
          }`}
        >
          <div>
            <input
              id="firstName"
              name="firstName"
              type="text"
              autoComplete="off"
              required={isSignUp}
              value={formData.firstName}
              onChange={handleChange}
              placeholder="First name"
              className="w-full bg-[#EBEBD8] focus:outline-none focus:ring-2 focus:ring-[#455230]/40 rounded-xl px-3.5 py-2.5 sm:py-3 text-sm sm:text-base text-[#455230] placeholder-[#637545]/70 transition-all shadow-sm font-medium border-0"
            />
          </div>
          <div>
            <input
              id="lastName"
              name="lastName"
              type="text"
              autoComplete="off"
              value={formData.lastName}
              onChange={handleChange}
              placeholder="Last name"
              className="w-full bg-[#EBEBD8] focus:outline-none focus:ring-2 focus:ring-[#455230]/40 rounded-xl px-3.5 py-2.5 sm:py-3 text-sm sm:text-base text-[#455230] placeholder-[#637545]/70 transition-all shadow-sm font-medium border-0"
            />
          </div>
        </div>

        {/* Email Field */}
        <div>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="off"
            required
            value={formData.email}
            onChange={handleChange}
            placeholder="Email"
            className="w-full bg-[#EBEBD8] focus:outline-none focus:ring-2 focus:ring-[#455230]/40 rounded-xl px-3.5 py-2.5 sm:py-3 text-sm sm:text-base text-[#455230] placeholder-[#637545]/70 transition-all shadow-sm font-medium border-0"
          />
        </div>

        {/* Password Field with Toggle */}
        <div className="relative">
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            value={formData.password}
            onChange={handleChange}
            placeholder="Enter your password"
            className="w-full bg-[#EBEBD8] focus:outline-none focus:ring-2 focus:ring-[#455230]/40 rounded-xl pl-3.5 pr-10 py-2.5 sm:py-3 text-sm sm:text-base text-[#455230] placeholder-[#637545]/70 transition-all shadow-sm font-medium border-0"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#455230] hover:text-black transition-colors cursor-pointer p-1"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <EyeOff className="w-4 h-4 sm:w-4.5 sm:h-4.5 stroke-[2.5]" />
            ) : (
              <Eye className="w-4 h-4 sm:w-4.5 sm:h-4.5 stroke-[2.5]" />
            )}
          </button>
        </div>

        {/* Terms or Remember Me Checkbox */}
        <div className="flex items-center justify-between pt-0.5">
          {isSignUp ? (
            <label className="flex items-center gap-2 text-xs sm:text-sm text-[#455230] cursor-pointer select-none font-medium">
              <div
                onClick={() => setAgreedToTerms(!agreedToTerms)}
                className={`w-4 h-4 sm:w-4.5 sm:h-4.5 rounded flex items-center justify-center transition-all ${
                  agreedToTerms
                    ? 'bg-[#455230] text-[#EBEBD8] shadow-sm'
                    : 'bg-[#EBEBD8]'
                }`}
              >
                {agreedToTerms && <Check className="w-3 h-3 stroke-[3]" />}
              </div>
              <span>
                I agree to the{' '}
                <a href="#terms" className="text-[#455230] underline font-bold hover:text-black transition-colors">
                  Terms & Conditions
                </a>
              </span>
            </label>
          ) : (
            <>
              <label
                onClick={() =>
                  setFormData((prev) => ({ ...prev, rememberMe: !prev.rememberMe }))
                }
                className="flex items-center gap-2 text-xs sm:text-sm text-[#455230] cursor-pointer select-none font-medium"
              >
                <div
                  className={`w-4 h-4 sm:w-4.5 sm:h-4.5 rounded flex items-center justify-center transition-all ${
                    formData.rememberMe
                      ? 'bg-[#455230] text-[#EBEBD8] shadow-sm'
                      : 'bg-[#EBEBD8]'
                  }`}
                >
                  {formData.rememberMe && <Check className="w-3 h-3 stroke-[3]" />}
                </div>
                <span className="text-[#455230] font-bold">Remember me</span>
              </label>
              <a href="#forgot" className="text-xs sm:text-sm text-[#455230] underline font-bold hover:text-black">
                Forgot password?
              </a>
            </>
          )}
        </div>

        {/* Primary CTA Action Button */}
        <button
          type="submit"
          className="w-full mt-2.5 sm:mt-3 py-2.5 sm:py-3 px-6 rounded-xl bg-[#455230] hover:bg-[#364126] active:scale-[0.99] text-[#EBEBD8] font-black text-sm sm:text-base shadow-lg shadow-[#455230]/25 transition-all duration-200 cursor-pointer flex items-center justify-center tracking-wide border-0"
        >
          {isSignUp ? 'Create account' : 'Log in'}
        </button>

        {/* Toggle Mode Link Below CTA */}
        <p className="text-center text-xs sm:text-sm text-[#455230]/85 font-medium pt-1">
          {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
          <button
            type="button"
            onClick={onToggleMode}
            className="text-[#455230] hover:text-black underline font-bold transition-colors cursor-pointer ml-1"
          >
            {isSignUp ? 'Log in' : 'Sign up'}
          </button>
        </p>
      </form>

      {/* Divider */}
      <div className="relative my-3 sm:my-3.5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full h-[1px] bg-[#455230]/20" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="bg-[#9BA685] px-3 text-[#455230] font-bold">
            {isSignUp ? 'Or register with' : 'Or log in with'}
          </span>
        </div>
      </div>

      {/* Social SSO Buttons */}
      <div className="space-y-2.5">
        {/* Row 1: Google and Apple side-by-side */}
        <div className="grid grid-cols-2 gap-2.5 sm:gap-3">
          {/* Google SSO Button */}
          <button
            type="button"
            className="flex items-center justify-center gap-2 px-3 py-2 sm:py-2.5 rounded-xl bg-[#EBEBD8] hover:bg-white text-xs sm:text-sm font-bold text-[#455230] transition-all cursor-pointer shadow-sm hover:shadow border-0"
          >
            <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Google</span>
          </button>

          {/* Apple SSO Button */}
          <button
            type="button"
            className="flex items-center justify-center gap-2 px-3 py-2 sm:py-2.5 rounded-xl bg-[#EBEBD8] hover:bg-white text-xs sm:text-sm font-bold text-[#455230] transition-all cursor-pointer shadow-sm hover:shadow border-0"
          >
            <svg className="w-4 h-4 fill-[#455230] shrink-0" viewBox="0 0 170 170">
              <path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.7-3.04-7.69-7.85-11.97-14.42-6.19-9.59-11.05-20.91-14.58-33.97-3.53-13.06-5.3-25.04-5.3-35.94 0-16.14 4.17-29.23 12.51-39.26 8.34-10.03 18.77-15.11 31.29-15.24 4.8 0 10.15 1.25 16.06 3.75 5.91 2.5 9.77 3.86 11.59 4.08 1.95-.22 5.99-1.63 12.13-4.24 6.13-2.61 11.45-3.8 15.96-3.59 12.24.87 22.37 5.76 30.39 14.67-10.88 6.54-16.21 15.68-15.99 27.42.22 9.36 3.86 17.15 10.92 23.37 7.07 6.21 15.35 9.73 24.84 10.54-2.17 6.53-4.73 12.83-7.68 18.9zM119.22 31.78c-.22-5.44 1.74-10.87 5.87-16.3 4.13-5.43 9.35-9.35 15.65-11.74.43 5.43-1.41 10.87-5.54 16.3-4.13 5.43-9.46 9.35-15.98 11.74z" />
            </svg>
            <span>Apple</span>
          </button>
        </div>

        {/* Row 2: GitHub on its own separate line */}
        <button
          type="button"
          className="w-full flex items-center justify-center gap-2 px-3 py-2 sm:py-2.5 rounded-xl bg-[#EBEBD8] hover:bg-white text-xs sm:text-sm font-bold text-[#455230] transition-all cursor-pointer shadow-sm hover:shadow border-0"
        >
          <svg className="w-4 h-4 fill-[#455230] shrink-0" viewBox="0 0 24 24">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
            />
          </svg>
          <span>GitHub</span>
        </button>
      </div>
    </div>
  );
}

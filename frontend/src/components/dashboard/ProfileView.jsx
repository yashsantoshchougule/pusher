import React, { useState, useEffect } from 'react';
import {
  User,
  Shield,
  Save,
  RotateCcw,
  CheckCircle2,
  HardDrive,
  Cpu,
  Github,
  Building,
  Mail,
  Fingerprint,
  Clock,
  Sparkles,
  ExternalLink,
  Sliders,
  LogOut,
  ArrowRight,
  KeyRound,
  Moon
} from 'lucide-react';

export default function ProfileView({
  profile,
  onSaveProfile,
  appearance = 'light',
  onAppearanceChange,
  deviceId = 'DEV-LOCAL-CREATOR',
  themeMode = 'production',
  setActiveNav,
  onLogout,
  operator,
  onNavigate,
}) {
  const [formData, setFormData] = useState({
    full_name: '',
    username: '',
    email: '',
    role_title: '',
    organization: '',
    github_username: '',
    avatar_url: '',
    bio_notes: '',
    default_ram_ceiling_mb: 500,
  });

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [avatarError, setAvatarError] = useState(false);
  const [signOutError, setSignOutError] = useState('');
  const signedIn = operator && !operator.offline;
  const darkAppearance = appearance === 'dark';

  useEffect(() => {
    if (profile) {
      setFormData({
        full_name: profile.full_name || '',
        username: profile.username || '',
        email: profile.email || '',
        role_title: profile.role_title || '',
        organization: profile.organization || '',
        github_username: profile.github_username || '',
        avatar_url: profile.avatar_url || '',
        bio_notes: profile.bio_notes || '',
        default_ram_ceiling_mb: profile.default_ram_ceiling_mb || 500,
      });
      setAvatarError(false);
    }
  }, [profile]);

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: (type === 'number' || type === 'range') ? (parseInt(value, 10) || 50) : value,
    }));
    setSaveSuccess(false);
    setSaveError('');
  };

  const handleReset = () => {
    if (profile) {
      setFormData({
        full_name: profile.full_name || '',
        username: profile.username || '',
        email: profile.email || '',
        role_title: profile.role_title || '',
        organization: profile.organization || '',
        github_username: profile.github_username || '',
        avatar_url: profile.avatar_url || '',
        bio_notes: profile.bio_notes || '',
        default_ram_ceiling_mb: profile.default_ram_ceiling_mb || 500,
      });
      setSaveSuccess(false);
      setSaveError('');
      setAvatarError(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    setSaveError('');
    try {
      await onSaveProfile(formData);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } catch (error) {
      setSaveError(error?.message || 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = async () => {
    try {
      setSignOutError('');
      await onLogout();
    } catch (error) {
      setSignOutError(error.message);
    }
  };

  const handleLogIn = () => {
    if (onNavigate) {
      onNavigate('auth');
    } else {
      window.location.hash = '#/';
    }
  };

  // Derive user initials for fallback avatar
  const getInitials = () => {
    if (formData.full_name && formData.full_name.trim()) {
      const parts = formData.full_name.trim().split(/\s+/);
      if (parts.length > 1) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      }
      return formData.full_name.trim().slice(0, 2).toUpperCase();
    }
    if (formData.username && formData.username.trim()) {
      return formData.username.trim().slice(0, 2).toUpperCase();
    }
    return 'PU';
  };

  return (
    <div className="space-y-6">
      {/* View Header Banner */}
      <div className="flex flex-col justify-between gap-4 border-b border-line pb-5 md:flex-row md:items-center">
        <div>
          <h1 className="ui-page-title">Profile</h1>
          <p className="mt-1 text-sm text-muted">Manage your account, appearance, and default run settings.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 md:shrink-0">
          <button
            type="button"
            role="switch"
            aria-checked={darkAppearance}
            onClick={() => onAppearanceChange(darkAppearance ? 'light' : 'dark')}
            className="inline-flex items-center gap-2 border border-line px-3 py-1.5 text-xs font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
          >
            <Moon aria-hidden="true" className="h-3.5 w-3.5" />
            <span>Dark mode</span>
            <span aria-hidden="true" className={`relative h-4 w-8 rounded-full ${darkAppearance ? 'bg-primary' : 'bg-soft'}`}>
              <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-[#fff] shadow-sm transition-transform motion-reduce:transition-none ${darkAppearance ? 'translate-x-4' : ''}`} />
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveNav && setActiveNav('dashboard')}
            className="border border-line px-3 py-1.5 text-xs font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {saveSuccess && (
        <div className="border border-line p-3.5 bg-emerald-100 text-emerald-950 font-bold text-xs uppercase flex items-center justify-between shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] animate-fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-700" />
            <span>Profile successfully persisted to SQLite database!</span>
          </div>
          <span className="text-[10px] opacity-75">UPDATED AT {new Date().toLocaleTimeString()}</span>
        </div>
      )}

      {/* 2-Column Responsive Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* LEFT COLUMN: Identity Preview & Hardware Lock Card (4 cols) */}
        <div className="lg:col-span-4 space-y-6">

          {/* Profile Card */}
          <div className="ui-outline border border-line p-5 bg-surface shadow-lg space-y-5">
            <div className="flex items-start gap-4">
              {/* Avatar Image or Fallback Initials */}
              <div className="w-16 h-16 border border-line rounded-none shrink-0 overflow-hidden bg-primary text-white flex items-center justify-center font-black text-xl select-none shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                {formData.avatar_url && !avatarError ? (
                  <img
                    src={formData.avatar_url}
                    alt={formData.full_name || 'Avatar'}
                    onError={() => setAvatarError(true)}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <span>{getInitials()}</span>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h2 className="text-base font-black uppercase truncate">
                  {formData.full_name || 'Anonymous Architect'}
                </h2>
                <div className="text-xs text-muted font-bold truncate">
                  @{formData.username || 'pusher_operator'}
                </div>
                <div className="mt-1 inline-block border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase bg-soft truncate max-w-full">
                  {formData.role_title || 'Load Test Engineer'}
                </div>
              </div>
            </div>

            {/* Bio / Hardware Notes */}
            <div className="border-t border-line pt-3">
              <span className="text-[10px] font-bold uppercase text-muted block mb-1">
                ENGINEER BIO / SPECS:
              </span>
              <p className="text-xs text-muted font-normal leading-relaxed whitespace-pre-wrap bg-field p-2.5 border border-line/40 min-h-[60px]">
                {formData.bio_notes || 'No operator bio provided.'}
              </p>
            </div>

            {/* Quick Metadata List */}
            <div className="border-t border-line pt-3 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted flex items-center gap-1.5 font-bold">
                  <Mail className="w-3.5 h-3.5" /> Email:
                </span>
                <span className="font-mono truncate max-w-[160px] text-right font-bold" title={formData.email}>
                  {formData.email || 'dev@pusher.internal'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted flex items-center gap-1.5 font-bold">
                  <Building className="w-3.5 h-3.5" /> Org:
                </span>
                <span className="font-mono truncate max-w-[160px] text-right font-bold">
                  {formData.organization || 'Independent'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted flex items-center gap-1.5 font-bold">
                  <Github className="w-3.5 h-3.5" /> GitHub:
                </span>
                {formData.github_username ? (
                  <a
                    href={`https://github.com/${formData.github_username.replace(/^@/, '')}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-teal-800 hover:underline flex items-center gap-1 font-bold"
                  >
                    <span>@{formData.github_username.replace(/^@/, '')}</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                ) : (
                  <span className="font-mono text-muted">None</span>
                )}
              </div>
            </div>

            {/* Telemetry Hardware Badges */}
            <div className="border-t border-line pt-3 space-y-2">
              <div className="border border-line p-2 bg-field flex items-center justify-between text-xs">
                <span className="font-bold flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5" /> Default RAM Limit:
                </span>
                <span className="font-mono font-black text-sm bg-primary text-white px-2 py-0.5">
                  {formData.default_ram_ceiling_mb} MB
                </span>
              </div>

              <div className="border border-line p-2 bg-field flex items-center justify-between text-xs">
                <span className="font-bold flex items-center gap-1.5">
                  <Fingerprint className="w-3.5 h-3.5" /> Device Lock:
                </span>
                <span className="font-mono text-[11px] truncate max-w-[130px] font-bold" title={deviceId}>
                  {deviceId}
                </span>
              </div>

              {profile?.updated_at && (
                <div className="text-[10px] text-muted font-mono text-right">
                  Synced: {profile.updated_at}
                </div>
              )}
            </div>
          </div>

          {/* Dedicated ACCOUNT SESSION & ACCESS Card */}
          <div className="ui-outline border border-line p-4 sm:p-5 bg-surface shadow-lg space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-2.5">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-ink" />
                <span className="text-xs font-black uppercase tracking-wider text-ink">
                  ACCOUNT SESSION &amp; ACCESS
                </span>
              </div>
              {signedIn ? (
                <span className={`px-2 py-0.5 text-[10px] font-black uppercase border border-line ${
                  themeMode === 'production' ? 'bg-emerald-600 text-white' : 'bg-primary text-white'
                }`}>
                  SESSION: AUTHENTICATED
                </span>
              ) : (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase border border-line bg-soft text-ink">
                  SESSION: NOT SIGNED IN
                </span>
              )}
            </div>

            {signedIn ? (
              <div className="space-y-3">
                <div className="bg-field border border-line/40 p-2.5 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-muted">SIGNED IN AS:</span>
                    <span className="font-mono font-bold truncate max-w-[170px]" title={operator.email || formData.email}>
                      {operator.email || formData.email || 'operator@pusher.internal'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-[11px]">
                    <span className="font-bold text-muted">USER ID:</span>
                    <span className="font-mono opacity-80 truncate max-w-[170px]" title={profile?.user_key}>
                      {profile?.user_key || 'default_user'}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-2 pt-1">
                  {signOutError && <p role="alert">{signOutError}</p>}
                  <button
                    type="button"
                    onClick={handleSignOut}
                    className="w-full border border-line px-3 py-2 text-xs font-black uppercase bg-red-600 text-white hover:bg-red-700 transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>[ SIGN OUT ]</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleSignOut}
                    className="w-full ui-outline border border-line px-3 py-2 text-xs font-black uppercase bg-surface text-ink hover:bg-primary hover:text-white transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                  >
                    <span>[ LOG IN WITH ANOTHER ACCOUNT → ]</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-muted font-normal leading-relaxed bg-field p-2.5 border border-line/40">
                  Operating in local workstation mode with default system privileges. Sign in to synchronize test runs and multi-account configs.
                </p>
                <button
                  type="button"
                  onClick={handleLogIn}
                  className={`w-full border border-line px-4 py-2.5 text-xs font-black uppercase transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${
                    themeMode === 'production' ? 'bg-primary text-white hover:bg-primary-hover' : 'bg-primary text-white hover:bg-primary-hover'
                  }`}
                >
                  <span>[ LOG IN / SIGN UP → ]</span>
                </button>
              </div>
            )}
          </div>

          {/* Platform Invariants Notice Card */}
          <div className="ui-outline border border-line p-4 bg-surface shadow-lg space-y-2 text-xs">
            <div className="font-black uppercase flex items-center gap-1.5 text-ink">
              <Shield className="w-4 h-4" /> Hardened Invariants
            </div>
            <ul className="text-[11px] text-muted space-y-1 list-disc list-inside font-normal">
              <li>RAM Base Overhead: <span className="font-bold">50 MB</span></li>
              <li>Virtual User Cost: <span className="font-bold">0.20 MB / VU</span></li>
              <li>Rate Limit Bypass: <span className="font-bold">HMAC-SHA256 Signed</span></li>
              <li>Tripwire Burn Threshold: <span className="font-bold">Permanent SQLite Lock</span></li>
            </ul>
          </div>
        </div>

        {/* RIGHT COLUMN: Edit Profile Form (8 cols) */}
        <div className="lg:col-span-8">
          <form
            onSubmit={handleSubmit}
            className="ui-outline border border-line p-5 sm:p-6 bg-surface shadow-lg space-y-5"
          >
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <User className="w-5 h-5" />
                <h2 className="text-base sm:text-lg font-black uppercase tracking-tight">
                  Edit Profile Information
                </h2>
              </div>
              <span className="text-[11px] font-bold text-muted uppercase">
                * All changes saved to SQLite
              </span>
            </div>

            {/* Row 1: Full Name & Username */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  Full Name:
                </label>
                <input
                  type="text"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  placeholder="e.g. Yash Chougule"
                  className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  Username:
                </label>
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  placeholder="e.g. pusher_lead"
                  className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                />
              </div>
            </div>

            {/* Row 2: Email & Role Title */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  Email Address:
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="e.g. engineer@pusher.internal"
                  className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  Role / Title:
                </label>
                <input
                  type="text"
                  name="role_title"
                  value={formData.role_title}
                  onChange={handleChange}
                  placeholder="e.g. Principal Performance Architect"
                  className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                />
              </div>
            </div>

            {/* Row 3: Organization & GitHub Username */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  Organization / Team:
                </label>
                <input
                  type="text"
                  name="organization"
                  value={formData.organization}
                  onChange={handleChange}
                  placeholder="e.g. Pusher Ops Core"
                  className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  GitHub Handle:
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-xs font-mono text-muted select-none">
                    @
                  </span>
                  <input
                    type="text"
                    name="github_username"
                    value={formData.github_username.replace(/^@/, '')}
                    onChange={handleChange}
                    placeholder="github-username"
                    className="w-full ui-outline border border-line p-2.5 pl-7 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
                  />
                </div>
              </div>
            </div>

            {/* Row 4: Avatar Image URL */}
            <div className="space-y-1.5">
              <label className="text-xs font-black uppercase tracking-wider block flex items-center justify-between">
                <span>Avatar Image URL:</span>
                <span className="text-[10px] font-normal normal-case text-muted">
                  (HTTPS image or leave blank for initials)
                </span>
              </label>
              <input
                type="url"
                name="avatar_url"
                value={formData.avatar_url}
                onChange={handleChange}
                placeholder="https://images.unsplash.com/... or https://github.com/username.png"
                className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
              />
            </div>

            {/* Row 5: Hardware Default RAM Ceiling Slider / Input */}
            <div className="border border-line p-4 bg-field space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-ink" />
                  <label className="text-xs font-black uppercase tracking-wider">
                    Default RAM Limit Ceiling (MB):
                  </label>
                </div>
                <span className="font-mono text-xs font-black bg-primary text-white px-2.5 py-0.5">
                  {formData.default_ram_ceiling_mb} MB
                </span>
              </div>

              <input
                type="range"
                name="default_ram_ceiling_mb"
                min="51"
                max="4096"
                step="1"
                value={formData.default_ram_ceiling_mb}
                onChange={handleChange}
                className="w-full accent-primary cursor-pointer"
              />

              <div className="flex justify-between text-[10px] font-bold text-muted uppercase">
                <span>51 MB (Micro)</span>
                <span>500 MB (Standard)</span>
                <span>1000 MB (Heavy)</span>
                <span>4 GB (4,096 MB)</span>
              </div>
              <p className="text-[11px] text-muted font-normal">
                Sets your workstation default concurrency memory ceiling when initiating new ramp-up load tests.
              </p>
            </div>

            {/* Row 6: Bio & Workstation Notes */}
            <div className="space-y-1.5">
              <label className="text-xs font-black uppercase tracking-wider block">
                Workstation Notes / Operator Bio:
              </label>
              <textarea
                name="bio_notes"
                rows={3}
                value={formData.bio_notes}
                onChange={handleChange}
                placeholder="Notes on testing environment, target cluster setups, or hardware limits..."
                className="w-full ui-outline border border-line p-2.5 text-xs font-mono bg-surface focus:outline-none focus:bg-field transition-colors shadow-inner"
              />
            </div>

            {/* Error Banner */}
            {saveError && (
              <p role="alert" className="text-xs font-bold text-rose-700">
                {saveError}
              </p>
            )}

            {/* Footer Buttons */}
            <div className="pt-3 border-t border-line flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="w-full sm:w-auto border border-line px-4 py-2 text-xs font-black uppercase hover:bg-primary hover:text-white transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Revert Changes</span>
              </button>

              <button
                type="submit"
                disabled={saving}
                className={`w-full sm:w-auto border border-line px-6 py-2.5 text-xs font-black uppercase transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${
                  saving
                    ? 'bg-soft text-ink cursor-wait'
                    : (themeMode === 'production'
                        ? 'bg-primary text-white hover:bg-primary-hover'
                        : 'bg-primary text-white hover:bg-primary-hover')
                }`}
              >
                <Save className="w-4 h-4" />
                <span>{saving ? 'PERSISTING TO SQLITE...' : 'SAVE PROFILE'}</span>
              </button>
            </div>
          </form>
        </div>

      </div>
    </div>
  );
}

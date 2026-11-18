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
  Sliders
} from 'lucide-react';

export default function ProfileView({
  profile,
  onSaveProfile,
  deviceId = 'DEV-LOCAL-CREATOR',
  themeMode = 'production',
  setActiveNav,
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
  const [avatarError, setAvatarError] = useState(false);

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
      [name]: type === 'number' ? (parseInt(value, 10) || 50) : value,
    }));
    setSaveSuccess(false);
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
      setAvatarError(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      await onSaveProfile(formData);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } finally {
      setSaving(false);
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
      <div className="border-2 border-black p-4 sm:p-5 bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-black uppercase tracking-wider text-black/60">
              [ USER PROFILE & PREFERENCES ]
            </span>
            <span className="border border-black px-1.5 py-0.2 text-[10px] font-bold uppercase bg-white">
              SQLite Persistent
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-black uppercase tracking-tight mt-1">
            Operator Profile & Hardware Defaults
          </h1>
          <p className="text-xs text-black/80 mt-1 max-w-2xl font-normal">
            Manage your developer identity, default concurrency caps, and workstation defaults.
            All attributes persist across application reloads in <span className="font-bold">backend/pusher_runs.db</span>.
          </p>
        </div>

        {/* Quick Action Badges */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setActiveNav && setActiveNav('dashboard')}
            className="border-2 border-black px-3 py-1.5 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      {/* Success Notification Banner */}
      {saveSuccess && (
        <div className="border-2 border-black p-3.5 bg-emerald-100 text-emerald-950 font-bold text-xs uppercase flex items-center justify-between shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] animate-fade-in">
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
          <div className="border-2 border-black p-5 bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-5">
            <div className="flex items-start gap-4">
              {/* Avatar Image or Fallback Initials */}
              <div className="w-16 h-16 border-2 border-black rounded-none shrink-0 overflow-hidden bg-slate-900 text-white flex items-center justify-center font-black text-xl select-none shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
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
                <div className="text-xs text-black/70 font-bold truncate">
                  @{formData.username || 'pusher_operator'}
                </div>
                <div className="mt-1 inline-block border border-black px-1.5 py-0.5 text-[10px] font-bold uppercase bg-slate-100 truncate max-w-full">
                  {formData.role_title || 'Load Test Engineer'}
                </div>
              </div>
            </div>

            {/* Bio / Hardware Notes */}
            <div className="border-t border-black pt-3">
              <span className="text-[10px] font-bold uppercase text-black/60 block mb-1">
                ENGINEER BIO / SPECS:
              </span>
              <p className="text-xs text-black/80 font-normal leading-relaxed whitespace-pre-wrap bg-slate-50 p-2.5 border border-black/40 min-h-[60px]">
                {formData.bio_notes || 'No operator bio provided.'}
              </p>
            </div>

            {/* Quick Metadata List */}
            <div className="border-t border-black pt-3 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-black/70 flex items-center gap-1.5 font-bold">
                  <Mail className="w-3.5 h-3.5" /> Email:
                </span>
                <span className="font-mono truncate max-w-[160px] text-right font-bold" title={formData.email}>
                  {formData.email || 'dev@pusher.internal'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-black/70 flex items-center gap-1.5 font-bold">
                  <Building className="w-3.5 h-3.5" /> Org:
                </span>
                <span className="font-mono truncate max-w-[160px] text-right font-bold">
                  {formData.organization || 'Independent'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-black/70 flex items-center gap-1.5 font-bold">
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
                  <span className="font-mono text-black/50">None</span>
                )}
              </div>
            </div>

            {/* Telemetry Hardware Badges */}
            <div className="border-t border-black pt-3 space-y-2">
              <div className="border border-black p-2 bg-slate-50 flex items-center justify-between text-xs">
                <span className="font-bold flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5" /> Default RAM Limit:
                </span>
                <span className="font-mono font-black text-sm bg-black text-white px-2 py-0.5">
                  {formData.default_ram_ceiling_mb} MB
                </span>
              </div>

              <div className="border border-black p-2 bg-slate-50 flex items-center justify-between text-xs">
                <span className="font-bold flex items-center gap-1.5">
                  <Fingerprint className="w-3.5 h-3.5" /> Device Lock:
                </span>
                <span className="font-mono text-[11px] truncate max-w-[130px] font-bold" title={deviceId}>
                  {deviceId}
                </span>
              </div>

              {profile?.updated_at && (
                <div className="text-[10px] text-black/60 font-mono text-right">
                  Synced: {profile.updated_at}
                </div>
              )}
            </div>
          </div>

          {/* Platform Invariants Notice Card */}
          <div className="border-2 border-black p-4 bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-2 text-xs">
            <div className="font-black uppercase flex items-center gap-1.5 text-black">
              <Shield className="w-4 h-4" /> Hardened Invariants
            </div>
            <ul className="text-[11px] text-black/80 space-y-1 list-disc list-inside font-normal">
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
            className="border-2 border-black p-5 sm:p-6 bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] space-y-5"
          >
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div className="flex items-center gap-2">
                <User className="w-5 h-5" />
                <h2 className="text-base sm:text-lg font-black uppercase tracking-tight">
                  Edit Profile Information
                </h2>
              </div>
              <span className="text-[11px] font-bold text-black/60 uppercase">
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
                  className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
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
                  className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
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
                  className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
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
                  className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
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
                  className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-black uppercase tracking-wider block">
                  GitHub Handle:
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-xs font-mono text-black/50 select-none">
                    @
                  </span>
                  <input
                    type="text"
                    name="github_username"
                    value={formData.github_username.replace(/^@/, '')}
                    onChange={handleChange}
                    placeholder="github-username"
                    className="w-full border-2 border-black p-2.5 pl-7 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
                  />
                </div>
              </div>
            </div>

            {/* Row 4: Avatar Image URL */}
            <div className="space-y-1.5">
              <label className="text-xs font-black uppercase tracking-wider block flex items-center justify-between">
                <span>Avatar Image URL:</span>
                <span className="text-[10px] font-normal normal-case text-black/60">
                  (HTTPS image or leave blank for initials)
                </span>
              </label>
              <input
                type="url"
                name="avatar_url"
                value={formData.avatar_url}
                onChange={handleChange}
                placeholder="https://images.unsplash.com/... or https://github.com/username.png"
                className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
              />
            </div>

            {/* Row 5: Hardware Default RAM Ceiling Slider / Input */}
            <div className="border-2 border-black p-4 bg-slate-50 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-black" />
                  <label className="text-xs font-black uppercase tracking-wider">
                    Default RAM Limit Ceiling (MB):
                  </label>
                </div>
                <span className="font-mono text-xs font-black bg-black text-white px-2.5 py-0.5">
                  {formData.default_ram_ceiling_mb} MB
                </span>
              </div>

              <input
                type="range"
                name="default_ram_ceiling_mb"
                min="50"
                max="2048"
                step="50"
                value={formData.default_ram_ceiling_mb}
                onChange={handleChange}
                className="w-full accent-black cursor-pointer"
              />

              <div className="flex justify-between text-[10px] font-bold text-black/60 uppercase">
                <span>50 MB (Micro)</span>
                <span>500 MB (Standard)</span>
                <span>1000 MB (Heavy)</span>
                <span>2048 MB (Extreme)</span>
              </div>
              <p className="text-[11px] text-black/70 font-normal">
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
                className="w-full border-2 border-black p-2.5 text-xs font-mono bg-white focus:outline-none focus:bg-slate-50 transition-colors shadow-inner"
              />
            </div>

            {/* Footer Buttons */}
            <div className="pt-3 border-t-2 border-black flex flex-col sm:flex-row items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="w-full sm:w-auto border-2 border-black px-4 py-2 text-xs font-black uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Revert Changes</span>
              </button>

              <button
                type="submit"
                disabled={saving}
                className={`w-full sm:w-auto border-2 border-black px-6 py-2.5 text-xs font-black uppercase transition-all flex items-center justify-center gap-2 cursor-pointer shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${
                  saving
                    ? 'bg-slate-200 text-black cursor-wait'
                    : (themeMode === 'production'
                        ? 'bg-teal-700 text-white hover:bg-teal-800'
                        : 'bg-black text-white hover:bg-slate-800')
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

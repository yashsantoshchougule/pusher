import React from 'react';
import { Sliders, Database, AlertTriangle, Shield, CheckSquare, Square, Layers, Play } from 'lucide-react';

export default function TrafficSetupView({
  trafficMode,
  setTrafficMode,
  ramLimitMb,
  handleSetRamLimit,
  maxHardwareSafeRamMb,
  vus,
  setVus,
  maxAllowedVus,
  duration,
  setDuration,
  max5xxThreshold,
  setMax5xxThreshold,
  wafAutoAbort,
  setWafAutoAbort,
  p95Ceiling,
  setP95Ceiling,
  cacheBusting,
  setCacheBusting,
  estimatedRam,
  estimatedFdPercent,
  isVerified,
  handleStartTest,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';
  const modeLabel = trafficMode === 'step_ramp' ? 'STEP-RAMP' : trafficMode === 'sudden_rush' ? 'SUDDEN RUSH' : 'STEADY CROWD';

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black uppercase tracking-wider">
            TRAFFIC SETUP &amp; SAFETY CONTROLS
          </h1>
          <p className="text-xs opacity-75">
            Configure virtual user progression curves, safety limits, and resource budgeting.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setActiveNav('dashboard')}
          className="border-2 border-black px-3 py-1 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer"
        >
          ← Back to Dashboard
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Mode, Concurrency & Visual Curve */}
        <div className={`lg:col-span-6 border-2 border-black p-5 bg-white space-y-4 ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div className="border-b-2 border-black pb-2">
            <h2 className="text-sm font-black uppercase">
              1. TRAFFIC PROGRESSION PROFILE
            </h2>
          </div>

          {/* Mode Buttons */}
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase block">Mode:</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'step_ramp', label: 'Step-Ramp' },
                { id: 'sudden_rush', label: 'Sudden Rush' },
                { id: 'steady_crowd', label: 'Steady Crowd' },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setTrafficMode(m.id)}
                  className={`border-2 border-black py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    trafficMode === m.id
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* ASCII Progression Curve Preview */}
          <div className="border-2 border-black p-3 bg-white">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2 flex justify-between">
              <span>Traffic Curve Shape Preview:</span>
              <span>{modeLabel}</span>
            </div>
            <pre className="text-[10px] font-mono leading-tight bg-white p-2 border border-black overflow-x-auto">
              {trafficMode === 'step_ramp' ?
                `VUs  |
${String(vus).padStart(4)} |               +--- (Peak)
     |          +----+
     |     +----+
  10 |+----+
     +---------------------------> Time (${duration}s)` :
                trafficMode === 'sudden_rush' ?
                  `VUs  |
${String(vus).padStart(4)} |+-----------------------
     |
     |
  10 |
     +---------------------------> Time (${duration}s)` :
                  `VUs  |
${String(vus).padStart(4)} |======================== (Steady Soak)
     |
     |
  10 |
     +---------------------------> Time (${duration}s)`
              }
            </pre>
          </div>

          {/* Hardware RAM Scaling Selector */}
          <div className="border-2 border-black p-3 bg-white space-y-2">
            <div className="flex justify-between items-center text-xs font-bold uppercase">
              <span>RAM Budget &amp; Hardware Ceiling:</span>
              <span className={`text-xs font-black border border-black px-2 py-0.5 ${
                isProd ? 'bg-teal-700 text-white' : 'bg-black text-white'
              }`}>
                {ramLimitMb} MB ({maxAllowedVus.toLocaleString()} Max VUs)
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {[
                { limit: 250, label: '250 MB', vus: '1,000 VUs' },
                { limit: 500, label: '500 MB', vus: '2,250 VUs (Default)' },
                { limit: 1024, label: '1,024 MB', vus: '4,870 VUs' },
                { limit: 2048, label: '2,048 MB', vus: '9,990 VUs' },
              ].map((preset) => (
                <button
                  key={preset.limit}
                  type="button"
                  onClick={() => handleSetRamLimit(preset.limit)}
                  className={`border-2 border-black py-1.5 px-1 text-[10px] font-bold uppercase transition-colors text-center cursor-pointer ${
                    ramLimitMb === preset.limit
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  <div>{preset.label}</div>
                  <div className="text-[9px] opacity-80">{preset.vus}</div>
                </button>
              ))}
            </div>
            {/* Custom RAM Entry */}
            <div className="flex items-center gap-2 pt-1">
              <span className="text-[10px] font-bold uppercase shrink-0">Custom Limit:</span>
              <input
                type="number"
                min="100"
                max={maxHardwareSafeRamMb}
                step="50"
                value={ramLimitMb}
                onChange={(e) => handleSetRamLimit(Number(e.target.value))}
                className="w-24 border border-black px-2 py-1 text-xs font-mono font-bold bg-white text-black focus:outline-none focus:bg-black focus:text-white"
              />
              <span className="text-[10px] font-bold">MB</span>
              <span className="text-[9px] opacity-75 ml-auto">
                Host Cap: {maxHardwareSafeRamMb.toLocaleString()} MB (75% Host RAM)
              </span>
            </div>
          </div>

          {/* Concurrency Slider & Direct Numeric Input */}
          <div className="border-2 border-black p-3 bg-white space-y-2">
            <div className="flex justify-between items-center text-xs font-bold uppercase">
              <span>Virtual Users (Concurrency):</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="10"
                  max={maxAllowedVus}
                  step="10"
                  value={vus}
                  onChange={(e) => setVus(Math.max(10, Math.min(maxAllowedVus, Number(e.target.value) || 10)))}
                  className="w-20 border-2 border-black px-1.5 py-0.5 text-xs font-mono font-black text-center bg-white text-black focus:outline-none focus:bg-black focus:text-white"
                />
                <span className="text-[10px] font-bold">VUs</span>
                <span className="text-[10px] font-bold border border-black px-1.5 py-0.5 bg-black text-white">
                  Cap: {maxAllowedVus.toLocaleString()}
                </span>
              </div>
            </div>
            <input
              type="range"
              min="10"
              max={maxAllowedVus}
              step="10"
              value={Math.min(vus, maxAllowedVus)}
              onChange={(e) => setVus(Number(e.target.value))}
              className="w-full accent-black cursor-pointer"
            />
            <div className="flex justify-between text-[10px] opacity-75">
              <span>10 VUs</span>
              <span>Default Cap: 2,250 VUs</span>
              <span>Current Cap: {maxAllowedVus.toLocaleString()} VUs</span>
            </div>
          </div>

          {/* Duration Selector */}
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase block">Duration:</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { sec: 60, label: '60s (Quick)' },
                { sec: 180, label: '180s (Standard)' },
                { sec: 300, label: '300s (Soak)' },
              ].map((d) => (
                <button
                  key={d.sec}
                  type="button"
                  onClick={() => setDuration(d.sec)}
                  className={`border-2 border-black py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    duration === d.sec
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Circuit Breakers & Resource Budgeting */}
        <div className={`lg:col-span-6 border-2 border-black p-5 bg-white space-y-4 ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div className="border-b-2 border-black pb-2">
            <h2 className="text-sm font-black uppercase">
              2. SAFETY CIRCUIT BREAKERS &amp; GUARDS
            </h2>
          </div>

          {/* Max Error Rate Selector */}
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase block">
              Max Error Rate (5xx / 429) Threshold:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { val: 2, label: '2% (Strict)' },
                { val: 5, label: '5% (Standard)' },
                { val: 10, label: '10% (Relaxed)' },
              ].map((t) => (
                <button
                  key={t.val}
                  type="button"
                  onClick={() => setMax5xxThreshold(t.val)}
                  className={`border-2 border-black py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    max5xxThreshold === t.val
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* WAF Auto-Abort Toggle */}
          <div
            onClick={() => setWafAutoAbort(!wafAutoAbort)}
            className="border-2 border-black p-3 bg-white flex items-center justify-between cursor-pointer select-none"
          >
            <div>
              <div className="text-xs font-bold uppercase">WAF Auto-Abort (Circuit Breaker)</div>
              <div className="text-[10px] opacity-75">
                Automatically halt load if edge rate limiter or 5xx spikes
              </div>
            </div>
            <button type="button" className="text-black">
              {wafAutoAbort ? <CheckSquare className="w-5 h-5" /> : <Square className="w-5 h-5" />}
            </button>
          </div>

          {/* P95 Latency Ceiling */}
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase block">
              P95 Latency Ceiling:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { ms: 1000, label: '1,000 ms' },
                { ms: 2000, label: '2,000 ms (Std)' },
                { ms: 5000, label: '5,000 ms' },
              ].map((p) => (
                <button
                  key={p.ms}
                  type="button"
                  onClick={() => setP95Ceiling(p.ms)}
                  className={`border-2 border-black py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    p95Ceiling === p.ms
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Cache-Busting Nonce Toggle */}
          <div className="border-2 border-black p-3 bg-white flex items-center justify-between">
            <div>
              <div className="text-xs font-bold uppercase">Dynamic Cache-Busting</div>
              <div className="text-[10px] opacity-75">Append ?_cb=nonce to bypass CDN caches</div>
            </div>
            <button
              type="button"
              onClick={() => setCacheBusting(!cacheBusting)}
              className={`border border-black px-3 py-1 text-xs font-bold uppercase cursor-pointer ${
                cacheBusting
                  ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                  : 'bg-white text-black'
              }`}
            >
              {cacheBusting ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>

          {/* Live Resource Estimator */}
          <div className="border-2 border-black p-3 bg-white text-xs space-y-1">
            <div className="font-bold uppercase border-b border-black pb-1 mb-1">
              Resource Consumption Estimate:
            </div>
            <div className="flex justify-between">
              <span>Est. Engine RAM:</span>
              <span className="font-bold">{estimatedRam} MB (Max Cap: {ramLimitMb} MB)</span>
            </div>
            <div className="flex justify-between">
              <span>Est. OS File Descriptors:</span>
              <span className="font-bold">{estimatedFdPercent}% (Max Cap: 70%)</span>
            </div>
            <div className="flex justify-between text-[10px] opacity-75">
              <span>Streaming Buffer Model:</span>
              <span>4KB Discard Active (0.20 MB / VU)</span>
            </div>
            <div className="flex justify-between text-[10px] opacity-75">
              <span>Host Safety Ceiling:</span>
              <span className={isProd && ramLimitMb <= maxHardwareSafeRamMb ? 'text-emerald-700 font-bold' : ''}>
                {ramLimitMb <= maxHardwareSafeRamMb ? 'SAFE (< 75% Host RAM)' : 'EXCEEDS SAFE HOST LIMIT'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Action Ribbon */}
      <div className="border-t-2 border-black pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => setActiveNav('dashboard')}
          className="border-2 border-black py-3 px-4 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer text-center"
        >
          SAVE PROFILE &amp; RETURN TO DASHBOARD
        </button>
        <button
          type="button"
          onClick={handleStartTest}
          disabled={!isVerified}
          className={`border-2 border-black py-3 px-4 text-xs font-black uppercase transition-colors text-center tracking-wider ${
            isVerified
              ? (isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer' : 'bg-black text-white hover:bg-white hover:text-black cursor-pointer')
              : 'bg-white text-black opacity-40 cursor-not-allowed'
          }`}
        >
          {isVerified ? 'SAVE & LAUNCH LOAD TEST NOW →' : 'DISABLED (VERIFY TARGET FIRST)'}
        </button>
      </div>
    </div>
  );
}

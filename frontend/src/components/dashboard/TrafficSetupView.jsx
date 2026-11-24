import React from 'react';

export default function TrafficSetupView({
  trafficMode,
  setTrafficMode,
  ramLimitMb,
  handleSetRamLimit,
  maxHardwareSafeRamMb,
  vus,
  setVus,
  maxAllowedVus,
  trafficVuLimit,
  maxWorkerVus,
  phases = [],
  duration,
  setDuration,
  max5xxThreshold,
  setMax5xxThreshold,
  p95Ceiling,
  maxP95Ceiling,
  setP95Ceiling,
  cacheBusting,
  setCacheBusting,
  estimatedRam,
  trafficLaunchBlocker,
  launchError,
  runType,
  handleStartTest,
  handleSaveTraffic,
  trafficSaving,
  trafficLoading,
  trafficSaveError,
  trafficCloneNotice,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';
  const modeLabel = trafficMode === 'step_ramp' ? 'STEP-RAMP' : trafficMode === 'sudden_rush' ? 'SUDDEN RUSH' : 'STEADY CROWD';
  const canSetVus = maxAllowedVus > 0;
  const time = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
  const effectiveP95 = Math.min(p95Ceiling, maxP95Ceiling ?? p95Ceiling);

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

      <div className="flex flex-wrap items-center justify-between gap-2 border-2 border-black p-3">
        <span className="text-xs"><strong>Next run</strong> {runType}</span>
        <button
          type="button"
          disabled={trafficSaving}
          onClick={() => setActiveNav('api')}
          className="text-xs font-bold underline disabled:opacity-50"
        >
          Open API Journey Builder
        </button>
      </div>
      {trafficCloneNotice && <p role="status" className="text-xs font-bold">{trafficCloneNotice}</p>}

      <fieldset disabled={trafficSaving || trafficLoading} aria-label="Traffic settings" className="min-w-0 grid grid-cols-1 lg:grid-cols-12 gap-6">
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

          <div className="border-2 border-black p-3 bg-white">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2 flex justify-between">
              <span>Traffic schedule</span>
              <span>{modeLabel}</span>
            </div>
            {phases.length ? (
              <ol className="space-y-1 text-xs font-mono">
                {phases.map(phase => (
                  <li key={phase.start} className="flex justify-between gap-3">
                    <span>{time.format(phase.start)}–{time.format(phase.end)} s</span>
                    <span>{phase.vus.toLocaleString()} VUs</span>
                  </li>
                ))}
              </ol>
            ) : <p className="text-xs">Schedule unavailable.</p>}
          </div>

          {/* Hardware RAM Scaling Selector */}
          <div className="border-2 border-black p-3 bg-white space-y-2">
            <div className="flex justify-between items-center text-xs font-bold uppercase">
              <span>RAM Budget &amp; Hardware Ceiling:</span>
              <span className={`text-xs font-black border border-black px-2 py-0.5 ${
                isProd ? 'bg-teal-700 text-white' : 'bg-black text-white'
              }`}>
                {ramLimitMb} MB ({maxAllowedVus?.toLocaleString() ?? 'Unknown'} max VUs)
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {[250, 500, 1024, 2048].map((limit) => (
                <button
                  key={limit}
                  type="button"
                  disabled={!maxHardwareSafeRamMb || limit > maxHardwareSafeRamMb}
                  onClick={() => handleSetRamLimit(limit)}
                  className={`border-2 border-black py-1.5 px-1 text-[10px] font-bold uppercase transition-colors text-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    ramLimitMb === limit
                      ? (isProd ? 'bg-slate-900 text-white' : 'bg-black text-white')
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  <div>{limit.toLocaleString()} MB</div>
                  <div className="text-[9px] opacity-80">
                    {limit > maxHardwareSafeRamMb ? 'Above host limit' : `${trafficVuLimit(limit)?.toLocaleString() ?? 'Unknown'} max VUs`}
                  </div>
                </button>
              ))}
            </div>
            {/* Custom RAM Entry */}
            <div className="flex items-center gap-2 pt-1">
              <span className="text-[10px] font-bold uppercase shrink-0">Custom Limit:</span>
              <input
                type="number"
                min="51"
                max={maxHardwareSafeRamMb}
                step="1"
                disabled={!maxHardwareSafeRamMb || maxHardwareSafeRamMb < 51}
                value={ramLimitMb}
                onChange={(e) => handleSetRamLimit(Number(e.target.value))}
                className="w-24 border border-black px-2 py-1 text-xs font-mono font-bold bg-white text-black focus:outline-none focus:bg-black focus:text-white"
              />
              <span className="text-[10px] font-bold">MB</span>
              <span className="text-[9px] opacity-75 ml-auto">
                {maxHardwareSafeRamMb == null ? 'Host cap unavailable' : `Host cap ${maxHardwareSafeRamMb.toLocaleString()} MB (75% host RAM)`}
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
                  min="1"
                  max={maxAllowedVus ?? undefined}
                  step="1"
                  disabled={!canSetVus}
                  value={vus}
                  onChange={(e) => setVus(Math.max(1, Math.min(maxAllowedVus, Math.floor(Number(e.target.value)) || 1)))}
                  className="w-20 border-2 border-black px-1.5 py-0.5 text-xs font-mono font-black text-center bg-white text-black focus:outline-none focus:bg-black focus:text-white"
                />
                <span className="text-[10px] font-bold">VUs</span>
                <span className="text-[10px] font-bold border border-black px-1.5 py-0.5 bg-black text-white">
                  Cap: {maxAllowedVus?.toLocaleString() ?? 'Unknown'}
                </span>
              </div>
            </div>
            <input
              type="range"
              min="1"
              max={canSetVus ? maxAllowedVus : 1}
              step="1"
              disabled={!canSetVus}
              value={canSetVus ? Math.min(vus, maxAllowedVus) : 1}
              onChange={(e) => setVus(Number(e.target.value))}
              className="w-full accent-black cursor-pointer"
            />
          </div>

          {/* Duration Selector */}
          <div className="space-y-1">
            <div className="text-xs font-bold uppercase">Duration · {duration} s</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { sec: 30, label: '30 s (Default)' },
                { sec: 60, label: '60s (Quick)' },
                { sec: 180, label: '180s (Standard)' },
                { sec: 300, label: '300s (Soak)' },
              ].map((d) => (
                <button
                  key={d.sec}
                  type="button"
                  aria-pressed={duration === d.sec}
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
              Rolling server-error threshold (5xx)
            </label>
            <p className="text-[10px] opacity-75">Applies when at least 20 responses were received in the last 5 seconds.</p>
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

          <div className="border-2 border-black p-3 bg-white space-y-1">
            <div className="text-xs font-bold uppercase">Automatic stops are always on</div>
            <p className="text-[10px] opacity-75">
              Pusher stops on a detected firewall block, 3 rate-limit responses in 3 seconds, or 5 consecutive server errors.
            </p>
          </div>

          {/* P95 Latency Ceiling */}
          <div className="space-y-1">
            <div className="text-xs font-bold uppercase">P95 latency ceiling · {effectiveP95.toLocaleString()} ms</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { ms: 1000, label: '1,000 ms' },
                { ms: 1500, label: '1,500 ms (Default)' },
                { ms: 2000, label: '2,000 ms' },
                { ms: 5000, label: '5,000 ms' },
              ].map((p) => (
                <button
                  key={p.ms}
                  type="button"
                  aria-pressed={p95Ceiling === p.ms}
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
              <span className="font-bold">{estimatedRam == null ? 'Unavailable' : `${estimatedRam} MB of ${ramLimitMb} MB budget`}</span>
            </div>
            <div className="flex justify-between">
              <span>Engine worker limit</span>
              <span className="font-bold">{maxWorkerVus?.toLocaleString() ?? 'Unavailable'}</span>
            </div>
            <div className="flex justify-between text-[10px] opacity-75">
              <span>Streaming Buffer Model:</span>
              <span>4KB Discard Active (0.20 MB / VU)</span>
            </div>
            <div className="flex justify-between text-[10px] opacity-75">
              <span>Host Safety Ceiling:</span>
              <span className={isProd && ramLimitMb <= maxHardwareSafeRamMb ? 'text-emerald-700 font-bold' : ''}>
                {maxHardwareSafeRamMb == null ? 'Unavailable' : ramLimitMb <= maxHardwareSafeRamMb ? 'Within host limit' : 'Above host limit'}
              </span>
            </div>
          </div>
        </div>
      </fieldset>

      {/* Bottom Action Ribbon */}
      {trafficSaveError && <p role="alert" className="text-xs font-bold text-rose-800">{trafficSaveError}</p>}
      {launchError && <p role="alert" className="text-xs font-bold text-rose-800">{launchError}</p>}
      {trafficLaunchBlocker && <p role="status" className="text-xs font-bold">{trafficLaunchBlocker}</p>}
      <div className="border-t-2 border-black pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={handleSaveTraffic}
          disabled={trafficSaving || trafficLoading}
          className="border-2 border-black py-3 px-4 text-xs font-bold uppercase hover:bg-black hover:text-white transition-colors cursor-pointer text-center"
        >
          SAVE PROFILE &amp; RETURN TO DASHBOARD
        </button>
        <button
          type="button"
          onClick={handleStartTest}
          disabled={Boolean(trafficLaunchBlocker)}
          className={`border-2 border-black py-3 px-4 text-xs font-black uppercase transition-colors text-center tracking-wider ${
            !trafficLaunchBlocker
              ? (isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer' : 'bg-black text-white hover:bg-white hover:text-black cursor-pointer')
              : 'bg-white text-black opacity-40 cursor-not-allowed'
          }`}
        >
          SAVE &amp; LAUNCH LOAD TEST
        </button>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';

export default function TrafficSetupView({
  projectName = '',
  setProjectName,
  projectNameSource = '',
  onSaveProjectName,
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
  sameProcessLoopback = false,
  loopbackAdvisory = '',
  sandboxMode = false,
  targetUrl = '',
  requestTimeoutSec = 5,
  hasUnsavedTraffic = false,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';
  const modeLabel = trafficMode === 'step_ramp' ? 'STEP-RAMP' : trafficMode === 'sudden_rush' ? 'SUDDEN RUSH' : 'STEADY CROWD';
  const canSetVus = maxAllowedVus > 0;
  const time = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });
  const effectiveP95 = Math.min(p95Ceiling, maxP95Ceiling ?? p95Ceiling);
  const effective5xx = Math.min(max5xxThreshold, 25);

  const [ramDraft, setRamDraft] = useState(String(ramLimitMb));
  const [vuDraft, setVuDraft] = useState(String(vus));
  const [durationDraft, setDurationDraft] = useState(String(duration));

  useEffect(() => { setRamDraft(String(ramLimitMb)); }, [ramLimitMb]);
  useEffect(() => { setVuDraft(String(vus)); }, [vus]);
  useEffect(() => { setDurationDraft(String(duration)); }, [duration]);

  const targetIsLoopback = Boolean(
    sandboxMode || sameProcessLoopback || (() => {
      try {
        const host = new URL((targetUrl || '').trim()).hostname.toLowerCase();
        return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]' || host === '0.0.0.0';
      } catch {
        return false;
      }
    })()
  );

  // Step-ramp schedule summary & warnings
  const stepDuration = duration / 5;
  const stepCount = phases.length || 5;
  const step1Vus = phases[0]?.vus ?? Math.max(1, Math.round(vus * 0.2));

  const commitRam = (raw) => {
    if (maxHardwareSafeRamMb == null || maxHardwareSafeRamMb < 51) return;
    const parsed = Math.floor(Number(raw));
    const clamped = Number.isFinite(parsed) && raw.trim() !== ''
      ? Math.max(51, Math.min(maxHardwareSafeRamMb, parsed))
      : ramLimitMb;
    setRamDraft(String(clamped));
    if (clamped !== ramLimitMb) handleSetRamLimit(clamped);
  };

  const commitVus = (raw) => {
    if (!canSetVus) return;
    const parsed = Math.floor(Number(raw));
    const clamped = Number.isFinite(parsed) && raw.trim() !== ''
      ? Math.max(1, Math.min(maxAllowedVus, parsed))
      : vus;
    setVuDraft(String(clamped));
    if (clamped !== vus) setVus(clamped);
  };

  const commitDuration = (raw) => {
    const parsed = Math.floor(Number(raw));
    const clamped = Number.isFinite(parsed) && raw.trim() !== ''
      ? Math.max(1, Math.min(86400, parsed))
      : duration;
    setDurationDraft(String(clamped));
    if (clamped !== duration) setDuration(clamped);
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b border-line pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="ui-page-title">
            Traffic setup
          </h1>
          <p className="text-xs opacity-75">
            Configure virtual user progression curves, safety limits, and resource budgeting.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setActiveNav('dashboard')}
          className="border border-line px-3 py-1 text-xs font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer"
        >
          ← Back to Dashboard
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border border-line p-3">
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
      {hasUnsavedTraffic && !trafficCloneNotice && (
        <p role="status" className="text-xs font-bold text-amber-800">
          Unsaved staged draft — click Save Profile or Save &amp; Launch to persist.
        </p>
      )}

      {targetIsLoopback && vus > 50 && (
        <div role="status" className={`border-2 p-3 text-xs font-mono ${
          isProd ? 'border-amber-500 bg-amber-50 text-amber-900' : 'border-line bg-surface'
        }`}>
          <strong>Loopback / single-host saturation warning:</strong>{' '}
          {loopbackAdvisory || `Running ${vus.toLocaleString()} VUs against a local/sandbox target shares the same host CPU and event loop and typically saturates above ~50 VUs.`}
        </div>
      )}

      <fieldset disabled={trafficSaving || trafficLoading} aria-label="Traffic settings" className="min-w-0 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Mode, Concurrency & Visual Curve */}
        <div className={`lg:col-span-6 ui-outline border border-line p-5 bg-surface space-y-4 ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div className="border-b border-line pb-2">
            <h2 className="text-sm font-black uppercase">
              Traffic progression
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
                  aria-pressed={trafficMode === m.id}
                  className={`rounded-xl border border-control min-h-12 px-2 text-sm font-semibold transition-colors ${
                    trafficMode === m.id
                      ? 'border-transparent bg-accent text-accent-ink'
                      : 'bg-field text-ink hover:bg-soft'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="ui-outline border border-line p-3 bg-surface space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider flex justify-between">
              <span>Traffic schedule</span>
              <span>{modeLabel}</span>
            </div>
            {trafficMode === 'step_ramp' && (
              <div className="text-[11px] font-mono opacity-85">
                {stepCount} steps · {time.format(stepDuration)}s/step · starts at Step 1 {step1Vus.toLocaleString()} VUs
              </div>
            )}
            {trafficMode === 'step_ramp' && duration < 5 && (
              <p className="text-[10px] font-bold text-amber-800">
                Duration under 5s truncates later ramp steps (minimum 1s/step).
              </p>
            )}
            {trafficMode === 'step_ramp' && duration >= 5 && stepDuration <= 10 && (
              <p className="text-[10px] font-bold text-amber-800">
                Short step window ({time.format(stepDuration)}s/step) overlaps the 10s rolling breaker window and {requestTimeoutSec}s request timeout.
              </p>
            )}
            {trafficMode === 'step_ramp' && vus < 5 && (
              <p className="text-[10px] font-bold text-amber-800">
                Fewer than 5 VUs produces duplicate step levels, preventing 3-tier knee detection.
              </p>
            )}
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
          <div className="ui-outline border border-line p-3 bg-surface space-y-2">
            <div className="flex justify-between items-center text-xs font-bold uppercase">
              <span>RAM Budget &amp; Hardware Ceiling:</span>
              <span className={`text-xs font-black border border-line px-2 py-0.5 ${
                isProd ? 'bg-primary text-white' : 'bg-primary text-white'
              }`}>
                {ramLimitMb} MB ({maxAllowedVus?.toLocaleString() ?? 'Unknown'} max VUs)
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {[250, 500, 1024, 2048, 4096].map((limit) => (
                <button
                  key={limit}
                  type="button"
                  disabled={maxHardwareSafeRamMb == null || limit > maxHardwareSafeRamMb}
                  onClick={() => handleSetRamLimit(limit)}
                  className={`border border-line py-1.5 px-1 text-[10px] font-bold uppercase transition-colors text-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    ramLimitMb === limit
                      ? (isProd ? 'bg-primary text-white' : 'bg-primary text-white')
                      : 'bg-surface text-ink hover:bg-soft'
                  }`}
                >
                  <div>{limit.toLocaleString()} MB</div>
                  <div className="text-[9px] opacity-80">
                    {maxHardwareSafeRamMb != null && limit > maxHardwareSafeRamMb
                      ? 'Above host limit'
                      : `${trafficVuLimit(limit)?.toLocaleString() ?? 'Unknown'} max VUs`}
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
                max={maxHardwareSafeRamMb ?? undefined}
                step="1"
                disabled={maxHardwareSafeRamMb == null || maxHardwareSafeRamMb < 51}
                value={ramDraft}
                onChange={(e) => {
                  const val = e.target.value;
                  setRamDraft(val);
                  const parsed = Math.floor(Number(val));
                  if (val.trim() !== '' && Number.isFinite(parsed) && parsed >= 51 && parsed <= maxHardwareSafeRamMb) {
                    handleSetRamLimit(parsed);
                  }
                }}
                onBlur={() => commitRam(ramDraft)}
                className="w-24 ui-outline border border-line px-2 py-1 text-xs font-mono font-bold bg-surface text-ink focus:outline-none focus:bg-primary focus:text-white"
              />
              <span className="text-[10px] font-bold">MB</span>
              <span className="text-[9px] opacity-75 ml-auto">
                {maxHardwareSafeRamMb == null ? 'Host cap unavailable' : `Maximum ${maxHardwareSafeRamMb.toLocaleString()} MB`}
              </span>
            </div>
          </div>

          {/* Concurrency Slider & Direct Numeric Input */}
          <div className="ui-outline border border-line p-3 bg-surface space-y-2">
            <div className="flex justify-between items-center text-xs font-bold uppercase">
              <span>Virtual Users (Concurrency):</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="1"
                  max={maxAllowedVus ?? undefined}
                  step="1"
                  disabled={!canSetVus}
                  value={vuDraft}
                  onChange={(e) => {
                    const val = e.target.value;
                    setVuDraft(val);
                    const parsed = Math.floor(Number(val));
                    if (val.trim() !== '' && Number.isFinite(parsed) && parsed >= 1 && (maxAllowedVus == null || parsed <= maxAllowedVus)) {
                      setVus(parsed);
                    }
                  }}
                  onBlur={() => commitVus(vuDraft)}
                  className="w-20 ui-outline border border-line px-1.5 py-0.5 text-xs font-mono font-black text-center bg-surface text-ink focus:outline-none focus:bg-primary focus:text-white"
                />
                <span className="text-[10px] font-bold">VUs</span>
                <span className="text-[10px] font-bold border border-line px-1.5 py-0.5 bg-primary text-white">
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
              className="w-full accent-primary cursor-pointer"
            />
          </div>

          {/* Duration Selector + Custom Duration */}
          <div className="space-y-2">
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
                  className={`border border-line py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    duration === d.sec
                      ? (isProd ? 'bg-primary text-white' : 'bg-primary text-white')
                      : 'bg-surface text-ink hover:bg-soft'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 pt-1">
              <span className="text-[10px] font-bold uppercase shrink-0">Custom Duration:</span>
              <input
                type="number"
                min="1"
                max="86400"
                step="1"
                value={durationDraft}
                onChange={(e) => {
                  const val = e.target.value;
                  setDurationDraft(val);
                  const parsed = Math.floor(Number(val));
                  if (val.trim() !== '' && Number.isFinite(parsed) && parsed >= 1 && parsed <= 86400) {
                    setDuration(parsed);
                  }
                }}
                onBlur={() => commitDuration(durationDraft)}
                className="w-24 ui-outline border border-line px-2 py-1 text-xs font-mono font-bold bg-surface text-ink focus:outline-none focus:bg-primary focus:text-white"
              />
              <span className="text-[10px] font-bold">sec (1–86,400)</span>
            </div>
          </div>
        </div>

        {/* Right: Circuit Breakers & Resource Budgeting */}
        <div className={`lg:col-span-6 ui-outline border border-line p-5 bg-surface space-y-4 ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div className="border-b border-line pb-2">
            <h2 className="text-sm font-black uppercase">
              2. SAFETY CIRCUIT BREAKERS &amp; GUARDS
            </h2>
          </div>

          {/* Max Error Rate Selector */}
          <div className="space-y-1">
            <label className="text-xs font-bold uppercase block">
              Rolling server-error threshold (5xx) · {effective5xx}%
            </label>
            <p className="text-[10px] opacity-75">
              Applies when at least 20 responses were received in the last 5 seconds (hard breaker cap: max 25%).
            </p>
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
                  className={`border border-line py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer ${
                    effective5xx === t.val
                      ? (isProd ? 'bg-primary text-white' : 'bg-primary text-white')
                      : 'bg-surface text-ink hover:bg-soft'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="ui-outline border border-line p-3 bg-surface space-y-1">
            <div className="text-xs font-bold uppercase">Automatic stops are always on</div>
            <p className="text-[10px] opacity-75">
              Pusher stops on a detected firewall block, 3 rate-limit responses in 3 seconds, 5 consecutive server errors, &gt;30% request timeouts, or rolling p95 ceiling breaches.
            </p>
          </div>

          {/* P95 Latency Ceiling */}
          <div className="space-y-1">
            <div className="text-xs font-bold uppercase">P95 latency ceiling · {effectiveP95.toLocaleString()} ms</div>
            {maxP95Ceiling != null && p95Ceiling > maxP95Ceiling && (
              <p className="text-[10px] font-bold text-amber-800">
                Clamped to engine ceiling of {maxP95Ceiling.toLocaleString()} ms.
              </p>
            )}
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
                  disabled={maxP95Ceiling != null && p.ms > maxP95Ceiling}
                  aria-pressed={effectiveP95 === p.ms}
                  onClick={() => setP95Ceiling(p.ms)}
                  className={`border border-line py-2 px-1 text-xs font-bold uppercase transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    effectiveP95 === p.ms
                      ? (isProd ? 'bg-primary text-white' : 'bg-primary text-white')
                      : 'bg-surface text-ink hover:bg-soft'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Cache-Busting Nonce Toggle */}
          <div className="ui-outline border border-line p-3 bg-surface flex items-center justify-between">
            <div>
              <div className="text-xs font-bold uppercase">Dynamic Cache-Busting</div>
              <div className="text-[10px] opacity-75">Append ?_cb=nonce to bypass CDN caches</div>
            </div>
            <button
              type="button"
              onClick={() => setCacheBusting(!cacheBusting)}
              className={`border border-line px-3 py-1 text-xs font-bold uppercase cursor-pointer ${
                cacheBusting
                  ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-primary text-white')
                  : 'bg-surface text-ink'
              }`}
            >
              {cacheBusting ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>

          {/* Live Resource Estimator */}
          <div className="ui-outline border border-line p-3 bg-surface text-xs space-y-1">
            <div className="font-bold uppercase border-b border-line pb-1 mb-1">
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
              <span className={isProd && maxHardwareSafeRamMb != null && ramLimitMb <= maxHardwareSafeRamMb ? 'text-emerald-700 font-bold' : ''}>
                {maxHardwareSafeRamMb == null ? 'Unavailable' : ramLimitMb <= maxHardwareSafeRamMb ? 'Within host limit' : 'Above host limit'}
              </span>
            </div>
          </div>
        </div>
      </fieldset>

      <div className="ui-outline border border-line p-3 bg-surface flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex-1 space-y-1">
          <label htmlFor="traffic-project-name" className="text-xs font-bold uppercase flex items-center gap-2">
            <span>Project Name Before Launch:</span>
            {projectName && projectNameSource && (
              <span className="border border-line px-1.5 py-0.2 text-[9px] font-bold uppercase bg-soft">
                {projectNameSource === 'custom' ? 'Custom' : 'Auto-detected'}
              </span>
            )}
          </label>
          <input
            id="traffic-project-name"
            type="text"
            maxLength={80}
            value={projectName}
            onChange={(e) => setProjectName?.(e.target.value)}
            onBlur={() => onSaveProjectName?.()}
            placeholder="e.g. Veribite API or My Web App"
            className="w-full ui-outline border border-line px-2.5 py-1.5 text-xs font-mono bg-surface text-ink focus:outline-none"
          />
        </div>
      </div>

      {/* Bottom Action Ribbon */}
      {trafficSaveError && <p role="alert" className="text-xs font-bold text-rose-800">{trafficSaveError}</p>}
      {launchError && <p role="alert" className="text-xs font-bold text-rose-800">{launchError}</p>}
      {trafficLaunchBlocker && <p role="status" className="text-xs font-bold">{trafficLaunchBlocker}</p>}
      <div className="border-t border-line pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={handleSaveTraffic}
          disabled={trafficSaving || trafficLoading}
          className="border border-line py-3 px-4 text-xs font-bold uppercase hover:bg-primary hover:text-white transition-colors cursor-pointer text-center"
        >
          SAVE PROFILE &amp; RETURN TO DASHBOARD
        </button>
        <button
          type="button"
          onClick={handleStartTest}
          disabled={Boolean(trafficLaunchBlocker)}
          className={`border border-line py-3 px-4 text-xs font-black uppercase transition-colors text-center tracking-wider ${
            !trafficLaunchBlocker
              ? (isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer' : 'bg-primary text-white hover:bg-surface hover:text-ink cursor-pointer')
              : 'bg-surface text-ink opacity-40 cursor-not-allowed'
          }`}
        >
          SAVE &amp; LAUNCH LOAD TEST
        </button>
      </div>
    </div>
  );
}

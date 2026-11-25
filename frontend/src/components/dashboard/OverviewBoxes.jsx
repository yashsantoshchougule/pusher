import React from 'react';
import { ArrowRight, Play, Square as StopSquare, Zap, Layers, AlertTriangle } from 'lucide-react';

export default function OverviewBoxes({
  targetUrl,
  isVerified,
  guardToken,
  guardTimerSeconds,
  formatTimer,
  ssrfCheck,
  latestScorecard,
  latestRunSummary = null,
  modeLabel,
  vus,
  duration,
  estimatedRam,
  ramLimitMb,
  effectiveP95Ceiling = 1500,
  max5xxThreshold = 5,
  hasUnsavedTraffic = false,
  trafficCapacityError = '',
  journeyStepsCount,
  journeySelectionKnown = true,
  sameProcessLoopback = false,
  loopbackAdvisory = '',
  testRunning,
  canStart,
  statusUnavailable,
  stopping,
  elapsed,
  telemetry = {},
  runMeta = {},
  stepMetrics = [],
  useJourney,
  handleStartTest,
  handleStopTest,
  stopError,
  launchError,
  launching,
  handleSimulateSpike,
  onInspectRun,
  outcomeDismissed = false,
  onDismissOutcome,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';

  // Box 2 dynamic verdict & health evaluation
  const scVerdict = (latestScorecard?.verdict || '').toUpperCase();
  const isScFailed = scVerdict === 'CIRCUIT_BREAKER' || scVerdict === 'FAILED';
  const isScAborted = scVerdict === 'MANUAL_ABORT';
  const scorecardCeiling = latestScorecard?.effective_p95_ceiling_ms ?? latestScorecard?.p95_ceiling_ms ?? effectiveP95Ceiling ?? 1500;
  const scP95 = latestScorecard?.p95_ms;
  const scErr = latestScorecard?.error_pct;

  const scHealthLabel = scP95 == null
    ? 'Not Measured'
    : (isScFailed || (scorecardCeiling > 0 && scP95 > scorecardCeiling))
    ? 'Ceiling Breached'
    : (isScAborted || (scorecardCeiling > 0 && scP95 > 0.8 * scorecardCeiling) || (scErr ?? 0) > 2)
    ? 'Degraded'
    : 'Healthy';

  const scTileBorder = isProd
    ? (isScFailed ? 'border-t-4 border-t-rose-600' : isScAborted ? 'border-t-4 border-t-amber-500' : 'border-t-4 border-t-teal-700')
    : '';

  const scVerdictBadgeClass = isProd
    ? (isScFailed
      ? 'bg-rose-100 text-rose-800 border-rose-400'
      : isScAborted
      ? 'bg-amber-100 text-amber-900 border-amber-400'
      : 'bg-emerald-100 text-emerald-800 border-emerald-400')
    : 'bg-white text-black border-black';

  const headerBreakerSource = testRunning
    ? (telemetry?.circuitBreaker || 'ARMED')
    : (latestRunSummary?.verdict || scVerdict || 'CIRCUIT BREAKER: ARMED');
  const headerBadgeText = testRunning
    ? `CIRCUIT BREAKER: ${headerBreakerSource}`
    : (latestRunSummary?.verdict || scVerdict)
    ? `LAST RUN: ${latestRunSummary?.verdict || scVerdict}`
    : 'CIRCUIT BREAKER: ARMED';
  const headerBadgeIsAlert = /TRIPPED|CIRCUIT_BREAKER|FAILED|AUTO|STOPPED/i.test(headerBreakerSource);
  const headerBadgeIsWarn = !headerBadgeIsAlert && /ABORT/i.test(headerBreakerSource);
  const headerBadgeClass = isProd
    ? (headerBadgeIsAlert
      ? 'bg-rose-100 text-rose-800 border-rose-400'
      : headerBadgeIsWarn
      ? 'bg-amber-100 text-amber-900 border-amber-400'
      : (latestRunSummary?.verdict || scVerdict) === 'PASSED'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-400'
      : 'bg-amber-100 text-amber-900 border-amber-400')
    : 'bg-white text-black';

  // Box 2 Staged Profile status
  const emptyJourneyBlocked = Boolean(useJourney && journeySelectionKnown && journeyStepsCount === 0);
  const stagedBlocked = Boolean(trafficCapacityError) || emptyJourneyBlocked || Boolean(useJourney && !journeySelectionKnown);
  const stagedStatus = hasUnsavedTraffic ? 'UNSAVED' : stagedBlocked ? 'BLOCKED' : 'READY';
  const stagedStatusClass = isProd
    ? (stagedStatus === 'UNSAVED'
      ? 'bg-amber-50 text-amber-900 border-amber-400 font-bold'
      : stagedStatus === 'BLOCKED'
      ? 'bg-rose-50 text-rose-800 border-rose-400 font-bold'
      : 'bg-emerald-50 text-emerald-800 border-emerald-400 font-bold')
    : 'font-bold';

  // Box 3 live ceilings & breaker badge
  const p95Cap = runMeta?.effectiveP95CeilingMs ?? runMeta?.p95CeilingMs ?? effectiveP95Ceiling ?? 1500;
  const errCap = runMeta?.effectiveMaxErrorPct ?? runMeta?.maxErrorPct ?? max5xxThreshold ?? 5;
  const activeBreakerText = testRunning ? (telemetry?.circuitBreaker || 'ARMED') : 'ARMED';
  const breakerAlert = testRunning && (/TRIPPED|AUTO|FAILED/i.test(activeBreakerText));
  const breakerWarn = testRunning && !breakerAlert && /STOPPED/i.test(activeBreakerText);

  // Post-run outcome banner when idle & last run ended tripped/aborted/failed
  const lastCircuitStatus = runMeta?.lastCircuitStatus;
  const lastCircuitTripped = Boolean(lastCircuitStatus && !/^ARMED\b/i.test(lastCircuitStatus));
  const latestRunNonPassed = Boolean(
    latestRunSummary?.verdict && ['CIRCUIT_BREAKER', 'FAILED', 'MANUAL_ABORT'].includes(latestRunSummary.verdict)
  );
  const postRunBannerReason = !testRunning && !outcomeDismissed
    ? (lastCircuitTripped
      ? lastCircuitStatus
      : latestRunNonPassed
      ? (latestRunSummary.status_label || latestRunSummary.verdict)
      : '')
    : '';
  const postRunId = runMeta?.runId || latestRunSummary?.run_id || null;

  // Compact status breakdown visibility
  const totalReqs = runMeta?.totalRequests ?? 0;
  const showStatusBreakdown = Boolean(testRunning || totalReqs > 0);
  const timeoutCount = runMeta?.timeoutCount ?? 0;
  const netAndOtherCount = (runMeta?.networkErrorCount ?? 0) + (runMeta?.statusOther ?? 0) + (runMeta?.status3xx ?? 0) + (runMeta?.status4xx ?? 0);

  const startDisabled = !isVerified || Boolean(trafficCapacityError) || emptyJourneyBlocked || Boolean(useJourney && !journeySelectionKnown);
  const startDisabledNote = !isVerified
    ? ''
    : trafficCapacityError
    ? trafficCapacityError
    : emptyJourneyBlocked
    ? 'Add journey steps in API Journey Builder.'
    : (useJourney && !journeySelectionKnown)
    ? 'Waiting for journey configuration.'
    : '';

  return (
    <div className="space-y-6">
      {/* Top Row: Box 1 & Box 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* BOX 1: ACTIVE TARGET & 48H GUARD STATUS (Top-Left Read-Only) */}
        <div className={`lg:col-span-6 border-2 border-black p-4 sm:p-5 bg-white flex flex-col justify-between ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div>
            <div className="flex items-center justify-between border-b-2 border-black pb-2 mb-4">
              <h2 className="text-sm sm:text-base font-black uppercase tracking-wider">
                BOX 1: ACTIVE TARGET STATUS
              </h2>
              <span
                className={`border border-black px-2 py-0.5 text-xs font-bold uppercase ${
                  isVerified
                    ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                    : (isProd ? 'bg-rose-100 text-rose-800 border-rose-400' : 'bg-white text-black')
                }`}
              >
                {isVerified ? 'VERIFIED' : 'EXPIRED / LOCKED'}
              </span>
            </div>

            {/* Read-Only Details */}
            {!isVerified && !targetUrl ? (
              <div className="border-2 border-dashed border-black p-4 text-center mb-4 bg-gray-50 flex flex-col items-center justify-center">
                <div className="text-xs font-black uppercase tracking-wider text-black">
                  NO VERIFIED TARGET
                </div>
                <div className="text-[10px] opacity-75 mt-1 font-bold">
                  GO TO 2. VERIFY TARGET TO CONFIGURE ORIGIN
                </div>
              </div>
            ) : (
              <div className="space-y-2 mb-4 text-xs font-mono">
                <div className="border border-black p-2.5 bg-white flex justify-between items-center">
                  <span className="font-bold uppercase">Active Domain:</span>
                  <span className="font-bold truncate max-w-[240px]">{targetUrl || 'NONE (UNCONFIGURED)'}</span>
                </div>
                <div className="border border-black p-2.5 bg-white flex justify-between items-center">
                  <span className="font-bold uppercase">Guard Token:</span>
                  <span className="font-bold">{isVerified ? guardToken : 'NONE (REVOKED)'}</span>
                </div>
                <div className="border border-black p-2.5 bg-white flex justify-between items-center">
                  <span className="font-bold uppercase">SSRF Check:</span>
                  <span className={`font-bold border border-black px-1.5 py-0.5 text-[10px] ${
                    ssrfCheck?.valid
                      ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                      : (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-black text-white')
                  }`}>
                    {ssrfCheck?.valid ? 'PASSED' : 'BLOCKED'}
                  </span>
                </div>
              </div>
            )}

            {/* 48-Hour Live Countdown Banner */}
            <div className={`border-2 border-black p-3 mb-4 bg-white ${
              isProd && isVerified ? 'border-l-4 border-l-emerald-600' : ''
            }`}>
              <div className="text-[11px] font-bold uppercase tracking-wider mb-1 flex items-center justify-between">
                <span>48-Hour Guard Expiry Countdown:</span>
                <span className="text-[10px] font-bold">INTERVAL: 1s TICK</span>
              </div>
              <div className={`text-2xl sm:text-3xl font-black tracking-widest ${
                isProd && !isVerified ? 'text-rose-600' : ''
              }`}>
                {isVerified ? (formatTimer ? formatTimer(guardTimerSeconds) : `${guardTimerSeconds ?? 0}s`) : '00:00:00 (EXPIRED)'}
              </div>
              <div className="text-[10px] opacity-75 mt-1">
                Cryptographic DNS/HMAC probe armed. Re-verify in wizard when expired.
              </div>
            </div>
          </div>

          {/* Single Bottom Trigger Button */}
          <div className="pt-2 border-t-2 border-black">
            <button
              type="button"
              onClick={() => setActiveNav('verify')}
              className="w-full border-2 border-black py-2.5 px-3 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center justify-center gap-2 tracking-wider"
            >
              <span>MANAGE TARGET IN VERIFY WIZARD</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* BOX 2: CAPACITY SCORECARD & STAGED PROFILE (Top-Right Read-Only) */}
        <div className={`lg:col-span-6 border-2 border-black p-4 sm:p-5 bg-white flex flex-col justify-between ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div>
            <div className="flex items-center justify-between border-b-2 border-black pb-2 mb-4 gap-2">
              <h2 className="text-sm sm:text-base font-black uppercase tracking-wider">
                BOX 2: CAPACITY SCORECARD &amp; STAGED PROFILE
              </h2>
              <span className={`border border-black px-2 py-0.5 text-[10px] sm:text-xs font-bold uppercase shrink-0 ${headerBadgeClass}`}>
                {headerBadgeText}
              </span>
            </div>

            {/* 3 Read-Only KPI Mini-Boxes or Empty State */}
            {!latestScorecard ? (
              <div className="border-2 border-dashed border-black p-5 text-center mb-4 bg-gray-50 flex flex-col items-center justify-center min-h-[90px]">
                <div className="text-xs font-black uppercase tracking-wider text-black">
                  NO COMPLETED RUNS IN DATABASE
                </div>
                <div className="text-[10px] opacity-75 mt-1 font-bold">
                  RUN A LOAD TEST TO GENERATE SCORECARD
                </div>
              </div>
            ) : (
              <div className="space-y-2 mb-4">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className={`border-2 border-black p-2.5 bg-white ${scTileBorder}`}>
                    <div className="text-[10px] font-bold uppercase">RECOMMENDED LOAD</div>
                    <div className="text-lg sm:text-xl font-black mt-1">
                      {latestScorecard.knee_vus > 0 ? `${latestScorecard.knee_vus} VUs` : 'Capacity unavailable'}
                    </div>
                    {latestScorecard.capacity_reason && (
                      <div className="text-[9px] opacity-75 mt-0.5 leading-tight">{latestScorecard.capacity_reason}</div>
                    )}
                  </div>
                  <div className={`border-2 border-black p-2.5 bg-white ${scTileBorder}`}>
                    <div className="text-[10px] font-bold uppercase">PEAK RPS</div>
                    <div className="text-lg sm:text-xl font-black mt-1">
                      {Number(latestScorecard.peak_rps ?? 0).toLocaleString()} RPS
                    </div>
                    <div className="text-[9px] opacity-75">Max Throughput</div>
                  </div>
                  <div className={`border-2 border-black p-2.5 bg-white ${scTileBorder}`}>
                    <div className="text-[10px] font-bold uppercase">P95 LATENCY</div>
                    <div className="text-lg sm:text-xl font-black mt-1">
                      {scP95 == null ? 'Unavailable' : `${scP95} ms`}
                    </div>
                    <div className={`text-[9px] mt-0.5 font-bold ${
                      isProd && scHealthLabel === 'Ceiling Breached' ? 'text-rose-700' : isProd && scHealthLabel === 'Degraded' ? 'text-amber-700' : 'opacity-75'
                    }`}>
                      {scHealthLabel}
                    </div>
                  </div>
                </div>

                {(scVerdict || scErr != null || latestScorecard.elapsed_sec != null) && (
                  <div className="border border-black px-2.5 py-1.5 bg-gray-50 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono">
                    <div className="flex items-center gap-2">
                      {scVerdict && (
                        <span className={`border px-1.5 py-0.2 font-bold uppercase ${scVerdictBadgeClass}`}>
                          {scVerdict}
                        </span>
                      )}
                      {latestScorecard.run_id && <span className="font-bold">{latestScorecard.run_id}</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      {scErr != null && <span>Error: <strong>{scErr}%</strong></span>}
                      {latestScorecard.elapsed_sec != null && <span>Elapsed: <strong>{latestScorecard.elapsed_sec}s</strong></span>}
                    </div>
                  </div>
                )}

                {latestRunSummary?.run_id && latestRunSummary.run_id !== latestScorecard.run_id && latestRunSummary.verdict && latestRunSummary.verdict !== 'PASSED' && (
                  <div className={`border px-2.5 py-1.5 text-[10px] font-mono ${
                    isProd ? 'border-rose-400 bg-rose-50 text-rose-900' : 'border-black bg-white'
                  }`}>
                    Latest run <strong>{latestRunSummary.run_id}</strong> ended <strong>{latestRunSummary.verdict}</strong>
                    {latestRunSummary.error_pct != null ? ` (${latestRunSummary.error_pct}% err` : ''}
                    {latestRunSummary.p95_ms != null ? `, ${latestRunSummary.p95_ms} ms p95)` : latestRunSummary.error_pct != null ? ')' : ''}.
                  </div>
                )}
              </div>
            )}

            {/* Staged Config Summary Box */}
            <div className="border-2 border-black p-3 mb-4 bg-white text-xs">
              <div className="font-bold uppercase border-b border-black pb-1 mb-2 flex justify-between items-center">
                <span>STAGED TRAFFIC PROFILE:</span>
                <span className={`text-[10px] border border-black px-1.5 py-0.2 ${stagedStatusClass}`}>
                  {stagedStatus}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-y-1 text-[11px]">
                <div><span className="font-bold">Mode:</span> {modeLabel}</div>
                <div><span className="font-bold">Concurrency:</span> {vus} VUs</div>
                <div><span className="font-bold">Duration:</span> {duration}s</div>
                <div>
                  <span className="font-bold">Est. RAM:</span>{' '}
                  {estimatedRam == null
                    ? 'Unavailable'
                    : `${estimatedRam} MB (${estimatedRam <= ramLimitMb ? '<=' : '>'} ${ramLimitMb} MB)`}
                </div>
                <div><span className="font-bold">P95 Ceiling:</span> {Number(effectiveP95Ceiling).toLocaleString()} ms</div>
                <div><span className="font-bold">5xx Limit:</span> {max5xxThreshold}%</div>
              </div>
              {sameProcessLoopback && vus > 50 && (
                <div className={`mt-2 border p-1.5 text-[10px] font-mono ${
                  isProd ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-black bg-white'
                }`}>
                  {loopbackAdvisory || `Loopback advisory: ${vus} VUs against a local/sandbox target competes for the same host CPU above ~50 VUs.`}
                </div>
              )}
            </div>
          </div>

          {/* Staged Traffic Profile Action */}
          <div className="pt-2 border-t-2 border-black flex gap-2">
            <button
              type="button"
              onClick={() => setActiveNav('traffic')}
              className="flex-1 border-2 border-black py-2.5 px-3 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center justify-center gap-1.5 tracking-wider"
            >
              <span>ADJUST PROFILE IN TRAFFIC SETUP</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setActiveNav('reports')}
              className={`border-2 border-black py-2.5 px-3 text-xs font-bold uppercase transition-colors cursor-pointer ${
                isProd ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-black text-white hover:bg-white hover:text-black'
              }`}
            >
              REPORTS →
            </button>
          </div>
        </div>
      </div>

      {/* BOX 3: LIVE TELEMETRY STREAM & TELEMETRY CONTROLS (Full-Width Bottom Box) */}
      <div className={`border-2 border-black p-4 sm:p-5 bg-white space-y-4 ${
        isProd ? 'shadow-sm' : ''
      }`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b-2 border-black pb-3 gap-2">
          <div>
            <h2 className="text-base font-black uppercase tracking-wider flex items-center gap-2">
              <span className={`inline-block w-3 h-3 border-2 border-black ${
                testRunning
                  ? (isProd ? 'bg-emerald-500 animate-ping' : 'bg-black animate-ping')
                  : 'bg-white'
              }`} />
              <span>BOX 3: LIVE TELEMETRY STREAM &amp; EXECUTION</span>
            </h2>
            <p className="text-xs opacity-75">
              Real-time metrics sampled at 1s intervals. Circuit breaker monitors 429/5xx rates, rolling p95 ceiling, &gt;30% timeouts, WAF 403 blocks, RAM budget &amp; guard expiry.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase">Elapsed:</span>
            <span className="border-2 border-black px-2.5 py-1 text-sm font-black bg-white">
              {String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')} / {String(Math.floor(duration / 60)).padStart(2, '0')}:{String(duration % 60).padStart(2, '0')}
            </span>
          </div>
        </div>

        {/* 6 Real-Time Telemetry KPI Tiles */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">CURRENT VUs</div>
            <div className="text-xl sm:text-2xl font-black mt-1">{telemetry.currentVus ?? 0}</div>
            <div className="text-[9px] opacity-75">Target: {vus}</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">LIVE RPS</div>
            <div className="text-xl sm:text-2xl font-black mt-1">
              {Number(telemetry.liveRps ?? 0).toLocaleString()}
            </div>
            <div className="text-[9px] opacity-75">Req/sec</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">P95 LATENCY</div>
            <div className={`text-xl sm:text-2xl font-black mt-1 ${
              isProd && (telemetry.p95Latency ?? 0) >= p95Cap
                ? 'text-rose-600'
                : isProd && (telemetry.p95Latency ?? 0) >= 0.8 * p95Cap
                ? 'text-amber-600'
                : ''
            }`}>
              {telemetry.p95Latency ?? 0} ms
            </div>
            <div className="text-[9px] opacity-75">Ceiling: {Number(p95Cap).toLocaleString()} ms</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">ERROR RATE</div>
            <div className={`text-xl sm:text-2xl font-black mt-1 ${
              (telemetry?.errorRate || 0) > 0
                ? (isProd ? 'text-rose-600' : 'text-black')
                : (isProd ? 'text-emerald-600' : 'text-black')
            }`}>
              {(Number(telemetry?.errorRate || 0)).toFixed(1)}%
            </div>
            <div className="text-[9px] opacity-75">5xx Limit: {errCap}% · All errors shown</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">CIRCUIT BREAKER</div>
            <div className={`text-xs font-black mt-2 border border-black px-1 py-0.5 uppercase ${
              breakerAlert
                ? (isProd ? 'bg-rose-600 text-white' : 'bg-black text-white')
                : breakerWarn
                ? (isProd ? 'bg-amber-100 text-amber-900' : 'bg-white text-black')
                : (isProd ? 'bg-emerald-100 text-emerald-800' : 'bg-white text-black')
            }`}>
              {activeBreakerText}
            </div>
            <div className="text-[9px] opacity-75 mt-1">Automatic safety stops</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">DISCARDED STREAM</div>
            <div className="text-xl sm:text-2xl font-black mt-1">{telemetry.bytesDiscardedMb ?? 0} MB</div>
            <div className="text-[9px] opacity-75">4KB Chunk Discard</div>
          </div>
        </div>

        {/* Compact Status Breakdown Bar */}
        {showStatusBreakdown && (
          <div className="border border-black p-2.5 bg-gray-50 flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono">
            <span className="font-bold uppercase">Request Breakdown:</span>
            <div className="flex flex-wrap items-center gap-3">
              <span>Total: <strong>{totalReqs.toLocaleString()}</strong></span>
              <span className={isProd ? 'text-emerald-800' : ''}>2xx: <strong>{(runMeta.status2xx ?? 0).toLocaleString()}</strong></span>
              <span className={isProd && (runMeta.status429 ?? 0) > 0 ? 'text-amber-800 font-bold' : ''}>429: <strong>{(runMeta.status429 ?? 0).toLocaleString()}</strong></span>
              <span className={isProd && (runMeta.status5xx ?? 0) > 0 ? 'text-rose-700 font-bold' : ''}>5xx: <strong>{(runMeta.status5xx ?? 0).toLocaleString()}</strong></span>
              <span className={isProd && timeoutCount > 0 ? 'text-rose-700 font-bold' : ''}>Timeouts: <strong>{timeoutCount.toLocaleString()}</strong></span>
              <span className={isProd && netAndOtherCount > 0 ? 'text-amber-800 font-bold' : ''}>Net/Other: <strong>{netAndOtherCount.toLocaleString()}</strong></span>
              {runMeta.loopLagMs != null && testRunning && (
                <span>Loop Lag: <strong>{runMeta.loopLagMs} ms</strong></span>
              )}
            </div>
          </div>
        )}

        {/* Post-run tripped / aborted outcome banner */}
        {postRunBannerReason && (
          <div role="status" className={`border-2 p-3 flex flex-wrap items-center justify-between gap-2 text-xs font-mono ${
            isProd ? 'border-rose-500 bg-rose-50 text-rose-900' : 'border-black bg-white text-black'
          }`}>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>
                <strong>Previous run ended:</strong> {postRunBannerReason}
                {postRunId ? ` (${postRunId})` : ''}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {postRunId && onInspectRun && (
                <button
                  type="button"
                  onClick={() => onInspectRun(postRunId)}
                  className="border border-current px-2 py-0.5 text-[10px] font-bold uppercase cursor-pointer hover:opacity-80"
                >
                  Inspect Report
                </button>
              )}
              {onDismissOutcome && (
                <button
                  type="button"
                  onClick={() => onDismissOutcome(postRunId || postRunBannerReason)}
                  className="border border-current px-2 py-0.5 text-[10px] font-bold uppercase cursor-pointer hover:opacity-80"
                >
                  Dismiss
                </button>
              )}
            </div>
          </div>
        )}

        {/* Start / Stop & Fault Injection Controls */}
        <div className="border-t-2 border-black pt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            {!testRunning && !canStart ? (
              <p role="status" className="text-xs">
                {launching ? 'Starting load test…' : statusUnavailable ? 'Run status unavailable. Retrying…' : 'Checking run status…'}
              </p>
            ) : !testRunning ? (
              <button
                type="button"
                onClick={handleStartTest}
                disabled={startDisabled}
                className={`flex-1 sm:flex-none border-2 border-black px-6 py-2.5 text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${
                  !startDisabled
                    ? (isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700 cursor-pointer' : 'bg-black text-white hover:bg-white hover:text-black cursor-pointer')
                    : 'bg-white text-black opacity-40 cursor-not-allowed'
                }`}
              >
                <Play className="w-4 h-4" />
                <span>START LOAD TEST NOW</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStopTest}
                disabled={stopping}
                className={`flex-1 sm:flex-none border-2 border-black px-6 py-2.5 text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-colors cursor-pointer ${
                  isProd ? 'bg-rose-600 text-white hover:bg-rose-700' : 'bg-black text-white hover:bg-white hover:text-black'
                }`}
              >
                <StopSquare className="w-4 h-4" />
                <span>{stopping ? 'Stopping…' : 'ABORT LOAD TEST (USER STOP)'}</span>
              </button>
            )}
            {stopError && <p role="alert" className="text-sm text-red-700">{stopError}</p>}
            {launchError && <p role="alert" className="text-sm text-red-700">{launchError}</p>}
            {!launchError && !testRunning && canStart && startDisabledNote && (
              <p role="status" className="text-xs font-bold text-rose-700">{startDisabledNote}</p>
            )}

            <button
              type="button"
              onClick={handleSimulateSpike}
              disabled={!testRunning}
              className={`border-2 border-black px-4 py-2.5 text-xs font-bold uppercase transition-colors flex items-center gap-1.5 ${
                testRunning
                  ? (isProd ? 'bg-amber-500 text-black hover:bg-amber-600 cursor-pointer' : 'bg-black text-white hover:bg-white hover:text-black cursor-pointer')
                  : 'bg-white text-black opacity-40 cursor-not-allowed'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Simulate 429/5xx Spike (Test Auto-Abort)</span>
            </button>
          </div>
        </div>

        {/* Multi-Step Journey Step Telemetry Table */}
        {useJourney && (
          <div className="border-2 border-black p-3.5 bg-white space-y-2 font-mono">
            <div className="flex items-center justify-between border-b border-black pb-1.5">
              <span className="font-bold text-xs uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                <span>MULTI-STEP JOURNEY STEP TELEMETRY</span>
                <span className="text-[10px] opacity-70 font-normal">(4 KB Chunk-Discard Enforced)</span>
              </span>
              <span className={`border border-black px-1.5 py-0.5 text-[10px] font-bold ${
                isProd && testRunning ? 'bg-emerald-600 text-white' : 'bg-black text-white'
              }`}>
                {testRunning ? 'STREAMING' : 'CONFIGURED'}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-[11px]">
                <thead>
                  <tr className="border-b-2 border-black">
                    <th className="py-1 px-1.5">STEP</th>
                    <th className="py-1 px-1.5">METHOD</th>
                    <th className="py-1 px-1.5">PATH</th>
                    <th className="py-1 px-1.5 text-right">REQS</th>
                    <th className="py-1 px-1.5 text-right">PASS</th>
                    <th className="py-1 px-1.5 text-right">FAIL</th>
                    <th className="py-1 px-1.5 text-right">AVG (MS)</th>
                    <th className="py-1 px-1.5 text-center">LAST HTTP</th>
                  </tr>
                </thead>
                <tbody>
                  {(!stepMetrics || stepMetrics.length === 0) ? (
                    <tr>
                      <td colSpan={8} className="py-3 text-center opacity-70">
                        No step telemetry recorded yet. Start run or configure steps in API Builder.
                      </td>
                    </tr>
                  ) : (
                    stepMetrics.map((sm, idx) => (
                      <tr key={sm.step_id || idx} className="border-b border-black/30 hover:bg-black/5">
                        <td className="py-1 px-1.5 font-bold">{sm.name || `Step ${idx + 1}`}</td>
                        <td className="py-1 px-1.5">
                          <span className={`border border-black px-1 py-0.2 text-[9px] font-bold ${
                            sm.method === 'POST'
                              ? (isProd ? 'bg-teal-700 text-white' : 'bg-black text-white')
                              : 'bg-white text-black'
                          }`}>
                            {sm.method}
                          </span>
                        </td>
                        <td className="py-1 px-1.5 font-mono text-[10px] truncate max-w-[200px]">{sm.path}</td>
                        <td className="py-1 px-1.5 text-right font-bold">{sm.requests ?? 'Unavailable'}</td>
                        <td className={`py-1 px-1.5 text-right font-bold ${isProd ? 'text-emerald-700' : ''}`}>
                          {sm.passed ?? 'Unavailable'}
                        </td>
                        <td className={`py-1 px-1.5 text-right font-bold ${
                          sm.failed > 0 ? (isProd ? 'text-rose-600' : 'text-black') : ''
                        }`}>
                          {sm.failed ?? 'Unavailable'}
                        </td>
                        <td className="py-1 px-1.5 text-right">
                          {sm.requests > 0 && Number.isFinite(sm.avg_latency_ms) ? sm.avg_latency_ms : 'Unavailable'}
                        </td>
                        <td className="py-1 px-1.5 text-center">
                          <span className={`border px-1.5 py-0.5 text-[9px] font-bold ${
                            !sm.last_status
                              ? 'bg-gray-100 text-black/70 border-black/40'
                              : sm.last_status >= 200 && sm.last_status < 400
                              ? (isProd ? 'bg-emerald-600 text-white border-black' : 'bg-black text-white border-black')
                              : (isProd ? 'bg-rose-600 text-white border-black' : 'bg-white text-black border-black')
                          }`}>
                            {sm.last_status || '---'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

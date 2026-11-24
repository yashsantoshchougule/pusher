import React from 'react';
import { ArrowRight, Play, Square as StopSquare, Zap, AlertTriangle, Layers } from 'lucide-react';

export default function OverviewBoxes({
  targetUrl,
  isVerified,
  guardToken,
  guardTimerSeconds,
  formatTimer,
  ssrfCheck,
  latestScorecard,
  modeLabel,
  vus,
  duration,
  estimatedRam,
  ramLimitMb,
  testRunning,
  canStart,
  statusUnavailable,
  stopping,
  elapsed,
  telemetry,
  stepMetrics,
  useJourney,
  handleStartTest,
  handleStopTest,
  stopError,
  launchError,
  launching,
  handleSimulateSpike,
  setActiveNav,
  themeMode = 'production',
}) {
  const isProd = themeMode === 'production';

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
                    ssrfCheck.valid
                      ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                      : (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-black text-white')
                  }`}>
                    {ssrfCheck.valid ? 'PASSED' : 'BLOCKED'}
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
                {isVerified ? formatTimer(guardTimerSeconds) : '00:00:00 (EXPIRED)'}
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
            <div className="flex items-center justify-between border-b-2 border-black pb-2 mb-4">
              <h2 className="text-sm sm:text-base font-black uppercase tracking-wider">
                BOX 2: CAPACITY SCORECARD &amp; STAGED PROFILE
              </h2>
              <span className={`border border-black px-2 py-0.5 text-xs font-bold uppercase ${
                isProd ? 'bg-amber-100 text-amber-900 border-amber-400' : 'bg-white'
              }`}>
                CIRCUIT BREAKER: ARMED
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
              <div className="grid grid-cols-3 gap-2 mb-4 text-center">
                <div className={`border-2 border-black p-2.5 bg-white ${
                  isProd ? 'border-t-4 border-t-teal-700' : ''
                }`}>
                  <div className="text-[10px] font-bold uppercase">RECOMMENDED LOAD</div>
                  <div className="text-lg sm:text-xl font-black mt-1">
                    {latestScorecard.knee_vus > 0 ? `${latestScorecard.knee_vus} VUs` : 'Capacity unavailable'}
                  </div>
                </div>
                <div className={`border-2 border-black p-2.5 bg-white ${
                  isProd ? 'border-t-4 border-t-teal-700' : ''
                }`}>
                  <div className="text-[10px] font-bold uppercase">PEAK RPS</div>
                  <div className="text-lg sm:text-xl font-black mt-1">
                    {Number(latestScorecard.peak_rps).toLocaleString()} RPS
                  </div>
                  <div className="text-[9px] opacity-75">Max Throughput</div>
                </div>
                <div className={`border-2 border-black p-2.5 bg-white ${
                  isProd ? 'border-t-4 border-t-teal-700' : ''
                }`}>
                  <div className="text-[10px] font-bold uppercase">P95 LATENCY</div>
                  <div className="text-lg sm:text-xl font-black mt-1">
                    {latestScorecard.p95_ms == null ? 'Unavailable' : `${latestScorecard.p95_ms} ms`}
                  </div>
                  <div className="text-[9px] opacity-75">Optimal Health</div>
                </div>
              </div>
            )}

            {/* Staged Config Summary Box */}
            <div className="border-2 border-black p-3 mb-4 bg-white text-xs">
              <div className="font-bold uppercase border-b border-black pb-1 mb-2 flex justify-between items-center">
                <span>STAGED TRAFFIC PROFILE:</span>
                <span className={`text-[10px] border border-black px-1 ${
                  isProd ? 'bg-emerald-50 text-emerald-800 border-emerald-400 font-bold' : ''
                }`}>READY</span>
              </div>
              <div className="grid grid-cols-2 gap-y-1 text-[11px]">
                <div><span className="font-bold">Mode:</span> {modeLabel}</div>
                <div><span className="font-bold">Concurrency:</span> {vus} VUs</div>
                <div><span className="font-bold">Duration:</span> {duration}s</div>
                <div><span className="font-bold">Est. RAM:</span> {estimatedRam} MB (&lt; {ramLimitMb} MB)</div>
              </div>
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
              Real-time metrics sampled at 1s intervals. Circuit breaker monitors 429/5xx rates and auto-aborts.
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
            <div className="text-xl sm:text-2xl font-black mt-1">{telemetry.currentVus}</div>
            <div className="text-[9px] opacity-75">Target: {vus}</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">LIVE RPS</div>
            <div className="text-xl sm:text-2xl font-black mt-1">
              {Number(telemetry.liveRps).toLocaleString()}
            </div>
            <div className="text-[9px] opacity-75">Req/sec</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">P95 LATENCY</div>
            <div className={`text-xl sm:text-2xl font-black mt-1 ${
              isProd && telemetry.p95Latency > 500 ? 'text-amber-600' : ''
            }`}>
              {telemetry.p95Latency} ms
            </div>
            <div className="text-[9px] opacity-75">Ceiling: 2,000ms</div>
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
            <div className="text-[9px] opacity-75">Threshold: 5.0%</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">CIRCUIT BREAKER</div>
            <div className={`text-xs font-black mt-2 border border-black px-1 py-0.5 uppercase ${
              (telemetry?.circuitBreaker || '').includes('TRIPPED') || (telemetry?.circuitBreaker || '').includes('AUTO')
                ? (isProd ? 'bg-rose-600 text-white' : 'bg-black text-white')
                : (isProd ? 'bg-emerald-100 text-emerald-800' : 'bg-white text-black')
            }`}>
              {telemetry?.circuitBreaker || 'ARMED'}
            </div>
            <div className="text-[9px] opacity-75 mt-1">Automatic safety stops</div>
          </div>
          <div className="border-2 border-black p-3 bg-white text-center">
            <div className="text-[10px] font-bold uppercase">DISCARDED STREAM</div>
            <div className="text-xl sm:text-2xl font-black mt-1">{telemetry.bytesDiscardedMb} MB</div>
            <div className="text-[9px] opacity-75">4KB Chunk Discard</div>
          </div>
        </div>

        {/* Start / Stop & Fault Injection Controls */}
        <div className="border-t-2 border-black pt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            {!testRunning && !canStart ? (
              <p role="status" className="text-xs">
                {launching ? 'Starting load test…' : statusUnavailable ? 'Run status unavailable. Retrying…' : 'Checking run status…'}
              </p>
            ) : !testRunning ? (
              <button
                type="button"
                onClick={handleStartTest}
                disabled={!isVerified}
                className={`flex-1 sm:flex-none border-2 border-black px-6 py-2.5 text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${
                  isVerified
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
        {(useJourney || (stepMetrics && stepMetrics.length > 0)) && (
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
                  {stepMetrics.map((sm, idx) => (
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
                        <span className={`border border-current px-1.5 py-0.5 text-[9px] font-bold ${
                          sm.last_status && sm.last_status >= 200 && sm.last_status < 400
                            ? (isProd ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                            : (isProd ? 'bg-rose-600 text-white' : 'bg-white text-black')
                        }`}>
                          {sm.last_status || '---'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

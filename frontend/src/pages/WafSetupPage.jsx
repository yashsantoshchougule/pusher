import { operatorFetch } from '../lib/operatorApi';
import React, { useState, useEffect } from 'react';
import {
  Shield,
  ArrowLeft,
  Zap,
  Terminal,
  AlertTriangle,
  ChevronRight
} from 'lucide-react';

export default function WafSetupPage({ onBack, appearance = 'light' }) {
  // Active Guard Telemetry State
  const [guardToken, setGuardToken] = useState(null);
  const [isVerified, setIsVerified] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // WAF Probe State
  const [probeTarget, setProbeTarget] = useState('');
  const [probeSandbox, setProbeSandbox] = useState(false);
  const [probeLoading, setProbeLoading] = useState(false);
  const [probeResult, setProbeResult] = useState(null);
  const [probeError, setProbeError] = useState(null);

  // Fetch status on mount
  useEffect(() => {
    document.body.style.backgroundColor = '#ffffff';
    fetchTargetStatus();
  }, []);

  const fetchTargetStatus = async () => {
    try {
      const res = await operatorFetch(`/api/target/status`);
      if (res.ok) {
        const data = await res.json();
        setProbeTarget(data.target_url || '');
        setProbeSandbox(Boolean(data.is_sandbox));
        setGuardToken(data.guard_id || null);
        if (data.is_verified !== undefined) {
          setIsVerified(data.is_verified);
        }
        if (data.remaining_seconds !== undefined) {
          setRemainingSeconds(data.remaining_seconds);
        }
      }
    } catch {
      setProbeError('Could not load the verified target.');
    }
  };

  const formatTimer = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  // Run WAF Probe
  const handleRunWafProbe = async () => {
    setProbeLoading(true);
    setProbeError(null);
    setProbeResult(null);

    try {
      const res = await operatorFetch(`/api/target/waf-probe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_url: probeTarget,
          is_sandbox: Boolean(probeSandbox),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setProbeResult(data);
      } else {
        const err = await res.json();
        setProbeError(err.detail?.detail || err.detail || 'WAF Probe execution failed');
      }
    } catch {
      setProbeError('Could not contact Pusher to run the probe.');
    } finally {
      setProbeLoading(false);
    }
  };

  return (
    <div data-appearance={appearance} className="pusher-workspace min-h-screen w-full bg-white text-black font-mono selection:bg-black selection:text-white flex flex-col antialiased overflow-y-auto pb-24">
      {/* ========================================================================= */}
      {/* STICKY TOP BAR                                                            */}
      {/* ========================================================================= */}
      <header className="sticky top-0 z-40 w-full border-b-2 border-black bg-white px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="border-2 border-black px-3 py-1.5 text-xs font-black uppercase bg-black text-white hover:bg-white hover:text-black transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>BACK TO DASHBOARD</span>
          </button>
          <span className="hidden md:inline-block border-l-2 border-black h-5" />
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-teal-700" />
            <h1 className="text-xs sm:text-sm font-black uppercase tracking-wider">
              PUSHER // EDGE DIAGNOSTICS
            </h1>
          </div>
        </div>

        {/* Live Status Telemetry Badges */}
        <div className="flex items-center gap-2 text-xs">
          <div className="border border-black px-2.5 py-1 text-[11px] font-bold bg-white flex items-center gap-1.5">
            <span className="opacity-70">ACTIVE GUARD:</span>
            <span className="font-black text-teal-800">{guardToken ?? 'None'}</span>
          </div>
          <div className={`border border-black px-2.5 py-1 text-[11px] font-bold ${
            isVerified ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-800'
          }`}>
            {isVerified ? `VERIFIED (${formatTimer(remainingSeconds)})` : 'UNVERIFIED'}
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* MAIN CONTENT BODY                                                         */}
      {/* ========================================================================= */}
      <main className="max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-6">

        <section className="border-2 border-black p-4 space-y-2">
          <h2 className="text-sm font-black uppercase">Edge diagnostics</h2>
          <p className="text-xs">Review the edge provider’s event logs for blocks and rate limits. Use staging with an approved traffic budget for capacity testing.</p>
        </section>

        <div className="border-2 border-black p-4 sm:p-5 bg-white space-y-4">
          <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider flex items-center gap-2">
                <Terminal className="w-4 h-4 text-teal-700" />
                <span>HTTP REACHABILITY PROBE</span>
              </h3>
              <p className="text-[11px] opacity-75">
                Sends one HEAD request to the verified origin. Review app and edge logs to identify the source of a block.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
            <div className="md:col-span-6 space-y-1">
              <label className="text-[10px] font-bold uppercase block text-black/70">
                Target Endpoint URL:
              </label>
              <input
                type="text"
                value={probeTarget}
                onChange={(e) => setProbeTarget(e.target.value)}
                placeholder="https://api.myproject.dev"
                className="w-full border-2 border-black p-2 text-xs font-mono bg-white text-black focus:outline-none"
              />
            </div>

            <div className="md:col-span-3 flex items-center gap-2 mt-5">
              <label className="flex items-center gap-2 text-xs font-bold cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={probeSandbox}
                  onChange={(e) => setProbeSandbox(e.target.checked)}
                  className="w-4 h-4 accent-black"
                />
                <span>SANDBOX SIMULATION</span>
              </label>
            </div>

            <div className="md:col-span-3 mt-5">
              <button
                type="button"
                onClick={handleRunWafProbe}
                disabled={probeLoading || !probeTarget.trim()}
                className={`w-full border-2 border-black py-2 px-3 text-xs font-black uppercase transition-colors flex items-center justify-center gap-2 cursor-pointer ${
                  probeLoading
                    ? 'bg-slate-200 text-black/50 cursor-not-allowed'
                    : 'bg-teal-700 text-white hover:bg-teal-800'
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                <span>{probeLoading ? 'PROBING EDGE...' : 'RUN PROBE'}</span>
              </button>
            </div>
          </div>

          {/* Diagnostic Error Banner */}
          {probeError && (
            <div className="border-2 border-black p-3 bg-rose-50 text-rose-900 border-rose-500 text-xs font-bold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{probeError}</span>
            </div>
          )}

          {/* Terminal-Style Probe Diagnosis Console */}
          {probeResult && (
            <div className="border-2 border-black bg-slate-950 text-slate-100 p-4 font-mono text-xs space-y-2.5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white">
                    {probeResult.simulated ? 'SANDBOX SIMULATION' : 'PROBE RESULT'}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  {probeResult.latency_ms != null && <span>ELAPSED: <strong className="text-white">{probeResult.latency_ms} ms</strong></span>}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] text-slate-300">
                <div>
                  <span className="text-slate-500 block">HTTP STATUS CODE:</span>
                  <strong className="text-white">
                    {probeResult.status_code ?? 'No HTTP response'}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500 block">EDGE PROVIDER HINT:</span>
                  <strong className="text-white">{probeResult.edge_hint ?? 'Unavailable'}</strong>
                </div>
                <div className="md:col-span-2">
                  <span className="text-slate-500 block">INSPECTED ENDPOINT:</span>
                  <code className="text-teal-300 break-all">{probeResult.probe_endpoint}</code>
                </div>
              </div>

              <div className="border-t border-slate-800 pt-2 text-[11px] leading-relaxed">
                <span className="text-slate-500 block font-bold">ANALYSIS &amp; RECOMMENDATION:</span>
                <p>{probeResult.recommendation}</p>
              </div>
            </div>
          )}
        </div>

        {/* 4. Security & Safety Invariants Summary */}
        <div className="border-2 border-black p-4 bg-slate-50 space-y-3">
          <div className="flex items-center justify-between border-b border-black pb-1.5 text-xs font-bold uppercase">
            <span className="flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-teal-800" />
              <span>SECURITY &amp; EXPIRY INVARIANTS</span>
            </span>
            <span className="text-[10px] font-bold border border-black px-1.5 py-0.5 bg-white">
              AUTOMATIC ZERO-TOUCH EXPOSURE
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] opacity-85 leading-relaxed">
            <div className="border border-black p-2.5 bg-white space-y-1">
              <div className="font-bold uppercase text-[10px]">1. 48-Hour Hard Expiry:</div>
              <p>Tokens automatically expire after 48 hours. Pusher will refuse to issue traffic once the countdown reaches 00:00:00.</p>
            </div>
            <div className="border border-black p-2.5 bg-white space-y-1">
              <div className="font-bold uppercase text-[10px]">2. Single-Active Token:</div>
              <p>Revoke your active Guard before generating a new one.</p>
            </div>
            <div className="border border-black p-2.5 bg-white space-y-1">
              <div className="font-bold uppercase text-[10px]">3. Immediate Kill Switch:</div>
              <p>Revoking a Guard ends its authorization in Pusher. Remove the file from your target when it is no longer needed.</p>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={onBack}
              className="border-2 border-black px-4 py-1.5 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>MANAGE GUARD ID IN VERIFY TARGET</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

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
    <div data-appearance={appearance} className="flex min-h-screen flex-col bg-canvas pb-12 text-ink">
      {/* ========================================================================= */}
      {/* STICKY TOP BAR                                                            */}
      {/* ========================================================================= */}
      <header className="sticky top-0 z-40 w-full bg-nav text-nav-ink px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="border border-line px-3 py-1.5 text-xs font-black uppercase bg-primary text-white hover:bg-surface hover:text-ink transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>BACK TO DASHBOARD</span>
          </button>
          <span className="hidden md:inline-block border-l border-line h-5" />
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-teal-700" />
            <h1 className="text-xs sm:text-sm font-black uppercase tracking-wider">
              PUSHER // EDGE DIAGNOSTICS
            </h1>
          </div>
        </div>

        {/* Live Status Telemetry Badges */}
        <div className="flex items-center gap-2 text-xs">
          <div className="border border-line px-2.5 py-1 text-[11px] font-bold bg-surface flex items-center gap-1.5">
            <span className="opacity-70">ACTIVE GUARD:</span>
            <span className="font-black text-teal-800">{guardToken ?? 'None'}</span>
          </div>
          <div className={`border border-line px-2.5 py-1 text-[11px] font-bold ${
            isVerified ? 'bg-emerald-600 text-white' : 'bg-soft text-ink'
          }`}>
            {isVerified ? `VERIFIED (${formatTimer(remainingSeconds)})` : 'UNVERIFIED'}
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* MAIN CONTENT BODY                                                         */}
      {/* ========================================================================= */}
      <main className="max-w-6xl w-full mx-auto p-4 sm:p-6 space-y-6">

        <section className="space-y-2 rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-sm font-black uppercase">Edge diagnostics</h2>
          <p className="text-xs">Review the edge provider’s event logs for blocks and rate limits. Use staging with an approved traffic budget for capacity testing.</p>
        </section>

        <div className="border border-line p-4 sm:p-5 bg-surface space-y-4">
          <div className="border-b border-line pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
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
              <label className="text-[10px] font-bold uppercase block text-muted">
                Target Endpoint URL:
              </label>
              <input
                type="text"
                value={probeTarget}
                onChange={(e) => setProbeTarget(e.target.value)}
                placeholder="https://api.myproject.dev"
                className="w-full border border-line p-2 text-xs font-mono bg-surface text-ink focus:outline-none"
              />
            </div>

            <div className="md:col-span-3 flex items-center gap-2 mt-5">
              <label className="flex items-center gap-2 text-xs font-bold cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={probeSandbox}
                  onChange={(e) => setProbeSandbox(e.target.checked)}
                  className="w-4 h-4 accent-primary"
                />
                <span>SANDBOX SIMULATION</span>
              </label>
            </div>

            <div className="md:col-span-3 mt-5">
              <button
                type="button"
                onClick={handleRunWafProbe}
                disabled={probeLoading || !probeTarget.trim()}
                className={`w-full border border-line py-2 px-3 text-xs font-black uppercase transition-colors flex items-center justify-center gap-2 cursor-pointer ${
                  probeLoading
                    ? 'bg-soft text-muted cursor-not-allowed'
                    : 'bg-primary text-white hover:bg-primary-hover'
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                <span>{probeLoading ? 'PROBING EDGE...' : 'RUN PROBE'}</span>
              </button>
            </div>
          </div>

          {/* Diagnostic Error Banner */}
          {probeError && (
            <div className="border border-line p-3 bg-rose-50 text-rose-900 border-rose-500 text-xs font-bold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{probeError}</span>
            </div>
          )}

          {/* Terminal-Style Probe Diagnosis Console */}
          {probeResult && (
            <div className="border border-line bg-slate-950 text-slate-100 p-4 font-mono text-xs space-y-2.5">
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
                  <span className="text-muted block">HTTP STATUS CODE:</span>
                  <strong className="text-white">
                    {probeResult.status_code ?? 'No HTTP response'}
                  </strong>
                </div>
                <div>
                  <span className="text-muted block">EDGE PROVIDER HINT:</span>
                  <strong className="text-white">{probeResult.edge_hint ?? 'Unavailable'}</strong>
                </div>
                <div className="md:col-span-2">
                  <span className="text-muted block">INSPECTED ENDPOINT:</span>
                  <code className="text-teal-300 break-all">{probeResult.probe_endpoint}</code>
                </div>
              </div>

              <div className="border-t border-slate-800 pt-2 text-[11px] leading-relaxed">
                <span className="text-muted block font-bold">ANALYSIS &amp; RECOMMENDATION:</span>
                <p>{probeResult.recommendation}</p>
              </div>
            </div>
          )}
        </div>

        {/* 4. Security & Safety Invariants Summary */}
        <div className="border border-line p-4 bg-field space-y-3">
          <div className="flex items-center justify-between border-b border-line pb-1.5 text-xs font-bold uppercase">
            <span className="flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-teal-800" />
              <span>SECURITY &amp; EXPIRY INVARIANTS</span>
            </span>
            <span className="text-[10px] font-bold border border-line px-1.5 py-0.5 bg-surface">
              AUTOMATIC ZERO-TOUCH EXPOSURE
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px] opacity-85 leading-relaxed">
            <div className="border border-line p-2.5 bg-surface space-y-1">
              <div className="font-bold uppercase text-[10px]">1. 48-Hour Hard Expiry:</div>
              <p>Tokens automatically expire after 48 hours. Pusher will refuse to issue traffic once the countdown reaches 00:00:00.</p>
            </div>
            <div className="border border-line p-2.5 bg-surface space-y-1">
              <div className="font-bold uppercase text-[10px]">2. Single-Active Token:</div>
              <p>Revoke your active Guard before generating a new one.</p>
            </div>
            <div className="border border-line p-2.5 bg-surface space-y-1">
              <div className="font-bold uppercase text-[10px]">3. Immediate Kill Switch:</div>
              <p>Revoking a Guard ends its authorization in Pusher. Remove the file from your target when it is no longer needed.</p>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={onBack}
              className="border border-line px-4 py-1.5 text-xs font-bold uppercase bg-surface hover:bg-primary hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
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

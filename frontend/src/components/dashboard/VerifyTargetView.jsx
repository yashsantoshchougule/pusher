import React from 'react';
import {
  Shield,
  Download,
  CheckSquare,
  Square,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertOctagon,
  ExternalLink,
  Code,
  Copy,
  Clock,
  Zap,
  Flame,
  Laptop
} from 'lucide-react';

export default function VerifyTargetView({
  targetUrl,
  requiresTargetQuery,
  setTargetUrl,
  sandboxMode,
  sandboxTargetUrl,
  sandboxRequiresRevocation,
  handleToggleSandbox,
  ssrfCheck,
  urlValidation = { checking: false, valid: true, ready: false, status: 'IDLE', message: '', suggestions: [] },
  guardToken,
  isVerified,
  verifiedOrigin,
  isGuardVerified,
  guardTimerSeconds,
  formatTimer,
  verificationError,
  setVerificationError,
  guardQuota = { used: 0, max: 3, remaining: 3, revokedCount: 0, lastRevokedId: null },
  supersededNotice,
  deviceId = 'DEV-LOCAL-CREATOR',
  lastBurnReason = null,
  handleDownloadGuard,
  guardChecksum,
  handleVerifyTarget,
  handleKillGuard,
  setWafModalOpen,
  setActiveNav,
  themeMode = 'production',
  onNavigate,
}) {
  const isProd = themeMode === 'production';
  const quotaRemaining = guardQuota.remaining ?? 3;
  const isQuotaDepleted = quotaRemaining <= 0;
  const hasActiveGuard = Boolean(guardToken && guardToken !== 'NONE' && guardToken !== 'EXPIRED');

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black uppercase tracking-wider">
            TARGET VERIFICATION
          </h1>
          <p className="text-xs opacity-75">
            {sandboxMode ? 'Verify the local sandbox before starting a test.' : 'Verify target ownership with pusher_guard.py before starting a test.'}
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

      {/* Quota & Device Lock Ribbon */}
      <div className={`border-2 border-black p-3.5 bg-white flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
        isProd ? 'shadow-sm border-l-4 border-l-teal-700' : ''
      }`}>
        <div className="flex flex-wrap items-center gap-3">
          {!sandboxMode && <span className="text-xs font-black uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            <span>DAILY GUARD QUOTA:</span>
          </span>}
          {!sandboxMode && <span className={`border-2 border-black px-2.5 py-0.5 text-xs font-black uppercase tracking-wider ${
            isQuotaDepleted
              ? (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-black text-white')
              : (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
          }`}>
            {quotaRemaining} / {guardQuota.max || 3} REMAINING (24H LIMIT)
          </span>}

          {/* Hardware Device Lock Badge */}
          <div className="flex items-center gap-1.5 border-2 border-black px-2.5 py-0.5 text-xs font-mono font-bold bg-white">
            <Laptop className="w-3.5 h-3.5 text-teal-700" />
            <span className="opacity-75 uppercase">DEVICE LOCK:</span>
            <span className="font-black text-teal-800">BOUND TO {deviceId}</span>
          </div>
        </div>

        {guardQuota.revokedCount > 0 && (
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="flex items-center gap-1 text-[11px] font-bold">
              <Flame className={`w-3.5 h-3.5 ${isProd ? 'text-amber-600' : ''}`} />
              <span>BURN REGISTRY:</span>
            </span>
            <span className={`border border-black px-2 py-0.5 text-[10px] font-bold ${
              isProd ? 'bg-slate-100 text-slate-800' : 'bg-white'
            }`}>
              {guardQuota.revokedCount} ID{guardQuota.revokedCount > 1 ? 's' : ''} BURNED (SQLITE)
            </span>
            {guardQuota.lastRevokedId && (
              <span className="text-[10px] opacity-70">
                (Last: {guardQuota.lastRevokedId})
              </span>
            )}
          </div>
        )}
      </div>

      {/* Irreversible Burn Alert Banner */}
      {lastBurnReason && (
        <div className="border-2 border-black p-3.5 bg-rose-50 border-l-8 border-l-rose-600 text-rose-950 font-mono text-xs space-y-1 shadow-sm">
          <div className="font-black flex items-center gap-2 text-rose-800 uppercase tracking-wider text-xs">
            <AlertOctagon className="w-4 h-4 shrink-0" />
            <span>
              {lastBurnReason === 'DEVICE_MISMATCH_VIOLATION'
                ? 'SECURITY TRIPWIRE TRIPPED: KILLED — CROSS-DEVICE VIOLATION'
                : lastBurnReason === 'EXPIRED_48H'
                ? 'SECURITY EXPIRATION: KILLED — 48H EXPIRED'
                : 'REVOCATION NOTICE: KILLED — MANUALLY REVOKED'}
            </span>
          </div>
          <p className="text-[11px] leading-relaxed">
            Guard ID <code className="font-bold underline">{guardToken || guardQuota.lastRevokedId || 'ACTIVE_ID'}</code> has been permanently terminated. The 48-hour session timer is stopped at <span className="font-black text-rose-700">00:00:00</span> and this ID has been permanently written to the persistent SQLite tombstone registry (<code>burned_guards</code>). It can never be used, verified, or re-issued to any device.
          </p>
        </div>
      )}

      {/* Superseded Notification Banner */}
      {supersededNotice && (
        <div className={`border-2 border-black p-3 text-xs font-bold flex items-center justify-between ${
          isProd ? 'bg-amber-100 text-amber-950 border-amber-500' : 'bg-black text-white'
        }`}>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{supersededNotice}</span>
          </div>
        </div>
      )}

      {/* Quota Depleted Warning Banner */}
      {!sandboxMode && isQuotaDepleted && (
        <div className={`border-2 border-black p-3 text-xs font-bold flex items-center gap-2 ${
          isProd ? 'bg-rose-50 text-rose-900 border-rose-500' : 'bg-black text-white'
        }`}>
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            Daily generation limit reached (3 per 24 hours). Downloads are locked until rolling 24h window clears. Active token remains valid.
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Full Interactive Verification Wizard */}
        <div className={`lg:col-span-7 border-2 border-black p-5 bg-white space-y-4 ${
          isProd ? 'shadow-sm' : ''
        }`}>
          <div className="flex items-center justify-between border-b-2 border-black pb-2">
            <h2 className="text-sm font-black uppercase">
              {sandboxMode ? 'LOCAL SANDBOX' : 'DOMAIN OWNERSHIP VERIFICATION'}
            </h2>
            <span
              className={`border border-black px-2 py-0.5 text-xs font-bold uppercase ${
                isVerified
                  ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
                  : (isProd ? 'bg-rose-100 text-rose-800 border-rose-400' : 'bg-white text-black')
              }`}
            >
              {isVerified ? 'STATUS: VERIFIED' : 'STATUS: UNVERIFIED'}
            </span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold uppercase block">
              Target Root URL:
            </label>
            <input
              type="text"
              value={targetUrl}
              onChange={(e) => {
                setTargetUrl(e.target.value);
                setVerificationError(null);
              }}
              placeholder={sandboxMode ? sandboxTargetUrl : 'https://your-deployed-app.com'}
              className="w-full border-2 border-black p-2 text-xs font-mono bg-white text-black focus:outline-none focus:bg-black focus:text-white"
            />
            {verifiedOrigin && !isVerified && (
              <p className="text-[11px]">
                The active Guard covers <code>{verifiedOrigin}</code> in its verified mode.
              </p>
            )}
          </div>

          {/* Real-time Dynamic URL Reachability, DNS & SSRF Diagnostic Ribbon */}
          <div
            className={`border-2 p-3 text-xs font-mono transition-all ${
              urlValidation.checking
                ? 'bg-slate-100 border-slate-400 text-slate-800'
                : urlValidation.ready
                ? (isProd ? 'bg-emerald-50 border-emerald-500 text-emerald-900 shadow-sm' : 'bg-white text-black border-black')
                : (isProd ? 'bg-rose-50 border-rose-500 text-rose-950 shadow-sm' : 'bg-black text-white border-black')
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {urlValidation.checking ? (
                  <Clock className="w-4 h-4 animate-spin text-teal-700 shrink-0" />
                ) : urlValidation.ready ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                )}
                <span className="font-bold">
                  {urlValidation.checking
                    ? (sandboxMode ? 'CHECKING SANDBOX ADDRESS...' : 'CHECKING URL & DNS...')
                    : urlValidation.message}
                </span>
              </div>
              <span
                className={`text-[10px] font-black border px-1.5 py-0.5 uppercase tracking-wider shrink-0 ${
                  urlValidation.checking
                    ? 'border-slate-500 bg-white text-slate-700'
                    : urlValidation.ready
                    ? (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white border-black')
                    : (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-white text-black border-black')
                }`}
              >
                {urlValidation.checking
                  ? 'CHECKING...'
                  : urlValidation.ready
                  ? 'PASSED'
                  : urlValidation.status || 'FAILED'}
              </span>
            </div>

            {/* Smart Domain Typo Suggestions */}
            {!urlValidation.checking && !urlValidation.ready && urlValidation.suggestions && urlValidation.suggestions.length > 0 && (
              <div className="mt-2.5 pt-2 border-t border-rose-200 flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-bold text-rose-950 uppercase tracking-wide">
                  Did you mean:
                </span>
                {urlValidation.suggestions.map((suggestion, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setTargetUrl(suggestion);
                    }}
                    className="px-2.5 py-1 bg-white hover:bg-teal-700 hover:text-white text-teal-900 border-2 border-teal-600 text-xs font-mono font-bold transition-colors cursor-pointer shadow-xs"
                    title={`Click to use ${suggestion}`}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>

          {requiresTargetQuery && (
            <p className="text-xs">Single-target tests require the target query. Re-enter it or verify the URL without it.</p>
          )}

          {sandboxTargetUrl && (
            <button
              type="button"
              aria-pressed={sandboxMode}
              onClick={handleToggleSandbox}
              className="w-full border-2 border-black p-3 bg-white flex items-center justify-between text-left cursor-pointer"
            >
              <span className="text-xs font-bold uppercase">Sandbox Simulation Target</span>
              {sandboxMode ? <CheckSquare className="w-5 h-5" /> : <Square className="w-5 h-5" />}
            </button>
          )}

          {/* Step 2: Download Sealed pusher_guard.py */}
          {!sandboxMode && <div className="border-2 border-black p-3.5 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase">2. Install Ownership Guard</span>
              <span className="text-[10px] font-bold border border-black px-1.5 py-0.5">
                ACTIVE ID: {guardToken || 'NONE'}
              </span>
            </div>
            <p className="text-[11px] opacity-80">
              One guard file is allowed at a time (Max 3/day). To generate a new pusher_guard.py file, you must first click 'KILL ID' below to permanently burn the current ID.
            </p>
            <button
              type="button"
              onClick={handleDownloadGuard}
              disabled={isQuotaDepleted || hasActiveGuard || (urlValidation.checking || !urlValidation.ready)}
              className={`w-full border-2 border-black py-2.5 px-3 text-xs font-bold uppercase transition-colors flex items-center justify-center gap-2 ${
                isQuotaDepleted || hasActiveGuard || (urlValidation.checking || !urlValidation.ready)
                  ? 'bg-slate-100 text-black/60 opacity-60 cursor-not-allowed border-black/40'
                  : 'bg-white hover:bg-black hover:text-white cursor-pointer'
              }`}
            >
              <Download className="w-4 h-4" />
              <span>
                {isQuotaDepleted
                  ? 'QUOTA DEPLETED (3/3 USED)'
                  : hasActiveGuard
                  ? `LOCKED — USE ACTIVE ID (${guardToken}) OR CLICK 'KILL ID' BELOW FIRST`
                  : urlValidation.checking
                  ? 'CHECKING TARGET DNS...'
                  : !urlValidation.ready
                  ? 'ENTER A URL WITH VALID DNS TO UNLOCK'
                  : 'DOWNLOAD PUSHER_GUARD.PY'}
              </span>
            </button>
          </div>}

          {/* Step 3: Run Challenge Handshake */}
          <div className="border-2 border-black p-3.5 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase">
                {sandboxMode ? 'Verify Local Sandbox' : '3. Execute Live Cryptographic Handshake'}
              </span>
              <span className={`text-[10px] font-bold border border-black px-1.5 py-0.5 ${
                isVerified
                  ? (isProd ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                  : 'bg-white text-black'
              }`}>
                {isVerified ? 'VERIFIED' : 'PENDING'}
              </span>
            </div>
            <p className="text-[11px] opacity-80">
              {sandboxMode
                ? 'The built-in sandbox verifies directly. No Guard file is required.'
                : <>Pusher sends a cryptographic challenge to your target at <code>/__pusher_verify</code> to confirm ownership.</>}
            </p>
            {sandboxRequiresRevocation && (
              <p className="text-[11px] font-bold">Revoke the current live Guard before verifying the sandbox.</p>
            )}

            {verificationError && (
              <div className={`border p-2.5 text-xs font-bold flex items-center gap-2 ${
                isProd ? 'bg-rose-50 border-rose-400 text-rose-800' : 'bg-black text-white border-black'
              }`}>
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{verificationError}</span>
              </div>
            )}

            <div className="flex flex-col sm:flex-row flex-wrap gap-2">
              <button
                type="button"
                onClick={handleVerifyTarget}
                disabled={sandboxRequiresRevocation}
                className={`flex-1 min-w-[160px] border-2 border-black py-2.5 px-3 text-xs font-black uppercase transition-colors cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                  isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-black text-white hover:bg-white hover:text-black'
                }`}
              >
                <Shield className="w-4 h-4" />
                <span>{sandboxMode ? 'VERIFY SANDBOX' : 'VERIFY TARGET NOW'}</span>
              </button>
              {hasActiveGuard && (
                <button
                  type="button"
                  onClick={handleKillGuard}
                  className={`border-2 border-black py-2.5 px-3 text-xs font-bold uppercase transition-colors cursor-pointer flex items-center justify-center gap-1.5 ${
                    isProd ? 'bg-rose-100 text-rose-800 border-rose-400 hover:bg-rose-200' : 'bg-white text-black hover:bg-black hover:text-white'
                  }`}
                >
                  <Flame className="w-3.5 h-3.5" />
                  <span>KILL ID (PERMANENT)</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right: Technical Spec & WAF Mini-Screen Preview */}
        <div className="lg:col-span-5 space-y-4">
          {/* 48-Hour Live Countdown Card */}
          <div className={`border-2 border-black p-4 bg-white ${
            isProd ? 'shadow-sm border-l-4 border-l-emerald-600' : ''
          }`}>
            <div className="text-xs font-bold uppercase tracking-wider mb-1 flex items-center justify-between">
              <span>48-Hour Active Session Timer:</span>
              <span className={`text-[10px] font-bold border border-black px-1.5 py-0.5 ${
                isGuardVerified
                  ? (isProd ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                  : 'bg-white'
              }`}>
                {isGuardVerified ? 'TICKING' : 'LOCKED'}
              </span>
            </div>
            <div className="text-3xl font-black tracking-widest my-2">
              {isGuardVerified ? formatTimer(guardTimerSeconds) : '00:00:00'}
            </div>
            <p className="text-[10px] opacity-75">
              Target verification is sealed for 48 hours. Pusher will automatically block tests after this window to prevent unauthorized long-term scanning.
            </p>
          </div>

          <div className="border-2 border-black p-4 bg-white space-y-2">
            <h3 className="text-xs font-bold uppercase">Target verification</h3>
            {!sandboxMode && (
              <p className="text-[11px]">Install the current ownership Guard and verify it from Pusher. Target traffic keeps the app’s usual security checks.</p>
            )}
            {!sandboxMode && guardChecksum && <p className="text-[10px] break-all">File SHA-256 · {guardChecksum}</p>}
            <button type="button" onClick={() => onNavigate?.('waf-setup')} className="text-[10px] font-bold underline">
              View edge diagnostics
            </button>
          </div>

          {/* Locked Security Invariants */}
          {!sandboxMode && <div className="border-2 border-black p-3.5 bg-white text-xs font-mono space-y-1.5">
            <div className="font-bold uppercase border-b border-black pb-1">
              Enforced Security Invariants:
            </div>
            <ul className="text-[10px] opacity-80 space-y-1 list-disc list-inside">
              <li>Rate Limit: Maximum 3 guard generations per 24 hours.</li>
              <li>Revoke the current Guard before generating a replacement.</li>
              <li>SSRF: Loopbacks, 10.x/192.168.x &amp; 169.254.x metadata blocked.</li>
              <li>Anti-Tamper: SHA-256 sealed lockbox with HMAC verification.</li>
              <li>Zero Data Leak: Target receives only stateless cryptographic nonces.</li>
            </ul>
          </div>}
        </div>
      </div>
    </div>
  );
}

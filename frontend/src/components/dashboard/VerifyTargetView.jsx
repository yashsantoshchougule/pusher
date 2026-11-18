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
  setTargetUrl,
  sandboxMode,
  setSandboxMode,
  ssrfCheck,
  guardToken,
  isVerified,
  guardTimerSeconds,
  formatTimer,
  verificationError,
  setVerificationError,
  guardQuota = { used: 0, max: 3, remaining: 3, revokedCount: 0, lastRevokedId: null },
  supersededNotice,
  deviceId = 'DEV-LOCAL-CREATOR',
  lastBurnReason = null,
  handleDownloadGuard,
  handleVerifyTarget,
  handleKillGuard,
  handleTestCrossDeviceBlock,
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
            TARGET VERIFICATION &amp; WAF BYPASS CONFIGURATOR
          </h1>
          <p className="text-xs opacity-75">
            Arm cryptographic domain ownership, hardware device lock, and bypass edge rate limits with pusher_guard.py.
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
          <span className="text-xs font-black uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            <span>DAILY GUARD QUOTA:</span>
          </span>
          <span className={`border-2 border-black px-2.5 py-0.5 text-xs font-black uppercase tracking-wider ${
            isQuotaDepleted
              ? (isProd ? 'bg-rose-600 text-white border-rose-700' : 'bg-black text-white')
              : (isProd ? 'bg-emerald-600 text-white border-emerald-700' : 'bg-black text-white')
          }`}>
            {quotaRemaining} / {guardQuota.max || 3} REMAINING (24H LIMIT)
          </span>

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
      {isQuotaDepleted && (
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
              1. DOMAIN OWNERSHIP VERIFICATION WIZARD
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
              placeholder="https://your-deployed-app.com"
              className="w-full border-2 border-black p-2 text-xs font-mono bg-white text-black focus:outline-none focus:bg-black focus:text-white"
            />
          </div>

          {/* SSRF Diagnostic Ribbon */}
          <div
            className={`border p-2.5 text-xs font-mono flex items-center justify-between ${
              ssrfCheck.valid
                ? (isProd ? 'bg-emerald-50 border-emerald-400 text-emerald-900' : 'bg-white text-black border-black')
                : (isProd ? 'bg-rose-50 border-rose-400 text-rose-900' : 'bg-black text-white border-black')
            }`}
          >
            <span className="font-bold">{ssrfCheck.message}</span>
            <span className="text-[10px] font-bold border border-current px-1.5 py-0.5">
              {ssrfCheck.valid ? 'PASSED' : 'DENIED'}
            </span>
          </div>

          {/* Sandbox Toggle */}
          <div
            onClick={() => setSandboxMode(!sandboxMode)}
            className="border-2 border-black p-3 bg-white flex items-center justify-between cursor-pointer select-none"
          >
            <div>
              <div className="text-xs font-bold uppercase">Sandbox Simulation Target</div>
              <div className="text-[10px] opacity-75">
                Bypasses public DNS validation for local Docker / sandbox load testing
              </div>
            </div>
            <button type="button" className="text-black">
              {sandboxMode ? <CheckSquare className="w-5 h-5" /> : <Square className="w-5 h-5" />}
            </button>
          </div>

          {/* Step 2: Download Sealed pusher_guard.py */}
          <div className="border-2 border-black p-3.5 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase">2. Deploy Guard Middleware</span>
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
              disabled={isQuotaDepleted || hasActiveGuard}
              className={`w-full border-2 border-black py-2.5 px-3 text-xs font-bold uppercase transition-colors flex items-center justify-center gap-2 ${
                isQuotaDepleted || hasActiveGuard
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
                  : 'DOWNLOAD PUSHER_GUARD.PY'}
              </span>
            </button>
          </div>

          {/* Step 3: Run Challenge Handshake */}
          <div className="border-2 border-black p-3.5 bg-white space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase">3. Execute Live Cryptographic Handshake</span>
              <span className={`text-[10px] font-bold border border-black px-1.5 py-0.5 ${
                isVerified
                  ? (isProd ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                  : 'bg-white text-black'
              }`}>
                {isVerified ? 'VERIFIED' : 'PENDING'}
              </span>
            </div>
            <p className="text-[11px] opacity-80">
              Pusher sends a cryptographic challenge nonce to your target at <code>/__pusher_verify?nonce=...</code> to confirm ownership.
            </p>

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
                className={`flex-1 min-w-[160px] border-2 border-black py-2.5 px-3 text-xs font-black uppercase transition-colors cursor-pointer flex items-center justify-center gap-2 ${
                  isProd ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-black text-white hover:bg-white hover:text-black'
                }`}
              >
                <Shield className="w-4 h-4" />
                <span>VERIFY TARGET NOW</span>
              </button>
              {hasActiveGuard && (
                <>
                  <button
                    type="button"
                    onClick={handleKillGuard}
                    className={`border-2 border-black py-2.5 px-3 text-xs font-bold uppercase transition-colors cursor-pointer flex items-center justify-center gap-1.5 ${
                      isProd ? 'bg-rose-100 text-rose-800 border-rose-400 hover:bg-rose-200' : 'bg-white text-black hover:bg-black hover:text-white'
                    }`}
                    title="Immediately revoke token and burn in registry"
                  >
                    <Flame className="w-3.5 h-3.5" />
                    <span>KILL ID</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleTestCrossDeviceBlock}
                    className={`border-2 border-black py-2.5 px-3 text-xs font-black uppercase transition-colors cursor-pointer flex items-center justify-center gap-1.5 ${
                      isProd ? 'bg-amber-100 text-amber-900 border-amber-500 hover:bg-amber-200' : 'bg-white text-black hover:bg-black hover:text-white'
                    }`}
                    title="Test cross-device tripwire: Sends a foreign device ID (DEV-FOREIGN-9999) to verify endpoint, instantly triggering permanent burn, stopping the 48h timer, and writing to SQLite tombstone"
                  >
                    <AlertOctagon className="w-3.5 h-3.5" />
                    <span>[ TEST CROSS-DEVICE BLOCK ]</span>
                  </button>
                </>
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
                isVerified
                  ? (isProd ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                  : 'bg-white'
              }`}>
                {isVerified ? 'TICKING' : 'LOCKED'}
              </span>
            </div>
            <div className="text-3xl font-black tracking-widest my-2">
              {isVerified ? formatTimer(guardTimerSeconds) : '00:00:00'}
            </div>
            <p className="text-[10px] opacity-75">
              Target verification is sealed for 48 hours. Pusher will automatically block tests after this window to prevent unauthorized long-term scanning.
            </p>
          </div>

          {/* WAF Rate Limit Bypass Explainer */}
          <div className={`border-2 border-black p-4 bg-white space-y-3 ${isProd ? 'shadow-sm' : ''}`}>
            <div className="flex items-center justify-between border-b border-black pb-1.5">
              <span className="text-xs font-bold uppercase">Cloudflare / AWS WAF &amp; In-App Auth Bypass</span>
              <button
                type="button"
                onClick={() => {
                  if (onNavigate) {
                    onNavigate('waf-setup');
                  } else {
                    window.location.hash = '#/waf-setup';
                  }
                }}
                className="text-[10px] font-bold underline cursor-pointer hover:opacity-70"
              >
                [ VIEW GUIDE ]
              </button>
            </div>

            <div className="space-y-2 text-[11px] leading-relaxed">
              <div className="p-2 border border-black/30 bg-slate-50 space-y-1">
                <span className="font-bold block uppercase text-[10px] text-teal-800">
                  1. Automatic Backend Bypass (Zero Config):
                </span>
                <p className="opacity-85 text-[10px]">
                  <code>pusher_guard.py</code> automatically bypasses Python in-app rate limiters (<code>slowapi</code>, Starlette throttles) and injects synthetic test auth credentials when it verifies Pusher's cryptographic <code>X-Pusher-Signature</code> HMAC header.
                </p>
              </div>

              <div className="p-2 border border-black/30 bg-slate-50 space-y-1">
                <span className="font-bold block uppercase text-[10px] text-teal-800">
                  2. Edge CDN Skip Rule (Cloudflare / AWS WAF):
                </span>
                <p className="opacity-85 text-[10px]">
                  Configure an Edge WAF Skip Rule to bypass Cloudflare / AWS edge rate limiting before requests reach your origin server:
                </p>
                <div className="bg-black text-white p-2 font-mono text-[9px] break-all select-all">
                  http.request.headers["x-pusher-guard-id"][0] eq "{guardToken || 'PG-ACTIVE'}"
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                if (onNavigate) {
                  onNavigate('waf-setup');
                } else {
                  window.location.hash = '#/waf-setup';
                }
              }}
              className="w-full border-2 border-black py-2 px-3 text-xs font-black uppercase bg-teal-700 text-white hover:bg-teal-800 transition-colors flex items-center justify-center gap-1.5 cursor-pointer mt-1"
            >
              <span>OPEN FULL WAF SETUP PAGE →</span>
            </button>

            <div className="border border-black p-2 bg-white font-mono text-[10px] space-y-1">
              <div className="font-bold uppercase text-[9px] opacity-70">Handshake Curl Test:</div>
              <div className="text-black break-all select-all text-[9px]">
                curl -i -H "X-Pusher-Guard-ID: {guardToken || 'PG-ACTIVE'}" "{targetUrl}/__pusher_verify?nonce=waf_check"
              </div>
            </div>
          </div>

          {/* Locked Security Invariants */}
          <div className="border-2 border-black p-3.5 bg-white text-xs font-mono space-y-1.5">
            <div className="font-bold uppercase border-b border-black pb-1">
              Enforced Security Invariants:
            </div>
            <ul className="text-[10px] opacity-80 space-y-1 list-disc list-inside">
              <li>Rate Limit: Maximum 3 guard generations per 24 hours.</li>
              <li>Single-Active: Generating a new token burns the previous ID.</li>
              <li>SSRF: Loopbacks, 10.x/192.168.x &amp; 169.254.x metadata blocked.</li>
              <li>Anti-Tamper: SHA-256 sealed lockbox with HMAC verification.</li>
              <li>Zero Data Leak: Target receives only stateless cryptographic nonces.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

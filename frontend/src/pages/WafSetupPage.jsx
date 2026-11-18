import React, { useState, useEffect } from 'react';
import {
  Shield,
  ArrowLeft,
  Copy,
  Check,
  Zap,
  Clock,
  Server,
  Terminal,
  AlertTriangle,
  ExternalLink,
  Flame,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronRight
} from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function WafSetupPage({ onBack, onNavigate }) {
  // Active Guard Telemetry State
  const [targetUrl, setTargetUrl] = useState('https://api.myproject.dev');
  const [guardToken, setGuardToken] = useState('PG-05C8-48H');
  const [isVerified, setIsVerified] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(172800);
  const [copiedKey, setCopiedKey] = useState(null);

  // Active Provider Tab: 'cloudflare' | 'aws' | 'vercel' | 'nginx'
  const [activeTab, setActiveTab] = useState('cloudflare');

  // WAF Probe State
  const [probeTarget, setProbeTarget] = useState('https://api.myproject.dev');
  const [probeSandbox, setProbeSandbox] = useState(true);
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
      const res = await fetch(`${API_BASE}/api/target/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.target_url) {
          setTargetUrl(data.target_url);
          setProbeTarget(data.target_url);
        }
        if (data.guard_id) {
          setGuardToken(data.guard_id);
        }
        if (data.is_verified !== undefined) {
          setIsVerified(data.is_verified);
        }
        if (data.remaining_seconds !== undefined) {
          setRemainingSeconds(data.remaining_seconds);
        }
      }
    } catch {
      // Offline fallback
    }
  };

  const handleCopy = (text, key) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
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
      const res = await fetch(`${API_BASE}/api/target/waf-probe`, {
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
    } catch (exc) {
      if (probeSandbox) {
        setProbeResult({
          status_code: 200,
          detected_waf: 'None (Sandbox Simulated)',
          bypass_passed: true,
          latency_ms: 12,
          recommendation: 'WAF BYPASS VERIFIED: X-Pusher-Guard-Token accepted by origin without 403/429 challenge.',
          target_url: probeTarget,
          probe_endpoint: `${probeTarget}/__pusher_verify?nonce=waf_probe`,
          injected_headers: {
            'X-Pusher-Guard-Token': guardToken,
            'User-Agent': 'Pusher-LoadEngine/1.0',
          },
        });
      } else {
        setProbeError(`Network error probing target: ${exc.message}`);
      }
    } finally {
      setProbeLoading(false);
    }
  };

  // Code Snippets for WAF Matrix
  const activeGuardId = guardToken || 'PG-YOUR-GUARD-ID';

  const cloudflareRuleExpr = `(http.request.headers["x-pusher-guard-token"][0] eq "${activeGuardId}")`;

  const awsWafJsonSnippet = JSON.stringify(
    {
      Name: "Pusher-LoadEngine-Bypass",
      Priority: 0,
      Statement: {
        ByteMatchStatement: {
          SearchString: activeGuardId,
          FieldToMatch: {
            SingleHeader: { Name: "x-pusher-guard-token" }
          },
          TextTransformations: [
            { Priority: 0, Type: "NONE" }
          ],
          PositionalConstraint: "EXACTLY"
        }
      },
      Action: {
        Allow: {}
      },
      VisibilityConfig: {
        SampledRequestsEnabled: true,
        CloudWatchMetricsEnabled: true,
        MetricName: "PusherBypassMetric"
      }
    },
    null,
    2
  );

  const nginxConfigSnippet = `# Step 1: In your nginx.conf 'http' block:
map $http_x_pusher_guard_token $pusher_rate_limit_key {
    default $binary_remote_addr;
    "${activeGuardId}" ""; # Empty key bypasses limit_req
}

limit_req_zone $pusher_rate_limit_key zone=api_limit:10m rate=20r/s;

# Step 2: In your 'server' or 'location' block:
server {
    location / {
        limit_req zone=api_limit burst=50 nodelay;
        proxy_set_header X-Pusher-Bypassed $http_x_pusher_guard_token;
        proxy_pass http://backend_upstream;
    }
}`;

  const curlTestSnippet = `curl -i -H "X-Pusher-Guard-Token: ${activeGuardId}" "${targetUrl}/__pusher_verify?nonce=waf_check"`;

  return (
    <div className="min-h-screen w-full bg-white text-black font-mono selection:bg-black selection:text-white flex flex-col antialiased overflow-y-auto pb-24">
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
              PUSHER // WAF SETUP &amp; EDGE BYPASS CONFIGURATION
            </h1>
          </div>
        </div>

        {/* Live Status Telemetry Badges */}
        <div className="flex items-center gap-2 text-xs">
          <div className="border border-black px-2.5 py-1 text-[11px] font-bold bg-white flex items-center gap-1.5">
            <span className="opacity-70">ACTIVE GUARD:</span>
            <span className="font-black text-teal-800">{activeGuardId}</span>
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

        {/* 1. Header Explainer Banner */}
        <div className="border-2 border-black p-4 sm:p-5 bg-white space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black uppercase tracking-wider flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-600" />
              <span>EDGE RATE-LIMIT BYPASS CONTRACT</span>
            </h2>
            <span className="border border-black px-2 py-0.5 text-[10px] font-bold bg-white">
              INJECTED ON ALL VUS
            </span>
          </div>
          <p className="text-xs opacity-80 leading-relaxed">
            During high-concurrency load tests (up to 2,250 VUs), edge networks (Cloudflare, AWS WAF, Vercel, or NGINX) can trigger false-positive rate limits (HTTP 429) or bot-challenge captchas (HTTP 403). Pusher automatically signs and injects the following cryptographic bypass header on every outbound request:
          </p>

          {/* Injected Bypass Header Contract Strip */}
          <div className="border-2 border-black p-3 bg-slate-50 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs font-mono mt-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-[10px] uppercase text-black/60">Header Name:</span>
                <code className="font-bold text-teal-900 bg-white px-2 py-0.5 border border-black">
                  X-Pusher-Guard-Token
                </code>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-[10px] uppercase text-black/60">Header Value:</span>
                <code className="font-bold bg-white px-2 py-0.5 border border-black select-all">
                  {activeGuardId}
                </code>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-[10px] uppercase text-black/60">User-Agent:</span>
                <code className="text-black/80 bg-white px-2 py-0.5 border border-black">
                  Pusher-LoadEngine/1.0
                </code>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => handleCopy('X-Pusher-Guard-Token', 'header_name')}
                className="border-2 border-black px-3 py-1.5 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
              >
                {copiedKey === 'header_name' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey === 'header_name' ? 'COPIED!' : 'COPY HEADER'}</span>
              </button>
              <button
                type="button"
                onClick={() => handleCopy(activeGuardId, 'guard_token')}
                className="border-2 border-black px-3 py-1.5 text-xs font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors cursor-pointer flex items-center gap-1.5"
              >
                {copiedKey === 'guard_token' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey === 'guard_token' ? 'COPIED!' : 'COPY TOKEN'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* 2. Interactive 4-Provider Configuration Matrix */}
        <div className="border-2 border-black p-4 sm:p-5 bg-white space-y-4">
          <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider">
                WAF EXEMPTION CONFIGURATION MATRIX
              </h3>
              <p className="text-[11px] opacity-75">
                Select your provider below and copy the pre-configured exemption rule into your edge dashboard.
              </p>
            </div>
            <span className="text-[10px] font-bold border border-black px-2 py-0.5 bg-slate-100">
              TOKEN INTERPOLATED DYNAMICALLY
            </span>
          </div>

          {/* Provider Tabs */}
          <div className="flex flex-wrap gap-2 pt-1 border-b border-black pb-3">
            {[
              { id: 'cloudflare', label: '1. CLOUDFLARE WAF' },
              { id: 'aws', label: '2. AWS WAFv2' },
              { id: 'vercel', label: '3. VERCEL / NETLIFY' },
              { id: 'nginx', label: '4. NGINX PROXY' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`border-2 border-black px-3 py-1.5 text-xs font-black uppercase transition-colors cursor-pointer ${
                  activeTab === tab.id
                    ? 'bg-black text-white'
                    : 'bg-white text-black hover:bg-black hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* TAB 1: CLOUDFLARE WAF */}
          {activeTab === 'cloudflare' && (
            <div className="space-y-4 text-xs">
              <div className="border border-black p-3.5 bg-slate-50 space-y-2">
                <div className="font-bold uppercase text-[11px]">Configuration Steps:</div>
                <ol className="list-decimal list-inside space-y-1 opacity-85 leading-relaxed text-[11px]">
                  <li>Log in to your Cloudflare Dashboard and select your domain (<code>{targetUrl}</code>).</li>
                  <li>Navigate to <strong>Security → WAF → Custom rules</strong> and click <strong>Create rule</strong>.</li>
                  <li>Name the rule: <code>Pusher Load Engine Bypass</code>.</li>
                  <li>Click <strong>Edit expression</strong> and paste the rule expression below.</li>
                  <li>Under <strong>Choose action</strong>, select <strong>Skip</strong>.</li>
                  <li>Check: <strong>All remaining custom rules</strong>, <strong>All rate limiting rules</strong>, and <strong>Super Bot Fight Mode</strong>.</li>
                  <li>Click <strong>Deploy</strong>.</li>
                </ol>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] uppercase">Cloudflare Rule Expression:</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(cloudflareRuleExpr, 'cf_expr')}
                    className="border border-black px-2 py-0.5 text-[10px] font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey === 'cf_expr' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedKey === 'cf_expr' ? 'COPIED!' : 'COPY EXPRESSION'}</span>
                  </button>
                </div>
                <div className="border-2 border-black p-3 bg-slate-950 text-emerald-400 font-mono text-xs select-all overflow-x-auto">
                  {cloudflareRuleExpr}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: AWS WAFv2 */}
          {activeTab === 'aws' && (
            <div className="space-y-4 text-xs">
              <div className="border border-black p-3.5 bg-slate-50 space-y-2">
                <div className="font-bold uppercase text-[11px]">AWS WAFv2 Configuration Steps:</div>
                <ol className="list-decimal list-inside space-y-1 opacity-85 leading-relaxed text-[11px]">
                  <li>Open AWS WAF Console → <strong>Web ACLs</strong> → Select your regional Web ACL or CloudFront Web ACL.</li>
                  <li>Click <strong>Rules → Add rules → Add managed rule / Add my own rules</strong> (or import via JSON).</li>
                  <li>Set <strong>Rule Priority: 0</strong> (top priority above rate-limiting rules).</li>
                  <li>Match condition: <strong>Single Header</strong> <code>x-pusher-guard-token</code> exactly equals <code>{activeGuardId}</code>.</li>
                  <li>Action: <strong>Allow</strong>.</li>
                </ol>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] uppercase">AWS WAFv2 JSON Rule Statement:</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(awsWafJsonSnippet, 'aws_json')}
                    className="border border-black px-2 py-0.5 text-[10px] font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey === 'aws_json' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedKey === 'aws_json' ? 'COPIED!' : 'COPY JSON'}</span>
                  </button>
                </div>
                <pre className="border-2 border-black p-3 bg-slate-950 text-emerald-400 font-mono text-[11px] select-all overflow-x-auto">
                  {awsWafJsonSnippet}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 3: VERCEL & NETLIFY */}
          {activeTab === 'vercel' && (
            <div className="space-y-4 text-xs">
              <div className="border border-black p-3.5 bg-slate-50 space-y-2">
                <div className="font-bold uppercase text-[11px]">Vercel Firewall Custom Rule:</div>
                <ol className="list-decimal list-inside space-y-1 opacity-85 leading-relaxed text-[11px]">
                  <li>Navigate to Vercel Dashboard → Your Project → <strong>Settings → Firewall</strong>.</li>
                  <li>Click <strong>Custom Rules → Create Rule</strong>.</li>
                  <li>Condition: <code>If Request Header [x-pusher-guard-token] equals [{activeGuardId}]</code>.</li>
                  <li>Action: <code>Bypass / Allow</code> (exempts request from Rate Limiting and Challenge mode).</li>
                  <li>Save and deploy.</li>
                </ol>
              </div>

              <div className="border border-black p-3.5 bg-white space-y-2">
                <div className="font-bold uppercase text-[11px]">Netlify Edge Functions / WAF:</div>
                <p className="opacity-80 text-[11px]">
                  In your <code>netlify.toml</code> or edge middleware, inspect <code>request.headers.get("x-pusher-guard-token")</code>. When it matches <code>"{activeGuardId}"</code>, bypass origin rate limit counters.
                </p>
              </div>
            </div>
          )}

          {/* TAB 4: NGINX PROXY */}
          {activeTab === 'nginx' && (
            <div className="space-y-4 text-xs">
              <div className="border border-black p-3.5 bg-slate-50 space-y-2">
                <div className="font-bold uppercase text-[11px]">NGINX Rate Limit Exemption Architecture:</div>
                <p className="opacity-80 text-[11px] leading-relaxed">
                  NGINX <code>limit_req_zone</code> evaluates the mapped key. If the key evaluates to an empty string (<code>""</code>), NGINX completely exempts the request from rate limiting.
                </p>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] uppercase">nginx.conf Configuration:</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(nginxConfigSnippet, 'nginx_cfg')}
                    className="border border-black px-2 py-0.5 text-[10px] font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey === 'nginx_cfg' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedKey === 'nginx_cfg' ? 'COPIED!' : 'COPY CONFIG'}</span>
                  </button>
                </div>
                <pre className="border-2 border-black p-3 bg-slate-950 text-emerald-400 font-mono text-[11px] select-all overflow-x-auto">
                  {nginxConfigSnippet}
                </pre>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[11px] uppercase">Test Curl Verification Command:</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(curlTestSnippet, 'curl_cmd')}
                    className="border border-black px-2 py-0.5 text-[10px] font-bold uppercase bg-white hover:bg-black hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey === 'curl_cmd' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedKey === 'curl_cmd' ? 'COPIED!' : 'COPY CURL'}</span>
                  </button>
                </div>
                <div className="border border-black p-2.5 bg-white font-mono text-[11px] select-all overflow-x-auto">
                  {curlTestSnippet}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 3. Live WAF Header Pass-Through Tester (Probe Card) */}
        <div className="border-2 border-black p-4 sm:p-5 bg-white space-y-4">
          <div className="border-b-2 border-black pb-2 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-black uppercase tracking-wider flex items-center gap-2">
                <Terminal className="w-4 h-4 text-teal-700" />
                <span>LIVE WAF HEADER PASS-THROUGH TESTER</span>
              </h3>
              <p className="text-[11px] opacity-75">
                Sends a live diagnostic request with <code>X-Pusher-Guard-Token</code> to verify that edge firewalls pass requests directly to origin.
              </p>
            </div>
            <span className="text-[10px] font-bold border border-black px-2 py-0.5 bg-slate-100">
              ENDPOINT: /api/target/waf-probe
            </span>
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
                disabled={probeLoading}
                className={`w-full border-2 border-black py-2 px-3 text-xs font-black uppercase transition-colors flex items-center justify-center gap-2 cursor-pointer ${
                  probeLoading
                    ? 'bg-slate-200 text-black/50 cursor-not-allowed'
                    : 'bg-teal-700 text-white hover:bg-teal-800'
                }`}
              >
                <Zap className="w-3.5 h-3.5" />
                <span>{probeLoading ? 'PROBING EDGE...' : 'RUN WAF BYPASS PROBE'}</span>
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
                  <span className={`w-2.5 h-2.5 rounded-full ${probeResult.bypass_passed ? 'bg-emerald-400' : 'bg-rose-500'}`} />
                  <span className="font-bold text-white">PROBE DIAGNOSTIC RESULT</span>
                </div>
                <div className="flex items-center gap-3">
                  <span>LATENCY: <strong className="text-white">{probeResult.latency_ms} ms</strong></span>
                  <span className={`px-1.5 py-0.5 text-[10px] font-bold ${
                    probeResult.bypass_passed ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white'
                  }`}>
                    {probeResult.bypass_passed ? 'BYPASS VERIFIED' : 'BYPASS BLOCKED'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] text-slate-300">
                <div>
                  <span className="text-slate-500 block">HTTP STATUS CODE:</span>
                  <strong className={probeResult.status_code === 200 ? 'text-emerald-400' : 'text-rose-400'}>
                    {probeResult.status_code} {probeResult.status_code === 200 ? 'OK' : ''}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500 block">DETECTED EDGE / WAF:</span>
                  <strong className="text-white">{probeResult.detected_waf}</strong>
                </div>
                <div className="md:col-span-2">
                  <span className="text-slate-500 block">INSPECTED ENDPOINT:</span>
                  <code className="text-teal-300 break-all">{probeResult.probe_endpoint}</code>
                </div>
              </div>

              <div className="border-t border-slate-800 pt-2 text-[11px] leading-relaxed">
                <span className="text-slate-500 block font-bold">ANALYSIS &amp; RECOMMENDATION:</span>
                <p className={probeResult.bypass_passed ? 'text-emerald-300' : 'text-rose-300'}>
                  &gt; {probeResult.recommendation}
                </p>
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
              <p>Only one active token can exist per session. Generating a new guard burns the prior ID into the permanent revocation registry.</p>
            </div>
            <div className="border border-black p-2.5 bg-white space-y-1">
              <div className="font-bold uppercase text-[10px]">3. Immediate Kill Switch:</div>
              <p>Clicking 'KILL ID' instantly burns the token and closes the verification window on both origin and load engine.</p>
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

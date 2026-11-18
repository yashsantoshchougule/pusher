import React, { useState, useEffect, useRef } from 'react';
import {
  Shield,
  Activity,
  AlertTriangle,
  Download,
  CheckSquare,
  Square,
  Play,
  Square as StopSquare,
  Zap,
  Sliders,
  Database,
  FileText,
  MoreVertical,
  RefreshCw,
  AlertOctagon,
  Clock,
  Cpu,
  Layers,
  CheckCircle2,
  XCircle,
  HelpCircle,
  HardDrive,
  ArrowRight,
  ExternalLink,
  Code,
  X,
  History,
  Copy,
  Search,
  Filter,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown
} from 'lucide-react';

// Modular View Components
import OverviewBoxes from '../components/dashboard/OverviewBoxes';
import VerifyTargetView from '../components/dashboard/VerifyTargetView';
import TrafficSetupView from '../components/dashboard/TrafficSetupView';
import ApiBuilderView from '../components/dashboard/ApiBuilderView';
import TestHistoryView from '../components/dashboard/TestHistoryView';
import ReportsView from '../components/dashboard/ReportsView';

export default function DashboardPage({ onLogout }) {
  // Navigation & Dropdown States (6 Views)
  const [activeNav, setActiveNav] = useState('dashboard'); // 'dashboard' | 'verify' | 'traffic' | 'api' | 'history' | 'reports'
  const [menuOpen, setMenuOpen] = useState(false);
  const [sandboxMode, setSandboxMode] = useState(false);
  const [wafModalOpen, setWafModalOpen] = useState(false);

  // Theme Mode: 'production' (polished accents & colored badges) vs 'wireframe' (strict monochrome)
  const [themeMode, setThemeMode] = useState('production');

  // Target Verification & 48h Timer States (Shared across views)
  const [targetUrl, setTargetUrl] = useState('https://api.myproject.dev');
  const [guardToken, setGuardToken] = useState('PG-9065-48H');
  const [isVerified, setIsVerified] = useState(true);
  const [guardTimerSeconds, setGuardTimerSeconds] = useState(172782); // ~47h 59m 42s
  const [verificationError, setVerificationError] = useState(null);

  // Quota & Burn Registry Telemetry (3/Day Rate Limit + Permanent Superseding Burn)
  const [guardQuota, setGuardQuota] = useState({
    used: 0,
    max: 3,
    remaining: 3,
    revokedCount: 0,
    lastRevokedId: null,
  });
  const [supersededNotice, setSupersededNotice] = useState(null);

  // Backend API Base & Hardware Limits
  const API_BASE = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : '';

  const [hardwareLimits, setHardwareLimits] = useState({
    total_system_ram_mb: 16384,
    max_safe_ram_mb: 12288,
    fd_cap_pct: 70,
    open_files_soft: 2048,
  });

  // Set clean white body background on mount and fetch System Limits
  useEffect(() => {
    document.body.style.backgroundColor = '#ffffff';
    const fetchLimits = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/system/limits`);
        if (res.ok) {
          const data = await res.json();
          setHardwareLimits(data);
        }
      } catch {
        // Fallback to standard hardware specs if backend is offline
      }
    };
    fetchLimits();
  }, []);

  // Fetch Target Status & Quota Telemetry
  const fetchTargetStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/target/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.daily_generations_used !== undefined) {
          setGuardQuota({
            used: data.daily_generations_used,
            max: data.daily_generations_max || 3,
            remaining: data.daily_generations_remaining !== undefined ? data.daily_generations_remaining : (3 - data.daily_generations_used),
            revokedCount: data.revoked_count || 0,
            lastRevokedId: data.last_revoked_guard_id || null,
          });
        }
        if (data.is_verified !== undefined) {
          setIsVerified(data.is_verified);
        }
        setGuardToken(data.guard_id || null);
        if (data.remaining_seconds !== undefined) {
          setGuardTimerSeconds(data.remaining_seconds);
        }
      }
    } catch {
      // offline fallback
    }
  };

  useEffect(() => {
    fetchTargetStatus();
  }, [activeNav]);

  // Traffic Setup & Safety Controls (Shared across views)
  const [trafficMode, setTrafficMode] = useState('step_ramp'); // 'step_ramp' | 'sudden_rush' | 'steady_crowd'
  const [ramLimitMb, setRamLimitMb] = useState(500); // 250, 500 (default ceiling), 1024, 2048, or custom
  const [vus, setVus] = useState(460);
  const [duration, setDuration] = useState(60); // 60s, 180s, 300s
  const [max5xxThreshold, setMax5xxThreshold] = useState(5); // 2%, 5%, 10%
  const [wafAutoAbort, setWafAutoAbort] = useState(true);
  const [p95Ceiling, setP95Ceiling] = useState(2000); // 1000, 2000, 5000 ms
  const [cacheBusting, setCacheBusting] = useState(true);
  const [testRunning, setTestRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  // Live Telemetry Stream State
  const [elapsed, setElapsed] = useState(0);
  const [telemetry, setTelemetry] = useState({
    currentVus: 460,
    liveRps: 1180,
    p95Latency: 164,
    errorRate: 0.0,
    circuitBreaker: 'ARMED',
    bytesDiscardedMb: 4.8,
  });

  // Stage 4: Multi-Step API Journey Builder State
  const [useJourney, setUseJourney] = useState(false);
  const [journeySteps, setJourneySteps] = useState([
    {
      step_id: 'step_1',
      name: 'Simulated OAuth Login & Token Issue',
      method: 'POST',
      path: '/api/sandbox/auth/token',
      headers: { 'Content-Type': 'application/json' },
      body: { username: 'load_tester', role: 'tester' },
      expected_status: 200,
      extract_json_key: 'access_token',
    },
    {
      step_id: 'step_2',
      name: 'Fetch Paginated Resource Catalog',
      method: 'GET',
      path: '/api/sandbox/items?limit=20',
      headers: { Authorization: 'Bearer {{token}}' },
      body: null,
      expected_status: 200,
      extract_json_key: null,
    },
    {
      step_id: 'step_3',
      name: 'Process Checkout Order',
      method: 'POST',
      path: '/api/sandbox/checkout',
      headers: { Authorization: 'Bearer {{token}}', 'Content-Type': 'application/json' },
      body: { item_id: 'ITEM-101', quantity: 1 },
      expected_status: 200,
      extract_json_key: null,
    },
  ]);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [dryRunResults, setDryRunResults] = useState(null);
  const [journeyMessage, setJourneyMessage] = useState(null);
  const [stepMetrics, setStepMetrics] = useState([]);

  // Stage 5: Test History & Reports State
  const [historySearch, setHistorySearch] = useState('');
  const [historyModeFilter, setHistoryModeFilter] = useState('ALL');
  const [historyStatusFilter, setHistoryStatusFilter] = useState('ALL');
  const [selectedForCompare, setSelectedForCompare] = useState([]);
  const [selectedReportId, setSelectedReportId] = useState('RUN-103');
  const [singleRunReport, setSingleRunReport] = useState(null);
  const [compareBaseId, setCompareBaseId] = useState('RUN-102');
  const [compareCandidateId, setCompareCandidateId] = useState('RUN-103');
  const [compareData, setCompareData] = useState(null);
  const [reportMode, setReportMode] = useState('single');
  const [latestScorecard, setLatestScorecard] = useState({
    knee_vus: 390,
    peak_rps: 1180,
    p95_ms: 164,
  });

  const [runHistory, setRunHistory] = useState([
    {
      id: 'RUN-103',
      timestamp: '21:18:44',
      target: 'https://api.myproject.dev',
      guardToken: 'PG-9065',
      mode: 'Step-Ramp',
      peakVus: 460,
      duration: 60,
      peakRps: 1180,
      p95: '164 ms',
      status: 'PASSED (Completed 60s)',
      verdictCategory: 'PASSED',
    },
    {
      id: 'RUN-102',
      timestamp: '21:12:05',
      target: 'https://api.myproject.dev',
      guardToken: 'PG-9065',
      mode: 'Sudden Rush',
      peakVus: 460,
      duration: 180,
      peakRps: 1120,
      p95: '188 ms',
      status: 'PASSED (Completed 180s)',
      verdictCategory: 'PASSED',
    },
    {
      id: 'RUN-101',
      timestamp: '21:05:12',
      target: 'https://api.myproject.dev',
      guardToken: 'PG-8411',
      mode: 'Step-Ramp',
      peakVus: 500,
      duration: 60,
      peakRps: 1040,
      p95: '290 ms',
      status: 'MANUAL ABORT (User Stopped)',
      verdictCategory: 'MANUAL_ABORT',
    },
  ]);

  // SSRF Validation Logic
  const validateSsrf = (url, isSandbox) => {
    if (!url || !url.trim()) {
      return { valid: false, message: 'URL cannot be empty' };
    }
    const trimmed = url.trim().toLowerCase();
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      return { valid: false, message: 'Must start with http:// or https://' };
    }
    try {
      const parsed = new URL(trimmed);
      const host = parsed.hostname;
      if (!isSandbox) {
        if (
          host === 'localhost' ||
          host === '127.0.0.1' ||
          host === '0.0.0.0' ||
          host.startsWith('192.168.') ||
          host.startsWith('10.') ||
          host === '169.254.169.254'
        ) {
          return {
            valid: false,
            message: 'SSRF BLOCKED: Loopback / Private IP prohibited without Sandbox',
          };
        }
      }
      return {
        valid: true,
        message: isSandbox
          ? 'SANDBOX DEV MODE: Local target allowed'
          : 'SSRF PASSED: Public target domain eligible',
      };
    } catch {
      return { valid: false, message: 'Malformed URL syntax' };
    }
  };

  const ssrfCheck = validateSsrf(targetUrl, sandboxMode);

  // 48-Hour Live Countdown Timer
  useEffect(() => {
    if (!isVerified || guardTimerSeconds <= 0) return;
    const interval = setInterval(() => {
      setGuardTimerSeconds((prev) => {
        if (prev <= 1) {
          setIsVerified(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isVerified, guardTimerSeconds]);

  const formatTimer = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  // Real-Time WebSocket Telemetry Client
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    const connectWs = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Connect to 127.0.0.1:8000 directly or via Vite proxy
        const wsUrl = `${protocol}//${window.location.host}/api/load/ws`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.is_running !== undefined) {
              setElapsed(data.elapsed_sec);
              setTelemetry({
                currentVus: data.current_vus ?? 460,
                liveRps: data.live_rps ?? 0,
                p95Latency: data.p95_latency_ms ?? 0,
                errorRate: data.error_rate_pct ?? 0.0,
                circuitBreaker: data.circuit_status ?? 'ARMED',
                bytesDiscardedMb: data.bytes_discarded_mb ?? 0,
              });
              setTestRunning(data.is_running);
              if (data.step_metrics) {
                setStepMetrics(data.step_metrics);
              }
              if (data.use_journey !== undefined) {
                setUseJourney(data.use_journey);
              }
              if (data.run_history && data.run_history.length > 0) {
                setRunHistory(data.run_history);
              }
            }
          } catch { }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 2000);
        };

        ws.onerror = () => {
          setWsConnected(false);
        };
      } catch {
        setWsConnected(false);
      }
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  // Polling fallback when test is running
  const testTimerRef = useRef(null);
  useEffect(() => {
    if (!testRunning) {
      if (testTimerRef.current) clearInterval(testTimerRef.current);
      return;
    }

    testTimerRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/load/status`);
        if (res.ok) {
          const data = await res.json();
          setElapsed(data.elapsed_sec);
          setTelemetry({
            currentVus: data.current_vus ?? 460,
            liveRps: data.live_rps ?? 0,
            p95Latency: data.p95_latency_ms ?? 0,
            errorRate: data.error_rate_pct ?? 0.0,
            circuitBreaker: data.circuit_status ?? 'ARMED',
            bytesDiscardedMb: data.bytes_discarded_mb ?? 0,
          });
          if (data.step_metrics) {
            setStepMetrics(data.step_metrics);
          }
          if (data.use_journey !== undefined) {
            setUseJourney(data.use_journey);
          }
          if (data.run_history && data.run_history.length > 0) {
            setRunHistory(data.run_history);
          }
          if (!data.is_running) {
            setTestRunning(false);
            clearInterval(testTimerRef.current);
          }
          return;
        }
      } catch { }
    }, 1000);

    return () => clearInterval(testTimerRef.current);
  }, [testRunning]);

  // Actions: Download Guard with Rate Limiting (3/Day) & Superseding Feedback
  const handleDownloadGuard = async () => {
    setVerificationError(null);
    setSupersededNotice(null);
    let guardData = null;

    try {
      const res = await fetch(`${API_BASE}/api/target/generate-guard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_url: targetUrl,
          is_sandbox: Boolean(sandboxMode),
        }),
      });

      if (res.status === 429) {
        const err = await res.json();
        setVerificationError(err.detail || 'Daily Guard generation limit reached (3 per 24 hours). Downloads are locked.');
        return;
      }

      if (res.ok) {
        guardData = await res.json();
      } else {
        const err = await res.json();
        setVerificationError(err.detail || 'Failed to generate pusher_guard.py');
        return;
      }
    } catch {
      // Fallback
    }

    if (guardData?.guard_id) {
      setGuardToken(guardData.guard_id);
      setIsVerified(false); // Newly generated guard requires re-verification

      // Update quota telemetry
      setGuardQuota({
        used: guardData.daily_generations_used ?? (guardQuota.used + 1),
        max: guardData.daily_generations_max ?? 3,
        remaining: guardData.daily_generations_remaining ?? Math.max(0, 3 - (guardQuota.used + 1)),
        revokedCount: guardData.revoked_count ?? (guardQuota.revokedCount + 1),
        lastRevokedId: guardData.last_revoked_guard_id || null,
      });

      if (guardData.superseded_guard_id) {
        setSupersededNotice(
          `Previous Guard ID ${guardData.superseded_guard_id} superseded and permanently burned into revocation registry.`
        );
      }
    }

    const scriptContent = guardData?.content || `# pusher_guard.py\nGUARD_TOKEN = "${guardToken}"\n`;

    const blob = new Blob([scriptContent], { type: 'text/x-python;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', guardData?.filename || 'pusher_guard.py');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleVerifyTarget = async () => {
    setVerificationError(null);
    if (!ssrfCheck.valid) {
      setVerificationError(ssrfCheck.message);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/target/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_url: targetUrl,
          guard_id: guardToken,
          is_sandbox: Boolean(sandboxMode),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setIsVerified(true);
        setGuardTimerSeconds(data.remaining_seconds || 172800);
        return;
      } else {
        const err = await res.json();
        const msg = err.detail?.detail || err.detail || 'Verification challenge failed.';
        setVerificationError(msg);
        return;
      }
    } catch {
      if (sandboxMode) {
        setIsVerified(true);
        setGuardTimerSeconds(172800);
      } else {
        setVerificationError('Target unreachable. Verify endpoint or enable Sandbox Simulation.');
      }
    }
  };

  const handleKillGuard = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/target/kill`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsVerified(false);
        setGuardToken(null);
        setGuardTimerSeconds(0);
        setSupersededNotice(
          `Guard ID ${guardToken || ''} has been permanently revoked and burned. Verification locked.`
        );
        fetchTargetStatus();
      }
    } catch {
      setIsVerified(false);
      setGuardToken(null);
      setGuardTimerSeconds(0);
    }
  };

  // Stage 4 Journey Handlers
  const handleUpdateStep = (index, field, value) => {
    setJourneySteps((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleAddStep = () => {
    const nextIdx = journeySteps.length + 1;
    setJourneySteps((prev) => [
      ...prev,
      {
        step_id: `step_${nextIdx}`,
        name: `Sequential Action ${nextIdx}`,
        method: 'GET',
        path: `/api/sandbox/resource_${nextIdx}`,
        headers: { Authorization: 'Bearer {{token}}' },
        body: null,
        expected_status: 200,
        extract_json_key: null,
      },
    ]);
  };

  const handleDeleteStep = (index) => {
    if (journeySteps.length <= 1) return;
    setJourneySteps((prev) => prev.filter((_, i) => i !== index));
  };

  const handleMoveStep = (index, delta) => {
    const targetIdx = index + delta;
    if (targetIdx < 0 || targetIdx >= journeySteps.length) return;
    setJourneySteps((prev) => {
      const copy = [...prev];
      const temp = copy[index];
      copy[index] = copy[targetIdx];
      copy[targetIdx] = temp;
      return copy;
    });
  };

  const handleResetJourneyDefaults = () => {
    setJourneySteps([
      {
        step_id: 'step_1',
        name: 'Simulated OAuth Login & Token Issue',
        method: 'POST',
        path: '/api/sandbox/auth/token',
        headers: { 'Content-Type': 'application/json' },
        body: { username: 'load_tester', role: 'tester' },
        expected_status: 200,
        extract_json_key: 'access_token',
      },
      {
        step_id: 'step_2',
        name: 'Fetch Paginated Resource Catalog',
        method: 'GET',
        path: '/api/sandbox/items?limit=20',
        headers: { Authorization: 'Bearer {{token}}' },
        body: null,
        expected_status: 200,
        extract_json_key: null,
      },
      {
        step_id: 'step_3',
        name: 'Process Checkout Order',
        method: 'POST',
        path: '/api/sandbox/checkout',
        headers: { Authorization: 'Bearer {{token}}', 'Content-Type': 'application/json' },
        body: { item_id: 'ITEM-101', quantity: 1 },
        expected_status: 200,
        extract_json_key: null,
      },
    ]);
    setJourneyMessage('Reset journey steps to Sandbox defaults.');
  };

  const handleExecuteDryRun = async () => {
    setIsDryRunning(true);
    setJourneyMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/journey/dry-run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps: journeySteps }),
      });
      if (res.ok) {
        const data = await res.json();
        setDryRunResults(data);
        if (data.all_passed) {
          setJourneyMessage(`1-VU Dry-Run PASSED (${data.total_steps}/${data.total_steps} steps). Token chaining verified.`);
        } else {
          setJourneyMessage(`1-VU Dry-Run FAILED: ${data.steps.filter((s) => !s.passed).length} step(s) failed.`);
        }
      } else {
        const err = await res.json();
        setJourneyMessage(err.detail || 'Dry-run execution failed.');
      }
    } catch {
      setJourneyMessage('Error contacting backend for dry-run.');
    } finally {
      setIsDryRunning(false);
    }
  };

  const handleSaveJourney = async (enable = null) => {
    const newUseJourney = enable !== null ? enable : useJourney;
    try {
      const res = await fetch(`${API_BASE}/api/journey/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          steps: journeySteps,
          use_journey: newUseJourney,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setJourneySteps(data.steps);
        setUseJourney(data.use_journey);
        setJourneyMessage('Multi-step journey configuration saved.');
        return true;
      } else {
        const err = await res.json();
        setJourneyMessage(err.detail || 'Failed to save journey.');
        return false;
      }
    } catch {
      setJourneyMessage('Error contacting backend to save journey.');
      return false;
    }
  };

  const handleSaveAndLaunchJourney = async () => {
    await handleSaveJourney(true);
    setUseJourney(true);
    handleStartTest();
  };

  const handleStartTest = async () => {
    if (!isVerified) {
      setActiveNav('verify');
      setVerificationError('Target must be verified with active 48h guard before launching test.');
      return;
    }
    setVerificationError(null);

    try {
      const isSandboxTarget = sandboxMode || targetUrl.includes('sandbox.pusher.local') || targetUrl.includes('/api/sandbox/target');
      const resolvedTarget = isSandboxTarget && !targetUrl.startsWith('http')
        ? `${API_BASE}/api/sandbox/target`
        : targetUrl;

      const res = await fetch(`${API_BASE}/api/load/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_url: resolvedTarget,
          traffic_mode: trafficMode,
          target_vus: vus,
          duration_sec: duration,
          cache_bust: cacheBusting,
          ram_limit_mb: ramLimitMb,
          max_error_pct: max5xxThreshold,
          p95_ceiling_ms: p95Ceiling,
          is_sandbox: isSandboxTarget,
          use_journey: useJourney,
          journey_steps: useJourney ? journeySteps : null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setTestRunning(true);
        setElapsed(0);
        setActiveNav('dashboard');
        return;
      } else {
        const err = await res.json();
        setActiveNav('verify');
        setVerificationError(err.detail || 'Failed to start load test.');
      }
    } catch {
      // Local fallback simulation
      setTestRunning(true);
      setElapsed(0);
      setActiveNav('dashboard');
    }
  };

  const handleStopTest = async () => {
    try {
      await fetch(`${API_BASE}/api/load/stop`, { method: 'POST' });
    } catch { }
    setTestRunning(false);
  };

  const handleSimulateSpike = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/load/simulate-spike`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error_burst_count: 50, status_code: 503 }),
      });
      if (res.ok) {
        const data = await res.json();
        setTelemetry((prev) => ({
          ...prev,
          errorRate: data.error_rate_pct || 18.5,
          circuitBreaker: data.circuit_status || 'AUTO-ABORT (TRIPPED: 5xx Spike)',
        }));
        setTestRunning(false);
        return;
      }
    } catch { }

    setTelemetry((prev) => ({
      ...prev,
      errorRate: 18.5,
      circuitBreaker: 'AUTO-ABORT (TRIPPED: 5xx Spike)',
    }));
    setTestRunning(false);
  };

  // Stage 5 History & Report Actions
  const fetchHistory = async () => {
    try {
      const params = new URLSearchParams();
      if (historyModeFilter && historyModeFilter !== 'ALL') params.append('mode', historyModeFilter);
      if (historyStatusFilter && historyStatusFilter !== 'ALL') params.append('verdict', historyStatusFilter);
      if (historySearch && historySearch.trim()) params.append('q', historySearch.trim());

      const res = await fetch(`${API_BASE}/api/history?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        if (data.runs && data.runs.length > 0) {
          setRunHistory(data.runs);
        }
        if (data.scorecard) {
          setLatestScorecard(data.scorecard);
        }
      }
    } catch { }
  };

  useEffect(() => {
    fetchHistory();
  }, [activeNav, historyModeFilter, historyStatusFilter]);

  const handleClearArchive = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/history`, { method: 'DELETE' });
      if (res.ok) {
        const data = await res.json();
        setRunHistory(data.runs || []);
        if (data.scorecard) setLatestScorecard(data.scorecard);
        setSelectedForCompare([]);
      }
    } catch {
      setRunHistory([]);
      setSelectedForCompare([]);
    }
  };

  const handleViewSingleReport = async (runId) => {
    const idToFetch = runId || selectedReportId || 'RUN-103';
    try {
      const res = await fetch(`${API_BASE}/api/reports/${idToFetch}`);
      if (res.ok) {
        const data = await res.json();
        setSingleRunReport(data);
        setSelectedReportId(idToFetch);
        setReportMode('single');
        setActiveNav('reports');
        return;
      }
    } catch { }
    setSelectedReportId(idToFetch);
    setReportMode('single');
    setActiveNav('reports');
  };

  const handleCompareRuns = async (baseId, candId) => {
    const base = baseId || compareBaseId || (selectedForCompare.length >= 2 ? selectedForCompare[1] : 'RUN-102');
    const cand = candId || compareCandidateId || (selectedForCompare.length >= 1 ? selectedForCompare[0] : 'RUN-103');
    try {
      const res = await fetch(`${API_BASE}/api/reports/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_run_id: base, candidate_run_id: cand }),
      });
      if (res.ok) {
        const data = await res.json();
        setCompareData(data);
        setCompareBaseId(base);
        setCompareCandidateId(cand);
        setReportMode('compare');
        setActiveNav('reports');
        return;
      }
    } catch { }
    setCompareBaseId(base);
    setCompareCandidateId(cand);
    setReportMode('compare');
    setActiveNav('reports');
  };

  const handleExportReport = (runId) => {
    const id = runId || selectedReportId || 'RUN-103';
    window.open(`${API_BASE}/api/reports/${id}/export`, '_blank');
  };

  const handleCloneRun = (run) => {
    const matchedMode = run.mode.toLowerCase().includes('step') ? 'step_ramp' : run.mode.toLowerCase().includes('rush') ? 'sudden_rush' : 'steady_crowd';
    setTrafficMode(matchedMode);
    setVus(run.peakVus || run.vus || 460);
    setDuration(run.duration || 60);
    setActiveNav('traffic');
  };

  const toggleCompareRun = (runId) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(runId)) {
        return prev.filter((id) => id !== runId);
      }
      if (prev.length >= 2) {
        return [prev[1], runId];
      }
      return [...prev, runId];
    });
  };

  const filteredRuns = runHistory.filter((run) => {
    const runId = run.id || run.run_id || '';
    const matchSearch = runId.toLowerCase().includes(historySearch.toLowerCase()) || (run.target || '').toLowerCase().includes(historySearch.toLowerCase());
    const matchMode = historyModeFilter === 'ALL' || (run.mode || '').toUpperCase().includes(historyModeFilter);
    const matchStatus = historyStatusFilter === 'ALL' || run.verdictCategory === historyStatusFilter;
    return matchSearch && matchMode && matchStatus;
  });

  // RAM & Concurrency Scaling Model
  const BASE_ENGINE_RAM_MB = 50;
  const RAM_PER_VU_MB = 0.20;
  const SYSTEM_HOST_RAM_MB = hardwareLimits.total_system_ram_mb || 16384;
  const maxHardwareSafeRamMb = hardwareLimits.max_safe_ram_mb || Math.floor(SYSTEM_HOST_RAM_MB * 0.75);
  const maxAllowedVus = Math.floor((ramLimitMb - BASE_ENGINE_RAM_MB) / RAM_PER_VU_MB);
  const estimatedRam = Math.min(ramLimitMb, Math.round(BASE_ENGINE_RAM_MB + vus * RAM_PER_VU_MB));
  const estimatedFdPercent = Math.min(70, Math.round(15 + (vus / Math.max(1, maxAllowedVus)) * 55));
  const modeLabel = trafficMode === 'step_ramp' ? 'STEP-RAMP' : trafficMode === 'sudden_rush' ? 'SUDDEN RUSH' : 'STEADY CROWD';

  const handleSetRamLimit = (newLimit) => {
    const parsed = Math.max(100, Math.min(maxHardwareSafeRamMb, Number(newLimit) || 500));
    setRamLimitMb(parsed);
    const newMaxVus = Math.floor((parsed - BASE_ENGINE_RAM_MB) / RAM_PER_VU_MB);
    if (vus > newMaxVus) {
      setVus(newMaxVus);
    }
  };

  return (
    <div className="min-h-screen w-full bg-white text-black font-mono selection:bg-black selection:text-white flex flex-col antialiased">
      {/* ========================================================================= */}
      {/* TOP HEADER                                                                */}
      {/* ========================================================================= */}
      <header className="w-full h-16 border-b-2 border-black px-4 sm:px-6 flex items-center justify-between bg-white z-30 shrink-0">
        <div className="flex items-center gap-3">
          <div
            onClick={() => setActiveNav('dashboard')}
            className="border-2 border-black px-2.5 py-1 text-sm sm:text-base font-black tracking-widest bg-white cursor-pointer select-none"
          >
            PUSHER
          </div>
          <span className="hidden md:inline-block border border-black px-2 py-0.5 text-xs font-bold uppercase tracking-wider bg-white">
            [ WIREFRAME v1.0 ]
          </span>

          {/* 1-Click UI Switcher: PRODUCTION vs WIREFRAME */}
          <button
            type="button"
            onClick={() => setThemeMode(themeMode === 'production' ? 'wireframe' : 'production')}
            className={`border-2 border-black px-2.5 py-0.5 text-xs font-black uppercase tracking-wider transition-colors cursor-pointer ${themeMode === 'production'
              ? 'bg-teal-700 text-white hover:bg-teal-800'
              : 'bg-white text-black hover:bg-black hover:text-white'
              }`}
            title="Toggle theme styling between Production color badges and strict monochrome wireframe"
          >
            UI: {themeMode.toUpperCase()}
          </button>
        </div>

        {/* Center Live Engine Status & Telemetry Caps */}
        <div className="hidden lg:flex items-center gap-6 border-2 border-black px-4 py-1.5 text-xs font-bold bg-white">
          <div className="flex items-center gap-2">
            <span className={`inline-block w-2.5 h-2.5 border-2 border-black ${testRunning
              ? (themeMode === 'production' ? 'bg-emerald-500 animate-ping' : 'bg-black animate-ping')
              : 'bg-black'
              }`} />
            <span>ENGINE: LOCAL ASYNC WORKER</span>
          </div>
          <span className="border-l-2 border-black h-3.5" />
          <div>
            <span>RAM: {testRunning ? estimatedRam : 50} MB / {ramLimitMb} MB MAX</span>
            <span className="text-[10px] ml-1.5 opacity-80">(4KB Chunk Discard Active)</span>
          </div>
          <span className="border-l-2 border-black h-3.5" />
          <div>
            <span>FD CAP: 70% OS LIMIT</span>
          </div>
        </div>

        {/* Right Action Menu: ••• */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            className="border-2 border-black px-3 py-1 font-black text-sm tracking-widest hover:bg-black hover:text-white transition-colors cursor-pointer"
            aria-label="Options Menu"
          >
            •••
          </button>

          {menuOpen && (
            <div className="absolute right-0 mt-2 w-64 border-2 border-black bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] z-50 text-xs">
              <div className="p-3 border-b-2 border-black font-bold uppercase flex justify-between items-center">
                <span>Pusher Options</span>
                <span className="text-[10px] opacity-75">v1.0.0</span>
              </div>
              <div className="p-1 space-y-0.5">
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setWafModalOpen(true);
                  }}
                  className="w-full text-left px-3 py-2 font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-between"
                >
                  <span>WAF Setup Guide</span>
                  <Code className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setActiveNav('reports');
                  }}
                  className="w-full text-left px-3 py-2 font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-between"
                >
                  <span>Capacity Reports</span>
                  <FileText className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setActiveNav('history');
                  }}
                  className="w-full text-left px-3 py-2 font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-between"
                >
                  <span>Run History</span>
                  <History className="w-3.5 h-3.5" />
                </button>
                <div className="border-t border-black my-1" />
                <button
                  type="button"
                  onClick={onLogout}
                  className="w-full text-left px-3 py-2 font-bold uppercase text-red-600 hover:bg-red-600 hover:text-white transition-colors flex items-center justify-between"
                >
                  <span>Log Out / Exit</span>
                  <span>→</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* ========================================================================= */}
      {/* 2-COLUMN MAIN LAYOUT: LEFT SIDEBAR + MAIN CONTENT AREA                   */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col md:flex-row bg-white">

        {/* LEFT SIDEBAR: 6 DISTINCT VIEWS */}
        <aside className="w-full md:w-64 border-b-2 md:border-b-0 md:border-r-2 border-black p-4 bg-white flex flex-col justify-between shrink-0">
          <div className="space-y-4">
            <div className="text-xs font-black uppercase tracking-wider text-black/60 pb-1 border-b border-black">
              [ NAVIGATION ]
            </div>

            <nav className="flex flex-col gap-1.5">
              {[
                { id: 'dashboard', label: '1. Dashboard', desc: 'Read-only 3-Box Overview' },
                { id: 'verify', label: '2. Verify Target', desc: '48h Guard & SSRF Security' },
                { id: 'traffic', label: '3. Traffic Setup', desc: 'Curve, Concurrency & Caps' },
                { id: 'api', label: '4. API Builder', desc: 'Multi-Step Request Chains' },
                { id: 'history', label: '5. Test History', desc: 'Searchable Runs Archive' },
                { id: 'reports', label: '6. Reports', desc: 'Knee Curve & Comparison' },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveNav(item.id)}
                  className={`w-full text-left p-2.5 border-2 border-black text-xs font-bold uppercase transition-colors cursor-pointer ${activeNav === item.id
                    ? (themeMode === 'production' ? 'bg-slate-900 text-white' : 'bg-black text-white')
                    : 'bg-white text-black hover:bg-black hover:text-white'
                    }`}
                >
                  <div className="flex items-center justify-between">
                    <span>{item.label}</span>
                    {activeNav === item.id && <span>●</span>}
                  </div>
                  <div className="text-[10px] normal-case opacity-75 font-normal mt-0.5">
                    {item.desc}
                  </div>
                </button>
              ))}
            </nav>
          </div>

          {/* Sidebar System Telemetry Footer */}
          <div className="mt-6 pt-4 border-t-2 border-black space-y-2 text-xs">
            <div className="flex justify-between items-center text-[10px] font-bold">
              <span>ACTIVE TARGET:</span>
              <span className={`px-1 text-[9px] uppercase border border-black ${isVerified
                ? (themeMode === 'production' ? 'bg-emerald-600 text-white' : 'bg-black text-white')
                : 'bg-white text-black'
                }`}>
                {isVerified ? 'VERIFIED' : 'UNVERIFIED'}
              </span>
            </div>
            <div className="font-mono text-[10px] truncate border border-black p-1.5 bg-white">
              {targetUrl}
            </div>
            <div className="flex justify-between items-center text-[10px]">
              <span className="font-bold">GUARD TOKEN:</span>
              <span className="font-mono font-bold">{isVerified ? guardToken : 'EXPIRED'}</span>
            </div>
            <div className="flex justify-between items-center text-[10px]">
              <span className="font-bold">48H EXPIRY:</span>
              <span className="font-mono font-bold">
                {isVerified ? formatTimer(guardTimerSeconds) : '00:00:00'}
              </span>
            </div>
            <div className="flex justify-between items-center text-[10px]">
              <span className="font-bold">GUARD QUOTA:</span>
              <span className="font-mono font-bold">
                {guardQuota.remaining} / {guardQuota.max || 3} left
              </span>
            </div>
          </div>
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-1 p-4 sm:p-6 space-y-6 bg-white pb-24">

          {/* VIEW 1: `1. Dashboard` (READ-ONLY 3-BOX SUMMARY SCREEN) */}
          {activeNav === 'dashboard' && (
            <OverviewBoxes
              targetUrl={targetUrl}
              isVerified={isVerified}
              guardToken={guardToken}
              guardTimerSeconds={guardTimerSeconds}
              formatTimer={formatTimer}
              ssrfCheck={ssrfCheck}
              latestScorecard={latestScorecard}
              modeLabel={modeLabel}
              vus={vus}
              duration={duration}
              estimatedRam={estimatedRam}
              ramLimitMb={ramLimitMb}
              testRunning={testRunning}
              elapsed={elapsed}
              telemetry={telemetry}
              stepMetrics={stepMetrics}
              useJourney={useJourney}
              handleStartTest={handleStartTest}
              handleStopTest={handleStopTest}
              handleSimulateSpike={handleSimulateSpike}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 2: `2. Verify Target` */}
          {activeNav === 'verify' && (
            <VerifyTargetView
              targetUrl={targetUrl}
              setTargetUrl={setTargetUrl}
              sandboxMode={sandboxMode}
              setSandboxMode={setSandboxMode}
              ssrfCheck={ssrfCheck}
              guardToken={guardToken}
              isVerified={isVerified}
              guardTimerSeconds={guardTimerSeconds}
              formatTimer={formatTimer}
              verificationError={verificationError}
              setVerificationError={setVerificationError}
              guardQuota={guardQuota}
              supersededNotice={supersededNotice}
              handleDownloadGuard={handleDownloadGuard}
              handleVerifyTarget={handleVerifyTarget}
              handleKillGuard={handleKillGuard}
              setWafModalOpen={setWafModalOpen}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 3: `3. Traffic Setup` */}
          {activeNav === 'traffic' && (
            <TrafficSetupView
              trafficMode={trafficMode}
              setTrafficMode={setTrafficMode}
              ramLimitMb={ramLimitMb}
              handleSetRamLimit={handleSetRamLimit}
              maxHardwareSafeRamMb={maxHardwareSafeRamMb}
              vus={vus}
              setVus={setVus}
              maxAllowedVus={maxAllowedVus}
              duration={duration}
              setDuration={setDuration}
              max5xxThreshold={max5xxThreshold}
              setMax5xxThreshold={setMax5xxThreshold}
              wafAutoAbort={wafAutoAbort}
              setWafAutoAbort={setWafAutoAbort}
              p95Ceiling={p95Ceiling}
              setP95Ceiling={setP95Ceiling}
              cacheBusting={cacheBusting}
              setCacheBusting={setCacheBusting}
              estimatedRam={estimatedRam}
              estimatedFdPercent={estimatedFdPercent}
              isVerified={isVerified}
              handleStartTest={handleStartTest}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 4: `4. API Builder` */}
          {activeNav === 'api' && (
            <ApiBuilderView
              journeySteps={journeySteps}
              setJourneySteps={setJourneySteps}
              useJourney={useJourney}
              setUseJourney={setUseJourney}
              journeyMessage={journeyMessage}
              setJourneyMessage={setJourneyMessage}
              isDryRunning={isDryRunning}
              dryRunResults={dryRunResults}
              handleUpdateStep={handleUpdateStep}
              handleAddStep={handleAddStep}
              handleDeleteStep={handleDeleteStep}
              handleMoveStep={handleMoveStep}
              handleResetJourneyDefaults={handleResetJourneyDefaults}
              handleExecuteDryRun={handleExecuteDryRun}
              handleSaveJourney={handleSaveJourney}
              handleSaveAndLaunchJourney={handleSaveAndLaunchJourney}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 5: `5. Test History` */}
          {activeNav === 'history' && (
            <TestHistoryView
              runHistory={runHistory}
              filteredRuns={filteredRuns}
              historySearch={historySearch}
              setHistorySearch={setHistorySearch}
              historyModeFilter={historyModeFilter}
              setHistoryModeFilter={setHistoryModeFilter}
              historyStatusFilter={historyStatusFilter}
              setHistoryStatusFilter={setHistoryStatusFilter}
              selectedForCompare={selectedForCompare}
              toggleCompareRun={toggleCompareRun}
              handleCompareRuns={handleCompareRuns}
              handleClearArchive={handleClearArchive}
              handleViewSingleReport={handleViewSingleReport}
              handleCloneRun={handleCloneRun}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 6: `6. Reports` */}
          {activeNav === 'reports' && (
            <ReportsView
              reportMode={reportMode}
              setReportMode={setReportMode}
              runHistory={runHistory}
              selectedReportId={selectedReportId}
              singleRunReport={singleRunReport}
              compareBaseId={compareBaseId}
              setCompareBaseId={setCompareBaseId}
              compareCandidateId={compareCandidateId}
              setCompareCandidateId={setCompareCandidateId}
              compareData={compareData}
              handleViewSingleReport={handleViewSingleReport}
              handleCompareRuns={handleCompareRuns}
              handleExportReport={handleExportReport}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

        </main>
      </div>

      {/* ========================================================================= */}
      {/* WAF & MIDDLEWARE FULL GUIDE MODAL DRAWER                                  */}
      {/* ========================================================================= */}
      {wafModalOpen && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white border-2 border-black max-w-2xl w-full p-6 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b-2 border-black pb-3">
              <h3 className="text-base font-black uppercase">
                COMPLETE WAF &amp; MIDDLEWARE BYPASS GUIDE
              </h3>
              <button
                type="button"
                onClick={() => setWafModalOpen(false)}
                className="border-2 border-black px-2 py-1 text-xs font-black hover:bg-black hover:text-white cursor-pointer"
              >
                ✕ CLOSE
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="border border-black p-3">
                <span className="font-bold block uppercase mb-1">1. How Pusher Guard Works:</span>
                <p>
                  Pusher Guard uses an out-of-band token (<code className="font-bold">{guardToken}</code>) validated in application middleware to confirm the tester owns the infrastructure. This prevents accidental DDoS against unauthorized third parties.
                </p>
              </div>

              <div className="border border-black p-3">
                <span className="font-bold block uppercase mb-1">2. Cloudflare Rate Limiting Skip Rule:</span>
                <p className="mb-2">
                  To prevent Cloudflare from blocking load tests with HTTP 429 challenges, create a WAF Custom Skip Rule:
                </p>
                <div className="bg-black text-white p-2 text-[10px] font-mono">
                  Expression: http.request.headers["x-pusher-guard"] eq "{guardToken}"<br />
                  Action: Skip &gt; All Rate Limiting Rules
                </div>
              </div>

              <div className="border border-black p-3">
                <span className="font-bold block uppercase mb-1">3. Automated Token Expiry &amp; Rate Limits:</span>
                <p>
                  Tokens are valid for exactly 48 hours ({formatTimer(guardTimerSeconds)} remaining). Once expired, all tests immediately lock until re-verification occurs. Generation is rate-limited to 3 downloads per rolling 24 hours.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setWafModalOpen(false)}
              className="w-full border-2 border-black py-2 text-xs font-bold uppercase bg-black text-white hover:bg-white hover:text-black transition-colors cursor-pointer"
            >
              ACKNOWLEDGE &amp; RETURN
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

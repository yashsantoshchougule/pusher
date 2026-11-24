import { journeyRequestError, restoreJourneyInputs, saveAndLaunchJourney } from '../lib/journeyLaunch';
import { restoreTargetQuery, targetOrigin, targetTemplate } from '../lib/targetInput';
import { mapTelemetry } from '../lib/telemetry';
import { operatorFetch, operatorToken } from '../lib/operatorApi';
import { watchRun } from '../lib/runMonitor';
import { createTrafficProfile, DEFAULT_TRAFFIC_PROFILE, trafficPhases } from '../lib/trafficProfile';
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
  ArrowDown,
  User
} from 'lucide-react';

// Modular View Components
import OverviewBoxes from '../components/dashboard/OverviewBoxes';
import VerifyTargetView from '../components/dashboard/VerifyTargetView';
import TrafficSetupView from '../components/dashboard/TrafficSetupView';
import ApiBuilderView from '../components/dashboard/ApiBuilderView';
import TestHistoryView from '../components/dashboard/TestHistoryView';
import ReportsView from '../components/dashboard/ReportsView';
import ProfileView from '../components/dashboard/ProfileView';
import { getDeviceId } from '../utils/deviceFingerprint';

export default function DashboardPage({ operator, onLogout, onNavigate, appearance = 'light', onAppearanceChange }) {
  const maxJourneySteps = 10;
  // Navigation & Dropdown States (7 Views)
  const [activeNav, setActiveNav] = useState('dashboard'); // 'dashboard' | 'verify' | 'traffic' | 'api' | 'history' | 'reports' | 'profile'
  const [menuOpen, setMenuOpen] = useState(false);
  const [sandboxMode, setSandboxMode] = useState(false);
  const [sandboxTargetUrl, setSandboxTargetUrl] = useState(null);
  const liveTargetDraft = useRef(null);
  const [wafModalOpen, setWafModalOpen] = useState(false);

  // Theme Mode: 'production' (polished accents & colored badges) vs 'wireframe' (strict monochrome)
  const [themeMode, setThemeMode] = useState('production');

  // Device Lock State (Deterministic hardware fingerprint DEV-XXXXXXXXXXXX)
  const [deviceId, setDeviceId] = useState('DEV-LOCAL-CREATOR');
  const [lastBurnReason, setLastBurnReason] = useState(null);

  // Target Verification & 48h Timer States (Shared across views - Zero hardcoded values)
  const [targetUrl, setTargetUrl] = useState('');
  const [confirmedTarget, setConfirmedTarget] = useState('');
  const [confirmedSandbox, setConfirmedSandbox] = useState(false);
  const [requiresTargetQuery, setRequiresTargetQuery] = useState(false);
  const targetGuardRef = useRef(null);
  const [guardToken, setGuardToken] = useState(null);
  const sandboxRequiresRevocation = sandboxMode && Boolean(guardToken) && !confirmedSandbox;
  const [guardChecksum, setGuardChecksum] = useState(null);
  const [isGuardVerified, setIsGuardVerified] = useState(false);
  const [guardTimerSeconds, setGuardTimerSeconds] = useState(0);
  const verifiedOrigin = isGuardVerified ? targetOrigin(confirmedTarget) : null;
  const isVerified = Boolean(verifiedOrigin && sandboxMode === confirmedSandbox && targetOrigin(targetUrl) === verifiedOrigin);
  const [verificationError, setVerificationError] = useState(null);
  const [urlValidation, setUrlValidation] = useState({
    checking: false,
    valid: true,
    ready: false,
    status: 'IDLE',
    message: '',
    suggestions: [],
    resolved_ip: null,
  });

  // Quota & Burn Registry Telemetry (3/Day Rate Limit + Permanent Superseding Burn)
  const [guardQuota, setGuardQuota] = useState({
    used: 0,
    max: 3,
    remaining: 3,
    revokedCount: 0,
    lastRevokedId: null,
  });
  const [supersededNotice, setSupersededNotice] = useState(null);

  // Backend API Base & Hardware Limits (Dynamically populated from /api/system/limits)
  const [hardwareLimits, setHardwareLimits] = useState(null);

  // Traffic Setup & Safety Controls (Shared across views)
  const [trafficConfig, setTrafficConfig] = useState(DEFAULT_TRAFFIC_PROFILE);
  const [trafficLoading, setTrafficLoading] = useState(true);
  const [trafficSaveError, setTrafficSaveError] = useState('');
  const [trafficCloneNotice, setTrafficCloneNotice] = useState('');
  const [trafficSaving, setTrafficSaving] = useState(false);
  const trafficActionInProgress = useRef(false);
  const trafficProfile = useRef(null);
  if (!trafficProfile.current) {
    trafficProfile.current = createTrafficProfile(operatorFetch, setTrafficConfig, setTrafficSaveError);
  }
  const {
    mode: trafficMode, ram_limit_mb: ramLimitMb, virtual_users: vus, duration_sec: duration,
    max_error_pct: max5xxThreshold, p95_ceiling_ms: p95Ceiling, cache_bust: cacheBusting,
  } = trafficConfig;
  const [runStatus, setRunStatus] = useState(null);
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState('');
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState('');
  const launchInProgress = useRef(false);
  const runMonitor = useRef(null);
  const testRunning = runStatus?.is_running ?? false;
  const canStart = Boolean(runStatus && !testRunning && !statusUnavailable && !launching);
  const telemetry = mapTelemetry(runStatus ?? undefined);
  const elapsed = runStatus?.elapsed_sec ?? 0;

  // Stage 4: Multi-Step API Journey Builder State
  const [useJourney, setUseJourney] = useState(false);
  const [journeySteps, setJourneySteps] = useState([]);
  const [journeySelectionStatus, setJourneySelectionStatus] = useState('loading');
  const journeyModeEdited = useRef(false);
  const journeyStepsEdited = useRef(false);
  const journeyRevision = useRef(0);
  const journeySavePending = useRef(false);
  const [journeySaving, setJourneySaving] = useState(false);
  const resetJourneyPending = useRef(false);
  const [resettingJourney, setResettingJourney] = useState(false);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const dryRunPending = useRef(null);
  const stopPendingFor = useRef(null);
  const [dryRunStopping, setDryRunStopping] = useState(false);
  const dryRunRevision = useRef(0);
  const [dryRunResults, setDryRunResults] = useState(null);
  const [journeyMessage, setJourneyMessage] = useState(null);
  const stepMetrics = runStatus?.step_metrics ?? [];

  // Stage 5: Test History & Reports State
  const [historySearch, setHistorySearch] = useState('');
  const [historyModeFilter, setHistoryModeFilter] = useState('ALL');
  const [historyStatusFilter, setHistoryStatusFilter] = useState('ALL');
  const [selectedForCompare, setSelectedForCompare] = useState([]);
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [singleRunReport, setSingleRunReport] = useState(null);
  const [compareBaseId, setCompareBaseId] = useState(null);
  const [compareCandidateId, setCompareCandidateId] = useState(null);
  const [compareData, setCompareData] = useState(null);
  const [reportMode, setReportMode] = useState('single');
  const [latestScorecard, setLatestScorecard] = useState(null);
  const [runHistory, setRunHistory] = useState([]);
  const [historyCursor, setHistoryCursor] = useState(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const historyRequest = useRef(null);

  // User Profile State (SQLite Persistent)
  const [userProfile, setUserProfile] = useState({
    full_name: 'Lead Test Architect',
    username: 'pusher_admin',
    email: 'dev@pusher.internal',
    role_title: 'Performance Engineer',
    organization: 'Pusher Ops',
    github_username: 'pusher-eng',
    avatar_url: '',
    bio_notes: 'Hardware load and knee-curve benchmarking lead.',
    default_ram_ceiling_mb: 500,
  });

  const handleSaveProfile = async (formData) => {
    const res = await operatorFetch(`/api/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    if (!res.ok) {
      throw new Error('Failed to update profile');
    }
    const updated = await res.json();
    setUserProfile(updated);
    if (updated.default_ram_ceiling_mb) {
      await updateTrafficConfig({ ram_limit_mb: updated.default_ram_ceiling_mb });
    }
    return updated;
  };

  const updateTrafficConfig = (overrides) => {
    setTrafficCloneNotice('');
    trafficProfile.current.edit(overrides);
    return trafficProfile.current.save();
  };

  const saveTrafficAndThen = async (next) => {
    if (trafficActionInProgress.current) return;
    trafficActionInProgress.current = true;
    setTrafficSaving(true);
    try {
      if (await trafficProfile.current.save()) await next();
    } finally {
      trafficActionInProgress.current = false;
      setTrafficSaving(false);
    }
  };

  // Parallel hydration from SQLite APIs on initial mount
  useEffect(() => {
    document.body.style.backgroundColor = '#ffffff';
    getDeviceId().then((id) => setDeviceId(id));

    operatorFetch('/api/traffic/config')
      .then(async (response) => {
        if (!response.ok) throw new Error('Traffic profile unavailable');
        trafficProfile.current.hydrate(await response.json());
      })
      .catch(() => setTrafficSaveError('Could not load the saved traffic profile. Saving will use the settings shown here.'))
      .finally(() => setTrafficLoading(false));

    operatorFetch('/api/journey')
      .then(async response => {
        if (!response.ok) throw new Error('Journey configuration unavailable');
        const data = await response.json();
        if (typeof data.use_journey !== 'boolean' || !Array.isArray(data.steps)) throw new Error('Invalid journey configuration');
        if (!journeyModeEdited.current) setUseJourney(data.use_journey);
        if (!journeyStepsEdited.current) setJourneySteps(data.steps);
        if (data.dry_run_results && !journeyStepsEdited.current && !dryRunPending.current) {
          setDryRunResults(previous => previous ?? data.dry_run_results);
        }
        setJourneySelectionStatus('ready');
      })
      .catch(() => setJourneySelectionStatus('unavailable'));

    const hydrateFromDatabase = async () => {
      try {
        const [limitsRes, profileRes] = await Promise.all([
          operatorFetch(`/api/system/limits`).catch(() => null),
          operatorFetch(`/api/profile`).catch(() => null),
        ]);

        if (limitsRes && limitsRes.ok) {
          const data = await limitsRes.json();
          setHardwareLimits(data);
        }

        if (profileRes && profileRes.ok) {
          const data = await profileRes.json();
          if (data && data.user_key) {
            setUserProfile(data);
          }
        }
      } catch (err) {
        console.error('Initial hydration error:', err);
      }
    };

    hydrateFromDatabase();
  }, []);

  // Fetch Target Status & Quota Telemetry on navigation
  const fetchTargetStatus = async () => {
    try {
      const res = await operatorFetch(`/api/target/status`);
      if (res.ok) {
        const data = await res.json();
        const sameGuard = Boolean(data.guard_id && targetGuardRef.current === data.guard_id);
        targetGuardRef.current = data.guard_id || null;
        setTargetUrl((draft) => restoreTargetQuery(data.target_url || '', draft, sameGuard));
        setConfirmedTarget(data.target_url || '');
        setConfirmedSandbox(Boolean(data.is_sandbox));
        setSandboxTargetUrl(data.sandbox_url || null);
        setRequiresTargetQuery(Boolean(data.requires_target_query));
        if (data.is_sandbox !== undefined) {
          setSandboxMode(Boolean(data.sandbox_url && data.is_sandbox));
        }
        setGuardToken(data.guard_id || null);
        setGuardChecksum(data.checksum_sha256 || null);
        if (data.needs_guard_replacement) setVerificationError('Revoke this old Guard and install a newly generated file.');
        setIsGuardVerified(Boolean(data.is_verified));
        setGuardTimerSeconds(data.remaining_seconds || 0);
        setLastBurnReason(data.last_burn_reason || null);
        setGuardQuota({
          used: data.daily_generations_used ?? 0,
          max: data.daily_generations_max ?? 3,
          remaining: data.daily_generations_remaining ?? 3,
          revokedCount: data.revoked_count ?? 0,
          lastRevokedId: data.last_revoked_guard_id ?? null,
        });
      }
    } catch {}
  };

  useEffect(() => {
    fetchTargetStatus();
  }, [activeNav]);

  const handleToggleSandbox = () => {
    if (!sandboxTargetUrl) return;
    if (sandboxMode) {
      setTargetUrl(liveTargetDraft.current ?? (confirmedSandbox ? '' : confirmedTarget));
    } else {
      liveTargetDraft.current = targetUrl;
      setTargetUrl(confirmedSandbox ? confirmedTarget : sandboxTargetUrl);
    }
    setSandboxMode(!sandboxMode);
    setVerificationError(null);
  };

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

  // Automatic Debounced Live URL Reachability, DNS & Typo Auto-Check (600ms)
  useEffect(() => {
    if (!targetUrl || !targetUrl.trim()) {
      setUrlValidation({
        checking: false,
        valid: false,
        ready: false,
        status: 'EMPTY',
        message: 'Enter target website or API endpoint (e.g., https://your-app.com)',
        suggestions: [],
      });
      return;
    }

    // Set immediate checking state
    setUrlValidation((prev) => ({
      ...prev,
      checking: true,
      status: 'CHECKING',
      message: 'CHECKING URL & DNS REACHABILITY...',
    }));

    const controller = new AbortController();
    const timeoutId = setTimeout(async () => {
      try {
        const res = await operatorFetch(`/api/target/validate-url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_url: targetUrl.trim(),
            is_sandbox: Boolean(sandboxMode),
          }),
          signal: controller.signal,
        });

        if (res.ok) {
          const data = await res.json();
          setUrlValidation({
            checking: false,
            valid: Boolean(data.valid),
            ready: Boolean(data.ready),
            status: data.status || (data.valid ? 'DNS_READY' : 'INVALID_URL'),
            message: data.message || '',
            suggestions: data.suggestions || [],
            resolved_ip: data.resolved_ip || null,
          });
        } else {
          const err = await res.json();
          const detail = err.detail || {};
          setUrlValidation({
            checking: false,
            valid: false,
            ready: false,
            status: detail.status || 'UNREACHABLE',
            message: detail.message || detail.detail || 'Validation failed.',
            suggestions: detail.suggestions || [],
          });
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setUrlValidation({
            checking: false,
            valid: false,
            ready: false,
            status: 'UNREACHABLE',
            message: 'Unable to reach backend validation service.',
            suggestions: [],
          });
        }
      }
    }, 600);

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [targetUrl, sandboxMode]);

  // 48-Hour Live Countdown Timer
  useEffect(() => {
    if (!isGuardVerified || guardTimerSeconds <= 0) return;
    const interval = setInterval(() => {
      setGuardTimerSeconds((prev) => {
        if (prev <= 1) {
          setIsGuardVerified(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isGuardVerified, guardTimerSeconds]);

  const formatTimer = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  // Restore the owner's run independently of WebSocket availability.
  useEffect(() => {
    setRunStatus(null);
    setStatusUnavailable(false);
    setStopError('');
    setStopping(false);

    const monitor = watchRun({
      fetch: operatorFetch,
      getToken: operatorToken,
      openSocket: () => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return new WebSocket(`${protocol}//${window.location.host}/api/load/ws`);
      },
      onStatus: (data, ended) => {
        setRunStatus(data);
        setStatusUnavailable(false);
        if (ended) setHistoryVersion((version) => version + 1);
      },
      onStatusError: () => setStatusUnavailable(true),
      onStopping: setStopping,
      onStopError: setStopError,
    });
    runMonitor.current = monitor;
    return () => {
      runMonitor.current = null;
      monitor.close();
    };
  }, [operator.user_id, guardToken, confirmedTarget]);


  // Actions: Download Guard with Rate Limiting (3/Day), Hardware Device Binding & Superseding Feedback
  const handleDownloadGuard = async () => {
    setVerificationError(null);
    setSupersededNotice(null);
    let guardData = null;

    try {
      const res = await operatorFetch(`/api/target/generate-guard`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Pusher-Device-ID': deviceId,
        },
        body: JSON.stringify({
          target_url: targetUrl,
          is_sandbox: Boolean(sandboxMode),
          device_id: deviceId,
        }),
      });

      if (res.status === 429) {
        const err = await res.json();
        setVerificationError(err.detail || 'Daily Guard generation limit reached (3 per 24 hours). Downloads are locked.');
        return;
      }

      if (res.status === 409) {
        const err = await res.json();
        setVerificationError(err.detail || 'An active Guard exists. Click KILL ID below before generating a new file.');
        return;
      }

      if (res.status === 422) {
        const err = await res.json();
        setVerificationError(err.detail || 'Check the target URL and DNS before generating a Guard.');
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
      targetGuardRef.current = guardData.guard_id;
      setRequiresTargetQuery(Boolean(guardData.requires_target_query));
      setGuardToken(guardData.guard_id);
      setGuardChecksum(guardData.checksum_sha256);
      setIsGuardVerified(false); // Newly generated guard requires re-verification
      setLastBurnReason(null);

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

    if (!guardData?.content) {
      setVerificationError('The server did not return a Guard file.');
      return;
    }
    const scriptContent = guardData.content;

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
    if (sandboxRequiresRevocation) {
      setVerificationError('Revoke the current live Guard before verifying the sandbox.');
      return;
    }
    if (!sandboxMode && (!urlValidation.valid || !urlValidation.ready)) {
      setVerificationError(urlValidation.message || 'Check the target URL and DNS before attempting ownership verification.');
      return;
    }
    if (!ssrfCheck.valid) {
      setVerificationError(ssrfCheck.message);
      return;
    }

    try {
      const res = await operatorFetch(`/api/target/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Pusher-Device-ID': deviceId,
        },
        body: JSON.stringify({
          target_url: targetUrl,
          guard_id: guardToken,
          is_sandbox: Boolean(sandboxMode),
          device_id: deviceId,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setIsGuardVerified(Boolean(data.is_verified));
        setGuardToken(data.guard_id || '');
        targetGuardRef.current = data.guard_id || null;
        setRequiresTargetQuery(Boolean(data.requires_target_query));
        const query = data.requires_target_query ? new URL(targetUrl.trim()).search : '';
        setTargetUrl((draft) => draft === targetUrl ? data.target_url + query : draft);
        setConfirmedTarget(data.target_url);
        setConfirmedSandbox(sandboxMode);
        setGuardTimerSeconds(data.remaining_seconds || 0);
        setLastBurnReason(null);
        return;
      } else {
        const err = await res.json();
        const msg = err.detail?.detail || err.detail || 'Verification challenge failed.';
        setVerificationError(msg);
        fetchTargetStatus();
        return;
      }
    } catch {
      setIsGuardVerified(false);
      setVerificationError('Unable to verify the target. Check your connection to Pusher.');
    }
  };

  const handleKillGuard = async () => {
    setVerificationError(null);
    try {
      const res = await operatorFetch(`/api/target/kill`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Pusher-Device-ID': deviceId,
        },
        body: JSON.stringify({ device_id: deviceId }),
      });
      const data = await res.json();
      if (!res.ok) {
        const message = data?.detail?.detail || data?.detail;
        setVerificationError(typeof message === 'string' ? message : 'Failed to revoke the Guard. Try again.');
      } else if (data?.is_verified === false && Object.hasOwn(data, 'revoked_guard_id')) {
        setIsGuardVerified(false);
        setGuardToken(null);
        setGuardTimerSeconds(0);
        setLastBurnReason(data.last_burn_reason || null);
        setSupersededNotice(
          data.revoked_guard_id ? `Guard ID ${data.revoked_guard_id} was revoked.` : null
        );
      } else {
        setVerificationError('Could not confirm revocation. Check your connection and try again.');
      }
    } catch {
      setVerificationError('Could not confirm revocation. Check your connection and try again.');
    } finally {
      await fetchTargetStatus();
    }
  };

  // Stage 4 Journey Handlers
  useEffect(() => {
    dryRunRevision.current += 1;
    setDryRunResults(previous => Array.isArray(previous) ? previous : null);
    setJourneyMessage(null);
  }, [targetUrl, guardToken, isVerified, sandboxMode, cacheBusting]);

  const changeJourneyMode = (enabled) => {
    journeyRevision.current += 1;
    journeyModeEdited.current = true;
    setUseJourney(enabled);
  };

  const editJourneySteps = (steps) => {
    dryRunRevision.current += 1;
    setDryRunResults(null);
    setJourneyMessage(null);
    journeyRevision.current += 1;
    journeyStepsEdited.current = true;
    setJourneySteps(steps);
  };

  const handleUpdateStep = (index, field, value) => {
    editJourneySteps((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleAddStep = () => {
    const stepId = `step-${crypto.getRandomValues(new Uint32Array(4)).join('-')}`;
    editJourneySteps((prev) => {
      if (prev.length >= maxJourneySteps) return prev;
      const nextIdx = prev.length + 1;
      return [...prev, {
        step_id: stepId,
        name: `Sequential Action ${nextIdx}`,
        method: 'GET',
        path: sandboxMode ? '/api/sandbox/items' : '/',
        headers: {},
        body: null,
        expected_status: 200,
        extract_json_key: null,
      }];
    });
  };

  const handleDeleteStep = (index) => {
    if (journeySteps.length <= 1) return;
    editJourneySteps((prev) => prev.filter((_, i) => i !== index));
  };

  const handleMoveStep = (index, delta) => {
    const targetIdx = index + delta;
    if (targetIdx < 0 || targetIdx >= journeySteps.length) return;
    editJourneySteps((prev) => {
      const copy = [...prev];
      const temp = copy[index];
      copy[index] = copy[targetIdx];
      copy[targetIdx] = temp;
      return copy;
    });
  };

  const handleResetJourneyDefaults = async () => {
    if (!sandboxTargetUrl || resetJourneyPending.current) return;
    if (journeySteps.length && !window.confirm('Replace the current journey with the sandbox preset? Unsaved steps will be replaced.')) return;
    resetJourneyPending.current = true;
    setResettingJourney(true);
    const revision = journeyRevision.current;
    try {
      const response = await operatorFetch('/api/journey/sandbox-defaults');
      if (!response.ok) throw new Error('Preset unavailable');
      const { steps } = await response.json();
      if (!Array.isArray(steps) || !steps.length) throw new Error('Invalid preset');
      if (revision !== journeyRevision.current) {
        setJourneyMessage('The journey changed while loading the preset. Your current steps are still in the editor.');
        return;
      }
      editJourneySteps(steps);
      setJourneyMessage('Reset journey steps to sandbox defaults.');
    } catch {
      setJourneyMessage('Could not load the sandbox preset. Your current steps are still in the editor.');
    } finally {
      resetJourneyPending.current = false;
      setResettingJourney(false);
    }
  };

  const handleExecuteDryRun = async () => {
    if (dryRunPending.current) return;
    if (!isVerified || !verifiedOrigin || !guardToken) {
      setJourneyMessage('Verify the target before running a journey.');
      return;
    }
    if (!journeySteps.length) {
      setJourneyMessage('Add at least one step before running a journey.');
      return;
    }
    const writes = journeySteps.some(step => !['GET', 'HEAD', 'OPTIONS'].includes((step.method || 'GET').toUpperCase()));
    if (writes && !window.confirm(`Run these steps once against ${verifiedOrigin}? They can change data on the target.`)) return;
    const id = crypto.getRandomValues(new Uint32Array(4)).join('-');
    dryRunPending.current = id;
    const revision = ++dryRunRevision.current;
    setIsDryRunning(true);
    setDryRunStopping(false);
    setDryRunResults(null);
    setJourneyMessage(null);
    try {
      const res = await operatorFetch(`/api/journey/dry-run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run_id: id, guard_id: guardToken, steps: journeySteps, cache_bust: cacheBusting }),
      });
      const data = await res.json();
      if (revision !== dryRunRevision.current) return;
      if (res.ok) {
        setDryRunResults(data);
        if (data.status === 'cancelled') {
          setJourneyMessage(data.message);
        } else if (data.all_passed) {
          setJourneyMessage(`1-VU Dry-Run PASSED (${data.total_steps}/${data.total_steps} steps).`);
        } else {
          setJourneyMessage(`1-VU Dry-Run FAILED: ${data.steps.filter((s) => !s.passed).length} step(s) failed.`);
        }
      } else {
        setJourneyMessage(journeyRequestError(data.detail, 'Dry-run execution failed.'));
      }
    } catch {
      if (revision === dryRunRevision.current) setJourneyMessage('Error contacting backend for dry-run.');
    } finally {
      dryRunPending.current = null;
      setIsDryRunning(false);
    }
  };

  const handleStopDryRun = async () => {
    const id = dryRunPending.current;
    if (!id || stopPendingFor.current === id) return;
    stopPendingFor.current = id;
    setDryRunStopping(true);
    try {
      const response = await operatorFetch('/api/journey/dry-run/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run_id: id }),
      });
      if (!response.ok && dryRunPending.current === id) {
        const data = await response.json();
        if (dryRunPending.current === id) setJourneyMessage(journeyRequestError(data.detail, 'Could not stop the dry run.'));
      }
    } catch {
      if (dryRunPending.current === id) setJourneyMessage('Could not confirm the dry run stopped. Try again.');
    } finally {
      if (stopPendingFor.current === id) {
        stopPendingFor.current = null;
        setDryRunStopping(false);
      }
    }
  };

  const handleSaveJourney = async (enable = null) => {
    if (journeySavePending.current) return null;
    if (!journeySteps.length) {
      setJourneyMessage('Add at least one step before saving.');
      return null;
    }
    journeySavePending.current = true;
    setJourneySaving(true);
    const revision = journeyRevision.current;
    const newUseJourney = enable !== null ? enable : useJourney;
    try {
      const res = await operatorFetch(`/api/journey/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          steps: journeySteps,
          use_journey: newUseJourney,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (revision !== journeyRevision.current) {
          setJourneyMessage('An earlier draft was saved. Your latest edits are still here. Save again to include them.');
          return null;
        }
        data.steps = restoreJourneyInputs(data.steps, journeySteps);
        journeyStepsEdited.current = true;
        setJourneySteps(data.steps);
        changeJourneyMode(data.use_journey);
        setJourneyMessage('Journey saved. Query strings, request bodies, and private header values stay in this tab.');
        return data;
      } else {
        const err = await res.json();
        setJourneyMessage(journeyRequestError(err.detail, 'Failed to save journey.'));
        return null;
      }
    } catch {
      setJourneyMessage('Error contacting backend to save journey.');
      return null;
    } finally {
      journeySavePending.current = false;
      setJourneySaving(false);
    }
  };

  const handleSaveAndLaunchJourney = () => {
    if (journeyLaunchBlocker || journeySavePending.current || launchInProgress.current) return;
    return saveAndLaunchJourney(handleSaveJourney, launchTest);
  };

  const journeySelectionKnown = journeyModeEdited.current || journeySelectionStatus === 'ready';
  const handleStartTest = () => launchTest({ use_journey: useJourney, steps: journeySteps, selectionKnown: journeySelectionKnown });

  const launchTest = async (journey) => {
    if (!canStart || launchInProgress.current) return;
    if (!isVerified) {
      setActiveNav('verify');
      setVerificationError('Target must be verified with active 48h guard before launching test.');
      return;
    }
    if (journey.selectionKnown === false) {
      setLaunchError('Open API Journey Builder to confirm what the test should run.');
      return;
    }
    setVerificationError(null);
    setLaunchError('');
    launchInProgress.current = true;
    setLaunching(true);
    const monitor = runMonitor.current;
    const showError = (message) => {
      if (activeNav === 'api') setJourneyMessage(message);
      else setLaunchError(message);
    };

    try {
      const isSandboxTarget = sandboxMode;
      const res = await operatorFetch(`/api/load/start`, {
        method: 'POST',
        signal: AbortSignal.timeout(10000),
        headers: {
          'Content-Type': 'application/json',
          'X-Pusher-Device-ID': deviceId,
        },
        body: JSON.stringify({
          target_url: targetUrl,
          traffic_mode: trafficMode,
          target_vus: vus,
          duration_sec: duration,
          cache_bust: cacheBusting,
          ram_limit_mb: ramLimitMb,
          max_error_pct: max5xxThreshold,
          p95_ceiling_ms: p95Ceiling,
          is_sandbox: isSandboxTarget,
          use_journey: journey.use_journey,
          journey_steps: journey.use_journey ? journey.steps : null,
          device_id: deviceId,
        }),
      });

      const data = await res.json().catch(() => null);
      if (res.ok && data?.snapshot) {
        monitor?.accept(data.snapshot);
        setActiveNav('dashboard');
      } else if (res.ok) {
        throw new Error('Start response did not include a run snapshot');
      } else {
        showError(typeof data?.detail === 'string' ? data.detail : 'Pusher could not start the load test. Review your settings and try again.');
        if (res.status === 409) void monitor?.refresh();
      }
    } catch {
      showError('Pusher could not confirm that the test started. Checking run status before you can retry.');
      setStatusUnavailable(true);
      void monitor?.refresh();
    } finally {
      launchInProgress.current = false;
      setLaunching(false);
    }
  };

  const handleStopTest = () => runMonitor.current?.stop(runStatus?.run_id);

  const handleSimulateSpike = async () => {
    setStopError('');
    const monitor = runMonitor.current;
    try {
      const response = await operatorFetch('/api/load/simulate-spike', { method: 'POST' });
      if (!response.ok) throw new Error('Pusher could not simulate the spike.');
      await monitor?.refresh();
    } catch (error) {
      setStopError(error.message);
    }
  };

  // Stage 5 History & Report Actions
  const fetchHistory = async (cursor = null) => {
    historyRequest.current?.abort();
    const controller = new AbortController();
    historyRequest.current = controller;
    setHistoryLoading(true);
    setHistoryError('');
    const params = new URLSearchParams();
    if (historyModeFilter !== 'ALL') params.set('mode', historyModeFilter);
    if (historyStatusFilter !== 'ALL') params.set('verdict', historyStatusFilter);
    if (historySearch.trim()) params.set('q', historySearch.trim());
    if (cursor) params.set('cursor', cursor);
    try {
      const res = await operatorFetch('/api/history?' + params.toString(), { signal: controller.signal });
      if (!res.ok) throw new Error('Could not load test history.');
      const { runs, scorecard, next_cursor } = await res.json();
      if (controller.signal.aborted) return;
      setRunHistory((previous) => cursor ? [...previous, ...runs] : runs);
      setLatestScorecard(scorecard);
      setHistoryCursor(next_cursor);
    } catch (error) {
      if (!controller.signal.aborted) setHistoryError(error.message);
    } finally {
      if (!controller.signal.aborted) setHistoryLoading(false);
    }
  };

  useEffect(() => {
    historyRequest.current?.abort();
    setHistoryCursor(null);
    const timer = setTimeout(() => fetchHistory(), 200);
    return () => {
      clearTimeout(timer);
      historyRequest.current?.abort();
    };
  }, [historyModeFilter, historyStatusFilter, historySearch, historyVersion]);

  const handleClearArchive = async () => {
    setHistoryError('');
    try {
      const response = await operatorFetch('/api/history', { method: 'DELETE' });
      if (!response.ok) throw new Error('Could not clear test history.');
      setSingleRunReport(null);
      setSelectedForCompare([]);
      setHistoryVersion((version) => version + 1);
    } catch (error) {
      setHistoryError(error.message);
    }
  };

  const handleViewSingleReport = async (runId) => {
    const idToFetch = runId || selectedReportId;
    if (!idToFetch) return;
    try {
      const res = await operatorFetch(`/api/reports/${idToFetch}`);
      if (res.ok) {
        const data = await res.json();
        setSingleRunReport(data);
        setSelectedReportId(idToFetch);
        setReportMode('single');
        setActiveNav('reports');
        return;
      }
    } catch { }
    setSingleRunReport(null);
    setSelectedReportId(idToFetch);
    setReportMode('single');
    setActiveNav('reports');
  };

  useEffect(() => {
    if (activeNav === 'reports' && reportMode === 'single' && !selectedReportId && runHistory.length > 0) {
      handleViewSingleReport(runHistory[0].run_id);
    }
  }, [activeNav, reportMode, selectedReportId, runHistory]);

  const handleCompareRuns = async (baseId, candId) => {
    const base = baseId || compareBaseId || (selectedForCompare.length >= 2 ? selectedForCompare[1] : null);
    const cand = candId || compareCandidateId || (selectedForCompare.length >= 1 ? selectedForCompare[0] : null);
    if (!base || !cand) {
      setActiveNav('history');
      return;
    }
    setCompareData(null);
    try {
      const res = await operatorFetch(`/api/reports/compare`, {
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

  const handleExportReport = async (runId) => {
    const id = runId || selectedReportId;
    if (id) {
      const response = await operatorFetch(`/api/reports/${encodeURIComponent(id)}/export`);
      if (!response.ok) throw new Error('Export unavailable');
      const url = URL.createObjectURL(await response.blob());
      const download = document.createElement('a');
      download.href = url;
      download.download = `report_${id}.json`;
      download.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    }
  };

  const handleCloneRun = (run) => {
    const plannedMode = run.mode?.toLowerCase().replace(/[- ]/g, '_');
    const plannedDuration = run.duration_sec ?? run.duration;
    const overrides = {};
    const notes = [];
    if (['step_ramp', 'sudden_rush', 'steady_crowd'].includes(plannedMode)) {
      overrides.mode = plannedMode;
    } else {
      notes.push('The report has no recognized traffic mode. Kept the current mode.');
    }
    if (Number.isInteger(plannedDuration) && plannedDuration > 0 && plannedDuration <= 86400) {
      overrides.duration_sec = plannedDuration;
    } else {
      notes.push('The report has no valid planned duration. Kept the current duration.');
    }
    if (Number.isInteger(run.target_vus) && run.target_vus > 0) {
      overrides.virtual_users = maxAllowedVus > 0 ? Math.min(run.target_vus, maxAllowedVus) : run.target_vus;
      if (overrides.virtual_users < run.target_vus) {
        notes.push(`Reduced the cloned user count from ${run.target_vus.toLocaleString()} to ${overrides.virtual_users.toLocaleString()} to fit the current limit.`);
      }
    } else {
      notes.push('The report has no planned user count. Kept the current user count.');
    }
    trafficProfile.current.edit(overrides);
    setTrafficCloneNotice(notes.join(' ') || 'Copied the planned traffic settings. Review and save them below.');
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



  // RAM & Concurrency Scaling Model
  const {
    max_safe_ram_mb: maxHardwareSafeRamMb, base_engine_ram_mb: baseEngineRamMb,
    ram_per_vu_mb: ramPerVuMb, max_worker_vus: maxWorkerVus,
  } = hardwareLimits ?? {};
  const capacityKnown = Number.isInteger(maxHardwareSafeRamMb) && Number.isInteger(maxWorkerVus)
    && Number.isFinite(baseEngineRamMb) && ramPerVuMb > 0;
  const trafficVuLimit = (budget) => capacityKnown
    ? Math.max(0, Math.min(maxWorkerVus, Math.floor((Math.min(budget, maxHardwareSafeRamMb) - baseEngineRamMb) / ramPerVuMb)))
    : null;
  const maxAllowedVus = trafficVuLimit(ramLimitMb);
  const estimatedRam = capacityKnown ? Math.round(baseEngineRamMb + vus * ramPerVuMb) : null;
  const trafficCapacityError = !capacityKnown ? 'Hardware limits are unavailable.'
    : ramLimitMb > maxHardwareSafeRamMb ? 'Reduce the RAM budget to the host limit.'
    : vus > maxAllowedVus ? `Reduce virtual users to ${maxAllowedVus.toLocaleString()} or fewer.`
    : '';
  let launchBlocker = '';
  if (launching) launchBlocker = 'Starting load test…';
  else if (testRunning) launchBlocker = 'A load test is already running.';
  else if (statusUnavailable) launchBlocker = 'Run status unavailable. Retrying…';
  else if (!runStatus) launchBlocker = 'Checking run status…';
  else if (!isVerified) launchBlocker = 'Verify the target before launching.';
  else if (trafficLoading) launchBlocker = 'Loading traffic profile…';
  else if (trafficSaving) launchBlocker = 'Saving traffic profile…';

  const missingJourneySteps = 'Add journey steps in API Journey Builder.';
  const journeyLaunchBlocker = launchBlocker || (!journeySteps.length ? missingJourneySteps : trafficCapacityError);
  let trafficLaunchBlocker = launchBlocker;
  if (!trafficLaunchBlocker && !journeySelectionKnown) trafficLaunchBlocker = journeySelectionStatus === 'loading'
    ? 'Loading saved run type…' : 'Run type unavailable. Choose one in API Journey Builder.';
  if (!trafficLaunchBlocker) trafficLaunchBlocker = useJourney && !journeySteps.length ? missingJourneySteps : trafficCapacityError;
  const trafficRunType = !journeySelectionKnown ? 'Waiting for run selection'
    : useJourney ? `API journey · ${journeySteps.length} ${journeySteps.length === 1 ? 'step' : 'steps'}`
    : 'Single URL';
  const modeLabel = trafficMode === 'step_ramp' ? 'STEP-RAMP' : trafficMode === 'sudden_rush' ? 'SUDDEN RUSH' : 'STEADY CROWD';

  const handleSetRamLimit = (newLimit) => {
    if (!capacityKnown || maxHardwareSafeRamMb < 51) return;
    const parsed = Math.max(51, Math.min(maxHardwareSafeRamMb, Math.floor(newLimit) || 500));
    const newMaxVus = trafficVuLimit(parsed);
    updateTrafficConfig({ ram_limit_mb: parsed, virtual_users: Math.min(vus, newMaxVus) });
  };

  const handleUpdateTrafficMode = (mode) => {
    updateTrafficConfig({ mode });
  };

  const handleUpdateVus = (newVus) => {
    updateTrafficConfig({ virtual_users: newVus });
  };

  const handleUpdateDuration = (newDur) => {
    updateTrafficConfig({ duration_sec: newDur });
  };

  const handleUpdateMax5xx = (val) => {
    updateTrafficConfig({ max_error_pct: val });
  };

  const handleUpdateP95Ceiling = (val) => {
    updateTrafficConfig({ p95_ceiling_ms: val });
  };

  const handleUpdateCacheBusting = (val) => {
    updateTrafficConfig({ cache_bust: val });
  };

  return (
    <div data-appearance={appearance} className="pusher-workspace min-h-screen w-full bg-white text-black font-mono selection:bg-black selection:text-white flex flex-col antialiased">
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

        {/* Right Action Area: User Profile Pill + Options Menu */}
        <div className="flex items-center gap-2.5">
          {/* User Profile Pill / Button */}
          <button
            type="button"
            onClick={() => setActiveNav('profile')}
            className={`border-2 border-black px-2.5 py-1 text-xs font-bold uppercase transition-colors cursor-pointer flex items-center gap-2 ${activeNav === 'profile'
              ? (themeMode === 'production' ? 'bg-teal-700 text-white' : 'bg-black text-white')
              : 'bg-white text-black hover:bg-black hover:text-white'
              }`}
            title="View & Edit User Profile & Session"
          >
            <div className="w-5 h-5 border border-black bg-slate-900 text-white flex items-center justify-center text-[10px] font-black overflow-hidden shrink-0 select-none">
              {userProfile.avatar_url ? (
                <img src={userProfile.avatar_url} alt="" className="w-full h-full object-cover" />
              ) : (
                <span>{(userProfile.full_name || userProfile.username || 'PU').slice(0, 2).toUpperCase()}</span>
              )}
            </div>
            <span className="font-mono truncate max-w-[220px]">
              [ PROFILE: {userProfile.full_name || userProfile.username || userProfile.email || 'OPERATOR'} ]
            </span>
          </button>

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
                      setActiveNav('profile');
                    }}
                    className="w-full text-left px-3 py-2 font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-between cursor-pointer"
                  >
                    <span>User Profile</span>
                    <User className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      if (onNavigate) {
                        onNavigate('waf-setup');
                      } else {
                        window.location.hash = '#/waf-setup';
                      }
                    }}
                    className="w-full text-left px-3 py-2 font-bold uppercase hover:bg-black hover:text-white transition-colors flex items-center justify-between cursor-pointer"
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
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* 2-COLUMN MAIN LAYOUT: LEFT SIDEBAR + MAIN CONTENT AREA                   */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col md:flex-row bg-white">

        {/* LEFT SIDEBAR: 6 DISTINCT VIEWS */}
        <aside className="w-full md:w-64 border-b-2 md:border-b-0 md:border-r-2 border-black p-4 bg-white flex flex-col justify-between shrink-0 lg:sticky lg:top-4 self-start">
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
                { id: 'profile', label: '7. User Profile', desc: 'SQLite Profile & Defaults' },
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
              {targetTemplate(targetUrl)}
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
              targetUrl={targetTemplate(targetUrl)}
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
              canStart={canStart}
              statusUnavailable={statusUnavailable}
              stopping={stopping}
              elapsed={elapsed}
              telemetry={telemetry}
              stepMetrics={stepMetrics}
              useJourney={testRunning ? Boolean(runStatus.use_journey) : useJourney}
              handleStartTest={handleStartTest}
              handleStopTest={handleStopTest}
              stopError={stopError}
              launchError={launchError}
              launching={launching}
              handleSimulateSpike={handleSimulateSpike}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 2: `2. Verify Target` */}
          {activeNav === 'verify' && (
            <VerifyTargetView
              targetUrl={targetUrl}
              requiresTargetQuery={requiresTargetQuery}
              setTargetUrl={setTargetUrl}
              sandboxMode={sandboxMode}
              sandboxTargetUrl={sandboxTargetUrl}
              sandboxRequiresRevocation={sandboxRequiresRevocation}
              handleToggleSandbox={handleToggleSandbox}
              ssrfCheck={ssrfCheck}
              urlValidation={urlValidation}
              guardToken={guardToken}
              isVerified={isVerified}
              verifiedOrigin={verifiedOrigin}
              isGuardVerified={isGuardVerified}
              guardTimerSeconds={guardTimerSeconds}
              formatTimer={formatTimer}
              verificationError={verificationError}
              setVerificationError={setVerificationError}
              guardQuota={guardQuota}
              supersededNotice={supersededNotice}
              deviceId={deviceId}
              lastBurnReason={lastBurnReason}
              handleDownloadGuard={handleDownloadGuard}
              guardChecksum={guardChecksum}
              handleVerifyTarget={handleVerifyTarget}
              handleKillGuard={handleKillGuard}
              setWafModalOpen={setWafModalOpen}
              onNavigate={onNavigate}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 3: `3. Traffic Setup` */}
          {activeNav === 'traffic' && (
            <TrafficSetupView
              trafficMode={trafficMode}
              setTrafficMode={handleUpdateTrafficMode}
              ramLimitMb={ramLimitMb}
              handleSetRamLimit={handleSetRamLimit}
              maxHardwareSafeRamMb={maxHardwareSafeRamMb}
              vus={vus}
              setVus={handleUpdateVus}
              maxAllowedVus={maxAllowedVus}
              trafficVuLimit={trafficVuLimit}
              maxWorkerVus={maxWorkerVus}
              phases={trafficPhases(trafficMode, vus, duration, hardwareLimits?.traffic_schedule)}
              duration={duration}
              setDuration={handleUpdateDuration}
              max5xxThreshold={max5xxThreshold}
              setMax5xxThreshold={handleUpdateMax5xx}
              p95Ceiling={p95Ceiling}
              maxP95Ceiling={hardwareLimits?.max_p95_ceiling_ms}
              setP95Ceiling={handleUpdateP95Ceiling}
              cacheBusting={cacheBusting}
              setCacheBusting={handleUpdateCacheBusting}
              estimatedRam={estimatedRam}
              trafficLaunchBlocker={trafficLaunchBlocker}
              launchError={launchError}
              runType={trafficRunType}
              handleStartTest={() => {
                if (!trafficLaunchBlocker) return saveTrafficAndThen(handleStartTest);
              }}
              handleSaveTraffic={() => saveTrafficAndThen(() => setActiveNav('dashboard'))}
              trafficSaving={trafficSaving}
              trafficLoading={trafficLoading}
              trafficSaveError={trafficSaveError}
              trafficCloneNotice={trafficCloneNotice}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 4: `4. API Builder` */}
          {activeNav === 'api' && (
            <ApiBuilderView
              journeySteps={journeySteps}
              maxJourneySteps={maxJourneySteps}
              setJourneySteps={setJourneySteps}
              useJourney={useJourney}
              setUseJourney={changeJourneyMode}
              journeyMessage={journeyMessage}
              setJourneyMessage={setJourneyMessage}
              isDryRunning={isDryRunning}
              dryRunResults={dryRunResults}
              handleUpdateStep={handleUpdateStep}
              handleAddStep={handleAddStep}
              handleDeleteStep={handleDeleteStep}
              handleMoveStep={handleMoveStep}
              handleResetJourneyDefaults={handleResetJourneyDefaults}
              sandboxPresetAvailable={Boolean(sandboxTargetUrl)}
              resettingJourney={resettingJourney}
              handleExecuteDryRun={handleExecuteDryRun}
              dryRunTarget={isVerified ? verifiedOrigin : null}
              handleStopDryRun={handleStopDryRun}
              dryRunStopping={dryRunStopping}
              handleSaveJourney={handleSaveJourney}
              journeySaving={journeySaving}
              handleSaveAndLaunchJourney={handleSaveAndLaunchJourney}
              journeyLaunchBlocker={journeyLaunchBlocker}
              setActiveNav={setActiveNav}
              themeMode={themeMode}
            />
          )}

          {/* VIEW 5: `5. Test History` */}
          {activeNav === 'history' && (
            <TestHistoryView
              runHistory={runHistory}
              filteredRuns={runHistory}
              historyLoading={historyLoading}
              historyError={historyError}
              hasMoreHistory={Boolean(historyCursor)}
              onLoadMore={() => fetchHistory(historyCursor)}
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

          {/* VIEW 7: `7. User Profile` */}
          {activeNav === 'profile' && (
            <ProfileView
              profile={userProfile}
              onSaveProfile={handleSaveProfile}
              appearance={appearance}
              onAppearanceChange={onAppearanceChange}
              deviceId={deviceId}
              themeMode={themeMode}
              setActiveNav={setActiveNav}
              operator={operator}
              onLogout={onLogout}
              onNavigate={onNavigate}
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
                GUARD &amp; EDGE DIAGNOSTICS
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
                  Pusher Guard serves an ownership challenge. Test requests use the target app’s normal authentication and traffic controls.
                </p>
              </div>

              <div className="border border-black p-3">
                <span className="font-bold block uppercase mb-1">2. Investigate Blocks</span>
                <p>Check the app and edge provider’s event logs for 403 and 429 responses.</p>
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

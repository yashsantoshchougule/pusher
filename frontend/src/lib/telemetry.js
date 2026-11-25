export function mapTelemetry(status = {}) {
  return {
    currentVus: status?.active_vus ?? 0,
    liveRps: status?.live_rps ?? 0,
    p95Latency: status?.p95_ms ?? 0,
    errorRate: status?.error_pct ?? 0,
    circuitBreaker: status?.is_running === false ? 'ARMED' : (status?.circuit_status ?? 'ARMED'),
    bytesDiscardedMb: status?.bytes_discarded_mb ?? 0,
  };
}

export function mapRunMeta(status = {}) {
  const totalRequests = status?.total_requests ?? 0;
  const status2xx = status?.status_2xx ?? 0;
  const status3xx = status?.status_3xx ?? 0;
  const status4xx = status?.status_4xx ?? 0;
  const status429 = status?.status_429 ?? 0;
  const status5xx = status?.status_5xx ?? 0;
  const timeoutCount = status?.timeout_count ?? status?.timeouts ?? 0;
  const networkErrorCount = status?.network_error_count ?? status?.network_errors ?? 0;
  const statusOther = Number.isFinite(status?.status_other)
    ? status.status_other
    : Math.max(0, totalRequests - status2xx - status3xx - status4xx - status429 - status5xx - timeoutCount - networkErrorCount);

  return {
    isRunning: Boolean(status?.is_running),
    runId: status?.run_id ?? null,
    totalRequests,
    status2xx,
    status3xx,
    status4xx,
    status429,
    status5xx,
    statusOther,
    timeoutCount,
    networkErrorCount,
    ramMb: status?.ram_mb ?? null,
    ramLimitMb: status?.ram_limit_mb ?? null,
    p95CeilingMs: status?.p95_ceiling_ms ?? null,
    maxErrorPct: status?.max_error_pct ?? null,
    effectiveP95CeilingMs: status?.effective_p95_ceiling_ms ?? null,
    effectiveMaxErrorPct: status?.effective_max_error_pct ?? null,
    requestTimeoutSec: status?.request_timeout_sec ?? null,
    loopLagMs: status?.loop_lag_ms ?? null,
    lastCircuitStatus: status?.is_running === false ? (status?.circuit_status ?? null) : null,
  };
}

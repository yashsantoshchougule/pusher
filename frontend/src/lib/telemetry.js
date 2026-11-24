export function mapTelemetry(status = {}) {
  return {
    currentVus: status.active_vus ?? 0,
    liveRps: status.live_rps ?? 0,
    p95Latency: status.p95_ms ?? 0,
    errorRate: status.error_pct ?? 0,
    circuitBreaker: status.circuit_status ?? 'ARMED',
    bytesDiscardedMb: status.bytes_discarded_mb ?? 0,
  };
}

import test from 'node:test';
import assert from 'node:assert/strict';
import { mapRunMeta, mapTelemetry } from '../../../frontend/src/lib/telemetry.js';

test('live status and WebSocket frames use the same backend fields', () => {
  const status = {
    active_vus: 23, live_rps: 81, p95_ms: 41.5, error_pct: 3.2,
    circuit_status: 'ARMED (Normal)', bytes_discarded_mb: 7.5,
  };
  const expected = {
    currentVus: 23, liveRps: 81, p95Latency: 41.5, errorRate: 3.2,
    circuitBreaker: 'ARMED (Normal)', bytesDiscardedMb: 7.5,
  };
  assert.deepEqual(mapTelemetry(status), expected);
  assert.deepEqual(mapTelemetry({ ...status, event: 'TICK' }), expected);
});

test('zero metrics and idle defaults stay zero', () => {
  assert.deepEqual(mapTelemetry({ active_vus: 0, p95_ms: 0, error_pct: 0 }), mapTelemetry());
  assert.equal(mapTelemetry().currentVus, 0);
});

test('idle status resets live circuitBreaker to ARMED and exposes full runMeta', () => {
  const idle = {
    is_running: false,
    run_id: 'RUN-123',
    active_vus: 0,
    live_rps: 0,
    p95_ms: 0,
    error_pct: 0,
    circuit_status: 'TRIPPED (rolling p95 latency threshold)',
    bytes_discarded_mb: 1.79,
    total_requests: 255,
    status_2xx: 226,
    status_429: 0,
    status_5xx: 0,
    ram_mb: 124.3,
    ram_limit_mb: 500,
    p95_ceiling_ms: 5000,
    max_error_pct: 5,
    effective_p95_ceiling_ms: 5000,
    effective_max_error_pct: 5,
    request_timeout_sec: 5,
    loop_lag_ms: 1.2,
  };
  const telemetry = mapTelemetry(idle);
  assert.equal(telemetry.circuitBreaker, 'ARMED');
  assert.deepEqual(Object.keys(telemetry), [
    'currentVus', 'liveRps', 'p95Latency', 'errorRate', 'circuitBreaker', 'bytesDiscardedMb',
  ]);

  const meta = mapRunMeta(idle);
  assert.equal(meta.isRunning, false);
  assert.equal(meta.runId, 'RUN-123');
  assert.equal(meta.totalRequests, 255);
  assert.equal(meta.status2xx, 226);
  assert.equal(meta.statusOther, 29);
  assert.equal(meta.lastCircuitStatus, 'TRIPPED (rolling p95 latency threshold)');
  assert.equal(meta.effectiveP95CeilingMs, 5000);
  assert.equal(meta.requestTimeoutSec, 5);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { mapTelemetry } from '../../../frontend/src/lib/telemetry.js';

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

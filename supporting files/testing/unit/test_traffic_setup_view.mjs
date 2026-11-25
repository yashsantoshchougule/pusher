import assert from 'node:assert/strict';
import test from 'node:test';
import { renderView } from './react_view_fixture.mjs';
import { trafficPhases } from '../../../frontend/src/lib/trafficProfile.js';

const schedule = {
  step_ratios: [0.2, 0.4, 0.6, 0.8, 1], step_min_seconds: 1,
  rush_warmup_seconds: 3, rush_warmup_ratio: 0.1, rush_warmup_min_vus: 10,
};

function renderTraffic(overrides = {}) {
  return renderView('TrafficSetupView', {
    trafficMode: 'step_ramp',
    ramLimitMb: 500,
    maxHardwareSafeRamMb: 12000,
    vus: 100,
    maxAllowedVus: 2250,
    maxWorkerVus: 3000,
    trafficVuLimit: budget => Math.min(3000, (budget - 50) * 5),
    duration: 30,
    max5xxThreshold: 5,
    p95Ceiling: 1500,
    isVerified: true,
    canStart: true,
    ...overrides,
  });
}

test('traffic setup separates the rolling server error setting from always-on stops', () => {
  const markup = renderTraffic();
  assert.ok(markup.includes('Rolling server-error threshold'));
  assert.ok(markup.includes('at least 20 responses'));
  assert.ok(markup.includes('Automatic stops are always on'));
  assert.ok(markup.includes('3 rate-limit responses in 3 seconds'));
  assert.ok(!markup.includes('WAF Auto-Abort'));
});

test('RAM presets and the resource display use the engine limit', () => {
  const markup = renderTraffic({ maxWorkerVus: 1200, trafficVuLimit: () => 1200, maxAllowedVus: 1200 });
  assert.ok(markup.includes('1,200 max VUs'));
  assert.ok(markup.includes('Engine worker limit'));
  assert.ok(!markup.includes('9,990 VUs'));
  assert.ok(!markup.includes('Est. OS File Descriptors'));
});

test('hardware estimates remain unknown when the limits are unavailable', () => {
  const markup = renderTraffic({
    maxAllowedVus: null, maxHardwareSafeRamMb: undefined, maxWorkerVus: undefined,
    trafficVuLimit: () => null, trafficLaunchBlocker: 'Hardware limits are unavailable.',
  });
  assert.ok(markup.includes('Hardware limits are unavailable.'));
  assert.ok(markup.includes('Host cap unavailable'));
  assert.ok(!markup.includes('2,250 VUs'));
});

test('disabled launch has disabled styling and explains why', () => {
  const markup = renderTraffic({ trafficLaunchBlocker: 'A load test is already running.' });
  assert.match(markup, /role="status"[^>]*>A load test is already running/);
  assert.match(markup, /<button[^>]*disabled=""[^>]*cursor-not-allowed[^>]*>SAVE &amp; LAUNCH LOAD TEST/);
});

test('current duration and latency are visible, with the real defaults selected', () => {
  const defaults = renderTraffic();
  assert.match(defaults, /aria-pressed="true"[^>]*>30 s \(Default\)/);
  assert.match(defaults, /aria-pressed="true"[^>]*>1,500 ms \(Default\)/);
  const custom = renderTraffic({ duration: 45, p95Ceiling: 9000, maxP95Ceiling: 8000 });
  assert.ok(custom.includes('45 s'));
  assert.ok(custom.includes('8,000 ms'));
  assert.ok(!custom.includes('9,000 ms'));
});

test('the schedule shows the rush warm-up, skips unreachable phases, and renders the actual ramp', () => {
  const rush = trafficPhases('sudden_rush', 105, 30, schedule);
  assert.deepEqual(rush, [{ start: 0, end: 3, vus: 10 }, { start: 3, end: 30, vus: 105 }]);
  assert.deepEqual(trafficPhases('sudden_rush', 6, 2, schedule), [{ start: 0, end: 2, vus: 6 }]);
  const ramp = trafficPhases('step_ramp', 100, 3, schedule);
  assert.deepEqual(ramp.map(phase => phase.vus), [20, 40, 60]);
  assert.deepEqual(trafficPhases('step_ramp', 100, 30, schedule).map(phase => phase.vus), [20, 40, 60, 80, 100]);
  assert.deepEqual(trafficPhases('steady_crowd', 85, 30), [{ start: 0, end: 30, vus: 85 }]);
  const markup = renderTraffic({ trafficMode: 'sudden_rush', phases: rush });
  assert.ok(markup.includes('0–3 s'));
  assert.ok(markup.includes('3–30 s'));
  assert.ok(markup.includes('105 VUs'));
});

test('step-ramp warnings, loopback high-VU advisory, and null host RAM guard render cleanly', () => {
  const markup = renderTraffic({
    trafficMode: 'step_ramp',
    vus: 175,
    duration: 30,
    sandboxMode: true,
    maxHardwareSafeRamMb: null,
  });
  assert.ok(markup.includes('5 steps · 6s/step · starts at Step 1 35 VUs'));
  assert.ok(markup.includes('Short step window'));
  assert.ok(markup.includes('Loopback / single-host saturation warning'));
  assert.ok(markup.includes('max 25%'));
  assert.ok(!markup.includes('Above host limit'));
});

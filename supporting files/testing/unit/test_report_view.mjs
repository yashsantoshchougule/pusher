import assert from 'node:assert/strict';
import test from 'node:test';
import { renderView } from './react_view_fixture.mjs';

test('scorecard renders zero and absent latency without example numbers', () => {
  const markup = renderView('ReportsView', {
    reportMode: 'single',
    singleRunReport: { p95_ms: 0, error_pct: 0, metrics_scope: 'whole_run' },
  });
  assert.match(markup, /P95:<\/td><td[^>]+>0 ms/);
  assert.match(markup, /P50 \(Median\):<\/td><td[^>]+>Unavailable/);
  assert.doesNotMatch(markup, /164 ms|2,000 ms/);

  const legacy = renderView('ReportsView', {
    reportMode: 'single', singleRunReport: { p95_ms: 27.3, metrics_scope: 'legacy_window' },
  });
  assert.match(legacy, /27\.3 ms/);
  assert.match(legacy, /final telemetry window/);
  assert.match(legacy, /Capacity unavailable/);

  const empty = renderView('ReportsView', {
    reportMode: 'single', singleRunReport: { p95_ms: null, metrics_scope: 'whole_run' },
  });
  assert.match(empty, /P95:<\/td><td[^>]+>Unavailable/);
});

test('comparison shows API values and an honest empty state', () => {
  const base = { run_id: 'observed-base', p95_ms: 41, knee_vus: 0, peak_rps: 50 };
  const props = { reportMode: 'compare', runHistory: [base] };
  const markup = renderView('ReportsView', {
    ...props,
    compareData: {
      base_run: base,
      candidate_run: { ...base, run_id: 'observed-candidate', p95_ms: 0 },
      deltas: { knee_vus_delta: 0, peak_rps_delta: 0, p95_ms_delta: -41 },
      overall_verdict: 'IMPROVED', summary: 'Measured comparison',
    },
  });
  assert.match(markup, /Measured comparison/);
  assert.match(markup, /Capacity unavailable/);
  assert.match(markup, /P95 Latency<\/th><td[^>]+>41 ms<\/td><td[^>]+>0 ms<\/td><td[^>]+>-41 ms/);
  assert.doesNotMatch(markup, /164 ms|CAPACITY IMPROVED/);
  assert.match(renderView('ReportsView', props), /Select two reports/);
});

test('dashboard scorecard displays unavailable capacity instead of zero VUs', () => {
  const render = (knee_vus) => renderView('OverviewBoxes', {
    telemetry: {}, latestScorecard: { knee_vus, p95_ms: 12, peak_rps: 100 },
  });
  assert.match(render(0), /Capacity unavailable/);
  assert.match(render(20), /20 VUs/);
});

test('live journey metrics display measured counts and average latency', () => {
  const markup = renderView('OverviewBoxes', {
    telemetry: {},
    useJourney: true,
    stepMetrics: [
      { name: 'Measured', path: '/measured', requests: 7, passed: 5, failed: 2, avg_latency_ms: 14, last_status: 200 },
      { name: 'Pending', path: '/pending', requests: 0, passed: 0, failed: 0, avg_latency_ms: 0 },
      { name: 'Fast', path: '/fast', requests: 1, passed: 1, failed: 0, avg_latency_ms: 0, last_status: 200 },
    ],
  });
  const cells = path => markup.match(new RegExp(`>${path}</td>(.*?)</tr>`))[1]
    .matchAll(/<td[^>]*>([^<]*)<\/td>/g);
  const measurements = path => Array.from(cells(path), cell => cell[1]);
  assert.deepEqual(measurements('/measured'), ['7', '5', '2', '14']);
  assert.deepEqual(measurements('/pending'), ['0', '0', '0', 'Unavailable']);
  assert.deepEqual(measurements('/fast'), ['1', '1', '0', '0']);
  assert.match(markup, /AVG \(MS\)/);
});

test('a report shows recorded progression in time order with honest missing values', () => {
  const markup = renderView('ReportsView', {
    reportMode: 'single',
    singleRunReport: { run_id: 'sample-run', timeseries: [
      { elapsed_sec: 9, vus: 27, rps: 818, p95_ms: 731, error_pct: 2 },
      null,
      { elapsed_sec: 0, vus: 0, rps: 0, p95_ms: null, error_pct: 0 },
    ] },
  });
  assert.match(markup, /Run timeline/);
  assert.match(markup, />0 s<.*>0 VUs<.*>0 RPS<.*>Unavailable<.*>0%<.*>9 s<.*>818 RPS<.*>731 ms</);
  assert.match(renderView('ReportsView', {
    reportMode: 'single', singleRunReport: { run_id: 'legacy-run' },
  }), /No timeline was recorded for this run/);
});

test('long report timelines render a bounded page and offer the remaining samples', () => {
  const markup = renderView('ReportsView', {
    reportMode: 'single',
    singleRunReport: {
      run_id: 'long-run',
      timeseries: Array.from({ length: 70 }, (_, elapsed_sec) => ({ elapsed_sec })),
    },
  });
  assert.match(markup, /Page 1 of 2/);
  assert.match(markup, />49 s</);
  assert.doesNotMatch(markup, />50 s</);
  assert.match(markup, />Next samples</);
});

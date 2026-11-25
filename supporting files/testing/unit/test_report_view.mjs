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

test('OverviewBoxes renders tripped scorecard honestly and resets Box 3 breaker when idle', () => {
  const markup = renderView('OverviewBoxes', {
    isVerified: true,
    testRunning: false,
    effectiveP95Ceiling: 5000,
    max5xxThreshold: 5,
    telemetry: {
      p95Latency: 0,
      errorRate: 0,
      circuitBreaker: 'ARMED',
    },
    runMeta: {
      isRunning: false,
      runId: 'RUN-61a9',
      totalRequests: 255,
      status2xx: 226,
      status429: 0,
      status5xx: 0,
      timeoutCount: 29,
      networkErrorCount: 0,
      statusOther: 0,
      lastCircuitStatus: 'TRIPPED (rolling p95 latency threshold)',
    },
    latestScorecard: {
      run_id: 'RUN-61a9',
      verdict: 'CIRCUIT_BREAKER',
      knee_vus: 0,
      peak_rps: 61,
      p95_ms: 5344,
      error_pct: 11.4,
      elapsed_sec: 6,
      capacity_reason: 'First step at 175 VUs saturated.',
    },
  });
  assert.match(markup, /Ceiling Breached/);
  assert.doesNotMatch(markup, /Optimal Health/);
  assert.match(markup, /11\.4%/);
  assert.match(markup, /First step at 175 VUs saturated/);
  assert.match(markup, /Ceiling: 5,000 ms/);
  assert.match(markup, /5xx Limit: 5%/);
  assert.match(markup, /Timeouts: <strong>29<\/strong>/);
  assert.match(markup, /Previous run ended:<\/strong> TRIPPED/);
});

test('ReportsView renders breakdown, thresholds, timeseries-aggregated steps, and compare warnings', () => {
  const markup = renderView('ReportsView', {
    reportMode: 'single',
    selectedReportId: 'RUN-61a9',
    singleRunReport: {
      run_id: 'RUN-61a9',
      target_url: 'http://127.0.0.1:8000/api/sandbox/target',
      mode: 'Step Ramp',
      target_vus: 873,
      peak_vus: 175,
      duration_sec: 30,
      elapsed_sec: 6,
      avg_rps: 42,
      peak_rps: 61,
      ram_mb: 124.3,
      bytes_discarded_mb: 1.79,
      p95_ms: 5344,
      error_pct: 11.4,
      total_requests: 255,
      status_2xx: 226,
      status_429: 0,
      status_5xx: 0,
      timeout_count: 29,
      p95_ceiling_ms: 5000,
      max_error_pct: 5,
      ram_limit_mb: 500,
      request_timeout_sec: 5,
      verdict: 'CIRCUIT_BREAKER',
      capacity_reason: 'All samples at 175 VUs exceeded latency ceiling.',
      timeseries: [
        { elapsed_sec: 1, vus: 175, rps: 59, p95_ms: 1045, error_pct: 0 },
        { elapsed_sec: 5, vus: 175, rps: 54, p95_ms: 5376.4, error_pct: 53.7 },
      ],
    },
  });
  assert.match(markup, /873/);
  assert.match(markup, /124\.3 MB/);
  assert.match(markup, /5,000 ms/);
  assert.match(markup, /TIMEOUTS.*29/);
  assert.match(markup, /All samples at 175 VUs exceeded latency ceiling/);
  assert.match(markup, /Step 1.*175/);

  const cmp = renderView('ReportsView', {
    reportMode: 'compare',
    runHistory: [{ run_id: 'R1' }, { run_id: 'R2' }],
    compareData: {
      base_run: { run_id: 'R1', mode: 'Step Ramp', target_vus: 100, verdict: 'PASSED', knee_vus: 50, peak_rps: 200, p95_ms: 40, error_pct: 0 },
      candidate_run: { run_id: 'R2', mode: 'Sudden Rush', target_vus: 500, verdict: 'CIRCUIT_BREAKER', knee_vus: 0, peak_rps: 60, p95_ms: 5000, error_pct: 12 },
      deltas: { knee_vus_delta: 0, peak_rps_delta: -140, p95_ms_delta: 4960, error_pct_delta: 12 },
      overall_verdict: 'REGRESSED',
      summary: 'Regression detected.',
    },
  });
  assert.match(cmp, /Comparability warning/);
  assert.match(cmp, /Error Rate/);
});

test('TestHistoryView renders CIRCUIT_BREAKER filter, active-filter empty state, and [0]/[1] compare order', () => {
  const emptyFiltered = renderView('TestHistoryView', {
    runHistory: [],
    filteredRuns: [],
    hasActiveFilter: true,
    historySearch: 'nonexistent',
    historyModeFilter: 'ALL',
    historyStatusFilter: 'CIRCUIT_BREAKER',
    selectedForCompare: [],
  });
  assert.match(emptyFiltered, /value="CIRCUIT_BREAKER"[^>]*>CIRCUIT BREAKER \(TRIPPED\)/);
  assert.match(emptyFiltered, /No matching load test runs found in archive/);
  assert.doesNotMatch(emptyFiltered, /0 RECORDED RUNS IN DATABASE/);
});

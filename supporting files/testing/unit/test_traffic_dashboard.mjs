import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { deferred, reply, trafficDashboard, verifiedTarget } from './traffic_dashboard_fixture.mjs';

test('traffic profile saves are serialized and combine edits from the current draft', async () => {
  const first = deferred();
  const saved = [];
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.equal(path, '/api/traffic/config');
    saved.push(JSON.parse(options.body));
    return saved.length === 1 ? first.promise : reply({});
  });
  const setup = dashboard.props('TrafficSetupView');
  setup.setTrafficMode('steady_crowd');
  setup.setVus(200);
  await setImmediate();
  assert.equal(saved.length, 1);
  first.resolve(reply({}));
  await setImmediate();
  assert.equal(saved.length, 2);
  assert.equal(saved[1].mode, 'steady_crowd');
  assert.equal(saved[1].virtual_users, 200);
});

test('Save Profile and Save & Launch wait for success and allow retry', async () => {
  let fail = true;
  let starts = 0;
  const save = deferred();
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    if (path === '/api/traffic/config') return fail ? reply({}, false) : save.promise;
    assert.equal(path, '/api/load/start');
    starts++;
    return reply({ snapshot: { is_running: true } });
  });
  const setup = () => dashboard.props('TrafficSetupView');
  await setup().handleSaveTraffic();
  assert.match(setup().trafficSaveError, /could not save/i);
  await setup().handleStartTest();
  assert.equal(starts, 0);
  assert.ok(setup());
  fail = false;
  const starting = setup().handleStartTest();
  await setImmediate();
  assert.equal(setup().trafficSaving, true);
  assert.equal(starts, 0);
  save.resolve(reply({}));
  await starting;
  assert.equal(starts, 1);
  assert.ok(dashboard.props('OverviewBoxes'));
});

test('late initial traffic profile hydration does not replace a local edit', async () => {
  const initial = deferred();
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/traffic/config' && !options) return initial.promise;
    if (path === '/api/target/status') return reply(verifiedTarget);
    return reply({});
  }, { hydrate: true });
  dashboard.props('TrafficSetupView').setDuration(180);
  initial.resolve(reply({ duration_sec: 60 }));
  await setImmediate();
  assert.equal(dashboard.props('TrafficSetupView').duration, 180);
});

test('Traffic Setup blocks launch when the saved VUs exceed the actual engine limit', async () => {
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.fail(`Unexpected request ${path}`);
  }, { hardware: { max_safe_ram_mb: 12000, base_engine_ram_mb: 50, ram_per_vu_mb: 0.2, max_worker_vus: 80 } });
  const setup = dashboard.props('TrafficSetupView');
  assert.equal(setup.maxAllowedVus, 80);
  assert.equal(setup.trafficVuLimit(2048), 80);
  assert.match(setup.trafficLaunchBlocker, /80 or fewer/);
  await setup.handleStartTest();
});

test('Traffic Setup explains pending, unavailable and active run status', async () => {
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.fail(`Unexpected request ${path}`);
  }, { status: null });
  const setup = () => dashboard.props('TrafficSetupView');
  assert.match(setup().trafficLaunchBlocker, /checking run status/i);
  await setup().handleStartTest();
  dashboard.monitorCallbacks.onStatusError();
  assert.match(setup().trafficLaunchBlocker, /unavailable/i);
  dashboard.monitorCallbacks.onStatus({ is_running: true });
  assert.match(setup().trafficLaunchBlocker, /already running/i);
  await setup().handleStartTest();
});

test('Traffic Setup sends one start and shows a rejection where launch was requested', async () => {
  const failedStart = deferred();
  let starts = 0;
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    if (path === '/api/traffic/config') return reply({});
    assert.equal(path, '/api/load/start');
    return ++starts === 1 ? failedStart.promise : reply({ snapshot: { is_running: true } });
  });
  const setup = () => dashboard.props('TrafficSetupView');
  const click = setup().handleStartTest;
  const first = click();
  await setImmediate();
  assert.match(setup().trafficLaunchBlocker, /starting/i);
  await click();
  assert.equal(starts, 1);
  failedStart.resolve(reply({ detail: 'The settings could not be used.' }, false));
  await first;
  assert.equal(setup().launchError, 'The settings could not be used.');
  assert.equal(setup().trafficLaunchBlocker, '');
  await setup().handleStartTest();
  assert.equal(starts, 2);
  assert.ok(dashboard.props('OverviewBoxes'));
});

test('an unconfirmed start blocks retry until the run status is known', async () => {
  let starts = 0;
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    if (path === '/api/traffic/config') return reply({});
    assert.equal(path, '/api/load/start');
    starts++;
    throw new TypeError('Network failure');
  });
  const setup = () => dashboard.props('TrafficSetupView');
  await setup().handleStartTest();
  assert.match(setup().launchError, /could not confirm/i);
  assert.match(setup().trafficLaunchBlocker, /unavailable/i);
  await setup().handleStartTest();
  assert.equal(starts, 1);
  dashboard.monitorCallbacks.onStatus({ is_running: false });
  assert.equal(setup().trafficLaunchBlocker, '');
});

test('Traffic Setup labels and launches the saved journey or single URL', async () => {
  const steps = [{ name: 'Fixture request', method: 'GET', path: '/fixture' }];
  for (const enabled of [true, false]) {
    const starts = [];
    const dashboard = await trafficDashboard(async (path, options) => {
      if (path === '/api/target/status') return reply(verifiedTarget);
      if (path === '/api/journey') return reply({ use_journey: enabled, steps });
      if (path === '/api/load/start') {
        starts.push(JSON.parse(options.body));
        return reply({ snapshot: { is_running: true } });
      }
      return reply({});
    }, { hydrate: true });
    const setup = dashboard.props('TrafficSetupView');
    assert.match(setup.runType, enabled ? /API journey.*1 step$/ : /Single URL/);
    await setup.handleStartTest();
    assert.equal(starts.length, 1);
    assert.equal(starts[0].use_journey, enabled);
    assert.deepEqual(starts[0].journey_steps, enabled ? steps : null);
  }
});

test('late journey hydration and active-run telemetry preserve an edited next run', async () => {
  const saved = deferred();
  const dashboard = await trafficDashboard(async (path) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    if (path === '/api/journey') return saved.promise;
    return reply({});
  }, { hydrate: true });
  assert.match(dashboard.props('TrafficSetupView').trafficLaunchBlocker, /loading saved run type/i);
  dashboard.navigate('api');
  const editor = () => dashboard.props('ApiBuilderView');
  editor().setUseJourney(false);
  editor().handleAddStep();
  editor().handleUpdateStep(0, 'name', 'Local edit');
  saved.resolve(reply({ use_journey: true, steps: [{ name: 'Old saved step' }] }));
  await setImmediate();
  dashboard.monitorCallbacks.onStatus({ is_running: true, use_journey: true });
  assert.equal(editor().useJourney, false);
  assert.equal(editor().journeySteps[0].name, 'Local edit');
  dashboard.navigate('traffic');
  assert.equal(dashboard.props('TrafficSetupView').runType, 'Single URL');
});

test('Clone copies configured users and duration, not peak users or elapsed time', async () => {
  const dashboard = await trafficDashboard(async path => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.fail(`Unexpected request ${path}`);
  });
  dashboard.navigate('history');
  dashboard.props('TestHistoryView').handleCloneRun({
    mode: 'Sudden Rush', target_vus: 500, peak_vus: 120, elapsed_sec: 8, duration_sec: 180,
  });
  const setup = dashboard.props('TrafficSetupView');
  assert.equal(setup.trafficMode, 'sudden_rush');
  assert.equal(setup.vus, 500);
  assert.equal(setup.duration, 180);
  assert.match(setup.trafficCloneNotice, /copied the planned/i);
});

test('Clone explains a cap adjustment and preserves the current count for legacy reports', async () => {
  const dashboard = await trafficDashboard(async path => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.fail(`Unexpected request ${path}`);
  });
  dashboard.navigate('history');
  dashboard.props('TestHistoryView').handleCloneRun({ mode: 'Step Ramp', target_vus: 9000, peakVus: 240, duration: 60 });
  const setup = () => dashboard.props('TrafficSetupView');
  assert.equal(setup().vus, 2250);
  assert.match(setup().trafficCloneNotice, /9,000 to 2,250/);
  dashboard.navigate('history');
  dashboard.props('TestHistoryView').handleCloneRun({ mode: 'Steady Crowd', peakVus: 400, duration: 300 });
  assert.equal(setup().vus, 2250);
  assert.equal(setup().duration, 300);
  assert.match(setup().trafficCloneNotice, /no planned user count/i);
});

test('rapid slider updates coalesce into one pending write with the latest draft', async () => {
  const first = deferred();
  const saved = [];
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    assert.equal(path, '/api/traffic/config');
    saved.push(JSON.parse(options.body));
    return saved.length === 1 ? first.promise : reply({});
  });
  const setup = dashboard.props('TrafficSetupView');
  setup.setVus(110);
  for (let next = 111; next <= 160; next += 1) {
    setup.setVus(next);
  }
  await setImmediate();
  assert.equal(saved.length, 1);
  first.resolve(reply({}));
  await setImmediate();
  await setImmediate();
  assert.equal(saved.length, 2);
  assert.equal(saved[1].virtual_users, 160);
});

test('Clone preserves thresholds, marks unsaved draft, and Dashboard launch auto-saves and clamps p95', async () => {
  const calls = [];
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    calls.push([path, JSON.parse(options.body)]);
    if (path === '/api/traffic/config') return reply({});
    if (path === '/api/load/start') return reply({ snapshot: { is_running: true } });
    return reply({});
  }, { hardware: { max_safe_ram_mb: 12000, base_engine_ram_mb: 50, ram_per_vu_mb: 0.2, max_worker_vus: 3000, max_p95_ceiling_ms: 8000 } });

  dashboard.navigate('history');
  dashboard.props('TestHistoryView').handleCloneRun({
    mode: 'Step Ramp',
    target_vus: 150,
    duration_sec: 60,
    ram_limit_mb: 1024,
    p95_ceiling_ms: 9500,
    max_error_pct: 10,
    cache_bust: false,
  });
  const setup = dashboard.props('TrafficSetupView');
  assert.equal(setup.ramLimitMb, 1024);
  assert.equal(setup.p95Ceiling, 8000);
  assert.equal(setup.max5xxThreshold, 10);
  assert.equal(setup.cacheBusting, false);
  assert.equal(setup.hasUnsavedTraffic, true);
  assert.equal(calls.length, 0);

  dashboard.navigate('dashboard');
  assert.equal(dashboard.props('OverviewBoxes').hasUnsavedTraffic, true);
  await dashboard.props('OverviewBoxes').handleStartTest();
  assert.deepEqual(calls.map(([p]) => p), ['/api/traffic/config', '/api/load/start']);
  assert.equal(calls[1][1].p95_ceiling_ms, 8000);
});

test('filtered history preserves dashboard scorecard and clear-archive honors confirm()', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let deletes = 0;
  let allowConfirm = false;
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/target/status') return reply(verifiedTarget);
    if (path === '/api/history' && options?.method === 'DELETE') {
      deletes += 1;
      return reply({});
    }
    if (path.startsWith('/api/history')) {
      const hasFilter = path.includes('verdict=');
      return reply({
        runs: [{ run_id: hasFilter ? 'R-FILTERED' : 'R-GLOBAL', mode: 'Step Ramp', verdict: hasFilter ? 'FAILED' : 'PASSED' }],
        scorecard: hasFilter
          ? { run_id: 'R-FILTERED', knee_vus: 0, peak_rps: 10, p95_ms: 5000 }
          : { run_id: 'R-GLOBAL', knee_vus: 40, peak_rps: 500, p95_ms: 120 },
      });
    }
    return reply({});
  }, { confirm: () => allowConfirm });

  dashboard.runEffect('fetchHistory');
  t.mock.timers.tick(200);
  await setImmediate();
  dashboard.navigate('dashboard');
  assert.equal(dashboard.props('OverviewBoxes').latestScorecard.run_id, 'R-GLOBAL');

  dashboard.navigate('history');
  await dashboard.props('TestHistoryView').handleClearArchive();
  assert.equal(deletes, 0);
  allowConfirm = true;
  await dashboard.props('TestHistoryView').handleClearArchive();
  assert.equal(deletes, 1);

  dashboard.runEffect('fetchHistory');
  t.mock.timers.tick(200);
  await setImmediate();
  dashboard.props('TestHistoryView').setHistoryStatusFilter('CIRCUIT_BREAKER');
  dashboard.runEffect('fetchHistory');
  t.mock.timers.tick(200);
  await setImmediate();
  dashboard.navigate('dashboard');
  assert.equal(dashboard.props('OverviewBoxes').latestScorecard.run_id, 'R-GLOBAL');
});

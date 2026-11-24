import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { deferred, reply, trafficDashboard, verifiedTarget } from './traffic_dashboard_fixture.mjs';
import { loadView, renderView } from './react_view_fixture.mjs';

const step = { step_id: 'step_1', name: 'Original', method: 'GET', path: '/fixture' };
const hardware = { max_safe_ram_mb: 12000, base_engine_ram_mb: 50, ram_per_vu_mb: 0.2, max_worker_vus: 3000 };

async function builder(fetch, steps = [step], target = verifiedTarget, options = {}) {
  const dashboard = await trafficDashboard(async (path, options) => {
    if (path === '/api/target/status') return reply(target);
    if (path === '/api/journey') return reply({ use_journey: false, steps });
    return fetch(path, options);
  }, { hydrate: true, ...options });
  dashboard.navigate('api');
  return { ...dashboard, view: () => dashboard.props('ApiBuilderView') };
}

test('standalone Save blocks an empty journey and works again after adding a step', async () => {
  const writes = [];
  const { view } = await builder(async (path, options) => {
    if (path === '/api/journey/save') {
      const payload = JSON.parse(options.body);
      writes.push(payload);
      return reply(payload);
    }
    return reply({});
  }, []);

  await view().handleSaveJourney();
  assert.deepEqual(writes, []);
  const empty = renderView('ApiBuilderView', view());
  assert.match(empty, /<button[^>]*disabled=""[^>]*>Save Journey Configuration/);
  assert.match(empty, /Add at least one step before saving/);

  view().handleAddStep();
  assert.doesNotMatch(renderView('ApiBuilderView', view()), /<button[^>]*disabled=""[^>]*>Save Journey Configuration/);
  await view().handleSaveJourney();
  assert.equal(writes.length, 1);
  assert.equal(writes[0].steps.length, 1);

  view().handleDeleteStep(0);
  assert.equal(view().journeySteps.length, 1);
});

test('an unverified target blocks Save & Launch before saving and allows a standalone save', async () => {
  const writes = [];
  const { view } = await builder(async (path, options) => {
    if (options?.method === 'POST') writes.push([path, JSON.parse(options.body)]);
    return reply({ use_journey: false, steps: [step] });
  }, [step], { ...verifiedTarget, is_verified: false });

  await view().handleSaveAndLaunchJourney();
  assert.deepEqual(writes, []);
  const markup = renderView('ApiBuilderView', view());
  assert.match(markup, /Verify the target before launching/);
  assert.match(markup, /<button[^>]*disabled=""[^>]*>Save &amp; Launch/);

  await view().handleSaveJourney();
  assert.deepEqual(writes.map(([path]) => path), ['/api/journey/save']);
  assert.equal(writes[0][1].use_journey, false);
});

test('a verified target launches only after the journey is saved', async () => {
  const writes = [];
  const saved = { ...step, name: 'Acknowledged step' };
  const { view, props } = await builder(async (path, options) => {
    if (options?.method === 'POST') writes.push([path, JSON.parse(options.body)]);
    if (path === '/api/journey/save') return reply({ use_journey: true, steps: [saved] });
    if (path === '/api/load/start') return reply({ snapshot: { is_running: true } });
    return reply({});
  }, [step], verifiedTarget, { hardware: { ...hardware, max_worker_vus: 100 } });

  await view().handleSaveAndLaunchJourney();
  assert.deepEqual(writes.map(([path]) => path), ['/api/journey/save', '/api/load/start']);
  assert.equal(writes[1][1].use_journey, true);
  assert.equal(writes[1][1].target_vus, 100);
  assert.equal(writes[1][1].journey_steps[0].name, saved.name);
  assert.ok(props('OverviewBoxes'));
});

test('Builder and Traffic Setup block the same over-limit or unknown traffic profiles', async (t) => {
  const cases = [
    ['engine worker limit', { ...hardware, max_worker_vus: 80 }, 'Reduce virtual users to 80 or fewer.'],
    ['host RAM limit', { ...hardware, max_safe_ram_mb: 400 }, 'Reduce the RAM budget to the host limit.'],
    ['unavailable hardware limits', null, 'Hardware limits are unavailable.'],
  ];

  for (const [name, limits, reason] of cases) {
    await t.test(name, async () => {
      const writes = [];
      const { navigate, props, view } = await builder(async (path, options) => {
        if (options?.method === 'POST') writes.push(path);
        if (path === '/api/journey/save') return reply({ use_journey: true, steps: [step] });
        if (path === '/api/load/start') return reply({ snapshot: { is_running: true } });
        return reply({});
      }, [step], verifiedTarget, { hardware: limits });

      await view().handleSaveAndLaunchJourney();
      assert.deepEqual(writes, []);
      assert.equal(view().journeyLaunchBlocker, reason);
      assert.match(renderView('ApiBuilderView', view()), /<button[^>]*disabled=""[^>]*>Save &amp; Launch/);

      navigate('traffic');
      assert.equal(props('TrafficSetupView').trafficLaunchBlocker, reason);
    });
  }
});

test('a late save keeps later edits and prevents stale launch or duplicate saves', async () => {
  const accepted = deferred();
  const paths = [];
  const { view } = await builder(async path => {
    if (path === '/api/journey/save') {
      paths.push(path);
      return accepted.promise;
    }
    if (path === '/api/load/start') paths.push(path);
    return reply({});
  });
  const launching = view().handleSaveAndLaunchJourney();
  await setImmediate();
  assert.equal(view().journeySaving, true);
  view().handleUpdateStep(0, 'name', 'Newer edit');
  view().setUseJourney(false);
  await view().handleSaveJourney();
  accepted.resolve(reply({ use_journey: true, steps: [step] }));
  await launching;
  assert.equal(view().journeySteps[0].name, 'Newer edit');
  assert.equal(view().useJourney, false);
  assert.equal(view().journeySaving, false);
  assert.match(view().journeyMessage, /earlier draft was saved/i);
  assert.deepEqual(paths, ['/api/journey/save']);
});

test('Add Step caps the draft even if multiple clicks use the same render', async () => {
  const steps = Array.from({ length: 9 }, (_, index) => ({ ...step, step_id: `step_${index + 1}` }));
  const { view } = await builder(async () => reply({}), steps);
  const click = view().handleAddStep;
  click();
  click();
  assert.equal(view().journeySteps.length, 10);
  assert.match(renderView('ApiBuilderView', view()), /<button[^>]*disabled=""[^>]*>.*?Add Step \(10\/10\)/);
});

test('structured save and dry-run errors appear as text without rendering submitted data', async () => {
  const { view } = await builder(async path => {
    if (path === '/api/journey/save' || path === '/api/journey/dry-run') {
      return reply({ detail: [{ loc: ['body', 'steps'], type: 'too_long', input: 'fixture-private-input' }] }, false);
    }
    return reply({});
  });
  await view().handleSaveJourney();
  assert.match(view().journeyMessage, /up to 10 steps/);
  await view().handleExecuteDryRun();
  const markup = renderView('ApiBuilderView', view());
  assert.match(markup, /up to 10 steps/);
  assert.doesNotMatch(markup, /fixture-private-input/);
});

test('the body editor keeps quoted JSON text as entered', () => {
  const edits = [];
  const tree = loadView('ApiBuilderView')({
    journeySteps: [step],
    handleUpdateStep: (...args) => edits.push(args),
  });
  function findBody(node) {
    if (Array.isArray(node)) return node.map(findBody).find(Boolean);
    if (node?.props?.placeholder === '{"quantity": 1}') return node;
    return node?.props ? findBody(node.props.children) : undefined;
  }
  findBody(tree).props.onChange({ target: { value: '"literal"' } });
  assert.deepEqual(edits, [[0, 'body', '"literal"']]);
});

test('Add Step keeps IDs unique after deletion and supplies a neutral target-relative default', async () => {
  const steps = [1, 2, 3].map(index => ({ ...step, step_id: `step_${index}` }));
  const { view } = await builder(async () => reply({}), steps);
  view().handleDeleteStep(1);
  const click = view().handleAddStep;
  click();
  click();
  const added = view().journeySteps;
  assert.deepEqual(added.slice(0, 2).map(item => item.step_id), ['step_1', 'step_3']);
  assert.equal(new Set(added.map(item => item.step_id)).size, 4);
  assert.deepEqual(added.slice(2).map(item => [item.path, item.method, item.headers]), [
    ['/', 'GET', {}], ['/', 'GET', {}],
  ]);
  const sandboxUrl = 'http://127.0.0.1:8000/api/sandbox/target';
  const sandbox = await builder(async () => reply({}), [], {
    ...verifiedTarget, is_sandbox: true, sandbox_url: sandboxUrl, target_url: sandboxUrl,
  });
  sandbox.view().handleAddStep();
  assert.equal(sandbox.view().journeySteps[0].path, '/api/sandbox/items');
});

const passedDryRun = {
  status: 'completed', all_passed: true, total_steps: 1, total_duration_ms: 1,
  steps: [{ passed: true }], results: [{ ...step, passed: true, status_code: 200 }],
};

test('editing and a rejected retry remove the previous successful dry run', async () => {
  let attempts = 0;
  const { view, runEffect } = await builder(async path => {
    if (path !== '/api/journey/dry-run') return reply({});
    return ++attempts === 1 ? reply(passedDryRun) : reply({ detail: 'Target is unavailable.' }, false);
  });
  await view().handleExecuteDryRun();
  assert.equal(view().dryRunResults.all_passed, true);
  runEffect('Array.isArray(previous)');
  assert.equal(view().dryRunResults, null);
  view().handleUpdateStep(0, 'path', '/new');
  await view().handleExecuteDryRun();
  assert.equal(view().dryRunResults, null);
  assert.match(view().journeyMessage, /Target is unavailable/);
});

test('a dry run finishing after an edit cannot restore its previous result', async () => {
  const result = deferred();
  let attempts = 0;
  const { view } = await builder(async path => {
    if (path !== '/api/journey/dry-run') return reply({});
    attempts++;
    return result.promise;
  });
  const waiting = view().handleExecuteDryRun();
  view().handleUpdateStep(0, 'path', '/new');
  await view().handleExecuteDryRun();
  result.resolve(reply(passedDryRun));
  await waiting;
  assert.equal(attempts, 1);
  assert.equal(view().dryRunResults, null);
  assert.equal(view().isDryRunning, false);
});

test('Stop Dry Run sends the matching ID and allows a retry after rejection', async () => {
  const running = deferred();
  const stopIds = [];
  let id;
  const { view } = await builder(async (path, options) => {
    if (path === '/api/journey/dry-run') {
      id = JSON.parse(options.body).dry_run_id;
      return running.promise;
    }
    if (path === '/api/journey/dry-run/stop') {
      stopIds.push(JSON.parse(options.body).dry_run_id);
      if (stopIds.length === 1) return reply({ detail: 'Stop unavailable.' }, false);
      running.resolve(reply({ status: 'cancelled', message: 'Stopped by the operator.' }));
      return reply({ status: 'stopped' });
    }
    return reply({});
  });
  const pending = view().handleExecuteDryRun();
  assert.ok(id);
  assert.match(renderView('ApiBuilderView', view()), /Stop dry run/);
  await view().handleStopDryRun();
  assert.equal(view().dryRunStopping, false);
  assert.match(view().journeyMessage, /Stop unavailable/);
  await view().handleStopDryRun();
  await pending;
  assert.deepEqual(stopIds, [id, id]);
  assert.equal(view().dryRunResults.status, 'cancelled');
  assert.equal(view().isDryRunning, false);
});

test('write steps require confirmation and the request identifies the displayed Guard', async () => {
  let allowed = false;
  const confirmations = [];
  const requests = [];
  const write = { ...step, method: 'POST' };
  const { view } = await builder(async (path, options) => {
    if (path === '/api/journey/dry-run') requests.push(JSON.parse(options.body));
    return reply(passedDryRun);
  }, [write], verifiedTarget, { confirm: message => { confirmations.push(message); return allowed; } });
  assert.match(renderView('ApiBuilderView', view()), /send real requests to.*fixture.example.invalid/);
  await view().handleExecuteDryRun();
  assert.equal(requests.length, 0);
  assert.match(confirmations[0], /fixture.example.invalid/);
  allowed = true;
  await view().handleExecuteDryRun();
  assert.equal(requests[0].guard_id, verifiedTarget.guard_id);
  view().handleUpdateStep(0, 'method', 'GET');
  await view().handleExecuteDryRun();
  assert.equal(confirmations.length, 2);
  assert.equal(requests.length, 2);
});

test('an unverified Builder cannot start a dry run', async () => {
  const { view } = await builder(async (path) => {
    assert.notEqual(path, '/api/journey/dry-run');
    return reply({});
  }, [step], { ...verifiedTarget, is_verified: false });
  await view().handleExecuteDryRun();
  assert.match(view().journeyMessage, /verify the target/i);
});

test('sandbox preset is hidden without the server capability', async () => {
  const { view } = await builder(async path => {
    assert.notEqual(path, '/api/journey/sandbox-defaults');
    return reply({});
  });
  assert.doesNotMatch(renderView('ApiBuilderView', view()), /Reset Sandbox Defaults/);
  await view().handleResetJourneyDefaults();
  assert.equal(view().journeySteps[0].name, step.name);
});

test('sandbox reset confirms replacement and ignores late results after an edit', async () => {
  const latePreset = deferred();
  const preset = { ...step, name: 'Sandbox preset' };
  let confirmed = false;
  let resets = 0;
  const { view } = await builder(async path => {
    if (path === '/api/journey/sandbox-defaults') {
      return ++resets === 1 ? latePreset.promise : reply({ steps: [preset] });
    }
    return reply({});
  }, [step], { ...verifiedTarget, sandbox_url: 'http://127.0.0.1:8000/api/sandbox/target' },
  { confirm: () => confirmed });
  assert.match(renderView('ApiBuilderView', view()), /Reset Sandbox Defaults/);
  await view().handleResetJourneyDefaults();
  assert.equal(resets, 0);
  confirmed = true;
  const waiting = view().handleResetJourneyDefaults();
  assert.equal(view().resettingJourney, true);
  await view().handleResetJourneyDefaults();
  assert.equal(resets, 1);
  view().handleUpdateStep(0, 'name', 'Later edit');
  latePreset.resolve(reply({ steps: [preset] }));
  await waiting;
  assert.equal(view().journeySteps[0].name, 'Later edit');
  await view().handleResetJourneyDefaults();
  assert.equal(view().journeySteps[0].name, 'Sandbox preset');
});

import assert from 'node:assert/strict';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import { loadView } from './react_view_fixture.mjs';
import { watchRun } from '../../../frontend/src/lib/runMonitor.js';

const OverviewBoxes = loadView('OverviewBoxes');
const active = (revision, run_id = 'RUN-A') => ({ status_revision: revision, is_running: true, run_id });
const ended = (revision, run_id = 'RUN-A') => ({ status_revision: revision, is_running: false, run_id });
const reply = (body, ok = true) => ({ ok, json: async () => body });
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};

function find(node, predicate) {
  if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean);
  if (node == null) return undefined;
  return predicate(node) ? node : node.props && find(node.props.children, predicate);
}

function setup(t, fetch) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const socket = { close: t.mock.fn(), send: t.mock.fn(), readyState: 0 };
  const state = { status: null, unavailable: false, stopping: false, error: '' };
  const monitor = watchRun({
    fetch,
    getToken: async () => 'test-session',
    openSocket: () => socket,
    onStatus(status) {
      state.status = status;
      state.unavailable = false;
    },
    onStatusError() { state.unavailable = true; },
    onStopping(value) { state.stopping = value; },
    onStopError(error) { state.error = error; },
  });
  t.after(() => monitor.close());
  const clickStop = () => monitor.stop(state.status?.run_id);
  function view() {
    return OverviewBoxes({
      isVerified: false, telemetry: {}, elapsed: 0, duration: 60,
      testRunning: Boolean(state.status?.is_running),
      canStart: Boolean(state.status && !state.status.is_running && !state.unavailable),
      statusUnavailable: state.unavailable,
      stopping: state.stopping, stopError: state.error, handleStopTest: clickStop,
    });
  }
  return { socket, state, monitor, view,
    stopButton: () => find(view(), (node) => node.type === 'button' && node.props.onClick === clickStop) };
}

test('reload without WebSocket recovers the run and Stop sends its ID', async (t) => {
  const request = deferred();
  const fetch = t.mock.fn(async (path) => path === '/api/load/status' ? request.promise :
    reply({ snapshot: ended(2) }));
  const { stopButton, view, state, socket } = setup(t, fetch);
  assert.equal(socket.readyState, 0);
  assert.equal(fetch.mock.calls[0].arguments[0], '/api/load/status');
  assert.ok(find(view(), (node) => node === 'Checking run status…'));
  assert.equal(stopButton(), undefined);

  request.resolve(reply(active(1)));
  await setImmediate();
  assert.equal(state.status.run_id, 'RUN-A');
  await stopButton().props.onClick();
  const [path, options] = fetch.mock.calls[1].arguments;
  assert.equal(path, '/api/load/stop');
  assert.equal(options.method, 'POST');
  assert.deepEqual(JSON.parse(options.body), { run_id: 'RUN-A' });
  assert.equal(stopButton(), undefined);
});

test('an idle or owner-filtered snapshot has no Stop control', async (t) => {
  const { stopButton, monitor, state } = setup(t, async () => reply(ended(1, null)));
  await setImmediate();
  assert.equal(state.status.is_running, false);
  assert.equal(stopButton(), undefined);
  monitor.accept(ended(2, 'RUN-OLD'));
  assert.equal(stopButton(), undefined);
});

test('HTTP fallback retries an unavailable initial response', async (t) => {
  let attempts = 0;
  const { stopButton, view } = setup(t, async () => ++attempts === 1 ? reply({}, false) : reply(active(2)));
  await setImmediate();
  assert.equal(stopButton(), undefined);
  assert.ok(find(view(), (node) => node === 'Run status unavailable. Retrying…'));
  t.mock.timers.tick(1000);
  await setImmediate();
  assert.ok(stopButton());
});

test('older HTTP or WebSocket snapshots cannot revive a finished or superseded run', async (t) => {
  const request = deferred();
  const { stopButton, socket, state } = setup(t, () => request.promise);
  const frame = (data) => socket.onmessage({ data: JSON.stringify(data) });
  frame(active(2));
  assert.ok(stopButton());
  frame({ ...ended(3), event: 'COMPLETE' });
  request.resolve(reply(active(1, 'RUN-OLDER')));
  await setImmediate();
  frame(active(2));
  assert.equal(stopButton(), undefined);
  frame(active(4, 'RUN-B'));
  frame(ended(3));
  assert.equal(state.status.run_id, 'RUN-B');
  assert.ok(stopButton());
});

test('a failed Stop keeps the same run actionable and lets the owner retry', async (t) => {
  let stops = 0;
  const { stopButton, state, view } = setup(t, async (path) => {
    if (path === '/api/load/status') return reply(active(1));
    return ++stops === 1 ? reply({ detail: 'Stop temporarily unavailable' }, false) :
      reply({ snapshot: ended(2) });
  });
  await setImmediate();
  await stopButton().props.onClick();
  assert.ok(find(view(), (node) => node.props?.role === 'alert'));
  assert.equal(state.error, 'Stop temporarily unavailable');
  assert.equal(stopButton().props.disabled, false);
  await stopButton().props.onClick();
  assert.equal(stops, 2);
  assert.equal(stopButton(), undefined);
});

test('closing a monitor aborts the pending status request and ignores late responses', async (t) => {
  const request = deferred();
  const fetch = t.mock.fn(() => request.promise);
  const { monitor, state, socket } = setup(t, fetch);
  monitor.close();
  assert.equal(fetch.mock.calls[0].arguments[1].signal.aborted, true);
  assert.equal(socket.close.mock.callCount(), 1);
  request.resolve(reply(active(1)));
  await setImmediate();
  t.mock.timers.tick(2000);
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(state.status, null);
});

test('terminal WS event still fires ended=true after an intermediate HTTP poll flipped is_running to false', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const socket = { close: t.mock.fn(), send: t.mock.fn(), readyState: 1 };
  const endedEvents = [];
  const monitor = watchRun({
    fetch: async () => reply(active(1, 'RUN-RACE')),
    getToken: async () => 'test-session',
    openSocket: () => socket,
    onStatus(status, ended) {
      if (ended) endedEvents.push(status);
    },
    onStatusError() {},
    onStopping() {},
    onStopError() {},
  });
  t.after(() => monitor.close());
  await setImmediate();

  // Intermediate HTTP poll after engine sets is_running=false but before _finish_run saves
  monitor.accept({ status_revision: 2, is_running: false, run_id: 'RUN-RACE' });
  assert.equal(endedEvents.length, 1);

  // Terminal WS event arrives after save_run() completes
  socket.onmessage({
    data: JSON.stringify({ status_revision: 3, is_running: false, run_id: 'RUN-RACE', event: 'CIRCUIT_TRIPPED' }),
  });
  assert.equal(endedEvents.length, 2);
  assert.equal(endedEvents[1].event, 'CIRCUIT_TRIPPED');
});

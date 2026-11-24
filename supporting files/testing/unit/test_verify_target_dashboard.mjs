import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { setImmediate } from 'node:timers/promises';
import * as targetInput from '../../../frontend/src/lib/targetInput.js';
import * as trafficProfile from '../../../frontend/src/lib/trafficProfile.js';

const frontend = new URL('../../../frontend/', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
const React = require('react');
const { transformSync } = require('esbuild');
const { code } = transformSync(readFileSync(new URL('src/pages/DashboardPage.jsx', frontend), 'utf8'), {
  loader: 'jsx',
  format: 'cjs',
});
const sandboxUrl = 'http://127.0.0.1:8123/api/sandbox/target';
const active = {
  is_verified: true,
  guard_id: 'PG-FIXTURE',
  target_url: 'https://verified.example.invalid/',
  remaining_seconds: 600,
  is_sandbox: false,
  sandbox_url: sandboxUrl,
};
const revoked = {
  ...active,
  is_verified: false,
  guard_id: null,
  remaining_seconds: 0,
  last_burn_reason: 'MANUAL_USER_KILL',
  last_revoked_guard_id: active.guard_id,
};
const reply = (body, ok = true) => ({ ok, json: async () => body });

function find(node, predicate) {
  if (Array.isArray(node)) return node.map(child => find(child, predicate)).find(Boolean);
  if (!node?.props) return undefined;
  return predicate(node) ? node : find(node.props.children, predicate);
}

async function dashboard(operatorFetch) {
  const values = [];
  const refs = [];
  const effects = [];
  let stateIndex, refIndex;
  const hooks = {
    ...React,
    useState(initial) {
      const index = stateIndex++;
      if (!(index in values)) values[index] = typeof initial === 'function' ? initial() : initial;
      return [values[index], value => {
        values[index] = typeof value === 'function' ? value(values[index]) : value;
      }];
    },
    useRef(initial) {
      return refs[refIndex++] ??= { current: initial };
    },
    useEffect(effect) {
      effects.push(effect);
    },
  };
  const imports = {
    react: hooks,
    '../lib/targetInput': targetInput,
    '../lib/trafficProfile': trafficProfile,
    '../lib/operatorApi': { operatorFetch },
    '../lib/telemetry': { mapTelemetry: () => ({}) },
    '../lib/runMonitor': {
      watchRun({ onStatus }) {
        onStatus({ is_running: false });
        return { close() {} };
      },
    },
  };
  const module = { exports: {} };
  new Function('module', 'require', code)(module, name => {
    if (name in imports) return imports[name];
    if (name.startsWith('../')) return () => null;
    return require(name);
  });

  function render() {
    stateIndex = refIndex = effects.length = 0;
    return module.exports.default({ operator: { user_id: 'fixture' } });
  }

  render();
  effects.find(effect => effect.toString().includes('fetchTargetStatus'))();
  effects.find(effect => effect.toString().includes('watchRun'))();
  await setImmediate();
  const overview = () => find(render(), node => node.props.handleStopTest).props;
  overview().setActiveNav('verify');
  const verify = () => find(render(), node => node.props.handleKillGuard).props;
  verify.overview = () => {
    verify().setActiveNav('dashboard');
    return overview();
  };
  return verify;
}

test('Kill ID keeps the last confirmed Guard when offline and accepts a successful retry', async () => {
  let attempt = 0;
  let status = active;
  const view = await dashboard(async path => {
    if (path === '/api/target/status') {
      if (attempt === 1) throw new TypeError('offline');
      return reply(status);
    }
    assert.equal(path, '/api/target/kill');
    if (++attempt === 1) throw new TypeError('offline');
    status = revoked;
    return reply({ is_verified: false, revoked_guard_id: active.guard_id, last_burn_reason: revoked.last_burn_reason });
  });
  await view().handleKillGuard();
  assert.equal(view().guardToken, active.guard_id);
  assert.equal(view().isVerified, true);
  assert.equal(view().lastBurnReason, null);
  assert.match(view().verificationError, /could not confirm/i);

  await view().handleKillGuard();
  assert.equal(view().guardToken, null);
  assert.equal(view().isVerified, false);
  assert.equal(view().lastBurnReason, 'MANUAL_USER_KILL');
  assert.equal(view().verificationError, null);
});

test('Kill ID reports an unreadable success reply as unconfirmed', async () => {
  const view = await dashboard(async path => {
    if (path === '/api/target/status') return reply(active);
    assert.equal(path, '/api/target/kill');
    return { ok: true, json: async () => { throw new SyntaxError('invalid JSON'); } };
  });
  await view().handleKillGuard();
  assert.match(view().verificationError, /could not confirm/i);
  assert.equal(view().guardToken, active.guard_id);
  assert.equal(view().lastBurnReason, null);
});

test('Kill ID refreshes status after rejection and shows only the confirmed revocation reason', async () => {
  let status = active;
  let statusReads = 0;
  const view = await dashboard(async path => {
    if (path === '/api/target/status') {
      statusReads++;
      return reply(status);
    }
    assert.equal(path, '/api/target/kill');
    status = { ...revoked, last_burn_reason: 'DEVICE_MISMATCH_VIOLATION' };
    return reply({ detail: { detail: 'Device mismatch.' } }, false);
  });
  await view().handleKillGuard();
  assert.equal(statusReads, 2);
  assert.equal(view().isVerified, false);
  assert.equal(view().lastBurnReason, 'DEVICE_MISMATCH_VIOLATION');
  assert.equal(view().verificationError, 'Device mismatch.');
});

test('verification follows the draft origin and mode while retaining the active Guard', async () => {
  const view = await dashboard(async path => {
    assert.equal(path, '/api/target/status');
    return reply(active);
  });
  for (const draft of [
    'https://different.example.invalid/',
    'http://verified.example.invalid/',
    'https://verified.example.invalid:8443/',
    'https://user@verified.example.invalid/',
    'invalid URL',
  ]) {
    view().setTargetUrl(draft);
    assert.equal(view().isVerified, false, draft);
    assert.equal(view().verifiedOrigin, 'https://verified.example.invalid');
    assert.equal(view().guardToken, active.guard_id);
    assert.equal(view().guardTimerSeconds, 600);
  }
  const equivalent = 'https://VERIFIED.example.invalid:443/orders?runtime=fixture';
  view().setTargetUrl(equivalent);
  assert.equal(view().isVerified, true);
  view().handleToggleSandbox();
  view().setTargetUrl(equivalent);
  assert.equal(view().isVerified, false);
  view().handleToggleSandbox();
  assert.equal(view().isVerified, true);
});

test('launch does not send an unmatched draft to the load endpoint', async () => {
  const paths = [];
  const view = await dashboard(async path => {
    paths.push(path);
    return reply(active);
  });
  view().setTargetUrl('https://different.example.invalid/');
  await view.overview().handleStartTest();
  assert.deepEqual(paths, ['/api/target/status']);
  assert.match(view().verificationError, /must be verified/i);
});

test('sandbox uses the configured URL and verifies directly while preserving the live draft', async () => {
  const view = await dashboard(async (path, options) => {
    if (path === '/api/target/status') return reply({
      ...active, guard_id: null, is_verified: false, target_url: '', remaining_seconds: 0,
    });
    assert.equal(path, '/api/target/verify');
    const payload = JSON.parse(options.body);
    assert.equal(payload.target_url, sandboxUrl);
    assert.equal(payload.is_sandbox, true);
    assert.equal(payload.guard_id, null);
    return reply({
      target_url: sandboxUrl,
      is_verified: true,
      guard_id: 'PG-SYNTHETIC-SANDBOX',
      remaining_seconds: 172800,
    });
  });
  const draft = 'https://draft.example.invalid/orders';
  view().setTargetUrl(draft);
  view().handleToggleSandbox();
  assert.equal(view().targetUrl, sandboxUrl);
  await view().handleVerifyTarget();
  assert.equal(view().isVerified, true);
  assert.equal(view().guardToken, 'PG-SYNTHETIC-SANDBOX');
  view().handleToggleSandbox();
  assert.equal(view().targetUrl, draft);
  assert.equal(view().isVerified, false);
});

test('a live Guard stays active until explicitly revoked before sandbox verification', async () => {
  const paths = [];
  const view = await dashboard(async path => {
    paths.push(path);
    return reply(active);
  });
  view().handleToggleSandbox();
  assert.equal(view().sandboxRequiresRevocation, true);
  await view().handleVerifyTarget();
  assert.deepEqual(paths, ['/api/target/status']);
  assert.equal(view().guardToken, active.guard_id);
  assert.match(view().verificationError, /revoke the current live guard/i);
});

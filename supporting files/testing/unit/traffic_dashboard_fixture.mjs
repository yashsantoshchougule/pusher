import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { setImmediate } from 'node:timers/promises';
import * as targetInput from '../../../frontend/src/lib/targetInput.js';
import * as trafficProfile from '../../../frontend/src/lib/trafficProfile.js';
import * as journeyLaunch from '../../../frontend/src/lib/journeyLaunch.js';

const frontend = new URL('../../../frontend/', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
const React = require('react');
const { transformSync } = require('esbuild');
const { code } = transformSync(readFileSync(new URL('src/pages/DashboardPage.jsx', frontend), 'utf8'), {
  loader: 'jsx',
  format: 'cjs',
});

export const reply = (body, ok = true) => ({ ok, json: async () => body });
export const verifiedTarget = {
  is_verified: true, target_url: 'https://fixture.example.invalid/',
  guard_id: 'PG-FIXTURE', remaining_seconds: 3600,
};
export const deferred = () => {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
};

function find(node, predicate) {
  if (Array.isArray(node)) return node.map(child => find(child, predicate)).find(Boolean);
  if (!node?.props) return undefined;
  return predicate(node) ? node : find(node.props.children, predicate);
}

const defaultHardware = {
  max_safe_ram_mb: 12000, base_engine_ram_mb: 50, ram_per_vu_mb: 0.2, max_worker_vus: 3000,
};

export async function trafficDashboard(fetch, {
  hydrate = false, status = { is_running: false }, hardware = defaultHardware, confirm = () => true,
} = {}) {
  const values = [], refs = [], effects = [];
  let stateIndex, refIndex, monitorCallbacks;
  const hooks = {
    ...React,
    useState(initial) {
      const index = stateIndex++;
      if (!(index in values)) values[index] = typeof initial === 'function' ? initial() : initial;
      return [values[index], value => {
        values[index] = typeof value === 'function' ? value(values[index]) : value;
      }];
    },
    useRef(initial) { return refs[refIndex++] ??= { current: initial }; },
    useEffect(effect) { effects.push(effect); },
  };
  const imports = {
    react: hooks,
    '../lib/targetInput': targetInput,
    '../lib/trafficProfile': trafficProfile,
    '../lib/journeyLaunch': journeyLaunch,
    '../lib/operatorApi': { operatorFetch(path, options) {
      if (path === '/api/system/limits') return Promise.resolve(reply(hardware, Boolean(hardware)));
      if (!hydrate && !options && ['/api/traffic/config', '/api/journey', '/api/profile'].includes(path)) {
        return Promise.resolve(reply(path === '/api/journey' ? { use_journey: false, steps: [] } : {}));
      }
      return fetch(path, options);
    } },
    '../lib/telemetry': { mapTelemetry: () => ({}) },
    '../utils/deviceFingerprint': { getDeviceId: async () => 'fixture-device' },
    '../lib/runMonitor': {
      watchRun(callbacks) {
        monitorCallbacks = callbacks;
        if (status) callbacks.onStatus(status);
        return { accept: callbacks.onStatus, refresh() {}, close() {} };
      },
    },
  };
  const module = { exports: {} };
  new Function('module', 'require', 'document', 'window', code)(module, name => {
    if (name in imports) return imports[name];
    if (name.startsWith('../components/dashboard/')) return name.split('/').at(-1);
    if (name.startsWith('../')) return () => null;
    return require(name);
  }, { body: { style: {} } }, { confirm });

  function render() {
    stateIndex = refIndex = effects.length = 0;
    return module.exports.default({ operator: { user_id: 'fixture' } });
  }
  const props = name => find(render(), node => node.type === name)?.props;
  render();
  effects.find(effect => effect.toString().includes('fetchTargetStatus'))();
  effects.find(effect => effect.toString().includes('watchRun'))();
  effects.find(effect => effect.toString().includes('hydrateFromDatabase'))();
  await setImmediate();
  const navigate = props('OverviewBoxes').setActiveNav;
  navigate('traffic');
  const runEffect = (marker) => {
    render();
    return effects.find(effect => effect.toString().includes(marker))();
  };
  return { props, navigate, monitorCallbacks, runEffect };
}

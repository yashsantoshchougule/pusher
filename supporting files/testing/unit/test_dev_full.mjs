import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { findPython, localOptions, sessionReady, waitUntilReady } from '../../../frontend/scripts/dev-full.mjs';

const launcher = fileURLToPath(new URL('../../../frontend/scripts/dev-full.mjs', import.meta.url));

test('launcher defaults to cloud on the normal loopback ports and accepts explicit offline mode', () => {
  assert.deepEqual(localOptions([], {}), { frontendPort: 3000, backendPort: 8000, offline: false });
  assert.equal(localOptions(['--offline'], { PUSHER_DEV_FRONTEND_PORT: '4000' }).offline, true);
  assert.throws(() => localOptions([], { PUSHER_DEV_BACKEND_PORT: '0' }), /between 1 and 65535/);
  assert.throws(() => localOptions([], { PUSHER_DEV_BACKEND_PORT: '3000' }), /different ports/);
  assert.throws(() => localOptions(['--public'], {}), /Supported argument/);
});

test('Windows fallback uses the matching base Python and the synced environment only', t => {
  const folder = mkdtempSync(join(tmpdir(), 'pusher-dev-test-'));
  t.after(() => rmSync(folder, { recursive: true, force: true }));
  const directory = join(folder, '.venv');
  assert.throws(() => findPython({ directory, platform: 'win32', env: {}, probe() {} }), /uv sync --locked/);
  const home = join(folder, 'base');
  const env = { PUSHER_OFFLINE_DEV: 'false' };
  writeFileSync(join(folder, 'pyvenv.cfg'), `home = ${home}\nversion_info = 3.12\n`);
  const blocked = { error: new Error('Application Control') };
  const exe = join(home, 'python.exe');
  const selection = findPython({
    directory: folder, platform: 'win32', env,
    probe: file => file === exe ? { status: 0, stdout: '3.12.13\n' } : blocked,
  });
  assert.deepEqual(selection, { executable: exe, env: { ...env, PYTHONPATH: join(folder, 'Lib', 'site-packages') } });
  assert.throws(() => findPython({
    directory: folder, platform: 'win32', env,
    probe: file => file === exe ? { status: 0, stdout: '3.13.0\n' } : blocked,
  }), /could not start/);
  assert.equal(env.PYTHONPATH, undefined);
});

test('readiness rejects proxy failures and accepts only the expected session response', async () => {
  assert.equal(await sessionReady(new Response(null, { status: 500 }), false), false);
  assert.equal(await sessionReady(new Response(null, { status: 401 }), false), false);
  const signedOut = new Response(null, { status: 401, headers: { 'WWW-Authenticate': 'Bearer' } });
  assert.equal(await sessionReady(signedOut, false), true);
  assert.equal(await sessionReady(signedOut, true), false);
  assert.equal(await sessionReady(Response.json({ offline: true, user_id: 'offline:operator' }), true), true);
  assert.equal(await sessionReady(Response.json({ offline: false, user_id: 'example' }), true), false);
  let tries = 0;
  await waitUntilReady('Backend', async () => ++tries > 1, { timeout: 250, interval: 0 });
  await assert.rejects(waitUntilReady('Backend', async () => false, { timeout: 10, interval: 1 }), /did not become ready/);
});

test('launcher exits on an occupied port without stopping the existing listener', async t => {
  const server = createServer(socket => socket.end());
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const port = server.address().port;
  const child = spawn(process.execPath, [launcher], {
    env: { ...process.env, PUSHER_DEV_BACKEND_PORT: String(port), PUSHER_DEV_FRONTEND_PORT: port === 3000 ? '3001' : '3000' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let error = '';
  child.stderr.setEncoding('utf8').on('data', data => { error += data; });
  const [code] = await once(child, 'close');
  assert.equal(code, 1);
  assert.match(error, /Backend cannot bind.*EADDRINUSE/);
  assert.equal(server.listening, true);
});

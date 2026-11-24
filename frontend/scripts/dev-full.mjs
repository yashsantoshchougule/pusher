import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { isAbsolute, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const root = fileURLToPath(new URL('../../', import.meta.url));
const host = '127.0.0.1';

function portFrom(value, fallback, name) {
  const port = Number(value ?? fallback);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`${name} must be a port between 1 and 65535.`);
  }
  return port;
}

export function localOptions(args, env) {
  if (args.some(arg => arg !== '--offline')) throw new Error('Supported argument: --offline');
  const frontendPort = portFrom(env.PUSHER_DEV_FRONTEND_PORT, 3000, 'PUSHER_DEV_FRONTEND_PORT');
  const backendPort = portFrom(env.PUSHER_DEV_BACKEND_PORT, 8000, 'PUSHER_DEV_BACKEND_PORT');
  if (frontendPort === backendPort) throw new Error('The frontend and backend need different ports.');
  return { frontendPort, backendPort, offline: args.includes('--offline') };
}

async function requireFreePort(port, name) {
  await new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', error => reject(new Error(`${name} cannot bind to ${host}:${port} (${error.code}).`)));
    server.listen(port, host, () => server.close(resolve));
  });
}

export function findPython({ directory, platform, env, probe }) {
  const windows = platform === 'win32';
  const shim = join(directory, windows ? 'Scripts' : 'bin', windows ? 'python.exe' : 'python');
  const cfgPath = join(directory, 'pyvenv.cfg');
  if (!existsSync(cfgPath)) throw new Error('Python environment missing. Run uv sync --locked from the project root.');
  const cfg = readFileSync(cfgPath, 'utf8');
  const readSetting = key => cfg.match(new RegExp(`^${key}\\s*=\\s*(.+)$`, 'm'))?.[1].trim();
  const version = readSetting('version_info') ?? readSetting('version');
  const matches = result => !result.error && result.status === 0 && version &&
    (result.stdout.trim() === version || (version === '3.12' && /^3\.12\.\d+$/.test(result.stdout.trim())));
  const interpreter = probe(shim, env);
  if (matches(interpreter)) return { executable: shim, env };
  const home = readSetting('home');
  if (windows && (interpreter.error || interpreter.status === 126) && home && isAbsolute(home)) {
    const base = join(home, 'python.exe');
    const fallbackEnv = { ...env, PYTHONPATH: join(directory, 'Lib', 'site-packages') };
    if (matches(probe(base, fallbackEnv))) return { executable: base, env: fallbackEnv };
  }
  throw new Error('The project Python environment could not start or import its dependencies. Use a permitted Python 3.12 and run uv sync --locked.');
}

export async function sessionReady(response, offline) {
  if (!offline) {
    return response.status === 401 && /^Bearer(?:\s|$)/i.test(response.headers.get('www-authenticate') ?? '');
  }
  if (response.status !== 200) return false;
  const data = await response.json();
  return data.offline === true && data.user_id === 'offline:operator';
}

export async function waitUntilReady(name, probe, { signal, timeout = 20000, interval = 150 } = {}) {
  const deadline = Date.now() + timeout;
  do {
    signal?.throwIfAborted();
    try {
      if (await probe()) return;
    } catch {
      // A starting service can refuse the connection or return incomplete data.
    }
    await delay(interval, undefined, { signal });
  } while (Date.now() < deadline);
  throw new Error(`${name} did not become ready within ${timeout / 1000}s.`);
}

async function run() {
  const { frontendPort, backendPort, offline } = localOptions(process.argv.slice(2), process.env);
  const vite = join(frontend, 'node_modules', 'vite', 'bin', 'vite.js');
  if (!existsSync(vite)) throw new Error('Frontend dependencies missing. Run npm ci --prefix frontend.');
  await requireFreePort(backendPort, 'Backend');
  await requireFreePort(frontendPort, 'Frontend');

  const backendEnv = { ...process.env, HOST: host, PORT: String(backendPort), PUSHER_OFFLINE_DEV: String(offline) };
  if (offline) backendEnv.PUSHER_MODE = 'local_dev';
  const python = findPython({
    directory: join(root, '.venv'), platform: process.platform, env: backendEnv,
    probe: (executable, env) => spawnSync(executable, [
      '-s', '-c', 'import platform, uvicorn, fastapi; print(platform.python_version())',
    ], { cwd: root, env, encoding: 'utf8', timeout: 10000 }),
  });

  const lifecycle = new AbortController();
  const children = [];
  let closing = false;
  let finish;
  const finished = new Promise(resolve => { finish = resolve; });
  function stop(error) {
    if (closing) return;
    closing = true;
    if (error) {
      console.error(error.message);
      process.exitCode = 1;
    }
    lifecycle.abort();
    for (const { child } of children) {
      if (child.pid && child.exitCode === null && child.signalCode === null) child.kill();
    }
    finish();
  }
  function start(name, executable, args, options) {
    const child = spawn(executable, args, { ...options, stdio: 'inherit', windowsHide: true });
    children.push({ child, closed: new Promise(resolve => child.once('close', resolve)) });
    child.once('error', error => stop(new Error(`${name} could not start: ${error.code ?? error.message}`)));
    child.once('exit', (code, signal) => stop(new Error(`${name} stopped (${signal ?? code}).`)));
  }
  const onStop = () => stop();
  process.on('SIGINT', onStop);
  process.on('SIGTERM', onStop);
  const backend = `http://${host}:${backendPort}`;
  const ui = `http://${host}:${frontendPort}`;
  const get = url => fetch(url, { redirect: 'error', signal: AbortSignal.any([lifecycle.signal, AbortSignal.timeout(1000)]) });
  try {
    start('Backend', python.executable, [
      '-s', '-m', 'uvicorn', 'backend.main:app', '--host', host, '--port', String(backendPort), '--no-access-log',
    ], { cwd: root, env: python.env });
    await waitUntilReady('Pusher backend', async () => {
      const response = await get(backend);
      return response.ok && (await response.json()).service === 'Pusher Backend Engine';
    }, { signal: lifecycle.signal });
    start('Frontend', process.execPath, [vite, '--host', host, '--port', String(frontendPort), '--strictPort', '--logLevel', 'warn'], {
      cwd: frontend, env: { ...process.env, PUSHER_DEV_API_ORIGIN: backend },
    });
    await waitUntilReady('Frontend and session proxy', async () => {
      const page = await get(ui);
      return page.ok && (await page.text()).includes('/src/main.jsx') &&
        await sessionReady(await get(ui + '/api/session'), offline);
    }, { signal: lifecycle.signal });
    lifecycle.signal.throwIfAborted();
    console.log(`Pusher ready at ${ui}/`);
    await finished;
  } catch (error) {
    stop(error);
  } finally {
    const shutdown = setTimeout(() => {
      for (const { child } of children) {
        if (child.pid && child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
      }
    }, 3000);
    try {
      await Promise.all(children.map(({ closed }) => closed));
    } finally {
      clearTimeout(shutdown);
      process.off('SIGINT', onStop);
      process.off('SIGTERM', onStop);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  run().catch(error => {
    console.error(`Pusher startup failed: ${error.message}`);
    process.exitCode = 1;
  });
}

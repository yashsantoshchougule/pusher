import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { createServer as createViteServer } from '../../../frontend/node_modules/vite/dist/node/index.js';

test('Vite proxies the load start, WAF status, and telemetry upgrade', { timeout: 8000 }, async () => {
  const requests = [];
  const upgraded = [];
  const sockets = new Set();
  const backend = createServer((request, response) => {
    requests.push({ method: request.method, path: request.url, device: request.headers['x-pusher-device-id'] });
    request.resume();
    response.setHeader('Content-Type', 'application/json');
    response.end('{"ok":true}');
  });
  backend.on('connection', (socket) => {
    sockets.add(socket);
    socket.once('close', () => sockets.delete(socket));
  });
  backend.on('upgrade', (request, socket) => {
    upgraded.push(request.url);
    const key = request.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
    const accepted = createHash('sha1').update(key).digest('base64');
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accepted + '\r\n\r\n');
  });
  backend.listen(0, '127.0.0.1');
  await once(backend, 'listening');
  const prior = process.env.PUSHER_DEV_API_ORIGIN;
  let vite;
  try {
    process.env.PUSHER_DEV_API_ORIGIN = 'http://127.0.0.1:' + backend.address().port;
    const root = fileURLToPath(new URL('../../../frontend/', import.meta.url));
    vite = await createViteServer({
      root,
      server: { port: 0, hmr: false, watch: null },
      optimizeDeps: { noDiscovery: true },
      plugins: [{
        name: 'skip-prebundling-for-proxy-test',
        configResolved(config) {
          // The React plugin adds dependencies even when discovery is disabled.
          config.optimizeDeps.include = [];
        },
      }],
    });
    await vite.listen();
    const port = vite.httpServer.address().port;
    const base = 'http://127.0.0.1:' + port;
    const index = await fetch(base);
    assert.equal(index.status, 200);
    assert.match(await index.text(), /\/src\/main\.jsx/);
    const start = await fetch(base + '/api/load/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Pusher-Device-ID': 'proxy-fixture' },
      body: '{}',
    });
    assert.equal(start.status, 200);
    assert.equal((await fetch(base + '/api/target/status')).status, 200);
    const ws = new WebSocket('ws://127.0.0.1:' + port + '/api/load/ws');
    await once(ws, 'open', { signal: AbortSignal.timeout(3000) });
    assert.deepEqual(upgraded, ['/api/load/ws']);
    assert.deepEqual(requests, [
      { method: 'POST', path: '/api/load/start', device: 'proxy-fixture' },
      { method: 'GET', path: '/api/target/status', device: undefined },
    ]);
  } finally {
    if (prior === undefined) delete process.env.PUSHER_DEV_API_ORIGIN;
    else process.env.PUSHER_DEV_API_ORIGIN = prior;
    for (const socket of sockets) socket.destroy();
    await vite?.close();
    await new Promise((resolve) => backend.close(resolve));
  }
});

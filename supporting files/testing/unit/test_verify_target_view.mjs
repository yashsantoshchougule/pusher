import assert from 'node:assert/strict';
import test from 'node:test';
import { renderView } from './react_view_fixture.mjs';

function renderTarget(overrides = {}) {
  return renderView('VerifyTargetView', {
    targetUrl: 'https://example.invalid/',
    ssrfCheck: { valid: true },
    guardToken: 'PG-FIXTURE',
    isVerified: true,
    isGuardVerified: true,
    guardTimerSeconds: 600,
    formatTimer: () => '00:10:00',
    setTargetUrl() {},
    ...overrides,
  });
}

test('the Verify Target page exposes only deliberate manual revocation', () => {
  const markup = renderTarget();
  assert.match(markup, /KILL ID/);
  assert.doesNotMatch(markup, /TEST CROSS-DEVICE BLOCK/);
  assert.doesNotMatch(markup, /Generating a new token burns the previous ID/);
});

test('local sandbox shows direct verification and keeps manual revocation', () => {
  const markup = renderTarget({
    sandboxMode: true,
    sandboxTargetUrl: 'http://127.0.0.1:8123/api/sandbox/target',
  });
  assert.ok(markup.includes('VERIFY SANDBOX'));
  assert.ok(markup.includes('KILL ID (PERMANENT)'));
  assert.ok(!markup.includes('Install Ownership Guard'));
  assert.ok(!markup.includes('Cryptographic Handshake'));
  assert.ok(!markup.includes('DAILY GUARD QUOTA'));
});

test('production keeps the live Guard flow and hides sandbox mode', () => {
  const markup = renderTarget({ sandboxTargetUrl: null });
  assert.ok(markup.includes('Install Ownership Guard'));
  assert.ok(markup.includes('Cryptographic Handshake'));
  assert.ok(!markup.includes('Sandbox Simulation Target'));
});

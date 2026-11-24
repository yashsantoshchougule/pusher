import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import {
  closeRecoverySession, requestPasswordReset, resetRequestMessage, trackRecoverySession, updateRecoveryPassword,
} from '../../../frontend/src/lib/passwordRecovery.js';

const frontend = new URL('../../../frontend/', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
const React = require('react');
const { Children, createElement, isValidElement } = React;
const { renderToStaticMarkup } = require('react-dom/server');
const { transformSync } = require('esbuild');

function view(path, requireModule = require) {
  const source = readFileSync(new URL(path, frontend), 'utf8');
  const { code } = transformSync(source, { loader: 'jsx', format: 'cjs' });
  const module = { exports: {} };
  new Function('module', 'require', code)(module, requireModule);
  return module.exports.default;
}

function providerFixture() {
  const calls = [];
  const user = { id: 'fixture-user' };
  let emit;
  const auth = {
    onAuthStateChange(callback) { emit = callback; },
    async getUser() { return { data: { user }, error: null }; },
    async updateUser(input) { calls.push(['update', input]); return { error: null }; },
    async signOut(input) { calls.push(['signout', input]); emit('SIGNED_OUT', null); return { error: null }; },
  };
  const tracker = trackRecoverySession(auth);
  return { auth, calls, user, getRecovery: tracker.getSnapshot, emit };
}

test('reset uses the exact local callback and does not disclose an unknown account', async () => {
  for (const error of [null, { code: 'user_not_found' }]) {
    const auth = { async resetPasswordForEmail(email, options) {
      assert.equal(email, 'operator@example.invalid');
      assert.deepEqual(options, { redirectTo: 'http://127.0.0.1:3000/auth/recovery' });
      return { error };
    } };
    assert.equal(await requestPasswordReset(auth, ' operator@example.invalid ', 'http://127.0.0.1:3000'), resetRequestMessage);
  }
  await assert.rejects(requestPasswordReset({
    resetPasswordForEmail: async () => ({ error: { code: 'service_unavailable', message: 'Private provider details' } }),
  }, 'operator@example.invalid', 'https://fixture.example.invalid'), /^Error: The reset request could not be sent/);
  await assert.rejects(requestPasswordReset({
    resetPasswordForEmail: async () => { throw new Error('Private transport details'); },
  }, 'operator@example.invalid', 'https://fixture.example.invalid'), /^Error: The reset request could not be sent/);
});

test('ordinary, expired, and reused callback sessions do not permit updating a password', async () => {
  for (const initialSession of [null, { user: { id: 'existing-account' } }]) {
    const { auth, calls, emit, getRecovery } = providerFixture();
    emit('INITIAL_SESSION', initialSession);
    if (initialSession) emit('SIGNED_IN', initialSession);
    assert.equal(getRecovery().status, 'invalid');
    await assert.rejects(updateRecoveryPassword(auth, getRecovery, 'valid-fixture', 'valid-fixture'), /new password reset link/);
    await closeRecoverySession(auth, getRecovery);
    assert.deepEqual(calls, []);
  }
});

test('verified recovery checks the password and identity, updates once and closes the local session', async () => {
  const { auth, calls, emit, getRecovery, user } = providerFixture();
  emit('INITIAL_SESSION', null);
  emit('PASSWORD_RECOVERY', { user });
  await assert.rejects(updateRecoveryPassword(auth, getRecovery, 'short', 'short'), /at least 8/);
  await assert.rejects(updateRecoveryPassword(auth, getRecovery, 'valid-fixture', 'other-fixture'), /do not match/);
  await updateRecoveryPassword(auth, getRecovery, 'valid-fixture', 'valid-fixture');
  await closeRecoverySession(auth, getRecovery);
  assert.deepEqual(calls, [['update', { password: 'valid-fixture' }], ['signout', { scope: 'local' }]]);
  assert.equal(getRecovery().status, 'invalid');
});

test('sign-out or a replaced session invalidates an interrupted recovery', async () => {
  for (const otherEvent of ['SIGNED_OUT', 'SIGNED_IN']) {
    const { auth, calls, emit, getRecovery, user } = providerFixture();
    emit('PASSWORD_RECOVERY', { user });
    auth.getUser = async () => {
      emit(otherEvent, otherEvent === 'SIGNED_OUT' ? null : { user: { id: 'another-user' } });
      return { data: { user } };
    };
    await assert.rejects(updateRecoveryPassword(auth, getRecovery, 'valid-fixture', 'valid-fixture'), /no longer valid/);
    assert.deepEqual(calls, []);
  }
});

test('signup starts with unchecked Terms and blocks all signup buttons until accepted', () => {
  const AuthFormPanel = view('src/components/auth/AuthFormPanel.jsx');
  const signup = renderToStaticMarkup(createElement(AuthFormPanel, { mode: 'signup' }));
  const checkbox = signup.match(/<input[^>]*type="checkbox"[^>]*>/)?.[0];
  assert.ok(checkbox);
  assert.doesNotMatch(checkbox, /checked/);
  assert.match(checkbox, /aria-label="I agree to the Terms and Conditions"/);
  assert.match(signup, /href="\/terms"/);
  assert.equal((signup.match(/<button[^>]+disabled=""/g) ?? []).length, 3);
  const login = renderToStaticMarkup(createElement(AuthFormPanel, { mode: 'login' }));
  assert.match(login, /href="\/auth\/forgot"/);
  assert.doesNotMatch(login, /disabled=""/);
});

test('Terms page displays the four approved sections', () => {
  const TermsPage = view('src/pages/TermsPage.jsx');
  const terms = renderToStaticMarkup(createElement(TermsPage));
  assert.doesNotMatch(terms, /Draft for owner review|not approved for release/i);
  const sections = Array.from(terms.matchAll(/<h2[^>]*>([^<]+)<\/h2><p>([^<]+)<\/p>/g), match => match.slice(1));
  assert.deepEqual(sections, [
    ['Authorized use', 'Use Pusher only on systems you own or have explicit written permission to test. Stay within the authorized targets, time windows, traffic limits, and credentials.'],
    ['Running tests', 'Set a traffic budget appropriate for the target. Monitor the run and stop it if it causes unexpected errors or affects other users. Follow the target operator’s rules for staging and production.'],
    ['Accounts and test data', 'Keep account and target credentials private. Use disposable test data where possible, and review exports before sharing them. Pusher stores profiles, configuration, and run reports in its backend database.'],
    ['Interpreting results', 'Results describe the measured workload and environment. They can vary with the host, network, configuration, and target behavior.'],
  ]);
});

test('changing signup consent governs all three actions and the email submit handler', () => {
  const state = [];
  let nextHook = 0;
  const AuthFormPanel = view('src/components/auth/AuthFormPanel.jsx', name => name === 'react' ? {
    ...React,
    useState(initial) {
      const index = nextHook++;
      state[index] ??= initial;
      return [state[index], value => { state[index] = value; }];
    },
  } : require(name));

  const descendants = element => [element, ...Children.toArray(element.props.children)
    .filter(isValidElement).flatMap(descendants)];
  const calls = [];
  const onGoogleClick = () => calls.push('google');
  const onGitHubClick = () => calls.push('github');

  for (const [accepted, nextAccepted] of [[false, true], [true, false], [false, false]]) {
    nextHook = 0;
    const nodes = descendants(AuthFormPanel({
      mode: 'signup', onSubmit: () => calls.push('email'), onGoogleClick, onGitHubClick,
    }));
    const checkbox = nodes.find(node => node.type === 'input' && node.props.type === 'checkbox');
    const form = nodes.find(node => node.type === 'form');
    const actions = nodes.filter(node => node.type === 'button' && (
      node.props.type === 'submit' || [onGoogleClick, onGitHubClick].includes(node.props.onClick)
    ));

    assert.equal(checkbox.props.checked, accepted);
    assert.equal(actions.length, 3);
    assert.ok(actions.every(button => button.props.disabled === !accepted));

    form.props.onSubmit({ preventDefault() {} });
    for (const button of actions) {
      if (!button.props.disabled && button.props.type !== 'submit') button.props.onClick();
    }
    checkbox.props.onChange({ target: { checked: nextAccepted } });
  }
  assert.deepEqual(calls, ['email', 'google', 'github']);
});

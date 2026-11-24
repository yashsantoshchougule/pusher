import assert from 'node:assert/strict';
import test from 'node:test';
import { restoreTargetQuery, targetTemplate } from '../../../frontend/src/lib/targetInput.js';

test('target status preserves a runtime query only for the same Guard and endpoint', () => {
  const template = 'https://example.invalid/orders';
  const draft = template + '?a=local%2Bvalue#section';
  assert.equal(targetTemplate(draft), template);
  assert.equal(restoreTargetQuery(template, draft, true), template + '?a=local%2Bvalue');
  assert.equal(restoreTargetQuery(template, draft, false), template);
  assert.equal(restoreTargetQuery(template, '', true), template);
  assert.equal(restoreTargetQuery(template, draft.replace('/orders', '/other'), true), template);
});

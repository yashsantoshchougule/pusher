import assert from 'node:assert/strict';
import test from 'node:test';
import { renderView } from './react_view_fixture.mjs';

const render = (dryRunResults) => renderView('ApiBuilderView', { dryRunResults, journeySteps: [] });
const step = { step_id: 'fixture', method: 'GET', path: '/orders', status_code: 200, passed: true, latency_ms: 0 };

test('dry-run summary uses the actual duration and variable names without values', () => {
  const markup = render({
    all_passed: true, total_steps: 1, total_duration_ms: 0,
    extracted_context: { token: 'synthetic-secret' }, results: [step],
  });
  assert.match(markup, /Total Duration:<\/span> 0 ms/);
  assert.match(markup, /Extracted Variables:<\/span> \{\{token\}\}/);
  assert.match(markup, /GET \/orders/);
  assert.doesNotMatch(markup, /synthetic-secret/);
});

test('empty variables and saved step arrays render without fabricated totals', () => {
  const markup = render({
    all_passed: true, total_steps: 1, total_duration_ms: 12.4,
    results: [step], extracted_context: {},
  });
  assert.match(markup, /Total Duration:<\/span> 12\.4 ms/);
  assert.match(markup, /Extracted Variables:<\/span> None/);
  const saved = render([step]);
  assert.match(saved, /Last Saved Dry-Run Steps/);
  assert.doesNotMatch(saved, /Total Duration:|CHAIN FAILED/);
  assert.doesNotMatch(render([]), /Dry-Run Execution Log|Last Saved Dry-Run Steps/);
});

test('cancelled outcomes and step errors have distinct readable labels', () => {
  const markup = render({
    status: 'cancelled', all_passed: false, total_steps: 2, total_duration_ms: 10000,
    results: [{ ...step, passed: false, status_code: 0, error: 'The request did not respond.' }],
  });
  assert.match(markup, /DRY RUN CANCELLED/);
  assert.match(markup, /10000 ms/);
  assert.match(markup, /No response/);
  assert.match(markup, /The request did not respond/);
  assert.doesNotMatch(markup, /CHAIN FAILED|HTTP 0/);
});

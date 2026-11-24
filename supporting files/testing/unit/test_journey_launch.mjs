import assert from 'node:assert/strict';
import test from 'node:test';
import { restoreJourneyInputs, saveAndLaunchJourney } from '../../../frontend/src/lib/journeyLaunch.js';

test('a failed save does not launch anything', async () => {
  await saveAndLaunchJourney(async () => null, () => assert.fail('unexpected launch'));
});

test('launch uses the acknowledged steps and flag from the save response', async () => {
  const saved = { use_journey: true, steps: [{ path: '/confirmed' }] };
  let launched;
  await saveAndLaunchJourney(async (enabled) => {
    assert.equal(enabled, true);
    return saved;
  }, async (journey) => { launched = journey; });
  assert.equal(launched, saved);
});

test('save and launch keep private inputs in the tab and use the saved metadata', async () => {
  const submitted = [{ path: '/draft?query=private', headers: { Authorization: 'Bearer test' }, body: false }];
  const persisted = [{ path: '/saved', headers: {}, body: null, requires_body: true }];
  await saveAndLaunchJourney(
    async () => ({ use_journey: true, steps: restoreJourneyInputs(persisted, submitted) }),
    async ({ steps: [step] }) => {
      assert.equal(step.path, '/saved?query=private');
      assert.equal(step.headers.Authorization, 'Bearer test');
      assert.equal(step.body, false);
    },
  );
  assert.deepEqual(persisted[0].headers, {});
  assert.equal(persisted[0].path, '/saved');
  assert.equal(persisted[0].body, null);
});

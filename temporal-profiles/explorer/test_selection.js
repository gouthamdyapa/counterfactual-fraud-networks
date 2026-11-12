/* Focused behavior checks using the packaged, exhaustively checked examples. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({ window: {}, console });
vm.runInContext(fs.readFileSync(path.join(__dirname, 'data.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8'), context);
const data = context.window.TEMPORAL_EXPLORER_DATA;
const api = context.window.TemporalExplorer;
assert.equal(typeof api.selectTarget, 'function');
assert.equal(typeof api.countWalks, 'function');
let selectionChecks = 0;

function choose(id, minW2, mode, target, budget = null) {
  const example = data.cases.find(item => item.id === id);
  assert.ok(example, id);
  const quota = example.quotas.find(item => item.min_w2 === minW2);
  assert.ok(quota, `${id} quota ${minW2}`);
  selectionChecks += 1;
  return api.selectTarget(quota, { mode, target, budget });
}

function checkSuccess(result, w2, w3, cost, deleted) {
  assert.equal(result.status, 'success');
  assert.equal(result.profile.w2, w2);
  assert.equal(result.profile.w3, w3);
  assert.equal(result.profile.total_cost, cost);
  assert.equal(Array.from(result.profile.deleted_ids).sort().join('|'), deleted.slice().sort().join('|'));
}

checkSuccess(choose('nonmonotone', 2, 'exact', 2), 2, 2, 1, ['a_late']);
checkSuccess(choose('nonmonotone', 2, 'upper', 2), 2, 1, 1, ['a_early']);
checkSuccess(choose('weighted_a', 1, 'exact', 1), 1, 1, 1, ['a_late_cheap']);
assert.equal(choose('weighted_c', 2, 'exact', 3).status, 'unattainable');
checkSuccess(choose('weighted_c', 2, 'upper', 3, 1), 2, 2, 1, ['c_second_cheap']);
const over = choose('weighted_c', 2, 'upper', 3, 0);
assert.equal(over.status, 'over_budget');
assert.equal(over.minimumCost, 1);
assert.equal(choose('weighted_c', 3, 'upper', 3).status, 'unattainable');
checkSuccess(choose('weighted_c', 0, 'exact', 0), 0, 0, 101, ['c_first_expensive', 'c_second_cheap']);
assert.equal(choose('forced_baseline', 0, 'exact', 0, 6).status, 'over_budget');
checkSuccess(choose('forced_baseline', 0, 'exact', 0, 7), 0, 0, 7, ['b_forced']);
assert.equal(choose('forced_baseline', 1, 'exact', 0).status, 'quota_infeasible');
const illustration = choose('illustration', 5, 'exact', 1);
assert.equal(illustration.status, 'success');
assert.equal(illustration.profile.w3, 1);
assert.ok(illustration.profile.w2 >= 5);
assert.equal(illustration.profile.w2, 10);
assert.equal(illustration.profile.total_cost, 1);
assert.equal(Array.from(illustration.profile.deleted_ids).join('|'), 'A2');
checkSuccess(choose('illustration', 5, 'exact', 0), 10, 0, 2, ['A2', 'A4']);
assert.equal(choose('nonmonotone', 2, 'exact', -1).status, 'invalid');
assert.equal(choose('nonmonotone', 2, 'exact', 1.5).status, 'invalid');
assert.equal(choose('nonmonotone', 2, 'exact', 2, -1).status, 'invalid');
assert.equal(choose('nonmonotone', 2, 'exact', 2, 0.5).status, 'invalid');

let witnessChecks = 0;
for (const example of data.cases) {
  const original = api.countWalks(example.events, example.root);
  assert.equal(original.w2, example.original.w2);
  assert.equal(original.w3, example.original.w3);
  for (const quota of example.quotas) {
    for (const profile of quota.profiles) {
      const deleted = new Set(profile.deleted_ids);
      const counts = api.countWalks(example.events.filter(event => !deleted.has(event.id)), example.root);
      assert.equal(counts.w2, profile.w2, `${example.id}: W2`);
      assert.equal(counts.w3, profile.w3, `${example.id}: W3`);
      witnessChecks += 1;
    }
  }
}

const ties = api.countWalks([
  { id: 'a', source: 'leaf', target: 'v', time: 0 },
  { id: 'b', source: 'v', target: 'u', time: 0 },
  { id: 'c', source: 'u', target: 'z', time: 1 }
], 'z');
assert.equal(ties.w2, 1);
assert.equal(ties.w3, 0, 'Equal timestamps must not extend a three-event walk');
const wrongRoot = api.countWalks([
  { id: 'a', source: 'leaf', target: 'v', time: 0 },
  { id: 'b', source: 'v', target: 'u', time: 1 }
], 'z');
assert.equal(wrongRoot.w2, 0, 'Walks must end at the designated root');
assert.equal(wrongRoot.w3, 0);

console.log(`Explorer selection checks: PASS (${selectionChecks} scenarios; ${witnessChecks} witness counts; strict-time/root sentinels)`);

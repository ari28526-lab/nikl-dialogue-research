'use strict';

const fs = require('fs');
const vm = require('vm');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('usage: node test_pv_reviewer_v2_1_runtime.js HTML_PATH');
const html = fs.readFileSync(htmlPath, 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
assert(match, 'inline script not found');

const sandbox = {
  console,
  Date,
  Math,
  JSON,
  Set,
  Object,
  Array,
  String,
  Error,
  Number,
  globalThis: null,
  crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000021' },
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(match[1], sandbox, { filename: htmlPath });
const api = sandbox.PV_REVIEWER_V2_TEST_API;
assert(api, 'test API was not exposed');

assert(api.SAMPLES.length === 14, `samples=${api.SAMPLES.length}`);
assert(api.BASE_HISTORY.length === 15, `base history=${api.BASE_HISTORY.length}`);
assert(Object.keys(api.latestByEvent(api.BASE_HISTORY)).length === 14, 'base latest view is not 14');
assert(api.SAMPLES.every(row => Array.isArray(row.target_word_indices) && row.target_word_indices.length), 'highlight metadata missing');
assert(api.SAMPLES.reduce((sum, row) => sum + row.target_word_indices.length, 0) === 15, 'highlight token count is not 15');

for (const sample of api.SAMPLES) {
  const rendered = api.highlightActiveForm(sample);
  const marks = (rendered.match(/<mark /g) || []).length;
  assert(marks === sample.target_word_indices.length, `${sample.pv_id}: mark count=${marks}`);
  for (const index of sample.target_word_indices) {
    assert(rendered.includes(`data-word-index="${index}"`), `${sample.pv_id}: word index ${index} not marked`);
  }
}
const pv0151 = api.SAMPLES.find(row => row.pv_id === 'PV0151');
const pv0151Html = api.highlightActiveForm(pv0151);
assert(pv0151Html.includes('>떡</mark>'), 'PV0151 first target is not highlighted');
assert(pv0151Html.includes('>벌어질</mark>'), 'PV0151 second target is not highlighted');
const escaped = api.highlightActiveForm({ active_form: '<표적> 나머지', target_word_indices: [1] });
assert(escaped.includes('&lt;표적&gt;') && !escaped.includes('><표적></mark>'), 'highlight renderer did not escape HTML');

assert(api.morphStatusText('direct_from_match_evidence').includes('직접 표시'), 'direct morph status translation failed');
assert(api.morphStatusText('unavailable_form_tagged_count_mismatch_zero_drop').includes('삭제 없이 유지'), 'zero-drop translation failed');
assert(api.morphBoundaryLabel('orth_contraction_probe') === '축약 음절', 'HIA label failed');
assert(api.morphBoundaryLabel('boundary') === '경계', 'ordinary boundary label failed');

let confirmCalls = 0;
assert(api.canDiscardDirty(false, () => { confirmCalls += 1; return false; }) === true, 'clean navigation failed');
assert(confirmCalls === 0, 'clean navigation called confirm');
assert(api.canDiscardDirty(true, () => false) === false, 'dirty navigation cancellation failed');
assert(api.canDiscardDirty(true, () => true) === true, 'dirty navigation discard failed');

const newer = { review_event_id: 'event', reviewed_at: '2026-08-22T13:00:00+09:00', value: 'newer' };
const older = { review_event_id: 'event', reviewed_at: '2026-08-22T12:00:00+09:00', value: 'older' };
assert(api.latestByEvent([newer, older]).event.value === 'newer', 'reviewed_at ordering failed');
const equalA = { review_event_id: 'equal', reviewed_at: '2026-08-22T13:00:00+09:00', value: 'a' };
const equalB = { review_event_id: 'equal', reviewed_at: '2026-08-22T13:00:00+09:00', value: 'b' };
assert(api.latestByEvent([equalA, equalB]).equal.value === 'b', 'equal-time array tie-break failed');
const invalidA = { review_event_id: 'invalid', reviewed_at: '', value: 'a' };
const invalidB = { review_event_id: 'invalid', value: 'b' };
assert(api.latestByEvent([invalidA, invalidB]).invalid.value === 'b', 'invalid-time fallback failed');

assert(api.filterIds('', 'all').length === 14, 'all filter failed');
assert(api.filterIds('', 'core').length === 10, 'core filter failed');
assert(api.filterIds('', 'exploratory').length === 4, 'exploratory filter failed');
assert(api.filterIds('PV0163', 'all').length === 1, 'candidate search failed');

const exported = api.toJsonl(api.BASE_HISTORY);
assert(api.parseJsonl(exported).length === 15, 'base export/import failed');
for (const input of ['', '{not json}\n', JSON.stringify({ review_event_id: 'unknown' }) + '\n']) {
  let failed = false;
  try { api.parseJsonl(input); } catch (_error) { failed = true; }
  assert(failed, 'invalid import did not fail');
}

console.log('PV_REVIEWER_V2_1_RUNTIME_OK');

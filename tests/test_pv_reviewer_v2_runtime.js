'use strict';

const fs = require('fs');
const vm = require('vm');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('usage: node test_pv_reviewer_v2_runtime.js HTML_PATH');
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
  globalThis: null,
  crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000001' },
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(match[1], sandbox, { filename: htmlPath });
const api = sandbox.PV_REVIEWER_V2_TEST_API;
assert(api, 'test API was not exposed');

assert(api.SAMPLES.length === 14, `samples=${api.SAMPLES.length}`);
assert(new Set(api.SAMPLES.map(row => row.pv_id)).size === 14, 'pv_id values are not unique');
assert(api.BASE_HISTORY.length === 15, `base history=${api.BASE_HISTORY.length}`);
assert(Object.keys(api.latestByEvent(api.BASE_HISTORY)).length === 14, 'latest view is not 14');

const fingerprints = api.BASE_HISTORY.map(api.semanticFingerprint);
assert(fingerprints.length - new Set(fingerprints).size === 1, 'semantic duplicate count is not one');
assert(api.duplicateCount(api.BASE_HISTORY, api.BASE_HISTORY) === 15, 'duplicate import accounting failed');

assert(api.filterIds('', 'all').length === 14, 'all filter failed');
assert(api.filterIds('', 'core').length === 10, 'core filter failed');
assert(api.filterIds('', 'exploratory').length === 4, 'exploratory filter failed');
assert(api.filterIds('PV0163', 'all').length === 1, 'ID search failed');
assert(api.filterIds('2025', 'all').length === 7, 'year search failed');

const baseText = api.toJsonl(api.BASE_HISTORY);
assert(api.parseJsonl(baseText).length === 15, 'valid import failed');
for (const [label, input] of [
  ['empty', ''],
  ['malformed', '{not json}\n'],
  ['unknown event', JSON.stringify({ review_event_id: 'unknown' }) + '\n'],
  ['wrong batch', JSON.stringify({
    review_event_id: api.SAMPLES[0].review_event_id,
    ipad_batch: 'another_batch',
  }) + '\n'],
]) {
  let failed = false;
  try { api.parseJsonl(input); } catch (_error) { failed = true; }
  assert(failed, `${label} import did not fail`);
}

const sample = api.SAMPLES.find(row => row.pv_id === 'PV0001');
assert(sample, 'PV0001 missing');
const revision = api.makeRevision(
  {
    review_event_id: sample.review_event_id,
    pv_id: sample.pv_id,
    phenomenon_code: sample.phenomenon_code,
    phenomenon_label: sample.phenomenon_label,
    pv_query_id: sample.pv_query_id,
    environment_scope: sample.environment_scope,
    year: String(sample.year),
    utt_id: sample.utt_id,
    occurrence_ref: sample.occurrence_ref,
    priority_tier: sample.priority_tier,
    target_display_status: sample.target_display_status,
    morph_display_status: sample.morph_display_status,
  },
  {
    listened: true,
    heard_form_free: '시험',
    heard_variant_tags: '경음, 기타',
    judgement_confidence: 'unjudged',
    overlap_impression: 'not_checked',
  },
  api.BASE_HISTORY,
  new Set(['pm2', 'dialogue-panel'])
);
assert(revision.schema_version === 'pv_reviewer_event.v2', 'revision schema mismatch');
assert(revision.revision_seq === 2, `revision sequence=${revision.revision_seq}`);
assert(revision.supersedes_event_uuid, 'supersedes identity missing');
assert(revision.record_role === 'exploratory_pv_only_not_formal_realization_ledger', 'record role mismatch');
assert(JSON.parse(revision.heard_variant_tags_json).length === 2, 'variant tag encoding failed');
assert(api.parseJsonl(api.toJsonl(api.BASE_HISTORY.concat([revision]))).length === 16, '16-row export failed');

assert(api.LITERATURE.length > 0, 'positive literature payload is empty');
assert(api.LITERATURE.every(row => row.relation !== 'not_found'), 'not_found entered positive literature');
assert(api.LITERATURE.every(row => row.evidence_owner !== 'cited_source'), 'cited source entered positive literature');

console.log('PV_REVIEWER_V2_RUNTIME_OK');

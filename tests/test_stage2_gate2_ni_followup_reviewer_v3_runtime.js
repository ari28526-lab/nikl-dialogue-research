'use strict';

const fs = require('fs');
const vm = require('vm');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('usage: node test_stage2_gate2_ni_followup_reviewer_v3_runtime.js HTML_PATH');
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
  crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000031' },
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(match[1], sandbox, { filename: htmlPath });
const api = sandbox.PV_REVIEWER_V3_TEST_API;
assert(api, 'Gate 2 v3 test API was not exposed');

assert(api.SAMPLES.length === 14, `samples=${api.SAMPLES.length}`);
assert(api.TEXTGRID_ASSETS.length === 14, `assets=${api.TEXTGRID_ASSETS.length}`);
assert(api.BASE_HISTORY.length === 15, `base history=${api.BASE_HISTORY.length}`);
assert(api.TEXTGRID_ASSETS.filter(row => row.gate_method_role === 'ni_method_reference').length === 2, 'NI role count differs');
assert(api.TEXTGRID_ASSETS.filter(row => row.gate_method_role === 'cross_phenomenon_ui_regression_only').length === 12, 'regression role count differs');
assert(api.TEXTGRID_ASSETS.every(row => row.textgrid_asset_status === 'available'), 'real asset availability differs');
assert(api.TEXTGRID_ASSETS.every(row => row.textgrid.tiers.length === 6), 'six-tier projection differs');
assert(api.TEXTGRID_ASSETS.every(row => row.waveform.peaks.length === 320), 'waveform peak count differs');

assert(api.filterGate2Ids('', 'all').length === 14, 'all phenomenon filter failed');
assert(api.filterGate2Ids('', 'NI').length === 2, 'NI filter failed');
assert(api.filterGate2Ids('PV0163', 'all').length === 1, 'exact ID search failed');

const validValues = {
  textgrid_review_need: 'required',
  textgrid_review_reasons_json: JSON.stringify(['boundary', 'target_span']),
  additional_information_requests_json: JSON.stringify([
    { information_key: 'prosodic_boundary_review', requested_reason: 'AP/IP 경계를 확인하기 위해' },
  ]),
  followup_need_confidence: '4',
  followup_note: 'runtime test',
  listened: true,
};
assert(api.validateGate2Values(validValues).ok, 'valid Gate 2 values failed');
assert(!api.validateGate2Values({ ...validValues, followup_need_confidence: '' }).ok, 'missing 1-5 confidence passed');
assert(!api.validateGate2Values({ ...validValues, textgrid_review_reasons_json: '[]' }).ok, 'required without reason passed');
assert(!api.validateGate2Values({ ...validValues, textgrid_review_need: 'not_needed' }).ok, 'not_needed with reasons passed');

const sample = api.SAMPLES.find(row => row.pv_id === 'PV0015');
const asset = api.TEXTGRID_ASSETS.find(row => row.pv_id === 'PV0015');
const meta = {
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
};
const revision = api.makeGate2Revision(meta, validValues, api.BASE_HISTORY, new Set(['pm2', 'textgrid-panel']), asset);
assert(revision.schema_version === 'pv_reviewer_event.v3', 'new revision schema differs');
assert(revision.record_role === 'exploratory_gate2_followup_need_not_formal_realization_ledger', 'record role differs');
assert(revision.textgrid_asset_status === 'available', 'asset status not copied');
assert(revision.manual_task_status === 'not_created', 'manual task was advanced');
assert(revision.followup_need_confidence === '4', '1-5 confidence not retained');
assert(JSON.parse(revision.textgrid_review_reasons_json).length === 2, 'multi-reason roundtrip failed');
assert(JSON.parse(revision.additional_information_requests_json).length === 1, 'information-request roundtrip failed');

const history = api.BASE_HISTORY.concat([revision]);
const coverage = api.reviewCoverage(api.SAMPLES, history, api.TEXTGRID_ASSETS);
assert(coverage.input === 14, 'coverage input differs');
assert(coverage.decision.required === 1 && coverage.decision.not_reviewed === 13, 'decision zero-drop differs');
assert(coverage.asset.available === 14, 'asset zero-drop differs');
assert(Object.values(coverage.decision).reduce((a, b) => a + b, 0) === 14, 'decision axis sum differs');
assert(Object.values(coverage.asset).reduce((a, b) => a + b, 0) === 14, 'asset axis sum differs');
assert(Object.values(coverage.manual).reduce((a, b) => a + b, 0) === 14, 'manual axis sum differs');

const queue = api.buildQueueCandidates(api.SAMPLES, history, api.TEXTGRID_ASSETS);
assert(queue.length === 1, `queue length=${queue.length}`);
assert(queue[0].occurrence_id === sample.occurrence_ref, 'queue exact-ID differs');
assert(queue[0].record_role === 'exploratory_queue_candidate_not_manual_task', 'queue role differs');
assert(queue[0].manual_task_status === 'not_created', 'queue created a formal task');
assert(api.shouldOpenTextGrid(revision, asset), 'required did not request auto-open');
assert(!api.shouldOpenTextGrid({ textgrid_review_need: 'not_needed', manual_task_status: 'not_created' }, asset), 'not_needed auto-opened');

const syntheticAssets = api.TEXTGRID_ASSETS.map(row => ({ ...row }));
syntheticAssets[0].textgrid_asset_status = 'unavailable';
const syntheticCoverage = api.reviewCoverage(api.SAMPLES, api.BASE_HISTORY, syntheticAssets);
assert(syntheticCoverage.asset.unavailable === 1, 'unavailable fixture not retained');
assert(Object.values(syntheticCoverage.asset).reduce((a, b) => a + b, 0) === 14, 'unavailable fixture dropped a row');

const exported = api.toJsonl(history);
assert(api.parseJsonl(exported).length === 16, 'legacy+v3 export/import failed');
let confirmCalls = 0;
assert(api.canDiscardDirty(false, () => { confirmCalls += 1; return false; }), 'clean navigation failed');
assert(confirmCalls === 0, 'clean navigation called confirm');
assert(!api.canDiscardDirty(true, () => false), 'dirty cancel failed');
assert(api.canDiscardDirty(true, () => true), 'dirty discard failed');

console.log('STAGE2_GATE2_NI_REVIEWER_V3_RUNTIME_OK');

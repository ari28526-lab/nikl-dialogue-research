'use strict';

const fs = require('fs');
const vm = require('vm');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('usage: node test_stage2_two_hour_seven_phenomena_reviewer_runtime.js HTML_PATH');
const document = fs.readFileSync(htmlPath, 'utf8');

function embedded(id) {
  const pattern = new RegExp(`<script id="${id}" type="application/json">([\\s\\S]*?)<\\/script>`);
  const match = document.match(pattern);
  assert(match, `embedded JSON missing: ${id}`);
  return JSON.parse(match[1].replace(/<\\\//g, '</'));
}

const mainMatch = document.match(/<script>\s*([\s\S]*?)<\/script>\s*<\/body>/);
assert(mainMatch, 'main reviewer script missing');
new vm.Script(mainMatch[1], { filename: htmlPath });
assert(!/\bconst\s+history\s*=/.test(mainMatch[1]), 'window.history shadowed by const history');
assert(mainMatch[1].includes('window.history.replaceState'), 'explicit window.history.replaceState missing');
assert(document.includes('id="target-jump"') && document.includes('표적 구간으로 이동'), 'target jump missing');
assert(mainMatch[1].includes('canplay'), 'pre-canplay target jump fallback missing');
assert(document.includes('id="phenomenon-summary-save"'), 'phenomenon summary save missing');
assert(document.includes('stage2_two_hour_phenomenon_summary.v1'), 'phenomenon summary schema missing');
assert(document.includes('phenomenon_summary_exploratory_only_not_formal_ledger'), 'phenomenon summary role missing');
assert(document.includes('5 · 단서 명확·재청취 불필요'), 'confidence anchor 5 missing');
assert(document.includes('1 · 추측'), 'confidence anchor 1 missing');
assert(document.includes('blindRecheck'), 'shuffled blind recheck missing');
assert(document.includes('불러오기 실패 — 행 ${lineNumber}'), 'import line-number error missing');

const samples = embedded('samples-data');
const dialogues = embedded('dialogues-data');
const metadata = embedded('metadata-data');
const literature = embedded('literature-data');
const textgrids = embedded('textgrids-data');
const build = embedded('build-data');

assert(samples.length === 84, `samples=${samples.length}`);
assert(new Set(samples.map(row => row.sample_id)).size === 84, 'sample IDs not unique');
for (const code of ['PT', 'NAN', 'NAL', 'NI', 'LLN', 'VH', 'HIA']) {
  assert(samples.filter(row => row.phenomenon_code === code).length === 12, `${code} count`);
  assert(literature[code], `${code} literature missing`);
}
assert(samples.every(row => dialogues[row.utt_id]), 'dialogue mapping missing');
assert(samples.every(row => metadata[row.utt_id]), 'metadata mapping missing');
assert(Object.keys(textgrids).length === 84, 'TextGrid projection count');
assert(samples.every(row => row.target_audio.startsWith('assets/')), 'relative audio path');
assert(samples.every(row => row.praat_work_textgrid.startsWith('praat_work/')), 'Praat work path');
assert(!samples.some(row => row.phenomenon_code === 'NI' && row.query_id.endsWith('VCP_SURFACE_BRANCH_V1')), 'invalid NI VCP selected');
assert(build.automatic_realization_judgement === false, 'automatic realization flag');
assert(document.includes("record_role:'exploratory_pilot_only_not_formal_realization_ledger'"), 'record role missing');
assert(document.includes("review_order_mode:byId('order-mode').value"), 'order mode not exported');

function makeElement(id) {
  const listeners = Object.create(null);
  return {
    id,
    value: '',
    checked: false,
    type: '',
    name: '',
    style: {},
    dataset: {},
    className: '',
    innerHTML: '',
    textContent: '',
    href: '',
    src: '',
    currentTime: 0,
    addEventListener(type, callback) { listeners[type] = callback; },
    emit(type, event = {}) { return listeners[type]?.(event); },
    click() { return this.onclick?.(); },
  };
}

async function smokeMainScript() {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
  };
  for (const [id, value] of [
    ['samples-data', samples],
    ['dialogues-data', dialogues],
    ['metadata-data', metadata],
    ['literature-data', literature],
    ['textgrids-data', textgrids],
    ['build-data', build],
  ]) get(id).textContent = JSON.stringify(value);

  const form = get('review-form');
  const names = [
    'listened', 'reviewer', 'scope_decision', 'environment_confidence',
    'realization_impression', 'realization_confidence', 'context_sufficient',
    'boundary_edit_need', 'compoundness_decision', 'context_type',
    'morph_environment_note', 'phonological_note', 'literature_connection_note',
    'uncertainty_and_question', 'selected_context_utt_ids_json',
  ];
  form.elements = [];
  for (const name of names) {
    const element = name === 'realization_impression' ? get('realization-impression') : makeElement(name);
    element.name = name;
    if (name === 'listened') element.type = 'checkbox';
    form.elements.push(element);
    form.elements[name] = element;
  }
  form.reset = () => {
    for (const element of form.elements) {
      element.value = '';
      if (element.type === 'checkbox') element.checked = false;
    }
  };
  get('order-mode').value = 'grouped';
  get('target-audio').readyState = 4;

  const storage = new Map();
  const localStorage = {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); },
    removeItem(key) { storage.delete(key); },
  };
  const replaceStateCalls = [];
  const fakeWindow = {
    history: { replaceState(...args) { replaceStateCalls.push(args); } },
    addEventListener() {},
  };
  const fakeDocument = {
    getElementById: get,
    querySelectorAll() { return []; },
    createElement(id) { return makeElement(id); },
  };
  class FakeFormData {
    forEach() {}
  }
  class FakeBlob {
    constructor(parts) { this.parts = parts; }
  }
  class FakeURL extends URL {}
  FakeURL.createObjectURL = () => 'blob:test';
  FakeURL.revokeObjectURL = () => {};
  const context = vm.createContext({
    document: fakeDocument,
    localStorage,
    location: { search: '?phenomenon=PT' },
    window: fakeWindow,
    URLSearchParams,
    URL: FakeURL,
    Blob: FakeBlob,
    FormData: FakeFormData,
    crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000001' },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    confirm: () => true,
    console,
  });
  new vm.Script(mainMatch[1], { filename: `${htmlPath}:smoke` }).runInContext(context);

  get('phenomenon').value = 'NAN';
  get('phenomenon').onchange();
  assert(replaceStateCalls.at(-1)?.[2] === '?phenomenon=NAN', 'phenomenon switch URL smoke');
  assert(get('position').textContent.endsWith('· NAN'), 'phenomenon switch render smoke');

  const nanFirst = samples
    .filter(row => row.phenomenon_code === 'NAN')
    .sort((a, b) => Number(a.grouped_order) - Number(b.grouped_order))[0];
  get('target-audio').currentTime = 0;
  get('target-jump').onclick();
  assert(
    get('target-audio').currentTime === Number(textgrids[nanFirst.sample_id].target_xmin),
    'target jump currentTime smoke',
  );

  get('phenomenon-lit-note').value = '자동 저장 확인';
  get('phenomenon-lit-note').emit('input');
  assert(
    [...storage.entries()].some(([key, value]) => key.endsWith('_lit_NAN') && value === '자동 저장 확인'),
    'literature note immediate storage smoke',
  );
  get('phenomenon-summary-save').onclick();
  const reviewStorageKey = [...storage.keys()].find(key => !key.includes('_lit_'));
  const savedRows = JSON.parse(storage.get(reviewStorageKey));
  assert(savedRows.some(row => row.record_role === 'phenomenon_summary_exploratory_only_not_formal_ledger'), 'summary row smoke');
  assert(!('sample_id' in savedRows.find(row => row.schema_version === 'stage2_two_hour_phenomenon_summary.v1')), 'summary sample_id omitted');

  savedRows.push({
    schema_version: 'stage2_two_hour_exploratory_review.v1',
    event_uuid: 'grouped-row',
    revision_seq: 1,
    sample_id: nanFirst.sample_id,
    phenomenon_code: 'NAN',
    review_order_mode: 'grouped',
    realization_impression: 'observed',
    realization_confidence: '2',
    environment_confidence: '4',
    record_role: 'exploratory_pilot_only_not_formal_realization_ledger',
    reviewed_at: '2099-01-01T00:00:00.000Z',
  });
  storage.set(reviewStorageKey, JSON.stringify(savedRows));
  get('order-mode').value = 'shuffled';
  get('order-mode').onchange();
  assert(get('realization-impression').value === '', 'shuffled impression not blank');
  assert(form.elements.realization_confidence.value === '', 'shuffled confidence not blank');
  assert(form.elements.environment_confidence.value === '4', 'shuffled cleared non-target field');

  await get('import').onchange({ target: { files: [{ text: async () => '{broken' }] } });
  assert(get('import-status').textContent.includes('불러오기 실패 — 행 1'), 'import error row smoke');
  assert(JSON.parse(storage.get(reviewStorageKey)).length === savedRows.length, 'failed import changed local rows');
}

smokeMainScript().then(() => {
  console.log(JSON.stringify({
    passed: true,
    samples: samples.length,
    dialogueKeys: Object.keys(dialogues).length,
    literatureCodes: Object.keys(literature).length,
    textgridProjections: Object.keys(textgrids).length,
    domSmoke: true,
  }));
}).catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});

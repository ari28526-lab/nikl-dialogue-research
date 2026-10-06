"""Build portable utterance/media links after COPY_FINAL; never declares DELIVERY_FINAL.

Only copied native discourse JSON and frozen ANALYSIS_LINKS provide joins. No
token-to-word or morpheme timing is inferred. Source files are never changed.
"""
import argparse
from collections import Counter
from contextlib import closing
import csv
import gzip
import hashlib
import json
import msvcrt
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import sqlite3
import time
import traceback
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    with (gzip.open if str(path).endswith('.gz') else open)(path, 'rt', encoding='utf-8-sig') as f:
        return json.load(f)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with (gzip.open if path.suffix == '.gz' else open)(tmp, 'wt', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    tmp.replace(path)


def relative(value):
    p = PurePosixPath(value)
    if not p.parts or '\\' in value or p.is_absolute() or any(x in ('..', '.') or ':' in x for x in p.parts):
        raise ValueError('Unsafe relative path: ' + value)
    return p.as_posix()


def csv_rows(path):
    with (gzip.open if str(path).endswith('.gz') else open)(path, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


class Package:
    def __init__(self, root):
        self.root = root.resolve()
        self.contract = read(root / 'CONTRACT.json')
        self.roles = {x['role']: x for x in self.contract['config']['roots']}
        self.db = sqlite3.connect((root / 'COPY_LEDGER.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
        self.cache = {}

    def path(self, rel):
        p = self.root / relative(rel)
        if not p.resolve().is_relative_to(self.root):
            raise ValueError('Path escapes package')
        return p

    def ref(self, role, subpath, expected=None, optional=False):
        rel = relative(self.roles[role]['destination'] + '/' + relative(subpath))
        # Only small/shared references are cached; millions of per-utterance paths are not.
        record = self.cache.get(rel)
        if record is None:
            record = self.db.execute('SELECT relative,bytes,sha256,copied FROM files WHERE relative=?', (rel,)).fetchone()
        if record is None:
            if optional:
                return None
            raise ValueError('Required copied file missing: ' + rel)
        if record[3] != 1 or not record[2] or (expected and expected != record[2]):
            raise ValueError('Copied file not verified or SHA differs: ' + rel)
        if len(self.cache) < 20000 and not rel.endswith(('.wav', '.TextGrid')):
            self.cache[rel] = record
        return dict(path=record[0], bytes=record[1], sha256=record[2])

    def load(self, ref):
        p = self.path(ref['path'])
        if sha(p) != ref['sha256']:
            raise ValueError('Copied input changed: ' + ref['path'])
        return read(p)


def source_relative(pkg, role, source):
    # Interpret recorded Windows paths without requiring their old drive to exist.
    return relative(PureWindowsPath(source).relative_to(PureWindowsPath(pkg.roles[role]['source'])).as_posix())


def modu_document(pkg, entry, document, link_entry):
    prov = document['provenance']
    source_file = link_entry['source_file']
    ref = pkg.ref('current_cloud_20260926', link_entry['links_relative'], link_entry['sha256'])
    path = pkg.path(ref['path'])
    if sha(path) != ref['sha256']:
        raise ValueError('ANALYSIS_LINKS hash mismatch')
    links = csv_rows(path)
    by_id = {x['utt_id']: x for x in links}
    if len(by_id) != len(links):
        raise ValueError('Duplicate ANALYSIS_LINKS ID')
    base = PurePosixPath(prov['analysis_relative']).parent.as_posix()
    shared = dict(
        source_transcript=pkg.ref('raw_transcripts_and_references', 'dialogue_json/' + prov['raw_relative'], prov['raw_sha256']),
        stored_analysis=pkg.ref('current_cloud_20260926', prov['analysis_relative'], prov['analysis_sha256']),
        morphology_csv=pkg.ref('current_cloud_20260926', base + '/morphemes.csv.gz'),
        original_analysis_links=ref,
        alignment_tables={name: pkg.ref('modu_base_and_alignment', f'alignment/{entry["year"]}/{name}') for name in
                          ['word_intervals_mfa.csv.gz', 'phone_intervals_mfa.csv.gz', 'utterance_alignment.csv.gz', 'excluded_utterances.csv.gz', 'TABLES_MANIFEST.json']},
        historical_context={name: pkg.ref('historical_context_export_20260928', 'files/' + str(PurePosixPath(source_file).with_suffix('')) + '/' + name)
                            for name in ['utterances.json.gz', 'morphemes.json.gz', 'json_alignment.json.gz', 'RECEIPT.json']})
    rows = []
    seen = set()
    for position, u in enumerate(document['utterances'], 1):
        uid = u['utterance_id']
        if uid in seen or u['turn_order'] != position or u['original']['id'] != uid:
            raise ValueError('Native ID/order mismatch')
        seen.add(uid)
        a = u['analysis']; link = by_id.get(uid)
        row = dict(utterance_id=uid, turn_order=position, analysis_status=a['status'],
                   source_start=u['original'].get('start'), source_end=u['original'].get('end'),
                   speaker_id=u['original'].get('speaker_id'), source_row_index=None,
                   original_json_pointer=f'/utterances/{position-1}', morphology_join_key='utt_id',
                   morpheme_timing='not_established', source_recording_audio_status='location_unverified',
                   clip_time_origin='clip_local_zero_if_present')
        if link is None:
            if a['status'] != 'empty_source_not_analyzed':
                raise ValueError('Analyzed native utterance has no ANALYSIS_LINKS row: ' + uid)
            row.update(alignment_status='empty_source_not_analyzed', textgrid=None)
        else:
            response = a['input_and_response']
            if response['utt_id'] != uid or response['source_file'] != source_file or link['source_file'] != source_file:
                raise ValueError('Source identity mismatch')
            if str(response['source_row_index']) != link['source_row_index']:
                raise ValueError('Source row index mismatch')
            if hashlib.sha256(response['form'].encode('utf-8')).hexdigest() != link['source_form_sha256']:
                raise ValueError('Source form mismatch')
            if link['analysis_json'] != prov['analysis_relative'] or link['morphology_csv'] != base + '/morphemes.csv.gz':
                raise ValueError('Analysis path mismatch')
            if source_relative(pkg, 'modu_base_and_alignment', link['word_alignment_table']) != f'alignment/{entry["year"]}/word_intervals_mfa.csv.gz':
                raise ValueError('Alignment table mismatch')
            if link['status'] not in ['derived', 'no_mfa_alignment']:
                raise ValueError('Unexpected alignment status')
            tg = pkg.ref('current_cloud_20260926', link['textgrid_path'], link['textgrid_sha256']) if link['status'] == 'derived' else None
            if tg is None and (link['textgrid_path'] or link['textgrid_sha256']):
                raise ValueError('Unaligned utterance has a TextGrid reference')
            row.update(alignment_status=link['status'], textgrid=tg, source_row_index=link['source_row_index'],
                       source_form_sha256=link['source_form_sha256'], token_to_word_mapping=link['token_to_word_mapping'])
        session = PurePosixPath(source_file).stem
        # The 2020 recovered namespace is explicitly distinct from canonical_original.
        prefixes = [f'analysis_resolved_2020/{session}'] if entry['year'] == '2020' else [f'canonical_original/{entry["year"]}/{session}', f'canonical_original/{entry["year"]}']
        matches = [r for prefix in prefixes if (r := pkg.ref('modu_clips_and_recovered_ids', f'{prefix}/{uid}.wav', optional=True))]
        if len(matches) > 1:
            raise ValueError('Ambiguous clip path: ' + uid)
        row['clip'] = matches[0] if matches else None
        row['clip_status'] = 'available' if matches else 'not_in_declared_copy_scope'
        if row['alignment_status'] == 'derived' and not matches:
            raise ValueError('Aligned utterance has no verified clip: ' + uid)
        rows.append(row)
    return dict(source_file=source_file, references=shared, utterances=rows,
                time_policy='source_start/end are native recording coordinates; clip time is local; no morpheme timing',
                textgrid_policy='Five preserved alignment tiers; old six-tier TextGrids remain in historical_versions')


def seoul_document(pkg, entry, document, recording, interview_ref):
    ident = document['discourse_id']; metadata = document['recording_metadata']; prov = document['provenance']
    if metadata['source_file'] != ident or recording['source_file'] != ident:
        raise ValueError('Seoul recording identity mismatch')
    media = {}
    for kind, field, digest in [('audio', 'wav_path', 'source_wav_sha256'), ('textgrid', 'textgrid_path', 'source_textgrid_sha256')]:
        prefix = '../00_SOURCE/'
        if not recording[field].startswith(prefix):
            raise ValueError('Unexpected Seoul metadata path')
        media[kind] = pkg.ref('seoul_original', recording[field][len(prefix):], metadata[digest])
    shared = dict(**media, interview_json=interview_ref,
                  stored_analysis=pkg.ref('current_cloud_20260926', prov['analysis_relative'], prov['analysis_sha256']),
                  morphology_csv=pkg.ref('current_cloud_20260926', 'seoul/COMPLETE/morphemes.csv'),
                  recording_metadata=pkg.ref('seoul_research_metadata', 'recordings.csv'))
    rows = []; seen = set()
    for position, u in enumerate(document['utterances'], 1):
        uid = u['utterance_id']; orig = u['original']
        if uid in seen or u['turn_order'] != position or uid != f'seoul:{ident}:t7:i{orig["interval_index"]}':
            raise ValueError('Seoul ID/order mismatch')
        seen.add(uid)
        rows.append(dict(utterance_id=uid, turn_order=position, analysis_status=u['analysis']['status'],
                         original_json_pointer=f'/utterances/{position-1}', source_start=orig['start'], source_end=orig['end'],
                         interval_index=orig['interval_index'], source_tier_index=7, alignment_status='original_seoul_annotation',
                         source_recording_audio_status='available', clip_status='use_recording_interval',
                         morphology_join_key='utt_id', morpheme_timing='not_established'))
    return dict(source_file=ident, references=shared, utterances=rows,
                time_policy='Native recording-local seconds; interview segments retain their separate clocks',
                textgrid_policy='Original seven tiers, including repeated tier names; no Modu tier-removal rule')


def totals_check(totals, sample):
    if sample:
        return
    expected = {'modu_documents': 17156, 'modu_utterances': 5157997, 'seoul_documents': 240,
                'seoul_utterances': 128313, 'seoul_interviews': 40, 'seoul_segments': 240,
                'modu_derived': 4286046, 'modu_no_mfa_alignment': 817310,
                'modu_empty_source_not_analyzed': 54641}
    for key, value in expected.items():
        if totals[key] != value:
            raise ValueError(f'Full scope count mismatch: {key} {totals[key]} != {value}')


def build(pkg, out, entries, sample=False):
    production = 'current_cloud_20260926'
    link_index_ref = pkg.ref(production, 'modu/alignment_textgrids_v1/LINK_INDEX.csv.gz')
    if sha(pkg.path(link_index_ref['path'])) != link_index_ref['sha256']:
        raise ValueError('Link index changed')
    links = {r['source_file']: r for r in csv_rows(pkg.path(link_index_ref['path']))}
    recordings_ref = pkg.ref('seoul_research_metadata', 'recordings.csv')
    if sha(pkg.path(recordings_ref['path'])) != recordings_ref['sha256']:
        raise ValueError('Seoul recording metadata changed')
    recordings = {r['source_file']: r for r in csv_rows(pkg.path(recordings_ref['path']))}
    interviews = {}; totals = Counter(); receipts = []
    for e in entries:
        if e['corpus'] != 'seoul_interviews':
            continue
        ref = pkg.ref(production, 'discourse_json/' + e['path'], e['sha256']); d = pkg.load(ref)
        if len(d['segments']) != e['expected_records']:
            raise ValueError('Interview segment count mismatch')
        totals['seoul_interviews'] += 1
        for segment in d['segments']:
            ident = segment['discourse_id']
            if ident in interviews:
                raise ValueError('Duplicate interview recording')
            interviews[ident] = ref; totals['seoul_segments'] += 1
    with closing(sqlite3.connect(out / 'UTTERANCE_INDEX.sqlite')) as db:
        db.execute('CREATE TABLE IF NOT EXISTS utterances(corpus TEXT, utterance_id TEXT, discourse_id TEXT, document_path TEXT, turn_order INTEGER, PRIMARY KEY(corpus,utterance_id)) WITHOUT ROWID')
        for e in entries:
            if e['corpus'] == 'seoul_interviews':
                continue
            if (out / 'STOP').exists():
                raise InterruptedError('STOP at document boundary')
            ref = pkg.ref(production, 'discourse_json/' + e['path'], e['sha256'])
            key = relative('documents/' + e['path'] + '.links.json.gz')
            dest = out / key; rp = dest.with_name(dest.name + '.receipt.json')
            if rp.exists():
                receipt = read(rp)
                if receipt['source_sha256'] != e['sha256'] or sha(dest) != receipt['sha256']:
                    raise ValueError('Resume receipt mismatch')
                result = read(dest)
            else:
                d = pkg.load(ref)
                if e['corpus'] == 'modu':
                    # Use provenance path, not a guessed utterance prefix, to select source.
                    source = PurePosixPath(d['provenance']['analysis_relative']).parent
                    source_file = PurePosixPath(*source.parts[3:]).as_posix() + '.csv'
                    result = modu_document(pkg, e, d, links[source_file])
                else:
                    result = seoul_document(pkg, e, d, recordings[d['discourse_id']], interviews[d['discourse_id']])
                result.update(schema='portable_utterance_links.v1', corpus=e['corpus'], discourse_id=d['discourse_id'],
                              source_discourse=ref, human_verified=False, references_base='package_root')
                if len(result['utterances']) != e['expected_records']:
                    raise ValueError('Native utterance count mismatch')
                save(dest, result)
                if read(dest) != result:
                    raise ValueError('Link JSON readback mismatch')
                receipt = dict(status='document_links_verified', source_sha256=e['sha256'], sha256=sha(dest), rows=len(result['utterances']))
                save(rp, receipt)
            corpus = e['corpus']; totals[corpus + '_documents'] += 1
            for row in result['utterances']:
                values = (corpus, row['utterance_id'], result['discourse_id'], key, row['turn_order'])
                prior = db.execute('SELECT corpus,utterance_id,discourse_id,document_path,turn_order FROM utterances WHERE corpus=? AND utterance_id=?', values[:2]).fetchone()
                if prior and prior != values:
                    raise ValueError('Duplicate utterance across documents')
                if not prior:
                    db.execute('INSERT INTO utterances VALUES(?,?,?,?,?)', values)
                totals[corpus + '_utterances'] += 1
                totals[corpus + '_' + row['alignment_status']] += 1
                totals[corpus + '_clip_' + row['clip_status']] += 1
            db.commit()
            receipts.append(dict(path=rp.relative_to(out).as_posix(), sha256=sha(rp)))
            save(out / 'STATE.json', dict(status='running', phase='semantic_links', pid=os.getpid(), updated_at=now(), counts=dict(totals)))
        if db.execute('SELECT count(*) FROM utterances').fetchone()[0] != totals['modu_utterances'] + totals['seoul_utterances']:
            raise ValueError('Index has unexpected retained entries')
    totals_check(totals, sample)
    catalog = {role: {'path': v['destination'], 'kind': 'directory'} for role, v in pkg.roles.items()}
    save(out / 'DATASET_CATALOG.json', dict(references_base='package_root', roles=catalog,
        historical_join_policy='Use source_file and original utt_id/json_alignment evidence; never transfer 3.1 senses to 3.2.',
        full_session_audio='Modu location unverified; Seoul original recording references verified',
        older_textgrid_policy='Historical directory references are included; per-utterance old TextGrid links are not yet built.'))
    final = dict(status='semantic_links_complete_with_explicit_scope_gaps', completed_at=now(), sample=sample,
                 counts=dict(totals), receipts=receipts, index_sha256=sha(out / 'UTTERANCE_INDEX.sqlite'),
                 catalog_sha256=sha(out / 'DATASET_CATALOG.json'), delivery_complete=False,
                 scope_gaps=['Modu full-session source audio location unverified', 'Old Modu TextGrid per-utterance link not indexed; historical directories preserved',
                             'Final code/guide bundling and full-package acceptance/reopen remain'])
    save(out / 'FINAL.json', final); save(out / 'STATE.json', final)
    return final


def run(root, out, wait=False):
    root = root.resolve(); out = out.resolve(); out.mkdir(parents=True, exist_ok=True)
    if out == root or root.is_relative_to(out):
        raise ValueError('Unsafe output scope')
    with (out / 'PROCESS.lock').open('a+b') as lock:
        lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            contract = dict(schema='portable_semantic_links.v1', runner_sha256=sha(Path(__file__)), copy_contract_sha256=sha(root / 'CONTRACT.json'))
            if (out / 'CONTRACT.json').exists():
                if read(out / 'CONTRACT.json') != contract:
                    raise ValueError('Frozen contract changed')
            else:
                save(out / 'CONTRACT.json', contract)
            while not (root / 'COPY_FINAL.json').exists():
                s = read(root / 'STATE.json')
                if s['status'] in ['error', 'stopped']:
                    raise RuntimeError('Copy dependency stopped: ' + s.get('error', s['status']))
                if not wait:
                    raise RuntimeError('COPY_FINAL required')
                if (out / 'STOP').exists():
                    raise InterruptedError('STOP while waiting')
                save(out / 'STATE.json', dict(status='waiting_for_copy', pid=os.getpid(), updated_at=now(), dependency_phase=s.get('phase')))
                time.sleep(300)
            final = read(root / 'COPY_FINAL.json')
            if final['status'] != 'declared_scope_copied_sha_verified' or sha(root / 'COPY_LEDGER.sqlite') != final['ledger_sha256'] or sha(root / 'INVENTORY.json') != final['inventory_sha256']:
                raise ValueError('Copy final binding mismatch')
            pkg = Package(root)
            try:
                source = pkg.ref('delivery_discourse_parquet_20260928', 'INPUTS.json')
                entries = pkg.load(source)
                build(pkg, out, entries)
            finally:
                pkg.db.close()
        except BaseException as exc:
            error = dict(status='stopped' if isinstance(exc, InterruptedError) else 'error', pid=os.getpid(), updated_at=now(), error=str(exc), traceback=traceback.format_exc())
            save(out / 'ERROR.json', error); save(out / 'STATE.json', error)
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    run(args.package, args.output, args.wait)

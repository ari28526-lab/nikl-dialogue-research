"""Independent streaming audit of a reference-only conversation request plan.

Uses only the standard library, not the planner's packing or mapping functions.
Never calls an API. Reads utterance tables, not audio or morphology payloads.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize(text):
    separators = {'\r', '\n', '\v', '\f', '\x85', '\u2028', '\u2029'}
    return ''.join(' ' if c in separators else c for c in text)


def audit(plan, morph):
    start_time = time.monotonic()
    report = json.loads((plan / 'REPORT.json').read_text(encoding='utf-8'))
    references = json.loads((plan / 'SOURCE_REFERENCES.json').read_text(encoding='utf-8'))['sources']
    refs = {r['relative']: r for r in references}
    if len(refs) != len(references):
        raise ValueError('duplicate_source_reference')
    output_path = plan / 'conversation_windows.jsonl.gz'
    with output_path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != report['output_sha256']:
        raise ValueError('output_sha_mismatch')
    totals = Counter()
    seen = set()
    used_refs = set()
    with gzip.open(output_path, 'rt', encoding='utf-8') as stream:
        objects = (json.loads(line) for line in stream)
        for conversation, group in itertools.groupby(objects, key=lambda w: w['conversation_id']):
            if conversation in seen:
                raise ValueError('duplicate_conversation')
            seen.add(conversation)
            wins = list(group)
            refname = wins[0]['morph_receipt']
            used_refs.add(refname)
            ref = refs[refname]
            receipt_data = (morph / refname).read_bytes()
            if sha(receipt_data) != ref['morph_receipt_sha256']:
                raise ValueError('source_receipt_sha_changed')
            receipt = json.loads(receipt_data)
            data = (morph / refname).parent.joinpath('utterances.csv.gz').read_bytes()
            if sha(data) != ref['utterances_sha256']:
                raise ValueError('utterance_sha_changed')
            rows = list(csv.DictReader(io.StringIO(gzip.decompress(data).decode('utf-8-sig'), newline='')))
            expected_ids = [r['utt_id'] for r in rows]
            if len(set(expected_ids)) != len(rows):
                raise ValueError('input_duplicate_id')
            core_ids = []
            for win_index, win in enumerate(wins):
                a, b, c, d = (win[k] for k in ('context_start', 'core_start', 'core_end', 'context_end'))
                if not 0 <= a <= b < c <= d <= len(rows) or win['window_index'] != win_index:
                    raise ValueError('invalid_window_bounds')
                if win['morph_receipt'] != refname or win['source_file'] != receipt['source_file']:
                    raise ValueError('cross_conversation_reference')
                segment = rows[a:d]
                texts = [normalize(r['form']) for r in segment]
                request = ' '.join(texts)
                if sha(request.encode('utf-8')) != win['request_sha256'] or len(request) != win['request_chars']:
                    raise ValueError('request_reconstruction_mismatch')
                if len(win['mappings']) != len(segment):
                    raise ValueError('mapping_count_mismatch')
                offset = 0
                for idx, (row, mapping, text) in enumerate(zip(segment, win['mappings'], texts, strict=True), a):
                    role = 'core' if b <= idx < c else 'context'
                    if mapping['utt_id'] != row['utt_id'] or mapping['speaker_id'] != row['speaker_id'] or mapping['source_row_index'] != int(row['source_row_index']) or mapping['role'] != role:
                        raise ValueError('mapping_identity_mismatch')
                    if mapping['begin_utf32'] != offset or mapping['end_utf32'] != offset + len(text):
                        raise ValueError('mapping_offset_mismatch')
                    if role == 'core':
                        core_ids.append(row['utt_id'])
                    offset += len(text) + 1
                expected_status = 'hold_oversize_utterance' if len(request) > report['max_chars'] else ('hold_empty_text' if not request.strip() else 'planned')
                if win['status'] != expected_status:
                    raise ValueError('incorrect_request_status')
                totals['windows'] += 1
                totals['request_eojeol_with_overlap'] += len(request.split())
            if core_ids != expected_ids:
                raise ValueError('utterance_core_order_or_zero_drop_failure')
            totals['conversations'] += 1
            totals['utterances'] += len(rows)
            totals['morphemes_referenced'] += sum(int(r['response_morph_count']) for r in rows)
    if used_refs != set(refs):
        raise ValueError('source_reference_coverage_failure')
    for key, count in totals.items():
        if report['counts'][key] != count:
            raise ValueError('reported_count_mismatch_' + key)
    return {'schema': 'wsd_conversation_plan_independent_audit.v1', 'passed': True,
            'counts': dict(totals), 'elapsed_seconds': round(time.monotonic() - start_time, 2),
            'input_utterance_sha_unchanged_since_planning': True,
            'source_order_and_speaker_mapping_passed': True, 'zero_drop_passed': True,
            'api_called': False, 'semantic_WSD_quality_audited': False,
            'plan_sha256': digest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--morph-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.plan, args.morph_root)
    except Exception as exc:
        result = {'passed': False, 'error_type': type(exc).__name__, 'message': str(exc)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=True, indent=2)
        handle.write('\n')
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 1)

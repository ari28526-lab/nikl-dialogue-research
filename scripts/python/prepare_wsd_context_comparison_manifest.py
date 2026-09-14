"""Select a small, reference-only paired pilot from an audited conversation plan.

No API, raw corpus text, or source mutation. The selection is a technical pilot,
not a representative estimate of WSD accuracy or an executable API runner.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re


def select(windows, years=tuple(str(y) for y in range(2020, 2026))):
    chosen = {}
    used_windows = set()
    for window in windows:
        match = re.search(r'NIKL_DIALOGUE_(\d{4})_', window['source_file'])
        if not match or match[1] not in years or window['status'] != 'planned':
            continue
        year = match[1]
        key = (window['conversation_id'], window['window_index'])
        if key in used_windows:
            continue
        core = [m for m in window['mappings'] if m['role'] == 'core'
                and m['end_utf32'] > m['begin_utf32']]
        if not core:
            continue
        short = min(core, key=lambda m: m['end_utf32'] - m['begin_utf32'])
        long = max(core, key=lambda m: m['end_utf32'] - m['begin_utf32'])
        candidates = [
            ('short_core', short, short['end_utf32'] - short['begin_utf32'] <= 20),
            ('long_core', long, long['end_utf32'] - long['begin_utf32'] >= 80),
            ('multi_speaker', short, len({m['speaker_id'] for m in window['mappings']
                                       if m['speaker_id']}) >= 2),
        ]
        for stratum, target, eligible in candidates:
            if eligible and (year, stratum) not in chosen:
                chosen[(year, stratum)] = {
                    'year': year, 'stratum': stratum,
                    'conversation_id': window['conversation_id'],
                    'window_index': window['window_index'],
                    'morph_receipt': window['morph_receipt'],
                    'request_sha256': window['request_sha256'],
                    'context_request_chars': window['request_chars'],
                    'target_utt_id': target['utt_id'],
                    'target_begin_utf32': target['begin_utf32'],
                    'target_end_utf32': target['end_utf32'],
                    'standalone_request_chars': target['end_utf32'] - target['begin_utf32'],
                }
                used_windows.add(key)
                break
    expected = {(y, s) for y in years for s in ('short_core', 'long_core', 'multi_speaker')}
    if set(chosen) != expected:
        raise ValueError('missing_pilot_strata: ' + str(sorted(expected - set(chosen))))
    return [chosen[key] for key in sorted(chosen)]


def prepare(plan, audit_path):
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    report = json.loads((plan / 'REPORT.json').read_text(encoding='utf-8'))
    path = plan / 'conversation_windows.jsonl.gz'
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if audit.get('passed') is not True or digest != audit.get('plan_sha256') or digest != report.get('output_sha256'):
        raise ValueError('plan_audit_binding_failed')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        selected = select(json.loads(line) for line in stream)
    return {
        'schema': 'wsd_context_comparison_manifest.v1',
        'status': 'offline_prepared_api_not_called',
        'plan_sha256': digest, 'pairs': selected,
        'proposed_api_calls_without_retries': 2 * len(selected),
        'proposed_request_chars': sum(p['context_request_chars'] + p['standalone_request_chars'] for p in selected),
        'API_called': False, 'raw_text_included': False,
        'execution_authorized_by_manifest': False,
        'semantic_quality_verified': False,
        'sampling': 'first_distinct_window_per_year_and_technical_stratum_not_representative',
        'comparison_contract': {
            'same_engine_and_options_except_input_context': True,
            'offset_convention_requires_response_probe': True,
            'boundary_crossing_or_ambiguous_mapping': 'hold_do_not_assign',
            'changed_sense_is_not_automatic_improvement': True,
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.plan, args.audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'pairs'}))

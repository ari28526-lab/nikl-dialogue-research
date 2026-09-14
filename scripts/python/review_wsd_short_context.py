"""Offline review: compare exact unique morphology anchors without forced merging."""
from collections import Counter
import json

from diagnose_wsd_short_context import DEST, select_jobs
from run_wsd_context_comparison import (ROOT, prepare, read_json, digest, canonical,
                                        project, atomic)


def signature(row):
    return (row['begin_in_utterance'], row['end_in_utterance'], row['surface'], row['pos'])


def sense_identity(row):
    sense = row.get('sense')
    return None if sense is None else (sense.get('sense_no'), sense.get('urimal_target_id'))


def compare_exact(a, b):
    ca, cb = Counter(map(signature, a)), Counter(map(signature, b))
    unique = {signature(m): m for m in b if cb[signature(m)] == 1}
    pairs = [(m, unique[signature(m)]) for m in a
             if ca[signature(m)] == cb[signature(m)] == 1]
    return dict(left_morphemes=len(a), right_morphemes=len(b),
                same_full_segmentation=list(map(signature, a)) == list(map(signature, b)),
                unique_exact_matches=len(pairs), left_unmatched=len(a)-len(pairs),
                right_unmatched=len(b)-len(pairs),
                sense_identity_changes=sum(sense_identity(x) != sense_identity(y) for x, y in pairs),
                sense_metadata_only_changes=sum(sense_identity(x) == sense_identity(y) and
                                                x.get('sense') != y.get('sense') for x, y in pairs),
                unmatched_policy='hold_no_forced_transfer', semantic_improvement_established=False)


def main():
    jobs, original, _ = prepare()
    selected = select_jobs(jobs)
    binding = read_json(DEST/'CONTRACT.json')
    if binding['original'] != original:
        raise ValueError('original_contract_changed')
    expected = [dict(id=j['id'], chars=len(j['text']), sha256=j['text_sha256']) for j in selected]
    if binding['jobs'] != expected:
        raise ValueError('request_contract_changed')
    rows, hashes = {}, {}
    for job in selected:
        path = DEST/job['id']/'RESULT.json'
        result = read_json(path)
        if (result['binding'] != dict(batch=binding, request_sha256=job['text_sha256']) or
                result['response_sha256'] != digest(canonical(result['response']))):
            raise ValueError('response_integrity')
        # Recompute against reconstructed frozen input, not the stored projection.
        projection = project(result['response'], job['text'], job['mappings'])
        if projection['held']:
            raise ValueError('projection_not_verified')
        rows[job['id']] = [m for m in projection['assigned'] if m['utt_id'] == job['target_utt_id']]
        if not rows[job['id']]:
            raise ValueError('target_missing')
        hashes[job['id']] = digest(path.read_bytes())
    names = list(rows)
    pairs = [(names[0], name) for name in names[1:]]
    if len(names) == 3:
        pairs.append((names[1], names[2]))
    report = dict(schema='wsd_short_context_offline_review.v1', source_result_sha256=hashes,
                  verified_frozen_input=True, projection_recomputed=True, api_calls=0,
                  comparisons=[dict(left=a, right=b, **compare_exact(rows[a], rows[b])) for a, b in pairs],
                  production_ready=False, scope='one_target_utterance_only',
                  next_step='multi_target_short_context_pilot_before_full_WSD')
    destination = ROOT/'outputs/reports/REVIEW_wsd_short_context_20260905.json'
    atomic(destination, report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

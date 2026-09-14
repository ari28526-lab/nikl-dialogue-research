"""Independent per-utterance geometry checks of offline diagnostic candidates.

No network calls. All candidates must independently cover their original input
exactly once at token level. Normalized morph surfaces need not equal source.
"""
from collections import Counter
import json

from run_wsd_conversation_pilot import ROOT, DEST, prepare_one, read_json, digest, canonical, atomic
from probe_wsd_conversation_jointing import DEST as PROBE, SELECTED


def bounds(item):
    t = item.get('text', {})
    b = int(t.get('begin_offset', 0))
    return b, b + int(t.get('length', 0))


def verify_candidate(response, text, mapping):
    """Deliberately independent of diagnose() and the old project()."""
    lo, hi = mapping['begin_utf32'], mapping['end_utf32']
    covered = Counter()
    morph_count = 0
    for s in response.get('sentences', []):
        sb, se = bounds(s)
        if not 0 <= sb < se <= len(text) or text[sb:se] != s['text'].get('content'):
            raise ValueError('candidate_bad_sentence_anchor')
        for t in s.get('tokens', []):
            b, e = bounds(t)
            if not sb <= b < e <= se or text[b:e] != t['text'].get('content'):
                raise ValueError('candidate_bad_token_anchor')
            # A malformed foreign morph may claim this utterance: it must hold.
            for morph in t.get('morphemes', []):
                mb, me = bounds(morph)
                if not 0 <= mb < me <= len(text):
                    raise ValueError('candidate_unlocalizable_morph')
                if mb < hi and lo < me and not b <= mb < me <= e:
                    raise ValueError('candidate_claimed_by_bad_morph')
            if e <= lo or hi <= b:
                continue
            if not lo <= b < e <= hi:
                raise ValueError('candidate_cross_utterance_token')
            if not t.get('morphemes'):
                raise ValueError('candidate_empty_morphemes')
            for morph in t['morphemes']:
                mb, me = bounds(morph)
                if not b <= mb < me <= e:
                    raise ValueError('candidate_bad_morph_extent')
                morph_count += 1
            covered.update(i for i in range(b, e) if not text[i].isspace())
    expected = {i for i in range(lo, hi) if not text[i].isspace()}
    if set(covered) != expected or any(v != 1 for v in covered.values()) or not morph_count:
        raise ValueError('candidate_coverage_not_exact')
    return morph_count


def main():
    rows, jobs, _ = prepare_one()
    path = ROOT/'outputs/reports/DIAGNOSE_wsd_local_mapping_20260905.json'
    diag = read_json(path)
    if diag['code_sha256'] != digest((ROOT/'scripts/python/diagnose_wsd_local_mapping.py').read_bytes()):
        raise ValueError('diagnostic_code_changed')
    if diag['baseline_audit_sha256'] != digest((DEST/'AUDIT.json').read_bytes()):
        raise ValueError('baseline_audit_changed')
    baseline_audit = read_json(DEST/'AUDIT.json')
    for name, sha in baseline_audit['artifact_sha256'].items():
        if digest((DEST/name).read_bytes()) != sha:
            raise ValueError('baseline_artifact_changed')
    probe_audit = read_json(ROOT/'outputs/reports/AUDIT_wsd_conversation_jointing_probe_20260905.json')
    if diag['probe_audit_sha256'] != digest(canonical(probe_audit)):
        raise ValueError('probe_audit_changed')
    by_job = {j['id']: j for j in jobs}
    result, queue = {}, []
    for track, root in [('baseline',DEST), ('no_jointing_probe',PROBE)]:
        data = diag['tracks'][track]
        selected = [j for j in jobs if j['mode']=='split' and (track=='baseline' or j['id'] in SELECTED)]
        expected = [m['utt_id'] for j in selected for m in j['mappings'] if m['role']=='core']
        ledger = data['ledger']
        if [r['utt_id'] for r in ledger] != expected or len(expected) != len(set(expected)):
            raise ValueError('ledger_coverage_or_order')
        responses = {}
        for name, sha in data['result_file_sha256'].items():
            rp = root/name/'RESULT.json'
            recorded_sha = baseline_audit['source_result_sha256'][name] if track=='baseline' else next(
                f['result_sha256'] for f in probe_audit['findings'] if f['job']==name)
            if digest(rp.read_bytes()) != sha or sha != recorded_sha:
                raise ValueError('response_changed')
            responses[name] = read_json(rp)['response']
        passed = 0
        for row in ledger:
            job = by_job[row['owner_job']]
            mapping = next(m for m in job['mappings'] if m['utt_id']==row['utt_id'] and m['role']=='core')
            if row['status']=='candidate_mapping_verified':
                count = verify_candidate(responses[job['id']], job['text'], mapping)
                if count != row['verified_morphemes'] or row['reasons']:
                    raise ValueError('candidate_count_or_reasons')
                passed += 1
            elif row['status'] in ('hold_mapping','api_missing'):
                if not row['reasons']:
                    raise ValueError('hold_without_reason')
                if (row['status']=='api_missing') != (job['id'] not in responses):
                    raise ValueError('missing_response_state_mismatch')
                queue.append(dict(track=track,utt_id=row['utt_id'],owner_job=job['id'],
                                  status=row['status'],reasons=row['reasons'],
                                  original_request_sha256=job['request_sha256'],
                                  action='review_options_or_context_before_new_api',
                                  auto_resubmit=False))
            else:
                raise ValueError('unknown_diagnostic_status')
        counts = dict(Counter(r['status'] for r in ledger))
        if counts != data['counts']:
            raise ValueError('diagnostic_count_mismatch')
        result[track] = dict(ledger_utterances=len(ledger),independently_verified_candidates=passed,counts=counts)
    old = read_json(DEST/'UTTERANCE_LEDGER.json')
    new = diag['tracks']['baseline']['ledger']
    for a,b in zip(old,new,strict=True):
        if a['utt_id'] != b['utt_id'] or (a['status']=='mapped' and b['status']!='candidate_mapping_verified'):
            raise ValueError('old_verified_candidate_regression')
    recovered = sum(a['status']=='hold_projection' and b['status']=='candidate_mapping_verified'
                    for a,b in zip(old,new,strict=True))
    report = dict(schema='wsd_local_mapping_audit.v1',integrity_passed=True,
                  source_utterances=len(rows),tracks=result,
                  recovered_from_window_hold_as_candidates=recovered,
                  baseline_artifacts_unchanged=True,independent_geometry_check=True,
                  zero_drop=True,duplicate_core=0,new_api_calls=0,coordinates_repaired=False,
                  production_ready=False,semantic_quality_verified=False,mixed_options_merged=False,
                  diagnostic_sha256=digest(path.read_bytes()),
                  followup_queue=queue,followup_auto_execute=False)
    atomic(ROOT/'outputs/reports/AUDIT_wsd_local_mapping_20260905.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='followup_queue'}),flush=True)


if __name__=='__main__': main()

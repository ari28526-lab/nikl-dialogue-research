"""Offline-only localization of source-coordinate issues; never repair or promote.

Pure diagnose() is reusable. main() reads the frozen conversation pilot/probe and
writes small, text-free diagnostic ledgers only to the repository outputs folder.
No client construction, secret loading, or API invocation occurs here.
"""
from collections import Counter
import json

from run_wsd_context_comparison import span, project, canonical, digest, atomic, ROOT


def diagnose(response, text, mappings):
    ids = [m['utt_id'] for m in mappings]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate_mapping_id')
    previous = 0
    for m in mappings:
        b, e = m['begin_utf32'], m['end_utf32']
        if not 0 <= b <= e <= len(text) or b < previous:
            raise ValueError('invalid_mapping_partition')
        previous = e
    reasons = {uid: set() for uid in ids}
    issues = []

    def flag(reason, ranges=(), **indices):
        # Invalid/out-of-input coordinates cannot prove a local influence scope.
        local = bool(ranges) and all(0 <= b < e <= len(text) for b, e in ranges)
        affected = [m['utt_id'] for m in mappings if any(
            b < m['end_utf32'] and m['begin_utf32'] < e for b, e in ranges)] if local else []
        if not affected:
            affected = ids[:]
            local = False
        for uid in affected:
            reasons[uid].add(reason)
        issues.append(dict(reason=reason, scope='localized' if local else 'whole_request',
                           affected_utt_ids=affected, ranges=[list(r) for r in ranges], **indices))

    covered = Counter()
    sentences = response.get('sentences', [])
    if not sentences:
        flag('empty_response')
    for si, sentence in enumerate(sentences):
        sb, se = span(sentence.get('text', {}))
        sentence_ok = (0 <= sb < se <= len(text)
                       and text[sb:se] == sentence.get('text', {}).get('content'))
        if not sentence_ok:
            # A contradictory sentence anchor is not safely localized by itself.
            flag('invalid_sentence_anchor', sentence=si)
        tokens = sentence.get('tokens', [])
        if not tokens:
            flag('empty_sentence_tokens', [(sb, se)] if sentence_ok else (), sentence=si)
        for ti, token in enumerate(tokens):
            tb, te = span(token.get('text', {}))
            token_ok = (sentence_ok and sb <= tb < te <= se
                        and text[tb:te] == token.get('text', {}).get('content'))
            owners = [m for m in mappings if m['begin_utf32'] <= tb < te <= m['end_utf32']]
            if not token_ok:
                flag('invalid_token_anchor', sentence=si, token=ti)
            else:
                covered.update(i for i in range(tb, te) if not text[i].isspace())
            if len(owners) != 1:
                flag('cross_or_unowned_token', [(tb, te)], sentence=si, token=ti)
            morphs = token.get('morphemes', [])
            if not morphs:
                flag('empty_token_morphemes', [(tb, te)], sentence=si, token=ti)
            for mi, morph in enumerate(morphs):
                mb, me = span(morph.get('text', {}))
                if not tb <= mb < me <= te:
                    flag('morph_outside_token', [(tb, te), (mb, me)],
                         sentence=si, token=ti, morph=mi)
    for i, char in enumerate(text):
        if char.isspace():
            continue
        if not covered[i]:
            flag('uncovered_source_position', [(i, i+1)])
        elif covered[i] > 1:
            flag('overlapping_token_coverage', [(i, i+1)])

    original = project(response, text, mappings)
    counts = Counter(m['utt_id'] for m in original['assigned'])
    ledger = []
    for m in mappings:
        uid = m['utt_id']
        if not counts[uid]:
            reasons[uid].add('no_verified_morphemes')
        ledger.append(dict(utt_id=uid, role=m['role'],
                           status='hold_mapping' if reasons[uid] else 'candidate_mapping_verified',
                           reasons=sorted(reasons[uid]), verified_morphemes=counts[uid]))
    # Every old rejection type must be explainable; unknown cases hold all rows.
    known = {'empty_response', 'empty_sentence_tokens', 'empty_token_morphemes',
             'unverified_offsets_or_cross_utterance_boundary',
             'overlapping_response_tokens', 'incomplete_response_source_coverage'}
    if any(h['reason'] not in known for h in original['held']) or (original['held'] and not issues):
        for row in ledger:
            row['status'] = 'hold_mapping'
            row['reasons'] = sorted(set(row['reasons']) | {'unlocalized_legacy_rejection'})
    return dict(ledger=ledger, issues=issues,
                old_held_units=len(original['held']), production_ready=False,
                coordinates_repaired=False, semantic_quality_verified=False)


def main():
    from run_wsd_conversation_pilot import DEST, prepare_one, read_json
    from audit_wsd_conversation_pilot import audit
    from probe_wsd_conversation_jointing import DEST as PROBE, SELECTED, PROBE_OPTIONS

    rows, jobs, contract = prepare_one()
    baseline = audit(DEST, rows, jobs, contract)
    if baseline != read_json(DEST/'AUDIT.json'):
        raise ValueError('baseline_audit_changed')
    probe_audit = read_json(ROOT/'outputs/reports/AUDIT_wsd_conversation_jointing_probe_20260905.json')
    probe_contract = read_json(PROBE/'CONTRACT.json')
    if (probe_contract['baseline_contract_sha256'] != digest(canonical(contract))
            or probe_contract['options'] != PROBE_OPTIONS):
        raise ValueError('probe_contract_changed')
    tracks = {}
    for track, root, selected in [('baseline', DEST, [j['id'] for j in jobs if j['mode']=='split']),
                                   ('no_jointing_probe', PROBE, SELECTED)]:
        ledger, findings, hashes = [], [], {}
        for job in jobs:
            if job['id'] not in selected:
                continue
            path = root/job['id']/'RESULT.json'
            if not path.exists():
                if track != 'baseline' or job['id'] in baseline['source_result_sha256']:
                    raise ValueError('audited_response_missing')
                ledger.extend(dict(utt_id=m['utt_id'], owner_job=job['id'], status='api_missing',
                                   reasons=['api_missing'], verified_morphemes=0)
                              for m in job['mappings'] if m['role']=='core')
                continue
            result = read_json(path)
            hashes[job['id']] = digest(path.read_bytes())
            expected = baseline['source_result_sha256'][job['id']] if track == 'baseline' else next(
                f['result_sha256'] for f in probe_audit['findings'] if f['job']==job['id'])
            if hashes[job['id']] != expected or result['response_sha256'] != digest(canonical(result['response'])):
                raise ValueError('saved_response_changed')
            if track != 'baseline':
                binding = dict(contract_sha256=digest(canonical(probe_contract)),
                               request_sha256=job['request_sha256'],request_chars=len(job['text']))
                if (result['binding'] != binding or read_json(root/job['id']/'INTENT.json') !=
                        dict(binding=binding,max_api_calls=1)):
                    raise ValueError('probe_binding_changed')
            diagnosis = diagnose(result['response'], job['text'], job['mappings'])
            ledger.extend(dict(utt_id=m['utt_id'], owner_job=job['id'], status=m['status'],
                               reasons=m['reasons'], verified_morphemes=m['verified_morphemes'])
                          for m in diagnosis['ledger'] if m['role']=='core')
            findings.append(dict(job=job['id'], issues=diagnosis['issues'],
                                 old_held_units=diagnosis['old_held_units']))
        expected_ids = [m['utt_id'] for j in jobs if j['id'] in selected
                        for m in j['mappings'] if m['role']=='core']
        if [r['utt_id'] for r in ledger] != expected_ids or len(set(expected_ids)) != len(expected_ids):
            raise ValueError('diagnostic_ledger_not_exact')
        tracks[track] = dict(ledger=ledger, counts=dict(Counter(r['status'] for r in ledger)),
                             findings=findings, result_file_sha256=hashes)
    if [r['utt_id'] for r in tracks['baseline']['ledger']] != [r['utt_id'] for r in rows]:
        raise ValueError('source_order_changed')
    # Verify inputs again immediately before writing the separate diagnostic file.
    for track, root in [('baseline', DEST), ('no_jointing_probe', PROBE)]:
        for job, sha in tracks[track]['result_file_sha256'].items():
            if digest((root/job/'RESULT.json').read_bytes()) != sha:
                raise ValueError('input_changed_during_diagnosis')
    result = dict(schema='wsd_offline_local_mapping.v1', tracks=tracks,
                  source_utterances=len(rows), baseline_artifacts_unchanged=True,
                  baseline_audit_sha256=digest((DEST/'AUDIT.json').read_bytes()),
                  probe_audit_sha256=digest(canonical(probe_audit)),
                  code_sha256=digest(__import__('pathlib').Path(__file__).read_bytes()),
                  new_api_calls=0, zero_drop=True, mixed_options_merged=False,
                  coordinates_repaired=False, production_ready=False, semantic_quality_verified=False)
    target = ROOT/'outputs/reports/DIAGNOSE_wsd_local_mapping_20260905.json'
    if target.exists() and read_json(target) != result:
        raise ValueError('diagnostic_output_exists_with_different_contract')
    if not target.exists():
        atomic(target, result)
    print(json.dumps(dict(source_utterances=len(rows), new_api_calls=0,
                          tracks={k:v['counts'] for k,v in tracks.items()}, production_ready=False)), flush=True)


if __name__ == '__main__':
    main()

"""Offline post-run checks from frozen source and saved API responses."""
from collections import Counter
import json

from run_wsd_conversation_pilot import (DEST, ROOT, prepare_one, read_json, canonical,
    digest, project, ref, checked_result, inventory, MAX_CALLS, MAX_CHARS, atomic)
from review_wsd_short_context import compare_exact


def audit(root,rows,jobs,contract):
    if read_json(root/'CONTRACT.json')!=contract:
        raise ValueError('audit_contract_mismatch')
    report=read_json(root/'REPORT.json')
    if read_json(root/'STATE.json')['status']=='running':
        raise ValueError('audit_during_execution')
    if read_json(root/'PLAN.json')!=[{k:v for k,v in j.items() if k!='text'} for j in jobs]:
        raise ValueError('audit_plan_changed')
    projections,hashes={},{}
    call_count,char_count=inventory(root)
    if call_count>MAX_CALLS or char_count>MAX_CHARS:
        raise ValueError('audit_budget_violation')
    for j in jobs:
        path=root/j['id']/'RESULT.json'
        binding=dict(contract_sha256=digest(canonical(contract)),job=ref(j))
        for ip in (root/j['id']).glob('attempt_*.intent.json'):
            if read_json(ip)!=dict(binding=binding,chars=len(j['text'])):
                raise ValueError('audit_attempt_changed')
        if not path.exists():
            continue
        r=checked_result(path,binding)
        matched_attempts=[]
        for ap in (root/j['id']).glob('attempt_*.result.json'):
            if not ap.with_name(ap.name.replace('.result.json','.intent.json')).exists():
                raise ValueError('audit_result_without_intent')
            candidate=checked_result(ap,binding)
            if candidate==r:
                matched_attempts.append(ap.name)
        if len(matched_attempts)!=1:
            raise ValueError('audit_final_attempt_link')
        p=project(r['response'],j['text'],j['mappings'])
        if p!=read_json(root/j['id']/'PROJECTION.json'):
            raise ValueError('audit_projection_changed')
        projections[j['id']]=p
        hashes[j['id']]=digest(path.read_bytes())
    ledger=read_json(root/'UTTERANCE_LEDGER.json')
    source_ids=[r['utt_id'] for r in rows]
    if [r['utt_id'] for r in ledger]!=source_ids or len(set(source_ids))!=len(source_ids):
        raise ValueError('audit_ledger_order_or_coverage')
    core_owner={}
    for j in jobs:
        if j['mode']!='split':
            continue
        for m in j['mappings']:
            if m['role']=='core':
                if m['utt_id'] in core_owner: raise ValueError('audit_duplicate_core')
                core_owner[m['utt_id']]=j['id']
    if set(core_owner)!=set(source_ids): raise ValueError('audit_missing_core')
    merged=[]
    statuses=Counter()
    for source,l in zip(rows,ledger,strict=True):
        uid=source['utt_id']
        owner=core_owner[uid]
        p=projections.get(owner)
        morphs=[] if p is None else [m for m in p['assigned'] if m['utt_id']==uid and m['role']=='core']
        state='api_missing' if p is None else 'hold_projection' if p['held'] or not morphs else 'mapped'
        expected=dict(utt_id=uid,source_row_index=int(source['source_row_index']),speaker_id=source['speaker_id'],
                      owner_job=owner,status=state,morpheme_count=len(morphs))
        if l!=expected: raise ValueError('audit_ledger_content')
        statuses[state]+=1
        if state=='mapped': merged.extend(dict(m,source_job=owner) for m in morphs)
    if read_json(root/'SPLIT_CORE_MORPHEMES.json')!=merged:
        raise ValueError('audit_merged_payload_changed')
    if report['statuses']!=dict(statuses) or report['split_mapping_passed']!=(statuses['mapped']==len(rows)):
        raise ValueError('audit_report_count_changed')
    if report['attempts']!=call_count or report['request_chars_attempted']!=char_count:
        raise ValueError('audit_report_budget_changed')
    if (report['source_utterances']!=len(rows) or report['ledger_utterances']!=len(ledger) or
            report['missing_ids']!=0 or report['duplicate_ids']!=0):
        raise ValueError('audit_report_coverage_changed')
    comparisons=[]
    whole=projections.get('whole')
    if (report['whole_response_available']!=(whole is not None) or
            report['whole_projection_passed']!=(whole is not None and not whole['held'])):
        raise ValueError('audit_whole_status_changed')
    if whole is not None and not whole['held']:
        for row in ledger:
            if row['status']!='mapped': continue
            uid=row['utt_id']
            a=[m for m in whole['assigned'] if m['utt_id']==uid]
            b=[m for m in merged if m['utt_id']==uid]
            if a: comparisons.append(dict(utt_id=uid,**compare_exact(a,b)))
    if comparisons!=report['whole_versus_split']:
        raise ValueError('audit_comparison_changed')
    overlap=[]
    for row in ledger:
        if row['status']!='mapped': continue
        uid=row['utt_id']
        a=[m for m in merged if m['utt_id']==uid]
        for j in jobs:
            if j['mode']!='split' or j['id']==row['owner_job']: continue
            p=projections.get(j['id'])
            if p is None or p['held']: continue
            b=[m for m in p['assigned'] if m['utt_id']==uid and m['role']=='context']
            if b: overlap.append(dict(utt_id=uid,owner_job=row['owner_job'],context_job=j['id'],**compare_exact(a,b)))
    if overlap!=report['overlap_checks']: raise ValueError('audit_overlap_changed')
    def stats(items):
        return dict(compared_utterance_pairs=len(items),
                    different_segmentation=sum(not p['same_full_segmentation'] for p in items),
                    exact_anchor_sense_changes=sum(p['sense_identity_changes'] for p in items),
                    exact_anchor_matches=sum(p['unique_exact_matches'] for p in items))
    return dict(schema='wsd_whole_conversation_audit.v1',integrity_passed=True,
                source_utterances=len(rows),ledger_utterances=len(ledger),zero_drop=True,duplicate_core=0,
                split_analysis_passed=statuses['mapped']==len(rows),utterance_statuses=dict(statuses),
                source_result_sha256=hashes,whole_response_available=whole is not None,
                whole_projection_passed=whole is not None and not whole['held'],
                whole_vs_split=stats(comparisons),overlap=stats(overlap),
                calls_attempted=call_count,request_chars_attempted=char_count,
                production_ready=False,semantic_improvement_established=False,
                artifact_sha256={p:digest((root/p).read_bytes()) for p in
                    ('CONTRACT.json','PLAN.json','REPORT.json','UTTERANCE_LEDGER.json','SPLIT_CORE_MORPHEMES.json')})


def main():
    rows,jobs,contract=prepare_one()
    result=audit(DEST,rows,jobs,contract)
    atomic(DEST/'AUDIT.json',result)
    atomic(ROOT/'outputs/reports/AUDIT_wsd_whole_conversation_pilot_20260905.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__': main()

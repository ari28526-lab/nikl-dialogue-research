"""Offline audit and option-comparison review of the bounded completed dialogue."""
from collections import Counter
import json
from pathlib import Path
from statistics import median

from run_wsd_jointing_completion import (DEST, ROOT, PROBE, prepare_completion, read_json,
    canonical, digest, atomic, request_ref, inventory, build_ledger, checked_result)
from run_wsd_conversation_pilot import DEST as BASE
from run_wsd_context_comparison import project
from diagnose_wsd_local_mapping import diagnose
from review_wsd_short_context import compare_exact


def require(value, label):
    if not value:
        raise ValueError(label)


def audit(root, rows, jobs, contract, reused):
    require(read_json(root/'CONTRACT.json')==contract,'completion_contract_changed')
    state=read_json(root/'STATE.json')
    require(state['status'] in ('completed_with_holds','completed_pending_quality_review'),
            'completion_not_finished')
    require(state['pid'] is None and state['stop_reason'] is None,'completion_still_active')
    require(read_json(root/'ACTIVE_REQUEST.json')==dict(pid=None,status=state['status']),
            'active_request_not_closed')
    require(read_json(root/'REPORT.json')==state,'report_state_disagree')
    responses, errors = dict(reused), {}
    result_hashes, artifact_hashes, attempts = {}, {}, []
    count, chars=inventory(root,jobs,contract)
    for j in jobs:
        if j['id'] in reused:
            require(not (root/j['id']).exists(),'reused_job_was_retransmitted')
            continue
        folder=root/j['id']
        names=set()
        found_success=False
        for n in range(1,contract['max_attempts_per_job']+1):
            prefix=f'attempt_{n}'
            ip=folder/(prefix+'.intent.json')
            if not ip.exists():
                break
            require(not found_success,'attempt_after_success')
            binding=dict(contract_sha256=digest(canonical(contract)),request=request_ref(j),attempt=n)
            require(read_json(ip)==binding,'attempt_binding_changed')
            rp=folder/(prefix+'.result.json')
            ep=folder/(prefix+'.error.json')
            require(rp.exists()!=ep.exists(),'uncertain_or_conflicting_attempt')
            outcome=rp if rp.exists() else ep
            names.update([ip.name,outcome.name])
            for p in (ip,outcome):
                artifact_hashes[p.relative_to(root).as_posix()]=digest(p.read_bytes())
            result=read_json(outcome)
            require(result['binding']==binding,'outcome_binding_changed')
            if rp.exists():
                responses[j['id']]=checked_result(rp,binding)
                result_hashes[j['id']]=digest(rp.read_bytes())
                found_success=True
                errors.pop(j['id'],None)
            else:
                errors[j['id']]=result
            attempts.append(dict(job=j['id'],attempt=n,chars=len(j['text']),
                                 outcome='response_saved' if rp.exists() else 'api_error',
                                 elapsed_seconds=result['elapsed_seconds'],
                                 error_code=None if rp.exists() else result.get('error_code')))
        require(folder.exists() and {p.name for p in folder.iterdir()}==names,'unexpected_attempt_artifact')
        require(found_success or len(names)==2*contract['max_attempts_per_job'],'incomplete_job_attempts')
    require(len(attempts)==count and sum(a['chars'] for a in attempts)==chars,'attempt_accounting')
    ledger,diagnoses=build_ledger(rows,jobs,responses,errors)
    require(read_json(root/'UTTERANCE_LEDGER.json')==ledger,'ledger_recompute_changed')
    require(read_json(root/'DIAGNOSES.json')==diagnoses,'diagnosis_recompute_changed')
    require(read_json(root/'FAILURE_QUEUE.json')==[dict(job=k,error=v) for k,v in errors.items()],
            'failure_queue_changed')
    counts=dict(Counter(r['status'] for r in ledger))
    require(state['statuses']==counts and state['source_utterances']==len(rows),'state_counts_changed')
    require(state['new_calls']==count and state['new_chars']==chars,'state_budget_changed')
    require(state['saved_requests']==len(responses) and state['total_requests']==len(jobs),
            'state_response_counts_changed')
    require(counts.get('pending',0)==0,'pending_jobs_in_completion')
    for name in ('CONTRACT.json','STATE.json','REPORT.json','UTTERANCE_LEDGER.json',
                 'DIAGNOSES.json','FAILURE_QUEUE.json','ACTIVE_REQUEST.json'):
        artifact_hashes[name]=digest((root/name).read_bytes())
    return dict(schema='wsd_jointing_completion_audit.v1',integrity_passed=True,
                source_utterances=len(rows),ledger_utterances=len(ledger),zero_drop=True,duplicate_core=0,
                saved_requests=len(responses),total_requests=len(jobs),reused_requests=len(reused),
                new_calls=count,new_chars=chars,attempts=attempts,statuses=counts,
                new_api_elapsed_seconds_sum=round(sum(a['elapsed_seconds'] for a in attempts),3),
                new_api_elapsed_seconds_median=median(a['elapsed_seconds'] for a in attempts) if attempts else None,
                all_api_responses_available=len(responses)==len(jobs),
                all_source_mapping_verified=counts.get('candidate_mapping_verified',0)==len(rows),
                production_ready=False,semantic_quality_verified=False,
                whole_conversation_context_verified=False,
                original_coordinates_repaired=False,options=contract.get('options'),
                artifact_sha256=artifact_hashes,new_result_file_sha256=result_hashes),responses,ledger


def review(rows,jobs,responses,ledger):
    baseline_audit=read_json(BASE/'AUDIT.json')
    require(baseline_audit['integrity_passed'],'baseline_not_audited')
    for name,sha in baseline_audit['artifact_sha256'].items():
        require(digest((BASE/name).read_bytes())==sha,'baseline_artifact_changed')
    before=read_json(ROOT/'outputs/reports/DIAGNOSE_wsd_local_mapping_20260905.json')['tracks']['baseline']
    before_status={r['utt_id']:r['status'] for r in before['ledger']}
    after_status={r['utt_id']:r['status'] for r in ledger}
    comparisons=[]
    overlap=[]
    projections={j['id']:project(responses[j['id']],j['text'],j['mappings'])
                 for j in jobs if j['id'] in responses}
    new_diagnostics={j['id']:diagnose(responses[j['id']],j['text'],j['mappings'])
                     for j in jobs if j['id'] in responses}
    for j in jobs:
        rp=BASE/j['id']/'RESULT.json'
        if not rp.exists() or j['id'] not in responses:
            continue
        require(digest(rp.read_bytes())==baseline_audit['source_result_sha256'][j['id']],
                'comparison_baseline_response_changed')
        old=read_json(rp)['response']
        old_diag=diagnose(old,j['text'],j['mappings'])
        old_status={r['utt_id']:r['status'] for r in old_diag['ledger']}
        a=project(old,j['text'],j['mappings'])['assigned']
        b=projections[j['id']]['assigned']
        for m in j['mappings']:
            uid=m['utt_id']
            if (m['role']=='core' and old_status[uid]=='candidate_mapping_verified'
                    and after_status[uid]=='candidate_mapping_verified'):
                comparisons.append(dict(utt_id=uid,**compare_exact([x for x in a if x['utt_id']==uid],
                                                                   [x for x in b if x['utt_id']==uid])))
    for row in ledger:
        if row['status']!='candidate_mapping_verified':
            continue
        uid=row['utt_id']
        core=[m for m in projections[row['owner_job']]['assigned'] if m['utt_id']==uid]
        for j in jobs:
            if j['id']==row['owner_job'] or j['id'] not in projections:
                continue
            alternative=next((m for m in new_diagnostics[j['id']]['ledger']
                              if m['utt_id']==uid and m['role']=='context'),None)
            if alternative and alternative['status']=='candidate_mapping_verified':
                seq=[m for m in projections[j['id']]['assigned'] if m['utt_id']==uid]
                overlap.append(dict(utt_id=uid,**compare_exact(core,seq)))
    def summarize(items):
        return dict(compared_utterance_pairs=len(items),
                    full_segmentation_changes=sum(not p['same_full_segmentation'] for p in items),
                    unique_exact_matches=sum(p['unique_exact_matches'] for p in items),
                    exact_anchor_sense_identity_changes=sum(p['sense_identity_changes'] for p in items))
    transitions=Counter((before_status[r['utt_id']],after_status[r['utt_id']]) for r in rows)
    core_morphs=[m for row in ledger if row['status']=='candidate_mapping_verified'
                 for m in projections[row['owner_job']]['assigned']
                 if m['utt_id']==row['utt_id'] and m['role']=='core']
    explicit_sense=sum(m.get('sense') is not None for m in core_morphs)
    positive_number=sum(isinstance((m.get('sense') or {}).get('sense_no'),int) and
                        (m.get('sense') or {})['sense_no']>0 for m in core_morphs)
    return dict(schema='wsd_jointing_completion_review.v1',
                status_transitions=[dict(before=a,after=b,count=n) for (a,b),n in sorted(transitions.items())],
                baseline_on_versus_off=summarize(comparisons),off_overlap_consistency=summarize(overlap),
                comparisons=comparisons,overlap_comparisons=overlap,
                remaining_holds=[r for r in ledger if r['status']!='candidate_mapping_verified'],
                candidate_core_morphemes=len(core_morphs),explicit_sense_objects=explicit_sense,
                positive_sense_numbers=positive_number,
                no_sense_object=len(core_morphs)-explicit_sense,
                sense_counts_are_presence_not_accuracy=True,
                changes_are_not_accuracy_improvement=True,whole_context_comparison_available=False,
                semantic_quality_verified=False,production_ready=False)


def main():
    rows,jobs,contract,reused=prepare_completion()
    result,responses,ledger=audit(DEST,rows,jobs,contract,reused)
    comparison=review(rows,jobs,responses,ledger)
    result['reused_external_artifacts']=contract['reused']
    result['auditor_sha256']=digest(Path(__file__).read_bytes())
    for name,value in [('AUDIT.json',result),('REVIEW.json',comparison)]:
        path=DEST/name
        if path.exists():
            require(read_json(path)==value,'audit_output_already_exists_and_differs')
        else:
            atomic(path,value)
    atomic(ROOT/'outputs/reports/AUDIT_wsd_jointing_completion_20260905.json',result)
    atomic(ROOT/'outputs/reports/REVIEW_wsd_jointing_completion_20260905.json',comparison)
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ('attempts','artifact_sha256','new_result_file_sha256','reused_external_artifacts')}),flush=True)
    print(json.dumps({k:v for k,v in comparison.items()
                      if k not in ('comparisons','overlap_comparisons','remaining_holds')}),flush=True)


if __name__=='__main__': main()

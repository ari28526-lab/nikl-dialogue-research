"""Reconstruct frozen input and verify the three saved jointing probe responses."""
import json

from probe_wsd_conversation_jointing import BASE,DEST,SELECTED,PROBE_OPTIONS
from run_wsd_conversation_pilot import (ROOT,prepare_one,read_json,digest,canonical,
                                       project,inventory,atomic)


def require(condition,label):
    if not condition:
        raise ValueError(label)


def main():
    _,jobs,original=prepare_one()
    contract=read_json(DEST/'CONTRACT.json')
    baseline=read_json(BASE/'AUDIT.json')
    require(contract['baseline_contract_sha256']==digest(canonical(original)),'baseline_contract')
    require(contract['baseline_audit_sha256']==digest((BASE/'AUDIT.json').read_bytes()),'baseline_audit')
    require(contract['options']==PROBE_OPTIONS and contract['max_new_calls']==3,'probe_options')
    require(contract['code_sha256']==digest((ROOT/'scripts/python/probe_wsd_conversation_jointing.py').read_bytes()),'probe_code')
    require(contract['helper_sha256']==digest((ROOT/'scripts/python/diagnose_wsd_context_request.py').read_bytes()),'probe_helper')
    for name,sha in baseline['artifact_sha256'].items():
        require(digest((BASE/name).read_bytes())==sha,'baseline_artifact_changed')
    findings=[]
    for name in SELECTED:
        job=next(j for j in jobs if j['id']==name)
        request=next(r for r in contract['requests'] if r['id']==name)
        require(request==dict(id=name,sha256=job['request_sha256'],chars=len(job['text'])),'probe_request')
        folder=DEST/name
        result=read_json(folder/'RESULT.json')
        binding=dict(contract_sha256=digest(canonical(contract)),request_sha256=job['request_sha256'],
                     request_chars=len(job['text']))
        require(read_json(folder/'INTENT.json')==dict(binding=binding,max_api_calls=1),'probe_intent')
        require(result['binding']==binding,'response_binding')
        require(result['response_sha256']==digest(canonical(result['response'])),'response_hash')
        projection=project(result['response'],job['text'],job['mappings'])
        require(projection==read_json(folder/'PROJECTION.json'),'projection_recompute')
        findings.append(dict(job=name,projection_passed=not projection['held'],
                             held_units=len(projection['held']),
                             held_reasons=[h['reason'] for h in projection['held']],
                             result_sha256=digest((folder/'RESULT.json').read_bytes())))
    intents=list(DEST.glob('*/INTENT.json'))
    require(len(intents)==3,'probe_attempt_count')
    old_count,old_chars=inventory(BASE)
    chars=sum(r['chars'] for r in contract['requests'])
    report=read_json(DEST/'REPORT.json')
    require(report['combined_calls']==old_count+3 and report['combined_chars']==old_chars+chars,'combined_budget')
    result=dict(schema='wsd_jointing_probe_audit.v1',integrity_passed=True,
                baseline_artifacts_unchanged=True,frozen_input_reconstructed=True,
                new_calls=3,new_chars=chars,combined_calls=old_count+3,combined_chars=old_chars+chars,
                findings=findings,all_projection_passed=all(f['projection_passed'] for f in findings),
                no_final_merge=True,production_ready=False,semantic_improvement_established=False)
    atomic(ROOT/'outputs/reports/AUDIT_wsd_conversation_jointing_probe_20260905.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__': main()

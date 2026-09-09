"""Validate candidate-constrained model responses without calling a service."""
import argparse,json
from pathlib import Path

def validate(request,response):
    if not isinstance(response,dict) or response.get('request_id')!=request['request_id']:raise ValueError('response request identity differs')
    decisions=response.get('decisions')
    if not isinstance(decisions,list):raise ValueError('decisions must be a list')
    targets={t['target_id']:t for t in request['targets']}
    if len(targets)!=len(request['targets']):raise ValueError('duplicate request target')
    context_ids={u['utt_id'] for u in request['context']};seen=set();result=[]
    for d in decisions:
        if not isinstance(d,dict):raise ValueError('invalid decision')
        tid=d.get('target_id')
        if not isinstance(tid,str) or tid not in targets or tid in seen:raise ValueError('unknown or repeated target')
        seen.add(tid)
        if 'selected_group' not in d:raise ValueError('decision must explicitly select or abstain')
        selected=d['selected_group'];evidence=d.get('evidence_utt_ids');reason=d.get('reason')
        if selected is not None and selected not in targets[tid]['candidate_groups']:raise ValueError('selection outside candidate set')
        if not isinstance(evidence,list) or any(not isinstance(u,str) or u not in context_ids for u in evidence):raise ValueError('evidence outside provided context')
        if selected is not None and not evidence:raise ValueError('selected group requires a cited utterance')
        if not isinstance(reason,str) or not reason.strip():raise ValueError('explanation required')
        result.append({'target_id':tid,'selected_group':selected,'status':'external_machine_choice_unvalidated' if selected is not None else 'abstained','evidence_utt_ids':evidence,'reason':reason,'human_gold':False})
    if seen!=set(targets):raise ValueError('missing target decisions')
    return {'request_id':request['request_id'],'decisions':result,'schema_validation':'passed','semantic_accuracy_validated':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--response',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    result=validate(json.loads(a.request.read_text(encoding='utf-8-sig')),json.loads(a.response.read_text(encoding='utf-8-sig')))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

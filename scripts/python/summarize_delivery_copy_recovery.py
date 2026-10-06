"""Interpret small copy STATE snapshots without scanning the payload or ledger."""
import argparse
import json
from pathlib import Path
from datetime import datetime


def summarize(current, expected_pid, prior_checkpoint, previous=None):
    for key in ('files','bytes','total_files','total_bytes'):
        if not isinstance(prior_checkpoint[key],int) or prior_checkpoint[key]<0:
            raise ValueError('Invalid checkpoint counter')
    result=dict(expected_pid=expected_pid, state_pid=current.get('pid'),
        state_belongs_to_current_runner=current.get('pid')==expected_pid,
        recorded_pre_shutdown_checkpoint=prior_checkpoint,
        recorded_checkpoint_is_freshly_revalidated=False,
        current_pass=None, interval=None, whole_copy_eta_hours=None,
        delivery_complete=False)
    if current.get('pid')!=expected_pid:
        result['interpretation']='Awaiting first STATE from the restarted runner; old STATE is historical.'
        return result
    for key in ('files','bytes'):
        if not isinstance(current.get(key),int) or not 0<=current[key]<=prior_checkpoint['total_'+key]:
            raise ValueError('Invalid current-pass counter')
    if (current.get('total_files'),current.get('total_bytes'))!=(prior_checkpoint['total_files'],prior_checkpoint['total_bytes']):
        raise ValueError('Scope changed across restart')
    reached=current['files']>=prior_checkpoint['files'] and current['bytes']>=prior_checkpoint['bytes']
    result['recorded_checkpoint_is_freshly_revalidated']=reached
    result['current_pass']=current
    result['interpretation']=('Past the recorded pre-shutdown checkpoint; counters still cover this pass.' if reached else
        'Revalidating the recorded prefix; lower counters do not establish deleted or lost copies.')
    if previous and previous.get('pid')==expected_pid:
        seconds=(datetime.fromisoformat(current['updated_at'])-datetime.fromisoformat(previous['updated_at'])).total_seconds()
        if seconds>=1800 and current['files']>=previous.get('files',0) and current['bytes']>=previous.get('bytes',0):
            result['interval']=dict(minutes=seconds/60,files_per_second=(current['files']-previous['files'])/seconds,
                bytes_per_second=(current['bytes']-previous['bytes'])/seconds,
                limits='Same PID and nondecreasing counters only. File-type and revalidation/copy boundaries still require inspection; no full ETA inferred.')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--recovery',type=Path,required=True)
    p.add_argument('--expected-pid',type=int,required=True)
    a=p.parse_args()
    read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
    recovery = read(a.recovery)
    checkpoint = recovery.get('prior_retained_checkpoint', recovery['last_copy_state'])
    print(json.dumps(summarize(read(a.state),a.expected_pid,checkpoint),ensure_ascii=False,indent=2))

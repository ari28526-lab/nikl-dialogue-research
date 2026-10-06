"""Bounded, timeout-isolated source evidence discovery. Never full audio coverage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import wave
from datetime import datetime, timezone

MAX_BYTES=2*1024*1024
def digest(raw):return hashlib.sha256(raw).hexdigest()
def bounded(path):
    with open(path,'rb') as handle:raw=handle.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('Audio/document sample exceeds bound')
    return raw
def probe(request):
    kind=request['kind']
    if kind=='document_directory':
        rows=[];count=0
        # Exactly one declared directory; no recursion into PCM/session folders.
        with os.scandir(request['path']) as entries:
            for entry in entries:
                count+=1
                if count>250:raise ValueError('Directory exceeds bounded metadata probe')
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(('.pdf','.txt','.md')):
                    rows.append(dict(path=entry.path,bytes=entry.stat(follow_symlinks=False).st_size))
        return dict(status='bounded_directory_read',entries_seen=count,document_candidates=rows,
                    reviewed=False,source_modified=False)
    if kind=='pcm_wav':
        raw=bounded(request['pcm']);bounded(request['wav'])
        with wave.open(request['wav'],'rb') as wav:
            header=dict(sample_rate=wav.getframerate(),channels=wav.getnchannels(),sample_width_bytes=wav.getsampwidth(),frames=wav.getnframes())
            payload=wav.readframes(wav.getnframes())
        if header['sample_rate']!=16000 or header['channels']!=1 or header['sample_width_bytes']!=2:
            raise ValueError('Observed WAV encoding differs')
        return dict(status='listed_pair_checked',pcm_sha256=digest(raw),wav_payload_sha256=digest(payload),
                    payload_equal=raw==payload,pcm_bytes=len(raw),wav_header=header,
                    full_coverage_verified=False,source_modified=False)
    raise ValueError('Unknown bounded probe')

def isolated(request,timeout=20):
    started=time.monotonic()
    # No PIPE communicate/automatic context wait: blocked device cancellation
    # can itself stall on Windows. Preserve local probe files if exit unconfirmed.
    folder=Path(tempfile.mkdtemp(prefix='delivery_audio_probe_'))
    stdin=folder/'request.json';stdout=folder/'stdout.json';stderr=folder/'stderr.txt'
    stdin.write_text(json.dumps(request),encoding='utf-8')
    try:
        with stdin.open('rb') as i,stdout.open('wb') as o,stderr.open('wb') as e:
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child'],stdin=i,stdout=o,stderr=e)
        child.wait(timeout=timeout)
        if child.returncode:return dict(status='probe_error',pid=child.pid,elapsed_seconds=time.monotonic()-started,error=stderr.read_text(encoding='utf-8',errors='replace')[-2000:],probe_files=str(folder))
        return json.loads(stdout.read_text(encoding='utf-8'))
    except subprocess.TimeoutExpired:
        exit_confirmed=False
        try:
            child.kill();child.wait(timeout=2);exit_confirmed=True
        except (subprocess.TimeoutExpired,OSError):pass
        return dict(status='probe_timeout',pid=child.pid,exit_confirmed=exit_confirmed,
                    elapsed_seconds=time.monotonic()-started,probe_files=str(folder),
                    error='Termination requested; exit independently bounded. No inference of missing source data')

def build(plan, prior, output, timeout=20):
    if len(plan['document_directories'])!=5 or [x['year'] for x in plan['document_directories']]!=list(range(2021,2026)):
        raise ValueError('Explicit 2021–2025 scope required')
    if prior['full_coverage_verified'] is not False or len(prior['pairs'])>6:raise ValueError('Bounded prior pairs required')
    results=[];unavailable=False
    for item in plan['document_directories']:
        if unavailable:
            result=dict(status='not_attempted_after_unavailable_root')
        else:
            result=isolated(dict(kind='document_directory',path=item['path']),timeout)
            unavailable=result['status'] in {'probe_timeout','probe_error'}
        results.append(dict(year=item['year'],path=item['path'],result=result))
    pairs=[]
    # After root timeout do not launch more reads against the same source drive.
    for item in prior['pairs']:
        result=(dict(status='not_attempted_after_unavailable_root') if unavailable else
                isolated(dict(kind='pcm_wav',pcm=item['pcm'],wav=item['wav']),timeout))
        if result['status']=='listed_pair_checked':
            if not result['payload_equal'] or result['pcm_sha256']!=item['pcm_sha256'] or result['wav_payload_sha256']!=item['wav_payload_sha256']:
                raise ValueError('Prior PCM/WAV sample evidence changed')
        pairs.append(dict(year=item['year'],utterance_id=item['utterance_id'],result=result,
                          preserved_prior_payload_equal=item['payload_equal'],freshly_verified=result['status']=='listed_pair_checked'))
    value=dict(schema='bounded_audio_scope_evidence.v1',status='partial_audio_scope_evidence',
               checked_at=datetime.now(timezone.utc).isoformat(),document_probes=results,sample_pairs=pairs,
               full_coverage_verified=False,official_2021_2025_scope_reviewed=False,delivery_complete=False,
               source_modified=False,api_calls=0,
               limitations=['Document candidates require actual content/page review.',
                            'Listed-pair equality is not full PCM/WAV correspondence.',
                            'Timeout is not proof of absent raw data.',
                            'No full-session audio or per-clip offset is inferred.'],
               next_step='Review bounded official document candidates and register year-specific audio provenance before final acceptance')
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Existing evidence receipt; use a new timestamp')
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if json.loads(output.read_text(encoding='utf-8'))!=value:raise ValueError('Evidence readback differs')
    return value

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--child',action='store_true');ap.add_argument('--plan',type=Path)
    ap.add_argument('--prior-pairs',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--timeout',type=float,default=20)
    args=ap.parse_args()
    if args.child:print(json.dumps(probe(json.loads(sys.stdin.read())),ensure_ascii=True))
    else:
        if not 1<=args.timeout<=30:raise ValueError('Bounded timeout required')
        value=build(json.loads(args.plan.read_text(encoding='utf-8-sig')),json.loads(args.prior_pairs.read_text(encoding='utf-8-sig')),args.output,args.timeout)
        print(json.dumps(dict(status=value['status'],source_modified=False,delivery_complete=False),ensure_ascii=True))

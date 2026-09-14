"""Seoul KOINA: genuine upstream pitch/Momel, explicit frame-clock adapter.

All source intervals and raw predictions are retained. Boundary extrapolations
are separate from internal machine candidates, never clipped into observations.
"""
import argparse,bisect,collections,csv,gzip,hashlib,json,math,os,re,shlex,shutil,subprocess,sys,time,wave
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics
from run_seoul_koina_pilot import read,sha,save,csvwrite,interval_index,PROJECT,BASE,UP,BINARY,SOURCES

OLD=data_path('koina_v1')
PILOT=data_path('koina_clock')
FULL=BASE/'52_KOINA_FULL_V2_20260911'
CLOCK=PROJECT/'work/koina_seoul_20260911/MOMEL_CLOCK_VALIDATION.json'
OUT=PILOT

def status(**kw):
    kw.update(pid=os.getpid(),updated_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
    save(OUT/'STATE.json',kw);print(json.dumps(kw,ensure_ascii=True),flush=True)

def frame_bounds(times,start,end):
    """Half-open sound interval, using actual Praat frame centers."""
    return bisect.bisect_left(times,start),bisect.bisect_left(times,end)

def point_quality(ms,hz,n,position,count,low,high):
    if not math.isfinite(ms) or not math.isfinite(hz):return 'invalid',['nonfinite']
    outside=ms<0 or ms>(n-1)*10+1e-6
    kind=('boundary_extrapolation' if position in (0,count-1) else 'outside_input_span') if outside else 'internal_target'
    flags=[]
    if hz<=0:flags.append('nonpositive_f0')
    if low is None:flags.append('no_filtered_voiced_support')
    elif hz<low or hz>high:flags.append('outside_recording_filtered_f0_range')
    if kind=='outside_input_span':flags.append('nonendpoint_outside_input')
    return kind,flags

def verify_result(dest):
    result=read(dest/'RESULT.json')
    for item in result['artifacts']:
        p=dest/item['name'];assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],str(p)
    return result

def algorithm_contract():
    runtime=read(PROJECT/'work/koina_seoul_20260911/RUNTIME_VALIDATION.json')
    clock=read(CLOCK)
    assert clock['status']=='passed' and clock['binary_sha256']==sha(BINARY)==runtime['momel_sha256']
    for name,h in runtime['source_sha256'].items():assert sha(UP/'src'/name)==h
    import importlib.metadata
    for pkg,version in runtime['versions'].items():assert importlib.metadata.version(pkg)==version
    return dict(schema='seoul_koina_clock_adapter.v2',runner_sha256=sha(__file__),helper_sha256=sha(PROJECT/'scripts/python/run_seoul_koina_pilot.py'),
        clock_validation_sha256=sha(CLOCK),runtime=runtime,pitch_sex_argument='',n_jobs=1,
        frame_selection='start <= actual Praat frame center < end',model_clock='first_selected_frame_time + model_ms / 1000',
        clipping=False,boundary_extrapolation='preserved separately; excluded from internal candidate TextGrid',human_verified=False,mfa=False,upload=False)

def preflight(scope):
    assert sys.platform=='linux'
    algorithm=algorithm_contract()
    assert read(BASE/'45_SCOPE_COMPLETION_20260911/COMPLETE/FINAL.json')['unexpected_excluded_transcribed_intervals']==0
    audit=read(BASE/'45_SCOPE_COMPLETION_20260911/SCOPE_AUDIT.json')
    records=sorted(audit['recordings'],key=lambda x:x['source_file'])
    assert len(records)==240 and len({x['source_file'] for x in records})==240
    if scope=='pilot':records=[x for x in records if x['source_file'] in SOURCES]
    else:
        gate=read(PILOT/'FINAL.json');assert gate['technical_gate_passed'] and gate['recordings']==2
        assert read(PILOT/'CONTRACT.json')['algorithm']==algorithm,'pilot_algorithm_changed'
    sources=[]
    for x in records:
        sid=x['source_file'];wav=BASE/'00_SOURCE/00_file'/(sid+'.wav');tg=wav.with_suffix('.TextGrid')
        sourcejson=BASE/'45_SCOPE_COMPLETION_20260911/MERGED_BAREUN/json'/(sid+'.json')
        assert sha(wav)==x['wav_sha256'] and sha(tg)==x['textgrid_sha256']
        sources.append(dict(source_file=sid,wav_sha256=x['wav_sha256'],textgrid_sha256=x['textgrid_sha256'],source_json_sha256=sha(sourcejson),duration_seconds=x['duration_seconds']))
    assert shutil.disk_usage(BASE).free>30*2**30,'disk_floor_30GiB'
    contract=dict(schema='seoul_koina_run.v2',scope=scope,algorithm=algorithm,sources=sources)
    if (OUT/'CONTRACT.json').exists():assert read(OUT/'CONTRACT.json')==contract,'contract_changed'
    else:save(OUT/'CONTRACT.json',contract)
    return contract

def parse_model(text):
    out=[]
    for line in text.splitlines():
        if line.strip():
            pair=line.split();assert len(pair)==2,'malformed_model_line'
            out.append(tuple(map(float,pair)))
    return out

def run_binary(values,settings):
    assert 0<len(values)<99999,'momel_binary_input_limit'
    assert all(math.isfinite(v) and v>=0 for v in values)
    raw=''.join(str(float(v))+'\n' for v in values).encode()
    r=subprocess.run([str(BINARY),*shlex.split(settings['momel_parameters'])],input=raw,capture_output=True,timeout=90)
    assert r.returncode==0,('momel_failed',r.returncode,r.stderr.decode(errors='replace')[:200])
    return raw,r.stdout.decode(),r.stderr.decode(errors='replace')

def load_old_cache(sid,item,settings):
    """Reuse only verified original frame data; replay every original Momel call."""
    oldcontract=read(OLD/'CONTRACT.json')
    assert oldcontract['runtime']['runtime_settings']==settings and oldcontract['pitch_sex_argument']==''
    assert next(x for x in oldcontract['sources'] if x['source_file']==sid)==item
    result=verify_result(OLD/sid)
    with (OLD/sid/'f0_frames.csv').open(encoding='utf-8-sig',newline='') as f:
        frames=list(csv.DictReader(f))
    times=[float(x['time_seconds']) for x in frames];f0=[float(x['f0_hz']) for x in frames]
    kept=[x['koina_filter_retained']=='True' for x in frames]
    segments=[]
    with gzip.open(OLD/sid/'raw_momel.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            rec=json.loads(line);raw,model,stderr=run_binary(rec['input_f0'],settings)
            assert hashlib.sha256(raw).hexdigest()==rec['input_sha256']
            assert hashlib.sha256(model.encode()).hexdigest()==rec['model_sha256'],'old_momel_not_reproducible'
            segments.append((rec['start'],rec['end']))
    assert len(times)==result['frames']
    return times,f0,kept,segments,len(segments)

def write_grid(tgpath,dest,data,duration,points):
    import parselmouth
    from parselmouth.praat import call
    raw=tgpath.read_bytes();enc='utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig'
    original=raw.decode(enc)
    changed,n=re.subn(r'(?m)^(\s*size\s*=\s*)7\s*$',r'\g<1>8',original,count=1);assert n==1
    chosen=[p for p in points if p['internal_candidate']]
    # Input sound segments do not overlap. Never silently deduplicate targets.
    assert len({p['time_seconds'] for p in chosen})==len(chosen),'duplicate_internal_target_time'
    chosen.sort(key=lambda x:x['time_seconds'])
    addition=f'\n    item [8]:\n        class = "TextTier"\n        name = "KOINA_Momel_INTERNAL_MACHINE"\n        xmin = 0\n        xmax = {duration!r}\n        points: size = {len(chosen)}\n'
    for i,p in enumerate(chosen,1):addition+=f'        points [{i}]:\n            number = {p["time_seconds"]!r}\n            mark = "{p["model_f0_hz"]:.3f}"\n'
    path=dest/'original_plus_momel_INTERNAL_MACHINE.TextGrid';path.write_text(changed+addition,encoding='utf-8')
    check=parselmouth.read(str(path));assert call(check,'Get number of tiers')==8
    for ti,tier in enumerate(data['tiers'],1):
        assert call(check,'Get number of intervals',ti)==len(tier['intervals'])
        for ii,u in enumerate(tier['intervals'],1):
            assert call(check,'Get label of interval',ti,ii)==u['text']
            assert call(check,'Get start time of interval',ti,ii)==u['start'] and call(check,'Get end time of interval',ti,ii)==u['end']
    return len(chosen)

def run_source(item,contract):
    import numpy as np
    import parselmouth
    from parselmouth.praat import call
    sid=item['source_file'];dest=OUT/sid
    # The validated pilot uses exactly the same algorithm and source hashes.
    if OUT==FULL and sid in SOURCES:
        pilotcontract=read(PILOT/'CONTRACT.json')
        assert pilotcontract['algorithm']==contract['algorithm']
        assert next(x for x in pilotcontract['sources'] if x['source_file']==sid)==item
        result=verify_result(PILOT/sid);return dict(result,result_directory=str(PILOT/sid),reused_validated_pilot=True)
    if (dest/'RESULT.json').exists():return verify_result(dest)
    assert shutil.disk_usage(BASE).free>30*2**30,'disk_floor_30GiB'
    dest.mkdir(exist_ok=True);started=time.monotonic()
    wav=BASE/'00_SOURCE/00_file'/(sid+'.wav');tgpath=wav.with_suffix('.TextGrid')
    jp=BASE/'45_SCOPE_COMPLETION_20260911/MERGED_BAREUN/json'/(sid+'.json')
    assert sha(wav)==item['wav_sha256'] and sha(tgpath)==item['textgrid_sha256'] and sha(jp)==item['source_json_sha256']
    data=read(jp);utterances=data['tiers'][6]['intervals'];ends=[u['end'] for u in utterances]
    duration=item['duration_seconds'];settings=contract['algorithm']['runtime']['runtime_settings'];sm=data['speaker_metadata']
    with wave.open(str(wav),'rb') as w:assert w.getframerate()==22050 and w.getnchannels()==1
    replayed=0
    if sid in SOURCES:
        status(status='running',stage='replay_and_verify_old_pilot',source_file=sid)
        times,f0,kept,segments,replayed=load_old_cache(sid,item,settings)
        pitch_origin='verified_original_pilot_cache'
    else:
        status(status='running',stage='pitch',source_file=sid)
        sys.path.insert(0,str(UP/'src'))
        from transcribe import pitch as kp
        sound=parselmouth.Sound(str(wav));assert abs(sound.get_total_duration()-duration)<1e-8
        pitch=kp.extract_pitch(sound,'',settings);times,f0=kp.extract_pitch_data(pitch)
        ct,cf=kp.remove_doubling_halving(times,f0);keep={round(t,6) for t in ct};kept=[round(t,6) in keep for t in times]
        sil=call(sound,'To TextGrid (silences)',70,settings['time_step'],settings['sil_thresh'],.25,.05,settings['sil_label'],settings['snd_label'])
        segments=[(call(sil,'Get start time of interval',1,i),call(sil,'Get end time of interval',1,i)) for i in range(1,call(sil,'Get number of intervals',1)+1) if call(sil,'Get label of interval',1,i)==settings['snd_label']]
        pitch_origin='genuine_upstream_pitch_extraction'
    assert times and len(times)==len(f0)==len(kept)
    assert all(math.isfinite(t) and 0<=t<duration for t in times)
    assert all(abs((b-a)-.01)<1e-8 for a,b in zip(times,times[1:]))
    positive=[v for v,k in zip(f0,kept) if k and v>0];low=min(positive) if positive else None;high=max(positive) if positive else None
    points=[];calls=[]
    with gzip.open(dest/'raw_momel.jsonl.gz','wt',encoding='utf-8') as trace:
        for k,(a,b) in enumerate(segments):
            fi,stop=frame_bounds(times,a,b);values=[f0[i] if kept[i] else 0. for i in range(fi,stop)]
            assert all(a<=t<b for t in times[fi:stop]),'frame_outside_sound_interval'
            if not values:raw=b'';model='';stderr='';state='no_pitch_frames'
            elif not any(v>0 for v in values):raw=''.join(str(float(v))+'\n' for v in values).encode();model='';stderr='';state='no_filtered_voiced_frames'
            else:raw,model,stderr=run_binary(values,settings);state='model_returned'
            modeled=parse_model(model);first=times[fi] if values else None
            rec=dict(segment_index=k,start=a,end=b,first_frame_index=fi,last_frame_index=stop-1,first_frame_time=first,input_frames=len(values),
                input_sha256=hashlib.sha256(raw).hexdigest(),model_sha256=hashlib.sha256(model.encode()).hexdigest(),status=state,
                model_points=len(modeled),input_voiced_frames=sum(v>0 for v in values),raw_process_called=state=='model_returned')
            trace.write(json.dumps(dict(**rec,input_f0=values,model_text=model,stderr=stderr),ensure_ascii=False)+'\n')
            local=[]
            for pi,(ms,hz) in enumerate(modeled):
                kind,flags=point_quality(ms,hz,len(values),pi,len(modeled),low,high)
                t=first+ms/1000 if math.isfinite(ms) else None
                within=t is not None and 0<=t<duration
                if not within:flags.append('outside_recording_clock')
                candidate=kind=='internal_target' and not flags
                ui=interval_index(ends,t) if within else None
                uid=f"seoul:{sid}:t7:i{utterances[ui]['interval_index']}" if ui is not None else None
                if candidate:assert a<=t<b and times[fi]-1e-6<=t<=times[stop-1]+1e-6
                local.append(dict(source_file=sid,segment_index=k,point_index=pi,model_relative_ms=ms if math.isfinite(ms) else None,
                    model_f0_hz=hz if math.isfinite(hz) else None,time_seconds=t,point_kind=kind,quality_flags='|'.join(flags),
                    internal_candidate=candidate,utt_id=uid,utt_join_role='internal_candidate' if candidate else 'coordinate_context_only',human_verified=False))
            rec['internal_candidates']=sum(p['internal_candidate'] for p in local)
            rec['point_kind_counts']=dict(collections.Counter(p['point_kind'] for p in local))
            rec['candidate_status']='internal_candidates' if rec['internal_candidates'] else 'no_internal_candidate'
            points.extend(local);calls.append(rec)
            if k%50==0:status(status='running',stage='momel',source_file=sid,completed_segments=k+1,total_segments=len(segments))
    bins=[[] for _ in utterances];frames=[]
    for i,(t,hz,keep) in enumerate(zip(times,f0,kept)):
        ui=interval_index(ends,t);u=utterances[ui];assert u['start']<=t<u['end']
        frames.append(dict(source_file=sid,frame_index=i,time_seconds=t,f0_hz=hz,voiced=hz>0,koina_filter_retained=keep,
            utt_id=f"seoul:{sid}:t7:i{u['interval_index']}",annotation=u['text'],human_verified=False))
        bins[ui].append((hz,keep))
    byutt=collections.Counter(p['utt_id'] for p in points if p['internal_candidate']);summaries=[]
    for u,ff in zip(utterances,bins):
        voiced=[x for x,k in ff if x>0];clean=[x for x,k in ff if x>0 and k];uid=f"seoul:{sid}:t7:i{u['interval_index']}"
        summaries.append(dict(source_file=sid,utt_id=uid,start=u['start'],end=u['end'],text=u['text'],
            annotation_class='interviewer_untranscribed' if u['text'].strip()=='<IVER>' else 'source_label_preserved',
            participant_id=sm['speaker_id'],participant_gender=sm['speaker_gender'],interviewer_gender=sm['interviewer_gender'],
            frames=len(ff),voiced_frames=len(voiced),filtered_voiced_frames=len(clean),f0_median_hz=float(np.median(voiced)) if voiced else None,
            filtered_f0_median_hz=float(np.median(clean)) if clean else None,internal_momel_candidates=byutt[uid],
            status='no_pitch_frames' if not ff else 'no_voiced_frames' if not voiced else 'measured',human_verified=False))
    assert sum(x['frames'] for x in summaries)==len(times)
    csvwrite(dest/'f0_frames.csv',frames);csvwrite(dest/'utterance_f0.csv',summaries)
    pointfields=['source_file','segment_index','point_index','model_relative_ms','model_f0_hz','time_seconds','point_kind','quality_flags','internal_candidate','utt_id','utt_join_role','human_verified']
    csvwrite(dest/'momel_points.csv',points,pointfields)
    csvwrite(dest/'momel_segments.csv',calls,['segment_index','start','end','first_frame_index','last_frame_index','first_frame_time','input_frames','input_sha256','model_sha256','status','model_points','input_voiced_frames','raw_process_called','internal_candidates','point_kind_counts','candidate_status'])
    gridcount=write_grid(tgpath,dest,data,duration,points)
    payload=dict(schema='seoul_koina_clock.source.v2',source_file=sid,source=item,algorithm=contract['algorithm'],
        speaker_metadata=sm,interviewer_metadata=data['interviewer_metadata'],original_tiers=data['tiers'],
        source_analysis_json=str(jp),utterance_f0=summaries,momel_points=points,momel_segments=calls,human_verified=False)
    with gzip.open(dest/'analysis.json.gz','wt',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,allow_nan=False)
    assert sha(wav)==item['wav_sha256'] and sha(tgpath)==item['textgrid_sha256'] and sha(jp)==item['source_json_sha256']
    result=dict(status='completed_machine_candidates',source_file=sid,result_directory=str(dest),source=item,
        duration_seconds=duration,elapsed_seconds=time.monotonic()-started,pitch_origin=pitch_origin,original_momel_calls_replayed=replayed,
        utterance_intervals=len(utterances),frames=len(frames),voiced_frames=sum(x['voiced'] for x in frames),momel_segments=len(calls),
        raw_momel_points=len(points),internal_candidates=gridcount,point_kind_counts=dict(collections.Counter(p['point_kind'] for p in points)),
        quality_flag_counts=dict(collections.Counter(flag for p in points for flag in p['quality_flags'].split('|') if flag)),
        segments_without_internal_candidate=sum(x['internal_candidates']==0 for x in calls),source_unchanged=True,all_original_tiers_verified=True,
        all_intervals_accounted=True,frame_clock_verified=True,human_verified=False,
        artifacts=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='RESULT.json'])
    save(dest/'RESULT.json',result);return verify_result(dest)

def consolidate(results,scope):
    # Stream combined tables; preserve per-recording JSON and trace provenance.
    for name in ('utterance_f0.csv','momel_points.csv'):
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as target:
            writer=None
            for r in results:
                with (Path(r['result_directory'])/name).open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f)
                    if writer is None:writer=csv.DictWriter(target,reader.fieldnames);writer.writeheader()
                    else:assert writer.fieldnames==reader.fieldnames
                    for row in reader:writer.writerow(row)
    for r in results:verify_result(Path(r['result_directory']))
    total={k:sum(r[k] for r in results) for k in ['utterance_intervals','frames','voiced_frames','momel_segments','raw_momel_points','internal_candidates','original_momel_calls_replayed']}
    assert len(results)==(2 if scope=='pilot' else 240)
    if scope=='full':assert total['utterance_intervals']==128313
    final=dict(status='completed_machine_candidates',technical_gate_passed=True,scope=scope,recordings=len(results),totals=total,
        sources=results,corpus_audio_uploaded=False,mfa_run=False,human_verified=False,
        limitations=['F0 and Momel are machine estimates, not validated prosodic or phonological findings.',
            'Boundary extrapolations and invalid/out-of-range points remain in JSON/CSV but are absent from the internal-candidate TextGrid.',
            'Mixed speaker recordings use common pitch range 75-600 Hz; participant metadata is not diarization.'],
        aggregate_artifacts=[dict(name=n,sha256=sha(OUT/n),bytes=(OUT/n).stat().st_size) for n in ('utterance_f0.csv','momel_points.csv')])
    save(OUT/'FINAL.json',final);status(status='completed_machine_candidates',recordings=len(results),**total)

def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('--scope',choices=['pilot','full'],default='pilot');ap.add_argument('--execute',action='store_true');args=ap.parse_args()
    OUT=PILOT if args.scope=='pilot' else FULL;OUT.mkdir(exist_ok=True)
    import fcntl
    with (OUT/'RUN.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            status(status='preflight_running',scope=args.scope);contract=preflight(args.scope)
            if not args.execute:status(status='preflight_passed',scope=args.scope,recordings=len(contract['sources']));return
            results=[]
            for item in contract['sources']:
                if (OUT/'STOP_REQUEST.json').exists():status(status='paused_at_recording_boundary',completed_recordings=len(results));return
                result=run_source(item,contract);results.append(result)
                save(OUT/'PROGRESS.json',dict(completed_recordings=len(results),total_recordings=len(contract['sources']),sources=results))
                status(status='running',stage='recording_complete',source_file=item['source_file'],completed_recordings=len(results),total_recordings=len(contract['sources']))
            consolidate(results,args.scope)
        except BaseException as e:status(status='paused_error',error_type=type(e).__name__,error=str(e));raise

if __name__=='__main__':main()

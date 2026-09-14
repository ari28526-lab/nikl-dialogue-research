"""Two complete Seoul recordings, genuine KOINA; retain raw Momel and QC holds."""
import argparse,bisect,collections,csv,gzip,hashlib,json,math,os,platform,re,shlex,shutil,subprocess,sys,tempfile,time,wave
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics

PROJECT=Path(__file__).resolve().parents[2]
BASE=drive_root()/'40_SEOUL_CORPUS';OUT=data_path('koina_v1')
UP=PROJECT/'work/koina_seoul_20260911/upstream';BINARY=Path('/opt/koina-seoul/bin/momel_linux')
SOURCES=['s01m16f1','s06f18m1']
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.partial')
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(8):
        try:tmp.replace(p);return
        except PermissionError:
            if attempt==7:raise
            time.sleep(.1*(attempt+1))
def status(**kw):
    kw.update(pid=os.getpid(),updated_at=time.strftime('%Y-%m-%dT%H:%M:%S'));save(OUT/'STATE.json',kw);print(json.dumps(kw,ensure_ascii=True),flush=True)
def csvwrite(p,rows,fields=None):
    rows=list(rows)
    if fields is None:fields=list(rows[0])
    with Path(p).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def interval_index(ends,t):return min(bisect.bisect_right(ends,t),len(ends)-1)
def raw_point_flags(ms,f0,n,input_min,input_max):
    flags=[]
    if not math.isfinite(ms) or not math.isfinite(f0):return ['nonfinite']
    if ms<0 or ms>(n-1)*10+1e-6:flags.append('outside_input_frame_span')
    if f0<=0:flags.append('nonpositive_f0')
    if f0<input_min or f0>input_max:flags.append('outside_recording_corrected_f0_range')
    return flags
def preflight():
    assert sys.platform=='linux' and platform.machine()=='x86_64'
    runtime=read(PROJECT/'work/koina_seoul_20260911/RUNTIME_VALIDATION.json')
    assert runtime['status']=='passed' and sha(BINARY)==runtime['momel_sha256']
    for name,h in runtime['source_sha256'].items():assert sha(UP/'src'/name)==h
    audit=read(BASE/'45_SCOPE_COMPLETION_20260911/SCOPE_AUDIT.json');source_audit={x['source_file']:x for x in audit['recordings']}
    final=read(BASE/'45_SCOPE_COMPLETION_20260911/COMPLETE/FINAL.json');assert final['unexpected_excluded_transcribed_intervals']==0
    source=[]
    for sid in SOURCES:
        wav=BASE/'00_SOURCE/00_file'/(sid+'.wav');tg=wav.with_suffix('.TextGrid');j=BASE/'45_SCOPE_COMPLETION_20260911/MERGED_BAREUN/json'/(sid+'.json')
        assert sha(wav)==source_audit[sid]['wav_sha256'] and sha(tg)==source_audit[sid]['textgrid_sha256']
        source.append(dict(source_file=sid,wav_sha256=sha(wav),textgrid_sha256=sha(tg),source_json_sha256=sha(j),duration_seconds=source_audit[sid]['duration_seconds']))
    assert shutil.disk_usage(BASE).free>30*2**30
    contract=dict(schema='seoul_koina_pilot.v1',sources=source,runner_sha256=sha(__file__),runtime=runtime,
        scope='two_full_recordings_including_all_untranscribed_regions',pitch_sex_argument='',pitch_range=[75,600],
        pitch_reason='Mixed participant and interviewer recording; use common upstream default range.',
        n_jobs=1,mfa=False,network=False,raw_momel_preserved=True,momel_times='upstream reported times plus separately labelled provisional frame-origin times',human_verified=False)
    if (OUT/'CONTRACT.json').exists():assert read(OUT/'CONTRACT.json')==contract,'contract_changed'
    else:save(OUT/'CONTRACT.json',contract)
    return contract
def run_source(item,contract):
    import numpy as np
    import parselmouth
    from parselmouth.praat import call
    import textgrid
    sid=item['source_file'];dest=OUT/sid;dest.mkdir(exist_ok=True)
    if (dest/'RESULT.json').exists():
        old=read(dest/'RESULT.json')
        for a in old['artifacts']:assert sha(dest/a['name'])==a['sha256']
        return old
    started=time.monotonic();scratch=Path(tempfile.mkdtemp(prefix=sid+'_',dir='/opt/koina-seoul/validation'));os.chdir(scratch)
    sys.path.insert(0,str(UP/'src'))
    from transcribe import pitch as kp,momel
    wav=BASE/'00_SOURCE/00_file'/(sid+'.wav');tgpath=wav.with_suffix('.TextGrid')
    data=read(BASE/'45_SCOPE_COMPLETION_20260911/MERGED_BAREUN/json'/(sid+'.json'))
    utterances=data['tiers'][6]['intervals'];ends=[u['end'] for u in utterances]
    sm=data['speaker_metadata'];duration=item['duration_seconds'];settings=contract['runtime']['runtime_settings'].copy()
    with wave.open(str(wav),'rb') as w:rate=w.getframerate();channels=w.getnchannels()
    assert rate==22050 and channels==1
    status(status='running',stage='pitch',source_file=sid)
    sound=parselmouth.Sound(str(wav));assert abs(sound.get_total_duration()-duration)<1e-8
    pitch=kp.extract_pitch(sound,'',settings)
    times,f0=kp.extract_pitch_data(pitch);corrected_t,corrected_f0=kp.remove_doubling_halving(times,f0)
    corrected_set={round(t,6) for t in corrected_t};positive=[v for v in corrected_f0 if v>0]
    assert positive and all(math.isfinite(t) and 0<=t<=duration for t in times)
    assert all(abs((b-a)-.01)<1e-8 for a,b in zip(times,times[1:]))
    lo,hi=min(positive),max(positive)
    sil=call(sound,'To TextGrid (silences)',70,settings['time_step'],settings['sil_thresh'],.25,.05,settings['sil_label'],settings['snd_label'])
    segments=[(call(sil,'Get start time of interval',1,i),call(sil,'Get end time of interval',1,i)) for i in range(1,call(sil,'Get number of intervals',1)+1) if call(sil,'Get label of interval',1,i)==settings['snd_label']]
    calls=[];raw_points=[];traces=dest/'raw_momel.jsonl.gz';trace=gzip.open(traces,'wt',encoding='utf-8')
    def checked_run(cmd,f0_name,model_name,params):
        k=len(calls);a,b=segments[k];assert f0_name==f'part_{a:.3f}_{b:.3f}.f0'
        fi=max(0,int(a/.01));fj=min(len(times)-1,int(b/.01));ip=Path('out/models')/f0_name;op=Path('out/models')/model_name
        values=[float(x) for x in ip.read_text().splitlines()]
        expected=[f0[i] if round(times[i],6) in corrected_set else 0. for i in range(fi,fj+1)]
        assert values==expected and values,'momel_input_projection'
        with ip.open('rb') as inp,op.open('wb') as out:
            r=subprocess.run([str(BINARY),*shlex.split(params)],stdin=inp,stdout=out,stderr=subprocess.PIPE,timeout=90)
        assert r.returncode==0,('momel_process_failed',k,r.returncode)
        model_text=op.read_text();points=[list(map(float,line.split())) for line in model_text.splitlines() if line.strip()]
        delta=times[fi]-a
        record=dict(segment_index=k,start=a,end=b,first_frame_index=fi,last_frame_index=fj,first_frame_time=times[fi],time_origin_delta_ms=delta*1000,
            input_frames=len(values),input_sha256=sha(ip),model_sha256=sha(op),return_code=r.returncode,raw_points=len(points),stderr=r.stderr.decode(errors='replace'))
        trace.write(json.dumps(dict(**record,input_f0=values,model_text=model_text),ensure_ascii=False)+'\n');trace.flush();calls.append(record)
        for pi,(ms,hz) in enumerate(points):
            flags=raw_point_flags(ms,hz,len(values),lo,hi);reported=max(0.,min(a+ms/1000,duration));candidate=times[fi]+ms/1000
            raw_points.append(dict(source_file=sid,segment_index=k,point_index=pi,model_relative_ms=ms,model_f0_hz=hz,
                koina_reported_time=reported,koina_clipped_f0_hz=max(min(hz,hi),lo),frame_origin_time_candidate=candidate,time_origin_delta_ms=delta*1000,
                utt_id_candidate=f"seoul:{sid}:t7:i{utterances[interval_index(ends,reported)]['interval_index']}",
                quality_flags='|'.join(flags),timing_status='requires_time_origin_review',human_verified=False))
        if k%25==0:status(status='running',stage='momel',source_file=sid,completed_segments=k+1,total_segments=len(segments))
    momel.run_momel_subprocess=checked_run
    grid=textgrid.TextGrid(minTime=0,maxTime=duration)
    try:ct,cf=momel.generate_momel_labels(sound,pitch,settings,grid,duration)
    finally:trace.close()
    assert ct==corrected_t and cf==corrected_f0 and len(calls)==len(segments)
    upstream=list(grid[-1].points);seen={}
    for p in raw_points:seen.setdefault(p['koina_reported_time'],f"{p['koina_clipped_f0_hz']:.2f}")
    assert [(p.time,p.mark) for p in upstream]==sorted(seen.items()),'upstream_point_projection'
    bins=[[] for _ in utterances];frames=[]
    for i,(t,hz) in enumerate(zip(times,f0)):
        ui=interval_index(ends,t);u=utterances[ui];assert u['start']<=t<=u['end']
        kept=round(t,6) in corrected_set
        frames.append(dict(source_file=sid,frame_index=i,time_seconds=t,f0_hz=hz,voiced=hz>0,koina_filter_retained=kept,
            utt_id=f"seoul:{sid}:t7:i{u['interval_index']}",annotation=u['text'],human_verified=False))
        bins[ui].append((hz,kept))
    summaries=[]
    for u,ff in zip(utterances,bins):
        voiced=[x for x,k in ff if x>0];clean=[x for x,k in ff if x>0 and k]
        summaries.append(dict(source_file=sid,utt_id=f"seoul:{sid}:t7:i{u['interval_index']}",start=u['start'],end=u['end'],text=u['text'],
            annotation_class='interviewer_untranscribed' if u['text'].strip()=='<IVER>' else 'source_label_preserved',
            participant_id=sm['speaker_id'],participant_gender=sm['speaker_gender'],interviewer_gender=sm['interviewer_gender'],
            frames=len(ff),voiced_frames=len(voiced),filtered_voiced_frames=len(clean),f0_median_hz=float(np.median(voiced)) if voiced else None,
            filtered_f0_median_hz=float(np.median(clean)) if clean else None,status='no_pitch_frames' if not ff else 'no_voiced_frames' if not voiced else 'measured',human_verified=False))
    csvwrite(dest/'f0_frames.csv',frames);csvwrite(dest/'utterance_f0.csv',summaries);csvwrite(dest/'momel_raw_points.csv',raw_points)
    csvwrite(dest/'momel_segments.csv',calls)
    # Keep the exact source text, changing only the global tier count, then append a clearly provisional tier.
    raw=tgpath.read_bytes();enc='utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig';original=raw.decode(enc)
    changed,n=re.subn(r'(?m)^(\s*size\s*=\s*)7\s*$',r'\g<1>8',original,count=1);assert n==1
    addition=f'\n    item [8]:\n        class = "TextTier"\n        name = "KOINA_Momel_REVIEW"\n        xmin = 0\n        xmax = {duration!r}\n        points: size = {len(upstream)}\n'
    for i,p in enumerate(upstream,1):addition+=f'        points [{i}]:\n            number = {p.time!r}\n            mark = "{p.mark}"\n'
    (dest/'original_plus_momel_REVIEW.TextGrid').write_text(changed+addition,encoding='utf-8')
    check=parselmouth.read(str(dest/'original_plus_momel_REVIEW.TextGrid'));assert call(check,'Get number of tiers')==8
    for ti,tier in enumerate(data['tiers'],1):
        assert call(check,'Get number of intervals',ti)==len(tier['intervals'])
        for ii,u in enumerate(tier['intervals'],1):
            assert call(check,'Get label of interval',ti,ii)==u['text']
            assert call(check,'Get start time of interval',ti,ii)==u['start'] and call(check,'Get end time of interval',ti,ii)==u['end']
    assert sha(wav)==item['wav_sha256'] and sha(tgpath)==item['textgrid_sha256']
    payload=dict(schema='seoul_koina_pilot.source.v1',source_file=sid,source=item,speaker_metadata=sm,interviewer_metadata=data['interviewer_metadata'],
        original_tiers=data['tiers'],utterance_f0=summaries,momel_points=raw_points,settings=settings,pitch_sex_argument='',human_verified=False,
        timing_warning='Upstream segmentation-origin times retained. Input first-frame clock differs; frame-origin alternatives remain provisional.')
    with gzip.open(dest/'analysis.json.gz','wt',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False)
    result=dict(status='completed_with_momel_review_holds',source_file=sid,duration_seconds=duration,elapsed_seconds=time.monotonic()-started,
        sample_rate=rate,utterance_intervals=len(utterances),frames=len(frames),voiced_frames=sum(x['voiced'] for x in frames),
        momel_segments=len(calls),raw_momel_points=len(raw_points),upstream_points=len(upstream),momel_flag_counts=dict(collections.Counter(flag for p in raw_points for flag in p['quality_flags'].split('|') if flag)),
        unflagged_raw_points=sum(not p['quality_flags'] for p in raw_points),time_origin_delta_ms_min=min(x['time_origin_delta_ms'] for x in calls),time_origin_delta_ms_max=max(x['time_origin_delta_ms'] for x in calls),
        source_unchanged=True,all_original_tiers_verified=True,all_intervals_accounted=True,frame_coordinates_verified=True,momel_timing_validated=False,
        scratch_directory=str(scratch),artifacts=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(dest.iterdir()) if p.is_file() and p.name!='RESULT.json'])
    save(dest/'RESULT.json',result);return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');a=ap.parse_args();OUT.mkdir(exist_ok=True)
    import fcntl
    with (OUT/'RUN.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            c=preflight()
            if not a.execute:status(status='preflight_passed',sources=SOURCES);return
            results=[run_source(x,c) for x in c['sources']]
            save(OUT/'FINAL.json',dict(status='pilot_completed_with_momel_review_holds',recordings=len(results),sources=results,corpus_audio_uploaded=False,mfa_run=False,full_corpus_run=False))
            status(status='pilot_completed_with_momel_review_holds',recordings=len(results),frames=sum(x['frames'] for x in results),raw_momel_points=sum(x['raw_momel_points'] for x in results))
        except BaseException as e:status(status='paused_error',error_type=type(e).__name__,error=str(e));raise
if __name__=='__main__':main()

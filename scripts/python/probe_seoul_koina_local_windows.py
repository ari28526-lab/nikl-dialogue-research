"""Bounded QC sensitivity pilot, never promoted to boundary/voicing ground truth."""
import bisect,csv,gzip,hashlib,json,os,sys,time
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics
import numpy as np
import parselmouth
from parselmouth.praat import call
from run_seoul_koina_pilot import read,sha,save,csvwrite,PROJECT,BASE,UP

OUT=data_path('koina_qc')
GATE=PROJECT/'outputs/reports/seoul_koina_repair_pilot_20260912/COMPLETION_GATE.json'

def run():
    import fcntl
    OUT.mkdir(exist_ok=True)
    with (OUT/'RUN.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        gate=read(GATE);assert gate['source_receipts']==240
        full=read(BASE/'52_KOINA_FULL_V2_20260911/FINAL.json');byid={r['source_file']:r for r in full['sources']}
        runtime=read(PROJECT/'work/koina_seoul_20260911/RUNTIME_VALIDATION.json')
        assert sha(UP/'src/transcribe/pitch.py')==runtime['source_sha256']['transcribe/pitch.py']
        contract=dict(schema='seoul_koina_local_window_diagnostic.v1',runner_sha256=sha(__file__),gate_sha256=sha(GATE),
            selected_sources=gate['pilot_sources'],pitch_source_sha256=runtime['source_sha256']['transcribe/pitch.py'],
            runtime_settings=runtime['runtime_settings'],core_seconds=20,context_seconds=2,pitch_silence_thresholds=[.03,.003],
            segment_thresholds=[-25.,-45.],n_jobs=1,source_edit=False,production_settings_changed=False,human_verified=False)
        if (OUT/'CONTRACT.json').exists():assert read(OUT/'CONTRACT.json')==contract
        else:save(OUT/'CONTRACT.json',contract)
        if (OUT/'FINAL.json').exists():print('already_completed');return
        os.chdir(OUT);sys.path.insert(0,str(UP/'src'))
        from transcribe import pitch as kp
        rows=[];sources=[];started=time.monotonic()
        for item in gate['pilot_sources']:
            sid=item['source_file'];record=byid[sid];wav=BASE/'00_SOURCE/00_file'/(sid+'.wav')
            assert sha(wav)==record['source']['wav_sha256']
            sound=parselmouth.Sound(str(wav));sr=sound.sampling_frequency;assert sr==22050
            samples=sound.values[0];duration=len(samples)/sr;peak=float(np.argmax(abs(samples)))/sr
            with (resolve_legacy_path(record['result_directory'])/'f0_frames.csv').open(encoding='utf-8-sig',newline='') as f:baseline=list(csv.DictReader(f))
            bt=np.array([float(x['time_seconds']) for x in baseline]);bf=np.array([float(x['f0_hz']) for x in baseline])
            dest=OUT/sid;dest.mkdir(exist_ok=True)
            centers=[('20pct',duration*.2),('50pct',duration*.5),('80pct',duration*.8),('peak',peak)]
            for wi,(label,center) in enumerate(centers):
                core_start=min(max(0.,center-10),duration-20);core_end=core_start+20
                ia=max(0,int((core_start-2)*sr));ib=min(len(samples),int((core_end+2)*sr))
                origin=ia/sr;clip=parselmouth.Sound(samples[ia:ib].copy(),sampling_frequency=sr)
                assert len(clip.values[0])==ib-ia and np.array_equal(clip.values[0],samples[ia:ib])
                clip.save(str(dest/(label+'.wav')),'WAV')
                # Saved clip is a listening derivative; original WAV bytes remain fixed.
                mask=(bt>=core_start)&(bt<core_end);base=bf[mask]
                stem=dict(source_file=sid,role=item['role'],window=label,core_start=core_start,core_end=core_end,
                    clip_sample_start=ia,clip_sample_end=ib,clip_origin_seconds=origin,
                    baseline_frames=len(base),baseline_voiced_frames=int(sum(base>0)),baseline_voiced_fraction=float(np.mean(base>0)),
                    core_peak=float(max(abs(samples[int(core_start*sr):int(core_end*sr)]))),human_verified=False)
                variants=[];pitchvariants=[]
                for threshold in (.03,.003):
                    settings=runtime['runtime_settings'].copy();settings['silence_threshold']=threshold
                    p=kp.extract_pitch(clip,'',settings);times,f0=kp.extract_pitch_data(p);ct,cf=kp.remove_doubling_halving(times,f0)
                    absolute=np.array(times)+origin;values=np.array(f0);core=(absolute>=core_start)&(absolute<core_end)
                    assert np.all(absolute>=origin) and np.all(absolute<ib/sr)
                    assert all(abs(b-a-.01)<1e-8 for a,b in zip(absolute,absolute[1:]))
                    keep={round(t,6) for t in ct};retained=np.array([round(t,6) in keep for t in times])
                    voiced=values[core]>0
                    pitchvariants.append(dict(pitch_silence_threshold=threshold,actual_frame_times=absolute.tolist(),f0_hz=f0,filter_retained=retained.tolist()))
                    for segthreshold in (-25.,-45.):
                        grid=call(clip,'To TextGrid (silences)',70,.01,segthreshold,.25,.05,'#','sound')
                        spans=[(call(grid,'Get start time of interval',1,k)+origin,call(grid,'Get end time of interval',1,k)+origin) for k in range(1,call(grid,'Get number of intervals',1)+1) if call(grid,'Get label of interval',1,k)=='sound']
                        insound=np.zeros(len(absolute),dtype=bool)
                        for a,b in spans:insound|=(absolute>=a)&(absolute<b)
                        supported=core&(values>0)&retained;den=int(sum(supported))
                        row=dict(**stem,pitch_silence_threshold=threshold,segment_silence_db=segthreshold,
                            local_frames=int(sum(core)),local_voiced_frames=int(sum(voiced)),local_voiced_fraction=float(np.mean(voiced)),
                            filtered_voiced_frames=den,momel_input_coverage=float(sum(supported&insound)/den) if den else None,
                            detected_sound_seconds=sum(max(0,min(b,core_end)-max(a,core_start)) for a,b in spans),
                            positive_f0_median_hz=float(np.median(values[core&(values>0)])) if sum(voiced) else None)
                        rows.append(row);variants.append(dict(**row,detected_sound_spans=spans))
                with gzip.open(dest/(label+'.json.gz'),'wt',encoding='utf-8') as f:json.dump(dict(**stem,variants=variants,pitch_variants=pitchvariants),f,ensure_ascii=False,allow_nan=False)
                save(OUT/'STATE.json',dict(status='running',source_file=sid,window=label,completed_rows=len(rows),pid=os.getpid()))
                print(json.dumps(dict(source_file=sid,window=label,completed_rows=len(rows))),flush=True)
            assert sha(wav)==record['source']['wav_sha256']
            sources.append(dict(source_file=sid,source_unchanged=True,artifacts=[dict(name=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(dest.iterdir())]))
        csvwrite(OUT/'comparison.csv',rows)
        result=dict(status='diagnostic_complete_not_promoted',recordings=len(sources),windows=16,comparison_rows=len(rows),
            elapsed_seconds=time.monotonic()-started,source_results=sources,human_accuracy_evaluated=False,AP_IP_boundaries_created=False,
            original_full_run_unchanged=True,comparison_sha256=sha(OUT/'comparison.csv'))
        assert len(rows)==64
        save(OUT/'FINAL.json',result);save(OUT/'STATE.json',dict(status=result['status'],pid=os.getpid(),windows=16,comparison_rows=len(rows)))
        print(json.dumps(result),flush=True)

if __name__=='__main__':run()

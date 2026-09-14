"""Independent persisted-output audit; requires TextGrid in the verified local WSL env."""
import argparse,csv,hashlib,json,wave
from collections import Counter,defaultdict
from pathlib import Path
import textgrid

def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(base,out,report):
    rows=json.loads((out/'candidates.json').read_text('utf-8'))
    with (out/'candidates.csv').open(encoding='utf-8-sig',newline='') as f:flat=list(csv.DictReader(f))
    assert len(rows)==len(flat)==48
    assert len(set(r['candidate_id'] for r in rows))==48
    groups=defaultdict(list)
    for r,c in zip(rows,flat):
        assert all((json.loads(c[k])==v if isinstance(v,(dict,list)) else
                    c[k]==('' if v is None else str(v))) for k,v in r.items() if k in c)
        assert not r['human_verified'] and r['manual_break_index'] is None
        if r['candidate_type'] in ('AP_candidate','IP_candidate'):
            assert not r['hold_reasons']
            assert len(set(r['parameter_classes']))==1
            assert not set(r['quality_flags']) & {'threshold_sensitive','local_pitch_settings_sensitive'}
        groups[r['source_file']].append(r)
    clip_count=0;intervals=0;points=0
    for name,selected in groups.items():
        # fromFile() silently rounds to five decimals; explicitly preserve source precision.
        orig=textgrid.TextGrid();orig.read(str(base/f'00_SOURCE/00_file/{name}.TextGrid'),round_digits=15)
        derived=textgrid.TextGrid();derived.read(str(out/f'textgrids/{name}_AP_IP_MACHINE_PILOT.TextGrid'),round_digits=15)
        assert len(orig.tiers)==7 and len(derived.tiers)==8
        for old,new in zip(orig.tiers,derived.tiers[:7]):
            assert old.name==new.name and len(old.intervals)==len(new.intervals)
            assert abs(old.minTime-new.minTime)<1e-6 and abs(old.maxTime-new.maxTime)<1e-6
            for a,b in zip(old.intervals,new.intervals):
                assert a.mark==b.mark and abs(a.minTime-b.minTime)<1e-6 and abs(a.maxTime-b.maxTime)<1e-6
                intervals+=1
        ordered=sorted(selected,key=lambda r:r['boundary_seconds'])
        assert len(derived.tiers[7].points)==len(ordered)
        for p,r in zip(derived.tiers[7].points,ordered):
            assert abs(p.time-r['boundary_seconds'])<1e-6
            assert p.mark==r['candidate_type']+'|'+r['candidate_id']
            w=orig.tiers[4].intervals[r['word_interval_index']-1]
            assert abs(w.maxTime-r['boundary_seconds'])<1e-6
            if r['utt_id']:
                u=orig.tiers[6].intervals[int(r['utt_id'].split(':i')[-1])-1]
                assert u.minTime<=w.minTime+1e-6 and w.maxTime<=u.maxTime+1e-6
            points+=1
        with wave.open(str(base/f'00_SOURCE/00_file/{name}.wav'),'rb') as original:
            for r in selected:
                with wave.open(str(out/r['clip_relative_path']),'rb') as clip:
                    assert clip.getframerate()==original.getframerate()==22050
                    assert clip.getnchannels()==original.getnchannels()==1
                    assert clip.getnframes()==r['clip_end_sample']-r['clip_start_sample']
                    original.setpos(r['clip_start_sample'])
                    assert clip.readframes(clip.getnframes())==original.readframes(clip.getnframes())
                    assert abs(r['clip_origin_seconds']-r['clip_start_sample']/22050)<1e-12
                    assert abs(r['boundary_in_clip_seconds']+r['clip_origin_seconds']-r['boundary_seconds'])<1e-12
                    assert 0<=r['boundary_in_clip_seconds']<=clip.getnframes()/22050
                ts=r['review_f0']['time_seconds'];fs=r['review_f0']['f0_hz']
                assert len(ts)==len(fs) and all(a<b for a,b in zip(ts,ts[1:]))
                assert all(r['clip_origin_seconds']<=t<r['clip_end_sample']/22050 for t in ts)
                clip_count+=1
    accounting=json.loads((out/'SCREENING_ACCOUNTING.json').read_text())
    assert all(sum(r['screening_counts'].values())==r['original_t5_intervals'] for r in accounting)
    assert sum(r['pilot_rows'] for r in accounting)==48
    assert all(r['pilot_rows']+r['not_selected_for_pilot']==r['original_t5_intervals'] for r in accounting)
    artifacts=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('AUDIT.json','FINAL.json')]
    result=dict(status='passed_technical_pilot_not_semantic_validation',rows=48,recordings=len(groups),
                candidate_counts=dict(Counter(r['candidate_type'] for r in rows)),original_tier_intervals_preserved=intervals,
                candidate_points_checked=points,clips_bitwise_equal_to_original_samples=clip_count,
                json_csv_roundtrip=True,source_scope_accounted=True,
                human_accuracy_evaluated=False,full_boundary_generation=False,artifacts=artifacts,
                parser_round_digits=15,initial_audit_issue='Parser default five-decimal rounding; source/output unchanged; explicit precision used for this audit')
    encoded=json.dumps(result,ensure_ascii=False,indent=2)
    (out/'AUDIT.json').write_text(encoded,encoding='utf-8')
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(encoded,encoding='utf-8')
    (out/'FINAL.json').write_text(json.dumps(dict(status=result['status'],rows=48,technical_gate_passed=True,
        human_accuracy_evaluated=False,full_boundary_generation=False,audit_sha256=digest(out/'AUDIT.json')),indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='artifacts'}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['base','out','report']:p.add_argument('--'+k,required=True)
    a=p.parse_args();run(Path(a.base),Path(a.out),Path(a.report))

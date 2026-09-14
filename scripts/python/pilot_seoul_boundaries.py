"""Bounded offline AP/IP heuristic pilot. Output is a new, separate derivative."""
import argparse,bisect,csv,gzip,hashlib,html,json,random,wave
from collections import Counter,defaultdict
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics
from prepare_seoul_corpus import parse,sha
from seoul_boundary_core import lexical,map_syllables,vowel_feature,semitones,classify

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def winpath(path):
    return resolve_legacy_path(path)

def features(i,words,mappings,times,f0,params):
    w=words[i]; syllables,reason=mappings[i]; holds=[]
    metrics=dict(annotated_silence_seconds=0,ap_context_eligible=False)
    if not lexical(w['text']): holds.append('nonlexical_or_marker')
    if not syllables: holds.append(reason)
    following=words[i+1] if i+1<len(words) else None
    if following and following['text'].strip()=='<SIL>':
        metrics['annotated_silence_seconds']=following['end']-following['start']
    elif following and not lexical(following['text']):
        holds.append('following_marker_or_speaker_uncertain')
    if syllables:
        last=vowel_feature(syllables[-1],times,f0,params)
        metrics.update(terminal_change_st=last['terminal_change_st'],last_vowel=last)
        if not last['quality_ok']: holds.append('terminal_vowel_f0_unreliable')
    nxt=mappings[i+1][0] if following else []
    if len(syllables)>=2 and len(nxt)>=2 and lexical(following['text']):
        vals=[vowel_feature(s,times,f0,params) for s in [syllables[-2],syllables[-1],nxt[0],nxt[1]]]
        low=nxt[0]['onset'] in set(params['low_initial_codes_subset']+params['vowel_codes_hypothesis'])
        metrics['ap_context_eligible']=low and all(v['quality_ok'] for v in vals)
        a,b,c,d=[v['median_hz'] for v in vals]
        metrics.update(pre_final_rise_st=semitones(a,b),next_initial_rise_st=semitones(c,d),
                       boundary_fall_st=semitones(c,b),next_onset=nxt[0]['onset'])
    metrics['lengthening_normalized']=None
    return metrics, sorted(set(holds))

def write_textgrid(path,tiers,rows):
    duration=tiers[6]['intervals'][-1]['end']
    lines=['File type = "ooTextFile"','Object class = "TextGrid"','', 'xmin = 0',f'xmax = {duration!r}',
           'tiers? <exists>', 'size = 8','item []:']
    for t in tiers:
        lines.extend([f'    item [{t["tier_index"]}]:','        class = "IntervalTier"',f'        name = "{t["name"]}"',
                      '        xmin = 0',f'        xmax = {duration!r}',f'        intervals: size = {len(t["intervals"])}'])
        for r in t['intervals']:
            label=r['text'].replace('"','""')
            lines.extend([f'        intervals [{r["interval_index"]}]:',f'            xmin = {r["start"]!r}',
                          f'            xmax = {r["end"]!r}',f'            text = "{label}"'])
    lines.extend(['    item [8]:','        class = "TextTier"','        name = "AP_IP_MACHINE_CANDIDATE_PILOT"',
                  '        xmin = 0',f'        xmax = {duration!r}',f'        points: size = {len(rows)}'])
    for n,r in enumerate(sorted(rows,key=lambda r:r['boundary_seconds']),1):
        label=r['candidate_type']+'|'+r['candidate_id']
        lines.extend([f'        points [{n}]:',f'            number = {r["boundary_seconds"]!r}',f'            mark = "{label}"'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run(base,out,params_path,topology_path,method_path):
    if out.exists(): raise RuntimeError('Pilot output exists: inspect/reuse, never overwrite')
    params=read(params_path); topology=read(topology_path)
    final=read(base/'52_KOINA_FULL_V2_20260911/FINAL.json')
    assert final['recordings']==240 and final['totals']['utterance_intervals']==128313
    receipts={r['source_file']:r for r in final['sources']}
    out.mkdir(parents=True);(out/'clips').mkdir();(out/'textgrids').mkdir()
    save(out/'PARAMETERS.json',params)
    allrows=[]; source_refs=[]; file_counts=[];rng=random.Random(params['seed'])
    for name in params['sources']:
        receipt=receipts[name];tg=base/f'00_SOURCE/00_file/{name}.TextGrid'
        assert sha(tg)==receipt['source']['textgrid_sha256']
        tiers,_=parse(tg);words=tiers[4]['intervals'];phones=tiers[0]['intervals'];ends=[p['end'] for p in phones]
        bad=name in topology['tier_mismatch_recordings']
        mappings=[([], 'tier_pair_mismatch') for w in words] if bad else [
            map_syllables(w,p,r,phones,ends,set(params['vowel_codes_hypothesis']))
            for w,p,r in zip(words,tiers[1]['intervals'],tiers[2]['intervals'])]
        result_dir=winpath(receipt['result_directory']);f0_path=result_dir/'f0_frames.csv'
        with f0_path.open(encoding='utf-8-sig',newline='') as f: frames=list(csv.DictReader(f))
        times=[float(r['time_seconds']) for r in frames]; pitches=[float(r['f0_hz']) for r in frames]
        assert len(times)==receipt['frames'] and all(a<b for a,b in zip(times,times[1:]))
        actual_sha=sha(f0_path);expected=next(a['sha256'] for a in receipt['artifacts'] if a['name']=='f0_frames.csv')
        assert actual_sha==expected
        with (result_dir/'momel_points.csv').open(encoding='utf-8-sig',newline='') as f:
            momel=[r for r in csv.DictReader(f) if r['internal_candidate']=='True']
        meta_path=base/f'45_SCOPE_COMPLETION_20260911/MERGED_BAREUN/json/{name}.json';meta=read(meta_path)
        assert meta['source_textgrid_sha256']==receipt['source']['textgrid_sha256']
        diagnostics=[]
        for path in qc_diagnostics(name):
            with gzip.open(path,'rt',encoding='utf-8') as f: diagnostics.append(json.load(f))
        utterances=tiers[6]['intervals'];utt_ends=[r['end'] for r in utterances]
        rows=[]
        for i,w in enumerate(words):
            metrics,holds=features(i,words,mappings,times,pitches,params)
            if bad: holds=sorted(set(holds+['tier_pair_mismatch']))
            classes=[classify(metrics,holds,g) for g in params['parameter_grid']]
            sensitivity=len(set(classes))>1
            kind='uncertain' if sensitivity else classes[0]
            quality=['threshold_sensitive'] if sensitivity else []
            if kind=='no_boundary_evidence':quality.append('heuristic_subset_only')
            # Local diagnostic variants are never silently substituted for full-recording F0.
            diagnostic_classes=[]
            for d in diagnostics:
                if mappings[i][0] and d['core_start']<=mappings[i][0][0]['start'] and w['end']<=d['core_end']:
                    for v in d['pitch_variants']:
                        m,h=features(i,words,mappings,v['actual_frame_times'],v['f0_hz'],params)
                        diagnostic_classes.append(dict(window=d['window'],silence_threshold=v['pitch_silence_threshold'],
                            candidate_type=classify(m,h,params['parameter_grid'][1])))
            if diagnostic_classes and any(d['candidate_type']!=classes[1] for d in diagnostic_classes):
                quality.append('local_pitch_settings_sensitive')
                if kind in ('AP_candidate','IP_candidate'):kind='uncertain'
            # Coordinate join of entire word; not a claim of speaker diarization.
            uidx=bisect.bisect_left(utt_ends,w['end']-1e-8)
            u=utterances[uidx] if uidx<len(utterances) else None
            join=bool(u and u['start']<=w['start']+1e-7 and u['end']>=w['end']-1e-7)
            if not join:
                holds.append('word_utterance_join_unresolved');kind='not_evaluable'
            rows.append(dict(candidate_id=f'seoul:{name}:t5:i{i+1}:end',source_file=name,
                boundary_seconds=w['end'],word_start_seconds=w['start'],word_tier_index=5,word_interval_index=i+1,
                utt_id=f'seoul:{name}:t7:i{u["interval_index"]}' if join else None,
                next_word_id=f'seoul:{name}:t5:i{i+2}' if i+1<len(words) else None,
                word=w['text'],next_annotation=words[i+1]['text'] if i+1<len(words) else None,
                candidate_type=kind,parameter_classes=classes,cue_metrics=metrics,quality_flags=quality,
                hold_reasons=sorted(set(holds)),syllable_mapping_status=mappings[i][1],
                local_diagnostic_classes=diagnostic_classes,human_verified=False,manual_break_index=None,
                speaker_metadata=meta.get('speaker_metadata'),interviewer_metadata=meta.get('interviewer_metadata'),
                speaker_assignment='recording_metadata_only_not_frame_diarization',
                morphology_join_role='utt_id_reference_only_no_reanalysis',
                morphology_source=str(meta_path),source_textgrid_sha256=receipt['source']['textgrid_sha256'],
                f0_sha256=actual_sha,rule_ids=['R01','R02','R03','R04','R05','R06'],
                source_refs=['S01:PDF2,7,14,15','S02:PDF4-7','S03:PDF106,109'],method_version='0.1'))
        # Every word accounted at screening; only bounded chosen rows exported in this pilot.
        counts=Counter(r['candidate_type'] for r in rows);selected=[]
        for category in ['AP_candidate','IP_candidate','uncertain','not_evaluable','no_boundary_evidence']:
            pool=[r for r in rows if r['candidate_type']==category]
            if pool:selected.append(rng.choice(pool))
        available=[r for r in rows if r not in selected];rng.shuffle(available)
        selected+=available[:params['samples_per_recording']-len(selected)]
        selected.sort(key=lambda r:r['boundary_seconds'])
        with wave.open(str(base/f'00_SOURCE/00_file/{name}.wav'),'rb') as wav:
            assert wav.getsampwidth()==2 and wav.getnchannels()==1 and wav.getframerate()==22050
            for r in selected:
                s=max(0,int((r['boundary_seconds']-2)*wav.getframerate()))
                e=min(wav.getnframes(),int((r['boundary_seconds']+2)*wav.getframerate()))
                wav.setpos(s);data=wav.readframes(e-s)
                clip=out/'clips'/f'{name}_{r["word_interval_index"]}.wav'
                with wave.open(str(clip),'wb') as target:
                    target.setparams(wav.getparams());target.writeframes(data)
                r['clip_relative_path']=clip.relative_to(out).as_posix()
                r['clip_start_sample']=s;r['clip_end_sample']=e;r['clip_origin_seconds']=s/wav.getframerate()
                r['boundary_in_clip_seconds']=r['boundary_seconds']-r['clip_origin_seconds']
                lo=r['clip_origin_seconds'];hi=e/wav.getframerate()
                a=bisect.bisect_left(times,lo);b=bisect.bisect_left(times,hi)
                r['review_f0']={'time_seconds':times[a:b],'f0_hz':pitches[a:b]}
                r['review_momel']=[{'time_seconds':float(p['time_seconds']),'f0_hz':float(p['model_f0_hz'])}
                                   for p in momel if lo<=float(p['time_seconds'])<hi]
        write_textgrid(out/'textgrids'/f'{name}_AP_IP_MACHINE_PILOT.TextGrid',tiers,selected)
        allrows.extend(selected)
        file_counts.append(dict(source_file=name,original_t5_intervals=len(words),screening_counts=dict(counts),
                               pilot_rows=len(selected),not_selected_for_pilot=len(words)-len(selected)))
        source_refs.append(dict(source_file=name,textgrid_sha256=receipt['source']['textgrid_sha256'],
                                wav_sha256_from_prior_receipt=receipt['source']['wav_sha256'],
                                wav_hash_recomputed=False,f0_sha256=actual_sha,metadata_sha256=sha(meta_path)))
        print(json.dumps(dict(source_file=name,pilot_rows=len(selected),screening_counts=counts)),flush=True)
    assert len(allrows)==48 and len({r['candidate_id'] for r in allrows})==48
    save(out/'candidates.json',allrows)
    # CSV is a machine-readable view of the canonical JSON, not a formatted workbook.
    fields=[k for k in allrows[0] if k not in ('review_f0','review_momel')]
    with (out/'candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in allrows:
            writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],(dict,list)) else row[k] for k in fields})
    save(out/'SCREENING_ACCOUNTING.json',file_counts)
    save(out/'SOURCE_REFERENCES.json',source_refs)
    save(out/'BUILD.json',dict(status='built_pending_independent_audit',rows=len(allrows),
        candidate_counts=dict(Counter(r['candidate_type'] for r in allrows)),
        method_sha256=sha(method_path),parameters_sha256=sha(params_path),topology_sha256=sha(topology_path),
        code_sha256={p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('seoul_boundary_core.py')]},
        human_accuracy_evaluated=False,full_boundary_generation=False,source_files_modified=False))
    cards=[]
    for r in allrows:
        data=html.escape(json.dumps({k:v for k,v in r.items() if k not in ('review_f0','review_momel')},ensure_ascii=False,indent=2))
        cards.append(f'<article><h2>{html.escape(r["candidate_id"])} — {r["candidate_type"]}</h2>'
                     f'<p>녹음 {r["boundary_seconds"]:.6f}초 / 클립 {r["boundary_in_clip_seconds"]:.6f}초</p>'
                     f'<audio controls preload="none" src="{r["clip_relative_path"]}"></audio>'
                     f'<details><summary>근거·보류·메타데이터</summary><pre>{data}</pre></details></article>')
    (out/'REVIEW.html').write_text('<!doctype html><meta charset="utf-8"><title>서울 AP/IP 소표본</title>'
        '<style>body{font:16px system-ui;max-width:1000px;margin:36px auto;padding:12px;background:#fafafa}article{background:white;padding:16px;margin:14px 0;border:1px solid #ddd}h2{font-size:18px}pre{white-space:pre-wrap;overflow-wrap:anywhere}audio{width:100%}</style>'
        '<h1>서울 AP/IP 후보 48곳</h1><p>기술 파일럿. 사람 정답·빈도 표본이 아닙니다. 미검출은 비경계 정답이 아닙니다. '
        'AP/IP 일부 유형만 시험했으며 원 전사와 분석 결과는 보존했습니다. 청취 판단은 아직 저장되지 않습니다.</p>'+''.join(cards),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['base','out','parameters','topology','method']:p.add_argument('--'+key,required=True)
    a=p.parse_args();run(Path(a.base),Path(a.out),Path(a.parameters),Path(a.topology),Path(a.method))

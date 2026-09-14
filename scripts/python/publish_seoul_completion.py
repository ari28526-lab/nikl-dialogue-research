"""Independent accounting and publication of the completed Seoul supplement."""
import collections,csv,gzip,json,sqlite3
from pathlib import Path
import repair_seoul_scope as s

def csv_write(path,rows):
    rows=iter(rows);first=next(rows,None)
    if first is None:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,list(first));w.writeheader();w.writerow(first);w.writerows(rows)

def publish():
    report=s.read(s.OUT/'SCOPE_AUDIT.json');assert report['status']=='passed'
    merged=s.read(s.OUT/'MERGED_BAREUN/FINAL.json')
    app=s.read(s.OUT/'DICTIONARY/APPLICATION.json');assert app['sources']==240
    jobs={q['request_id']:q for q in s.load_jobs()[0]}
    original_jobs={q['request_id']:q for q in map(json.loads,(s.BASE/'20_BAREUN_PLAN/REQUESTS.jsonl').read_text('utf-8').splitlines())}
    alljobs={**original_jobs,**jobs}
    inventory=list(csv.DictReader((s.OUT/'INTERVAL_ACCOUNTING.csv').open(encoding='utf-8-sig',newline='')))
    index={r['utt_id']:r for r in inventory};processed=set();held=set();gapped=set();review=[]
    morph_total=0;dictionary_total=0;comparison=collections.Counter();refs=collections.defaultdict(set);out=s.OUT/'COMPLETE';out.mkdir(exist_ok=True)
    csv_path=out/'dictionary_comparison.csv';morph_path=out/'morphemes.csv'
    fields=['case_id','source_file','utt_id','request_id','sentence_index','token_index','morph_index','morph','pos','token_text',
        'utterance_start','utterance_end','token_begin_in_utterance','token_end_in_utterance','speaker_id','speaker_gender','speaker_age','interviewer_gender',
        'source_utterance_text','analysis_utterance_text','speech_classification','bareun_sense_no','bareun_target_id','bareun_group','dictionary_group','candidate_groups','dictionary_status','comparison_status','evidence_namespace','evidence_refs','human_verified']
    with csv_path.open('w',encoding='utf-8-sig',newline='') as cf,morph_path.open('w',encoding='utf-8-sig',newline='') as mf:
        cw=csv.DictWriter(cf,fields);cw.writeheader();mw=None
        for p in sorted((s.OUT/'MERGED_BAREUN/json').glob('*.json')):
            d=s.read(p);old=s.read(s.BASE/'30_BAREUN/json'/p.name)
            assert d['tiers']==old['tiers'] and d['source_wav_sha256']==old['source_wav_sha256']
            assert d['morphology'][:len(old['morphology'])]==old['morphology'],'old_analysis_changed'
            by={s.dictionary.morph_key(r):r for r in d['morphology']};assert len(by)==len(d['morphology'])
            expected=[]
            for rid,q in jobs.items():
                if q['source_file']!=p.stem:continue
                result=s.read(s.OUT/'BAREUN/results'/(rid+'.json'))
                assert s.sha(s.OUT/'BAREUN/raw'/(rid+'.json'))==result['raw_sha256']
                assert result['text_sha256']==q['text_sha256'] and not result['projection']['errors']
                expected.extend(result['projection']['rows']);processed.update(x['utt_id'] for x in q['spans'])
            new=d['morphology'][len(old['morphology']):]
            assert len(expected)==len(new)
            for a,b in zip(expected,new):assert all(b[k]==v for k,v in a.items()),'supplement_merge_changed'
            intervals=next(t['intervals'] for t in d['tiers'] if t['tier_index']==7)
            ui={f"seoul:{p.stem}:t7:i{u['interval_index']}":(i,u) for i,u in enumerate(intervals)}
            for r in d['morphology']:
                raw=d.get('analysis_text_overrides',{}).get(r['utt_id'],{}).get('text',ui[r['utt_id']][1]['text']);a,b=r['token_begin_in_utterance'],r['token_end_in_utterance']
                assert raw[a:b]==r['token_text'];processed.add(r['utt_id'])
                if mw is None:mw=csv.DictWriter(mf,list(r));mw.writeheader()
                mw.writerow(r);morph_total+=1
            dj=s.dictionary.load_gzip(s.OUT/'DICTIONARY/json'/(p.stem+'.json.gz'))
            assert dj['source_sha256']==s.sha(Path(dj['source_json']));seen=set()
            if Path(dj['source_json'])!=p:
                view=s.read(Path(dj['source_json']));assert view['original_tiers_reference']['sha256']==s.sha(p)
                for view_tier,original_tier in zip(view['tiers'],d['tiers']):
                    for v,u in zip(view_tier['intervals'],original_tier['intervals']):
                        uid=f"seoul:{p.stem}:t7:i{u['interval_index']}"
                        if view_tier['tier_index']==7 and uid in d['analysis_text_overrides']:
                            assert v==dict(u,text=d['analysis_text_overrides'][uid]['text'])
                        else:assert v==u
            namespace=dj['dictionary_evidence_namespace']
            for x in dj['results']:
                r=x['bareun'];k=s.dictionary.morph_key(r);assert k not in seen and r==by[k];seen.add(k)
                a=x['dictionary'];c=x['comparison']
                assert c['final_selected_group'] is None and not c['human_verified']
                if a.get('selected_group'):assert a['selected_group'] in a['candidate_groups'] and not x['source_gap_in_utterance']
                if c['status']=='same_homonym_group':assert c['bareun_group']==a['selected_group']
                if c['status']=='group_conflict':assert c['bareun_group']!=a['selected_group']
                refs[namespace].update(x['evidence_refs']);comparison[c['status']]+=1
                rr={k:r.get(k) for k in fields if k in r}
                rr.update(case_id=x['case_id'],source_utterance_text=ui[r['utt_id']][1]['text'],analysis_utterance_text=index[r['utt_id']]['analysis_text'],speech_classification=index[r['utt_id']]['classification'],
                    bareun_sense_no=r.get('sense_no'),bareun_target_id=r.get('urimal_target_id'),bareun_group=c.get('bareun_group'),dictionary_group=c.get('dictionary_group'),
                    candidate_groups=json.dumps(a.get('candidate_groups',[]),ensure_ascii=False),dictionary_status=a['status'],comparison_status=c['status'],
                    evidence_namespace=namespace,evidence_refs=json.dumps(x['evidence_refs']),human_verified=False)
                cw.writerow(rr);dictionary_total+=1
            assert len(seen)==len(by)
            for kind,issues in [('token_span_gap',d['source_gaps']),('uncertain_request',d['request_holds'])]:
                for issue in issues:
                    uid=issue['utt_id'];i,u=ui[uid];q=alljobs[issue['request_id']];span=next(x for x in q['spans'] if x['utt_id']==uid)
                    offset=issue.get('request_character_offset');offset=offset-span['start'] if offset is not None else None
                    analysis_source=d.get('analysis_text_overrides',{}).get(uid,{}).get('text',u['text'])
                    if kind=='token_span_gap':gapped.add(uid);assert analysis_source[offset]==issue['character']
                    else:held.add(uid)
                    review.append(dict(case_id='SC-'+s.dictionary.digest([kind,uid,issue['request_id'],offset])[:20],kind=kind,utt_id=uid,
                        source_file=p.stem,request_id=issue['request_id'],start=u['start'],end=u['end'],source_text=u['text'],analysis_text=analysis_source,character_offset=offset,
                        character=issue.get('character',''),previous_context=' | '.join(x['text'] for x in intervals[max(0,i-2):i]),
                        next_context=' | '.join(x['text'] for x in intervals[i+1:i+3]),review_status='unreviewed',judgment=''))
    assert morph_total==dictionary_total==merged['morphemes']==app['counts']['morphemes']
    expected_text={r['utt_id'] for r in inventory if r['classification'] in ('ordinary_speech','annotated_speech','word_tier_speech')}
    assert processed.isdisjoint(held) and processed|held==expected_text,'unaccounted_transcribed_interval'
    assert len(held)==13
    for r in inventory:
        uid=r['utt_id'];r['analysis_coverage']='response_with_token_span_review' if uid in gapped else 'response_saved' if uid in processed else 'uncertain_request_hold' if uid in held else r['disposition']
    csv_write(out/'utterance_coverage.csv',inventory);csv_write(out/'review_cases.csv',review);s.save(out/'review_cases.json',review)
    paths={'original_dictionary':s.BASE/'40_RESEARCH_DICTIONARY_20260911/EVIDENCE.sqlite','supplement_dictionary':s.OUT/'DICTIONARY/EVIDENCE.sqlite'}
    with gzip.open(out/'evidence.jsonl.gz','wt',encoding='utf-8') as f:
        for ns,ids in refs.items():
            c=sqlite3.connect(f'file:{paths[ns].as_posix()}?mode=ro',uri=True)
            try:
                for eid in sorted(ids):
                    row=c.execute('SELECT kind,payload FROM evidence WHERE id=?',(eid,)).fetchone();assert row
                    payload=json.loads(row[1]);assert s.dictionary.digest([row[0],payload])==eid
                    f.write(json.dumps(dict(namespace=ns,id=eid,kind=row[0],payload=payload),ensure_ascii=False)+'\n')
            finally:c.close()
    result=dict(status='complete_with_explicit_reviews',recordings=240,original_morphemes=396193,total_morphemes=morph_total,
        added_morphemes=merged['added_morphemes'],transcribed_intervals=len(expected_text),response_intervals=len(processed),
        uncertain_request_intervals=len(held),uncertain_requests=1,unexpected_excluded_transcribed_intervals=0,
        source_gap_characters=sum(r['kind']=='token_span_gap' for r in review),comparison=dict(comparison),
        original_tiers_and_original_morphemes_preserved=True,auditory_transcription_accuracy_verified=False,human_semantic_accuracy_verified=False,
        code_sha256={p.name:s.sha(p) for p in [Path(__file__),Path(s.__file__),Path(s.dictionary.__file__)]},
        artifacts=[dict(path=str(p),bytes=p.stat().st_size,sha256=s.sha(p)) for p in out.iterdir() if p.is_file() and p.name!='FINAL.json'])
    s.save(out/'FINAL.json',result);s.update(status='completed_with_explicit_reviews',stage='completion_audited',**{k:v for k,v in result.items() if k!='status' and k!='artifacts'})
    return result
if __name__=='__main__':
    try:publish()
    except BaseException as e:
        s.update(status='paused_error',stage='publication_audit',error_type=type(e).__name__,error=str(e));raise

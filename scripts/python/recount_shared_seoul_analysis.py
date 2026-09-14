"""Offline reconstruction of seven frequency tables from the shared analysis only."""
import argparse,collections,csv,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'history'))
from frequency_units_v1 import events,js,aligned_span

def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--frequency-dir',help='Optional supplied reference tables for a key-by-key audit');a=ap.parse_args()
    root=BASE.parent;out=Path(a.out).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('Output must be empty')
    out.mkdir(parents=True,exist_ok=True)
    def key(r):return (r['utt_id'],r['request_id'],r['sentence_index'],r['token_index'],r['morph_index'])
    chosen={key(r):r['selected_group'] or None for r in rows(root/'01_analysis/semantic_selection.csv')}
    assert len(chosen)==400959
    by=collections.defaultdict(dict)
    for r in rows(root/'01_analysis/morphemes.csv'):
        k=key(r);tk=k[1:4];tokens=by[r['utt_id']]
        if tk not in tokens:tokens[tk]=dict(surface=r['token_text'],start=int(r['token_begin_in_utterance']) if r['token_begin_in_utterance'] else None,end=int(r['token_end_in_utterance']) if r['token_end_in_utterance'] else None,morphs=[])
        tokens[tk]['morphs'].append(dict(lemma=r['morph'],pos=r['pos'],group=chosen.pop(k)))
    assert not chosen
    counts=collections.Counter()
    for u in rows(root/'01_analysis/utterance_coverage.csv'):
        tokens=list(by.pop(u['utt_id'],{}).values());form=u['analysis_text']
        if not form.strip() and not tokens:form=''
        for t in tokens:
            if t['start'] is not None and t['end'] is not None:t['start'],t['end']=aligned_span(t['surface'],t['start'],t['end'],form)
        for unit,mode,base,sense,quality in events(form,tokens):counts[(unit,mode,base,sense)]+=1
    assert not by
    audits=[]
    reference_dir=Path(a.frequency_dir) if a.frequency_dir else root/'02_frequency_seoul'
    references=sorted(reference_dir.glob('*.csv'))
    if a.frequency_dir and len(references)!=7:raise ValueError('Expected seven reference CSV tables')
    for ref in references:
        expected={}
        for r in rows(ref):
            tag=r['pos_or_analysis']
            if tag.startswith('['):tag=json.loads(tag)
            elif tag=='':tag=None
            k=(r['unit'],r['mode'],js([r['form'],tag]),r['homonym_key']);assert k not in expected;expected[k]=int(r['frequency'])
        unit,mode=next(iter(expected))[:2];actual={k:n for k,n in counts.items() if k[:2]==(unit,mode)}
        assert actual==expected,('frequency mismatch',ref.name,len(actual),len(expected))
        with (out/ref.name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['unit','mode','base_key','homonym_key','frequency'])
            for k,n in sorted(actual.items(),key=lambda item:(-item[1],item[0])):w.writerow([*k,n])
        audits.append(dict(file=ref.name,keys=len(actual),total=sum(actual.values()),all_key_counts_equal=True))
    if not references:
        for unit,mode in sorted({k[:2] for k in counts}):
            actual={k:n for k,n in counts.items() if k[:2]==(unit,mode)}
            name=unit+'_'+mode+'.csv'
            with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(['unit','mode','base_key','homonym_key','frequency'])
                for k,n in sorted(actual.items(),key=lambda item:(-item[1],item[0])):w.writerow([*k,n])
            audits.append(dict(file=name,keys=len(actual),total=sum(actual.values()),reference_comparison_performed=False))
    (out/'RECOUNT_VALIDATION.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    print(json.dumps(audits,indent=2))

if __name__=='__main__':main()

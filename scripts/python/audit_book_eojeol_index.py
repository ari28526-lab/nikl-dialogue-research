"""Replay real book entries, separated sentence marks and unchanged numeric values."""
import collections, json
from build_book_eojeol_index import DEST, ROOT, lookup
from build_sejong_supplement import ro, morphology, sha
from book_eojeol_keys import keys
from apply_sejong_residual import atomic, read

def main():
    final=read(DEST/'FINAL.json')
    if final['index_sha256']!=sha(DEST/'INDEX.sqlite'):raise ValueError('index_sha')
    c=ro(DEST/'INDEX.sqlite');s=ro(ROOT/'SUPPLEMENT.sqlite')
    checked=0
    for vid,key,num,state in c.execute('SELECT variant_id,key,numeric_key,state FROM entries WHERE variant_id%4001=0'):
        surf,analysis=s.execute('SELECT e.surface,v.analysis FROM variants v JOIN eojeols e ON e.id=v.eojeol_id WHERE v.rowid=?',(vid,)).fetchone()
        try:k=keys(surf,analysis)
        except ValueError:
            if state!='parse_hold':raise
            continue
        if (key,num,state)!=(k['key'],k['numeric_key'],k['state']):raise ValueError('key_replay')
        checked+=1
    examples={}
    for dataset in ['05.txt','12.txt']:
        examples[dataset]={}
        for surface,analysis,lemma,pos in [('사람','사람/NNG','사람','NNG'),('사람은','사람/NNG + 은/JX','사람','NNG'),('사람.','사람/NNG + ./SF','사람','NNG'),('사람?','사람/NNG + ?/SF','사람','NNG'),('사람!','사람/NNG + !/SF','사람','NNG'),('1층','1/SN + 층__02/NNG','층','NNG'),('2층','2/SN + 층__02/NNG','층','NNG')]:
            examples[dataset][surface]=lookup(surface,analysis,lemma,pos,dataset)
        examples[dataset]['numeric_template_층']=lookup('1층','1/SN + 층__02/NNG','층','NNG',dataset,numeric=True)
    # Independent raw-text replay of actual retained source lines (not index rows).
    raw_counts={}
    wanted={'사람','사람,','사람은','사람은,','사람.','사람?','사람!','1층','2층'}
    for dataset in ['05.txt','12.txt']:
        found=collections.Counter();surface=None
        with (ROOT/'intake'/dataset).open(encoding='cp949') as f:
            next(f)
            for line in f:
                line=line.rstrip('\r\n')
                if not line:continue
                if not line.startswith('\t'):
                    _,rest=line.split('\t',1);surface,_=rest.rsplit(' : ',1)
                elif surface in wanted:
                    fields=line.split('\t');analysis=fields[1];freq=int(fields[2])
                    mp=morphology(analysis)
                    if any(p=='NNG' and l in {'사람','층'} for l,p,n in mp):found[(surface,analysis)]+=freq
        for (surface,analysis),freq in found.items():
            db=s.execute('SELECT SUM(v.frequency) FROM variants v JOIN eojeols e ON e.id=v.eojeol_id WHERE e.dataset=? AND e.surface=? AND v.analysis=?',(dataset,surface,analysis)).fetchone()[0]
            if freq!=db:raise ValueError('raw_source_frequency')
        raw_counts[dataset]=[{'surface':sur,'analysis':ana,'frequency':n} for (sur,ana),n in found.items()]
        for plain,comma in [('사람','사람,'),('사람은','사람은,')]:
            got=examples[dataset][plain]['surface_distribution']
            for sur in [plain,comma]:
                expected=sum(n for (surface,analysis),n in found.items() if surface==sur)
                if got.get(sur)!=expected:raise ValueError('punctuation_family_missing')
            if any(x in got for x in ['사람.','사람?','사람!']):raise ValueError('sentence_function_collapse')
        a=examples[dataset]['1층']['surface_distribution'];b=examples[dataset]['2층']['surface_distribution']
        if '2층' in a or '1층' in b:raise ValueError('numeric_values_collapsed')
        if a.get('1층')!=178 or b.get('2층')!=232:raise ValueError('numeric_source_example_missing')
        if not {'02','03','10'}.issubset(examples[dataset]['2층']['native_distribution']):raise ValueError('native_competition_lost')
        numeric=examples[dataset]['numeric_template_층']['surface_distribution']
        if numeric.get('1층')!=178 or numeric.get('2층')!=232:raise ValueError('numeric_template_missing')
    c.close();s.close()
    atomic(DEST/'EXAMPLES.json',examples)
    result={'status':'passed','errors':[],'sampled_variants_replayed':checked,'source_text_files_replayed':2,'raw_examples':raw_counts,'originals_modified':False,'api_called':False,'wsd_completed':False}
    atomic(DEST/'AUDIT.json',result)
    print(json.dumps({'status':'passed','sampled_variants_replayed':checked,'example_surface_counts':{d:{w:v.get('surface_distribution',{}) for w,v in ex.items() if w in ['사람','사람은']} for d,ex in examples.items()}},ensure_ascii=False))

if __name__=='__main__':main()

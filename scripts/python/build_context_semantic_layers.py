"""Index native Sejong semantic restrictions and explicitly provisional food cues."""
import json,re,sqlite3,time
from pathlib import Path
from build_context_evidence import OUT,sha,emit
from homonym_food_context import FOOD

def main():
    final=OUT/'semantic_cues.sqlite';partial=OUT/'semantic_cues.building.sqlite'
    if final.exists() or partial.exists():raise FileExistsError('semantic unit already exists')
    sources={n:sha(OUT/(n+'.sqlite')) for n in ('urimalsaem','sejong_collocations')}
    for n,h in sources.items():
        r=json.loads((OUT/(n+'.receipt.json')).read_text(encoding='utf-8'))
        if r['database_sha256']!=h:raise ValueError('unverified source')
    c=sqlite3.connect(partial)
    c.executescript('''
    CREATE TABLE semantic_classes(id INTEGER PRIMARY KEY,collocation_id INTEGER,kind TEXT,argument TEXT,role TEXT,native_expression TEXT,attributes_json TEXT);
    CREATE TABLE food_cues(target TEXT PRIMARY KEY,group_id TEXT,lemma TEXT,word TEXT,pos TEXT,definition TEXT,matched_cue TEXT,state TEXT);
    ''')
    s=sqlite3.connect(f'file:{(OUT/"sejong_collocations.sqlite").as_posix()}?mode=ro',uri=True);ns=0
    for cid,fields in s.execute('SELECT id,fields_json FROM collocations'):
        for f in json.loads(fields):
            if f['tag'] in {'sem_class','sel_rst'} and f['text']:
                a=f['attributes'];c.execute('INSERT INTO semantic_classes(collocation_id,kind,argument,role,native_expression,attributes_json) VALUES(?,?,?,?,?,?)',(cid,f['tag'],a.get('arg'),a.get('tht'),f['text'],json.dumps(a,ensure_ascii=False)));ns+=1
    s.close();s=sqlite3.connect(f'file:{(OUT/"urimalsaem.sqlite").as_posix()}?mode=ro',uri=True);nf=0
    for tid,gid,lemma,word,pos,definition in s.execute('SELECT target,group_id,lemma,word,pos,definition FROM entries'):
        m=FOOD.search(definition or '')
        if m:
            c.execute('INSERT INTO food_cues VALUES(?,?,?,?,?,?,?,?)',(tid,gid,lemma,word,pos,definition,m.group(),'definition_keyword_candidate'));nf+=1
    s.close();c.executescript('CREATE INDEX semantic_expression ON semantic_classes(native_expression); CREATE INDEX food_lemma ON food_cues(lemma,pos);');c.commit()
    if c.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('invalid database')
    c.close()
    result={'status':'complete','kind':'semantic_evidence_not_gold_classes','counts':{'native_semantic_class_and_restriction_records':ns,'food_definition_cue_entries':nf},'sources':sources,'builder_sha256':sha(Path(__file__)),'cue_definition_sha256':sha(Path(__file__).with_name('homonym_food_context.py')),'database_sha256':sha(partial),'limitations':['Sejong expressions and argument/role labels are native, not an automatically unified ontology.','Food keyword candidates can include figurative, animal or eating-related entries; they do not alone prove FOOD membership.','Food/eat cooccurrence does not establish an argument relation or select a sense.'],'api_called':False,'automatic_adoption':False}
    partial.rename(final);(OUT/'semantic_cues.receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');emit('semantic_layer_complete',**result['counts'])
if __name__=='__main__':main()

"""Compile source-specific observed patterns and provisional native-code links.

Pattern counts do not confer a sense decision. MP compatibility precedes native-code
matching; special codes never link. Conflicting senses remain queryable.
"""
import argparse, json, sqlite3, time
from collections import Counter
from pathlib import Path
from build_context_evidence import OUT, ROOT, js, sha, emit
from homonym_morphology import citation_forms, entry_compatibility

def candidates(lex,lemma,pos):
    found={}
    for form in citation_forms(lemma,pos):
        for tid,gid,sn,word,ep,definition in lex.execute('SELECT target,group_id,sense_no,word,pos,definition FROM entries WHERE lemma=?',(form,)):
            e={'wordinfo':{'word':word},'senseinfo':{'pos':ep,'definition':definition}}
            check=entry_compatibility(e,lemma,pos)
            found[tid]={'target':tid,'group':gid,'sense_no':sn,'word':word,'pos':ep,'definition':definition,**check}
    return list(found.values())

def binding(cs,native):
    if native in {None,'000','777','888','999'}:return 'special_or_invalid_native_code',[]
    matched=[x for x in cs if x['state']!='incompatible' and x['sense_no'].zfill(3)==native]
    groups={x['group'] for x in matched}
    return ('snapshot_code_match_candidate' if len(groups)==1 else 'multiple_snapshot_groups' if groups else 'no_snapshot_match'),matched

def compile_unit(name):
    inp=OUT/(name+'.sqlite');final=OUT/(name+'.dictionary.sqlite');partial=OUT/(name+'.dictionary.building.sqlite');rp=OUT/(name+'.dictionary.receipt.json')
    sources={n:sha(OUT/(n+'.sqlite')) for n in [name,'urimalsaem']}
    if final.exists() or partial.exists() or rp.exists():raise FileExistsError('dictionary unit exists: '+name)
    lex=sqlite3.connect(f'file:{(OUT/"urimalsaem.sqlite").as_posix()}?mode=ro',uri=True)
    src=sqlite3.connect(f'file:{inp.as_posix()}?mode=ro',uri=True)
    c=sqlite3.connect(partial);co=Counter();start=time.time()
    try:
        c.executescript('''
        CREATE TABLE lexical_candidates(lemma TEXT,pos TEXT,candidates_json TEXT,PRIMARY KEY(lemma,pos));
        CREATE TABLE bindings(lemma TEXT,pos TEXT,native_code TEXT,state TEXT,groups_json TEXT,entry_ids_json TEXT,occurrences INTEGER,PRIMARY KEY(lemma,pos,native_code));
        CREATE TABLE patterns(id INTEGER PRIMARY KEY,lemma TEXT,pos TEXT,native_code TEXT,family TEXT,word_pattern TEXT,anchor TEXT,occurrences INTEGER,documents INTEGER,evidence_occurrence_id INTEGER);
        ''')
        lastkey=None;cs=[]
        emit('dictionary_start',unit=name)
        for lemma,pos,native,n in src.execute('SELECT lemma,pos,native_code,COUNT(*) FROM occurrences GROUP BY lemma,pos,native_code ORDER BY lemma,pos,native_code'):
            if (lemma,pos)!=lastkey:
                cs=candidates(lex,lemma,pos);lastkey=(lemma,pos)
                c.execute('INSERT INTO lexical_candidates VALUES(?,?,?)',(lemma,pos,js(cs)));co['lemma_pos_keys']+=1
            state,matched=binding(cs,native)
            c.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?)',(lemma,pos,native,state,js(sorted({x['group'] for x in matched})),js(sorted({x['target'] for x in matched})),n))
            co['bindings']+=1;co[state+'_keys']+=1;co[state+'_occurrences']+=n
        c.commit();emit('bindings_complete',unit=name,**dict(co))
        for family,col in [('ordered_left_lexical','left_lex'),('ordered_right_lexical','right_lex')]:
            # Same neighboring lexical pattern under other native senses is retained.
            sql=f'''SELECT o.lemma,o.pos,o.native_code,o.word_pattern,o.{col},COUNT(*),COUNT(DISTINCT s.document_id),MIN(o.id)
            FROM occurrences o JOIN sentences s ON s.id=o.sentence_id
            WHERE o.word_pattern IS NOT NULL AND o.{col} IS NOT NULL AND o.{col}!='[]'
            GROUP BY o.lemma,o.pos,o.native_code,o.word_pattern,o.{col}'''
            for lemma,pos,native,word,anchor,n,nd,oid in src.execute(sql):
                c.execute('INSERT INTO patterns(lemma,pos,native_code,family,word_pattern,anchor,occurrences,documents,evidence_occurrence_id) VALUES(?,?,?,?,?,?,?,?,?)',(lemma,pos,native,family,word,anchor,n,nd,oid))
                co['patterns']+=1;co['pattern_occurrence_supports']+=n
            c.commit();emit('pattern_family_complete',unit=name,family=family,patterns=co['patterns'])
        c.execute('CREATE INDEX pattern_lookup ON patterns(lemma,pos,native_code)');c.commit()
        if c.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('sqlite_check_failed')
        c.close();src.close();lex.close()
        if sources!={n:sha(OUT/(n+'.sqlite')) for n in sources}:raise ValueError('evidence_changed')
        result={'unit':name,'kind':'observed_context_dictionary','status':'complete','source_database_sha256':sources,'compiler_sha256':sha(Path(__file__)),'counts':dict(co),'database_sha256':sha(partial),'elapsed_seconds':round(time.time()-start,1),'automatic_adoption':False,'api_called':False,'limitations':['Native code plus snapshot entry is a candidate correspondence, not gold.','Counts remain separate by source; LS and ML can overlap.','Patterns encode ordered cooccurrence, not dependency or semantic entailment.','All native codes, including special and conflicting alternatives, are retained.']}
        partial.rename(final);rp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');emit('dictionary_complete',unit=name,**dict(co))
    finally:c.close();src.close();lex.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',action='append',required=True);args=p.parse_args()
    for name in args.unit:
        if name not in {'LS2020_spoken','LS2020_messenger','LS2020_written','ML2025_spoken','ML2025_written'}:raise ValueError('unknown unit')
        for n in [name,'urimalsaem']:
            r=json.loads((OUT/(n+'.receipt.json')).read_text(encoding='utf-8'))
            if r['status']!='complete' or sha(OUT/(n+'.sqlite'))!=r['database_sha256']:raise ValueError('unverified evidence')
        compile_unit(name)

if __name__=='__main__':main()

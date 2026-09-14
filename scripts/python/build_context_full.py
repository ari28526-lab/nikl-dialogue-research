"""Compile all available morphology, bounded contexts and native relation layers."""
import argparse,json,sqlite3,time,zlib,shutil
from collections import Counter,defaultdict
from pathlib import Path
from context_full_lexicon import BASE,FULL,ROOT,SOURCES,Lexicon,ro,unpack,preflight,publish
from context_full_features import Sentence,extract,za_links,signature,VERSION,integer
from build_context_evidence import sha,js,emit
from homonym_morphology import structure_features

def code_shas():return {n:sha(Path(__file__).with_name(n)) for n in ['build_context_full.py','context_full_features.py','context_full_lexicon.py','homonym_morphology.py','homonym_context_core.py']}

def build(name,resume=False):
    preflight();partial=FULL/(name+'.building.sqlite');final=FULL/(name+'.sqlite');receipt=FULL/(name+'.receipt.json')
    inputs={str(BASE/(name+'.sqlite')):sha(BASE/(name+'.sqlite')),str(BASE/(name+'.dictionary.sqlite')):sha(BASE/(name+'.dictionary.sqlite')),str(FULL/'lexical.sqlite'):sha(FULL/'lexical.sqlite')}
    for p,h in inputs.items():
        rp=Path(p).with_name(Path(p).stem+'.receipt.json');r=json.loads(rp.read_text(encoding='utf-8'))
        if r['status']!='complete' or r['database_sha256']!=h:raise ValueError('unverified_input')
    if final.exists() and receipt.exists():
        r=json.loads(receipt.read_text(encoding='utf-8'))
        old_builder=ROOT/'work/context_dictionary_full_20260906/build_context_full_original.py'
        compatible=r['code_shas']==code_shas() or (old_builder.exists() and r['code_shas'].get('build_context_full.py')==sha(old_builder) and all(r['code_shas'].get(k)==v for k,v in code_shas().items() if k!='build_context_full.py'))
        if r['input_shas']==inputs and compatible and sha(final)==r['database_sha256']:emit('already_complete',unit=name);return
        raise ValueError('resume_mismatch')
    restarting=partial.exists()
    if (restarting and not resume) or final.exists() or receipt.exists():raise FileExistsError('unfinished unit requires inspection: '+name)
    src=ro(BASE/(name+'.sqlite'));old=ro(BASE/(name+'.dictionary.sqlite'));lex=Lexicon();c=sqlite3.connect(partial)
    bindings={(l,p,n):(state,json.loads(groups)) for l,p,n,state,groups in old.execute('SELECT lemma,pos,native_code,state,groups_json FROM bindings')};old.close()
    c.execute('PRAGMA cache_size=-65536');c.execute('PRAGMA temp_store=FILE')
    if restarting:
        # SQLite recovers the last uncommitted document, then we preserve a backup.
        if c.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('resume_database_invalid')
        backup=partial.with_name(name+'.before_append_optimization.sqlite')
        if not backup.exists():
            dest=sqlite3.connect(backup);c.backup(dest);dest.close()
    else:c.executescript('''
    PRAGMA journal_mode=DELETE;
    CREATE TABLE targets(id INTEGER PRIMARY KEY,sentence_id INTEGER,document_id INTEGER,morph_id INTEGER,word_id INTEGER,position INTEGER,lemma TEXT,pos TEXT,native_code TEXT,group_id TEXT,label_kind TEXT,candidates_json TEXT);
    CREATE TABLE annotations(occurrence_id INTEGER PRIMARY KEY,sentence_id INTEGER,morph_id INTEGER,status TEXT);
    CREATE TABLE patterns(hash BLOB,group_id TEXT,label_kind TEXT,lemma TEXT,pos TEXT,family TEXT,key_json TEXT,relation_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER,PRIMARY KEY(hash,group_id,label_kind)) WITHOUT ROWID;
    CREATE TABLE issues(sentence_id INTEGER,kind TEXT,count INTEGER);
    CREATE TABLE document_identity(id INTEGER PRIMARY KEY,native_id TEXT,sentence_count INTEGER,text_hash TEXT);
    CREATE TABLE relation_coverage(document_id INTEGER,kind TEXT,count INTEGER);
    CREATE VIRTUAL TABLE utterance_search USING fts5(sentence_id UNINDEXED,document_id UNINDEXED,native_id UNINDEXED,text,morphemes,tokenize='unicode61');
    ''')
    c.execute('CREATE TABLE IF NOT EXISTS pattern_observations(hash BLOB,group_id TEXT,label_kind TEXT,lemma TEXT,pos TEXT,family TEXT,key_json TEXT,relation_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER)')
    co=Counter();families=Counter();last=time.monotonic();start=time.time();tid=0;ordinal_global=0
    upsert='INSERT INTO pattern_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
    done={r[0] for r in c.execute('SELECT id FROM document_identity')}
    if done:
        tid=c.execute('SELECT COALESCE(MAX(id),0) FROM targets').fetchone()[0]
        co['documents']=len(done);co['sentences']=c.execute('SELECT SUM(sentence_count) FROM document_identity').fetchone()[0]
        co['native_WSD_annotations']=c.execute('SELECT COUNT(*) FROM annotations').fetchone()[0]
        co['lexical_targets']=c.execute('SELECT COUNT(*) FROM targets').fetchone()[0]
        for label,n in c.execute('SELECT label_kind,COUNT(*) FROM targets GROUP BY label_kind'):co['label_'+label]=n
        for label,n in c.execute('SELECT status,COUNT(*) FROM annotations GROUP BY status'):co['annotation_'+label]=n
        for label,n in c.execute('SELECT kind,SUM(count) FROM issues GROUP BY kind'):co['issue_'+label]=n
        for label,n in c.execute('SELECT kind,SUM(count) FROM relation_coverage GROUP BY kind'):co[label]=n
        for fam,n in c.execute('SELECT family,SUM(occurrences) FROM (SELECT family,occurrences FROM patterns UNION ALL SELECT family,occurrences FROM pattern_observations) GROUP BY family'):families[fam]=n;co['feature_observations']+=n
        for did in sorted(done):
            for ordinal,raw in src.execute('SELECT ordinal,raw FROM sentences WHERE document_id=?',(did,)):
                v=Sentence(unpack(raw),ordinal,lex);co['morphemes_accounted']+=len(v.raw.get('MP',v.raw.get('morpheme',[])))
                for m in v.targets:
                    a=lex.analyze(m['form'],m['label']);st=structure_features(v.mp[m['word_id']],m)
                    if len(a['groups'])==1 and not a['uncertain'] and not st['issues']:co['context_not_needed_morphology_singleton']+=1
                    elif not a['groups']:co['no_dictionary_context_retained_in_source']+=1
                    else:co['context_indexed_targets']+=1
        emit('resumed_committed_documents',unit=name,documents=len(done),targets=tid)
    try:
        for did,dnative in src.execute('SELECT id,native_id FROM documents ORDER BY id'):
            if did in done:continue
            rawrows=src.execute('SELECT id,ordinal,raw FROM sentences WHERE document_id=? ORDER BY ordinal',(did,)).fetchall()
            views=[Sentence(unpack(raw),ordinal,lex) for sid,ordinal,raw in rawrows];co['documents']+=1;co['sentences']+=len(views)
            text_hash=__import__('hashlib').sha256(js([v.raw.get('form','') for v in views]).encode()).hexdigest()
            c.execute('INSERT INTO document_identity VALUES(?,?,?,?)',(did,dnative,len(views),text_hash))
            native=defaultdict(list)
            for oid,sid,ordinal,raw in src.execute('SELECT o.id,o.sentence_id,o.ordinal,o.raw FROM occurrences o JOIN sentences s ON s.id=o.sentence_id WHERE s.document_id=? ORDER BY o.id',(did,)):
                native[sid].append((oid,unpack(raw)));co['native_WSD_annotations']+=1
            za,zissues=za_links(views)
            for kind,n in zissues.items():c.execute('INSERT INTO relation_coverage VALUES(?,?,?)',(did,kind,n));co[kind]+=n
            batch={}
            for si,((sid,ordinal,raw),v) in enumerate(zip(rawrows,views)):
                mps=v.raw.get('MP',v.raw.get('morpheme',[]));co['morphemes_accounted']+=len(mps)
                c.execute('INSERT INTO utterance_search VALUES(?,?,?,?,?)',(sid,did,v.raw['id'],v.raw.get('form',''),' '.join(m['form'] for m in v.targets)))
                annotation_by_morph=defaultdict(list)
                for oid,a in native[sid]:
                    form=a.get('form',a.get('word'));pos=a.get('pos');wid=a.get('word_id')
                    if not isinstance(form,str) or not isinstance(pos,str) or not integer(wid):hits=[];status='invalid_native_fields'
                    else:hits=[m for m in v.mp.get(wid,[]) if m['form']==form and m['label']==pos];status='aligned' if len(hits)==1 else 'ambiguous_or_unaligned'
                    c.execute('INSERT INTO annotations VALUES(?,?,?,?)',(oid,sid,hits[0]['id'] if len(hits)==1 else None,status));co['annotation_'+status]+=1
                    if len(hits)==1:annotation_by_morph[hits[0]['id']].append(a)
                for m in v.targets:
                    tid+=1;co['lexical_targets']+=1;ana=lex.analyze(m['form'],m['label']);structure=structure_features(v.mp[m['word_id']],m)
                    aa=annotation_by_morph.get(m['id'],[]);nc=None;gid='';label='unannotated'
                    if len(aa)==1:
                        from homonym_context_core import code
                        nc=code(aa[0].get('sense_id'));state,gg=bindings.get((m['form'],m['label'],nc),('unmapped',[]))
                        if state=='snapshot_code_match_candidate' and len(gg)==1:gid=gg[0];label='native_snapshot_candidate'
                        else:label='native_mapping_hold'
                    elif len(aa)>1:label='annotation_conflict'
                    elif len(ana['groups'])==1 and not ana['uncertain'] and not structure['issues']:gid=ana['groups'][0];label='morphology_machine'
                    co['label_'+label]+=1
                    c.execute('INSERT INTO targets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,sid,did,m['id'],m['word_id'],m['position'],m['form'],m['label'],nc,gid,label,js(ana['groups'])))
                    # Full target ledger and raw context remain available. Compile costly
                    # disambiguation conditions only where morphology leaves alternatives.
                    if len(ana['groups'])==1 and not ana['uncertain'] and not structure['issues']:
                        co['context_not_needed_morphology_singleton']+=1;continue
                    if not ana['groups']:
                        co['no_dictionary_context_retained_in_source']+=1;continue
                    co['context_indexed_targets']+=1
                    feats=extract(v,m,views[max(0,si-3):si])
                    for link in za.get((v.raw['id'],m['word_id']),[]):
                        key=[VERSION,'K31_ZA',m['form'],m['label'],m['position'],link,v.guard];h=signature(key);feats[h]=('K31_ZA',js(key),'native_ZA_validated_span')
                    for h,(fam,key,kind) in feats.items():
                        bkey=(h,gid,label);families[fam]+=1;co['feature_observations']+=1
                        if bkey in batch:
                            rec=batch[bkey]
                            if rec[6]!=key:raise ValueError('feature_hash_collision')
                            rec[8]+=1;rec[11]=tid
                        else:batch[bkey]=[h,gid,label,m['form'],m['label'],fam,key,kind,1,1,tid,tid]
                for kind,n in Counter(v.issues).items():c.execute('INSERT INTO issues VALUES(?,?,?)',(sid,kind,n));co['issue_'+kind]+=n
            c.executemany(upsert,batch.values());c.commit()
            if time.monotonic()-last>25:emit('full_progress',unit=name,**dict(co));last=time.monotonic()
        emit('full_aggregate_start',unit=name,feature_observations=co['feature_observations'])
        c.executescript('''
        CREATE TABLE patterns_merged AS
        SELECT hash,group_id,label_kind,MIN(lemma) AS lemma,MIN(pos) AS pos,MIN(family) AS family,MIN(key_json) AS key_json,MIN(relation_kind) AS relation_kind,SUM(occurrences) AS occurrences,SUM(documents) AS documents,MIN(first_target) AS first_target,MAX(last_target) AS last_target
        FROM (SELECT * FROM patterns UNION ALL SELECT * FROM pattern_observations)
        GROUP BY hash,group_id,label_kind;
        DROP TABLE patterns;
        ALTER TABLE patterns_merged RENAME TO patterns;
        DROP TABLE pattern_observations;
        CREATE UNIQUE INDEX pattern_hash ON patterns(hash,group_id,label_kind);
        CREATE INDEX target_lemma ON targets(lemma,pos);
        CREATE INDEX target_sentence ON targets(sentence_id);
        CREATE INDEX pattern_lemma ON patterns(lemma,pos,family);
        CREATE INDEX pattern_family ON patterns(family,label_kind);
        ''');c.commit()
        co['patterns']=c.execute('SELECT COUNT(*) FROM patterns').fetchone()[0]
        c.close();src.close();lex.close()
        if inputs!={p:sha(Path(p)) for p in inputs}:raise ValueError('input_changed')
        publish(partial,name,co,inputs,{'code_shas':code_shas(),'families':dict(families),'elapsed_seconds':round(time.time()-start,1),'source_unit':name,'resumed_committed_documents':len(done),'storage_strategy':'append document aggregates then merge; no feature semantics changed','limits':{'surface_windows':[2,3],'MP_windows':[2,3],'gapped_words':12,'DP_ancestors':3,'discourse_previous_sentences':3},'independent_accuracy_claim':False})
    finally:c.close();src.close();lex.close()

def main():
    a=argparse.ArgumentParser();a.add_argument('--unit',action='append');a.add_argument('--resume',action='store_true');args=a.parse_args()
    for n in args.unit or SOURCES:
        if n not in SOURCES:raise ValueError('invalid_source')
        emit('full_unit_start',unit=n);build(n,resume=args.resume)
if __name__=='__main__':main()

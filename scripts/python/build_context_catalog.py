"""Federated dictionary catalogue and exact full-document overlap census.

No corpus patterns are merged across sources; native repetitions are retained.
"""
import argparse,json,sqlite3,time
from collections import Counter
from pathlib import Path
from context_full_lexicon import BASE,FULL,SOURCES,ROOT,ro,preflight,publish
from build_context_evidence import sha,js,emit

def build(resume=False):
    preflight();part=FULL/'catalog.building.sqlite'
    if (FULL/'catalog.sqlite').exists() or (part.exists() and not resume):raise FileExistsError('catalog already exists')
    if resume and not part.exists():raise FileNotFoundError(part)
    receipts={n:json.loads((FULL/(n+'.receipt.json')).read_text(encoding='utf-8')) for n in SOURCES}
    audits={n:json.loads((ROOT/'work/context_dictionary_full_20260906'/('AUDIT_'+n+'.json')).read_text(encoding='utf-8')) for n in SOURCES}
    if any(a['status']!='passed' or a['database_sha256']!=receipts[n]['database_sha256'] for n,a in audits.items()):raise ValueError('source audit missing or mismatched')
    c=sqlite3.connect(part)
    if resume:
        if c.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('partial integrity')
        backup=FULL/'catalog.before_overlap_repair.sqlite'
        if not backup.exists():
            saved=sqlite3.connect(backup);c.backup(saved);saved.close()
        if c.execute('SELECT COUNT(*) FROM overlap_clusters').fetchone()[0]:raise ValueError('unexpected partial overlap records')
    if not resume:c.executescript('''
    CREATE TABLE source_units(source TEXT PRIMARY KEY,database_sha256 TEXT,counts_json TEXT);
    CREATE TABLE documents(source TEXT,document_id INTEGER,native_id TEXT,sentences INTEGER,text_hash TEXT,PRIMARY KEY(source,document_id));
    CREATE INDEX doc_hash ON documents(text_hash);
    CREATE INDEX doc_native ON documents(native_id);
    CREATE TABLE lexical_distribution(source TEXT,lemma TEXT,pos TEXT,group_id TEXT,label_kind TEXT,occurrences INTEGER,source_documents INTEGER,first_target INTEGER,last_target INTEGER);
    CREATE INDEX lexical_query ON lexical_distribution(lemma,pos,source);
    CREATE TABLE family_distribution(source TEXT,family TEXT,observation_count INTEGER);
    CREATE TABLE overlap_clusters(text_hash TEXT PRIMARY KEY,source_units INTEGER,documents INTEGER,members_json TEXT,state TEXT);
    ''')
    inputs={};co=Counter()
    for n,r in receipts.items():
        inputs[str(FULL/(n+'.sqlite'))]=r['database_sha256'];b=ro(FULL/(n+'.sqlite'))
        prior=c.execute('SELECT database_sha256,counts_json FROM source_units WHERE source=?',(n,)).fetchone()
        if prior:
            if prior!=(r['database_sha256'],js(r['counts'])):raise ValueError('partial source differs')
            b.close();continue
        c.execute('INSERT INTO source_units VALUES(?,?,?)',(n,r['database_sha256'],js(r['counts'])))
        c.executemany('INSERT INTO documents VALUES(?,?,?,?,?)',((n,*row) for row in b.execute('SELECT id,native_id,sentence_count,text_hash FROM document_identity')))
        c.executemany('INSERT INTO family_distribution VALUES(?,?,?)',[(n,f,count) for f,count in r['families'].items()])
        # Count each target once; document count is distinct within this source.
        for row in b.execute('SELECT lemma,pos,group_id,label_kind,COUNT(*),COUNT(DISTINCT document_id),MIN(id),MAX(id) FROM targets GROUP BY lemma,pos,group_id,label_kind'):
            c.execute('INSERT INTO lexical_distribution VALUES(?,?,?,?,?,?,?,?,?)',(n,*row));co['lexical_distribution_rows']+=1
        b.close();c.commit();emit('catalog_source_complete',source=n)
    for h,n in c.execute('SELECT text_hash,COUNT(*) FROM documents GROUP BY text_hash HAVING COUNT(*)>1').fetchall():
        members=[{'source':s,'document_id':i,'native_id':native,'sentences':sent} for s,i,native,sent in c.execute('SELECT source,document_id,native_id,sentences FROM documents WHERE text_hash=? ORDER BY source,document_id',(h,))]
        ns=len({m['source'] for m in members});c.execute('INSERT INTO overlap_clusters VALUES(?,?,?,?,?)',(h,ns,n,js(members),'exact_ordered_text_match_not_deleted'))
        co['exact_text_overlap_clusters']+=1;co['documents_in_overlap_clusters']+=n
        if ns>1:co['cross_source_overlap_clusters']+=1
        if any(sum(m['source']==s for m in members)>1 for s in {m['source'] for m in members}):co['within_source_overlap_clusters']+=1
    co['source_units']=len(receipts);co['documents']=c.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
    co['lexical_distribution_rows']=c.execute('SELECT COUNT(*) FROM lexical_distribution').fetchone()[0]
    co['lemma_pos_keys']=c.execute('SELECT COUNT(*) FROM (SELECT lemma,pos FROM lexical_distribution GROUP BY lemma,pos)').fetchone()[0]
    co['lexical_targets']=c.execute('SELECT SUM(occurrences) FROM lexical_distribution').fetchone()[0]
    if co['lexical_targets']!=sum(r['counts']['lexical_targets'] for r in receipts.values()):raise ValueError('target_accounting')
    c.commit();c.close()
    publish(part,'catalog',co,inputs,{'code_sha256':sha(Path(__file__)),'definition':'Federated lexical distributions, exact ordered full-document text overlap; no source pooling or deletion.','limitations':['Exact text overlap is not a complete near-duplicate or redistribution census.','Source-document support is not automatically independent evidence across resources.','Unannotated and machine-linked occurrences remain separate from native annotation support.']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--finish-existing',action='store_true');a=p.parse_args();build(a.finish_existing)

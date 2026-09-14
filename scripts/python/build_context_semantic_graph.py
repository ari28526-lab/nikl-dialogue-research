"""Supplementary typed dictionary hierarchy and native Sejong restriction aliases.

These proposals never change the frozen classifier used to extract corpus features.
"""
import json,sqlite3,re,time
from pathlib import Path
from context_full_lexicon import FULL,BASE,ro,publish,preflight
from build_context_evidence import sha,js

SEEDS=[('FOOD','479938','음식'),('FOOD','483492','음식'),('FOOD','212906','식품'),('FOOD','414303','과일'),('FOOD','287665','채소'),('FOOD','212052','식물'),('HUMAN','12170','사람'),('ANIMAL','426','동물'),('ANIMAL','38098','동물'),('PLANT','212053','식물'),('VEHICLE','300471','탈것')]
ALIASES={'인간':'HUMAN','사람':'HUMAN','인간집단':'HUMAN_GROUP','동물':'ANIMAL','식물':'PLANT','음식':'FOOD','음식물':'FOOD','식품':'FOOD','장소':'PLACE','신체부위':'BODY_PART','신체 부위':'BODY_PART','구체물':'CONCRETE_ENTITY','사태':'STATE_OF_AFFAIRS','행위':'ACTION','사건':'EVENT','명제':'PROPOSITION','사실명제':'FACTUAL_PROPOSITION'}

def build():
    preflight();p=FULL/'semantic_graph.building.sqlite'
    if p.exists() or (FULL/'semantic_graph.sqlite').exists():raise FileExistsError('graph exists')
    inputs={str(FULL/'lexical.sqlite'):sha(FULL/'lexical.sqlite'),str(BASE/'urimalsaem.sqlite'):sha(BASE/'urimalsaem.sqlite')}
    c=sqlite3.connect(p);c.execute('PRAGMA cache_size=-65536')
    c.executescript('''
    CREATE TABLE seeds(class TEXT,target TEXT,group_id TEXT,lemma TEXT,definition TEXT,PRIMARY KEY(class,target));
    CREATE TABLE edges(child TEXT,parent TEXT,source_relation_rowid INTEGER,source_direction TEXT,PRIMARY KEY(child,parent));
    CREATE TABLE nodes(target TEXT PRIMARY KEY,group_id TEXT,lemma TEXT,pos TEXT);
    CREATE TABLE sejong_aliases(collocation_id INTEGER,kind TEXT,argument TEXT,role TEXT,native_expression TEXT,native_atom TEXT,canonical_alias TEXT,basis TEXT);
    ''')
    lex=ro(FULL/'lexical.sqlite');raw=ro(BASE/'urimalsaem.sqlite')
    for cls,tid,expected in SEEDS:
        gid,lemma,pos,definition=raw.execute('SELECT group_id,lemma,pos,definition FROM entries WHERE target=?',(tid,)).fetchone()
        if lemma!=expected or pos!='명사':raise ValueError('seed_identity_mismatch')
        c.execute('INSERT INTO seeds VALUES(?,?,?,?,?)',(cls,tid,gid,lemma,definition))
    c.executemany('INSERT INTO nodes VALUES(?,?,?,?)',raw.execute('SELECT target,group_id,lemma,pos FROM entries'))
    for rid,child,parent,rel in lex.execute('SELECT rowid,source_target,target_id,relation FROM relations WHERE relation IN ("상위어","하위어") AND target_id IS NOT NULL'):
        if rel=='하위어':child,parent=parent,child
        c.execute('INSERT OR IGNORE INTO edges VALUES(?,?,?,?)',(child,parent,rid,rel))
    c.execute('CREATE INDEX parent_edge ON edges(parent)');c.commit()
    c.executescript('''
    CREATE TABLE proposals AS WITH RECURSIVE walk(class,root,target,depth,path) AS (
      SELECT class,target,target,0,'/'||target||'/' FROM seeds
      UNION ALL
      SELECT w.class,w.root,e.child,w.depth+1,w.path||e.child||'/' FROM walk w JOIN edges e ON e.parent=w.target
      WHERE w.depth<3 AND instr(w.path,'/'||e.child||'/')=0
    ), ranked AS (
      SELECT class,root,target,depth,path,ROW_NUMBER() OVER (PARTITION BY class,root,target ORDER BY depth,path) AS rank FROM walk
    ) SELECT r.class,r.root,r.target,n.group_id,n.lemma,n.pos,r.depth,r.path,'typed_dictionary_hierarchy_candidate' AS state FROM ranked r JOIN nodes n ON n.target=r.target WHERE r.rank=1;
    CREATE INDEX proposed_group ON proposals(group_id,class);
    CREATE INDEX proposed_lemma ON proposals(lemma,pos);
    ''')
    for cid,kind,arg,role,expr in lex.execute('SELECT collocation_id,kind,argument,role,expression FROM sejong_classes'):
        for atom in expr.split('|'):
            atom=atom.strip()
            c.execute('INSERT INTO sejong_aliases VALUES(?,?,?,?,?,?,?,?)',(cid,kind,arg,role,expr,atom,ALIASES.get(atom),'exact_native_atom_alias' if atom in ALIASES else 'native_term_unmapped'))
    c.execute('CREATE INDEX sejong_alias ON sejong_aliases(canonical_alias)');c.commit()
    counts={name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ['seeds','edges','nodes','proposals','sejong_aliases']}
    counts['unresolved_hierarchy_endpoints']=c.execute('SELECT COUNT(*) FROM edges e LEFT JOIN nodes a ON a.target=e.child LEFT JOIN nodes b ON b.target=e.parent WHERE a.target IS NULL OR b.target IS NULL').fetchone()[0]
    counts['mapped_Sejong_aliases']=c.execute('SELECT COUNT(*) FROM sejong_aliases WHERE canonical_alias IS NOT NULL').fetchone()[0]
    c.close();lex.close();raw.close()
    if inputs!={p:sha(Path(p)) for p in inputs}:raise ValueError('input_changed')
    publish(p,'semantic_graph',counts,inputs,{'code_sha256':sha(Path(__file__)),'max_hierarchy_depth':3,'limitations':['Only explicit upper/lower dictionary relations are traversed, never synonyms or dialect labels.','Proposals retain the exact root sense, edge path and unresolved endpoints.','Sejong aliases translate exact atoms for retrieval; native expressions and operators remain authoritative.','This supplement does not silently alter frozen corpus feature classes or assert a complete ontology.']})
if __name__=='__main__':build()

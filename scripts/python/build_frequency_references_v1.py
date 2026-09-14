"""Source-separated external norms. Historical sense numbers never become Urimalsaem IDs."""
import csv,json,math,sqlite3
from collections import Counter
from pathlib import Path
from frequency_units_v1 import norm,pos,js,PRED
from frequency_sources_v1 import ro,ROOT
from build_sejong_supplement import morphology

def build(out,project,include_eojeol=True):
    p=out/'REFERENCES.sqlite';c=sqlite3.connect(p)
    c.executescript('''PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS refs(dataset TEXT,unit TEXT,base TEXT,n INTEGER,PRIMARY KEY(dataset,unit,base));
    CREATE TABLE IF NOT EXISTS done(dataset TEXT PRIMARY KEY,summary TEXT);
    CREATE TABLE IF NOT EXISTS native_lexical(dataset TEXT,line INTEGER,lemma TEXT,pos TEXT,native_code TEXT,n INTEGER,PRIMARY KEY(dataset,line));''')
    insert='INSERT INTO refs VALUES(?,?,?,?) ON CONFLICT(dataset,unit,base) DO UPDATE SET n=n+excluded.n'
    complete={r[0] for r in c.execute('SELECT dataset FROM done')}
    for p in sorted((project/'01_frequency_data/final_word_frequency').glob('*.csv')):
        name='kofren:'+p.stem
        if name in complete:continue
        stats=Counter();counts=Counter()
        with p.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                n=int(r['COUNT']);stats['rows']+=1;stats['raw_count']+=n
                if not r['WORD'] or not r['POS_TAG']:
                    stats['missing_word_or_pos_count']+=n;continue
                counts[(norm(r['WORD']),pos(r['POS_TAG']))]+=n
        with c:
            c.executemany(insert,[(name,'morpheme',js([lemma,tag]),n) for (lemma,tag),n in counts.items()])
            c.execute('INSERT INTO done VALUES(?,?)',(name,js(dict(stats))))
    src=ro(ROOT/'context_dictionary_sejong_20260909/SUPPLEMENT.sqlite')
    for dataset,unit in [('06a.txt','morpheme'),('13a.txt','word')]:
        name='kang_kim_2009:'+dataset
        if name in complete:continue
        counts=Counter();native=[]
        for line,lemma,tag,code,n in src.execute('SELECT line,lemma,pos,native_code,frequency FROM lexical_frequency WHERE dataset=?',(dataset,)):
            tag=pos(tag);lemma=norm(lemma)
            if unit=='word' and tag in PRED:lemma+='다'
            counts[(lemma,tag)]+=n;native.append((name,line,lemma,tag,code,n))
        with c:
            c.executemany(insert,[(name,unit,js([a,b]),n) for (a,b),n in counts.items()])
            c.executemany('INSERT INTO native_lexical VALUES(?,?,?,?,?,?)',native)
            c.execute('INSERT INTO done VALUES(?,?)',(name,js(dict(rows=len(native),raw_count=sum(counts.values())))))
    if include_eojeol:
        for dataset in ['05.txt','12.txt']:
            name='kang_kim_2009:'+dataset
            if name in complete:continue
            stats=Counter();buffer=[]
            # Dataset transaction: interrupted construction rolls back instead of duplicating counts.
            with c:
                for surface,analysis,n in src.execute('SELECT e.surface,v.analysis,v.frequency FROM variants v JOIN eojeols e ON e.id=v.eojeol_id WHERE e.dataset=?',(dataset,)):
                    stats['rows']+=1;stats['raw_count']+=n
                    try:key=js([surface,[[norm(a),pos(b)] for a,b,code in morphology(analysis)]])
                    except ValueError:stats['parse_hold_count']+=n;continue
                    buffer.append((name,'eojeol',key,n))
                    if len(buffer)>=20000:c.executemany(insert,buffer);buffer=[]
                if buffer:c.executemany(insert,buffer)
                c.execute('INSERT INTO done VALUES(?,?)',(name,js(dict(stats))))
    src.close();c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close()
    return out/'REFERENCES.sqlite'

"""Check completed pattern provenance by reconstructing bounded keys from raw rows."""
import hashlib,json,sqlite3,zlib
from pathlib import Path
from build_sejong_supplement import ROOT,ro,sha,js,morphology,LEX,kind
from build_sejong_context_patterns import context_keys

def main():
    root=ROOT;r=json.loads((root/'CONTEXT_PATTERNS.receipt.json').read_text(encoding='utf-8'));p=ro(root/'CONTEXT_PATTERNS.sqlite');s=ro(root/'SUPPLEMENT.sqlite');errors=[]
    p.execute('PRAGMA cache_size=-262144');s.execute('PRAGMA cache_size=-65536')
    print('pattern audit: SHA and SQLite structure',flush=True)
    if sha(root/'CONTEXT_PATTERNS.sqlite')!=r['database_sha256']:errors.append('pattern_sha')
    if p.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:errors.append('pattern_quick_check')
    n=p.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
    if n!=r['counts']['source_pattern_records']:errors.append('record_count')
    if p.execute('SELECT COUNT(*) FROM done').fetchone()[0]!=255:errors.append('source_coverage')
    print('pattern audit: original supporting segments',flush=True)
    sample=sorted({1,n,*range(1,n,max(1,n//300))});verified=0
    for rowid in sample:
        row=p.execute('SELECT hash,family,native_code,label_kind,source_id,first_segment,last_segment FROM observations WHERE rowid=?',(rowid,)).fetchone()
        if not row:errors.append('missing_row');continue
        h,f,native,label,source,first,last=row
        for sid in {first,last}:
            src,raw=s.execute('SELECT source_id,raw FROM segments WHERE id=?',(sid,)).fetchone()
            if src!=source:errors.append('source_link')
            words=[]
            for rr in json.loads(zlib.decompress(raw)):
                try:words.append(morphology(rr[2]))
                except ValueError:words.append([])
            found=False
            for wi,mp in enumerate(words):
                for mi,(lemma,pos,nc) in enumerate(mp):
                    if nc!=native or kind(nc)!=label or pos not in LEX:continue
                    if any(hh==h and ff==f for hh,ff,key in context_keys(words,wi,mi)):found=True;break
                if found:break
            if not found:errors.append('pattern_not_reproducible:'+str(rowid))
            else:verified+=1
    bridge=json.loads((root/'DEFINITION_BRIDGE.receipt.json').read_text(encoding='utf-8'))
    if sha(root/'DEFINITION_BRIDGE.sqlite')!=bridge['database_sha256']:errors.append('definition_bridge_sha')
    from sejong_supplement import supplemented_dictionary
    d=supplemented_dictionary(root)
    try:
        q=d.lookup('배','NNG',limit=3)
        if not q.get('sejong_sense_supplement',{}).get('annotated_contexts'):errors.append('combined_lookup_empty')
        (root/'EXAMPLE_combined_dictionary.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')
        # Replay a real indexed context through the public lookup interface.
        rr=s.execute('SELECT raw FROM segments WHERE id=?',(p.execute('SELECT first_segment FROM observations LIMIT 1').fetchone()[0],)).fetchone()
        words=[morphology(row[2]) for row in json.loads(zlib.decompress(rr[0]))];matches=[]
        for wi,mp in enumerate(words):
            for mi,m in enumerate(mp):
                if m[1] in LEX:
                    matches=d.sejong.matched_patterns(words,wi,mi)
                    if matches:break
            if matches:break
        if not matches:errors.append('public_pattern_lookup_empty')
        (root/'EXAMPLE_context_pattern.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:d.close()
    p.close();s.close()
    report={'status':'passed' if not errors else 'failed','errors':errors,'pattern_records_sampled':len(sample),'original_support_segments_verified':verified,'combined_dictionary_lookup':True,'public_pattern_lookup':bool(matches),'api_called':False}
    (root/'PATTERN_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(js(report))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()

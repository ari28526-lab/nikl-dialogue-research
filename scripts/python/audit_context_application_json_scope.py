"""Compare every project dialogue JSON utterance to existing Bareun input."""
import csv,gzip,hashlib,json,subprocess,time
from collections import Counter
from pathlib import Path
from apply_context_dictionary_full import ROOT,DEFAULT_CONFIG,read,atomic_json,sha,js,digest,path_under

def audit():
    cfg=read(DEFAULT_CONFIG);raw=Path(cfg['json_root']);base=Path(cfg['input_root']);refs={}
    for rel,h in csv.reader((base/'RECEIPT_INVENTORY.tsv').open(encoding='utf-8-sig'),delimiter='\t'):
        p=path_under(base,rel);r=read(p)
        if sha(p)!=h:raise ValueError('source receipt changed')
        refs[r['source_file']]=(rel,h,r)
    names=subprocess.check_output(['rg','--files',str(raw),'-g','*.json'],text=True,encoding='utf-8').splitlines();mapping={}
    for name in names:
        p=Path(name);rel=p.relative_to(raw);key=(Path(rel.parts[0])/(p.stem+'.csv')).as_posix()
        if key in mapping:raise ValueError('nonunique year plus basename JSON mapping')
        mapping[key]=p
    errors=[];counts=Counter();years={};bound=[];last=time.monotonic()
    if set(mapping)!=set(refs):errors.append({'JSON_without_Bareun':sorted(set(mapping)-set(refs)),'Bareun_without_JSON':sorted(set(refs)-set(mapping))})
    for key in sorted(set(mapping)&set(refs)):
        p=mapping[key];rel,rh,r=refs[key];rawbytes=p.read_bytes();data=json.loads(rawbytes.decode('utf-8-sig'));seq=[];empty=0;trimmed=0
        for doc in data.get('document',[]):
            for u in doc.get('utterance',[]):
                form=u.get('form') or '';trimmed+=form!=form.strip()
                if form.strip():seq.append((u['id'],str(u.get('speaker_id','')),form.strip()))
                else:empty+=1
        with gzip.open((base/rel).parent/'utterances.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
            other=[(u['utt_id'],u.get('speaker_id',''),u['form']) for u in csv.DictReader(f)]
        if seq!=other:errors.append({'source_file':key,'reason':'ordered_utterance_ID_speaker_or_text_mismatch','json_nonempty':len(seq),'bareun':len(other)})
        c={'files':1,'documents':len(data.get('document',[])),'json_utterances':len(seq)+empty,'bareun_utterances':len(other),'empty_JSON_utterances':empty,'trimmed_source_forms':trimmed}
        counts.update(c);y=key.split('/')[0];years.setdefault(y,Counter()).update(c)
        bound.append({'source_file':key,'json_relative':p.relative_to(raw).as_posix(),'json_sha256':hashlib.sha256(rawbytes).hexdigest(),'json_bytes':len(rawbytes),'json_utterances':len(seq)+empty,'documents':len(data.get('document',[])),'empty_utterances':empty,'bareun_receipt_relative':rel,'bareun_receipt_sha256':rh,'ordered_ID_speaker_trimmed_text_sha256':digest(seq)})
        if time.monotonic()-last>25:print(js({'JSON_scope_progress':counts['files'],'total':len(mapping)}),flush=True);last=time.monotonic()
    dest=ROOT/cfg['json_bindings'];dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('w',encoding='utf-8',newline='\n') as f:
        for row in bound:f.write(js(row)+'\n')
    report={'status':'passed' if not errors else 'failed','errors':errors,'counts':dict(counts),'years':{k:dict(v) for k,v in years.items()},'json_bindings_sha256':sha(dest),'input_inventory_sha256':sha(base/'RECEIPT_INVENTORY.tsv'),'normalization':'Exact year directory plus basename mapping; nested extraction folder retained in json_relative. IDs, speakers and order match; legacy CSV strips outer form whitespace. Empty JSON utterances counted separately.','api_called':False}
    atomic_json(ROOT/cfg['json_scope_report'],report);print(js(report),flush=True)
    if errors:raise ValueError('JSON scope mismatch')
if __name__=='__main__':audit()

"""Explicit confirmed revision JSON -> lossless per-document CSV/Parquet overlay.

Preserves base/pooled tables. Readers must select this receipt's affected-document
overlay; concatenating it to the base would duplicate records.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import update_delivery_revision as revision

COMMON=[('source_json',pa.string()),('source_sha256',pa.string()),('corpus',pa.string()),
        ('analysis_version',pa.string()),('year',pa.string()),('discourse_id',pa.string())]
DOC=pa.schema(COMMON+[('list_field',pa.string()),('metadata_json',pa.large_string()),
                     ('top_level_keys_json',pa.string()),('record_count',pa.int64())])
ROW=pa.schema(COMMON+[('record_kind',pa.string()),('record_index',pa.int64()),('utterance_id',pa.string()),
                     ('turn_order',pa.int64()),('text',pa.large_string()),('speaker_id',pa.string()),
                     ('start',pa.float64()),('end',pa.float64()),('analysis_status',pa.string()),('payload_json',pa.large_string())])
def dumps(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate JSON key')
        result[k]=v
    return result
def native(p):return json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=unique)
def safe(root,rel):
    p=revision.safe(root,rel)
    for ancestor in [p,*p.parents]:
        if ancestor==root.parent:break
        if ancestor.exists() and (ancestor.is_symlink() or getattr(ancestor.stat(),'st_file_attributes',0)&1024):raise ValueError('Reparse point prohibited')
    return p
def check_plan(root,plan):
    if plan['schema']!='delivery_regeneration.v1':raise ValueError('Wrong regeneration schema')
    selected=revision.revision_id(plan['selected_revision']);output=revision.revision_id(plan['output_revision'])
    if output==selected:raise ValueError('New output revision required')
    rp=safe(root,'updates/revisions/'+selected+'/REVISION.json')
    if revision.sha(rp)!=plan['revision_manifest_sha256']:raise ValueError('Selected revision changed')
    chain=revision.chain(root,selected);current=chain[0]
    if current.get('affected_documents')!=plan['affected_documents']:raise ValueError('Affected-document list differs')
    changed={}
    for version in chain:
        for x in version['changed_files']:changed.setdefault(x['logical_path'],x)
    seen=set();work=[]
    if len(plan['documents'])>1000:raise ValueError('Explicit affected-document batch too large')
    for item in plan['documents']:
        logical=item['logical_path'];safe(root,logical)
        decision=item['confirmation']
        if decision.get('status')!='confirmed' or decision.get('basis')!='researcher_recorded' or not decision.get('decision_id') or not decision.get('evidence'):
            raise ValueError('Explicit recorded confirmation required')
        if item['corpus'] not in {'modu','seoul','seoul_interviews'}:raise ValueError('Unknown corpus')
        if item.get('analysis_version')!='bareun_3.2':raise ValueError('Explicit current3.2 revision required; historical analysis is separate')
        if item['discourse_id'] in seen:raise ValueError('Duplicate affected document')
        seen.add(item['discourse_id'])
        if item['discourse_id'] not in plan['affected_documents']:raise ValueError('Document not declared affected')
        entry=changed.get(logical)
        if entry is None or not logical.endswith('.json'):raise ValueError('Changed native JSON required')
        p=safe(root,entry['physical_path'])
        if p.stat().st_size!=entry['bytes'] or revision.sha(p)!=entry['sha256']:raise ValueError('Changed JSON hash/size differs')
        work.append((item,entry,p))
    if seen!=set(plan['affected_documents']):raise ValueError('Every affected document must be regenerated')
    return work
def split(doc,item,entry):
    field='segments' if item['corpus']=='seoul_interviews' else 'utterances'
    did=doc['interview_id'] if field=='segments' else doc['discourse_id']
    if did!=item['discourse_id']:raise ValueError('Native document ID differs')
    common=dict(source_json=entry['physical_path'],source_sha256=entry['sha256'],corpus=item['corpus'],
                analysis_version='bareun_3.2',year=str(item['year']),discourse_id=did)
    d=dict(**common,list_field=field,metadata_json=dumps({k:v for k,v in doc.items() if k!=field}),
           top_level_keys_json=dumps(list(doc)),record_count=len(doc[field]))
    rows=[];ids=set()
    for index,value in enumerate(doc[field]):
        row=dict(**common,record_kind='interview_segment' if field=='segments' else 'utterance',record_index=index,
                 utterance_id=None,turn_order=None,text=None,speaker_id=None,start=None,end=None,analysis_status=None,payload_json=dumps(value))
        if field=='utterances':
            uid=value['utterance_id']
            if not isinstance(uid,str) or uid in ids or type(value['turn_order']) is not int or value['turn_order']!=index+1:raise ValueError('Native ID/order differs')
            ids.add(uid);original=value['original'];text=original.get('form' if item['corpus']=='modu' else 'text')
            row.update(utterance_id=uid,turn_order=value['turn_order'],text=text,speaker_id=original.get('speaker_id'),
                       start=original.get('start'),end=original.get('end'),analysis_status=value['analysis'].get('status'))
            for key in ['text','speaker_id','analysis_status']:
                if row[key] is not None and not isinstance(row[key],str):raise ValueError('Native string type differs')
            for key in ['start','end']:
                if row[key] is not None and (type(row[key]) not in {int,float} or not math.isfinite(row[key])):raise ValueError('Native time differs')
        rows.append(row)
    return d,rows
def reconstruct(d,rows):
    meta=json.loads(d['metadata_json']);meta[d['list_field']]=[json.loads(r['payload_json']) for r in rows]
    return {k:meta[k] for k in json.loads(d['top_level_keys_json'])}
def write_table(base,name,rows,schema):
    table=pa.Table.from_pylist(rows,schema=schema);parquet=base/(name+'.parquet');csvpath=base/(name+'.csv')
    pq.write_table(table,parquet,compression='zstd')
    with csvpath.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=schema.names);writer.writeheader()
        for row in rows:writer.writerow({k:dumps(row[k]) for k in schema.names})
    with csvpath.open(encoding='utf-8',newline='') as f:
        decoded=[{k:json.loads(v) for k,v in row.items()} for row in csv.DictReader(f)]
    csvtable=pa.Table.from_pylist(decoded,schema=schema);saved=pq.ParquetFile(parquet).read()
    if not saved.equals(table) or not csvtable.equals(table):raise ValueError('CSV/Parquet typed value/order roundtrip differs')
    return saved.to_pylist(),[dict(path=p.name,bytes=p.stat().st_size,sha256=revision.sha(p),rows=table.num_rows,table=name) for p in [csvpath,parquet]]
def build(root,plan,out,resume=False):
    root=root.resolve();out=out.resolve();work=check_plan(root,plan)
    allowed=safe(root,'updates/regenerated/'+plan['output_revision']).resolve()
    if out.is_relative_to(root) and out!=allowed:raise ValueError('Cannot overwrite immutable package scope')
    binding=dict(schema='delivery_regeneration_resume.v1',plan_sha256=hashlib.sha256(dumps(plan).encode()).hexdigest())
    if out.exists():
        if not resume:raise ValueError('Immutable regeneration destination exists; inspect receipt first')
        if native(out/'RESUME_BINDING.json')!=binding:raise ValueError('Resume plan binding differs')
        if (out/'FINAL.json').exists():raise ValueError('Completed destination is immutable')
    else:
        out.mkdir(parents=True)
        revision.save(out/'RESUME_BINDING.json',binding)
    receipts=[];files=[]
    for i,(item,entry,path) in enumerate(work):
        folder=safe(out,f'document-{i+1:05d}');folder.mkdir(exist_ok=True);doc=native(path);d,rows=split(doc,item,entry)
        prior=native(folder/'RECEIPT.json') if (folder/'RECEIPT.json').exists() else None
        if prior is not None:
            if (prior['logical_source'],prior['source_sha256'],prior['confirmation'],prior['corpus'],prior['year'],prior['discourse_id'])!=(item['logical_path'],entry['sha256'],item['confirmation'],item['corpus'],item['year'],item['discourse_id']):raise ValueError('Resume receipt binding differs')
            outputs={f['path']:f for f in prior['outputs']}
            if len(outputs)!=4 or set(outputs)!={'documents.csv','documents.parquet','records.csv','records.parquet'}:raise ValueError('Resume outputs differ')
            for name,f in outputs.items():
                p=safe(folder,name)
                if p.stat().st_size!=f['bytes'] or revision.sha(p)!=f['sha256']:raise ValueError('Resume completed output hash differs')
            rd=pq.ParquetFile(folder/'documents.parquet').read().to_pylist();rr=pq.ParquetFile(folder/'records.parquet').read().to_pylist()
            if rd!=[d] or rr!=rows:raise ValueError('Resume table values differ')
            docfiles=[outputs[k] for k in ['documents.csv','documents.parquet']];rowfiles=[outputs[k] for k in ['records.csv','records.parquet']]
        else:
            rd,docfiles=write_table(folder,'documents',[d],DOC);rr,rowfiles=write_table(folder,'records',rows,ROW)
        if dumps(reconstruct(rd[0],rr))!=dumps(doc) or revision.sha(path)!=entry['sha256']:raise ValueError('Native JSON reconstruction/source changed')
        rows_meta=docfiles+rowfiles
        for f in rows_meta:
            logical='common_parquet/revisions/'+plan['output_revision']+f'/document-{i+1:05d}/'+f['path']
            files.append(dict(logical_path=logical,source=str(folder/f['path']),bytes=f['bytes'],sha256=f['sha256']))
        receipt=dict(discourse_id=item['discourse_id'],corpus=item['corpus'],year=item['year'],logical_source=item['logical_path'],
                     source_sha256=entry['sha256'],confirmation=item['confirmation'],records=len(rows),outputs=rows_meta)
        revision.save(folder/'RECEIPT.json',receipt);receipts.append(receipt)
        rp=folder/'RECEIPT.json';files.append(dict(logical_path='common_parquet/revisions/'+plan['output_revision']+f'/document-{i+1:05d}/RECEIPT.json',source=str(rp),bytes=rp.stat().st_size,sha256=revision.sha(rp)))
    # Revalidate only explicitly affected sources/receipt bindings after generation.
    check_plan(root,plan)
    changes=dict(schema='delivery_changes.v1',revision=plan['output_revision'],parent=plan['selected_revision'],
                 affected_documents=plan['affected_documents'],files=files)
    revision.save(out/'CHANGES.json',changes)
    result=dict(schema='delivery_regeneration_receipt.v1',status='affected_document_csv_parquet_verified',
                selected_revision=plan['selected_revision'],output_revision=plan['output_revision'],
                selected_revision_sha256=plan['revision_manifest_sha256'],plan_sha256=hashlib.sha256(dumps(plan).encode()).hexdigest(),
                documents=receipts,generated_files=len(files),csv_cell_encoding='Each cell contains a JSON value; null and empty string remain distinct',
                changes_sha256=revision.sha(out/'CHANGES.json'),base_modified=False,unchanged_media_rehashed=False,
                unchanged_tree_scanned=False,pooled_base_tables_rewritten=False,revision_applied=False,
                selection_rule='Replace affected document records when reading this overlay; never concatenate duplicates',
                api_calls=0,delivery_complete=False)
    revision.save(out/'FINAL.json',result);return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--resume',action='store_true')
    a=ap.parse_args();result=build(a.package,native(a.plan),a.output,resume=a.resume);print(dumps(result))

"""Bounded explicit CSV shard replacement from confirmed native revisions.

Unchanged CSV cells remain strings. No inferred token/character coordinates.
"""
import csv
import argparse
import gzip
import hashlib
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import regenerate_delivery_revision_tables as native
import update_delivery_revision as updates

META=['_analysis_version','_corpus','_year','_source_csv','_source_row_index']


def cell(value):
    if value is None:return ''
    if type(value) not in (str,int,float,bool):raise ValueError('CSV morphology value must be scalar')
    if isinstance(value,float) and not native.math.isfinite(value):raise ValueError('Nonfinite CSV value')
    return str(value)


def build(root,plan,out):
    root=Path(root).resolve();out=Path(out).resolve()
    work=native.check_plan(root,plan['regeneration'])
    updates.revision_id(plan['shard_id'])
    logical=plan['source_csv'];source=native.safe(root,logical)
    mirror_source=plan.get('mirror_source_csv',logical)
    updates.safe(root,mirror_source)
    if logical!=mirror_source and not logical.endswith('/'+mirror_source):raise ValueError('Mirror source CSV suffix differs')
    if source.stat().st_size>128*1024*1024 or updates.sha(source)!=plan['source_csv_sha256']:
        raise ValueError('Explicit bounded source CSV binding differs')
    if plan['corpus'] not in ('modu','seoul'):raise ValueError('Recording or Modu shard required')
    if out.is_relative_to(root):raise ValueError('Stage new morphology output outside immutable package')
    if out.exists():raise ValueError('Immutable output already exists')
    opener=gzip.open if source.suffix=='.gz' else open
    with opener(source,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames
        if not fields or 'utt_id' not in fields or len(set(fields))!=len(fields) or set(fields)&set(META):raise ValueError('Source CSV fields differ')
        rows=[]
        for row in reader:
            if len(rows)>=100000 or None in row or any(v is None for v in row.values()):raise ValueError('Malformed or oversized CSV shard')
            rows.append(row)
    replacements={};source_bindings=[]
    for item,entry,path in work:
        if item['corpus']!=plan['corpus'] or str(item['year'])!=str(plan['year']):raise ValueError('Cross corpus/year replacement')
        doc=native.native(path)
        if doc['discourse_id']!=item['discourse_id']:raise ValueError('Document identity differs')
        ids=[u['utterance_id'] for u in doc['utterances']]
        if ids!=plan['document_utterance_ids'][item['discourse_id']]:raise ValueError('Explicit utterance order/coverage differs')
        for u in doc['utterances']:
            uid=u['utterance_id']
            if uid in replacements:raise ValueError('Duplicate affected utterance')
            new=[]
            for row in u['analysis']['morphemes']:
                if row.get('utt_id')!=uid or set(fields)-set(row):raise ValueError('Stored morphology ID or original fields differ')
                new.append({k:cell(row[k]) for k in fields})
            replacements[uid]=new
        source_bindings.append(dict(path=item['logical_path'],sha256=entry['sha256']))
    present={row['utt_id'] for row in rows}
    if any(new and uid not in present for uid,new in replacements.items()):
        raise ValueError('Newly analyzed utterance requires explicit insertion plan; no inferred row position')
    output=[];emitted=set();unchanged=0
    for row in rows:
        uid=row['utt_id']
        if uid in replacements:
            if uid not in emitted:output.extend(replacements[uid]);emitted.add(uid)
        else:output.append(row);unchanged+=1
    out.mkdir(parents=True)
    target=out/'morphemes.csv.gz'
    with gzip.open(target,'wt',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(output)
    with gzip.open(target,'rt',encoding='utf-8-sig',newline='') as f:
        if list(csv.DictReader(f))!=output:raise ValueError('CSV cell roundtrip differs')
    mirror=[dict(_analysis_version='bareun_3.2',_corpus=plan['corpus'],_year=str(plan['year']),
                 _source_csv=mirror_source,_source_row_index=i,**row) for i,row in enumerate(output)]
    schema=pa.schema([pa.field(k,pa.int64() if k=='_source_row_index' else pa.string(),nullable=False) for k in META+fields])
    table=pa.Table.from_pylist(mirror,schema=schema);parquet=out/'morphemes.parquet';pq.write_table(table,parquet,compression='zstd')
    if not pq.ParquetFile(parquet).read().equals(table):raise ValueError('String cell Parquet differs')
    native.check_plan(root,plan['regeneration'])
    if updates.sha(source)!=plan['source_csv_sha256']:raise ValueError('Original CSV changed during regeneration')
    result=dict(status='affected_morphology_csv_parquet_verified',schema='morphology_shard_revision.v1',
        source_csv=logical,mirror_source_csv=mirror_source,source_csv_sha256=plan['source_csv_sha256'],selected_revision=plan['regeneration']['selected_revision'],
        output_revision=plan['regeneration']['output_revision'],corpus=plan['corpus'],year=str(plan['year']),
        plan_sha256=hashlib.sha256(native.dumps(plan).encode()).hexdigest(),native_sources=source_bindings,
        columns=fields,rows=len(output),unchanged_rows_preserved=unchanged,affected_utterances=len(replacements),
        empty_affected_utterances=[uid for uid,value in replacements.items() if not value],
        outputs=[dict(path=p.name,bytes=p.stat().st_size,sha256=updates.sha(p)) for p in (target,parquet)],
        base_modified=False,api_calls=0,delivery_complete=False,revision_applied=False)
    updates.save(out/'RECEIPT.json',result)
    prefix='common_parquet/morphology_revisions/'+result['output_revision']+'/'+plan['shard_id']+'/'
    updates.safe(root,prefix)
    updates.save(out/'CHANGES.json',dict(schema='delivery_changes.v1',revision=result['output_revision'],
        parent=result['selected_revision'],affected_documents=plan['regeneration']['affected_documents'],
        files=[dict(logical_path=prefix+p.name,source=str(p),bytes=p.stat().st_size,sha256=updates.sha(p))
               for p in (target,parquet,out/'RECEIPT.json')]))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(native.dumps(build(a.package,native.native(a.plan),a.output)))

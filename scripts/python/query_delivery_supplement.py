"""Fetch stored historical evidence by exact target ID or source-file/ordinal."""
import argparse
import json
from pathlib import Path
import pyarrow.dataset as ds
from delivery_reader_io import read,save


def evidence(root,version,table,target_id=None,source_file=None,utterance_ordinal=None,limit=50):
    if not(target_id is not None or source_file is not None):raise ValueError('Provide an exact target ID or source file')
    if limit<1:raise ValueError('limit must be positive')
    paths=[]
    for item in read(root/'FINAL.json')['receipts']:
        rp=root/item['path'];r=read(rp);e=r['sources'][0]
        if e['version']==version and e['table']==table:paths.extend(str(rp.parent/o['path']) for o in r['outputs'])
    if not paths:raise ValueError('No completed partition for requested version/table')
    dataset=ds.dataset(paths,format='parquet');predicate=(ds.field('analysis_version')==version)&(ds.field('table')==table)
    if target_id is not None:predicate=predicate&(ds.field('target_id')==target_id)
    if source_file is not None:predicate=predicate&(ds.field('source_file')==source_file)
    if utterance_ordinal is not None:predicate=predicate&(ds.field('utterance_ordinal')==utterance_ordinal)
    total=dataset.count_rows(filter=predicate);rows=dataset.scanner(filter=predicate).head(limit).to_pylist()
    return dict(version=version,table=table,matching_rows=total,returned_rows=len(rows),truncated=total>len(rows),
        records=[dict(source_export=r['source_export'],source_sha256=r['source_sha256'],source_row_index=r['source_row_index'],
                      item=json.loads(r['item_json'])) for r in rows],human_gold=False,
        scope='Stored historical machine decisions, candidates and holds; not copied into 3.2.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--version',required=True);p.add_argument('--table',required=True)
    p.add_argument('--target-id');p.add_argument('--source-file');p.add_argument('--utterance-ordinal',type=int);p.add_argument('--limit',type=int,default=50)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    save(a.output,evidence(a.root,a.version,a.table,a.target_id,a.source_file,a.utterance_ordinal,a.limit))

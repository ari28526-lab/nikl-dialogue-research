"""Export one utterance with neighbouring turns and complete stored evidence."""
import argparse
import json
from pathlib import Path
import pyarrow.dataset as ds
from delivery_reader_io import read,save


def files(root,corpus,table):
    result=[]
    for item in read(root/'FINAL.json')['receipts']:
        rp=root/item['path'];r=read(rp)
        if r['sources'][0]['corpus']!=corpus:continue
        result.extend(str(rp.parent/o['path']) for o in r['outputs'] if o['table']==table)
    if not result:raise ValueError('No completed corpus partitions')
    return result


def context(root,corpus,discourse_id,utterance_id,radius=2):
    if radius<0:raise ValueError('radius must be nonnegative')
    if corpus not in ['seoul','modu']:raise ValueError('Use seoul recording ID for local utterance contexts')
    dataset=ds.dataset(files(root,corpus,'records'),format='parquet')
    base=(ds.field('discourse_id')==discourse_id)&(ds.field('corpus')==corpus)
    target=dataset.to_table(filter=base&(ds.field('utterance_id')==utterance_id),columns=['record_index','source_json']).to_pylist()
    if len(target)!=1:raise ValueError('Expected exactly one utterance; check corpus, discourse and ID')
    index=target[0]['record_index']
    nearby=dataset.to_table(filter=base&(ds.field('source_json')==target[0]['source_json'])&(ds.field('record_index')>=max(0,index-radius))&(ds.field('record_index')<=index+radius)).to_pylist()
    nearby.sort(key=lambda r:r['record_index'])
    documents=ds.dataset(files(root,corpus,'documents'),format='parquet').to_table(filter=base&(ds.field('source_json')==target[0]['source_json'])).to_pylist()
    if len(documents)!=1:raise ValueError('Missing or ambiguous discourse metadata')
    return dict(corpus=corpus,discourse_id=discourse_id,target_utterance_id=utterance_id,radius=radius,
        source_json=target[0]['source_json'],source_sha256=documents[0]['source_sha256'],
        discourse_metadata=json.loads(documents[0]['metadata_json']),
        utterances=[json.loads(r['payload_json']) for r in nearby],
        coordinate_policy='Original local source times; original JSON null and empty values retained.',
        human_verified=False,scope='Stored machine analysis and evidence; no new semantic judgment or API call.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--corpus',choices=['seoul','modu'],required=True)
    p.add_argument('--discourse-id',required=True);p.add_argument('--utterance-id',required=True)
    p.add_argument('--radius',type=int,default=2);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    save(a.output,context(a.root,a.corpus,a.discourse_id,a.utterance_id,a.radius))

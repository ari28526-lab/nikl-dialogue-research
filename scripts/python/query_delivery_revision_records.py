"""Stream selected native-document records across base and revision tables."""
import argparse
import json
from pathlib import Path
import pyarrow.parquet as pq
from query_delivery_discourse import files
from delivery_revision_tables import iter_selected_records


def query(package, base_tables, revision, corpus, limit=100, contains=None):
    if not 1 <= limit <= 10000:
        raise ValueError('Output limit must be between 1 and 10000')
    def base_rows():
        for filename in files(base_tables, corpus, 'records'):
            for batch in pq.ParquetFile(filename).iter_batches(batch_size=4096):
                yield from batch.to_pylist()
    rows=[]
    for row in iter_selected_records(package, revision, base_rows()):
        if row['corpus'] != corpus:
            continue
        if contains is not None and contains not in (row['text'] or ''):
            continue
        rows.append(row)
        if len(rows) == limit:
            break
    return dict(selected_revision=revision, corpus=corpus, rows=rows,
                output_limit=limit, complete_corpus_count=False,
                selection_rule='Replace affected documents; retain unchanged base rows',
                human_verified=False, api_calls=0)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--base-tables',type=Path,required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--corpus',choices=['modu','seoul'],required=True)
    p.add_argument('--limit',type=int,default=100)
    p.add_argument('--contains')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=query(a.package,a.base_tables,a.revision,a.corpus,a.limit,a.contains)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

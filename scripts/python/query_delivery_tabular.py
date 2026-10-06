"""Small reproducible per-table count/ID/coordinate query (also implemented in R)."""
import argparse
from pathlib import Path
import pyarrow.parquet as pq
from delivery_reader_io import read, save


def query(root):
    results=[]
    for item in read(root/'FINAL.json')['receipts']:
        recpath=root/item['path']; rec=read(recpath); ids=[]; rows=0; nonnegative=0; missing=0
        e=rec['source']; names=e['columns']; idcol=next((k for k in ['utt_id','word_id','source_file','speaker_id'] if k in names),None)
        timecol=next((k for k in ['duration_seconds','utterance_start','start','source_start_seconds','begin_seconds'] if any(f[0]==k for f in e['typed_fields'])),None)
        cols=['_delivery_source_row_index']+([idcol] if idcol else [])+(['_delivery_typed_'+timecol] if timecol else [])
        for output in rec['outputs']:
            for batch in pq.ParquetFile(recpath.parent/output['path']).iter_batches(columns=cols,batch_size=25000):
                for row in batch.to_pylist():
                    rows+=1
                    if timecol:
                        t=row['_delivery_typed_'+timecol]; missing+=t is None; nonnegative+=t is not None and t>=0
                    if len(ids)<20:
                        ids.append(str(row['_delivery_source_row_index'])+'|'+(row[idcol] if idcol else ''))
        results.append(dict(partition=e['partition'],rows=rows,coordinate_column=timecol or '',missing_coordinates=missing,
                            nonnegative_coordinates=nonnegative,first_keys=ids))
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    save(a.output,query(a.root))

"""Portable bounded-output query example for the lossless morphology mirror."""
import argparse
from collections import Counter
import json
from pathlib import Path
import pyarrow.parquet as pq


def query(root, version, pos='NNG', max_files=0, package=None, revision=None):
    if revision is not None and (package is None or version!='bareun_3.2' or max_files):
        raise ValueError('Revision morphology query requires package, current3.2 and full base partition selection')
    files = sorted(root.glob(f'version={version}/corpus=modu/year=*/table=morphemes/group-*/part-*.parquet'))
    assert files, 'No morphology partitions found'
    if max_files:
        files = files[:max_files]
    counts = Counter(); selected = []; total = 0
    columns = ['_source_csv', '_source_row_index', 'utt_id', 'token_index', 'morph_index', 'pos']
    def base_rows():
        for path in files:
            for batch in pq.ParquetFile(path).iter_batches(columns=None if revision else columns, batch_size=25000):
                yield from batch.to_pylist()
    rows=base_rows()
    if revision is not None:
        from delivery_morphology_revision import selected_rows
        rows=selected_rows(package,revision,rows)
    for row in rows:
                total += 1; counts[row['pos']] += 1
                if row['pos'] == pos and len(selected) < 50:
                    selected.append('|'.join(str(row[k]) for k in columns[:-1]))
    result=dict(version=version, pos=pos, files=len(files), rows=total, counts=dict(sorted(counts.items())), selected_keys=selected,
                scope='first max_files partitions' if max_files else 'all morphology partitions', human_verified=False)
    if revision is not None:result.update(selected_revision=revision,selection_rule='Replace affected CSV shards; never concatenate base and revised rows')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--version', default='bareun_3.2')
    parser.add_argument('--pos', default='NNG')
    parser.add_argument('--max-files', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--package',type=Path)
    parser.add_argument('--revision')
    args = parser.parse_args()
    args.output.write_text(json.dumps(query(args.root, args.version, args.pos, args.max_files,args.package,args.revision), ensure_ascii=False, indent=2), encoding='utf-8')

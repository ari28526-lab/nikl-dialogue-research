"""Stream morphology CSV-cell mirror with explicit verified shard replacement."""
from pathlib import Path, PurePosixPath
import delivery_revision_view as views
import regenerate_delivery_revision_tables as native
import update_delivery_revision as updates


def selected_rows(root,revision,base_rows):
    view=views.View(Path(root),revision);shards={};covered=set()
    for logical,entry in view.entries.items():
        if not logical.startswith('common_parquet/morphology_revisions/') or not logical.endswith('/receipt.json'):continue
        receipt=native.native(view.path(entry['logical_path']))
        if receipt['status']!='affected_morphology_csv_parquet_verified':raise ValueError('Incomplete morphology revision')
        if any(updates.sha(view.path(s['path']))!=s['sha256'] for s in receipt['native_sources']):continue
        key=(receipt['corpus'],receipt['year'],receipt['mirror_source_csv'])
        if key in shards:continue  # newest chain entry wins
        parent=PurePosixPath(entry['logical_path']).parent
        outputs={f['path']:f for f in receipt['outputs']}
        for name,f in outputs.items():
            rel=(parent/name).as_posix()
            if rel.casefold() not in view.entries:raise ValueError('Undeclared morphology output')
            p=view.path(rel)
            if p.stat().st_size!=f['bytes'] or updates.sha(p)!=f['sha256']:raise ValueError('Morphology output binding differs')
        table=native.pq.ParquetFile(view.path((parent/'morphemes.parquet').as_posix())).read()
        if table.num_rows!=receipt['rows']:raise ValueError('Morphology revision row count differs')
        rows=table.to_pylist()
        for i,row in enumerate(rows):
            if (row['_corpus'],row['_year'],row['_source_csv'],row['_analysis_version'],row['_source_row_index'])!=(*key,'bareun_3.2',i):raise ValueError('Morphology row provenance/order differs')
        shards[key]=rows;covered.update(s['path'].casefold() for s in receipt['native_sources'])
    for logical in view.entries:
        if (logical.startswith(('analysis/','discourse_json/')) or '/discourse_json/' in logical) and logical.endswith('.json') and logical not in covered:
            raise ValueError('Changed native document lacks current morphology tables')
    emitted=set()
    for row in base_rows:
        key=(row['_corpus'],row['_year'],row['_source_csv'])
        if key in shards:
            if key not in emitted:yield from shards[key];emitted.add(key)
        else:yield row
    for key in sorted(shards):
        if key not in emitted:yield from shards[key]

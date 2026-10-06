"""Validated explicit partition routing for independent R aggregation."""
import argparse
from pathlib import Path
import delivery_morphology_revision as selection
import delivery_revision_view as views
import regenerate_delivery_revision_tables as native
import update_delivery_revision as updates


def plan(package,base,revision):
    package=Path(package).resolve();base=Path(base).resolve()
    if not base.is_relative_to(package):raise ValueError('Base mirror must be inside package')
    # Validate selected outputs/provenance before exporting any routing.
    for _ in selection.selected_rows(package,revision,iter([])):pass
    view=views.View(package,revision);shards=[];seen=set()
    for logical,entry in view.entries.items():
        if not logical.startswith('common_parquet/morphology_revisions/') or not logical.endswith('/receipt.json'):continue
        receipt=native.native(view.path(entry['logical_path']))
        if any(updates.sha(view.path(s['path']))!=s['sha256'] for s in receipt['native_sources']):continue
        key=(receipt['corpus'],receipt['year'],receipt['mirror_source_csv'])
        if key in seen:continue
        seen.add(key)
        path=view.path((Path(entry['logical_path']).parent/'morphemes.parquet').as_posix())
        shards.append(dict(corpus=key[0],year=key[1],source_csv=key[2],path=path.relative_to(package).as_posix(),sha256=updates.sha(path)))
    files=sorted(base.glob('version=bareun_3.2/corpus=modu/year=*/table=morphemes/group-*/part-*.parquet'))
    if not files:raise ValueError('No current morphology partitions')
    return dict(schema='morphology_selection_plan.v1',revision=revision,
                base_files=[p.relative_to(package).as_posix() for p in files],
                shards=[s for s in shards if s['corpus']=='modu'],
                audit_scope='Selected overlay outputs verified; immutable base hashes reused, not rehashed')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--revision',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();updates.save(a.output,plan(a.package,a.base,a.revision))

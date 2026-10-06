"""Read one explicitly selected regenerated document; never concatenate base rows.

Requires an explicit receipt logical path from the applied revision manifest.
Does not discover omissions, scan media, or replace whole-package acceptance.
"""
from pathlib import Path, PurePosixPath
import delivery_revision_view as view_module
import regenerate_delivery_revision_tables as tables
import update_delivery_revision as updates


def iter_selected_records(root, revision, base_rows):
    """Stream base rows with complete document replacement from a pinned overlay.

    Discover only receipts declared in the selected revision chain, never the
    package tree. Validate all overlays before emitting any query rows.
    """
    view = view_module.View(Path(root), revision)
    selected = {}
    changed_sources = set()
    for logical, entry in view.entries.items():
        if logical.startswith('common_parquet/revisions/') and logical.endswith('/receipt.json'):
            receipt = tables.native(view.path(entry['logical_path']))
            key = (receipt['corpus'], str(receipt['year']), receipt['discourse_id'])
            source = receipt['logical_source']
            # Older table receipts can remain declared in parent revisions.
            # Select the receipt matching the currently selected native source.
            if updates.sha(view.path(source)) != receipt['source_sha256']:
                continue
            value = read_document(root, revision, entry['logical_path'], source,
                                  receipt['corpus'], receipt['year'], receipt['discourse_id'])
            if key in selected and selected[key]['records'] != value['records']:
                raise ValueError('Conflicting selected document tables')
            selected[key] = value
            changed_sources.add(source.casefold())
    for item in updates.chain(view.root, revision):
        for entry in item['changed_files']:
            logical = entry['logical_path']
            # Known native discourse namespaces only; arbitrary JSON metadata
            # must not be mistaken for a changed linguistic document.
            if (logical.startswith(('analysis/', 'discourse_json/')) or '/discourse_json/' in logical) and logical.endswith('.json'):
                if logical.casefold() not in changed_sources:
                    raise ValueError('Changed native document lacks matching regenerated tables')
    emitted = set()
    for row in base_rows:
        key = (row['corpus'], str(row['year']), row['discourse_id'])
        if key in selected:
            if key not in emitted:
                yield from selected[key]['records']
                emitted.add(key)
        else:
            yield row
    for key in sorted(selected):
        if key not in emitted:
            yield from selected[key]['records']


def read_document(root, revision, receipt_logical, logical_source, corpus, year, discourse_id):
    view = view_module.View(Path(root), revision)
    if not receipt_logical.startswith('common_parquet/revisions/') or not receipt_logical.endswith('/RECEIPT.json'):
        raise ValueError('Explicit regenerated receipt required')
    def declared(logical):
        if logical.casefold() not in view.entries:
            raise ValueError('Selected revision does not declare this table/receipt')
        path = view.path(logical)
        if path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError('Bounded document reader size limit exceeded')
        return path
    receipt = tables.native(declared(receipt_logical))
    if (receipt['logical_source'], receipt['corpus'], receipt['year'], receipt['discourse_id']) != (logical_source, corpus, year, discourse_id):
        raise ValueError('Receipt document identity differs')
    confirmation = receipt['confirmation']
    if confirmation.get('status') != 'confirmed' or confirmation.get('basis') != 'researcher_recorded' or not confirmation.get('decision_id') or not confirmation.get('evidence'):
        raise ValueError('Confirmed researcher decision required')
    source = view.path(logical_source)
    if source.stat().st_size > 256 * 1024 * 1024 or updates.sha(source) != receipt['source_sha256']:
        raise ValueError('Selected native JSON changed without matching regenerated tables')
    parent = str(PurePosixPath(receipt_logical).parent)
    outputs = {x['path']: x for x in receipt['outputs']}
    if len(outputs) != len(receipt['outputs']):
        raise ValueError('Duplicate receipt outputs')
    loaded = []
    for name, schema in [('documents', tables.DOC), ('records', tables.ROW)]:
        filename = name + '.parquet'
        expected = outputs[filename]
        path = declared(parent + '/' + filename)
        if path.stat().st_size != expected['bytes'] or updates.sha(path) != expected['sha256']:
            raise ValueError('Receipt table hash/size differs')
        table = tables.pq.ParquetFile(path).read()
        if table.schema != schema or table.num_rows != expected['rows']:
            raise ValueError('Table schema/count differs')
        loaded.append(table.to_pylist())
    docs, rows = loaded
    if len(docs) != 1 or len(rows) != receipt['records']:
        raise ValueError('Document/count differs')
    d = docs[0]
    for row in [d] + rows:
        if (row['corpus'], row['year'], row['discourse_id'], row['analysis_version'], row['source_sha256']) != (corpus, year, discourse_id, 'bareun_3.2', receipt['source_sha256']):
            raise ValueError('Table provenance differs')
    if [r['record_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('Native record order differs')
    native = tables.native(source)
    expected_doc, expected_rows = tables.split(native,
        dict(corpus=corpus, year=year, discourse_id=discourse_id),
        dict(physical_path=d['source_json'], sha256=receipt['source_sha256']))
    if docs != [expected_doc] or rows != expected_rows:
        raise ValueError('Projected columns differ from selected native JSON')
    if tables.dumps(tables.reconstruct(d, rows)) != tables.dumps(native) or updates.sha(source) != receipt['source_sha256']:
        raise ValueError('Table reconstruction differs from selected native JSON')
    return {'document': d, 'records': rows, 'native': native, 'selection': revision,
            'selection_rule': 'Replace this document; do not concatenate base records'}

"""Build a small, allowlisted reader bundle independently of active corpus I/O."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from build_portable_supplement_guide import build_payload

PYTHON = ['delivery_reader_io.py', 'query_delivery_parquet.py', 'query_delivery_tabular.py',
          'query_delivery_discourse.py', 'query_delivery_supplement.py', 'query_delivery_links.py',
          'delivery_revision_view.py', 'update_delivery_revision.py', 'query_delivery_historical_textgrid.py']
R = ['query_delivery_parquet.R', 'query_delivery_tabular.R', 'query_delivery_discourse.R',
     'query_delivery_supplement.R', 'query_delivery_links.R', 'query_delivery_revision.R']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def write_same(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Existing bundle differs; use a new version: ' + str(path))
    else:
        with path.open('xb') as f:
            f.write(data)
    if sha(path.read_bytes()) != sha(data):
        raise ValueError('Bundle read-back mismatch: ' + str(path))


def build(repo, output):
    payload = {}
    for lang, names in [('python', PYTHON), ('R', R)]:
        for name in names:
            rel = f'scripts/{lang}/{name}'
            payload[rel] = (repo/rel).read_bytes()
    guide = (repo/'docs/delivery/PORTABLE_GUIDE.md').read_text(encoding='utf-8')
    payload['GUIDE.md'] = guide.encode('utf-8')
    payload['index.html'] = ('<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<title>연구 자료 열람 안내 — 준비본</title><style>body{max-width:1000px;margin:40px auto;'
        'font:17px/1.7 sans-serif;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
        '<h1>연구 자료 열람 안내 — 준비본</h1><p><a href="GUIDE.md">GUIDE.md</a> · '
        '<a href="source_inventory.json">자료 위치</a> · <a href="examples.json">실행 예제</a> · '
        '<a href="supplement_reader/index.html">실제 보완 예시·출처</a></p>'
        '<pre>' + html.escape(guide) + '</pre></html>').encode('utf-8')
    config = json.loads((repo/'outputs/reports/bareun32_reanalysis_plan_20260926/DELIVERY_COPY_SOURCES_20260929.json').read_text(encoding='utf-8-sig'))
    payload.update(build_payload(repo, config['roots']))
    payload['source_inventory.json'] = encoded(dict(schema='reader_sources.v1',
        path_base='package_root', status='declared_copy_scope_not_completion_proof',
        roots=[dict(role=x['role'], path=x['destination'], completion='Check COPY_FINAL and DELIVERY_FINAL') for x in config['roots']],
        links=dict(path='metadata/semantic_links', completion='Check FINAL.json'),
        source_identity='Exact original paths and source hashes remain in the package copy contract and provenance.'))
    payload['requirements.txt'] = b'pyarrow==21.0.0\n'
    payload['environment.json'] = encoded(dict(python='3.13', pyarrow='21.0.0', R='4.6.1',
        R_arrow='25.0.1', R_packages=['arrow','jsonlite','dplyr','tidyselect'],
        installation='Separate environment; not auto-installed', revision_support='Windows',
        R_revision_scope='Shared Python path/SHA; independent R selected JSON value/ID/order check'))
    payload['examples.json'] = encoded(dict(schema='reader_examples.v1', kind='argument_templates_not_corpus_results',
        replacements=['PYTHON','RSCRIPT','TOOLS','PACKAGE','OUTPUT','DISCOURSE_ID','UTTERANCE_ID','TARGET_ID','R_ARROW_LIB'],
        examples=[
            dict(name='native_context', argv=['PYTHON','TOOLS/scripts/python/query_delivery_discourse.py','PACKAGE/common_parquet/discourse','--corpus','modu','--discourse-id','DISCOURSE_ID','--utterance-id','UTTERANCE_ID','--radius','2','--output','OUTPUT/context.json']),
            dict(name='linked_context_after_index_completion', argv=['PYTHON','TOOLS/scripts/python/query_delivery_links.py','--package','PACKAGE','--links','PACKAGE/metadata/semantic_links','--corpus','modu','--utterance-id','UTTERANCE_ID','--output','OUTPUT/links.json']),
            dict(name='limited_pos_sample', argv=['PYTHON','TOOLS/scripts/python/query_delivery_parquet.py','--root','PACKAGE/common_parquet/csv_mirror_and_base_json','--version','bareun_3.2','--pos','NNG','--max-files','1','--output','OUTPUT/pos_sample.json']),
            dict(name='historical_textgrid_after_index_completion', argv=['PYTHON','TOOLS/scripts/python/query_delivery_historical_textgrid.py','--package','PACKAGE','--utterance-id','UTTERANCE_ID','--verify-sha','--output','OUTPUT/historical_textgrid.json']),
            dict(name='R_native_context', argv=['RSCRIPT','TOOLS/scripts/R/query_delivery_discourse.R','PACKAGE/common_parquet/discourse','modu','DISCOURSE_ID','UTTERANCE_ID','2','OUTPUT/r_context.json','R_ARROW_LIB'])]))
    manifest = dict(schema='reader_bundle.v1', status='reader_bundle_prepared_not_delivery_final',
        files=[dict(path=k, bytes=len(v), sha256=sha(v)) for k,v in sorted(payload.items())],
        checks='Each bundled file independently read back; runtime/relocation pilot recorded separately',
        delivery_complete=False)
    for relative, data in payload.items():
        write_same(output/relative, data)
    write_same(output/'BUNDLE_MANIFEST.json', encoded(manifest))
    return dict(files=len(payload), bytes=sum(len(v) for v in payload.values()), manifest_sha256=sha(encoded(manifest)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(build(a.repo,a.output)))

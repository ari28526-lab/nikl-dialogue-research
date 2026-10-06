"""Read one portable discourse context and its explicit media references."""
import argparse
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3


def safe(root, rel):
    p = PurePosixPath(rel)
    if not p.parts or p.is_absolute() or '\\' in rel or any(x == '..' or ':' in x for x in p.parts):
        raise ValueError('Unsafe package reference')
    target = root.joinpath(*p.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Escaping package reference')
    return target


def refs(value):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value and 'bytes' in value:
            yield value
        else:
            for child in value.values():
                yield from refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs(child)


def context(package, links, corpus, utterance_id, radius=2, verify_hashes=False, revision=None):
    if radius < 0:
        raise ValueError('Negative context radius')
    package = package.resolve(); links = links.resolve()
    view = None
    if revision is not None:
        from delivery_revision_view import View
        view = View(package, revision)
    def selected(path):
        return view.path(path.relative_to(package).as_posix()) if view else path
    with closing(sqlite3.connect(selected(links / 'UTTERANCE_INDEX.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('SELECT discourse_id,document_path,turn_order FROM utterances WHERE corpus=? AND utterance_id=?', (corpus, utterance_id)).fetchone()
    if row is None:
        raise ValueError('Utterance absent from completed index')
    logical_document = safe(links, row[1])
    document_path = selected(logical_document)
    receipt = json.loads(selected(logical_document.with_name(logical_document.name + '.receipt.json')).read_text(encoding='utf-8'))
    if hashlib.sha256(document_path.read_bytes()).hexdigest() != receipt['sha256']:
        raise ValueError('Link document SHA mismatch')
    with gzip.open(document_path, 'rt', encoding='utf-8') as f:
        document = json.load(f)
    source = document['source_discourse']
    path = selected(safe(package, source['path'])); raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source['sha256']:
        raise ValueError('Native discourse SHA mismatch')
    native = json.loads(raw.decode('utf-8-sig'))
    start = max(0, row[2] - 1 - radius); end = row[2] + radius
    result = dict(corpus=corpus, discourse_id=row[0], target_utterance_id=utterance_id,
                  metadata={k:v for k,v in native.items() if k != 'utterances'},
                  utterances=native['utterances'][start:end], links=document['utterances'][start:end],
                  references=document['references'], source_discourse=source,
                  references_base='package_root', time_policy=document['time_policy'], human_verified=False)
    if revision is not None:
        result.update(selected_revision=revision,
                      resolved_source_discourse=path.relative_to(package).as_posix(),
                      resolved_link_document=document_path.relative_to(package).as_posix())
    if [u['utterance_id'] for u in result['utterances']] != [u['utterance_id'] for u in result['links']]:
        raise ValueError('Native/link order mismatch')
    for ref in refs({k:result[k] for k in ['references', 'source_discourse', 'links']}):
        p = selected(safe(package, ref['path']))
        if not p.is_file() or p.stat().st_size != ref['bytes']:
            raise ValueError('Missing or changed reference: ' + ref['path'])
        if verify_hashes or p != safe(package, ref['path']):
            h = hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(4*1024*1024), b''):
                    h.update(b)
            if h.hexdigest() != ref['sha256']:
                raise ValueError('Reference SHA mismatch: ' + ref['path'])
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--package', type=Path, required=True)
    p.add_argument('--links', type=Path, required=True); p.add_argument('--corpus', choices=['modu','seoul'], required=True)
    p.add_argument('--utterance-id', required=True); p.add_argument('--radius', type=int, default=2)
    p.add_argument('--verify-hashes', action='store_true'); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--revision', help='Explicit immutable revision; base remains the default')
    a=p.parse_args(); value=context(a.package,a.links,a.corpus,a.utterance_id,a.radius,a.verify_hashes,a.revision)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

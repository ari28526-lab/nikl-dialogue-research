"""Register audited analysis releases and read one explicitly selected source."""
import argparse
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def child(root, relative):
    parts = PurePosixPath(relative)
    if parts.is_absolute() or '..' in parts.parts or ':' in relative or '\\' in relative:
        raise ValueError('Unsafe release-relative path')
    target = root.joinpath(*parts.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Release path escapes its root')
    return target


def register(catalog, version, root, audit_path, dictionary, dictionary_receipt):
    root = root.resolve()
    final = read(root / 'FULL_FINAL.json')
    audit = read(audit_path)
    contract = read(root / 'CONTRACT.json')
    contract_hash = hashlib.sha256(json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (audit.get('status') != 'passed_complete_baseline'
            or audit.get('full_final_sha256') != sha(root / 'FULL_FINAL.json')
            or audit.get('contract_sha256') != final['contract_sha256']
            or contract_hash != final['contract_sha256']
            or audit.get('audited_requests') != contract['config']['max_requests']
            or final.get('status') != 'complete_with_explicit_coverage_reviews'):
        raise ValueError('Full independent audit must pass before registration')
    receipt = read(dictionary_receipt)
    if receipt.get('status') != 'complete' or sha(dictionary) != receipt['database_sha256']:
        raise ValueError('Dictionary receipt does not match its database')
    sources = {}
    for corpus in ('seoul', 'modu'):
        sources[corpus] = {}
        for path in sorted((root / 'full' / corpus).rglob('RECEIPT.json')):
            item = read(path)
            if item['binding']['contract_sha256'] != final['contract_sha256']:
                raise ValueError('Source belongs to a different analysis contract')
            source = item['binding'].get('source_file', path.parent.name)
            if source in sources[corpus]:
                raise ValueError('Duplicate source identity')
            sources[corpus][source] = {
                'receipt': path.relative_to(root).as_posix(), 'sha256': sha(path),
            }
        if len(sources[corpus]) != final['counts'][corpus + '_sources']:
            raise ValueError('Source count differs from completed release')
    release = dict(
        root=str(root), analysis_version=contract['config']['version_provenance']['requested_release'],
        final_sha256=sha(root / 'FULL_FINAL.json'), audit=str(audit_path.resolve()),
        audit_sha256=sha(audit_path), contract_sha256=final['contract_sha256'],
        dictionary=str(dictionary.resolve()), dictionary_receipt=str(dictionary_receipt.resolve()),
        dictionary_sha256=receipt['database_sha256'],
        dictionary_mtime_ns=dictionary.stat().st_mtime_ns,
        dictionary_release=receipt.get('release_date', 'unspecified'),
        dictionary_receipt_sha256=sha(dictionary_receipt), sources=sources,
        semantic_unit='urimalsaem_group_id',
    )
    # Exclusive publication never overwrites or implicitly selects an older release.
    catalog.parent.mkdir(parents=True, exist_ok=True)
    with catalog.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema='analysis_catalog.v1', releases={version: release}),
                  stream, ensure_ascii=False, indent=2)
    return release


def selected_source(catalog, version, corpus, source):
    release = read(catalog)['releases'][version]
    root = Path(release['root'])
    if (sha(root / 'FULL_FINAL.json') != release['final_sha256']
            or sha(release['audit']) != release['audit_sha256']):
        raise ValueError('Selected release completion or audit changed')
    reference = release['sources'][corpus][source]
    receipt_path = child(root, reference['receipt'])
    if sha(receipt_path) != reference['sha256']:
        raise ValueError('Source receipt changed')
    receipt = read(receipt_path)
    filename = 'discourse.json.gz'
    path = receipt_path.parent / filename
    expected = receipt['outputs'][filename]
    if path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
        raise ValueError('Selected discourse changed')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        documents = json.load(stream)
    return release, documents if isinstance(documents, list) else [documents]


def dictionary_groups(release, lemma, pos=None, target_id=None):
    receipt_path = release['dictionary_receipt']
    if sha(receipt_path) != release['dictionary_receipt_sha256']:
        raise ValueError('Dictionary receipt changed')
    # Full database SHA was checked on registration. Verify on explicit request,
    # while normal lookup opens SQLite read-only and checks its publication size.
    receipt = read(receipt_path)
    path = Path(release['dictionary'])
    if (path.stat().st_size != receipt['bytes']
            or path.stat().st_mtime_ns != release['dictionary_mtime_ns']):
        raise ValueError('Dictionary size changed')
    forms = [lemma]
    if pos in {'VV', 'VA', 'VX', 'VCP', 'VCN', 'XSV', 'XSA'} and not lemma.endswith('다'):
        forms.append(lemma + '다')
    groups = {}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        marks = ','.join('?' for _ in forms)
        rows = db.execute(
            f'SELECT target,group_id,word,pos,definition FROM entries WHERE lemma IN ({marks}) '
            'ORDER BY group_id,target', forms,
        ).fetchall()
        machine_group = None
        if target_id is not None:
            match = db.execute('SELECT group_id FROM entries WHERE target=?', (str(target_id),)).fetchone()
            machine_group = match[0] if match else None
    for target, group, word, entry_pos, definition in rows:
        groups.setdefault(group, dict(group_id=group, entries=[]))['entries'].append(
            dict(target_id=target, word=word, pos=entry_pos, definition=definition))
    return dict(candidate_groups=list(groups.values()), machine_group_id=machine_group,
                unit='urimalsaem_group_id', human_verified=False)


def context(catalog, version, corpus, source, utterance_id, radius=2):
    if not 0 <= radius <= 20:
        raise ValueError('Context radius must be between 0 and 20')
    release, documents = selected_source(catalog, version, corpus, source)
    matches = [(doc, i) for doc in documents
               for i, row in enumerate(doc['utterances']) if row['utterance_id'] == utterance_id]
    if len(matches) != 1:
        raise ValueError('Utterance is absent or ambiguous in the selected source')
    doc, index = matches[0]
    return dict(selected_release=version, analysis_version=release['analysis_version'],
                dictionary_release=release['dictionary_release'], semantic_unit='urimalsaem_group_id',
                corpus=corpus, source=source, target_utterance_id=utterance_id,
                utterances=doc['utterances'][max(0, index-radius):index+radius+1],
                analysis_is_human_verified=False,
                coordinate_policy='Original character spans and utterance times; no inferred phone boundaries')


def search(catalog, version, corpus, lemma, pos=None, source=None, limit=100):
    if not lemma or not 1 <= limit <= 1000:
        raise ValueError('A lemma and output limit between 1 and 1000 are required')
    release = read(catalog)['releases'][version]
    sources = [source] if source is not None else sorted(release['sources'][corpus])
    found = []
    scanned = 0
    for identity in sources:
        _, documents = selected_source(catalog, version, corpus, identity)
        scanned += 1
        for document in documents:
            for utterance in document['utterances']:
                for morph in utterance['analysis']['morphemes']:
                    form = morph.get('morph_surface', morph.get('morph'))
                    if form == lemma and (pos is None or pos == morph['pos']):
                        found.append(dict(source=identity, utterance_id=utterance['utterance_id'],
                                          morphology=morph))
                        if len(found) == limit:
                            return dict(selected_release=version, rows=found,
                                        scanned_sources=scanned, stopped_at_limit=True)
    return dict(selected_release=version, rows=found, scanned_sources=scanned,
                stopped_at_limit=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    registration = commands.add_parser('register')
    registration.add_argument('--catalog', type=Path, required=True)
    registration.add_argument('--version', required=True)
    registration.add_argument('--root', type=Path, required=True)
    registration.add_argument('--audit', type=Path, required=True)
    registration.add_argument('--dictionary', type=Path, required=True)
    registration.add_argument('--dictionary-receipt', type=Path, required=True)
    query = commands.add_parser('context')
    query.add_argument('--catalog', type=Path, required=True)
    query.add_argument('--version', required=True)
    query.add_argument('--corpus', choices=['seoul', 'modu'], required=True)
    query.add_argument('--source', required=True)
    query.add_argument('--utterance-id', required=True)
    query.add_argument('--radius', type=int, default=2)
    lookup = commands.add_parser('groups')
    lookup.add_argument('--catalog', type=Path, required=True)
    lookup.add_argument('--version', required=True)
    lookup.add_argument('--lemma', required=True)
    lookup.add_argument('--pos')
    lookup.add_argument('--target-id')
    searching = commands.add_parser('search')
    searching.add_argument('--catalog', type=Path, required=True)
    searching.add_argument('--version', required=True)
    searching.add_argument('--corpus', choices=['seoul', 'modu'], required=True)
    searching.add_argument('--lemma', required=True)
    searching.add_argument('--pos')
    searching.add_argument('--source')
    searching.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    if args.command == 'register':
        register(args.catalog, args.version, args.root, args.audit,
                 args.dictionary, args.dictionary_receipt)
        print('Audited analysis release registered.')
    elif args.command == 'context':
        print(json.dumps(context(args.catalog, args.version, args.corpus, args.source,
                                 args.utterance_id, args.radius), ensure_ascii=False, indent=2))
    elif args.command == 'groups':
        release = read(args.catalog)['releases'][args.version]
        print(json.dumps(dictionary_groups(release, args.lemma, args.pos, args.target_id),
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps(search(args.catalog, args.version, args.corpus, args.lemma,
                                args.pos, args.source, args.limit), ensure_ascii=False, indent=2))

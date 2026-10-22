"""Local, bounded TextGrid snapshot packaging. No network or source mutations.

The inventory and all individual paths/hashes remain local. Only archives,
their chunks and aggregate receipts may be considered for an upload allowlist.
"""
import argparse
import contextlib
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import zipfile


def now():
    return dt.datetime.now().astimezone().isoformat()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.partial')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=True, sort_keys=True, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(8):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.1 * (attempt + 1))


def child(root, name):
    root = Path(root).resolve()
    p = Path(name)
    p = p.resolve() if p.is_absolute() else (root / p).resolve()
    require(p.is_relative_to(root) and p != root, 'path_outside_scope')
    return p


@contextlib.contextmanager
def lock(path):
    import msvcrt
    with open(path, 'a+b') as f:
        if f.tell() == 0:
            f.write(b'0')
            f.flush()
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def check(out, config):
    require(not (out / 'STOP').exists(), 'stopped_by_marker')
    require(shutil.disk_usage(out).free >= config['output_floor_bytes'], 'output_space_floor')
    require(shutil.disk_usage(config['modu_root']).free >= config['source_floor_bytes'], 'source_space_floor')


def bind_inputs(config):
    final_path = Path(config['modu_root']) / 'modu/TEXTGRID_FINAL.json'
    final = read(final_path)
    require(final['status'] == 'passed_with_explicit_alignment_reviews' and final['smoke'] is False,
            'completed_modu_release_required')
    index = child(config['modu_root'], final['link_index_relative'])
    require(sha(index) == final['link_index_sha256'], 'index_sha_mismatch')
    receipt = read(config['seoul_receipt'])
    require(receipt['status'] == 'verified', 'verified_seoul_copy_required')
    return dict(schema='existing_textgrid_backup.v1', config=config,
                code_sha256=sha(__file__), modu_final_sha256=sha(final_path),
                modu_index_sha256=sha(index), seoul_receipt_sha256=sha(config['seoul_receipt']),
                expected_modu_files=final['counts']['derived'],
                expected_modu_bytes=final['counts']['bytes'],
                expected_absent=final['counts']['no_mfa_alignment'])


def source_groups(config):
    root = Path(config['modu_root']).resolve()
    final = read(root / 'modu/TEXTGRID_FINAL.json')
    with gzip.open(child(root, final['link_index_relative']), 'rt', encoding='utf-8-sig', newline='') as f:
        for record in csv.DictReader(f):
            links = child(root, record['links_relative'])
            require(sha(links) == record['sha256'], 'source_links_sha_mismatch')
            yield record['links_relative'], record['sha256'], links


def modu_rows(config, links):
    root = Path(config['modu_root']).resolve()
    allowed = root / 'modu/alignment_textgrids_v1/textgrids'
    with gzip.open(links, 'rt', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if not row['textgrid_path']:
                yield None
                continue
            path = child(allowed, root / row['textgrid_path'])
            digest = row['textgrid_sha256']
            require(path.suffix.lower() == '.textgrid' and len(digest) == 64 and
                    all(c in '0123456789abcdef' for c in digest), 'invalid_textgrid_metadata')
            yield ('modu', path.as_posix(), path.relative_to(root).as_posix(), digest)


def inventory(out, contract):
    config = contract['config']
    ready_path = out / 'INVENTORY_READY.json'
    db_path = out / 'LOCAL_INVENTORY.sqlite'
    if ready_path.exists():
        ready = read(ready_path)
        require(ready['contract_sha256'] == sha(out / 'CONTRACT.json'), 'ready_contract_changed')
        require(sha(db_path) == ready['inventory_sha256'], 'inventory_changed')
        return ready
    db = sqlite3.connect(db_path)
    try:
        db.executescript('''
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=FULL;
            PRAGMA cache_size=-8192;
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY, corpus TEXT NOT NULL,
                path TEXT NOT NULL COLLATE NOCASE UNIQUE,
                archive_path TEXT NOT NULL COLLATE NOCASE UNIQUE, sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
                name TEXT PRIMARY KEY, sha256 TEXT NOT NULL, files INTEGER, absent INTEGER);
        ''')
        for name, digest, links in source_groups(config):
            check(out, config)
            prior = db.execute('SELECT sha256 FROM sources WHERE name=?', (name,)).fetchone()
            if prior:
                require(prior[0] == digest, 'completed_source_changed')
                continue
            count = absent = 0
            with db:
                for row in modu_rows(config, links):
                    if row is None:
                        absent += 1
                    else:
                        db.execute('INSERT INTO files(corpus,path,archive_path,sha256) VALUES(?,?,?,?)', row)
                        count += 1
                db.execute('INSERT INTO sources VALUES(?,?,?,?)', (name, digest, count, absent))
            if time.monotonic() - inventory.last_progress >= 10:
                inventory.last_progress = time.monotonic()
                totals = db.execute('SELECT COUNT(*),SUM(files),SUM(absent) FROM sources').fetchone()
                save(out / 'PROGRESS.json', dict(status='indexing_local_inventory', at=now(),
                     completed_sources=totals[0], files=totals[1], absent=totals[2]))
        seoul = read(config['seoul_receipt'])
        seoul_rows = [r for r in seoul['files'] if r['relative_path'].lower().endswith('.textgrid')]
        require(len(seoul_rows) == config['expected_seoul_files'], 'seoul_count_mismatch')
        if not db.execute("SELECT 1 FROM sources WHERE name='seoul_original'").fetchone():
            with db:
                for r in seoul_rows:
                    p = child(config['seoul_root'], r['relative_path'])
                    db.execute('INSERT INTO files(corpus,path,archive_path,sha256) VALUES(?,?,?,?)',
                               ('seoul', p.as_posix(), 'seoul/original/' + r['relative_path'], r['sha256']))
                db.execute('INSERT INTO sources VALUES(?,?,?,?)',
                           ('seoul_original', contract['seoul_receipt_sha256'], len(seoul_rows), 0))
        counts = dict(db.execute('SELECT corpus,COUNT(*) FROM files GROUP BY corpus'))
        absent = db.execute('SELECT SUM(absent) FROM sources').fetchone()[0]
        require(counts == dict(modu=contract['expected_modu_files'], seoul=len(seoul_rows)), 'inventory_counts_mismatch')
        require(absent == contract['expected_absent'], 'absent_alignment_count_mismatch')
        require(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'inventory_integrity')
    finally:
        db.close()
    ready = dict(at=now(), contract_sha256=sha(out / 'CONTRACT.json'), inventory_sha256=sha(db_path),
                 counts=counts, absent=absent, seoul_bytes=sum(r['bytes'] for r in seoul_rows))
    save(ready_path, ready)
    return ready


inventory.last_progress = 0


def copy_hash(src, dst):
    digest = hashlib.sha256()
    size = 0
    while block := src.read(1024 * 1024):
        digest.update(block)
        size += len(block)
        dst.write(block)
    return size, digest.hexdigest()


def package_part(out, config, rows, number):
    name = f'textgrids_{number:05d}.zip'
    target = out / name
    partial = out / (name + '.partial')
    require(not target.exists() and not partial.exists(), 'preserve_uncommitted_archive')
    total = 0
    corpus_bytes = {}
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for ident, corpus, path, relative, expected in rows:
            check(out, config)
            require(Path(path).suffix.lower() == '.textgrid', 'textgrid_only')
            with open(path, 'rb') as src, z.open(relative, 'w', force_zip64=True) as dst:
                size, digest = copy_hash(src, dst)
            require(digest == expected, 'source_sha_mismatch')
            total += size
            corpus_bytes[corpus] = corpus_bytes.get(corpus, 0) + size
    with zipfile.ZipFile(partial) as z:
        require(len(z.infolist()) == len(rows), 'archive_count_mismatch')
        for row in rows:
            with z.open(row[3]) as f:
                require(hashlib.file_digest(f, 'sha256').hexdigest() == row[4], 'archive_content_mismatch')
                # Reading to EOF verifies ZIP CRC as well as SHA.
    partial.replace(target)
    pieces = []
    if target.stat().st_size <= config['piece_bytes']:
        pieces.append(dict(name=name, bytes=target.stat().st_size, sha256=sha(target)))
    else:
        with target.open('rb') as f:
            n = 0
            while block := f.read(config['piece_bytes']):
                n += 1
                p = out / f'{name}.part{n:03d}'
                with p.open('xb') as dst:
                    dst.write(block)
                    dst.flush()
                    os.fsync(dst.fileno())
                pieces.append(dict(name=p.name, bytes=len(block), sha256=sha(p)))
        combined = hashlib.sha256()
        for piece in pieces:
            with (out / piece['name']).open('rb') as f:
                while block := f.read(1024 * 1024):
                    combined.update(block)
        require(combined.hexdigest() == sha(target), 'chunk_reassembly_mismatch')
    return dict(number=number, name=name, sha256=sha(target), bytes=target.stat().st_size,
                first_id=rows[0][0], last_id=rows[-1][0], files=len(rows), source_bytes=total,
                corpus_bytes=corpus_bytes, pieces=pieces, completed_at=now())


def package(out, contract, ready, max_parts=0):
    config = contract['config']
    db = sqlite3.connect(f'file:{(out / "LOCAL_INVENTORY.sqlite").as_posix()}?mode=ro', uri=True)
    last = number = count = total = 0
    corpus_bytes = {}
    receipts = []
    try:
        for p in sorted(out.glob('PART_*.json')):
            r = read(p)
            require(r['number'] == number + 1 and r['first_id'] == last + 1 and
                    r['last_id'] - r['first_id'] + 1 == r['files'], 'part_sequence_mismatch')
            require(r['contract_sha256'] == sha(out / 'CONTRACT.json') and
                    r['inventory_sha256'] == ready['inventory_sha256'], 'part_binding_mismatch')
            require(sha(out / r['name']) == r['sha256'], 'completed_archive_changed')
            for piece in r['pieces']:
                require((out / piece['name']).stat().st_size == piece['bytes'] and
                        sha(out / piece['name']) == piece['sha256'], 'completed_piece_changed')
            receipts.append(r)
            number, last = r['number'], r['last_id']
            count += r['files']
            total += r['source_bytes']
            for corpus, size in r['corpus_bytes'].items():
                corpus_bytes[corpus] = corpus_bytes.get(corpus, 0) + size
        # Uncommitted output is never adopted. Preserve for inspection, then rebuild from inventory.
        committed = {r['name'] for r in receipts} | {p['name'] for r in receipts for p in r['pieces']}
        leftovers = [p for p in out.glob('textgrids_*') if p.is_file() and p.name not in committed]
        if leftovers:
            saved = out / ('incomplete_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            saved.mkdir()
            for p in leftovers:
                p.rename(saved / p.name)
        made = 0
        while True:
            check(out, config)
            rows = db.execute('SELECT id,corpus,path,archive_path,sha256 FROM files WHERE id>? ORDER BY id LIMIT ?',
                              (last, config['entry_limit'])).fetchall()
            if not rows:
                break
            r = package_part(out, config, rows, number + 1)
            r.update(contract_sha256=sha(out / 'CONTRACT.json'), inventory_sha256=ready['inventory_sha256'])
            save(out / f'PART_{number + 1:05d}.json', r)
            receipts.append(r)
            number, last = r['number'], r['last_id']
            count += r['files']
            total += r['source_bytes']
            for corpus, size in r['corpus_bytes'].items():
                corpus_bytes[corpus] = corpus_bytes.get(corpus, 0) + size
            save(out / 'PROGRESS.json', dict(status='packaging_verified_parts', at=now(),
                 parts=number, files=count, source_bytes=total, archive_bytes=sum(r['bytes'] for r in receipts)))
            made += 1
            if max_parts and made >= max_parts:
                return dict(status='bounded_parts_complete_full_backup_pending', parts=number, files=count)
        require(count == sum(ready['counts'].values()), 'final_file_count_mismatch')
        require(corpus_bytes == dict(modu=contract['expected_modu_bytes'], seoul=ready['seoul_bytes']),
                'final_source_bytes_mismatch')
        final = dict(status='local_archives_verified_cloud_pending', at=now(), files=count, source_bytes=total,
                     corpus_counts=ready['counts'], corpus_bytes=corpus_bytes, parts=number,
                     archives=receipts, cloud_complete=False, detailed_inventory_external=False)
        save(out / 'PACKAGE_FINAL.json', final)
        return dict(status=final['status'], files=count, parts=number)
    finally:
        db.close()


def run(config_path, out, inventory_only=False, max_parts=0):
    config = read(config_path)
    require(0 < config['entry_limit'] <= 10000 and 0 < config['piece_bytes'] <= 90 * 2**20,
            'bounded_limits_required')
    out = Path(out).resolve()
    for source in (config['modu_root'], config['seoul_root']):
        root = Path(source).resolve()
        require(not out.is_relative_to(root) and not root.is_relative_to(out), 'output_overlaps_source')
    out.mkdir(parents=True, exist_ok=True)
    with lock(out / 'RUN.lock'):
        check(out, config)
        contract = bind_inputs(config)
        path = out / 'CONTRACT.json'
        if path.exists():
            require(read(path) == contract, 'contract_or_code_changed')
        else:
            save(path, contract)
        ready = inventory(out, contract)
        if inventory_only:
            return dict(status='inventory_ready', counts=ready['counts'])
        return package(out, contract, ready, max_parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--max-parts', type=int, default=0)
    args = parser.parse_args()
    try:
        result = run(args.config, args.output, args.inventory_only, args.max_parts)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as exc:
        # Error classes/reasons only; no corpus text or credentials.
        save(Path(args.output) / 'ERROR.json', dict(at=now(), error_type=type(exc).__name__, reason=str(exc)))
        raise

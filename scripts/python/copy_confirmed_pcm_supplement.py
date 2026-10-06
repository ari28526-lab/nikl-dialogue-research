"""Additive, bounded original PCM copy with independent destination SHA.

No raw-source edits, directory enumeration, inferred WAV encoding or base-index edits.
Each source access is isolated in a timed child. Interrupted partials are preserved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def now():
    return datetime.now(timezone.utc).isoformat()


def copy_one(item, target):
    """Only called in an isolated child in production; before/after source stat."""
    destination = Path(target)
    evidence = item['read_evidence']
    expected = evidence['bytes']
    if not 0 < expected <= 8 * 1024 * 1024:
        raise ValueError('Source exceeds bounded file size')
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix('.pcm.partial')
    if partial.exists():
        raise ValueError('Preserve interrupted partial; diagnose before retry')
    existed = destination.exists()
    digest = hashlib.sha256()
    total = 0
    with open(item['source_pcm_path'], 'rb') as source:
        before = os.fstat(source.fileno())
        if before.st_size != expected:
            raise ValueError('Source size changed since presence check')
        prefix = source.read(evidence['prefix_bytes'])
        if hashlib.sha256(prefix).hexdigest() != evidence['prefix_sha256']:
            raise ValueError('Source prefix changed since presence check')
        source.seek(0)
        output = None if existed else partial.open('xb')
        try:
            while True:
                block = source.read(65536)
                if not block:
                    break
                total += len(block)
                if total > expected:
                    raise ValueError('Source grew during copy')
                digest.update(block)
                if output:
                    output.write(block)
            after = os.fstat(source.fileno())
            if total != expected or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('Source changed during copy')
            if output:
                output.flush()
                os.fsync(output.fileno())
        finally:
            if output:
                output.close()
    # Separate open/read of the destination, not a reused write-stream digest.
    candidate = destination if existed else partial
    if sha(candidate) != digest.hexdigest() or candidate.stat().st_size != total:
        raise ValueError('Independent destination SHA mismatch')
    if not existed:
        # Do not replace any concurrently created destination.
        os.rename(partial, destination)
    return dict(utterance_id=item['utterance_id'], bytes=total,
                source_sha256=digest.hexdigest(), destination_sha256=digest.hexdigest(),
                source_mtime_ns=before.st_mtime_ns, independently_reopened_destination=True,
                existing_destination_verified=existed, completed_at=now())


def isolated(item, target, timeout=10):
    folder = Path(tempfile.mkdtemp(prefix='pcm_copy_'))
    save(folder / 'request.json', dict(item=item, target=str(target)))
    with (folder / 'request.json').open('rb') as inp, (folder / 'result.json').open('wb') as out, (folder / 'stderr.log').open('wb') as err:
        child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--child'], stdin=inp, stdout=out, stderr=err)
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        confirmed = False
        try:
            child.kill()
            child.wait(timeout=2)
            confirmed = True
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise RuntimeError(json.dumps(dict(error='source_copy_timeout', child_pid=child.pid, exit_confirmed=confirmed, evidence=str(folder))))
    if child.returncode:
        raise RuntimeError((folder / 'stderr.log').read_text(encoding='utf-8', errors='replace')[-2000:])
    return json.loads((folder / 'result.json').read_text(encoding='utf-8'))


def relative(item):
    uid = item['utterance_id']
    if item['year'] != '2020' or not re.fullmatch(r'SDRW20[0-9]+(?:\.[0-9]+){3}', uid):
        raise ValueError('Unexpected original PCM identity')
    source = Path(item['source_pcm_path'])
    if source.stem != uid or source.suffix.lower() != '.pcm':
        raise ValueError('Source basename does not match identity')
    return Path('audio_originals_supplement_v1') / 'pcm' / '2020' / uid.split('.')[0] / (uid + '.pcm')


def run(plan_path):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    root = Path(plan['delivery_root'])
    stage = Path(plan['stage_root'])
    stage.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with (stage / 'PROCESS.lock').open('a+b') as lock:
        lock.seek(0)
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        contract = dict(plan_sha256=sha(plan_path), runner_sha256=sha(__file__),
                        source_listing_sha256=sha(plan['source_listing']),
                        source_final_sha256=sha(plan['source_final']))
        if contract['runner_sha256'] != plan['runner_sha256']:
            raise ValueError('Runner differs from launch plan')
        if contract['source_listing_sha256'] != plan['source_listing_sha256'] or contract['source_final_sha256'] != plan['source_final_sha256']:
            raise ValueError('Source evidence changed')
        source_final = json.loads(Path(plan['source_final']).read_text(encoding='utf-8'))
        if source_final['status'] != 'declared_gap_source_presence_consolidated' or source_final['listing_sha256'] != contract['source_listing_sha256']:
            raise ValueError('Source consolidation receipt invalid')
        cf = stage / 'CONTRACT.json'
        if cf.exists() and json.loads(cf.read_text(encoding='utf-8')) != contract:
            raise ValueError('Frozen contract mismatch')
        if not cf.exists():
            save(cf, contract)
        if (stage / 'FINAL.json').exists():
            return
        rows = [json.loads(line) for line in Path(plan['source_listing']).read_text(encoding='utf-8').splitlines()]
        selected = [r for r in rows if r['source_pcm_presence'] == 'directly_readable']
        if len(selected) != plan['files'] or sum(r['read_evidence']['bytes'] for r in selected) != plan['bytes'] or len({r['utterance_id'] for r in selected}) != len(selected):
            raise ValueError('Unexpected selected scope')
        if plan['bytes'] > 512 * 1024 * 1024 or shutil.disk_usage(root).free < plan['bytes'] + 512 * 1024 * 1024:
            raise ValueError('Size bound or destination free-space guard')
        allowed = plan['source_root'].replace('\\', '/').rstrip('/') + '/'
        for row in selected:
            relative(row)
            normalized = row['source_pcm_path'].replace('\\', '/')
            if not normalized.startswith(allowed) or '..' in normalized.split('/'):
                raise ValueError('Source outside declared root')
        progress = stage / 'PROGRESS.json'
        receipts = json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else []
        if [r['utterance_id'] for r in receipts] != [r['utterance_id'] for r in selected[:len(receipts)]]:
            raise ValueError('Resume order mismatch')
        completed_bytes = sum(r['bytes'] for r in receipts)
        def state(status):
            save(stage / 'STATE.json', dict(status=status, updated_at=now(), pid=os.getpid(),
                 completed_files=len(receipts), completed_bytes=completed_bytes,
                 total_files=len(selected), total_bytes=plan['bytes'], phase='fresh_original_pcm_copy_and_independent_sha'))
        state('running')
        try:
            for item in selected[len(receipts):]:
                rel = relative(item)
                result = isolated(item, root / rel)
                result['relative_pcm_path'] = rel.as_posix()
                receipts.append(result)
                completed_bytes += result['bytes']
                if len(receipts) % 16 == 0:
                    save(progress, receipts)
                    state('running')
            save(progress, receipts)
            # Overlay includes all unresolved identities, preserving their previous statuses.
            by_id = {r['utterance_id']: r for r in receipts}
            index = stage / 'ORIGINAL_AUDIO_LINKS.jsonl'
            with index.open('x', encoding='utf-8') as stream:
                for row in rows:
                    entry = dict(row)
                    entry['pcm_supplement'] = by_id.get(row['utterance_id'])
                    entry['global_source_absence_established'] = False
                    stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
            (stage / 'GUIDE.md').write_text('# 원 PCM 보완 자료\n\n선언된 WAV 범위에서 빠진 발화 중 실제 확인한 2020 원 PCM을 별도로 보존합니다. ORIGINAL_AUDIO_LINKS.jsonl의 relative_pcm_path는 배포 루트 기준입니다. 원본 전체 SHA와 별도로 다시 연 복사본 SHA를 대조했습니다. PCM 인코딩은 2020 공식 제공 설명(16kHz, 16bit, little-endian)에 따릅니다. 원본과 기존 연결표를 수정하지 않았습니다. 후보 의미·정렬 없는 발화·빈 전사 상태를 유지합니다. 확인한 경로에서 찾지 못한 1436개는 전역 부재가 아닙니다. 이 보완 단계 완료는 전체 전달 완료가 아닙니다.\n', encoding='utf-8')
            evidence = {p.name: sha(p) for p in [plan_path, cf, progress, index, stage / 'GUIDE.md']}
            evidence['runner'] = sha(__file__)
            save(stage / 'FINAL.json', dict(status='confirmed_original_pcm_supplement_copied_sha_verified',
                 completed_at=now(), files=len(receipts), bytes=completed_bytes, unresolved_in_checked_roots=len(rows)-len(receipts),
                 source_listing_sha256=contract['source_listing_sha256'], evidence_sha256=evidence,
                 source_modified=False, independent_destination_sha=True,
                 source_absence_inferred=False, full_audio_coverage_verified=False, delivery_complete=False))
            state('completed')
        except Exception as exc:
            save(progress, receipts)
            save(stage / 'ERROR.json', dict(at=now(), error=str(exc), completed_files=len(receipts), retry_automatically=False))
            state('failed')
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan')
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        request = json.loads(sys.stdin.buffer.read().decode('utf-8'))
        print(json.dumps(copy_one(request['item'], request['target'])))
    else:
        run(args.plan)

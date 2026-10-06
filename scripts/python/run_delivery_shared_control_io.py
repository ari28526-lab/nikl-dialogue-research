"""Versioned Windows control-file transport for frozen delivery runners.

Only exact STATE/ERROR controls listed in the pinned policy are affected.
Corpus payloads, SQL, hashes, frozen runner/analysis contracts are unchanged.
"""
import argparse
import builtins
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import time

ATTEMPTS = 16
MAX_CONTROL_BYTES = 1024 * 1024
ORIGINAL_OPEN = builtins.open
ORIGINAL_IO_OPEN = io.open
ORIGINAL_REPLACE = os.replace
ORIGINAL_CONNECT = sqlite3.connect

def digest(path):
    with ORIGINAL_OPEN(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def key(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))

def retry(operation):
    for attempt in range(ATTEMPTS):
        try:
            return operation()
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (None, 5, 32, 33) or attempt == ATTEMPTS - 1:
                raise
            time.sleep(min(.05 * (attempt + 1), .5))

def shared_opener(path, flags):
    """A read handle permits atomic replacement while retaining its old bytes."""
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000, 1 | 2 | 4, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, flags | os.O_BINARY)
    except BaseException:
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close(handle)
        raise

def install(controls, copy_ledger=None, copy_state=None):
    controls = {key(p) for p in controls}
    def open_shared(file, mode='r', buffering=-1, encoding=None, errors=None,
                    newline=None, closefd=True, opener=None):
        eligible = (isinstance(file, (str, bytes, os.PathLike)) and key(file) in controls
                    and mode in ('r', 'rt', 'rb') and opener is None and os.name == 'nt')
        if not eligible:
            return ORIGINAL_OPEN(file, mode, buffering, encoding, errors, newline, closefd, opener)
        def snapshot():
            # Keep the native handle open only for the bounded read. Some Windows
            # volume/filter combinations reject replacing even a shared-delete
            # open target; consumers therefore receive an independent buffer.
            with ORIGINAL_OPEN(file, 'rb', opener=shared_opener) as stream:
                raw = stream.read(MAX_CONTROL_BYTES + 1)
            if len(raw) > MAX_CONTROL_BYTES:
                raise ValueError('Control metadata exceeds bounded snapshot limit')
            buffer = io.BytesIO(raw)
            if 'b' in mode:
                return buffer
            return io.TextIOWrapper(buffer, encoding=encoding, errors=errors, newline=newline)
        return retry(snapshot)
    def replace_shared(src, dst, *args, **kwargs):
        if key(dst) in controls:
            return retry(lambda: ORIGINAL_REPLACE(src, dst, *args, **kwargs))
        return ORIGINAL_REPLACE(src, dst, *args, **kwargs)
    builtins.open = open_shared
    io.open = open_shared
    os.replace = replace_shared
    if copy_ledger:
        published = False
        def connect(database, *args, **kwargs):
            nonlocal published
            connection = ORIGINAL_CONNECT(database, *args, **kwargs)
            if not published and key(database) == key(copy_ledger):
                # Original runner holds PROCESS.lock and has verified its contract
                # before this call. Dependents can wait through its long capacity SQL.
                published = True
                from datetime import datetime, timezone
                value = dict(status='running', phase='resume_capacity_check', pid=os.getpid(),
                             updated_at=datetime.now(timezone.utc).isoformat(),
                             progress_scope='current_resume_revalidation_pass')
                temp = Path(str(copy_state) + '.tmp')
                with ORIGINAL_OPEN(temp, 'w', encoding='utf-8') as stream:
                    json.dump(value, stream); stream.flush(); os.fsync(stream.fileno())
                replace_shared(temp, copy_state)
            return connection
        sqlite3.connect = connect

def uninstall():
    builtins.open = ORIGINAL_OPEN
    io.open = ORIGINAL_IO_OPEN
    os.replace = ORIGINAL_REPLACE
    sqlite3.connect = ORIGINAL_CONNECT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--policy-sha256', required=True)
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if digest(args.policy) != args.policy_sha256:
        raise ValueError('IO policy SHA changed')
    policy = json.loads(args.policy.read_text(encoding='utf-8-sig'))
    matches = [e for e in policy['workers'] if key(e['runner']) == key(args.runner)]
    if len(matches) != 1 or digest(args.runner) != matches[0]['runner_sha256']:
        raise ValueError('Frozen runner differs from IO policy')
    if digest(Path(__file__)) != policy['wrapper_sha256']:
        raise ValueError('Shared-control wrapper changed')
    package = Path(policy['package']).resolve()
    for name in policy['controls']:
        path = Path(name).resolve()
        if not path.is_relative_to(package) or path.name not in ('STATE.json', 'ERROR.json'):
            raise ValueError('Control outside declared package scope')
    copying = args.runner.name == 'build_portable_delivery_copy.py'
    install(policy['controls'], package/'COPY_LEDGER.sqlite' if copying else None,
            package/'STATE.json' if copying else None)
    sys.path.insert(0, str(args.runner.resolve().parent))
    sys.argv = [str(args.runner), *args.arguments]
    if len(sys.argv) > 1 and sys.argv[1] == '--':
        del sys.argv[1]
    runpy.run_path(str(args.runner), run_name='__main__')

if __name__ == '__main__':
    main()

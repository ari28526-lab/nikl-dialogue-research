"""대량 파이프라인 공통 안전 유틸리티.

연구 산출물은 같은 디렉터리의 임시파일에 완전히 쓴 뒤 ``os.replace``로
승격한다. 실행 manifest에는 코드·환경·입력의 fingerprint를 남긴다.
표준라이브러리만 사용하여 MFA conda Python에서도 실행할 수 있다.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Iterator


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_run_id(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def file_fingerprint(path: Path, *, with_sha256: bool = False) -> dict:
    stat = path.stat()
    result = {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if with_sha256:
        result["sha256"] = sha256_file(path)
    return result


@contextmanager
def staged_text_writer(
    path: Path,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[tuple[IO[str], Path]]:
    """동일 볼륨 임시파일을 완전히 쓰고 닫는다.

    성공해도 자동 승격하지 않는다. 호출자는 내용을 검증한 뒤
    :func:`promote_staged`를 호출해야 한다. 예외가 나면 임시파일을 보존한다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    stream = open(temp, "x", encoding=encoding, newline=newline)
    try:
        yield stream, temp
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
    except BaseException:
        if not stream.closed:
            stream.flush()
            stream.close()
        raise


def promote_staged(temp: Path, destination: Path) -> None:
    """검증을 끝낸 동일 볼륨 임시파일을 원자적으로 승격한다."""
    if temp.parent.resolve() != destination.parent.resolve():
        raise ValueError("원자 교체는 같은 디렉터리의 임시파일만 허용")
    delay_seconds = 0.05
    for attempt in range(10):
        try:
            os.replace(temp, destination)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 1.0)


@contextmanager
def atomic_text_writer(
    path: Path,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[tuple[IO[str], Path]]:
    """일반 텍스트를 임시파일에 완전히 쓴 뒤 원자적으로 승격한다."""
    with staged_text_writer(
        path, encoding=encoding, newline=newline
    ) as (stream, temp):
        yield stream, temp
    promote_staged(temp, path)


def atomic_write_json(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with atomic_text_writer(path, encoding="utf-8", newline="\n") as (stream, _):
        stream.write(text)


def archive_copy(source: Path, archive_root: Path, relative_path: Path) -> Path:
    """기존 파일을 보존한다. 같은 archive 대상이 이미 있으면 실패한다."""
    destination = archive_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"아카이브 대상이 이미 존재함: {destination}")
    shutil.copy2(source, destination)
    return destination


def git_commit(project_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def runtime_snapshot(project_root: Path) -> dict:
    return {
        "recorded_at": now_iso(),
        "git_commit": git_commit(project_root),
        "python": {
            "executable": str(Path(sys.executable).resolve()),
            "version": sys.version,
            "implementation": platform.python_implementation(),
        },
        "platform": platform.platform(),
        "pid": os.getpid(),
    }

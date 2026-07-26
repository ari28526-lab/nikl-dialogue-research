"""MFA 3.4 TextGrid export queue의 조기 worker 종료 경쟁을 고친다.

2020 전량 실행에서 4개 export worker를 요청했으나 실제로는 한 worker만
866,196개를 순차 처리해 약 15시간 57분이 걸렸다. MFA의 기존 계약은
``multiprocessing.Queue.put(대형 dict)`` 직후 1초를 기다리고
``finished_adding`` event를 켠다. Queue feeder가 대형 dict를 아직 직렬화하는
동안 worker의 1초 ``get`` timeout이 먼저 끝나면 worker가 조기 종료할 수 있다.

이 패치는 timeout/event 종료를 명시적 sentinel(None) 종료로 바꾼다.

- producer: 모든 batch 뒤에 worker 수만큼 ``None``을 enqueue
- worker: blocking ``get``으로 batch/sentinel을 받고 sentinel에서 종료

설치본은 프로젝트 밖에 있으므로 적용 전 원본 두 파일과 SHA256 manifest를
``--backup-root``에 보존한다. 정확히 알려진 코드 조각에만 적용하며, 예상과
다르면 어떤 파일도 쓰지 않고 실패한다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso

OLD_WORKER = """                    try:
                        (file_batch) = self.for_write_queue.get(timeout=1)
                    except Empty:
                        if self.finished_adding.is_set():
                            self.finished_processing.set()
                            break
                        continue

                    if self.stopped.is_set():
"""

NEW_WORKER = """                    # PROJECT PATCH 2026-07-26: 대형 batch가 Queue feeder에서
                    # 직렬화되는 동안 1초 timeout+finished_adding으로 worker가 먼저
                    # 종료되던 경쟁을 제거한다. producer가 worker 수만큼 넣는 None이
                    # 유일한 정상 종료 신호다.
                    file_batch = self.for_write_queue.get()
                    if file_batch is None:
                        break

                    if self.stopped.is_set():
"""

OLD_PRODUCER = """                    for batch in file_batches:
                        for_write_queue.put(batch)
                    time.sleep(1)
                    finished_adding.set()
"""

NEW_PRODUCER = """                    for batch in file_batches:
                        for_write_queue.put(batch)
                    # PROJECT PATCH 2026-07-26: Queue.put은 feeder 직렬화 완료를
                    # 보장하지 않는다. 명시적 sentinel을 batch 뒤에 넣어 모든
                    # worker가 실제 queue drain 뒤에만 종료하게 한다.
                    for _ in export_procs:
                        for_write_queue.put(None)
                    finished_adding.set()
"""


def package_root_from_install() -> Path:
    spec = importlib.util.find_spec("montreal_forced_aligner")
    if spec is None or spec.origin is None:
        raise RuntimeError("montreal_forced_aligner 패키지를 찾지 못함")
    return Path(spec.origin).resolve().parent


def patched_text(text: str, old: str, new: str, label: str) -> tuple[str, str]:
    """코드 조각을 한 번만 치환하거나 이미 패치된 상태를 확인한다."""
    if new in text:
        if old in text:
            raise RuntimeError(f"{label}: 구/신 코드가 동시에 존재")
        return text, "already_patched"
    occurrences = text.count(old)
    if occurrences != 1:
        raise RuntimeError(
            f"{label}: 예상 구 코드 조각 {occurrences}개(정확히 1개 필요)"
        )
    return text.replace(old, new), "needs_patch"


def atomic_replace_text(path: Path, text: str) -> None:
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def inspect_and_patch(
    package_root: Path,
    *,
    apply: bool,
    backup_root: Path | None,
) -> dict:
    targets = {
        "worker": package_root / "alignment" / "multiprocessing.py",
        "producer": package_root / "alignment" / "base.py",
    }
    original: dict[str, str] = {}
    proposed: dict[str, str] = {}
    states: dict[str, str] = {}
    replacements = {
        "worker": (OLD_WORKER, NEW_WORKER),
        "producer": (OLD_PRODUCER, NEW_PRODUCER),
    }
    for key, path in targets.items():
        text = path.read_text(encoding="utf-8")
        original[key] = text
        proposed[key], states[key] = patched_text(
            text, *replacements[key], label=key
        )

    result = {
        "schema_version": 1,
        "checked_at": now_iso(),
        "package_root": str(package_root.resolve()),
        "apply_requested": apply,
        "states_before": states,
        "files_before": {
            key: file_fingerprint(path, with_sha256=True)
            for key, path in targets.items()
        },
    }
    if not apply:
        result["status"] = (
            "already_patched"
            if all(value == "already_patched" for value in states.values())
            else "ready_to_patch"
        )
        return result

    needs_patch = [
        key for key, state in states.items() if state == "needs_patch"
    ]
    if needs_patch and backup_root is None:
        raise RuntimeError("--apply에는 --backup-root가 필요")
    if needs_patch:
        assert backup_root is not None
        backup_root.mkdir(parents=True, exist_ok=False)
        for key, path in targets.items():
            relative = path.relative_to(package_root)
            destination = backup_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        atomic_write_json(
            backup_root / "manifest_before.json",
            {
                **result,
                "backup_root": str(backup_root.resolve()),
            },
        )
        for key in needs_patch:
            atomic_replace_text(targets[key], proposed[key])

    verified = inspect_and_patch(
        package_root, apply=False, backup_root=None
    )
    if verified["status"] != "already_patched":
        raise RuntimeError(f"적용 뒤 검증 실패: {verified}")
    result["status"] = "patched" if needs_patch else "already_patched"
    result["patched_files"] = needs_patch
    result["files_after"] = {
        key: file_fingerprint(path, with_sha256=True)
        for key, path in targets.items()
    }
    if backup_root is not None and backup_root.exists():
        atomic_write_json(backup_root / "manifest_after.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    package_root = args.package_root or package_root_from_install()
    try:
        result = inspect_and_patch(
            package_root,
            apply=args.apply,
            backup_root=args.backup_root,
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_output:
        atomic_write_json(args.json_output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

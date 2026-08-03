"""Build a transaction-safe MFA WAV corpus from a reviewed ID recovery plan.

The source WAV tree is never renamed, overwritten, or deleted.  In apply mode the
script first archives every affected source session as a verified ZIP on an
independent drive.  It then builds a separate corpus:

* unaffected sessions use NTFS hard links to the read-only source WAVs;
* affected sessions use independent copies with reviewed target IDs;
* ambiguous or unresolved target utterances are intentionally omitted so that
  the exclusion-review gate can handle them explicitly.

Session checkpoints make an interrupted run restart at the current session, not
at the beginning of the year.  No cleanup or replacement is automatic.
"""

from __future__ import annotations

import argparse
import ctypes
import csv
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    now_iso,
    sha256_file,
)


SCHEMA_VERSION = "wav_recovery_corpus.v1"
POLICY_VERSION = "reviewed_duration_sequence_overlay.v1"
INCLUDED_STATUSES = {"identity_high_confidence", "remap_high_confidence"}
EXCLUDED_STATUSES = {"ambiguous_short_match", "target_unresolved"}
PLAN_FIELDS = {
    "year",
    "session",
    "target_utt_id",
    "source_utt_id",
    "status",
    "block_length",
    "target_duration_seconds",
    "source_duration_seconds",
    "duration_residual_seconds",
    "source_wav",
}


@dataclass(frozen=True)
class CorpusEntry:
    session: str
    target_utt_id: str
    source_utt_id: str
    source_wav: Path
    mapping_status: str
    affected_session: bool


def canonical_json_sha(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON 읽기 실패: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON 최상위가 object가 아님: {path}")
    return payload


def read_plan(path: Path, year: str) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = PLAN_FIELDS - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"복구 계획 필수 열 누락: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise RuntimeError("복구 계획이 비어 있음")
    if {row["year"] for row in rows} != {year}:
        raise RuntimeError("복구 계획 연도 불일치")

    by_target: dict[str, dict[str, str]] = {}
    for row in rows:
        target = row["target_utt_id"].strip()
        status = row["status"].strip()
        if status == "source_orphan":
            if target:
                raise RuntimeError("source_orphan에 target_utt_id가 존재함")
            continue
        if status not in INCLUDED_STATUSES | EXCLUDED_STATUSES:
            raise RuntimeError(f"알 수 없는 복구 status: {status}")
        if not target:
            raise RuntimeError(f"{status}에 target_utt_id가 없음")
        if target in by_target:
            raise RuntimeError(f"복구 계획 target 중복: {target}")
        by_target[target] = row
    return rows, by_target


def validate_review(
    *,
    plan_path: Path,
    review_manifest_path: Path,
    review_decisions_path: Path,
) -> dict[str, object]:
    plan_hash = sha256_file(plan_path)
    manifest = read_json(review_manifest_path)
    decisions = read_json(review_decisions_path)
    if manifest.get("plan_csv_sha256") != plan_hash:
        raise RuntimeError("청취 manifest와 현재 복구 계획 SHA가 다름")
    manifest_rows = manifest.get("review_rows")
    decision_rows = decisions.get("decisions")
    if not isinstance(manifest_rows, list) or not isinstance(decision_rows, list):
        raise RuntimeError("청취 검토 행 구조 손상")
    manifest_ids = {
        str(row.get("target_utt_id") or "")
        for row in manifest_rows
        if isinstance(row, dict)
    }
    decision_ids = {
        str(row.get("target_utt_id") or "")
        for row in decision_rows
        if isinstance(row, dict)
    }
    selection = manifest.get("selection_contract")
    expected_rows = 12
    if isinstance(selection, dict):
        expected_rows = int(selection.get("review_rows") or 0)
    if expected_rows < 12:
        raise RuntimeError("청취 검토 계약이 최소 12건보다 작음")
    if len(manifest_rows) != expected_rows or len(decision_rows) != expected_rows:
        raise RuntimeError(
            f"청취 검토 수 불일치: expected={expected_rows}, "
            f"manifest={len(manifest_rows)}, decisions={len(decision_rows)}"
        )
    if manifest_ids != decision_ids or "" in manifest_ids:
        raise RuntimeError("청취 manifest와 판정 ID 집합 불일치")
    if any(
        not isinstance(row, dict)
        or row.get("decision") != "A_MATCHES_TARGET"
        for row in decision_rows
    ):
        raise RuntimeError("청취 검토에 미완료 또는 불일치 판정이 있음")
    with plan_path.open(encoding="utf-8-sig", newline="") as stream:
        plan_status = {
            row.get("target_utt_id", ""): row.get("status", "")
            for row in csv.DictReader(stream)
            if row.get("target_utt_id")
        }
    invalid_review_targets = sorted(
        target
        for target in manifest_ids
        if plan_status.get(target) != "remap_high_confidence"
    )
    if invalid_review_targets:
        raise RuntimeError(
            "청취 표본이 고신뢰 remap만으로 구성되지 않음: "
            f"{len(invalid_review_targets)}"
        )
    return {
        "review_rows": expected_rows,
        "a_matches_target": expected_rows,
        "review_manifest_sha256": sha256_file(review_manifest_path),
        "review_decisions_sha256": sha256_file(review_decisions_path),
        "plan_sha256": plan_hash,
    }


def ensure_source_path(
    path: Path, *, source_year_root: Path, expected_stem: str
) -> Path:
    resolved = path.resolve()
    allowed = source_year_root.resolve()
    if allowed not in resolved.parents:
        raise RuntimeError(f"source WAV가 허용 연도 root 밖임: {resolved}")
    if resolved.stem != expected_stem or resolved.suffix.lower() != ".wav":
        raise RuntimeError(f"source WAV ID/확장자 불일치: {resolved}")
    if not resolved.is_file():
        raise RuntimeError(f"source WAV 누락: {resolved}")
    return resolved


def scan_corpus(
    *,
    year: str,
    search_master_root: Path,
    source_wav_root: Path,
    plan_rows: list[dict[str, str]],
    plan_by_target: dict[str, dict[str, str]],
) -> dict[str, object]:
    search_year = search_master_root / year
    source_year = source_wav_root / year
    files = sorted(path for path in search_year.glob("*.csv") if not path.name.startswith("_"))
    if not files:
        raise RuntimeError(f"search master 세션 CSV 0개: {search_year}")

    affected_sessions = {row["session"] for row in plan_rows}
    seen_targets: set[str] = set()
    counts: Counter[str] = Counter()
    source_bytes = 0
    used_source_targets: dict[str, str] = {}
    affected_source_files: dict[str, int] = {}
    session_summaries: list[dict[str, object]] = []
    for index, csv_path in enumerate(files, 1):
        session = csv_path.stem
        session_counts: Counter[str] = Counter()
        source_session = source_year / session
        try:
            source_entries = {
                entry.name: entry
                for entry in os.scandir(source_session)
                if entry.is_file() and entry.name.lower().endswith(".wav")
            }
        except OSError:
            source_entries = {}
        source_session_key = os.path.normcase(os.path.abspath(source_session))
        if session in affected_sessions:
            for source_entry in source_entries.values():
                affected_source_files[
                    os.path.normcase(os.path.abspath(source_entry.path))
                ] = source_entry.stat().st_size
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if "utt_id" not in set(reader.fieldnames or ()):
                raise RuntimeError(f"utt_id 열 누락: {csv_path}")
            for row in reader:
                target = (row.get("utt_id") or "").strip()
                if not target:
                    raise RuntimeError(f"빈 utt_id: {csv_path}")
                if target in seen_targets:
                    raise RuntimeError(f"search master utt_id 중복: {target}")
                seen_targets.add(target)
                plan = plan_by_target.get(target)
                if plan is None:
                    status = "unaffected_identity"
                    source_id = target
                    source_name = f"{target}.wav"
                else:
                    status = plan["status"]
                    if plan["session"] != session:
                        raise RuntimeError(f"plan/search session 불일치: {target}")
                    if status in EXCLUDED_STATUSES:
                        counts[status] += 1
                        session_counts[status] += 1
                        continue
                    source_id = plan["source_utt_id"].strip()
                    if not source_id:
                        raise RuntimeError(f"포함 status의 source ID 누락: {target}")
                    source_name = f"{source_id}.wav"
                    planned = Path(plan["source_wav"])
                    if (
                        planned.name != source_name
                        or os.path.normcase(os.path.abspath(planned.parent))
                        != source_session_key
                    ):
                        raise RuntimeError(f"plan source 경로 불일치: {target}")
                source_entry = source_entries.get(source_name)
                if source_entry is None:
                    raise RuntimeError(
                        f"source WAV 누락: {source_session / source_name}"
                    )
                source_key = os.path.normcase(os.path.abspath(source_entry.path))
                previous_target = used_source_targets.get(source_key)
                if previous_target is not None and previous_target != target:
                    raise RuntimeError(
                        "하나의 source WAV가 둘 이상의 target에 배정됨: "
                        f"{previous_target}, {target} <- {source_entry.path}"
                    )
                used_source_targets[source_key] = target
                size = source_entry.stat().st_size
                source_bytes += size
                counts[status] += 1
                session_counts[status] += 1
        session_summaries.append(
            {
                "session": session,
                "affected": session in affected_sessions,
                "source_session_exists": source_session.is_dir(),
                "source_wav_files": len(source_entries),
                "counts": dict(sorted(session_counts.items())),
            }
        )
        if index % 250 == 0 or index == len(files):
            print(f"[{year}] dry scan {index}/{len(files)} sessions", flush=True)

    missing_plan_targets = set(plan_by_target) - seen_targets
    if missing_plan_targets:
        raise RuntimeError(
            f"복구 계획 target이 search master에 없음: {len(missing_plan_targets)}"
        )
    status_counts = Counter(row["status"] for row in plan_rows)
    return {
        "year": year,
        "search_sessions": len(files),
        "search_utterances": len(seen_targets),
        "affected_sessions": len(affected_sessions),
        "corpus_entries": sum(
            counts[key]
            for key in ("unaffected_identity", *sorted(INCLUDED_STATUSES))
        ),
        "omitted_for_review": sum(counts[key] for key in EXCLUDED_STATUSES),
        "mapping_counts": dict(sorted(counts.items())),
        "plan_status_counts": dict(sorted(status_counts.items())),
        "logical_source_bytes": source_bytes,
        "logical_source_gib": round(source_bytes / (1024**3), 3),
        "unique_corpus_source_files": len(used_source_targets),
        "affected_unique_source_files": len(affected_source_files),
        "affected_unique_source_bytes": sum(affected_source_files.values()),
        "sessions": session_summaries,
    }


def build_contract(
    *,
    year: str,
    search_master_root: Path,
    source_wav_root: Path,
    output_wav_root: Path,
    archive_base: Path,
    review: dict[str, object],
    scan: dict[str, object],
) -> dict[str, object]:
    build_meta = search_master_root / "_build_meta.json"
    if not build_meta.is_file():
        raise RuntimeError(f"search master build meta 없음: {build_meta}")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "builder_sha256": sha256_file(Path(__file__).resolve()),
        "year": year,
        "search_build_meta_sha256": sha256_file(build_meta),
        "plan_sha256": review["plan_sha256"],
        "review_manifest_sha256": review["review_manifest_sha256"],
        "review_decisions_sha256": review["review_decisions_sha256"],
        "source_wav_root": str(source_wav_root.resolve()),
        "output_wav_root": str(output_wav_root.resolve()),
        "archive_base": str(archive_base.resolve()),
        "mapping_counts": scan["mapping_counts"],
        "search_utterances": scan["search_utterances"],
    }
    contract_id = canonical_json_sha(identity)
    return {**identity, "corpus_contract_id": contract_id}


def dry_run(
    *,
    year: str,
    plan_path: Path,
    search_master_root: Path,
    source_wav_root: Path,
    output_wav_root: Path,
    archive_base: Path,
    review_manifest_path: Path,
    review_decisions_path: Path,
) -> dict[str, object]:
    review = validate_review(
        plan_path=plan_path,
        review_manifest_path=review_manifest_path,
        review_decisions_path=review_decisions_path,
    )
    plan_rows, plan_by_target = read_plan(plan_path, year)
    scan = scan_corpus(
        year=year,
        search_master_root=search_master_root,
        source_wav_root=source_wav_root,
        plan_rows=plan_rows,
        plan_by_target=plan_by_target,
    )
    contract = build_contract(
        year=year,
        search_master_root=search_master_root,
        source_wav_root=source_wav_root,
        output_wav_root=output_wav_root,
        archive_base=archive_base,
        review=review,
        scan=scan,
    )
    archive_bytes = int(scan["affected_unique_source_bytes"])
    affected_session_rows = [
        row for row in scan["sessions"] if bool(row["affected"])
    ]
    missing_source_sessions = [
        str(row["session"])
        for row in affected_session_rows
        if not bool(row["source_session_exists"])
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "dry_run_passed",
        "created_at": now_iso(),
        "source_wav_tree_untouched": True,
        "year": year,
        "contract": contract,
        "review": review,
        "scan": scan,
        "apply_plan": {
            "archive_root": str(
                archive_base
                / f"wav_id_recovery_{year}_{contract['corpus_contract_id'][:12]}"
            ),
            "archive_format": (
                "one ZIP per existing affected source session; "
                "verified_absent manifest for missing source session"
            ),
            "archive_existing_source_sessions": (
                len(affected_session_rows) - len(missing_source_sessions)
            ),
            "archive_missing_source_sessions": missing_source_sessions,
            "archive_uncompressed_bytes": archive_bytes,
            "archive_uncompressed_gib": round(archive_bytes / (1024**3), 3),
            "output_year": str((output_wav_root / year).resolve()),
            "unaffected_materialization": "NTFS hard link",
            "affected_materialization": "independent verified copy",
            "ambiguous_unresolved_materialization": "omitted",
            "automatic_delete_or_overwrite": False,
        },
    }


def append_progress(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"observed_at": now_iso(), **payload}
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def free_space_for(path: Path) -> int:
    candidate = path.resolve()
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return shutil.disk_usage(candidate).free


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@contextmanager
def application_lock(lock_path: Path, contract_id: str):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            prior = read_json(lock_path)
        except RuntimeError:
            prior = {}
        prior_pid = int(prior.get("pid") or 0)
        if process_alive(prior_pid):
            raise RuntimeError(f"다른 복구 작업 실행 중(pid={prior_pid}): {lock_path}")
        stale_root = lock_path.parent / "stale_locks"
        stale_root.mkdir(parents=True, exist_ok=True)
        stale = stale_root / (
            f"{lock_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        os.replace(lock_path, stale)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pid": os.getpid(),
        "corpus_contract_id": contract_id,
        "started_at": now_iso(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(lock_path, flags)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        if lock_path.exists():
            try:
                current = read_json(lock_path)
            except RuntimeError:
                current = {}
            if int(current.get("pid") or 0) == os.getpid():
                lock_path.unlink()


def session_source_snapshot(source_session: Path) -> list[dict[str, object]]:
    try:
        entries = sorted(
            (
                entry
                for entry in os.scandir(source_session)
                if entry.is_file() and entry.name.lower().endswith(".wav")
            ),
            key=lambda entry: entry.name,
        )
    except OSError as exc:
        raise RuntimeError(f"영향 세션 WAV 폴더 읽기 실패: {source_session}") from exc
    records: list[dict[str, object]] = []
    for entry in entries:
        stat = entry.stat()
        records.append(
            {
                "name": entry.name,
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_file(Path(entry.path)),
            }
        )
    return records


def archive_session(
    *,
    session: str,
    source_session: Path,
    archive_root: Path,
    allow_missing_source_session: bool = False,
) -> dict[str, object]:
    zip_path = archive_root / "sessions" / f"{session}.zip"
    manifest_path = archive_root / "session_manifests" / f"{session}.json"
    source_session_exists = source_session.is_dir()

    if not source_session_exists:
        if not allow_missing_source_session:
            raise RuntimeError(f"영향 세션 WAV 폴더 누락: {source_session}")
        if zip_path.exists():
            raise RuntimeError(
                f"누락 세션에 기존 ZIP이 있어 자동 수용 불가: {session}"
            )
        if manifest_path.is_file():
            manifest = read_json(manifest_path)
            if (
                manifest.get("status") != "verified_absent"
                or manifest.get("session") != session
                or int(manifest.get("file_count") or -1) != 0
                or manifest.get("files") != []
            ):
                raise RuntimeError(f"누락 세션 archive manifest 검증 실패: {session}")
            return manifest
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "wav_recovery_session_archive.v1",
            "status": "verified_absent",
            "session": session,
            "source_session": str(source_session.resolve()),
            "source_session_exists": False,
            "created_at": now_iso(),
            "file_count": 0,
            "source_bytes": 0,
            "zip_path": None,
            "zip_bytes": 0,
            "zip_sha256": None,
            "files": [],
        }
        atomic_write_json(manifest_path, manifest)
        return manifest

    if zip_path.is_file() and manifest_path.is_file():
        manifest = read_json(manifest_path)
        if (
            manifest.get("status") != "verified"
            or manifest.get("session") != session
            or manifest.get("zip_sha256") != sha256_file(zip_path)
        ):
            raise RuntimeError(f"기존 세션 archive 검증 실패: {session}")
        current = {
            item["name"]: (item["bytes"], item["mtime_ns"])
            for item in session_source_snapshot_without_hash(source_session)
        }
        recorded = {
            str(item["name"]): (int(item["bytes"]), int(item["mtime_ns"]))
            for item in manifest.get("files", [])
        }
        if current != recorded:
            raise RuntimeError(f"archive 뒤 원본 snapshot 변경: {session}")
        return manifest
    if zip_path.exists() or manifest_path.exists():
        stale = archive_root / "stale_incomplete" / (
            datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{session}"
        )
        stale.mkdir(parents=True, exist_ok=False)
        if zip_path.exists():
            os.replace(zip_path, stale / zip_path.name)
        if manifest_path.exists():
            os.replace(manifest_path, stale / manifest_path.name)

    records = session_source_snapshot(source_session)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    partial_zip = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.partial")
    prior_partials = list(zip_path.parent.glob(f".{zip_path.name}.*.partial"))
    if prior_partials:
        stale = archive_root / "stale_incomplete" / (
            datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{session}_partial"
        )
        stale.mkdir(parents=True, exist_ok=False)
        for prior_partial in prior_partials:
            os.replace(prior_partial, stale / prior_partial.name)
    record_by_name = {str(item["name"]): item for item in records}
    try:
        with zipfile.ZipFile(
            partial_zip,
            "x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=1,
            allowZip64=True,
        ) as archive:
            for item in records:
                archive.write(source_session / str(item["name"]), str(item["name"]))
        with zipfile.ZipFile(partial_zip, "r") as archive:
            names = archive.namelist()
            if names != [str(item["name"]) for item in records]:
                raise RuntimeError(f"ZIP member 목록 불일치: {session}")
            for name in names:
                digest = hashlib.sha256()
                with archive.open(name, "r") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                if digest.hexdigest() != record_by_name[name]["sha256"]:
                    raise RuntimeError(f"ZIP member SHA 불일치: {session}/{name}")
        os.replace(partial_zip, zip_path)
    except BaseException:
        # 실패 partial은 증거로 남기며 다음 실행에서 자동 삭제하지 않는다.
        raise
    manifest = {
        "schema_version": "wav_recovery_session_archive.v1",
        "status": "verified",
        "session": session,
        "source_session": str(source_session.resolve()),
        "source_session_exists": True,
        "created_at": now_iso(),
        "file_count": len(records),
        "source_bytes": sum(int(item["bytes"]) for item in records),
        "zip_path": str(zip_path.resolve()),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "files": records,
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def session_source_snapshot_without_hash(
    source_session: Path,
) -> list[dict[str, object]]:
    try:
        entries = sorted(
            (
                entry
                for entry in os.scandir(source_session)
                if entry.is_file() and entry.name.lower().endswith(".wav")
            ),
            key=lambda entry: entry.name,
        )
    except OSError as exc:
        raise RuntimeError(f"세션 WAV 폴더 읽기 실패: {source_session}") from exc
    return [
        {
            "name": entry.name,
            "bytes": entry.stat().st_size,
            "mtime_ns": entry.stat().st_mtime_ns,
        }
        for entry in entries
    ]


def corpus_entries_for_session(
    *,
    year: str,
    csv_path: Path,
    source_wav_root: Path,
    plan_by_target: dict[str, dict[str, str]],
    affected_sessions: set[str],
) -> list[CorpusEntry]:
    session = csv_path.stem
    source_session = source_wav_root / year / session
    try:
        source_entries = {
            entry.name: Path(entry.path)
            for entry in os.scandir(source_session)
            if entry.is_file() and entry.name.lower().endswith(".wav")
        }
    except FileNotFoundError:
        source_entries = {}
    except OSError as exc:
        raise RuntimeError(f"세션 WAV 폴더 읽기 실패: {source_session}") from exc
    source_session_key = os.path.normcase(os.path.abspath(source_session))
    entries: list[CorpusEntry] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            target = (row.get("utt_id") or "").strip()
            plan = plan_by_target.get(target)
            if plan is None:
                status = "unaffected_identity"
                source_id = target
            else:
                status = plan["status"]
                if status in EXCLUDED_STATUSES:
                    continue
                source_id = plan["source_utt_id"].strip()
                planned = Path(plan["source_wav"])
                if (
                    planned.name != f"{source_id}.wav"
                    or os.path.normcase(os.path.abspath(planned.parent))
                    != source_session_key
                ):
                    raise RuntimeError(f"plan source 경로 불일치: {target}")
            source = source_entries.get(f"{source_id}.wav")
            if source is None:
                raise RuntimeError(f"source WAV 누락: {source_session}/{source_id}.wav")
            entries.append(
                CorpusEntry(
                    session=session,
                    target_utt_id=target,
                    source_utt_id=source_id,
                    source_wav=source,
                    mapping_status=status,
                    affected_session=session in affected_sessions,
                )
            )
    return entries


def entry_digest(entries: list[CorpusEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        stat = entry.source_wav.stat()
        digest.update(
            (
                f"{entry.target_utt_id}\0{entry.source_utt_id}\0"
                f"{entry.mapping_status}\0{stat.st_size}\0{stat.st_mtime_ns}\n"
            ).encode("utf-8")
        )
    return digest.hexdigest()


def build_session(
    *,
    session: str,
    entries: list[CorpusEntry],
    partial_year: Path,
    marker_root: Path,
    stale_root: Path,
    archive_manifest: dict[str, object] | None,
    affected_session: bool,
) -> dict[str, object]:
    session_dir = partial_year / session
    marker_path = marker_root / f"{session}.json"
    mapping_sha = entry_digest(entries)
    if session_dir.is_dir() and marker_path.is_file():
        marker = read_json(marker_path)
        wav_count = sum(1 for path in session_dir.glob("*.wav") if path.is_file())
        if (
            marker.get("status") == "complete"
            and marker.get("mapping_sha256") == mapping_sha
            and int(marker.get("wav_files") or -1) == len(entries)
            and wav_count == len(entries)
        ):
            return marker
        raise RuntimeError(f"기존 세션 checkpoint 검증 실패: {session}")
    if session_dir.exists() or marker_path.exists():
        stale = stale_root / (
            datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{session}_incomplete"
        )
        stale.mkdir(parents=True, exist_ok=False)
        if session_dir.exists():
            os.replace(session_dir, stale / session)
        if marker_path.exists():
            os.replace(marker_path, stale / marker_path.name)

    temporary = partial_year / f".{session}.{os.getpid()}.partial"
    prior_partials = list(partial_year.glob(f".{session}.*.partial"))
    if prior_partials:
        stale_root.mkdir(parents=True, exist_ok=True)
        stale = stale_root / (
            f"{session}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_partial"
        )
        stale.mkdir(parents=True, exist_ok=False)
        for prior_partial in prior_partials:
            os.replace(prior_partial, stale / prior_partial.name)
    temporary.mkdir(parents=True, exist_ok=False)
    status_counts: Counter[str] = Counter()
    logical_bytes = 0
    archive_hashes = {}
    if archive_manifest is not None:
        archive_hashes = {
            str(item["name"]): str(item["sha256"])
            for item in archive_manifest.get("files", [])
        }
    for entry in entries:
        destination = temporary / f"{entry.target_utt_id}.wav"
        size = entry.source_wav.stat().st_size
        if entry.affected_session:
            expected_hash = archive_hashes.get(entry.source_wav.name)
            if not expected_hash:
                raise RuntimeError(
                    f"archive manifest에 source WAV 없음: {entry.source_wav}"
                )
            shutil.copy2(entry.source_wav, destination)
            if sha256_file(destination) != expected_hash:
                raise RuntimeError(f"복구 copy SHA 불일치: {destination}")
        else:
            os.link(entry.source_wav, destination)
            if not os.path.samefile(entry.source_wav, destination):
                raise RuntimeError(f"hard link 동일 파일 검증 실패: {destination}")
        logical_bytes += size
        status_counts[entry.mapping_status] += 1
    os.replace(temporary, session_dir)
    marker = {
        "schema_version": "wav_recovery_session_checkpoint.v1",
        "status": "complete",
        "session": session,
        "affected": affected_session,
        "mapping_sha256": mapping_sha,
        "wav_files": len(entries),
        "logical_bytes": logical_bytes,
        "mapping_counts": dict(sorted(status_counts.items())),
        "completed_at": now_iso(),
    }
    atomic_write_json(marker_path, marker)
    return marker


def apply_recovery(
    *,
    preflight: dict[str, object],
    year: str,
    plan_path: Path,
    search_master_root: Path,
    source_wav_root: Path,
    output_wav_root: Path,
    archive_base: Path,
    approved_by: str,
    progress_jsonl: Path | None = None,
    require_independent_archive: bool = True,
) -> dict[str, object]:
    contract = preflight["contract"]
    contract_id = str(contract["corpus_contract_id"])
    if not approved_by.strip():
        raise RuntimeError("apply에는 approved_by가 필요함")
    source_drive = os.path.splitdrive(str(source_wav_root.resolve()))[0].lower()
    output_drive = os.path.splitdrive(str(output_wav_root.resolve()))[0].lower()
    archive_drive = os.path.splitdrive(str(archive_base.resolve()))[0].lower()
    if source_drive != output_drive:
        raise RuntimeError("unaffected hard link를 위해 source/output은 같은 volume이어야 함")
    if require_independent_archive and archive_drive == source_drive:
        raise RuntimeError("archive는 source와 다른 volume이어야 함")
    source_resolved = source_wav_root.resolve()
    output_resolved = output_wav_root.resolve()
    if (
        source_resolved == output_resolved
        or source_resolved in output_resolved.parents
        or output_resolved in source_resolved.parents
    ):
        raise RuntimeError("source와 derived output 경로가 중첩됨")

    final_year = output_wav_root / year
    contract_path = output_wav_root.parent / "contracts" / f"{year}.json"
    if final_year.is_dir() and contract_path.is_file():
        prior = read_json(contract_path)
        if (
            prior.get("status") == "passed"
            and prior.get("corpus_contract_id") == contract_id
        ):
            return {**prior, "reused": True}
        raise RuntimeError("기존 복구 corpus가 다른 계약으로 존재함")
    if final_year.exists() or contract_path.exists():
        raise RuntimeError("복구 corpus/contract 반쪽 또는 충돌 상태")

    archive_bytes = int(preflight["apply_plan"]["archive_uncompressed_bytes"])
    output_free = free_space_for(output_wav_root.parent)
    archive_free = free_space_for(archive_base)
    if output_free < archive_bytes + 5 * 1024**3:
        raise RuntimeError("D: 복구 corpus 생성 여유공간 부족")
    if archive_free < archive_bytes + 2 * 1024**3:
        raise RuntimeError("archive drive 여유공간 부족")

    plan_rows, plan_by_target = read_plan(plan_path, year)
    affected_sessions = sorted({row["session"] for row in plan_rows})
    affected_session_set = set(affected_sessions)
    scan_by_session = {
        str(row["session"]): row for row in preflight["scan"]["sessions"]
    }
    archive_root = archive_base / f"wav_id_recovery_{year}_{contract_id[:12]}"
    transaction_root = output_wav_root.parent / "_transactions" / contract_id
    partial_year = transaction_root / "partial" / year
    marker_root = transaction_root / "session_markers"
    stale_root = transaction_root / "stale_session_partials"
    lock_path = output_wav_root.parent / "locks" / f"wav_recovery_{year}.lock"
    output_wav_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)
    partial_year.mkdir(parents=True, exist_ok=True)
    marker_root.mkdir(parents=True, exist_ok=True)
    append_progress(
        progress_jsonl,
        {"event": "apply_started", "year": year, "contract_id": contract_id},
    )

    with application_lock(lock_path, contract_id):
        archive_manifests: dict[str, dict[str, object]] = {}
        for index, session in enumerate(affected_sessions, 1):
            scan_session = scan_by_session.get(session)
            if scan_session is None:
                raise RuntimeError(f"dry-run 세션 증거 누락: {session}")
            source_session_exists = bool(scan_session["source_session_exists"])
            if not source_session_exists:
                count_keys = set(dict(scan_session["counts"]))
                if not count_keys or not count_keys.issubset(EXCLUDED_STATUSES):
                    raise RuntimeError(
                        "원본 세션 누락인데 corpus 포함 대상이 있음: " + session
                    )
            archive_manifests[session] = archive_session(
                session=session,
                source_session=source_wav_root / year / session,
                archive_root=archive_root,
                allow_missing_source_session=not source_session_exists,
            )
            if index % 10 == 0 or index == len(affected_sessions):
                print(
                    f"[{year}] archive {index}/{len(affected_sessions)} sessions",
                    flush=True,
                )
                append_progress(
                    progress_jsonl,
                    {
                        "event": "archive_progress",
                        "corpus_contract_id": contract_id,
                        "current": index,
                        "total": len(affected_sessions),
                    },
                )

        search_files = sorted(
            path
            for path in (search_master_root / year).glob("*.csv")
            if not path.name.startswith("_")
        )
        totals: Counter[str] = Counter()
        total_wavs = 0
        total_bytes = 0
        for index, csv_path in enumerate(search_files, 1):
            session = csv_path.stem
            entries = corpus_entries_for_session(
                year=year,
                csv_path=csv_path,
                source_wav_root=source_wav_root,
                plan_by_target=plan_by_target,
                affected_sessions=affected_session_set,
            )
            marker = build_session(
                session=session,
                entries=entries,
                partial_year=partial_year,
                marker_root=marker_root,
                stale_root=stale_root,
                archive_manifest=archive_manifests.get(session),
                affected_session=session in affected_session_set,
            )
            total_wavs += int(marker["wav_files"])
            total_bytes += int(marker["logical_bytes"])
            totals.update(
                {
                    key: int(value)
                    for key, value in dict(marker["mapping_counts"]).items()
                }
            )
            if index % 100 == 0 or index == len(search_files):
                print(f"[{year}] corpus {index}/{len(search_files)} sessions", flush=True)
                append_progress(
                    progress_jsonl,
                    {
                        "event": "corpus_progress",
                        "corpus_contract_id": contract_id,
                        "current": index,
                        "total": len(search_files),
                        "wav_files": total_wavs,
                    },
                )

        expected_counts = {
            key: int(value)
            for key, value in dict(preflight["scan"]["mapping_counts"]).items()
            if key not in EXCLUDED_STATUSES
        }
        if total_wavs != int(preflight["scan"]["corpus_entries"]):
            raise RuntimeError("최종 corpus WAV 수가 dry-run과 다름")
        if dict(sorted(totals.items())) != dict(sorted(expected_counts.items())):
            raise RuntimeError("최종 corpus mapping count가 dry-run과 다름")
        if final_year.exists():
            raise RuntimeError(f"최종 year root 충돌: {final_year}")
        final_year.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial_year, final_year)

        archive_summary = [
            {
                "session": session,
                "manifest_path": str(
                    (archive_root / "session_manifests" / f"{session}.json").resolve()
                ),
                "manifest_sha256": sha256_file(
                    archive_root / "session_manifests" / f"{session}.json"
                ),
                "status": archive_manifests[session]["status"],
                "zip_sha256": archive_manifests[session].get("zip_sha256"),
            }
            for session in affected_sessions
        ]
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "passed",
            "corpus_contract_id": contract_id,
            "year": year,
            "approved_by": approved_by,
            "completed_at": now_iso(),
            "source_wav_tree_untouched": True,
            "rollback": "remove or archive derived corpus only; source restore not required",
            "source_wav_root": str(source_wav_root.resolve()),
            "output_year": str(final_year.resolve()),
            "archive_root": str(archive_root.resolve()),
            "search_sessions": len(search_files),
            "wav_files": total_wavs,
            "logical_bytes": total_bytes,
            "mapping_counts": dict(sorted(totals.items())),
            "omitted_for_review": int(preflight["scan"]["omitted_for_review"]),
            "preflight_contract": contract,
            "archive_sessions": archive_summary,
        }
        atomic_write_json(contract_path, result)
        atomic_write_json(transaction_root / "APPLIED_MANIFEST.json", result)
        append_progress(
            progress_jsonl,
            {
                "event": "apply_completed",
                "corpus_contract_id": contract_id,
            },
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2020")
    parser.add_argument("--plan-csv", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--source-wav-root", type=Path, required=True)
    parser.add_argument("--output-wav-root", type=Path, required=True)
    parser.add_argument("--archive-base", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--review-decisions", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--progress-jsonl", type=Path)
    parser.add_argument("--approved-by", default="")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="verified archive와 별도 corpus를 실제 생성(기본은 쓰기 없는 dry-run)",
    )
    args = parser.parse_args()
    report = dry_run(
        year=args.year,
        plan_path=args.plan_csv.resolve(),
        search_master_root=args.search_master_root.resolve(),
        source_wav_root=args.source_wav_root.resolve(),
        output_wav_root=args.output_wav_root.resolve(),
        archive_base=args.archive_base.resolve(),
        review_manifest_path=args.review_manifest.resolve(),
        review_decisions_path=args.review_decisions.resolve(),
    )
    if args.apply:
        result = apply_recovery(
            preflight=report,
            year=args.year,
            plan_path=args.plan_csv.resolve(),
            search_master_root=args.search_master_root.resolve(),
            source_wav_root=args.source_wav_root.resolve(),
            output_wav_root=args.output_wav_root.resolve(),
            archive_base=args.archive_base.resolve(),
            approved_by=args.approved_by,
            progress_jsonl=(
                args.progress_jsonl.resolve() if args.progress_jsonl else None
            ),
        )
        report = {
            **report,
            "status": "apply_passed",
            "application": result,
        }
    atomic_write_json(args.report.resolve(), report)
    print(
        f"[OK] {report['status']}: corpus={report['scan']['corpus_entries']:,}, "
        f"omit={report['scan']['omitted_for_review']:,}, "
        f"affected_archive={report['apply_plan']['archive_uncompressed_gib']:.3f}GiB",
        flush=True,
    )
    print(args.report.resolve(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

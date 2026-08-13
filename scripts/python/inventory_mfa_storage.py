"""검증 완료 MFA temp의 보존·정리 후보를 삭제 없이 고정한다.

이 도구는 파일을 지우거나 옮기는 기능이 없다. 직전 연도의 독립 QC와
다음 연도 선행 gate가 통과한 뒤, exact file manifest와 예상 회수 용량을
사용자 검토용 JSON으로 만드는 역할만 한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


ACTIVE_DB_SUFFIXES = (".db-journal", ".db-wal", ".db-shm")
RECOMPUTABLE_SUFFIXES = {".ark", ".scp"}
RETAINED_SUFFIXES = {
    ".alimdl",
    ".counts",
    ".fst",
    ".int",
    ".log",
    ".mat",
    ".mdl",
    ".txt",
    ".yaml",
}
INTERVAL_CSVS = {
    "alignment/phone_intervals.csv",
    "alignment/word_intervals.csv",
}
RETAINED_EXACT_PATHS = {
    # Kaldi alignment model의 decision tree. 확장자가 없지만 실행 재현에
    # 필요한 모델 구성요소이므로 archive 정리 후보로 분류하지 않는다.
    "alignment/tree",
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"JSON object가 아님: {path}")
    return value


def _iter_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    unsafe_links: list[str] = []
    resolved_root = root.resolve()
    for directory, dirnames, filenames in os.walk(
        resolved_root, followlinks=False
    ):
        base = Path(directory)
        retained_dirs: list[str] = []
        for name in dirnames:
            child = base / name
            if child.is_symlink():
                unsafe_links.append(str(child))
            else:
                retained_dirs.append(name)
        dirnames[:] = retained_dirs
        for name in filenames:
            path = base / name
            if path.is_symlink():
                unsafe_links.append(str(path))
                continue
            resolved = path.resolve()
            try:
                resolved.relative_to(resolved_root)
            except ValueError:
                unsafe_links.append(str(path))
                continue
            if resolved.is_file():
                files.append(resolved)
    files.sort(key=lambda path: path.relative_to(resolved_root).as_posix())
    return files, sorted(unsafe_links)


def classify_temp_file(
    *,
    year: str,
    relative_path: str,
) -> tuple[str, str]:
    """파일 하나의 보존 정책과 근거를 반환한다."""

    normalized = relative_path.replace("\\", "/")
    name = Path(normalized).name
    suffix = Path(normalized).suffix.lower()
    lower_name = name.lower()
    if normalized == f"{year}.db":
        return (
            "retain_critical",
            "direct 4-tier 재생성과 SQLite 무결성 재검증의 기준 DB",
        )
    if lower_name.endswith(ACTIVE_DB_SUFFIXES):
        return (
            "retain_active_transaction",
            "SQLite 미완료 transaction 가능성 — 정리 금지",
        )
    if normalized in INTERVAL_CSVS:
        return (
            "cleanup_candidate_after_qc",
            "DB 적재·독립 QC 뒤 재생성 가능한 interval 중간 CSV",
        )
    if normalized in RETAINED_EXACT_PATHS:
        return (
            "retain_reproducibility",
            "해당 실행의 Kaldi alignment model 재현 근거",
        )
    if suffix in RECOMPUTABLE_SUFFIXES:
        return (
            "cleanup_candidate_after_qc",
            "DB·최종 TextGrid 검증 뒤 재계산 가능한 Kaldi archive/index",
        )
    if normalized.startswith("dictionary/"):
        return (
            "retain_reproducibility",
            "해당 실행의 dictionary/FST 재현 근거",
        )
    if suffix in RETAINED_SUFFIXES:
        return (
            "retain_reproducibility",
            "실행 로그·모델·설정 재현 근거",
        )
    return (
        "retain_unclassified",
        "자동 정리 정책에 없는 파일 — 사람 분류 전 정리 금지",
    )


def _summary(
    entries: Iterable[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "bytes": 0}
    )
    for entry in entries:
        bucket = totals[str(entry["classification"])]
        bucket["files"] += 1
        bucket["bytes"] += int(entry["bytes"])
    return {key: totals[key] for key in sorted(totals)}


def build_inventory(
    *,
    year: str,
    temp_year: Path,
    qc_gate_report: Path,
    hash_db: bool = False,
) -> dict[str, Any]:
    temp_year = temp_year.resolve(strict=False)
    qc_gate_report = qc_gate_report.resolve(strict=False)
    blockers: list[str] = []

    gate: dict[str, Any] | None = None
    gate_kind: str | None = None
    if not qc_gate_report.is_file():
        blockers.append("qc_gate_report_missing")
    else:
        try:
            gate = _read_json(qc_gate_report)
        except (OSError, ValueError, json.JSONDecodeError):
            blockers.append("qc_gate_report_unreadable")

    if gate is not None:
        schema = str(gate.get("schema_version") or "")
        if schema == "mfa_r3_research_qc_state.v1":
            gate_kind = "mfa_r3_research_qc_state"
            if gate.get("status") != "passed":
                blockers.append("qc_gate_not_passed")
            if str(gate.get("year") or "") != year:
                blockers.append("qc_gate_year_mismatch")
            if gate.get("source_mutation_performed") is not False:
                blockers.append("qc_gate_source_mutation_not_false")
            if gate.get("mfa_recomputed") is not False:
                blockers.append("qc_gate_mfa_recomputed_not_false")
            if gate.get("full_export_repeated") is not False:
                blockers.append("qc_gate_full_export_repeated_not_false")
            counts = gate.get("counts")
            if not isinstance(counts, dict):
                blockers.append("qc_gate_counts_missing")
            else:
                sessions = int(counts.get("sample_sessions", -1))
                if (
                    sessions < 5
                    or int(counts.get("sample_semantic_equal", -1))
                    != sessions
                    or int(counts.get("sample_byte_equal", -1))
                    != sessions
                ):
                    blockers.append("qc_gate_db_sample_not_equal")
        else:
            gate_kind = "legacy_next_year_qc_gate"
            if gate.get("status") != "passed":
                blockers.append("qc_gate_not_passed")
            if str(gate.get("prior_year") or "") != year:
                blockers.append("qc_gate_year_mismatch")
            if gate.get("failed_checks") not in ([], None):
                blockers.append("qc_gate_has_failed_checks")

    if not temp_year.is_dir():
        blockers.append("temp_year_missing")
        files: list[Path] = []
        unsafe_links: list[str] = []
    else:
        files, unsafe_links = _iter_files(temp_year)
    if unsafe_links:
        blockers.append("unsafe_symlink_or_reparse_entries")

    entries: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(temp_year).as_posix()
        classification, reason = classify_temp_file(
            year=year,
            relative_path=relative,
        )
        stat = path.stat()
        entries.append(
            {
                "relative_path": relative,
                "path": str(path),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "classification": classification,
                "reason": reason,
            }
        )

    classifications = _summary(entries)
    active_files = [
        entry["relative_path"]
        for entry in entries
        if entry["classification"] == "retain_active_transaction"
    ]
    unknown_files = [
        entry["relative_path"]
        for entry in entries
        if entry["classification"] == "retain_unclassified"
    ]
    if active_files:
        blockers.append("active_sqlite_transaction_files_present")
    if unknown_files:
        blockers.append("unclassified_temp_files_present")

    db_path = temp_year / f"{year}.db"
    db_fingerprint: dict[str, Any] | None = None
    if not db_path.is_file() or db_path.stat().st_size <= 0:
        blockers.append("retained_alignment_db_missing")
    else:
        db_fingerprint = file_fingerprint(
            db_path, with_sha256=hash_db
        )

    if gate is not None and gate_kind == "mfa_r3_research_qc_state":
        qc_input = gate.get("qc_input")
        if not isinstance(qc_input, dict):
            blockers.append("qc_gate_input_missing")
        elif db_fingerprint is not None:
            if int(qc_input.get("source_db_bytes", -1)) != int(
                db_fingerprint["bytes"]
            ):
                blockers.append("qc_gate_alignment_db_bytes_mismatch")
            expected_sha = str(
                qc_input.get("source_db_expected_sha256") or ""
            ).lower()
            observed_sha = str(db_fingerprint.get("sha256") or "").lower()
            if hash_db and expected_sha != observed_sha:
                blockers.append("qc_gate_alignment_db_sha256_mismatch")
    elif gate is not None:
        recorded_db = (
            gate.get("inputs", {}).get("alignment_db")
            if isinstance(gate.get("inputs"), dict)
            else None
        )
        if not recorded_db:
            blockers.append("qc_gate_alignment_db_missing")
        elif Path(str(recorded_db)).resolve(strict=False) != db_path.resolve():
            blockers.append("qc_gate_alignment_db_path_mismatch")

    evidence: list[dict[str, Any]] = []
    if qc_gate_report.is_file():
        evidence.append(
            {
                "role": "qc_gate_report",
                **file_fingerprint(
                    qc_gate_report, with_sha256=True
                ),
            }
        )
    if gate is not None and gate_kind == "mfa_r3_research_qc_state":
        for role in ("audit_report", "missing_csv", "sample_report", "sample_csv"):
            record = gate.get(role)
            if not isinstance(record, dict) or not record.get("path"):
                continue
            path = Path(str(record["path"])).resolve(strict=False)
            if path.is_file():
                evidence.append(
                    {
                        "role": role,
                        **file_fingerprint(path, with_sha256=True),
                    }
                )
    elif gate is not None and isinstance(gate.get("inputs"), dict):
        for role, value in sorted(gate["inputs"].items()):
            if not value:
                continue
            path = Path(str(value)).resolve(strict=False)
            if path.is_file():
                evidence.append(
                    {
                        "role": role,
                        **file_fingerprint(
                            path,
                            with_sha256=path.stat().st_size <= 64 * 1024 * 1024,
                        ),
                    }
                )

    candidate = classifications.get(
        "cleanup_candidate_after_qc", {"files": 0, "bytes": 0}
    )
    unique_blockers = sorted(set(blockers))
    return {
        "schema_version": 1,
        "kind": "mfa_storage_inventory_and_cleanup_dry_run",
        "year": year,
        "recorded_at": now_iso(),
        "status": (
            "ready_for_user_review"
            if not unique_blockers
            else "blocked"
        ),
        "mode": "inventory_only",
        "deletion_performed": False,
        "apply_supported": False,
        "authorization_required_for_any_cleanup": True,
        "temp_year": str(temp_year),
        "qc_gate_report": str(qc_gate_report),
        "qc_gate_kind": gate_kind,
        "qc_gate_status": gate.get("status") if gate else None,
        "blockers": unique_blockers,
        "unsafe_links": unsafe_links,
        "active_transaction_files": active_files,
        "unclassified_files": unknown_files,
        "totals": {
            "files": len(entries),
            "bytes": sum(int(entry["bytes"]) for entry in entries),
        },
        "classification_summary": classifications,
        "estimated_reclaim": {
            "files": int(candidate["files"]),
            "bytes": int(candidate["bytes"]),
        },
        "retained_db_fingerprint": db_fingerprint,
        "completion_evidence": evidence,
        "files": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--temp-year", required=True, type=Path)
    parser.add_argument(
        "--qc-gate-report", required=True, type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--hash-db",
        action="store_true",
        help="보존 SQLite DB의 SHA256도 계산(대용량이므로 완료 뒤 사용)",
    )
    args = parser.parse_args()
    report = build_inventory(
        year=args.year,
        temp_year=args.temp_year,
        qc_gate_report=args.qc_gate_report,
        hash_db=args.hash_db,
    )
    output = args.output.resolve(strict=False)
    atomic_write_json(output, report)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(
        json.dumps(
            {
                "status": report["status"],
                "blockers": report["blockers"],
                "totals": report["totals"],
                "classification_summary": (
                    report["classification_summary"]
                ),
                "estimated_reclaim": report["estimated_reclaim"],
                "deletion_performed": report["deletion_performed"],
                "apply_supported": report["apply_supported"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "ready_for_user_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())

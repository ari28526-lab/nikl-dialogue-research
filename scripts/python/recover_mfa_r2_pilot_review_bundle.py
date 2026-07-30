"""완성된 MFA r2 Dropbox partial 묶음을 검증하고 안전하게 승격한다.

패키징의 모든 복사와 검증이 끝났지만 Dropbox 동기화 잠금 때문에 마지막
디렉터리 rename만 실패한 경우에 사용한다. 원본이나 partial을 삭제하지
않으며, payload와 근거 파일을 다시 해시한 뒤에만 최종 이름으로 바꾼다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from package_mfa_r2_pilot_review import (
    ALL_YEARS,
    BUNDLE_SCHEMA_VERSION,
    promote_with_retry,
)
from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
    staged_text_writer,
)

LEGACY_SCHEMA_VERSION = "mfa_r2_flat_review_bundle.v1"
EXPECTED_UTTERANCES = 60
EXPECTED_FILES_PER_UTTERANCE = 4
EXPECTED_SUPPORT_FILES = {"REVIEW.csv", "MANIFEST.csv", "README.md"}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object가 아님: {path}")
    return value


def record_name(record: dict[str, Any], *, label: str) -> str:
    raw = record.get("relative_path") or record.get("path")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError(f"{label}: 파일 경로 기록 누락")
    name = Path(raw).name
    if (
        name != raw
        and record.get("relative_path") is not None
    ):
        raise RuntimeError(f"{label}: 상대경로는 평면 파일명이어야 함: {raw}")
    if name in {"", ".", ".."}:
        raise RuntimeError(f"{label}: 잘못된 파일명: {raw}")
    return name


def verify_fingerprint(
    path: Path,
    record: dict[str, Any],
    *,
    label: str,
) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{label}: 일반 파일이 아님: {path}")
    actual_bytes = path.stat().st_size
    if actual_bytes != record.get("bytes"):
        raise RuntimeError(
            f"{label}: bytes 불일치: {actual_bytes} != "
            f"{record.get('bytes')}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != record.get("sha256"):
        raise RuntimeError(f"{label}: SHA256 불일치: {path}")


def verify_source(record: dict[str, Any], *, label: str) -> None:
    source_raw = record.get("source_path")
    source_sha = record.get("source_sha256")
    if not isinstance(source_raw, str) or not isinstance(source_sha, str):
        raise RuntimeError(f"{label}: 원본 경로/SHA256 기록 누락")
    source = Path(source_raw)
    if not source.is_file():
        raise RuntimeError(f"{label}: 원본 파일 누락: {source}")
    if sha256_file(source) != source_sha:
        raise RuntimeError(f"{label}: 원본 SHA256이 패키징 이후 달라짐")


def verify_external_record(
    record: object,
    *,
    label: str,
) -> None:
    if not isinstance(record, dict):
        raise RuntimeError(f"{label}: fingerprint object 누락")
    raw = record.get("path")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError(f"{label}: 근거 파일 경로 누락")
    verify_fingerprint(Path(raw), record, label=label)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_bundle(
    root: Path,
    *,
    accepted_schemas: set[str],
    allowed_extra_files: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError(f"partial 묶음이 일반 디렉터리가 아님: {root}")
    entries = list(root.iterdir())
    directories = [
        path.name for path in entries
        if path.is_dir() or path.is_symlink()
    ]
    if directories:
        raise RuntimeError(f"평면 묶음 내부 디렉터리/링크 발견: {directories}")

    bundle_path = root / "BUNDLE_MANIFEST.json"
    if not bundle_path.is_file():
        raise FileNotFoundError(bundle_path)
    bundle = read_json(bundle_path)
    schema = bundle.get("schema_version")
    if schema not in accepted_schemas:
        raise RuntimeError(f"지원하지 않는 bundle schema: {schema}")
    years = bundle.get("machine_gate_evidence", {}).get("years")
    if (
        bundle.get("status") != "success"
        or bundle.get("flat_layout") is not True
        or bundle.get("utterances") != EXPECTED_UTTERANCES
        or bundle.get("files_per_utterance")
        != EXPECTED_FILES_PER_UTTERANCE
        or bundle.get("review_scope")
        != "infrastructure_acceptance_only"
        or bundle.get("realization_judgment_performed") is not False
        or years != list(ALL_YEARS)
    ):
        raise RuntimeError("bundle의 6개년 인프라 검토 계약 불일치")

    records = bundle.get("files")
    supporting = bundle.get("supporting_files")
    if not isinstance(records, list) or not isinstance(supporting, dict):
        raise RuntimeError("bundle 파일 목록 누락")
    if len(records) != EXPECTED_UTTERANCES * EXPECTED_FILES_PER_UTTERANCE:
        raise RuntimeError(f"payload 파일 기록 수 불일치: {len(records)}")
    if set(supporting) != EXPECTED_SUPPORT_FILES:
        raise RuntimeError(
            f"support 파일 목록 불일치: {sorted(supporting)}"
        )

    seen: set[str] = set()
    role_counts: Counter[str] = Counter()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise RuntimeError(f"payload #{index}: record object가 아님")
        name = record_name(record, label=f"payload #{index}")
        if name in seen:
            raise RuntimeError(f"중복 payload 파일명: {name}")
        seen.add(name)
        verify_fingerprint(
            root / name,
            record,
            label=f"payload #{index}",
        )
        verify_source(record, label=f"payload #{index}")
        role_counts[str(record.get("role") or "")] += 1
    expected_roles = {
        "wav": EXPECTED_UTTERANCES,
        "lab": EXPECTED_UTTERANCES,
        "TextGrid": EXPECTED_UTTERANCES,
        "selected_search_row_csv": EXPECTED_UTTERANCES,
    }
    if dict(role_counts) != expected_roles:
        raise RuntimeError(f"payload 역할 수 불일치: {dict(role_counts)}")

    for name, record in supporting.items():
        if not isinstance(record, dict):
            raise RuntimeError(f"support {name}: record object가 아님")
        if record_name(record, label=f"support {name}") != name:
            raise RuntimeError(f"support 파일명 불일치: {name}")
        verify_fingerprint(root / name, record, label=f"support {name}")

    review_rows = read_csv_rows(root / "REVIEW.csv")
    selection_rows = read_csv_rows(root / "MANIFEST.csv")
    for label, rows in (
        ("REVIEW.csv", review_rows),
        ("MANIFEST.csv", selection_rows),
    ):
        counts = Counter(row.get("year", "") for row in rows)
        if (
            len(rows) != EXPECTED_UTTERANCES
            or counts != Counter({year: 10 for year in ALL_YEARS})
        ):
            raise RuntimeError(
                f"{label}: 6개년 각 10개 계약 불일치: {dict(counts)}"
            )

    evidence = bundle.get("machine_gate_evidence")
    if not isinstance(evidence, dict):
        raise RuntimeError("machine gate 근거 누락")
    markers = evidence.get("machine_markers")
    contracts = evidence.get("year_contracts")
    if (
        not isinstance(markers, dict)
        or not isinstance(contracts, dict)
        or sorted(markers) != list(ALL_YEARS)
        or sorted(contracts) != list(ALL_YEARS)
    ):
        raise RuntimeError("6개년 machine marker/contract 근거 불일치")
    for year in ALL_YEARS:
        verify_external_record(
            markers[year], label=f"{year} machine marker"
        )
        contract = contracts[year]
        if not isinstance(contract, dict):
            raise RuntimeError(f"{year} contract object 누락")
        database = contract.get("database")
        if not isinstance(database, str) or not Path(database).is_file():
            raise RuntimeError(f"{year} MFA DB 누락: {database}")
        verify_external_record(
            contract.get("db_textgrid_sample_report"),
            label=f"{year} DB/TextGrid 표본 보고서",
        )
    verify_external_record(
        evidence.get("cross_year_method_audit"),
        label="6개년 방법 동일성 감사",
    )

    expected_names = (
        seen
        | EXPECTED_SUPPORT_FILES
        | {"BUNDLE_MANIFEST.json"}
        | (allowed_extra_files or set())
    )
    actual_names = {path.name for path in entries}
    if actual_names != expected_names:
        raise RuntimeError(
            "묶음 파일 집합 불일치: "
            f"missing={sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )
    summary = {
        "schema_version": schema,
        "files": len(actual_names),
        "payload_files": len(records),
        "support_files": len(supporting),
        "utterances": len(review_rows),
        "years": list(ALL_YEARS),
        "role_counts": dict(sorted(role_counts.items())),
    }
    return bundle, summary


def normalize_destination_records(
    bundle: dict[str, Any],
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(bundle, ensure_ascii=False))
    for record in normalized["files"]:
        name = record_name(record, label="payload normalize")
        record["relative_path"] = name
        record.pop("path", None)
    for name, record in normalized["supporting_files"].items():
        actual_name = record_name(record, label=f"support {name} normalize")
        if actual_name != name:
            raise RuntimeError(f"support 파일명 불일치: {name}")
        record["relative_path"] = name
        record.pop("path", None)
    normalized["schema_version"] = BUNDLE_SCHEMA_VERSION
    return normalized


def replace_file_with_retry(
    temp: Path,
    destination: Path,
    *,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    delay = 0.5
    last_error: OSError | None = None
    while True:
        try:
            os.replace(temp, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)
    raise RuntimeError(
        f"manifest 교체 잠금이 해제되지 않음: {last_error}; "
        f"보존된 임시파일={temp}"
    ) from last_error


def write_json_with_retry(
    path: Path,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with staged_text_writer(
        path, encoding="utf-8", newline="\n"
    ) as (stream, temp):
        stream.write(text)
    replace_file_with_retry(
        temp,
        path,
        timeout_seconds=timeout_seconds,
    )


def recover_bundle(
    *,
    partial_root: Path,
    output_root: Path,
    report_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    partial_root = partial_root.resolve()
    output_root = output_root.resolve()
    report_path = report_path.resolve()
    if output_root.exists():
        raise FileExistsError(f"최종 검토 폴더가 이미 존재함: {output_root}")
    if partial_root.parent != output_root.parent:
        raise ValueError("partial과 최종 폴더는 같은 Dropbox 부모여야 함")
    if (
        not partial_root.name.startswith(f".{output_root.name}.")
        or not partial_root.name.endswith(".partial")
    ):
        raise ValueError(
            f"예상 partial 이름이 아님: {partial_root.name}"
        )
    if report_path.exists():
        raise FileExistsError(f"기존 복구 보고서를 덮어쓰지 않음: {report_path}")

    bundle_path = partial_root / "BUNDLE_MANIFEST.json"
    prior_manifest = file_fingerprint(bundle_path, with_sha256=True)
    bundle, before = validate_bundle(
        partial_root,
        accepted_schemas={
            LEGACY_SCHEMA_VERSION,
            BUNDLE_SCHEMA_VERSION,
        },
    )
    if bundle["schema_version"] == LEGACY_SCHEMA_VERSION:
        normalized = normalize_destination_records(bundle)
        normalized["recovery"] = {
            "recovered_at": now_iso(),
            "reason": "Dropbox directory rename lock after complete package",
            "prior_manifest": prior_manifest,
            "verification_before_rewrite": before,
            "destination_paths_normalized_to_relative": True,
        }
        write_json_with_retry(
            bundle_path,
            normalized,
            timeout_seconds=timeout_seconds,
        )
    elif not isinstance(bundle.get("recovery"), dict):
        raise RuntimeError(
            "v2 partial에 복구 provenance가 없어 자동 승격하지 않음"
        )

    _normalized, after_rewrite = validate_bundle(
        partial_root,
        accepted_schemas={BUNDLE_SCHEMA_VERSION},
    )
    promote_with_retry(
        partial_root,
        output_root,
        timeout_seconds=timeout_seconds,
    )
    final_bundle, after_promotion = validate_bundle(
        output_root,
        accepted_schemas={BUNDLE_SCHEMA_VERSION},
    )
    report: dict[str, Any] = {
        "schema_version": "mfa_r2_review_bundle_recovery.v1",
        "status": "success",
        "recovered_at": now_iso(),
        "reason": "Dropbox directory rename lock after complete package",
        "partial_root": str(partial_root),
        "output_root": str(output_root),
        "prior_manifest": prior_manifest,
        "verification_before_rewrite": before,
        "verification_after_rewrite": after_rewrite,
        "verification_after_promotion": after_promotion,
        "final_bundle_manifest": file_fingerprint(
            output_root / "BUNDLE_MANIFEST.json",
            with_sha256=True,
        ),
        "source_or_d_results_modified": False,
        "final_bundle_recovery": final_bundle.get("recovery"),
    }
    atomic_write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args()
    report = recover_bundle(
        partial_root=args.partial_root,
        output_root=args.output_root,
        report_path=args.report,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""MFA r2 파일럿을 Dropbox용 단일 평면 검토 폴더로 묶는다."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import time
from pathlib import Path

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)

ALL_YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
BUNDLE_SCHEMA_VERSION = "mfa_r2_flat_review_bundle.v2"

REVIEW_FIELDS = [
    "review_order",
    "year",
    "utt_id",
    "speaker_id",
    "session_id",
    "linkage_status",
    "tier_structure_status",
    "boundary_status",
    "csv_searchability_status",
    "overall_infrastructure_decision",
    "notes",
    "wav_file",
    "textgrid_file",
    "lab_file",
    "csv_file",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def write_csv(
    path: Path, fields: list[str], rows: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def copy_checked(source: Path, destination: Path) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(source)
    source_sha = sha256_file(source)
    shutil.copy2(source, destination)
    if (
        destination.stat().st_size != source.stat().st_size
        or destination.stat().st_size <= 0
    ):
        raise RuntimeError(f"복사 크기 검증 실패: {source} -> {destination}")
    destination_sha = sha256_file(destination)
    if destination_sha != source_sha:
        raise RuntimeError(f"복사 SHA256 검증 실패: {source} -> {destination}")
    result = file_fingerprint(destination, with_sha256=True)
    result["relative_path"] = destination.name
    result.pop("path", None)
    result["source_path"] = str(source.resolve())
    result["source_sha256"] = source_sha
    return result


def relative_fingerprint(path: Path) -> dict[str, object]:
    result = file_fingerprint(path, with_sha256=True)
    result["relative_path"] = path.name
    result.pop("path", None)
    return result


def promote_with_retry(
    staging: Path,
    output_root: Path,
    *,
    timeout_seconds: float = 120.0,
) -> None:
    """Dropbox의 일시적 Windows file lock이 풀릴 때까지 rename을 재시도."""

    deadline = time.monotonic() + timeout_seconds
    delay = 1.0
    last_error: OSError | None = None
    while True:
        try:
            os.replace(staging, output_root)
            return
        except PermissionError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)
    raise RuntimeError(
        "Dropbox partial 폴더 rename 잠금이 제한 시간 안에 해제되지 않음: "
        f"{staging} -> {output_root}: {last_error}"
    ) from last_error


def read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object 아님: {path}")
    return value


def validate_machine_gates(
    run_root: Path,
    rows: list[dict[str, str]],
) -> dict[str, object]:
    """단독 패키징이 연도별·6개년 기계 gate를 우회하지 못하게 한다."""

    years = sorted({row.get("year", "") for row in rows})
    if not years or any(year not in ALL_YEARS for year in years):
        raise RuntimeError(f"selection manifest 연도 계약 불일치: {years}")
    machine_records: dict[str, object] = {}
    year_contracts: dict[str, object] = {}
    for year in years:
        year_rows = [row for row in rows if row.get("year") == year]
        marker_path = run_root / "state" / f"{year}.machine_done.json"
        marker = read_json(marker_path)
        if (
            marker.get("year") != year
            or marker.get("stage") != "machine_qc"
            or marker.get("status") != "passed"
            or marker.get("pronunciation_mode")
            != "common_pron_mfa_r2_latest_jamo"
            or marker.get("inline_g2p_used") is not False
            or marker.get("researcher_review_status") != "pending"
            or marker.get("realization_judgment_performed") is not False
            or marker.get("textgrids") != len(year_rows)
            or not marker.get("alignment_contract_id")
            or not marker.get("lab_input_contract_id")
            or not marker.get("database")
            or not marker.get("db_textgrid_sample_report")
        ):
            raise RuntimeError(f"{year} machine gate marker 불일치")
        database = Path(str(marker["database"])).resolve()
        sample_path = Path(
            str(marker["db_textgrid_sample_report"])
        ).resolve()
        sample = read_json(sample_path)
        sample_db = sample.get("db")
        comparison = sample.get("comparison_counts")
        selection = sample.get("selection_counts")
        if (
            sample.get("status") != "success"
            or sample.get("year") != year
            or not isinstance(sample_db, dict)
            or Path(str(sample_db.get("path") or "")).resolve()
            != database
            or not isinstance(comparison, dict)
            or comparison.get("compared", 0) < 5
            or comparison.get("tier_equal")
            != comparison.get("compared")
            or not isinstance(selection, dict)
            or selection.get("selected_sessions", 0) < 5
        ):
            raise RuntimeError(f"{year} DB→TextGrid 표본 gate 불일치")
        machine_records[year] = file_fingerprint(
            marker_path, with_sha256=True
        )
        year_contracts[year] = {
            "alignment_contract_id": marker[
                "alignment_contract_id"
            ],
            "lab_input_contract_id": marker[
                "lab_input_contract_id"
            ],
            "database": str(database),
            "db_textgrid_sample_report": file_fingerprint(
                sample_path, with_sha256=True
            ),
        }

    cross_year_record: dict[str, object] | None = None
    if years == list(ALL_YEARS):
        cross_path = run_root / "logs" / "cross_year_method_audit.json"
        cross = read_json(cross_path)
        gate = cross.get("gate")
        if (
            cross.get("schema_version")
            != "mfa_cross_year_method_consistency.v1"
            or cross.get("status") != "passed"
            or not isinstance(gate, dict)
            or gate.get("years_expected") != 6
            or gate.get("years_observed") != 6
            or gate.get("cross_year_method_mismatches") != 0
            or gate.get("same_phone_generation_standard") is not True
            or gate.get("same_allowed_phone_inventory") is not True
            or gate.get("observed_phones_outside_allowed") != 0
        ):
            raise RuntimeError("6개년 method/phone gate 불일치")
        cross_year_record = file_fingerprint(
            cross_path, with_sha256=True
        )
    return {
        "years": years,
        "machine_markers": machine_records,
        "year_contracts": year_contracts,
        "cross_year_method_audit": cross_year_record,
    }


def package_review(run_root: Path, output_root: Path) -> dict[str, object]:
    run_root = run_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(
            f"기존 검토 폴더를 덮어쓰지 않음: {output_root}"
        )
    manifest_fields, rows = read_csv(
        run_root / "selection_manifest.csv"
    )
    if not rows:
        raise RuntimeError("selection manifest가 비어 있음")
    machine_evidence = validate_machine_gates(run_root, rows)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    old_partials = sorted(
        output_root.parent.glob(f".{output_root.name}.*.partial")
    )
    if old_partials:
        raise FileExistsError(
            "기존 검토 묶음 partial을 먼저 점검해야 함: "
            + ", ".join(str(path) for path in old_partials)
        )
    staging = output_root.with_name(
        f".{output_root.name}.{os.getpid()}.partial"
    )
    if staging.exists():
        raise FileExistsError(f"기존 partial 폴더 점검 필요: {staging}")
    staging.mkdir()
    review_rows: list[dict[str, object]] = []
    bundle_files: list[dict[str, object]] = []
    seen_prefixes: set[str] = set()
    for order, row in enumerate(rows, 1):
        year = row["year"]
        utt_id = row["utt_id"]
        session = row["session_id"]
        prefix = f"{year}__{utt_id}"
        if prefix in seen_prefixes:
            raise RuntimeError(f"중복 검토 파일 접두사: {prefix}")
        seen_prefixes.add(prefix)
        sources = {
            "wav": run_root / row["corpus_wav_relpath"],
            "lab": run_root / row["corpus_lab_relpath"],
            "TextGrid": (
                run_root / "textgrid_4tier" / year / session
                / f"{utt_id}.TextGrid"
            ),
        }
        names = {
            "wav": f"{prefix}.wav",
            "lab": f"{prefix}.lab",
            "TextGrid": f"{prefix}.TextGrid",
            "csv": f"{prefix}.csv",
        }
        for key, source in sources.items():
            destination = staging / names[key]
            record = copy_checked(source, destination)
            record["role"] = key
            bundle_files.append(record)

        session_csv = (
            run_root / "search_master" / year / f"{session}.csv"
        )
        search_fields, search_rows = read_csv(session_csv)
        matching = [
            item for item in search_rows
            if item.get("utt_id") == utt_id
        ]
        if len(matching) != 1:
            raise RuntimeError(
                f"{year} {utt_id} 동결 검색행 수={len(matching)}"
            )
        combined: dict[str, object] = {
            f"pilot__{field}": row.get(field, "")
            for field in manifest_fields
        }
        combined.update(
            {
                f"search__{field}": matching[0].get(field, "")
                for field in search_fields
            }
        )
        combined_fields = [
            *(f"pilot__{field}" for field in manifest_fields),
            *(f"search__{field}" for field in search_fields),
        ]
        csv_path = staging / names["csv"]
        write_csv(csv_path, combined_fields, [combined])
        bundle_files.append(
            {
                **relative_fingerprint(csv_path),
                "role": "selected_search_row_csv",
                "source_path": str(session_csv.resolve()),
                "source_sha256": sha256_file(session_csv),
            }
        )
        review_rows.append(
            {
                "review_order": order,
                "year": year,
                "utt_id": utt_id,
                "speaker_id": row["speaker_id"],
                "session_id": session,
                "linkage_status": "미검토",
                "tier_structure_status": "미검토",
                "boundary_status": "미검토",
                "csv_searchability_status": "미검토",
                "overall_infrastructure_decision": "미검토",
                "notes": "",
                "wav_file": names["wav"],
                "textgrid_file": names["TextGrid"],
                "lab_file": names["lab"],
                "csv_file": names["csv"],
            }
        )

    write_csv(staging / "REVIEW.csv", REVIEW_FIELDS, review_rows)
    write_csv(staging / "MANIFEST.csv", manifest_fields, rows)
    readme = (
        "# MFA r2 인프라 수용 파일럿\n\n"
        "이 폴더는 한 폴더에서 WAV·TextGrid·LAB·CSV 연결과 4-tier 구조를 "
        "점검하기 위한 평면 검토 묶음입니다.\n\n"
        "- 파일 이름: `연도__발화ID.확장자`\n"
        "- 검토 범위: 파일 연결, tier 구조·경계, CSV 검색 편의성\n"
        "- 이 단계에서 하지 않는 일: ㄴ 삽입 등 구체적 음운 실현 판정\n"
        "- TextGrid tiers: words, phones, morphemes, utterance\n"
        "- phones는 MFA 정렬용·탐색 보조층이며 실제 실현 판정값이 아닙니다.\n"
        "- REVIEW.xlsx의 노란 열에 인프라 점검만 기록하십시오.\n"
        "- 발화·파일 연결 열과 파일 이름은 바꾸지 마십시오.\n"
        "- REVIEW.csv는 XLSX 생성 기준이며, 작성본은 별도 검증 뒤 "
        "기계가독 결정표로 회수합니다.\n"
    )
    (staging / "README.md").write_text(readme, encoding="utf-8")
    supporting_files = {
        name: relative_fingerprint(staging / name)
        for name in ("REVIEW.csv", "MANIFEST.csv", "README.md")
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "status": "success",
        "created_at": now_iso(),
        "run_root": str(run_root),
        "output_root": str(output_root),
        "flat_layout": True,
        "utterances": len(rows),
        "files_per_utterance": 4,
        "review_scope": "infrastructure_acceptance_only",
        "realization_judgment_performed": False,
        "machine_gate_evidence": machine_evidence,
        "supporting_files": supporting_files,
        "files": bundle_files,
    }
    atomic_write_json(staging / "BUNDLE_MANIFEST.json", bundle)
    expected = len(rows) * 4 + 4
    actual = sum(path.is_file() for path in staging.iterdir())
    if actual != expected:
        raise RuntimeError(
            f"평면 묶음 파일 수 불일치: expected={expected} actual={actual}"
        )
    promote_with_retry(staging, output_root)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = package_review(args.run_root, args.output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

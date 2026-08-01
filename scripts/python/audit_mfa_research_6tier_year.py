"""연도별 연구 6-tier·동반표를 독립적으로 전수 감사한다.

러너의 exporter 성공 보고를 신뢰해 반복하는 대신 final staging 실물,
active LAB/WAV, 연구자 승인 제외 계약, 동반표 SHA/행 키를 다시 읽어 정확한
ID 집합과 시간·tier 계약을 검사한다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import time
import wave
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable

from mfa_exclusion_contract import load_contract as load_exclusion_contract
from phoneme_roman import load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_text_writer, atomic_write_json, sha256_file
from research_companion_schema import load_schema as load_companion_schema
from research_textgrid_v2 import BASE_TIERS, SILENCE
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

SCHEMA_VERSION = "mfa_research_6tier_year_audit.v1"
TABLE_SCHEMA_VERSION = "mfa_research_companion_tables.v2"


def iter_files(root: Path, suffix: str) -> Iterable[Path]:
    wanted = suffix.lower()
    for directory, subdirs, files in os.walk(root):
        subdirs.sort()
        files.sort()
        for name in files:
            if name.lower().endswith(wanted):
                yield Path(directory) / name


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def _same_edges(left: list[tuple], right: list[tuple], tolerance: float) -> bool:
    return len(left) == len(right) and all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        for a, b in zip(left, right)
    )


def inspect_textgrid(
    path: Path,
    *,
    wav_path: Path,
    allowed_phones: set[str],
    tolerance: float,
) -> dict[str, object]:
    reasons: list[str] = []
    phone_outside: set[str] = set()
    spn = 0
    try:
        duration, tiers = parse_mfa_textgrid(path)
        if list(tiers) != BASE_TIERS:
            reasons.append(f"tier_schema:{list(tiers)!r}")
        if duration is None or float(duration) <= 0:
            reasons.append(f"invalid_duration:{duration}")
            duration = 0.0
        for name in BASE_TIERS:
            intervals = list(tiers.get(name, []))
            if not intervals:
                reasons.append(f"empty_tier:{name}")
                continue
            cursor = 0.0
            for index, (begin, end, label) in enumerate(intervals):
                begin, end = float(begin), float(end)
                if abs(begin - cursor) > tolerance:
                    reasons.append(f"noncontinuous:{name}:{index}")
                    break
                if end < begin - tolerance or end > float(duration) + tolerance:
                    reasons.append(f"invalid_interval:{name}:{index}")
                    break
                cursor = end
                if name == "phones_mfa" and str(label).strip():
                    normalized = str(label).strip()
                    if normalized.lower() == "spn":
                        spn += 1
                        reasons.append(f"spn_interval:{index}")
                    elif normalized.lower() not in SILENCE and normalized not in allowed_phones:
                        phone_outside.add(normalized)
            if abs(cursor - float(duration)) > tolerance:
                reasons.append(f"right_boundary:{name}:{cursor}/{duration}")
        if not _same_edges(
            list(tiers.get("phones_mfa", [])),
            list(tiers.get("phoneme_r_auto", [])),
            tolerance,
        ):
            reasons.append("phone_phoneme_edges")
        speech = [
            list(tiers.get(name, []))
            for name in ("utterance", "utterance_orth_r", "morph_analysis_utt")
        ]
        if not all(_same_edges(speech[0], item, tolerance) for item in speech[1:]):
            reasons.append("speech_tier_edges")
        if not wav_path.is_file():
            reasons.append("wav_missing")
        elif abs(_duration(wav_path) - float(duration)) > tolerance:
            reasons.append("wav_duration_mismatch")
    except Exception as exc:
        reasons.append(f"parse_error:{type(exc).__name__}:{exc}")
    return {
        "utt_id": path.stem,
        "valid": not reasons,
        "reasons": reasons,
        "spn": spn,
        "phone_outside": sorted(phone_outside),
    }


def _scan_gzip_table(
    path: Path,
    *,
    table_name: str,
    expected_fields: list[str],
) -> dict[str, object]:
    """Scan a large table without retaining its interval rows in memory."""

    row_count = 0
    ids: set[str] = set()
    duplicate_keys = 0
    invalid_key_order = 0
    completed_ids: set[str] = set()
    current_id = ""
    current_index = 0
    index_field = {
        "words": "word_interval_idx",
        "phones": "phone_interval_idx",
    }.get(table_name)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        if fields != expected_fields:
            raise RuntimeError(
                f"{table_name}: table header mismatch: {fields!r}"
            )
        for row in reader:
            row_count += 1
            utt_id = str(row.get("utt_id", ""))
            if not utt_id:
                invalid_key_order += 1
                continue
            if index_field is None:
                if utt_id in ids:
                    duplicate_keys += 1
                ids.add(utt_id)
                continue
            if utt_id != current_id:
                if current_id:
                    completed_ids.add(current_id)
                if utt_id in completed_ids:
                    invalid_key_order += 1
                current_id = utt_id
                current_index = 0
            try:
                interval_index = int(str(row.get(index_field, "")))
            except ValueError:
                invalid_key_order += 1
                continue
            if interval_index <= current_index:
                duplicate_keys += 1
            if interval_index != current_index + 1:
                invalid_key_order += 1
            current_index = interval_index
            ids.add(utt_id)
    return {
        "row_count": row_count,
        "ids": ids,
        "duplicate_keys": duplicate_keys,
        "invalid_key_order": invalid_key_order,
    }


def audit_year(
    *,
    year: str,
    lab_root: Path,
    textgrid_root: Path,
    acoustic_model: Path,
    approved_exclusions_contract: Path,
    input_contract_id: str,
    alignment_contract_id: str,
    report_path: Path,
    missing_csv_path: Path,
    workers: int = 4,
    tolerance: float = 0.001,
) -> dict[str, object]:
    started = time.monotonic()
    lab_year = lab_root.resolve() / year
    tg_year = textgrid_root.resolve() / year
    contract_data, exclusions = load_exclusion_contract(
        approved_exclusions_contract,
        year=year,
        input_contract_id=input_contract_id,
    )
    alignment_excluded = {
        utt_id
        for utt_id, row in exclusions.items()
        if row["exclusion_scope"] == "alignment_and_analysis"
    }
    analysis_only = set(exclusions) - alignment_excluded

    lab_paths: dict[str, Path] = {}
    duplicate_labs: set[str] = set()
    for path in iter_files(lab_year, ".lab"):
        if path.stem in lab_paths:
            duplicate_labs.add(path.stem)
        lab_paths[path.stem] = path
    tg_paths: dict[str, Path] = {}
    duplicate_tg: set[str] = set()
    for path in iter_files(tg_year, ".TextGrid"):
        if path.stem in tg_paths:
            duplicate_tg.add(path.stem)
        tg_paths[path.stem] = path
    expected_tg_ids = set(lab_paths) - alignment_excluded
    missing = sorted(expected_tg_ids - set(tg_paths))
    extras = sorted(set(tg_paths) - expected_tg_ids)

    allowed_phones = set(model_group_lookup(load_acoustic_meta(acoustic_model)))
    reason_counts: Counter[str] = Counter()
    invalid_ids: list[str] = []
    spn = 0
    outside: set[str] = set()

    def inspect(item: tuple[str, Path]) -> dict[str, object]:
        utt_id, path = item
        relative = path.relative_to(tg_year)
        wav_path = lab_year / relative.parent / f"{utt_id}.wav"
        return inspect_textgrid(
            path,
            wav_path=wav_path,
            allowed_phones=allowed_phones,
            tolerance=tolerance,
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for result in executor.map(inspect, sorted(tg_paths.items())):
            spn += int(result["spn"])
            outside.update(result["phone_outside"])
            if not result["valid"]:
                invalid_ids.append(str(result["utt_id"]))
                for reason in result["reasons"]:
                    reason_counts[str(reason).split(":", 1)[0]] += 1

    table_root = tg_year / "_tables"
    manifest_path = table_root / "TABLES_MANIFEST.json"
    manifest_error = ""
    table_scans: dict[str, dict[str, object]] = {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != TABLE_SCHEMA_VERSION:
            raise RuntimeError("table schema version 불일치")
        if manifest.get("status") != "success":
            raise RuntimeError("table manifest status 불일치")
        if manifest.get("input_contract_id") != input_contract_id:
            raise RuntimeError("table input contract 불일치")
        if manifest.get("alignment_contract_id") != alignment_contract_id:
            raise RuntimeError("table alignment contract 불일치")
        _schema_path, companion_schema = load_companion_schema()
        if (
            manifest.get("column_schema", {}).get("sha256")
            != sha256_file(_schema_path)
            or manifest.get("csv_contract") != companion_schema.get("csv")
            or manifest.get("compression_contract")
            != companion_schema.get("compression")
        ):
            raise RuntimeError("table serialization/schema contract mismatch")
        expected_tables = set(companion_schema["tables"])
        manifest_tables = manifest.get("tables", {})
        if set(manifest_tables) != expected_tables:
            raise RuntimeError("table manifest table set mismatch")
        for name, info in manifest_tables.items():
            path = Path(str(info.get("path", "")))
            if not path.is_absolute():
                path = table_root / path
            if not path.is_file() or sha256_file(path) != info.get("sha256"):
                raise RuntimeError(f"table fingerprint 불일치: {name}")
            expected_fields = [
                item[0] for item in companion_schema["tables"][name]["fields"]
            ]
            table_scans[name] = _scan_gzip_table(
                path,
                table_name=name,
                expected_fields=expected_fields,
            )
    except Exception as exc:
        manifest = {}
        manifest_error = f"{type(exc).__name__}: {exc}"

    def scan(name: str) -> dict[str, object]:
        return table_scans.get(
            name,
            {
                "row_count": 0,
                "ids": set(),
                "duplicate_keys": 0,
                "invalid_key_order": 0,
            },
        )

    utterance_scan = scan("utterances")
    word_scan = scan("words")
    phone_scan = scan("phones")
    excluded_scan = scan("excluded")
    utterance_ids = set(utterance_scan["ids"])
    excluded_ids = set(excluded_scan["ids"])
    manifest_counts = manifest.get("counts", {}) if isinstance(manifest, dict) else {}
    hard = {
        "duplicate_lab_ids": len(duplicate_labs),
        "duplicate_textgrid_ids": len(duplicate_tg),
        "missing_textgrid_ids": len(missing),
        "extra_textgrid_ids": len(extras),
        "invalid_textgrids": len(invalid_ids),
        "spn_intervals": spn,
        "phone_outside_inventory": len(outside),
        "table_manifest_error": int(bool(manifest_error)),
        "utterance_table_id_mismatch": int(utterance_ids != set(tg_paths)),
        "duplicate_utterance_table_ids": int(utterance_scan["duplicate_keys"]),
        "duplicate_word_keys": int(word_scan["duplicate_keys"]),
        "duplicate_phone_keys": int(phone_scan["duplicate_keys"]),
        "invalid_word_key_order": int(word_scan["invalid_key_order"]),
        "invalid_phone_key_order": int(phone_scan["invalid_key_order"]),
        "excluded_table_id_mismatch": int(excluded_ids != set(exclusions)),
        "duplicate_excluded_table_ids": int(excluded_scan["duplicate_keys"]),
        "analysis_only_without_textgrid": len(analysis_only - set(tg_paths)),
        "manifest_utterance_count_mismatch": int(
            manifest_counts.get("utterances") != utterance_scan["row_count"]
        ),
        "manifest_word_count_mismatch": int(
            manifest_counts.get("word_intervals") != word_scan["row_count"]
        ),
        "manifest_phone_count_mismatch": int(
            manifest_counts.get("phone_intervals") != phone_scan["row_count"]
        ),
        "manifest_excluded_count_mismatch": int(
            manifest_counts.get("excluded_utterances", 0)
            != excluded_scan["row_count"]
        ),
    }
    status = "success" if set(lab_paths) and all(v == 0 for v in hard.values()) else "failed"
    with atomic_text_writer(
        missing_csv_path.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(
            stream, fieldnames=["year", "utt_id", "reason"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(
            [{"year": year, "utt_id": uid, "reason": "missing_textgrid"} for uid in missing]
            + [{"year": year, "utt_id": uid, "reason": "extra_textgrid"} for uid in extras]
        )
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "year": year,
        "input_contract_id": input_contract_id,
        "alignment_contract_id": alignment_contract_id,
        "lab_root": str(lab_root.resolve()),
        "textgrid_root": str(textgrid_root.resolve()),
        "approved_exclusions_contract": contract_data,
        "coverage_pct": (
            round(100 * len(set(tg_paths) & expected_tg_ids) / len(expected_tg_ids), 6)
            if expected_tg_ids else 0
        ),
        "hard_failure_counts": hard,
        "counts": {
            "active_lab_ids": len(lab_paths),
            "expected_textgrid_ids": len(expected_tg_ids),
            "textgrid_ids": len(tg_paths),
            "approved_exclusions": len(exclusions),
            "approved_alignment_exclusions": len(alignment_excluded),
            "approved_analysis_only_exclusions": len(analysis_only),
            "utterance_table_rows": int(utterance_scan["row_count"]),
            "word_table_rows": int(word_scan["row_count"]),
            "phone_table_rows": int(phone_scan["row_count"]),
            "excluded_table_rows": int(excluded_scan["row_count"]),
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "inventories": {
            "missing_textgrid_ids": missing,
            "extra_textgrid_ids": extras,
            "invalid_textgrid_ids": sorted(invalid_ids),
            "phone_outside_inventory": sorted(outside),
        },
        "table_manifest": manifest,
        "table_manifest_error": manifest_error,
        "missing_csv": str(missing_csv_path.resolve()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    atomic_write_json(report_path.resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--lab-root", type=Path, required=True)
    parser.add_argument("--textgrid-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--approved-exclusions-contract", type=Path, required=True)
    parser.add_argument("--input-contract-id", required=True)
    parser.add_argument("--alignment-contract-id", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--missing-csv", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    report = audit_year(
        year=args.year,
        lab_root=args.lab_root,
        textgrid_root=args.textgrid_root,
        acoustic_model=args.acoustic_model,
        approved_exclusions_contract=args.approved_exclusions_contract,
        input_contract_id=args.input_contract_id,
        alignment_contract_id=args.alignment_contract_id,
        report_path=args.report,
        missing_csv_path=args.missing_csv,
        workers=args.workers,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

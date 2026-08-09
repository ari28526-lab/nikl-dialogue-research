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
from typing import Callable, Iterable, Mapping

from audit_mfa_r3_alignment_contract import independent_contract_id
from mfa_exclusion_contract import load_contract as load_exclusion_contract
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_text_writer, atomic_write_json, sha256_file
from research_companion_schema import load_schema as load_companion_schema
from research_textgrid_v2 import (
    BASE_TIERS,
    SCHEMA_VERSION as TEXTGRID_SCHEMA_VERSION,
    SILENCE,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

SCHEMA_VERSION = "mfa_research_6tier_year_audit.v1"
TABLE_SCHEMA_VERSION = "mfa_research_companion_tables.v2"
R3_ALIGNMENT_SCHEMA_VERSION = "mfa_r3_alignment_contract.v1"
R3_ALIGNMENT_STATUS = "materialized_pending_runner_preflight_and_release_gate"
R3_REQUIRED_MANIFEST_FIELDS = (
    "pronunciation_release_id",
    "pronunciation_contract_id",
    "mfa_dictionary_sha256",
    "alignment_contract_id",
    "textgrid_schema",
    "source_db_sha256",
    "alignment_origin",
    "r3_full_realign",
    "safe_body_routing_contract_id",
    "followup_inventory_sha256",
)
PhoneMapper = Callable[[str], str]


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
    phone_mapper: PhoneMapper,
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
        phone_intervals = list(tiers.get("phones_mfa", []))
        phoneme_intervals = list(tiers.get("phoneme_r_auto", []))
        same_phone_edges = _same_edges(
            phone_intervals,
            phoneme_intervals,
            tolerance,
        )
        if not same_phone_edges:
            reasons.append("phone_phoneme_edges")
        else:
            for index, (phone_row, phoneme_row) in enumerate(
                zip(phone_intervals, phoneme_intervals)
            ):
                phone = str(phone_row[2]).strip()
                actual = str(phoneme_row[2]).strip()
                if phone.lower() in SILENCE:
                    expected = ""
                elif phone in allowed_phones:
                    expected = phone_mapper(phone)
                else:
                    continue
                if actual != expected:
                    reasons.append(
                        f"phoneme_label:{index}:{phone}:{actual}:{expected}"
                    )
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


def _verify_contract_file(record: Mapping[str, object], label: str) -> Path:
    path = Path(str(record.get("path", ""))).resolve()
    if (
        not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or str(record.get("sha256", "")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"r3 audit contract file mismatch: {label}")
    return path


def expected_r3_manifest_fields(
    *,
    alignment_contract_path: Path,
    source_db: Path,
    acoustic_model: Path,
    year: str,
    alignment_contract_id: str,
) -> dict[str, object]:
    contract = json.loads(
        alignment_contract_path.read_text(encoding="utf-8-sig")
    )
    if contract.get("schema_version") != R3_ALIGNMENT_SCHEMA_VERSION:
        return {}
    if (
        contract.get("status") != R3_ALIGNMENT_STATUS
        or str(contract.get("year")) != str(year)
        or contract.get("alignment_contract_id") != alignment_contract_id
        or contract.get("r3_full_realign") is not True
        or contract.get("alignment_origin") != "fresh_r3_full_realign"
        or independent_contract_id(contract) != alignment_contract_id
    ):
        raise RuntimeError("r3 alignment identity differs in independent export audit")
    identity = contract.get("identity")
    models = contract.get("models")
    if not isinstance(identity, Mapping) or not isinstance(models, Mapping):
        raise RuntimeError("r3 alignment identity/models missing in audit")
    dictionary = models.get("dictionary")
    acoustic = models.get("acoustic")
    g2p = models.get("g2p_provenance")
    if not all(isinstance(item, Mapping) for item in (dictionary, acoustic, g2p)):
        raise RuntimeError("r3 alignment model records missing in audit")
    dictionary_path = _verify_contract_file(dictionary, "dictionary")
    acoustic_path = _verify_contract_file(acoustic, "acoustic")
    _verify_contract_file(g2p, "g2p_provenance")
    if acoustic_path != acoustic_model.resolve():
        raise RuntimeError("r3 audit acoustic path differs from alignment contract")
    if (
        str(identity.get("mfa_dictionary_sha256", "")).lower()
        != str(dictionary.get("sha256", "")).lower()
        or str(identity.get("acoustic_model_sha256", "")).lower()
        != str(acoustic.get("sha256", "")).lower()
        or str(identity.get("g2p_model_sha256", "")).lower()
        != str(g2p.get("sha256", "")).lower()
    ):
        raise RuntimeError("r3 audit model identity differs")
    expected: dict[str, object] = {
        "pronunciation_release_id": str(
            identity.get("pronunciation_release_id", "")
        ).strip(),
        "pronunciation_contract_id": str(
            identity.get("pronunciation_contract_id", "")
        ).strip(),
        "mfa_dictionary_sha256": str(
            identity.get("mfa_dictionary_sha256", "")
        ).strip(),
        "alignment_contract_id": alignment_contract_id,
        "textgrid_schema": TEXTGRID_SCHEMA_VERSION,
        "source_db_sha256": sha256_file(source_db.resolve()),
        "alignment_origin": str(contract.get("alignment_origin", "")).strip(),
        "r3_full_realign": contract.get("r3_full_realign"),
        "safe_body_routing_contract_id": str(
            identity.get("safe_body_routing_contract_id", "")
        ).strip(),
        "followup_inventory_sha256": str(
            identity.get("followup_inventory_sha256", "")
        ).strip(),
    }
    if any(
        not expected[field]
        for field in R3_REQUIRED_MANIFEST_FIELDS
        if field != "r3_full_realign"
    ) or expected["r3_full_realign"] is not True:
        raise RuntimeError("r3 independent expected manifest fields are incomplete")
    return expected


def _scan_gzip_table(
    path: Path,
    *,
    table_name: str,
    expected_fields: list[str],
    expected_alignment_contract_id: str | None = None,
) -> dict[str, object]:
    """Scan a large table without retaining its interval rows in memory."""

    row_count = 0
    ids: set[str] = set()
    duplicate_keys = 0
    invalid_key_order = 0
    alignment_contract_mismatch = 0
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
            if (
                expected_alignment_contract_id is not None
                and str(row.get("alignment_contract_id", ""))
                != expected_alignment_contract_id
            ):
                alignment_contract_mismatch += 1
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
        "alignment_contract_mismatch": alignment_contract_mismatch,
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
    alignment_contract: Path | None = None,
    source_db: Path | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    lab_year = lab_root.resolve() / year
    tg_year = textgrid_root.resolve() / year
    r3_expected: dict[str, object] = {}
    r3_provenance_error = ""
    if alignment_contract is not None:
        try:
            if source_db is None:
                raise RuntimeError(
                    "alignment contract audit에는 source DB 경로가 필요함"
                )
            r3_expected = expected_r3_manifest_fields(
                alignment_contract_path=alignment_contract.resolve(),
                source_db=source_db.resolve(),
                acoustic_model=acoustic_model.resolve(),
                year=year,
                alignment_contract_id=alignment_contract_id,
            )
        except Exception as exc:
            r3_provenance_error = f"{type(exc).__name__}: {exc}"
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
    if not lab_paths:
        with atomic_text_writer(
            missing_csv_path.resolve(), encoding="utf-8-sig", newline=""
        ) as (stream, _temp):
            writer = csv.DictWriter(
                stream,
                fieldnames=["year", "utt_id", "reason"],
                lineterminator="\n",
            )
            writer.writeheader()
        report: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed",
            "year": year,
            "input_contract_id": input_contract_id,
            "alignment_contract_id": alignment_contract_id,
            "lab_root": str(lab_root.resolve()),
            "resolved_lab_year": str(lab_year),
            "textgrid_root": str(textgrid_root.resolve()),
            "configuration_error": "lab_year_empty",
            "hard_failure_counts": {"empty_lab_input": 1},
            "counts": {"active_lab_ids": 0},
            "inventories": {
                "missing_textgrid_ids": [],
                "extra_textgrid_ids": [],
                "invalid_textgrid_ids": [],
                "phone_outside_inventory": [],
            },
            "missing_csv": str(missing_csv_path.resolve()),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        atomic_write_json(report_path.resolve(), report)
        return report
    tg_paths: dict[str, Path] = {}
    duplicate_tg: set[str] = set()
    for path in iter_files(tg_year, ".TextGrid"):
        if path.stem in tg_paths:
            duplicate_tg.add(path.stem)
        tg_paths[path.stem] = path
    expected_tg_ids = set(lab_paths) - alignment_excluded
    missing = sorted(expected_tg_ids - set(tg_paths))
    extras = sorted(set(tg_paths) - expected_tg_ids)

    groups = model_group_lookup(load_acoustic_meta(acoustic_model))
    allowed_phones = set(groups)

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto
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
            phone_mapper=phone_mapper,
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
        if r3_provenance_error:
            raise RuntimeError(r3_provenance_error)
        if r3_expected:
            mismatches = {
                field: {
                    "expected": r3_expected[field],
                    "observed": manifest.get(field),
                }
                for field in R3_REQUIRED_MANIFEST_FIELDS
                if manifest.get(field) != r3_expected[field]
            }
            if mismatches:
                raise RuntimeError(
                    "r3 table manifest provenance mismatch: "
                    + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
                )
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
                expected_alignment_contract_id=alignment_contract_id,
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
                "alignment_contract_mismatch": 0,
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
        "utterance_table_contract_id_mismatch": int(
            utterance_scan["alignment_contract_mismatch"]
        ),
        "word_table_contract_id_mismatch": int(
            word_scan["alignment_contract_mismatch"]
        ),
        "phone_table_contract_id_mismatch": int(
            phone_scan["alignment_contract_mismatch"]
        ),
        "excluded_table_contract_id_mismatch": int(
            excluded_scan["alignment_contract_mismatch"]
        ),
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
        "required_r3_materialization_provenance": r3_expected,
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
    parser.add_argument("--alignment-contract", type=Path)
    parser.add_argument("--source-db", type=Path)
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
        alignment_contract=args.alignment_contract,
        source_db=args.source_db,
    )
    console_summary = {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "year": report.get("year"),
        "coverage_pct": report.get("coverage_pct"),
        "configuration_error": report.get("configuration_error"),
        "hard_failure_counts": report.get("hard_failure_counts", {}),
        "counts": report.get("counts", {}),
        "reason_counts": report.get("reason_counts", {}),
        "elapsed_seconds": report.get("elapsed_seconds"),
        "report": str(args.report.resolve()),
        "missing_csv": str(args.missing_csv.resolve()),
    }
    print(json.dumps(console_summary, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

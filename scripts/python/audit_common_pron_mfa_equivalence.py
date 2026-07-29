"""공통 MFA 사전이 2020·2021 phone 기준을 바꾸지 않는지 전수 감사한다.

2021은 보존된 완성 MFA SQLite의 word–pronunciation 집합과 직접 비교한다.
2020의 완성 DB는 보존돼 있지 않으므로, 독립 QC를 통과한 최종 4-tier
TextGrid 전부에서 각 word 구간의 phone열을 복원해 공통 사전 후보에 포함되는지
검사한다. archived 2020 partial DB도 그 안에 존재하는 발음 후보는 전수
비교하되, interval이 0인 부분본임을 보고서에 명시하고 전체 결과의 대체물로
오인하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from build_common_pron_mfa_lexicon import (
    SCHEMA_VERSION as LEXICON_SCHEMA_VERSION,
    acoustic_phone_inventory,
    clean,
    phone_inventory_contract,
    read_mfa_dictionary,
    read_vocabulary,
)
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEGACY_SCHEMA_VERSION = "common_pron_mfa_equivalence.v1"
DIFFERENCE_SCHEMA_VERSION = "common_pron_mfa_difference_inventory.v2"
CHECKPOINT_SCHEMA_VERSION = "common_pron_mfa_difference_checkpoint.v1"
EXPECTED_TIERS = ["words", "phones", "morphemes", "utterance"]
MISMATCH_FIELDS = (
    "baseline",
    "reason",
    "classification",
    "word",
    "baseline_phones",
    "common_phones",
    "occurrences",
    "example_utt_id",
)


def classify_mismatch(
    row: dict,
    *,
    base_dictionary_words: set[str],
) -> str:
    baseline_phones = set(str(row.get("baseline_phones", "")).split())
    common_phones = set(str(row.get("common_phones", "")).split())
    reason = str(row.get("reason", ""))
    word = str(row.get("word", ""))
    if "spn" in baseline_phones and "spn" not in common_phones:
        return "spn_defect_fixed"
    if reason in {
        "word_missing_from_common",
        "empty_phone_sequence",
        "tier_schema_or_duration",
    }:
        return "coverage_or_structure_difference"
    if word in base_dictionary_words:
        return "base_dictionary_word_difference"
    return "g2p_generated_difference"


def iter_textgrids(root: Path):
    for directory, subdirs, filenames in os.walk(root):
        subdirs.sort()
        filenames.sort()
        base = Path(directory)
        for filename in filenames:
            if filename.lower().endswith(".textgrid"):
                yield base / filename


def verify_g2p_contract(contract: dict) -> None:
    expected_core = {
        "num_pronunciations": 1,
        "strict_graphemes": True,
        "input_unit": "unique_surface_eojeol",
    }
    if any(
        contract.get(key) != value
        for key, value in expected_core.items()
    ):
        raise RuntimeError("동일 korean_mfa G2P 1-best 핵심 계약이 아님")
    no_path = contract.get("deterministic_no_path_policy")
    if no_path is not None and (
        no_path.get("same_frozen_model_required") is not True
        or no_path.get("researcher_approval_required") is not True
        or no_path.get("existing_model_pronunciations_replaced") != 0
        or no_path.get("final_spn_allowed") is not False
    ):
        raise RuntimeError("r2 deterministic no-path 안전 계약 불일치")


def load_release_manifest(path: Path) -> tuple[dict, Path]:
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != LEXICON_SCHEMA_VERSION
        or manifest.get("status") != "success"
    ):
        raise RuntimeError(f"공통 사전 manifest 계약 불일치: {path}")
    record = manifest["outputs"]["dictionary"]
    dictionary = Path(record["path"])
    if not dictionary.is_file():
        raise RuntimeError(f"공통 사전 없음: {dictionary}")
    actual = file_fingerprint(dictionary, with_sha256=True)
    if (
        actual["bytes"] != record["bytes"]
        or actual["sha256"] != record["sha256"]
    ):
        raise RuntimeError("공통 사전 fingerprint 불일치")
    if manifest["dictionary_contract"]["attested_dictionary_variants_added"] != 0:
        raise RuntimeError("우리말샘 등 사전 변이가 들어간 release는 동등성 감사 금지")
    if manifest["dictionary_contract"]["changes_phone_standard"]:
        raise RuntimeError("phone 기준 변경 release는 baseline 동등성 감사 금지")
    verify_g2p_contract(manifest.get("g2p_contract", {}))
    for role in ("base_dictionary", "g2p_model", "acoustic_model"):
        record = manifest.get("inputs", {}).get(role, {})
        model_path = Path(record.get("path", ""))
        if not model_path.is_file():
            raise RuntimeError(f"공통 사전 모델 원천 없음: {role}")
        actual = file_fingerprint(model_path, with_sha256=True)
        if (
            actual["bytes"] != record.get("bytes")
            or actual["sha256"] != record.get("sha256")
        ):
            raise RuntimeError(f"공통 사전 모델 fingerprint 불일치: {role}")
    acoustic = Path(manifest["inputs"]["acoustic_model"]["path"])
    inventory_contract = phone_inventory_contract(
        acoustic_phone_inventory(acoustic)
    )
    if inventory_contract != manifest.get("phone_inventory_contract"):
        raise RuntimeError("acoustic phone inventory 계약 불일치")
    return manifest, dictionary


def load_year_vocabulary(path: Path, year: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in read_vocabulary(path):
        count = int(row[f"count_{year}"])
        if count:
            result[row["token"]] = count
    if not result:
        raise RuntimeError(f"{year} vocabulary가 비어 있음")
    return result


def validate_2020_qc(report_path: Path, textgrid_root: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    expected_root = Path(report["textgrid_root"]).resolve()
    if (
        report.get("status") != "success"
        or str(report.get("year")) != "2020"
        or expected_root != textgrid_root.resolve()
        or int(report["counts"]["invalid_textgrids"]) != 0
        or int(report["counts"]["valid_textgrids"]) <= 0
    ):
        raise RuntimeError("2020 4-tier QC evidence 불일치")
    return report


def validate_2021_integrity(report_path: Path, database: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    expected = report["database"]
    if (
        report.get("status") != "success"
        or str(report.get("year")) != "2021"
        or report.get("result") != "ok"
        or Path(expected["path"]).resolve() != database.resolve()
        or int(expected["bytes"]) != database.stat().st_size
    ):
        raise RuntimeError("2021 DB integrity evidence 불일치")
    return report


def phones_for_word_interval(
    start: float,
    end: float,
    phone_intervals: list[tuple[float, float, str]],
    *,
    tolerance: float = 0.001,
) -> tuple[str, ...]:
    result = []
    for phone_start, phone_end, label in phone_intervals:
        if phone_end <= start + tolerance and phone_start < start - tolerance:
            continue
        if phone_start >= end - tolerance and phone_end > end + tolerance:
            break
        if (
            phone_start >= start - tolerance
            and phone_end <= end + tolerance
            and clean(label)
        ):
            result.append(clean(label))
    return tuple(result)


def inspect_2020_textgrid(
    path: Path,
    common: dict[str, set[tuple[str, ...]]],
) -> dict:
    duration, tiers = parse_mfa_textgrid(path)
    reasons: list[tuple[str, str, tuple[str, ...]]] = []
    matches = 0
    occurrences = 0
    if duration is None or list(tiers) != EXPECTED_TIERS:
        return {
            "utt_id": path.stem,
            "file_error": "tier_schema_or_duration",
            "matches": 0,
            "occurrences": 0,
            "mismatches": [],
        }
    phones = tiers["phones"]
    for start, end, label in tiers["words"]:
        word = clean(label)
        if not word:
            continue
        occurrences += 1
        sequence = phones_for_word_interval(start, end, phones)
        if not sequence:
            reasons.append(("empty_phone_sequence", word, sequence))
        elif word not in common:
            reasons.append(("word_missing_from_common", word, sequence))
        elif sequence not in common[word]:
            reasons.append(("phone_sequence_changed", word, sequence))
        else:
            matches += 1
    return {
        "utt_id": path.stem,
        "file_error": "",
        "matches": matches,
        "occurrences": occurrences,
        "mismatches": reasons,
    }


def audit_2020(
    *,
    textgrid_root: Path,
    qc_report_path: Path,
    common: dict[str, set[tuple[str, ...]]],
    workers: int,
    batch_size: int,
    checkpoint_path: Path | None = None,
    common_dictionary_sha256: str = "",
    checkpoint_every_batches: int = 10,
) -> tuple[dict, list[dict]]:
    if checkpoint_every_batches < 1:
        raise ValueError("checkpoint_every_batches must be at least 1")
    qc = validate_2020_qc(qc_report_path, textgrid_root)
    qc_record = file_fingerprint(qc_report_path, with_sha256=True)
    expected_files = int(qc["counts"]["valid_textgrids"])
    started = time.time()
    inventory = hashlib.sha256()
    counts: Counter = Counter()
    mismatches: Counter = Counter()
    examples: dict[tuple[str, str, tuple[str, ...]], str] = {}
    batch: list[Path] = []
    batch_relatives: list[str] = []
    last_completed_relative = ""
    expected_prefix_sha256 = ""
    resumed_from_files = 0

    checkpoint_contract = {
        "textgrid_root": str(textgrid_root.resolve()),
        "qc_report": {
            "bytes": int(qc_record["bytes"]),
            "sha256": str(qc_record["sha256"]).lower(),
        },
        "common_dictionary_sha256": common_dictionary_sha256.lower(),
        "expected_valid_textgrids": expected_files,
    }
    if checkpoint_path is not None and checkpoint_path.exists():
        checkpoint = json.loads(
            checkpoint_path.read_text(encoding="utf-8-sig")
        )
        if (
            checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
            or checkpoint.get("status") not in {"in_progress", "completed"}
            or checkpoint.get("contract") != checkpoint_contract
        ):
            raise RuntimeError("2020 difference checkpoint 계약 불일치")
        counts.update(
            {
                str(key): int(value)
                for key, value in checkpoint.get("counts", {}).items()
            }
        )
        for row in checkpoint.get("mismatches", []):
            key = (
                str(row["reason"]),
                str(row["word"]),
                tuple(str(value) for value in row["sequence"]),
            )
            mismatches[key] = int(row["count"])
            examples[key] = str(row["example_utt_id"])
        last_completed_relative = str(
            checkpoint.get("last_completed_relative", "")
        )
        expected_prefix_sha256 = str(
            checkpoint.get("prefix_inventory_sha256", "")
        )
        resumed_from_files = int(counts["textgrid_files"])
        if (
            not last_completed_relative
            or resumed_from_files <= 0
            or not expected_prefix_sha256
        ):
            raise RuntimeError("2020 difference checkpoint 진행상태 불완전")

    def checkpoint_mismatches() -> list[dict]:
        return [
            {
                "reason": reason,
                "word": word,
                "sequence": list(sequence),
                "count": count,
                "example_utt_id": examples[(reason, word, sequence)],
            }
            for (reason, word, sequence), count in sorted(
                mismatches.items(),
                key=lambda item: (
                    item[0][0],
                    item[0][1],
                    item[0][2],
                ),
            )
        ]

    def save_checkpoint(
        *,
        status: str,
        last_relative: str,
        prefix_sha256: str,
    ) -> None:
        if checkpoint_path is None:
            return
        atomic_write_json(
            checkpoint_path,
            {
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "status": status,
                "recorded_at": now_iso(),
                "contract": checkpoint_contract,
                "last_completed_relative": last_relative,
                "prefix_inventory_sha256": prefix_sha256,
                "counts": dict(sorted(counts.items())),
                "mismatches": checkpoint_mismatches(),
                "runtime": runtime_snapshot(PROJECT_ROOT),
            },
        )

    def consume(results):
        for result in results:
            counts["textgrid_files"] += 1
            counts["word_occurrences"] += result["occurrences"]
            counts["matched_word_occurrences"] += result["matches"]
            if result["file_error"]:
                counts["file_errors"] += 1
                key = (result["file_error"], "", ())
                mismatches[key] += 1
                examples.setdefault(key, result["utt_id"])
            for reason, word, sequence in result["mismatches"]:
                counts["mismatched_word_occurrences"] += 1
                counts[f"reason:{reason}"] += 1
                key = (reason, word, sequence)
                mismatches[key] += 1
                examples.setdefault(key, result["utt_id"])

    skipped_prefix_files = 0
    prefix_verified = not last_completed_relative

    def verify_resumed_prefix() -> None:
        nonlocal prefix_verified
        if prefix_verified:
            return
        if (
            skipped_prefix_files != resumed_from_files
            or inventory.hexdigest() != expected_prefix_sha256
        ):
            raise RuntimeError("2020 difference checkpoint 입력 prefix 변경")
        prefix_verified = True
        print(
            f"[2020] checkpoint 재개: {resumed_from_files:,}/"
            f"{expected_files:,} TextGrid",
            flush=True,
        )

    completed_batches = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for path in iter_textgrids(textgrid_root):
            stat = path.stat()
            relative = path.relative_to(textgrid_root).as_posix()
            inventory_record = (
                f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode(
                    "utf-8"
                )
            )
            if not prefix_verified:
                inventory.update(inventory_record)
                skipped_prefix_files += 1
                if relative == last_completed_relative:
                    verify_resumed_prefix()
                continue
            inventory.update(inventory_record)
            batch.append(path)
            batch_relatives.append(relative)
            if len(batch) >= batch_size:
                consume(
                    executor.map(
                        lambda item: inspect_2020_textgrid(item, common),
                        batch,
                    )
                )
                completed_batches += 1
                if completed_batches % checkpoint_every_batches == 0:
                    save_checkpoint(
                        status="in_progress",
                        last_relative=batch_relatives[-1],
                        prefix_sha256=inventory.hexdigest(),
                    )
                    print(
                        f"[2020] {counts['textgrid_files']:,}/"
                        f"{expected_files:,} TextGrid 검사",
                        flush=True,
                    )
                batch.clear()
                batch_relatives.clear()
        if batch:
            consume(
                executor.map(
                    lambda item: inspect_2020_textgrid(item, common),
                    batch,
                )
            )
            save_checkpoint(
                status="in_progress",
                last_relative=batch_relatives[-1],
                prefix_sha256=inventory.hexdigest(),
            )
        verify_resumed_prefix()

    passed = (
        counts["textgrid_files"] == expected_files
        and counts["file_errors"] == 0
        and counts["mismatched_word_occurrences"] == 0
        and counts["word_occurrences"] == counts["matched_word_occurrences"]
    )
    mismatch_rows = [
        {
            "baseline": "2020_textgrid",
            "reason": reason,
            "word": word,
            "baseline_phones": " ".join(sequence),
            "common_phones": " | ".join(
                " ".join(value) for value in sorted(common.get(word, set()))
            ),
            "occurrences": count,
            "example_utt_id": examples[(reason, word, sequence)],
        }
        for (reason, word, sequence), count in sorted(
            mismatches.items(),
            key=lambda item: (
                item[0][0],
                item[0][1],
                item[0][2],
            ),
        )
    ]
    if checkpoint_path is not None:
        save_checkpoint(
            status="completed",
            last_relative=last_completed_relative
            if resumed_from_files == expected_files
            else relative,
            prefix_sha256=inventory.hexdigest(),
        )
    return (
        {
            "status": "passed" if passed else "failed",
            "method": "all_valid_4tier_word_intervals_to_nested_phone_labels",
            "elapsed_seconds": round(time.time() - started, 3),
            "textgrid_root": str(textgrid_root.resolve()),
            "qc_report": file_fingerprint(qc_report_path, with_sha256=True),
            "inventory_path_size_mtime_sha256": inventory.hexdigest(),
            "counts": dict(sorted(counts.items())),
            "expected_valid_textgrids": expected_files,
            "unique_mismatch_rows": len(mismatch_rows),
            "checkpoint": (
                file_fingerprint(checkpoint_path, with_sha256=True)
                if checkpoint_path is not None
                else None
            ),
            "resumed_from_files": resumed_from_files,
        },
        mismatch_rows,
    )


def readonly_connection(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def sqlite_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def audit_2020_partial_db(
    *,
    database: Path,
    year_vocabulary: dict[str, int],
    common: dict[str, set[tuple[str, ...]]],
) -> tuple[dict, list[dict]]:
    """보존된 2020 부분 DB 내부의 모든 관측 발음 후보를 보조 감사한다."""

    started = time.time()
    baseline: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    connection = readonly_connection(database)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        table_counts = {
            table: sqlite_count(connection, table)
            for table in (
                "word",
                "pronunciation",
                "utterance",
                "word_interval",
                "phone_interval",
                "phone",
            )
        }
        query = """
            SELECT w.word, p.pronunciation
            FROM word w
            JOIN pronunciation p ON p.word_id = w.id
            WHERE w.word_type IN ('speech', 'oov')
            ORDER BY w.word, p.pronunciation
        """
        for word, pronunciation in connection.execute(query):
            word = clean(word)
            if word in year_vocabulary:
                baseline[word].add(tuple(clean(pronunciation).split()))
    finally:
        connection.close()

    mismatch_rows: list[dict] = []
    reason_counts: Counter = Counter()
    matched_words = 0
    for word in sorted(baseline):
        baseline_values = baseline[word]
        common_values = common.get(word, set())
        if not common_values:
            reason = "word_missing_from_common"
        elif baseline_values != common_values:
            reason = "pronunciation_set_changed"
        else:
            matched_words += 1
            continue
        reason_counts[reason] += 1
        mismatch_rows.append(
            {
                "baseline": "2020_partial_db",
                "reason": reason,
                "word": word,
                "baseline_phones": " | ".join(
                    " ".join(value) for value in sorted(baseline_values)
                ),
                "common_phones": " | ".join(
                    " ".join(value) for value in sorted(common_values)
                ),
                "occurrences": year_vocabulary[word],
                "example_utt_id": "",
            }
        )
    is_partial = (
        table_counts["word_interval"] == 0
        and table_counts["phone_interval"] == 0
        and table_counts["utterance"] > 0
    )
    passed = (
        quick_check == "ok"
        and is_partial
        and bool(baseline)
        and matched_words == len(baseline)
        and not mismatch_rows
    )
    return (
        {
            "status": "passed" if passed else "failed",
            "role": "auxiliary_partial_database_not_full_2020_baseline",
            "method": "all_pronunciation_candidates_present_in_partial_db",
            "scope_limitation": (
                "word_interval=0 and phone_interval=0; full output "
                "equivalence is established by baseline_2020_textgrid"
            ),
            "elapsed_seconds": round(time.time() - started, 3),
            "database": file_fingerprint(database, with_sha256=True),
            "quick_check": quick_check,
            "is_expected_partial_database": is_partial,
            "table_counts": table_counts,
            "counts": {
                "year_vocabulary_words": len(year_vocabulary),
                "partial_db_observed_words": len(baseline),
                "matched_words": matched_words,
                "mismatched_words": len(mismatch_rows),
                **{
                    f"reason:{reason}": count
                    for reason, count in sorted(reason_counts.items())
                },
            },
            "unique_mismatch_rows": len(mismatch_rows),
        },
        mismatch_rows,
    )


def audit_2021(
    *,
    database: Path,
    integrity_report_path: Path,
    year_vocabulary: dict[str, int],
    common: dict[str, set[tuple[str, ...]]],
) -> tuple[dict, list[dict]]:
    integrity = validate_2021_integrity(
        integrity_report_path, database
    )
    started = time.time()
    baseline: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    word_types: Counter = Counter()
    connection = readonly_connection(database)
    try:
        query = """
            SELECT w.word, w.word_type, p.pronunciation
            FROM word w
            JOIN pronunciation p ON p.word_id = w.id
            WHERE w.word_type IN ('speech', 'oov')
            ORDER BY w.word, p.pronunciation
        """
        for word, word_type, pronunciation in connection.execute(query):
            word = clean(word)
            word_types[clean(word_type)] += 1
            if word in year_vocabulary:
                baseline[word].add(tuple(clean(pronunciation).split()))
    finally:
        connection.close()

    mismatch_rows: list[dict] = []
    reason_counts: Counter = Counter()
    matched_words = 0
    matched_occurrences = 0
    for word in sorted(year_vocabulary):
        baseline_values = baseline.get(word, set())
        common_values = common.get(word, set())
        if not baseline_values:
            reason = "word_missing_from_2021_db"
        elif not common_values:
            reason = "word_missing_from_common"
        elif baseline_values != common_values:
            reason = "pronunciation_set_changed"
        else:
            matched_words += 1
            matched_occurrences += year_vocabulary[word]
            continue
        reason_counts[reason] += 1
        mismatch_rows.append(
            {
                "baseline": "2021_db",
                "reason": reason,
                "word": word,
                "baseline_phones": " | ".join(
                    " ".join(value) for value in sorted(baseline_values)
                ),
                "common_phones": " | ".join(
                    " ".join(value) for value in sorted(common_values)
                ),
                "occurrences": year_vocabulary[word],
                "example_utt_id": "",
            }
        )
    passed = matched_words == len(year_vocabulary) and not mismatch_rows
    return (
        {
            "status": "passed" if passed else "failed",
            "method": "all_2021_observed_words_exact_pronunciation_set",
            "elapsed_seconds": round(time.time() - started, 3),
            "database": {
                **file_fingerprint(database, with_sha256=True),
                "integrity_evidence_result": integrity["result"],
            },
            "integrity_report": file_fingerprint(
                integrity_report_path, with_sha256=True
            ),
            "counts": {
                "observed_vocabulary_words": len(year_vocabulary),
                "observed_vocabulary_occurrences": sum(
                    year_vocabulary.values()
                ),
                "matched_words": matched_words,
                "matched_occurrences": matched_occurrences,
                "mismatched_words": len(mismatch_rows),
                "baseline_pronunciation_rows_by_word_type": dict(
                    sorted(word_types.items())
                ),
                **{
                    f"reason:{reason}": count
                    for reason, count in sorted(reason_counts.items())
                },
            },
            "unique_mismatch_rows": len(mismatch_rows),
        },
        mismatch_rows,
    )


def write_mismatches(path: Path, rows: list[dict]) -> None:
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=MISMATCH_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def run_audit(
    *,
    common_manifest: Path,
    vocabulary: Path,
    textgrid_2020_root: Path,
    qc_2020_report: Path,
    partial_database_2020: Path,
    database_2021: Path,
    integrity_2021_report: Path,
    output_json: Path,
    output_csv: Path,
    workers: int,
    batch_size: int,
    mode: str = "difference-inventory",
    checkpoint_2020: Path | None = None,
    checkpoint_every_batches: int = 10,
) -> dict:
    if output_json.exists() or output_csv.exists():
        raise FileExistsError("기존 동등성 결과 덮어쓰기 금지")
    if mode not in {"difference-inventory", "strict-equivalence"}:
        raise ValueError(f"unsupported audit mode: {mode}")
    release, dictionary_path = load_release_manifest(common_manifest)
    _, common = read_mfa_dictionary(dictionary_path)
    _, base_prons = read_mfa_dictionary(
        Path(release["inputs"]["base_dictionary"]["path"])
    )
    vocab_2020 = load_year_vocabulary(vocabulary, "2020")
    vocab_2021 = load_year_vocabulary(vocabulary, "2021")
    result_2020, mismatch_2020 = audit_2020(
        textgrid_root=textgrid_2020_root,
        qc_report_path=qc_2020_report,
        common=common,
        workers=workers,
        batch_size=batch_size,
        checkpoint_path=checkpoint_2020,
        common_dictionary_sha256=str(
            release["outputs"]["dictionary"]["sha256"]
        ),
        checkpoint_every_batches=checkpoint_every_batches,
    )
    result_2020_partial_db, mismatch_2020_partial_db = (
        audit_2020_partial_db(
            database=partial_database_2020,
            year_vocabulary=vocab_2020,
            common=common,
        )
    )
    result_2021, mismatch_2021 = audit_2021(
        database=database_2021,
        integrity_report_path=integrity_2021_report,
        year_vocabulary=vocab_2021,
        common=common,
    )
    rows = (
        mismatch_2020
        + mismatch_2020_partial_db
        + mismatch_2021
    )
    for row in rows:
        row["classification"] = classify_mismatch(
            row,
            base_dictionary_words=set(base_prons),
        )
    write_mismatches(output_csv, rows)
    legacy_passed = (
        result_2020["status"] == "passed"
        and result_2020_partial_db["status"] == "passed"
        and result_2021["status"] == "passed"
        and not rows
    )
    counts_2020 = result_2020["counts"]
    counts_partial = result_2020_partial_db["counts"]
    counts_2021 = result_2021["counts"]
    inventory_complete = (
        counts_2020.get("textgrid_files", 0)
        == result_2020["expected_valid_textgrids"]
        and counts_2020.get("file_errors", 0) == 0
        and counts_2020.get("word_occurrences", 0) > 0
        and result_2020_partial_db.get("quick_check") == "ok"
        and result_2020_partial_db.get(
            "is_expected_partial_database"
        )
        and counts_partial.get("partial_db_observed_words", 0) > 0
        and counts_2021.get("observed_vocabulary_words", 0) > 0
    )
    if mode == "strict-equivalence":
        schema_version = LEGACY_SCHEMA_VERSION
        status = "passed" if legacy_passed else "failed"
        policy = "no_phone_standard_change"
    else:
        schema_version = DIFFERENCE_SCHEMA_VERSION
        status = (
            "differences_inventoried"
            if inventory_complete
            else "failed"
        )
        policy = "latest_jamo_r2_difference_inventory"
    classification_counts = Counter(
        str(row["classification"]) for row in rows
    )
    report = {
        "schema_version": schema_version,
        "status": status,
        "recorded_at": now_iso(),
        "mode": mode,
        "policy": policy,
        "method_contract": {
            "claim_scope": (
                "same phone symbol inventory and pronunciation-generation "
                "criterion; not identical acoustic realization or boundaries"
            ),
            "models": {
                role: release["inputs"][role]
                for role in (
                    "acoustic_model",
                    "base_dictionary",
                    "g2p_model",
                )
            },
            "g2p_contract": release["g2p_contract"],
            "phone_inventory_contract": release[
                "phone_inventory_contract"
            ],
            "dictionary_contract": release["dictionary_contract"],
        },
        "common_release": {
            "release_id": release["release_id"],
            "release_contract_id": release["release_contract_id"],
            "manifest": file_fingerprint(
                common_manifest, with_sha256=True
            ),
            "dictionary": file_fingerprint(
                dictionary_path, with_sha256=True
            ),
            "attested_dictionary_variants_added": 0,
        },
        "vocabulary": file_fingerprint(vocabulary, with_sha256=True),
        "baseline_2020": result_2020,
        "baseline_2020_partial_db_auxiliary": result_2020_partial_db,
        "baseline_2021": result_2021,
        "mismatches": {
            "rows": len(rows),
            "classifications": dict(
                sorted(classification_counts.items())
            ),
            "csv": file_fingerprint(output_csv, with_sha256=True),
        },
        "gate": {
            "difference_inventory_complete": inventory_complete,
            "legacy_exact_equivalence": legacy_passed,
            "allow_yearly_mfa": False,
            "researcher_approval_required": True,
            "legacy_mismatch_zero_is_not_an_adoption_gate": True,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_json, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common-manifest", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument(
        "--textgrid-2020-root", type=Path, required=True
    )
    parser.add_argument("--qc-2020-report", type=Path, required=True)
    parser.add_argument(
        "--partial-database-2020", type=Path, required=True
    )
    parser.add_argument("--database-2021", type=Path, required=True)
    parser.add_argument(
        "--integrity-2021-report", type=Path, required=True
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--checkpoint-2020", type=Path)
    parser.add_argument(
        "--checkpoint-every-batches", type=int, default=10
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument(
        "--mode",
        choices=("difference-inventory", "strict-equivalence"),
        default="difference-inventory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_audit(
        common_manifest=args.common_manifest.resolve(),
        vocabulary=args.vocabulary.resolve(),
        textgrid_2020_root=args.textgrid_2020_root.resolve(),
        qc_2020_report=args.qc_2020_report.resolve(),
        partial_database_2020=args.partial_database_2020.resolve(),
        database_2021=args.database_2021.resolve(),
        integrity_2021_report=args.integrity_2021_report.resolve(),
        output_json=args.output_json.resolve(),
        output_csv=args.output_csv.resolve(),
        workers=args.workers,
        batch_size=args.batch_size,
        mode=args.mode,
        checkpoint_2020=(
            args.checkpoint_2020.resolve()
            if args.checkpoint_2020 is not None
            else None
        ),
        checkpoint_every_batches=args.checkpoint_every_batches,
    )
    print(
        "[{0}] 2020={1}, 2021={2}, mismatch={3:,}".format(
            report["status"].upper(),
            report["baseline_2020"]["status"],
            report["baseline_2021"]["status"],
            report["mismatches"]["rows"],
        ),
        flush=True,
    )
    return (
        0
        if report["status"] in {
            "passed",
            "differences_inventoried",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())

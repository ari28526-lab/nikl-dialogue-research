"""Repair word labels that MFA attached to phone-only trailing silence.

The MFA SQLite database occasionally stores a terminal ``word_interval`` with
the final lexical ``word_id`` even though every linked phone is silence.  The
phone tier is already empty there, but the words tier repeats the last eojeol
across the remaining WAV duration.  This script accepts only candidates proven
by a failed companion utterance table, verifies the old and corrected six-tier
payloads, archives each derived TextGrid, and replaces only those files.

MFA DB, WAV, LAB, search CSV and interval times are read-only.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
from pathlib import Path
from typing import Mapping, Sequence

from export_mfa_db_research_6tier import (
    _db_inventory,
    _normalize_db_interval_rows,
    _session_intervals,
    load_alignment_contract,
    load_session_rows,
    open_readonly,
    placeholders,
)
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_write_json, file_fingerprint
import research_textgrid_v2 as textgrid_v2


SCHEMA_VERSION = "mfa_textgrid_phone_only_silence_word_repair.v1"


def fingerprint_matches(path: Path, expected: Mapping[str, object]) -> bool:
    if not path.is_file():
        return False
    observed = file_fingerprint(path, with_sha256=True)
    return (
        int(observed["bytes"]) == int(expected.get("bytes", -1))
        and str(observed["sha256"]) == str(expected.get("sha256", ""))
    )


def mismatch_rows(path: Path) -> list[dict[str, str]]:
    required = {
        "utt_id",
        "n_lab_words_expected",
        "n_mfa_words_aligned",
        "lab_word_count_match",
        "word_label_sequence_match",
    }
    rows: list[dict[str, str]] = []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"partial utterance table fields missing: {sorted(missing)}")
        for row in reader:
            if (
                str(row["lab_word_count_match"]).lower() != "true"
                or str(row["word_label_sequence_match"]).lower() != "true"
            ):
                rows.append(dict(row))
    if not rows:
        raise RuntimeError("partial companion table has no word mismatch")
    ids = [row["utt_id"].strip() for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RuntimeError("partial mismatch inventory has blank/duplicate utt_id")
    return rows


def build_tiers(
    *,
    duration: float,
    words: Sequence[tuple],
    phones: Sequence[tuple],
    search: Mapping[str, object],
    phone_mapper,
) -> list[tuple[str, list[tuple]]]:
    words, _wc, _wm = _normalize_db_interval_rows(words, duration)
    phones, _pc, _pm = _normalize_db_interval_rows(phones, duration)
    tiers, fallback = textgrid_v2.build_base_tier_data_from_intervals(
        duration=duration,
        words=[(row[1], row[2], row[3]) for row in words],
        phones=[(row[1], row[2], row[3]) for row in phones],
        row=search,
        phone_mapper=phone_mapper,
    )
    if fallback:
        raise RuntimeError("word span fallback is not repairable")
    return tiers


def tier_delta(old: Sequence[tuple], new: Sequence[tuple]) -> list[dict[str, object]]:
    if [row[0] for row in old] != [row[0] for row in new]:
        raise RuntimeError("old/new tier names differ")
    old_by_name = {str(name): intervals for name, intervals in old}
    new_by_name = {str(name): intervals for name, intervals in new}
    for tier_name in ("phones_mfa", "phoneme_r_auto"):
        if old_by_name[tier_name] != new_by_name[tier_name]:
            raise RuntimeError(f"repair would change phone-derived tier: {tier_name}")
    changes: list[dict[str, object]] = []
    old_words = old_by_name["words"]
    new_words = new_by_name["words"]
    if len(old_words) != len(new_words):
        raise RuntimeError("repair would change words interval count")
    for index, (before, after) in enumerate(zip(old_words, new_words), 1):
        if tuple(before[:2]) != tuple(after[:2]):
            raise RuntimeError("repair would change MFA word interval time")
        if str(before[2]) != str(after[2]):
            changes.append(
                {
                    "tier": "words",
                    "interval_index": index,
                    "begin": float(before[0]),
                    "end": float(before[1]),
                    "before": str(before[2]),
                    "after": str(after[2]),
                }
            )
    if (
        len(changes) != 1
        or changes[0]["tier"] != "words"
        or not str(changes[0]["before"]).strip()
        or str(changes[0]["after"]).strip()
    ):
        raise RuntimeError(f"repair is not one lexical-to-blank words change: {changes}")
    for tier_name in ("utterance", "utterance_orth_r", "morph_analysis_utt"):
        old_intervals = old_by_name[tier_name]
        new_intervals = new_by_name[tier_name]
        old_labels = [str(row[2]) for row in old_intervals if str(row[2])]
        new_labels = [str(row[2]) for row in new_intervals if str(row[2])]
        if old_labels != new_labels:
            raise RuntimeError(f"repair would change search-tier text: {tier_name}")
        if old_intervals != new_intervals:
            changes.append(
                {
                    "tier": tier_name,
                    "change": "label support follows corrected lexical word span",
                    "before_nonempty_spans": [
                        [float(row[0]), float(row[1]), str(row[2])]
                        for row in old_intervals
                        if str(row[2])
                    ],
                    "after_nonempty_spans": [
                        [float(row[0]), float(row[1]), str(row[2])]
                        for row in new_intervals
                        if str(row[2])
                    ],
                }
            )
    return changes


def repair(
    *,
    year: str,
    db_path: Path,
    search_root: Path,
    output_root: Path,
    acoustic_model: Path,
    alignment_contract: Path,
    utterance_table_partial: Path,
    archive_root: Path,
    manifest_path: Path,
    apply: bool,
) -> dict[str, object]:
    year = str(year)
    db_path = db_path.resolve()
    search_root = search_root.resolve()
    output_root = output_root.resolve()
    acoustic_model = acoustic_model.resolve()
    alignment_contract = alignment_contract.resolve()
    utterance_table_partial = utterance_table_partial.resolve()
    archive_root = archive_root.resolve()
    manifest_path = manifest_path.resolve()
    for path in (
        db_path,
        acoustic_model,
        alignment_contract,
        utterance_table_partial,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not (search_root / year).is_dir():
        raise FileNotFoundError(search_root / year)
    contract_id, contract = load_alignment_contract(alignment_contract, year)
    input_id = str(contract["lab_input_contract_id"])
    rows = mismatch_rows(utterance_table_partial)
    ids = [row["utt_id"].strip() for row in rows]
    row_by_id = {row["utt_id"].strip(): row for row in rows}
    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    def phone_mapper(phone: str) -> str:
        return classify_phone(phone, groups).phone_class_r_auto

    connection = open_readonly(db_path)
    try:
        word_labels, phone_labels = _db_inventory(connection)
        marks = placeholders(len(ids))
        db_rows = list(
            connection.execute(
                """
                SELECT u.id, f.name, f.relative_path, sf.duration
                FROM utterance u
                JOIN file f ON f.id=u.file_id
                JOIN sound_file sf ON sf.file_id=f.id
                WHERE f.name IN ("""
                + marks
                + ") ORDER BY f.name",
                ids,
            )
        )
        raw_words, phones_by_utt = _session_intervals(
            connection,
            [int(row[0]) for row in db_rows],
            word_labels,
            phone_labels,
            normalize_phone_only_silence_words=False,
        )
        fixed_words, _fixed_phones = _session_intervals(
            connection,
            [int(row[0]) for row in db_rows],
            word_labels,
            phone_labels,
        )
    finally:
        connection.close()
    by_name = {str(row[1]): row for row in db_rows}
    if set(by_name) != set(ids):
        raise RuntimeError("partial mismatch IDs and DB IDs differ")

    completed: dict[str, dict[str, object]] = {}
    if apply and manifest_path.is_file():
        prior = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if prior.get("status") in {"running", "failed"}:
            completed = {
                str(record["utt_id"]): record
                for record in prior.get("records") or []
            }
            for utt_id, record in completed.items():
                if (
                    utt_id not in set(ids)
                    or not fingerprint_matches(
                        Path(str(record["destination"])),
                        record["destination_after"],
                    )
                    or not fingerprint_matches(
                        Path(str(record["archive_path"])),
                        record["archive_fingerprint"],
                    )
                ):
                    raise RuntimeError(f"existing repair progress mismatch: {utt_id}")

    candidates: list[dict[str, object]] = []
    prepared: dict[str, dict[str, object]] = {}
    for utt_id in ids:
        source_row = row_by_id[utt_id]
        expected = int(source_row["n_lab_words_expected"])
        actual = int(source_row["n_mfa_words_aligned"])
        if actual != expected + 1:
            raise RuntimeError(f"mismatch is not exact +1 word: {utt_id}")
        if utt_id in completed:
            continue
        uid, _name, relative_path, duration = by_name[utt_id]
        uid = int(uid)
        duration = float(duration)
        session = str(relative_path or utt_id.split(".", 1)[0])
        search = load_session_rows(search_root, year, session)[utt_id]
        old_words = raw_words[uid]
        new_words = fixed_words[uid]
        changed_rows = [
            (before, after)
            for before, after in zip(old_words, new_words)
            if str(before[3]) != str(after[3])
        ]
        if len(old_words) != len(new_words) or len(changed_rows) != 1:
            raise RuntimeError(f"DB normalization scope is not one word row: {utt_id}")
        before_word, after_word = changed_rows[0]
        word_interval_id = int(before_word[0])
        linked = [
            row for row in phones_by_utt[uid] if row[4] == word_interval_id
        ]
        if (
            not linked
            or any(str(row[3]).strip() for row in linked)
            or not str(before_word[3]).strip()
            or str(after_word[3]).strip()
        ):
            raise RuntimeError(f"not a phone-only silence word interval: {utt_id}")
        if word_interval_id != int(old_words[-1][0]):
            raise RuntimeError(f"phone-only silence word is not terminal: {utt_id}")
        destination = output_root / year / session / f"{utt_id}.TextGrid"
        if not destination.is_file():
            raise FileNotFoundError(destination)
        old_tiers = build_tiers(
            duration=duration,
            words=old_words,
            phones=phones_by_utt[uid],
            search=search,
            phone_mapper=phone_mapper,
        )
        new_tiers = build_tiers(
            duration=duration,
            words=new_words,
            phones=phones_by_utt[uid],
            search=search,
            phone_mapper=phone_mapper,
        )
        changes = tier_delta(old_tiers, new_tiers)
        old_validation = textgrid_v2._validate_against_tier_data(
            destination, expected_duration=duration, expected_data=old_tiers
        )
        new_validation = textgrid_v2._validate_against_tier_data(
            destination, expected_duration=duration, expected_data=new_tiers
        )
        if not old_validation["valid"] or new_validation["valid"]:
            raise RuntimeError(f"existing TextGrid is not exact old policy: {utt_id}")
        archive_path = archive_root / destination.relative_to(output_root)
        candidate = {
            "utt_id": utt_id,
            "session": session,
            "word_interval_id": word_interval_id,
            "phone_interval_ids": [int(row[0]) for row in linked],
            "phone_labels_after_silence_normalization": [
                str(row[3]) for row in linked
            ],
            "tier_changes": changes,
            "destination": str(destination),
            "archive_path": str(archive_path),
            "destination_before": file_fingerprint(
                destination, with_sha256=True
            ),
            "old_policy_validation_passed": True,
            "replacement_validation_pending": True,
        }
        candidates.append(candidate)
        prepared[utt_id] = {
            "candidate": candidate,
            "duration": duration,
            "search": search,
            "words": new_words,
            "phones": phones_by_utt[uid],
            "new_tiers": new_tiers,
        }

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if not apply else "running",
        "year": year,
        "db_path": str(db_path),
        "search_master_root": str(search_root),
        "output_root": str(output_root),
        "archive_root": str(archive_root),
        "alignment_contract_id": contract_id,
        "input_contract_id": input_id,
        "source_companion_utterance_partial": file_fingerprint(
            utterance_table_partial, with_sha256=True
        ),
        "source_mismatch_count": len(ids),
        "candidate_count": len(ids),
        "candidates": candidates,
        "records": [completed[value] for value in ids if value in completed],
        "mutation_scope": (
            "derived partial TextGrid only: one words label becomes blank "
            "and utterance/search label support follows the corrected lexical "
            "span; MFA word/phone times, phone labels, DB, WAV, LAB and CSV "
            "unchanged"
        ),
    }
    atomic_write_json(manifest_path, manifest)
    if not apply:
        print(manifest_path)
        print(f"READY candidates={len(ids)}")
        return manifest

    try:
        for utt_id in ids:
            if utt_id in completed:
                continue
            item = prepared[utt_id]
            candidate = dict(item["candidate"])
            destination = Path(str(candidate["destination"]))
            archive_path = Path(str(candidate["archive_path"]))
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            if archive_path.exists():
                if not fingerprint_matches(
                    archive_path, candidate["destination_before"]
                ):
                    raise RuntimeError(f"conflicting archive: {archive_path}")
            else:
                partial_archive = archive_path.with_name(
                    archive_path.name + f".{os.getpid()}.partial"
                )
                shutil.copy2(destination, partial_archive)
                if not fingerprint_matches(
                    partial_archive, candidate["destination_before"]
                ):
                    raise RuntimeError(f"archive verification failed: {utt_id}")
                os.replace(partial_archive, archive_path)
            temporary = destination.with_name(
                destination.name + f".{os.getpid()}.repair.partial"
            )
            temporary.unlink(missing_ok=True)
            words, _wc, _wm = _normalize_db_interval_rows(
                item["words"], float(item["duration"])
            )
            phones, _pc, _pm = _normalize_db_interval_rows(
                item["phones"], float(item["duration"])
            )
            textgrid_v2.write_base_textgrid_from_intervals(
                temporary,
                duration=float(item["duration"]),
                words=[(row[1], row[2], row[3]) for row in words],
                phones=[(row[1], row[2], row[3]) for row in phones],
                row=item["search"],
                phone_mapper=phone_mapper,
            )
            replacement = file_fingerprint(temporary, with_sha256=True)
            validation = textgrid_v2._validate_against_tier_data(
                temporary,
                expected_duration=float(item["duration"]),
                expected_data=item["new_tiers"],
            )
            if not validation["valid"]:
                raise RuntimeError(f"replacement validation failed: {utt_id}")
            os.replace(temporary, destination)
            if not fingerprint_matches(destination, replacement):
                raise RuntimeError(f"replacement fingerprint failed: {utt_id}")
            candidate["archive_fingerprint"] = file_fingerprint(
                archive_path, with_sha256=True
            )
            candidate["destination_after"] = file_fingerprint(
                destination, with_sha256=True
            )
            candidate["replacement_validation_pending"] = False
            candidate["replacement_validation_passed"] = True
            completed[utt_id] = candidate
            manifest["records"] = [
                completed[value] for value in ids if value in completed
            ]
            atomic_write_json(manifest_path, manifest)
            print(f"repaired {len(completed)}/{len(ids)}: {utt_id}", flush=True)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(manifest_path, manifest)
        raise
    if set(completed) != set(ids):
        raise RuntimeError("repair did not cover exact mismatch inventory")
    manifest["status"] = "success"
    manifest["repaired_count"] = len(completed)
    manifest["repaired_ids"] = sorted(completed)
    manifest["records"] = [completed[value] for value in ids]
    manifest.pop("error", None)
    atomic_write_json(manifest_path, manifest)
    print(manifest_path)
    print(f"SUCCESS repaired={len(completed)}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--utterance-table-partial", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    repair(
        year=args.year,
        db_path=args.db,
        search_root=args.search_master_root,
        output_root=args.output_root,
        acoustic_model=args.acoustic_model,
        alignment_contract=args.alignment_contract,
        utterance_table_partial=args.utterance_table_partial,
        archive_root=args.archive_root,
        manifest_path=args.manifest,
        apply=args.apply,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

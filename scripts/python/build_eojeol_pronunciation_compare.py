"""Build an eojeol audit view across rule, dictionary, and MFA evidence.

This is a descriptive infrastructure table.  It never treats dictionary
independent-form pronunciations, contextual rule predictions, or forced-
alignment phones as interchangeable truth labels.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dictionary_pronunciation_registry import (  # noqa: E402
    atomic_gzip_text_writer,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "eojeol_pronunciation_compare.v2"
MASTER_REQUIRED = {
    "utt_id",
    "year",
    "session_id",
    "form",
    "canonical_tagged",
    "n_eojeol",
    "morph_eojeol_count_structured",
    "form_tagged_eojeol_count_equal",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_source",
    "pron_reference_status",
    "pron_reference_n_eojeol",
}
ORTH_EOJEOL_REQUIRED = {
    "utt_id",
    "year",
    "orth_eojeol_idx",
    "orth_eojeol_count",
    "orth_eojeol_form",
    "orth_eojeol_roman_v2",
    "linked_morph_eojeol_idx",
    "morph_link_status",
}
OCCURRENCE_REQUIRED = {
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_surface",
    "pos",
    "candidate_group_id",
    "dict_match_status",
    "preferred_source_tier",
    "pronunciation_resolution_status",
}
WORD_REQUIRED = {
    "utt_id",
    "year",
    "session_id",
    "reference_eojeol_idx",
    "reference_eojeol",
    "begin_seconds",
    "end_seconds",
    "word_mfa",
    "is_silence",
    "pron_mfa_ipa",
    "pron_mfa_r_auto",
    "mapping_status",
}
SUMMARY_REQUIRED = {
    "candidate_group_id",
    "preferred_source_tier",
    "pronunciation_resolution_status",
    "preferred_pron_hangul_json",
    "preferred_pron_roman_search_json",
}
OUTPUT_FIELDS = [
    "utt_id",
    "year",
    "eojeol_idx",
    "eojeol_count",
    "source_form_eojeol_count",
    "morph_analysis_eojeol_count",
    "form_tagged_eojeol_count_equal",
    "linked_morph_eojeol_idx",
    "morph_link_status",
    "eojeol_form",
    "eojeol_roman_v2",
    "morph_tagged",
    "morph_count_in_eojeol",
    "morph_surfaces_pos_json",
    "morph_candidate_group_ids_json",
    "morph_dict_match_statuses_json",
    "morph_dict_preferred_source_tiers_json",
    "morph_dict_resolution_statuses_json",
    "morph_dict_preferred_pron_hangul_json",
    "morph_dict_preferred_pron_roman_search_json",
    "dict_layer_status",
    "pron_rule_reference_form_eojeol",
    "pron_rule_hangul",
    "pron_rule_roman",
    "pron_rule_source",
    "pron_rule_utterance_status",
    "pron_rule_eojeol_map_status",
    "mfa_available",
    "mfa_word_interval_count",
    "mfa_begin_seconds",
    "mfa_end_seconds",
    "mfa_reference_eojeol",
    "mfa_word",
    "pron_mfa_ipa",
    "pron_mfa_r_auto",
    "mfa_mapping_status",
    "rule_mfa_roman_compare_status",
    "dictionary_comparison_scope",
    "single_morph_dict_rule_compare_status",
    "single_morph_dict_mfa_compare_status",
    "pron_audit_status",
    "pron_audit_issue_codes",
    "source_coordinate_contract",
]

csv.field_size_limit(20_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def json_compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def split_pipe(value: str | None) -> list[str]:
    text = clean(value)
    return [part.strip() for part in text.split("|")] if text else []


def roman_tokens(value: str | None) -> tuple[str, ...]:
    text = clean(value).replace("_", " ").replace("|", " ")
    return tuple(part for part in text.split() if part)


def compare_roman(left: str | None, right: str | None) -> str:
    left_tokens = roman_tokens(left)
    right_tokens = roman_tokens(right)
    if not left_tokens or not right_tokens:
        return "not_comparable_missing"
    if left_tokens == right_tokens:
        return "same_roman_token_sequence"
    return "different_roman_token_sequence"


def _load_success_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("status") != "success":
        raise RuntimeError(f"successful manifest required: {path}")
    return payload


def _manifest_file(path: Path, expected: dict, label: str) -> dict:
    actual = file_fingerprint(path, with_sha256=False)
    if int(actual["bytes"]) != int(expected.get("bytes", -1)):
        raise RuntimeError(f"{label} bytes differ from manifest")
    return {**actual, "sha256": expected.get("sha256", "")}


def grouped_reader(reader: csv.DictReader, label: str):
    for utt_id, rows in groupby(reader, key=lambda row: clean(row.get("utt_id"))):
        if not utt_id:
            raise RuntimeError(f"blank utt_id in {label}")
        yield utt_id, list(rows)


def session_grouped_reader(reader: csv.DictReader, label: str):
    previous = ""
    seen = False
    for session_id, rows in groupby(
        reader, key=lambda row: clean(row.get("session_id"))
    ):
        if not session_id:
            raise RuntimeError(f"blank session_id in {label}")
        if seen and session_id <= previous:
            raise RuntimeError(
                f"non-increasing session_id groups in {label}: {session_id}"
            )
        seen = True
        previous = session_id
        yield session_id, list(rows)


class GroupCursor:
    def __init__(self, groups, label: str):
        self.iterator = iter(groups)
        self.label = label
        self.current = next(self.iterator, None)

    def take_required(self, utt_id: str) -> list[dict[str, str]]:
        if self.current is None or self.current[0] != utt_id:
            observed = None if self.current is None else self.current[0]
            raise RuntimeError(
                f"{self.label} coverage/order mismatch: expected={utt_id}, observed={observed}"
            )
        rows = self.current[1]
        self.current = next(self.iterator, None)
        return rows

    def take_optional(self, utt_id: str) -> list[dict[str, str]]:
        if self.current is not None and self.current[0] < utt_id:
            raise RuntimeError(
                f"orphan {self.label} group before {utt_id}: {self.current[0]}"
            )
        if self.current is None or self.current[0] != utt_id:
            return []
        rows = self.current[1]
        self.current = next(self.iterator, None)
        return rows

    def require_exhausted(self) -> None:
        if self.current is not None:
            raise RuntimeError(f"unconsumed {self.label} group: {self.current[0]}")


def load_group_summaries(path: Path) -> dict[str, tuple[str, str, list, list]]:
    result: dict[str, tuple[str, str, list, list]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = SUMMARY_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"group summary fields missing: {sorted(missing)}")
        for row in reader:
            group_id = clean(row["candidate_group_id"])
            if not group_id or group_id in result:
                raise RuntimeError(f"blank/duplicate group summary: {group_id}")
            result[group_id] = (
                clean(row["preferred_source_tier"]),
                clean(row["pronunciation_resolution_status"]),
                json.loads(row["preferred_pron_hangul_json"]),
                json.loads(row["preferred_pron_roman_search_json"]),
            )
    if not result:
        raise RuntimeError("empty group summaries")
    return result


def indexed_rows(rows: list[dict[str, str]], field: str, label: str) -> dict[int, dict]:
    result: dict[int, dict] = {}
    for row in rows:
        raw = clean(row.get(field))
        if not raw:
            continue
        index = int(raw)
        if index in result:
            raise RuntimeError(f"duplicate {label} index={index}")
        result[index] = row
    return result


def build(args: argparse.Namespace) -> dict:
    year = str(args.year)
    master_path = args.utterance_master.resolve()
    orth_eojeol_path = args.orth_eojeol_tokens.resolve()
    year_manifest_path = args.year_manifest.resolve()
    occurrences_path = args.morph_occurrences.resolve()
    occurrence_manifest_path = args.occurrence_manifest.resolve()
    words_path = args.word_intervals.resolve()
    tables_manifest_path = args.tables_manifest.resolve()
    summaries_path = args.group_summaries.resolve()
    summary_manifest_path = args.group_summary_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_path = output_dir / "eojeol_pronunciation_compare.csv.gz"
    manifest_path = output_dir / "eojeol_pronunciation_compare_manifest.json"

    year_manifest = _load_success_manifest(year_manifest_path)
    occurrence_manifest = _load_success_manifest(occurrence_manifest_path)
    tables_manifest = _load_success_manifest(tables_manifest_path)
    summary_manifest = _load_success_manifest(summary_manifest_path)
    if any(
        str(payload.get("year")) != year
        for payload in (year_manifest, occurrence_manifest, tables_manifest)
    ):
        raise RuntimeError("input manifest year mismatch")
    inputs = {
        "utterance_master": _manifest_file(
            master_path, year_manifest["tables"]["master"], "utterance master"
        ),
        "orth_eojeol_tokens": _manifest_file(
            orth_eojeol_path,
            year_manifest["tables"]["orth_eojeol_tokens"],
            "orth eojeol tokens",
        ),
        "year_manifest": file_fingerprint(year_manifest_path, with_sha256=True),
        "morph_occurrences": _manifest_file(
            occurrences_path,
            occurrence_manifest["outputs"]["occurrences"],
            "morph occurrences",
        ),
        "occurrence_manifest": file_fingerprint(
            occurrence_manifest_path, with_sha256=True
        ),
        "word_intervals": _manifest_file(
            words_path, tables_manifest["tables"]["words"], "word intervals"
        ),
        "tables_manifest": file_fingerprint(tables_manifest_path, with_sha256=True),
        "group_summaries": _manifest_file(
            summaries_path,
            summary_manifest["outputs"]["summaries"],
            "group summaries",
        ),
        "group_summary_manifest": file_fingerprint(
            summary_manifest_path, with_sha256=True
        ),
    }
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "year": year,
        "expected_eojeol_rows": int(
            year_manifest["tables"]["orth_eojeol_tokens"]["rows"]
        ),
        "inputs": inputs,
        "outputs": {"compare": str(output_path), "manifest": str(manifest_path)},
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError(f"existing compare output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    group_summaries = load_group_summaries(summaries_path)
    counts: Counter = Counter()
    with gzip.open(master_path, "rt", encoding="utf-8-sig", newline="") as master_stream, \
            gzip.open(orth_eojeol_path, "rt", encoding="utf-8-sig", newline="") as eojeol_stream, \
            gzip.open(occurrences_path, "rt", encoding="utf-8-sig", newline="") as occurrence_stream, \
            gzip.open(words_path, "rt", encoding="utf-8-sig", newline="") as word_stream, \
            atomic_gzip_text_writer(output_path) as destination:
        master_reader = csv.DictReader(master_stream)
        eojeol_reader = csv.DictReader(eojeol_stream)
        occurrence_reader = csv.DictReader(occurrence_stream)
        word_reader = csv.DictReader(word_stream)
        for label, reader, required in (
            ("master", master_reader, MASTER_REQUIRED),
            ("orth eojeol", eojeol_reader, ORTH_EOJEOL_REQUIRED),
            ("occurrence", occurrence_reader, OCCURRENCE_REQUIRED),
            ("word", word_reader, WORD_REQUIRED),
        ):
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(f"{label} fields missing: {sorted(missing)}")
        eojeol_cursor = GroupCursor(grouped_reader(eojeol_reader, "eojeol"), "eojeol")
        occurrence_cursor = GroupCursor(
            grouped_reader(occurrence_reader, "occurrence"), "occurrence"
        )
        word_cursor = GroupCursor(
            session_grouped_reader(word_reader, "word"), "word session"
        )
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()

        active_word_session = ""
        active_words_by_utt: dict[str, list[dict[str, str]]] = {}
        for master_number, master in enumerate(master_reader, 1):
            utt_id = clean(master["utt_id"])
            if not utt_id:
                raise RuntimeError("blank master utt_id")
            if clean(master["year"]) != year:
                raise RuntimeError(f"master year mismatch: {utt_id}")
            eojeol_rows = eojeol_cursor.take_required(utt_id)
            occurrence_rows = occurrence_cursor.take_required(utt_id)
            session_id = clean(master["session_id"])
            if session_id != active_word_session:
                if active_words_by_utt:
                    raise RuntimeError(
                        "unconsumed MFA word utterances in session "
                        f"{active_word_session}: {sorted(active_words_by_utt)[:3]}"
                    )
                session_rows = word_cursor.take_optional(session_id)
                active_words_by_utt = {}
                for word_row in session_rows:
                    word_utt_id = clean(word_row["utt_id"])
                    active_words_by_utt.setdefault(word_utt_id, []).append(word_row)
                active_word_session = session_id
            word_rows = active_words_by_utt.pop(utt_id, [])
            eoj_by_index = indexed_rows(
                eojeol_rows, "orth_eojeol_idx", "orth eojeol"
            )
            source_eoj_count = int(clean(master["n_eojeol"]))
            morph_eoj_count = int(
                clean(master["morph_eojeol_count_structured"])
            )
            expected_eoj_count = source_eoj_count
            if sorted(eoj_by_index) != list(range(1, source_eoj_count + 1)):
                raise RuntimeError(f"orth eojeol coverage mismatch: {utt_id}")
            if any(
                int(clean(row["orth_eojeol_count"])) != source_eoj_count
                for row in eojeol_rows
            ):
                raise RuntimeError(f"orth eojeol count field mismatch: {utt_id}")
            morph_by_eoj: dict[int, list[dict]] = {}
            for row in occurrence_rows:
                morph_by_eoj.setdefault(int(row["eojeol_idx"]), []).append(row)
            if sorted(morph_by_eoj) != list(range(1, morph_eoj_count + 1)):
                raise RuntimeError(f"morph occurrence coverage mismatch: {utt_id}")
            for index, rows in morph_by_eoj.items():
                rows.sort(key=lambda row: int(row["morph_idx_in_eojeol"]))
                expected = list(range(1, len(rows) + 1))
                observed = [int(row["morph_idx_in_eojeol"]) for row in rows]
                if observed != expected:
                    raise RuntimeError(f"morph index mismatch: {utt_id}/{index}")

            reference_count = int(clean(master["pron_reference_n_eojeol"]) or 0)
            reference_forms = clean(master["pron_reference_form"]).split()
            rule_hangul = clean(master["pron_reference_hangul"]).split()
            rule_roman = split_pipe(master["pron_reference_roman"])
            source_reference_index_equal = (
                source_eoj_count == reference_count
                and len(reference_forms) == expected_eoj_count
            )
            rule_map_ok = (
                source_reference_index_equal
                and len(rule_hangul) == expected_eoj_count
                and len(rule_roman) == expected_eoj_count
            )
            lexical_words = [
                row
                for row in word_rows
                if clean(row["reference_eojeol_idx"])
                and clean(row["is_silence"]).lower() != "true"
            ]
            words_by_ref: dict[int, list[dict]] = {}
            for row in lexical_words:
                words_by_ref.setdefault(int(row["reference_eojeol_idx"]), []).append(row)

            for index in range(1, expected_eoj_count + 1):
                eojeol = eoj_by_index[index]
                linked_morph_raw = clean(eojeol["linked_morph_eojeol_idx"])
                linked_morph_index = (
                    int(linked_morph_raw) if linked_morph_raw else None
                )
                morphs = (
                    morph_by_eoj[linked_morph_index]
                    if linked_morph_index is not None
                    else []
                )
                group_ids: list[str | None] = []
                match_statuses: list[str] = []
                source_tiers: list[str | None] = []
                resolutions: list[str | None] = []
                dict_hangul: list[list[str]] = []
                dict_roman: list[list[str]] = []
                issues: set[str] = set()
                if linked_morph_index is None:
                    issues.add("dictionary_morph_coordinate_not_linked")
                for morph in morphs:
                    group_id = clean(morph["candidate_group_id"])
                    status = clean(morph["dict_match_status"])
                    group_ids.append(group_id or None)
                    match_statuses.append(status)
                    if group_id:
                        summary = group_summaries.get(group_id)
                        if summary is None:
                            raise RuntimeError(f"unknown group ID in occurrence: {group_id}")
                        source_tiers.append(summary[0])
                        resolutions.append(summary[1])
                        dict_hangul.append(summary[2])
                        dict_roman.append(summary[3])
                        if summary[0] == "legacy_fallback_only":
                            issues.add("dictionary_legacy_fallback_only")
                        if summary[1] == "multiple_pronunciations_unresolved":
                            issues.add("dictionary_multiple_pronunciations")
                    else:
                        source_tiers.append(None)
                        resolutions.append(None)
                        dict_hangul.append([])
                        dict_roman.append([])
                        if status not in (
                            "not_applicable_punctuation",
                            "not_applicable_nonstandard_surface",
                        ):
                            issues.add("dictionary_no_exact_surface_pos_link")

                if not morphs:
                    dict_layer_status = "morph_coordinate_not_linked"
                elif all(group_ids):
                    dict_layer_status = (
                        "all_morphs_linked_with_ambiguity"
                        if "dictionary_multiple_pronunciations" in issues
                        else "all_morphs_linked"
                    )
                elif any(group_ids):
                    dict_layer_status = "partially_linked"
                else:
                    dict_layer_status = "not_linked_or_not_applicable"

                if rule_map_ok:
                    rule_form = reference_forms[index - 1]
                    rule_h = rule_hangul[index - 1]
                    rule_r = rule_roman[index - 1]
                    rule_map_status = "mapped_by_equal_source_reference_count"
                else:
                    rule_form = rule_h = rule_r = ""
                    rule_map_status = "not_mapped_count_mismatch"
                    issues.add("rule_reference_eojeol_count_mismatch")
                if clean(master["pron_reference_status"]) == "unresolved_symbol":
                    issues.add("rule_reference_unresolved_symbol")

                mapped_words = (
                    words_by_ref.get(index, []) if source_reference_index_equal else []
                )
                if not source_reference_index_equal and word_rows:
                    issues.add("mfa_source_reference_index_not_equal")
                if not mapped_words:
                    mfa_available = "false"
                    mfa_begin = mfa_end = mfa_ref = mfa_word = ""
                    mfa_ipa = mfa_roman = mfa_mapping = ""
                    issues.add("mfa_eojeol_not_available")
                else:
                    mfa_available = "true"
                    if len(mapped_words) > 1:
                        issues.add("mfa_multiple_word_intervals_for_eojeol")
                    mfa_begin = min(float(row["begin_seconds"]) for row in mapped_words)
                    mfa_end = max(float(row["end_seconds"]) for row in mapped_words)
                    mfa_ref = " || ".join(clean(row["reference_eojeol"]) for row in mapped_words)
                    mfa_word = " || ".join(clean(row["word_mfa"]) for row in mapped_words)
                    mfa_ipa = " || ".join(clean(row["pron_mfa_ipa"]) for row in mapped_words)
                    mfa_roman = " || ".join(clean(row["pron_mfa_r_auto"]) for row in mapped_words)
                    mfa_mapping = " || ".join(clean(row["mapping_status"]) for row in mapped_words)

                rule_mfa = compare_roman(rule_r, mfa_roman)
                if rule_mfa == "different_roman_token_sequence":
                    issues.add("rule_mfa_roman_sequence_differs")
                if len(morphs) == 1 and group_ids[0] and len(dict_roman[0]) == 1:
                    dictionary_scope = "single_morph_single_preferred_pronunciation"
                    dict_rule = compare_roman(dict_roman[0][0], rule_r)
                    dict_mfa = compare_roman(dict_roman[0][0], mfa_roman)
                else:
                    dictionary_scope = "not_compared_multi_morph_or_ambiguous"
                    dict_rule = dict_mfa = "not_compared"

                if any(code.startswith("mfa_") and code != "mfa_multiple_word_intervals_for_eojeol" for code in issues) or "rule_reference_eojeol_count_mismatch" in issues:
                    audit_status = "incomplete_layer_mapping"
                elif "dictionary_multiple_pronunciations" in issues:
                    audit_status = "complete_dictionary_ambiguity_for_review"
                elif rule_mfa == "different_roman_token_sequence":
                    audit_status = "complete_rule_mfa_difference_for_review"
                elif issues:
                    audit_status = "complete_with_reference_warnings"
                else:
                    audit_status = "complete_no_flagged_difference"

                writer.writerow(
                    {
                        "utt_id": utt_id,
                        "year": year,
                        "eojeol_idx": index,
                        "eojeol_count": expected_eoj_count,
                        "source_form_eojeol_count": source_eoj_count,
                        "morph_analysis_eojeol_count": morph_eoj_count,
                        "form_tagged_eojeol_count_equal": clean(
                            master["form_tagged_eojeol_count_equal"]
                        ).lower(),
                        "linked_morph_eojeol_idx": linked_morph_raw,
                        "morph_link_status": clean(
                            eojeol["morph_link_status"]
                        ),
                        "eojeol_form": clean(eojeol["orth_eojeol_form"]),
                        "eojeol_roman_v2": clean(
                            eojeol["orth_eojeol_roman_v2"]
                        ),
                        "morph_tagged": " + ".join(
                            f"{clean(row['morph_surface'])}/{clean(row['pos'])}"
                            for row in morphs
                        ),
                        "morph_count_in_eojeol": len(morphs),
                        "morph_surfaces_pos_json": json_compact(
                            [f"{clean(row['morph_surface'])}/{clean(row['pos'])}" for row in morphs]
                        ),
                        "morph_candidate_group_ids_json": json_compact(group_ids),
                        "morph_dict_match_statuses_json": json_compact(match_statuses),
                        "morph_dict_preferred_source_tiers_json": json_compact(source_tiers),
                        "morph_dict_resolution_statuses_json": json_compact(resolutions),
                        "morph_dict_preferred_pron_hangul_json": json_compact(dict_hangul),
                        "morph_dict_preferred_pron_roman_search_json": json_compact(dict_roman),
                        "dict_layer_status": dict_layer_status,
                        "pron_rule_reference_form_eojeol": rule_form,
                        "pron_rule_hangul": rule_h,
                        "pron_rule_roman": rule_r,
                        "pron_rule_source": clean(master["pron_reference_source"]),
                        "pron_rule_utterance_status": clean(master["pron_reference_status"]),
                        "pron_rule_eojeol_map_status": rule_map_status,
                        "mfa_available": mfa_available,
                        "mfa_word_interval_count": len(mapped_words),
                        "mfa_begin_seconds": f"{mfa_begin:.6f}" if mfa_begin != "" else "",
                        "mfa_end_seconds": f"{mfa_end:.6f}" if mfa_end != "" else "",
                        "mfa_reference_eojeol": mfa_ref,
                        "mfa_word": mfa_word,
                        "pron_mfa_ipa": mfa_ipa,
                        "pron_mfa_r_auto": mfa_roman,
                        "mfa_mapping_status": mfa_mapping,
                        "rule_mfa_roman_compare_status": rule_mfa,
                        "dictionary_comparison_scope": dictionary_scope,
                        "single_morph_dict_rule_compare_status": dict_rule,
                        "single_morph_dict_mfa_compare_status": dict_mfa,
                        "pron_audit_status": audit_status,
                        "pron_audit_issue_codes": " | ".join(sorted(issues)),
                        "source_coordinate_contract": "orth_eojeol_idx; rule/MFA use source-reference equal-count mapping; dictionary morph candidates use explicit linked_morph_eojeol_idx only",
                    }
                )
                counts["eojeol_rows"] += 1
                counts[f"audit_{audit_status}"] += 1
                counts[f"dict_{dict_layer_status}"] += 1
                counts[f"rule_mfa_{rule_mfa}"] += 1
                for issue in issues:
                    counts[f"issue_{issue}"] += 1
            counts["utterances"] += 1
            if args.max_utterances is not None and counts["utterances"] >= args.max_utterances:
                break
            if args.progress_every and master_number % args.progress_every == 0:
                print(
                    f"[{year}] compare {master_number:,} utterances · "
                    f"{counts['eojeol_rows']:,} eojeol rows",
                    flush=True,
                )

        full_scope = args.max_utterances is None
        if full_scope:
            if active_words_by_utt:
                raise RuntimeError(
                    "unconsumed MFA word utterances in final session "
                    f"{active_word_session}: {sorted(active_words_by_utt)[:3]}"
                )
            eojeol_cursor.require_exhausted()
            occurrence_cursor.require_exhausted()
            word_cursor.require_exhausted()

    full_scope = args.max_utterances is None
    expected_rows = int(
        year_manifest["tables"]["orth_eojeol_tokens"]["rows"]
    )
    if full_scope and counts["eojeol_rows"] != expected_rows:
        raise RuntimeError(
            f"eojeol compare coverage mismatch: {counts['eojeol_rows']} != {expected_rows}"
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "eojeol_pronunciation_compare",
        "status": "success",
        "recorded_at": now_iso(),
        "year": year,
        "scope": "full_year" if full_scope else "bounded_pilot",
        "coverage_complete": full_scope,
        "policy": {
            "dictionary": "independent-form candidates; no sense/pronunciation auto-selection",
            "rule": "contextual rule-reference fields from frozen morph_search master",
            "mfa": "forced-alignment phone sequence; not actual realization judgment",
            "source_reference_mapping": "only equal eojeol-count coordinate domains are index-mapped",
            "mfa_dictionary_activation": False,
        },
        "counts": dict(sorted(counts.items())),
        "inputs": inputs,
        "outputs": {"compare": file_fingerprint(output_path, with_sha256=True)},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] {year} eojeol pronunciation compare: "
        f"{counts['eojeol_rows']:,} rows",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--utterance-master", type=Path, required=True)
    result.add_argument("--orth-eojeol-tokens", type=Path, required=True)
    result.add_argument("--year-manifest", type=Path, required=True)
    result.add_argument("--morph-occurrences", type=Path, required=True)
    result.add_argument("--occurrence-manifest", type=Path, required=True)
    result.add_argument("--word-intervals", type=Path, required=True)
    result.add_argument("--tables-manifest", type=Path, required=True)
    result.add_argument("--group-summaries", type=Path, required=True)
    result.add_argument("--group-summary-manifest", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--max-utterances", type=int)
    result.add_argument("--progress-every", type=int, default=100_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.max_utterances is not None and args.max_utterances <= 0:
        raise ValueError("--max-utterances must be positive")
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

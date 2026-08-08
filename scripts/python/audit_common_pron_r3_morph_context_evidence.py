"""Independently audit Stage 16 morphology/POS evidence linkage."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_r3_morph_context_evidence import (  # noqa: E402
    MORPH_FIELDS,
    SCHEMA_VERSION,
    STATUS,
    SUMMARY_FIELDS,
    TOKEN_FIELDS,
)
from build_common_pron_r3_unanimous_phone_change_audit import TOKEN_AUDIT_FIELDS  # noqa: E402
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file  # noqa: E402


AUDIT_SCHEMA = "common_pron_r3_morph_context_evidence_independent_audit.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def audit(manifest_path: Path, output: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
        raise RuntimeError("Stage 16 manifest identity differs")
    scope = manifest.get("scope", {})
    if (
        scope.get("bareun_analysis_is_automatic_not_gold") is not True
        or scope.get("readiness_v3_hold_preserved") is not True
        or any(scope.get(key) is not False for key in (
            "candidate_generation_performed", "canonical_selection_performed",
            "adoption_performed", "annual_mfa_started", "textgrids_modified",
            "source_files_modified", "standard_pronunciation_claimed",
            "actual_realization_claimed",
        ))
    ):
        raise RuntimeError("Stage 16 scope invariants differ")

    stage15_path = verify(manifest["inputs"]["stage15_token_inventory"], label="Stage 15 tokens")
    token_path = verify(manifest["outputs"]["token_evidence_coverage"], label="token coverage")
    morph_path = verify(manifest["outputs"]["morph_signatures"], label="morph signatures")
    summary_path = verify(manifest["outputs"]["route_summary"], label="route summary")
    meta_path = verify(manifest["inputs"]["search_master_build_meta"], label="search meta")
    for key in ("stage15_manifest", "readiness_v3_manifest", "policy_contract", "readiness_v3"):
        verify(manifest["inputs"][key], label=key)

    targets: dict[str, dict[str, str]] = {}
    with gzip.open(stage15_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TOKEN_AUDIT_FIELDS:
            raise RuntimeError("Stage 15 token fields differ")
        for row in reader:
            targets[row["token"]] = row
    if len(targets) != 4453:
        raise RuntimeError("Stage 16 independent target count differs")

    search_root = Path(str(manifest["inputs"]["search_master_inventory"]["root"])).resolve()
    files = [path for year in YEARS for path in sorted((search_root / year).glob("*.csv"))]
    if len(files) != int(manifest["counts"]["search_master_csv_files"]):
        raise RuntimeError("Stage 16 source file count differs")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    expected_utterances = int(meta["totals"]["n_utt"])

    surface_year: dict[str, Counter[str]] = defaultdict(Counter)
    morph_counts: dict[str, Counter[str]] = defaultdict(Counter)
    morph_year: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    pred_hangul: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    pred_roman: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    utterances = 0
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                utterances += 1
                forms = clean(row["form"]).split()
                tagged = clean(row["tagged"]).split()
                hangul = clean(row["pron_pred_hangul"]).split()
                roman = [part.strip() for part in clean(row["pron_pred_roman"]).split("|")] if clean(row["pron_pred_roman"]) else []
                expected = int(clean(row["n_eojeol"]) or 0)
                if len(forms) != expected:
                    raise RuntimeError(f"independent form alignment differs: {row['utt_id']}")
                tagged_aligned = len(tagged) == expected
                if hangul and len(hangul) != expected:
                    raise RuntimeError(f"independent predicted Hangul differs: {row['utt_id']}")
                if roman and len(roman) != expected:
                    raise RuntimeError(f"independent predicted Roman differs: {row['utt_id']}")
                year = clean(row["year"])
                for index, token in enumerate(forms):
                    if token not in targets:
                        continue
                    surface_year[token][year] += 1
                    if not tagged_aligned:
                        continue
                    signature = tagged[index]
                    morph_counts[token][signature] += 1
                    morph_year[(token, signature)][year] += 1
                    if hangul:
                        pred_hangul[(token, signature)][hangul[index]] += 1
                    if roman:
                        pred_roman[(token, signature)][roman[index]] += 1
    if utterances != expected_utterances:
        raise RuntimeError("Stage 16 independent utterance count differs")

    expected_morph_keys = {
        (token, signature) for token, signatures in morph_counts.items() for signature in signatures
    }
    seen_morph: set[tuple[str, str]] = set()
    with gzip.open(morph_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != MORPH_FIELDS:
            raise RuntimeError("Stage 16 morph fields differ")
        for row in reader:
            key = (row["token"], row["tagged_eojeol"])
            if key not in expected_morph_keys or key in seen_morph:
                raise RuntimeError(f"Stage 16 morph identity differs: {key}")
            seen_morph.add(key)
            token, signature = key
            if (
                int(row["total_occurrences"]) != morph_counts[token][signature]
                or any(int(row[f"count_{year}"]) != morph_year[key][year] for year in YEARS)
                or json.loads(row["predicted_hangul_counts_json"]) != dict(sorted(pred_hangul[key].items()))
                or json.loads(row["predicted_roman_counts_json"]) != dict(sorted(pred_roman[key].items()))
                or row["bareun_analysis_is_gold"] != "false"
                or row["actual_realization_claimed"] != "false"
            ):
                raise RuntimeError(f"Stage 16 morph row differs: {key}")
    if seen_morph != expected_morph_keys:
        raise RuntimeError("Stage 16 morph coverage differs")

    seen_tokens: set[str] = set()
    link_status: Counter[str] = Counter()
    morph_link_status: Counter[str] = Counter()
    morph_context_status: Counter[str] = Counter()
    linked_total = morph_linked_total = 0
    with gzip.open(token_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TOKEN_FIELDS:
            raise RuntimeError("Stage 16 token output fields differ")
        for row in reader:
            token = row["token"]
            source = targets.get(token)
            if source is None or token in seen_tokens:
                raise RuntimeError(f"Stage 16 token identity differs: {token}")
            seen_tokens.add(token)
            expected = int(source["total_occurrences"])
            surface = sum(surface_year[token].values())
            morph = sum(morph_counts[token].values())
            expected_link = "full_exact" if surface == expected else ("partial" if surface else "unlinked")
            expected_morph_link = "full_exact" if morph == expected else ("partial" if morph else "unlinked")
            expected_context = "unlinked" if not morph_counts[token] else ("single_signature" if len(morph_counts[token]) == 1 else "multiple_signatures")
            if (
                int(row["linked_search_master_occurrences"]) != surface
                or int(row["occurrence_delta"]) != surface - expected
                or row["occurrence_link_status"] != expected_link
                or int(row["morph_linked_occurrences"]) != morph
                or int(row["morph_unlinked_occurrences"]) != surface - morph
                or row["morph_link_status"] != expected_morph_link
                or int(row["morph_signature_count"]) != len(morph_counts[token])
                or row["morph_context_status"] != expected_context
                or row["automatic_candidate_eligible"] != "false"
                or row["planning_zero_fallback_hold_preserved"] != "true"
                or row["researcher_review_required_now"] != "false"
            ):
                raise RuntimeError(f"Stage 16 token row differs: {token}")
            seen_tokens.add(token)
            linked_total += surface
            morph_linked_total += morph
            link_status[expected_link] += 1
            morph_link_status[expected_morph_link] += 1
            morph_context_status[expected_context] += 1
    if seen_tokens != set(targets):
        raise RuntimeError("Stage 16 token coverage differs")

    with summary_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != SUMMARY_FIELDS:
            raise RuntimeError("Stage 16 summary fields differ")
        if any(row["automatic_candidate_types"] != "0" for row in reader):
            raise RuntimeError("Stage 16 summary implies candidate")

    counts = manifest["counts"]
    recomputed = {
        "search_master_csv_files": len(files),
        "search_master_utterances": utterances,
        "target_types": len(targets),
        "expected_target_occurrences": sum(int(row["total_occurrences"]) for row in targets.values()),
        "linked_target_occurrences": linked_total,
        "morph_linked_target_occurrences": morph_linked_total,
        "occurrence_link_status_types": dict(sorted(link_status.items())),
        "morph_link_status_types": dict(sorted(morph_link_status.items())),
        "morph_context_status_types": dict(sorted(morph_context_status.items())),
        "morph_signature_rows": len(expected_morph_keys),
        "dictionary_reference_types": int(counts["dictionary_reference_types"]),
        "surface_rule_reference_types": int(counts["surface_rule_reference_types"]),
        "automatic_candidate_types": 0,
        "preserved_zero_fallback_hold_types": len(targets),
    }
    if counts != recomputed:
        raise RuntimeError("Stage 16 manifest counts differ")

    result = {
        "schema_version": AUDIT_SCHEMA,
        "status": "passed_read_only",
        "recorded_at": now_iso(),
        "manifest": file_fingerprint(manifest_path, with_sha256=True),
        "recomputed_counts": recomputed,
        "invariants": {
            "all_target_types_accounted": True,
            "surface_and_morph_linkage_separated": True,
            "bareun_alignment_mismatch_not_forced": True,
            "automatic_candidate_types": 0,
            "canonical_selection_performed": False,
            "mfa_or_textgrid_modified": False,
        },
    }
    atomic_write_json(output, result)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    result = audit(args.manifest.resolve(), args.output.resolve())
    print(json.dumps(result["recomputed_counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

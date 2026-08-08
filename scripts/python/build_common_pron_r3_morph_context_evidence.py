"""Link Stage 15 phone-change holds to six-year morphology/POS contexts."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS  # noqa: E402
from build_common_pron_r3_selection_readiness_v3 import (  # noqa: E402
    OUTPUT_FIELDS as READINESS_FIELDS,
)
from build_common_pron_r3_unanimous_phone_change_audit import (  # noqa: E402
    SCHEMA_VERSION as STAGE15_SCHEMA,
    STATUS as STAGE15_STATUS,
    TOKEN_AUDIT_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_morph_context_evidence.v1"
POLICY_SCHEMA = "common_pron_r3_morph_context_evidence_policy.v1"
STATUS = "success_evidence_linked_not_candidate"

TOKEN_FIELDS = (
    "token",
    "primary_audit_route",
    "expected_vocab_occurrences",
    "linked_search_master_occurrences",
    "occurrence_delta",
    "occurrence_link_status",
    "morph_linked_occurrences",
    "morph_unlinked_occurrences",
    "morph_link_status",
    "n_years_expected",
    "n_years_linked",
    *(f"expected_count_{year}" for year in YEARS),
    *(f"linked_count_{year}" for year in YEARS),
    "morph_signature_count",
    "morph_context_status",
    "top_morph_analysis",
    "top_morph_count",
    "dictionary_pron_hangul_json",
    "dictionary_source_refs_json",
    "dictionary_reference_available",
    "surface_rule_names",
    "surface_rule_reference_available",
    "rule_prediction_variant_count",
    "evidence_strata_json",
    "researcher_review_required_now",
    "automatic_candidate_eligible",
    "planning_zero_fallback_hold_preserved",
    "standard_pronunciation_claimed",
    "actual_realization_claimed",
    "candidate_generation_performed",
    "canonical_selection_performed",
)

MORPH_FIELDS = (
    "token",
    "tagged_eojeol",
    "total_occurrences",
    *(f"count_{year}" for year in YEARS),
    "predicted_hangul_counts_json",
    "predicted_roman_counts_json",
    "example_utt_ids_json",
    "bareun_analysis_is_gold",
    "actual_realization_claimed",
)

SUMMARY_FIELDS = (
    "primary_audit_route",
    "target_types",
    "expected_occurrences",
    "linked_occurrences",
    "morph_linked_occurrences",
    "fully_linked_types",
    "partially_linked_types",
    "unlinked_types",
    "fully_morph_linked_types",
    "partially_morph_linked_types",
    "morph_unlinked_types",
    "single_morph_signature_types",
    "multiple_morph_signature_types",
    "dictionary_reference_types",
    "surface_rule_reference_types",
    "automatic_candidate_types",
)

SEARCH_REQUIRED_FIELDS = (
    "utt_id",
    "year",
    "form",
    "tagged",
    "n_eojeol",
    "pron_pred_hangul",
    "pron_pred_roman",
)

csv.field_size_limit(10_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], path: Path, *, label: str) -> None:
    if (
        Path(str(record["path"])).resolve() != path.resolve()
        or not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


@contextmanager
def gzip_writer(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "xt", encoding="utf-8-sig", newline="", compresslevel=6) as stream:
        yield stream


def fingerprint_for_final(temp: Path, final: Path) -> dict[str, object]:
    result = file_fingerprint(temp, with_sha256=True)
    result["path"] = str(final.resolve())
    return result


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_evidence_linkage"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("Stage 16 policy identity differs")
    contract = policy.get("input_contract", {})
    if (
        int(contract.get("expected_target_types", 0)) != 4453
        or int(contract.get("expected_target_occurrences", 0)) != 72030
        or int(contract.get("expected_search_master_utterances", 0)) != 5103356
        or int(contract.get("search_master_eojeol_mismatch", -1)) != 0
        or contract.get("exact_surface_eojeol_link_only") is not True
    ):
        raise RuntimeError("Stage 16 input contract differs")
    if any(value is not True for value in policy.get("evidence_policy", {}).values()):
        raise RuntimeError("Stage 16 evidence policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("Stage 16 policy exceeds read-only scope")
    return policy


def split_aligned(
    row: dict[str, str]
) -> tuple[list[str], list[str], list[str], list[str], bool]:
    forms = clean(row["form"]).split()
    tagged = clean(row["tagged"]).split()
    predicted_hangul = clean(row["pron_pred_hangul"]).split()
    predicted_roman = [part.strip() for part in clean(row["pron_pred_roman"]).split("|")] if clean(row["pron_pred_roman"]) else []
    expected = int(clean(row["n_eojeol"]) or 0)
    if len(forms) != expected:
        raise RuntimeError(f"search master form eojeol count differs: {row['utt_id']}")
    tagged_aligned = len(tagged) == expected
    if not tagged_aligned:
        tagged = []
    if predicted_hangul and len(predicted_hangul) != expected:
        raise RuntimeError(f"predicted Hangul alignment differs: {row['utt_id']}")
    if predicted_roman and len(predicted_roman) != expected:
        raise RuntimeError(f"predicted Roman alignment differs: {row['utt_id']}")
    return forms, tagged, predicted_hangul, predicted_roman, tagged_aligned


def source_inventory_digest(files: list[Path], root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        stat = path.stat()
        relative = path.relative_to(root).as_posix()
        digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
        total_bytes += stat.st_size
    return {
        "root": str(root.resolve()),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "path_size_mtime_sha256": digest.hexdigest(),
        "content_hash_scope": "frozen layer build meta plus path-size-mtime inventory",
    }


def build(
    *, stage15_manifest_path: Path, readiness_manifest_path: Path,
    search_master_root: Path, policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        manifest_path = output_root / "MORPH_CONTEXT_EVIDENCE_MANIFEST.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"Stage 16 root exists without manifest: {output_root}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
            raise RuntimeError("existing Stage 16 differs")
        return manifest

    policy = validate_policy(policy_path)
    stage15_manifest = json.loads(stage15_manifest_path.read_text(encoding="utf-8-sig"))
    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    if stage15_manifest.get("schema_version") != STAGE15_SCHEMA or stage15_manifest.get("status") != STAGE15_STATUS:
        raise RuntimeError("Stage 15 input differs")
    stage15_path = Path(str(stage15_manifest["outputs"]["token_inventory"]["path"])).resolve()
    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v3"]["path"])).resolve()
    verify(stage15_manifest["outputs"]["token_inventory"], stage15_path, label="Stage 15 token inventory")
    verify(readiness_manifest["outputs"]["selection_readiness_v3"], readiness_path, label="readiness v3")

    targets: dict[str, dict[str, str]] = {}
    with gzip.open(stage15_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TOKEN_AUDIT_FIELDS:
            raise RuntimeError("Stage 15 token fields differ")
        for row in reader:
            targets[row["token"]] = row
    readiness: dict[str, dict[str, str]] = {}
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != READINESS_FIELDS:
            raise RuntimeError("readiness v3 fields differ")
        for row in reader:
            if row["token"] in targets:
                readiness[row["token"]] = row
    contract = policy["input_contract"]
    if len(targets) != int(contract["expected_target_types"]) or set(readiness) != set(targets):
        raise RuntimeError("Stage 16 target coverage differs")

    meta_path = search_master_root / "_build_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if (
        int(meta.get("totals", {}).get("n_utt", 0)) != int(contract["expected_search_master_utterances"])
        or int(meta.get("totals", {}).get("eojeol_mismatch", -1)) != 0
    ):
        raise RuntimeError("search master build contract differs")
    files = [
        path for year in YEARS
        for path in sorted((search_master_root / year).glob("*.csv"))
    ]
    if not files:
        raise RuntimeError("search master CSV files missing")
    source_inventory = source_inventory_digest(files, search_master_root)

    morph_counts: dict[str, Counter[str]] = defaultdict(Counter)
    morph_year_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    predicted_hangul: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    predicted_roman: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    token_predicted_roman: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    linked_year: dict[str, Counter[str]] = defaultdict(Counter)
    morph_linked_year: dict[str, Counter[str]] = defaultdict(Counter)
    utterance_rows = 0
    for file_index, path in enumerate(files, 1):
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not set(SEARCH_REQUIRED_FIELDS).issubset(reader.fieldnames or ()):
                raise RuntimeError(f"search master columns differ: {path}")
            for row in reader:
                utterance_rows += 1
                forms, tagged, hangul, roman, tagged_aligned = split_aligned(row)
                year = clean(row["year"])
                if year not in YEARS:
                    raise RuntimeError(f"unexpected search year: {year}")
                for index, token in enumerate(forms):
                    if token not in targets:
                        continue
                    linked_year[token][year] += 1
                    if roman:
                        token_predicted_roman[token][roman[index]] += 1
                    if not tagged_aligned:
                        continue
                    signature = tagged[index]
                    morph_counts[token][signature] += 1
                    morph_year_counts[(token, signature)][year] += 1
                    morph_linked_year[token][year] += 1
                    if hangul:
                        predicted_hangul[(token, signature)][hangul[index]] += 1
                    if roman:
                        predicted_roman[(token, signature)][roman[index]] += 1
                    if len(examples[(token, signature)]) < 5:
                        examples[(token, signature)].append(row["utt_id"])
        if file_index % 1000 == 0:
            print(f"[Stage16] {file_index:,}/{len(files):,} CSV; {utterance_rows:,} utterances", flush=True)
    if utterance_rows != int(contract["expected_search_master_utterances"]):
        raise RuntimeError("search master utterance count differs")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    morph_output = temp_root / "unanimous_phone_change_morph_signatures.csv.gz"
    token_output = temp_root / "unanimous_phone_change_evidence_coverage.csv.gz"
    summary_output = temp_root / "unanimous_phone_change_evidence_route_summary.csv"
    final_morph = output_root / morph_output.name
    final_token = output_root / token_output.name
    final_summary = output_root / summary_output.name

    with gzip_writer(morph_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=MORPH_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(targets):
            for signature, count in morph_counts[token].most_common():
                years = morph_year_counts[(token, signature)]
                writer.writerow(
                    {
                        "token": token,
                        "tagged_eojeol": signature,
                        "total_occurrences": count,
                        **{f"count_{year}": years[year] for year in YEARS},
                        "predicted_hangul_counts_json": json.dumps(dict(sorted(predicted_hangul[(token, signature)].items())), ensure_ascii=False),
                        "predicted_roman_counts_json": json.dumps(dict(sorted(predicted_roman[(token, signature)].items())), ensure_ascii=False),
                        "example_utt_ids_json": json.dumps(examples[(token, signature)], ensure_ascii=False),
                        "bareun_analysis_is_gold": "false",
                        "actual_realization_claimed": "false",
                    }
                )

    route_counts: dict[str, Counter[str]] = defaultdict(Counter)
    token_rows: list[dict[str, object]] = []
    linked_total = 0
    with gzip_writer(token_output) as stream:
        writer = csv.DictWriter(stream, fieldnames=TOKEN_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(targets):
            stage15 = targets[token]
            ready = readiness[token]
            expected = int(stage15["total_occurrences"])
            years = linked_year[token]
            linked = sum(years.values())
            delta = linked - expected
            status = "full_exact" if delta == 0 else ("partial" if linked else "unlinked")
            morph_linked = sum(morph_linked_year[token].values())
            morph_unlinked = linked - morph_linked
            morph_link_status = (
                "full_exact" if morph_linked == expected
                else ("partial" if morph_linked else "unlinked")
            )
            signatures = morph_counts[token]
            morph_status = "unlinked" if not signatures else ("single_signature" if len(signatures) == 1 else "multiple_signatures")
            top_signature, top_count = signatures.most_common(1)[0] if signatures else ("", 0)
            dictionary = json.loads(ready["dictionary_pron_hangul_json"] or "[]")
            refs = json.loads(ready["dictionary_source_refs_json"] or "[]")
            rule_available = bool(ready["surface_rule_names"])
            strata = []
            if signatures:
                strata.append("occurrence_morph_pos")
            if dictionary:
                strata.append("dictionary_pronunciation_reference")
            if rule_available:
                strata.append("surface_rule_reference")
            if any(predicted_roman[(token, signature)] for signature in signatures):
                strata.append("occurrence_rule_prediction")
            prediction_variants = set(token_predicted_roman[token])
            route = stage15["primary_audit_route"]
            counters = route_counts[route]
            counters["target_types"] += 1
            counters["expected_occurrences"] += expected
            counters["linked_occurrences"] += linked
            counters["morph_linked_occurrences"] += morph_linked
            counters[f"{status}_types"] += 1
            counters[f"morph_{morph_link_status}_types"] += 1
            counters[f"{morph_status}_types"] += 1
            counters["dictionary_reference_types"] += int(bool(dictionary))
            counters["surface_rule_reference_types"] += int(rule_available)
            output_row: dict[str, object] = {
                "token": token,
                "primary_audit_route": route,
                "expected_vocab_occurrences": expected,
                "linked_search_master_occurrences": linked,
                "occurrence_delta": delta,
                "occurrence_link_status": status,
                "morph_linked_occurrences": morph_linked,
                "morph_unlinked_occurrences": morph_unlinked,
                "morph_link_status": morph_link_status,
                "n_years_expected": stage15["n_years_present"],
                "n_years_linked": sum(years[year] > 0 for year in YEARS),
                **{f"expected_count_{year}": stage15[f"count_{year}"] for year in YEARS},
                **{f"linked_count_{year}": years[year] for year in YEARS},
                "morph_signature_count": len(signatures),
                "morph_context_status": morph_status,
                "top_morph_analysis": top_signature,
                "top_morph_count": top_count,
                "dictionary_pron_hangul_json": ready["dictionary_pron_hangul_json"],
                "dictionary_source_refs_json": ready["dictionary_source_refs_json"],
                "dictionary_reference_available": str(bool(dictionary)).lower(),
                "surface_rule_names": ready["surface_rule_names"],
                "surface_rule_reference_available": str(rule_available).lower(),
                "rule_prediction_variant_count": len(prediction_variants),
                "evidence_strata_json": json.dumps(strata, ensure_ascii=False),
                "researcher_review_required_now": "false",
                "automatic_candidate_eligible": "false",
                "planning_zero_fallback_hold_preserved": "true",
                "standard_pronunciation_claimed": "false",
                "actual_realization_claimed": "false",
                "candidate_generation_performed": "false",
                "canonical_selection_performed": "false",
            }
            writer.writerow(output_row)
            token_rows.append(output_row)
            linked_total += linked

    with summary_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for route in sorted(route_counts):
            counts = route_counts[route]
            writer.writerow(
                {
                    "primary_audit_route": route,
                    "target_types": counts["target_types"],
                    "expected_occurrences": counts["expected_occurrences"],
                    "linked_occurrences": counts["linked_occurrences"],
                    "morph_linked_occurrences": counts["morph_linked_occurrences"],
                    "fully_linked_types": counts["full_exact_types"],
                    "partially_linked_types": counts["partial_types"],
                    "unlinked_types": counts["unlinked_types"],
                    "fully_morph_linked_types": counts["morph_full_exact_types"],
                    "partially_morph_linked_types": counts["morph_partial_types"],
                    "morph_unlinked_types": counts["morph_unlinked_types"],
                    "single_morph_signature_types": counts["single_signature_types"],
                    "multiple_morph_signature_types": counts["multiple_signatures_types"],
                    "dictionary_reference_types": counts["dictionary_reference_types"],
                    "surface_rule_reference_types": counts["surface_rule_reference_types"],
                    "automatic_candidate_types": 0,
                }
            )

    link_status_types = Counter(str(row["occurrence_link_status"]) for row in token_rows)
    morph_link_status_types = Counter(str(row["morph_link_status"]) for row in token_rows)
    morph_status_types = Counter(str(row["morph_context_status"]) for row in token_rows)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "scope": {
            "row_unit": "surface_eojeol_type_with_morph_signature_inventory",
            "bareun_analysis_is_automatic_not_gold": True,
            "readiness_v3_hold_preserved": True,
            **policy["invariants"],
        },
        "inputs": {
            "stage15_manifest": file_fingerprint(stage15_manifest_path, with_sha256=True),
            "readiness_v3_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "stage15_token_inventory": file_fingerprint(stage15_path, with_sha256=True),
            "readiness_v3": file_fingerprint(readiness_path, with_sha256=True),
            "search_master_build_meta": file_fingerprint(meta_path, with_sha256=True),
            "search_master_inventory": source_inventory,
        },
        "counts": {
            "search_master_csv_files": len(files),
            "search_master_utterances": utterance_rows,
            "target_types": len(targets),
            "expected_target_occurrences": sum(int(row["total_occurrences"]) for row in targets.values()),
            "linked_target_occurrences": linked_total,
            "morph_linked_target_occurrences": sum(int(row["morph_linked_occurrences"]) for row in token_rows),
            "occurrence_link_status_types": dict(sorted(link_status_types.items())),
            "morph_link_status_types": dict(sorted(morph_link_status_types.items())),
            "morph_context_status_types": dict(sorted(morph_status_types.items())),
            "morph_signature_rows": sum(len(value) for value in morph_counts.values()),
            "dictionary_reference_types": sum(json.loads(readiness[token]["dictionary_pron_hangul_json"] or "[]") != [] for token in targets),
            "surface_rule_reference_types": sum(bool(readiness[token]["surface_rule_names"]) for token in targets),
            "automatic_candidate_types": 0,
            "preserved_zero_fallback_hold_types": len(targets),
        },
        "outputs": {
            "token_evidence_coverage": fingerprint_for_final(token_output, final_token),
            "morph_signatures": fingerprint_for_final(morph_output, final_morph),
            "route_summary": fingerprint_for_final(summary_output, final_summary),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "MORPH_CONTEXT_EVIDENCE_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--stage15-manifest", type=Path, required=True)
    result.add_argument("--readiness-v3-manifest", type=Path, required=True)
    result.add_argument("--search-master-root", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = build(
        stage15_manifest_path=args.stage15_manifest.resolve(),
        readiness_manifest_path=args.readiness_v3_manifest.resolve(),
        search_master_root=args.search_master_root.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

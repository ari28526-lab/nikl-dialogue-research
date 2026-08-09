"""Independently audit the normalized r3 pronunciation/search database."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file  # noqa: E402
from realign_eojeol_build_corpus import MISSING, form_to_lab_mapping  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_r3_research_database_audit.v1"
TYPE_AUDIT_SCHEMA = "mfa_r3_pronunciation_type_catalog_audit.v1"
YEAR_AUDIT_SCHEMA = "mfa_r3_pronunciation_occurrence_year_audit.v1"
csv.field_size_limit(20_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_path(value: str) -> Path:
    path = Path(value)
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def fingerprint_matches(record: Mapping[str, object], path: Path) -> bool:
    return bool(
        path.is_file()
        and Path(clean(record.get("path"))).resolve() == path.resolve()
        and int(record.get("bytes", -1)) == path.stat().st_size
        and clean(record.get("sha256")).lower() == sha256_file(path).lower()
    )


def independent_class(row: Mapping[str, str]) -> str:
    status = clean(row.get("planning_status"))
    hold = clean(row.get("planning_zero_fallback_hold")) == "true"
    policy = clean(row.get("planning_requires_policy_decision")) == "true"
    if status.startswith("candidate_") and not hold:
        return "selected"
    if hold and not policy:
        return "zero_fallback_hold"
    if policy or status.startswith("policy_"):
        return "explicit_policy_hold"
    raise RuntimeError(f"unclassified source type: {row.get('token')}")


def projection_inventory(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    indices: dict[str, list[int]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            token = clean(row.get("token"))
            count = int(row["variant_count"])
            if token in result and result[token] != count:
                raise RuntimeError(f"projection variant count drift: {token}")
            result[token] = count
            indices.setdefault(token, []).append(int(row["variant_index"]))
    for token, count in result.items():
        if indices[token] != list(range(1, count + 1)):
            raise RuntimeError(f"projection variant sequence drift: {token}")
    return result


def audit_type_catalog(policy: Mapping[str, object], paths: Mapping[str, Path]) -> tuple[dict, dict[str, str]]:
    root = paths["output_root"]
    catalog_path = root / "pronunciation_type_catalog.csv.gz"
    manifest_path = root / "TYPE_CATALOG_MANIFEST.json"
    audit_path = root / "TYPE_CATALOG_AUDIT.json"
    manifest = load_json(manifest_path)
    projection = projection_inventory(paths["selected_projection"])
    classes: dict[str, str] = {}
    counts: Counter[str] = Counter()
    failures: list[str] = []

    with gzip.open(paths["readiness_table"], "rt", encoding="utf-8-sig", newline="") as source, gzip.open(
        catalog_path, "rt", encoding="utf-8-sig", newline=""
    ) as actual:
        source_reader = csv.DictReader(source)
        actual_reader = csv.DictReader(actual)
        for source_row in source_reader:
            row = next(actual_reader, None)
            if row is None:
                failures.append("catalog_truncated")
                break
            token = clean(source_row.get("token"))
            if clean(row.get("token")) != token or token in classes:
                failures.append("catalog_key_or_uniqueness")
                break
            klass = independent_class(source_row)
            classes[token] = klass
            expected_variants = projection.get(token, 0)
            if (
                clean(row.get("pronunciation_release_id")) != clean(policy["release_id"])
                or clean(row.get("pronunciation_contract_id")) != clean(policy["pronunciation_contract_id"])
                or clean(row.get("release_selection_class")) != klass
                or int(clean(row.get("release_selected_variant_count")) or 0) != expected_variants
                or (klass == "selected") != (token in projection)
            ):
                failures.append(f"catalog_value_mismatch:{token}")
                break
            counts["types"] += 1
            counts[klass] += 1
            counts["selected_variant_rows"] += expected_variants
        if next(actual_reader, None) is not None:
            failures.append("catalog_has_extra_rows")

    invariants = policy["invariants"]
    expected_counts = {
        "types": int(invariants["canonical_types"]),
        "selected": int(invariants["selected_types"]),
        "selected_variant_rows": int(invariants["selected_variant_rows"]),
        "zero_fallback_hold": int(invariants["zero_fallback_hold_types"]),
        "explicit_policy_hold": int(invariants["explicit_policy_hold_types"]),
    }
    if {key: counts[key] for key in expected_counts} != expected_counts:
        failures.append("catalog_partition_counts")
    if not fingerprint_matches(manifest.get("output", {}), catalog_path):
        failures.append("catalog_manifest_output_fingerprint")
    report = {
        "schema_version": TYPE_AUDIT_SCHEMA,
        "status": "passed" if not failures else "failed",
        "recorded_at": now_iso(),
        "release_id": policy["release_id"],
        "failures": failures,
        "counts": {key: counts[key] for key in expected_counts},
        "inputs": {
            "catalog": file_fingerprint(catalog_path, with_sha256=True),
            "catalog_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "readiness_table": file_fingerprint(paths["readiness_table"], with_sha256=True),
            "selected_projection": file_fingerprint(paths["selected_projection"], with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(audit_path, report)
    if failures:
        raise RuntimeError("type catalog audit failed: " + ", ".join(failures[:5]))
    return report, classes


def read_id_partition(root: Path, year: str) -> dict[str, tuple[str, dict[str, str]]]:
    specs = (
        ("r3_safe_body_input", root / f"expected_mfa_input_ids_{year}.csv.gz"),
        ("pre_mfa_excluded", root / f"pre_mfa_exclusion_ids_{year}.csv.gz"),
        ("pronunciation_followup", root / f"pronunciation_followup_ids_{year}.csv.gz"),
    )
    result: dict[str, tuple[str, dict[str, str]]] = {}
    for scope, path in specs:
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                utt_id = clean(row.get("utt_id"))
                if clean(row.get("year")) != year or not utt_id or utt_id in result:
                    raise RuntimeError(f"invalid exact-ID partition row: {utt_id}")
                result[utt_id] = (scope, row)
    return result


def reference_form(row: Mapping[str, str]) -> str:
    value = clean(row.get("pron_reference_form"))
    return clean(row.get("form")) if value in MISSING else value


def next_required(iterator: Iterator[dict[str, str]], label: str) -> dict[str, str]:
    row = next(iterator, None)
    if row is None:
        raise RuntimeError(f"annual output truncated: {label}")
    return row


def expected_coordinate_status(row: Mapping[str, str], reference_count: int) -> tuple[bool, bool, str]:
    def equal(name: str) -> bool:
        value = clean(row.get(name))
        return value.isdigit() and int(value) == reference_count

    orth = equal("orth_eojeol_count_structured")
    morph = equal("morph_eojeol_count_structured")
    if orth and morph:
        return orth, morph, "reference_orth_morph_counts_equal"
    if orth:
        return orth, morph, "reference_orth_counts_equal_morph_unlinked"
    if morph:
        return orth, morph, "reference_morph_counts_equal_orth_unlinked"
    return orth, morph, "reference_only_no_silent_index_guess"


def audit_year(
    *, year: str, policy: Mapping[str, object], paths: Mapping[str, Path],
    type_audit: Mapping[str, object], classes: Mapping[str, str],
) -> dict:
    year_root = paths["output_root"] / year
    manifest_path = year_root / f"YEAR_DATABASE_MANIFEST_{year}.json"
    scope_path = year_root / "utterance_pronunciation_scope.csv.gz"
    occurrence_path = year_root / "pronunciation_occurrences.csv.gz"
    audit_path = year_root / f"AUDIT_RESEARCH_DATABASE_{year}.json"
    manifest = load_json(manifest_path)
    year_contract_root = paths["year_input_contract_root"] / year
    year_contract_path = year_contract_root / f"YEAR_INPUT_CONTRACT_{year}.json"
    year_contract = load_json(year_contract_path)
    contract_id = clean(year_contract.get("year_input_contract_id"))
    partition = read_id_partition(year_contract_root, year)
    failures: list[str] = []
    counts: Counter[str] = Counter()
    seen: set[str] = set()

    with gzip.open(scope_path, "rt", encoding="utf-8-sig", newline="") as scope_stream, gzip.open(
        occurrence_path, "rt", encoding="utf-8-sig", newline=""
    ) as occurrence_stream:
        scope_iter = iter(csv.DictReader(scope_stream))
        occurrence_iter = iter(csv.DictReader(occurrence_stream))
        shard_sources = sorted(
            path for path in (paths["morph_search_root"] / year / "shards").glob("shard_*") if path.is_dir()
        )
        for shard in shard_sources:
            source_path = shard / "tables" / "utterance_master_v2.csv.gz"
            with gzip.open(source_path, "rt", encoding="utf-8-sig", newline="") as source:
                for source_row in csv.DictReader(source):
                    utt_id = clean(source_row.get("utt_id"))
                    session = clean(source_row.get("session_id"))
                    if utt_id in seen or utt_id not in partition:
                        failures.append(f"source_key_accounting:{utt_id}")
                        break
                    seen.add(utt_id)
                    scope, detail = partition[utt_id]
                    actual_scope = next_required(scope_iter, "utterance scope")
                    reference = reference_form(source_row)
                    mappings = form_to_lab_mapping(reference)
                    expected_scope = {
                        "year": year,
                        "utt_id": utt_id,
                        "session_id": session,
                        "pronunciation_release_id": clean(policy["release_id"]),
                        "pronunciation_contract_id": clean(policy["pronunciation_contract_id"]),
                        "year_input_contract_id": contract_id,
                        "alignment_scope": scope,
                        "alignment_layer_expected": "true" if scope == "r3_safe_body_input" else "false",
                        "pron_reference_form": reference,
                        "pron_reference_n_eojeol": str(len(mappings)),
                        "lab_n_eojeol": str(sum(bool(item["included_in_mfa"]) for item in mappings)),
                        "pron_reference_status": clean(source_row.get("pron_reference_status")),
                        "routing_class": clean(detail.get("routing_class")),
                        "hold_tokens_json": clean(detail.get("hold_tokens_json")) or "[]",
                        "policy_tokens_json": clean(detail.get("policy_tokens_json")) or "[]",
                        "unknown_tokens_json": clean(detail.get("unknown_tokens_json")) or "[]",
                        "pre_mfa_reason_codes_json": clean(detail.get("reason_codes_json")) or "[]",
                    }
                    if actual_scope != expected_scope:
                        failures.append(f"utterance_scope_value:{utt_id}")
                        break
                    counts["utterances"] += 1
                    counts[f"scope_{scope}"] += 1
                    for item in mappings:
                        actual = next_required(occurrence_iter, "occurrence")
                        index = int(item["source_eojeol_index"]) + 1
                        included = bool(item["included_in_mfa"])
                        token = clean(item["lab_token"])
                        klass = classes.get(token, "") if included else "not_applicable_empty_lab"
                        orth, morph, link_status = expected_coordinate_status(source_row, len(mappings))
                        expected_occurrence = {
                            "year": year,
                            "utt_id": utt_id,
                            "session_id": session,
                            "reference_eojeol_idx": str(index),
                            "reference_eojeol_count": str(len(mappings)),
                            "reference_eojeol": clean(item["source_token"]),
                            "pronunciation_token": token,
                            "included_in_mfa": "true" if included else "false",
                            "mfa_word_idx": str(int(item["mfa_word_index"]) + 1) if included else "",
                            "orth_eojeol_idx_if_count_aligned": str(index) if orth else "",
                            "morph_eojeol_idx_if_count_aligned": str(index) if morph else "",
                            "coordinate_link_status": link_status,
                            "pronunciation_release_id": clean(policy["release_id"]),
                            "pronunciation_contract_id": clean(policy["pronunciation_contract_id"]),
                            "year_input_contract_id": contract_id,
                            "release_selection_class": klass,
                            "alignment_scope": scope,
                            "alignment_layer_expected": "true" if scope == "r3_safe_body_input" else "false",
                        }
                        if actual != expected_occurrence:
                            failures.append(f"occurrence_value:{utt_id}:{index}")
                            break
                        if included and not klass:
                            failures.append(f"unknown_nonempty_token:{utt_id}:{token}")
                            break
                        if scope in {"r3_safe_body_input", "pre_mfa_excluded"} and included and klass != "selected":
                            failures.append(f"unsafe_safe_body_token:{utt_id}:{token}")
                            break
                        counts["occurrences"] += 1
                    if failures:
                        break
            if failures:
                break
        if next(scope_iter, None) is not None:
            failures.append("utterance_scope_extra_rows")
        if next(occurrence_iter, None) is not None:
            failures.append("occurrence_extra_rows")

    if seen != set(partition):
        failures.append("exact_id_partition_not_fully_observed")
    if not fingerprint_matches(manifest.get("outputs", {}).get("utterance_scope", {}), scope_path):
        failures.append("manifest_scope_fingerprint")
    if not fingerprint_matches(manifest.get("outputs", {}).get("occurrences", {}), occurrence_path):
        failures.append("manifest_occurrence_fingerprint")
    report = {
        "schema_version": YEAR_AUDIT_SCHEMA,
        "status": "passed" if not failures else "failed",
        "recorded_at": now_iso(),
        "year": year,
        "release_id": policy["release_id"],
        "pronunciation_contract_id": policy["pronunciation_contract_id"],
        "year_input_contract_id": contract_id,
        "post_mfa_join_key": ["year", "utt_id", "reference_eojeol_idx"],
        "failures": failures,
        "counts": dict(counts),
        "verdict": {
            "all_source_utterances_accounted": not failures and len(seen) == len(partition),
            "unknown_nonempty_lab_tokens": 0 if not any("unknown_nonempty" in item for item in failures) else None,
            "safe_body_uses_selected_types_only": not any("unsafe_safe_body" in item for item in failures),
            "ready_for_mfa_preflight": not failures,
        },
        "inputs": {
            "type_catalog_audit": file_fingerprint(paths["output_root"] / "TYPE_CATALOG_AUDIT.json", with_sha256=True),
            "year_database_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "year_input_contract": file_fingerprint(year_contract_path, with_sha256=True),
            "utterance_scope": file_fingerprint(scope_path, with_sha256=True),
            "occurrences": file_fingerprint(occurrence_path, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(audit_path, report)
    if failures:
        raise RuntimeError("annual r3 research database audit failed: " + ", ".join(failures[:5]))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path,
        default=PROJECT_ROOT / "config" / "mfa_r3_research_database_v1.json",
    )
    parser.add_argument("--year", required=True, choices=("2020", "2021", "2022", "2023", "2024", "2025"))
    args = parser.parse_args()
    policy = load_json(args.config.resolve())
    if policy.get("schema_version") != "mfa_r3_research_database.v1":
        raise RuntimeError("research database policy identity differs")
    paths = {name: resolve_path(clean(value)) for name, value in policy["paths"].items()}
    type_audit, classes = audit_type_catalog(policy, paths)
    report = audit_year(year=args.year, policy=policy, paths=paths, type_audit=type_audit, classes=classes)
    print(
        f"[PASS] {args.year} r3 research DB audit: "
        f"utterances={report['counts']['utterances']:,}, "
        f"occurrences={report['counts']['occurrences']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

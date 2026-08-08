"""Summarize the audited stage 11 rule/phone evidence for reporting."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file


SCHEMA_VERSION = "common_pron_r3_rule_phone_coverage_summary.v1"


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


def token_status(rows: list[dict[str, str]]) -> str:
    optional = [row["optional_place_assimilation_only"] == "true" for row in rows]
    frozen = [row["frozen_dictionary_exact_variant"] == "true" for row in rows]
    if all(optional):
        return "all_variants_optional_place_assimilation"
    if any(optional):
        return "some_variants_optional_place_assimilation"
    if all(frozen):
        return "all_variants_exact_frozen_dictionary"
    if any(frozen):
        return "some_variants_exact_frozen_dictionary"
    return "unresolved_g2p_or_rule_mapping"


def summarize(*, manifest_path: Path, audit_path: Path, output_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    if manifest.get("status") != "success_audited_not_candidate" or audit.get("status") != "passed_read_only":
        raise RuntimeError("rule/phone coverage inputs are not final read-only results")
    variant_path = verify(manifest["outputs"]["variant_coverage"], label="variant coverage")
    phone_path = verify(manifest["outputs"]["phone_rule_cooccurrence"], label="phone co-occurrence")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(variant_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            groups[row["token"]].append(row)
    type_counts: Counter[str] = Counter()
    occurrence_counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    for token, rows in groups.items():
        status = token_status(rows)
        total = int(rows[0]["total_occurrences"])
        type_counts[status] += 1
        occurrence_counts[status] += total
        examples[status].append(
            {
                "token": token,
                "total_occurrences": total,
                "r2_pron_phones": rows[0]["r2_pron_phones"],
                "r2_pron_roman": rows[0]["r2_pron_roman"],
                "rule_pron_roman": rows[0]["rule_pron_roman"],
                "edit_signature": rows[0]["edit_signature"],
            }
        )
    top_examples = {
        key: sorted(values, key=lambda row: (-int(row["total_occurrences"]), str(row["token"])))[:25]
        for key, values in examples.items()
    }
    noninjective: list[dict[str, object]] = []
    with phone_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["noninjective_for_rule_recovery"] != "true":
                continue
            counts = json.loads(row["rule_key_token_types_json"])
            noninjective.append(
                {
                    "phone_mfa": row["phone_mfa"],
                    "current_phone_class_r_auto": row["phone_class_r_auto"],
                    "rule_key_token_types": counts,
                    "examples_by_rule_key": json.loads(row["example_tokens_by_rule_key_json"]),
                    "supported_rule_key_count": sum(int(value) >= 2 for value in counts.values()),
                    "same_length_positional_token_types": int(row["same_length_positional_token_types"]),
                    "direct_mapping_authorized": False,
                }
            )
    noninjective.sort(
        key=lambda row: (-int(row["supported_rule_key_count"]), -int(row["same_length_positional_token_types"]), str(row["phone_mfa"]))
    )
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_summary_read_only",
        "recorded_at": now_iso(),
        "type_counts_by_primary_diagnostic": dict(sorted(type_counts.items())),
        "occurrence_counts_by_primary_diagnostic": dict(sorted(occurrence_counts.items())),
        "overlapping_evidence_counts": {
            "tokens_with_any_optional_place_assimilation": manifest["counts"]["tokens_with_any_optional_place_assimilation"],
            "tokens_all_variants_exact_frozen_dictionary": manifest["counts"]["tokens_all_variants_exact_frozen_dictionary"],
            "tokens_with_any_noninjective_phone": manifest["counts"]["tokens_with_any_noninjective_phone"],
            "noninjective_phone_types": manifest["counts"]["noninjective_phone_types"],
        },
        "top_examples_by_primary_diagnostic": top_examples,
        "noninjective_phone_inventory": noninjective,
        "interpretation": {
            "optional_place_assimilation_is_mandatory_standard_rule": False,
            "frozen_dictionary_variant_is_standard_pronunciation_truth": False,
            "phone_rule_cooccurrence_is_direct_mapping": False,
            "mfa_phone_is_actual_realization_transcription": False,
            "candidate_generation_performed": False,
        },
        "evidence": {
            "manifest": file_fingerprint(manifest_path, with_sha256=True),
            "audit": file_fingerprint(audit_path, with_sha256=True),
            "variant_coverage": file_fingerprint(variant_path, with_sha256=True),
            "phone_rule_cooccurrence": file_fingerprint(phone_path, with_sha256=True),
        },
    }
    atomic_write_json(output_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audit", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        manifest_path=args.manifest.resolve(),
        audit_path=args.audit.resolve(),
        output_path=args.output.resolve(),
    )
    print(json.dumps({"types": report["type_counts_by_primary_diagnostic"], "occurrences": report["occurrence_counts_by_primary_diagnostic"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

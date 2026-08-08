"""Summarize audited no-rule hold characterization for rule-engine planning."""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file


SCHEMA_VERSION = "common_pron_r3_no_rule_hold_summary.v1"
NASAL_MARKERS = ("SUB:N>NG", "SUB:NG>N", "SUB:M>N", "SUB:M>NG", "SUB:N>M", "SUB:NG>M")
LARYNGEAL_MARKERS = ("SUB:B>P", "SUB:P>B", "SUB:D>T", "SUB:T>D", "SUB:G>K", "SUB:K>G", "SUB:SS>S", "SUB:S>SS")
GLIDE_VOWEL_MARKERS = ("RULE_ONLY:W", "RULE_ONLY:Y", "RULE_ONLY:EU_G", "SUB:E>AE", "SUB:AE>E")


def clean(value: object) -> str:
    return str(value or "").strip()


def verify_record(record: dict[str, object], *, label: str) -> Path:
    path = Path(str(record["path"])).resolve()
    if (
        not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")
    return path


def family_hints(signatures: list[str]) -> set[str]:
    joined = ";".join(signatures)
    result: set[str] = set()
    if any(marker in joined for marker in NASAL_MARKERS):
        result.add("nasal_place_or_boundary_rule_gap")
    if any(marker in joined for marker in LARYNGEAL_MARKERS):
        result.add("laryngeal_contrast_or_phone_mapping_gap")
    if any(marker in joined for marker in GLIDE_VOWEL_MARKERS):
        result.add("glide_vowel_unitization_or_rule_gap")
    if "RULE_ONLY:" in joined or "CANDIDATE_ONLY:" in joined:
        result.add("segment_count_or_deletion_gap")
    if not result:
        result.add("other_substitution_or_mixed_gap")
    return result


def push_top(
    heap: list[tuple[int, str, dict[str, object]]],
    record: dict[str, object],
    *,
    limit: int,
) -> None:
    marker = (int(record["total_occurrences"]), str(record["token"]), record)
    if len(heap) < limit:
        heapq.heappush(heap, marker)
    elif marker[:2] > heap[0][:2]:
        heapq.heapreplace(heap, marker)


def summarize(
    *, manifest_path: Path, audit_path: Path, output_path: Path, top_n: int
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    if manifest.get("status") != "success_characterized_not_candidate" or audit.get("status") != "passed_read_only":
        raise RuntimeError("no-rule characterization is not audited")
    if manifest["counts"] != audit["counts"]:
        raise RuntimeError("no-rule characterization/audit counts differ")
    data_path = verify_record(
        manifest["outputs"]["no_rule_hold_characterization"], label="characterization"
    )
    signature_occurrences: Counter[str] = Counter()
    class_occurrences: Counter[str] = Counter()
    family_types: Counter[str] = Counter()
    family_occurrences: Counter[str] = Counter()
    overall: list[tuple[int, str, dict[str, object]]] = []
    by_evidence: dict[str, list[tuple[int, str, dict[str, object]]]] = defaultdict(list)
    by_family: dict[str, list[tuple[int, str, dict[str, object]]]] = defaultdict(list)
    with gzip.open(data_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            total = int(row["total_occurrences"])
            signatures = json.loads(row["edit_signatures_json"])
            classes = json.loads(row["diagnostic_classes_json"])
            families = family_hints(signatures)
            record: dict[str, object] = {
                "token": row["token"],
                "total_occurrences": total,
                "rule_pron_hangul": row["rule_pron_hangul"],
                "rule_pron_roman": row["rule_pron_roman"],
                "r2_pron_roman": json.loads(row["r2_pron_roman_json"]),
                "r2_pron_phones": json.loads(row["r2_pron_phones_json"]),
                "r2_pron_source": row["r2_pron_source"],
                "dictionary_pron_hangul": json.loads(row["dictionary_pron_hangul_json"]),
                "evidence_stratum": row["evidence_stratum"],
                "diagnostic_classes": classes,
                "edit_signatures": signatures,
                "diagnostic_family_hints": sorted(families),
            }
            push_top(overall, record, limit=top_n)
            push_top(by_evidence[row["evidence_stratum"]], record, limit=top_n)
            for family in families:
                family_types[family] += 1
                family_occurrences[family] += total
                push_top(by_family[family], record, limit=top_n)
            for signature in signatures:
                signature_occurrences[signature] += total
            for diagnostic_class in classes:
                class_occurrences[diagnostic_class] += total
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "audited_characterization_summary",
        "recorded_at": now_iso(),
        "counts": manifest["counts"],
        "diagnostic_family_hint_types": dict(sorted(family_types.items())),
        "diagnostic_family_hint_occurrences": dict(sorted(family_occurrences.items())),
        "top_edit_signature_occurrences": dict(signature_occurrences.most_common(100)),
        "diagnostic_class_occurrences": dict(sorted(class_occurrences.items())),
        "high_frequency_overall": [item[2] for item in sorted(overall, reverse=True)],
        "high_frequency_by_evidence_stratum": {
            key: [item[2] for item in sorted(value, reverse=True)]
            for key, value in sorted(by_evidence.items())
        },
        "high_frequency_by_diagnostic_family_hint": {
            key: [item[2] for item in sorted(value, reverse=True)]
            for key, value in sorted(by_family.items())
        },
        "interpretation_contract": {
            "diagnostic_family_is_rule_truth": False,
            "characterization_is_candidate_generation": False,
            "dictionary_presence_is_final_selection": False,
            "next_action": "audit and extend rule/phone mapping coverage before projecting no-rule holds",
        },
        "evidence": {
            "characterization_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "characterization_audit": file_fingerprint(audit_path, with_sha256=True),
        },
    }
    atomic_write_json(output_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--audit", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--top-n", type=int, default=20)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        manifest_path=args.manifest.resolve(),
        audit_path=args.audit.resolve(),
        output_path=args.output.resolve(),
        top_n=args.top_n,
    )
    print(json.dumps(report["diagnostic_family_hint_types"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

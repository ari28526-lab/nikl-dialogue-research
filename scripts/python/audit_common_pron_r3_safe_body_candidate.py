"""Independently verify the r3 safe-body candidate projection and dictionary."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import acoustic_phone_inventory, parse_mfa_dictionary_line
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_safe_body_candidate_audit.v1"


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], path: Path, label: str) -> None:
    if (
        Path(str(record["path"])).resolve() != path.resolve()
        or not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def audit(manifest_path: Path, output_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != "common_pron_r3_safe_body_candidate.v1" or manifest.get("status") != "passed_candidate_only_not_adopted":
        raise RuntimeError("safe-body candidate manifest identity differs")
    scope = manifest["scope"]
    if scope.get("candidate_only") is not True or any(scope.get(key) is not False for key in ("final_selection", "adopted", "allow_yearly_mfa", "allow_textgrid_materialization")):
        raise RuntimeError("safe-body candidate scope differs")

    readiness_path = Path(str(manifest["inputs"]["readiness_v4"]["path"])).resolve()
    projection_path = Path(str(manifest["outputs"]["candidate_projection"]["path"])).resolve()
    dictionary_path = Path(str(manifest["outputs"]["candidate_dictionary_not_adopted"]["path"])).resolve()
    acoustic_path = Path(str(manifest["inputs"]["frozen_acoustic_model"]["path"])).resolve()
    verify(manifest["inputs"]["readiness_v4"], readiness_path, "readiness")
    verify(manifest["outputs"]["candidate_projection"], projection_path, "projection")
    verify(manifest["outputs"]["candidate_dictionary_not_adopted"], dictionary_path, "dictionary")
    verify(manifest["inputs"]["frozen_acoustic_model"], acoustic_path, "acoustic")
    inventory = acoustic_phone_inventory(acoustic_path) - {"sil", "spn"}

    with gzip.open(projection_path, "rt", encoding="utf-8-sig", newline="") as stream:
        projection_rows = list(csv.DictReader(stream))
    dictionary_rows: list[tuple[str, tuple[str, ...]]] = []
    with dictionary_path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            token, phones, probabilities = parse_mfa_dictionary_line(line, path=dictionary_path, line_number=line_number)
            if probabilities:
                raise RuntimeError("candidate dictionary unexpectedly has probability columns")
            dictionary_rows.append((token, phones))
    if len(projection_rows) != len(dictionary_rows):
        raise RuntimeError("projection/dictionary row count differs")

    projection_by_token: dict[str, list[dict[str, str]]] = {}
    outside: set[str] = set()
    for index, (row, dictionary_row) in enumerate(zip(projection_rows, dictionary_rows), 1):
        token = row["token"]
        phones = tuple(row["pron_phones_mfa"].split())
        if (token, phones) != dictionary_row:
            raise RuntimeError(f"projection/dictionary byte projection differs at row {index}")
        if row["candidate_only"] != "true" or row["final_selection"] != "false" or row["adopted"] != "false":
            raise RuntimeError(f"projection status differs: {token}")
        outside.update(set(phones) - inventory)
        projection_by_token.setdefault(token, []).append(row)
    if outside:
        raise RuntimeError(f"candidate dictionary phones outside acoustic inventory: {sorted(outside)}")

    type_count = occurrence_count = 0
    status_types: Counter[str] = Counter()
    variant_distribution: Counter[int] = Counter()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if not row["planning_status"].startswith("candidate_"):
                if row["token"] in projection_by_token:
                    raise RuntimeError(f"non-candidate leaked into projection: {row['token']}")
                continue
            token = row["token"]
            projected = projection_by_token.pop(token, None)
            phones = [clean(value) for value in json.loads(row["planning_candidate_phones_json"] or "[]")]
            roman = [clean(value) for value in json.loads(row["planning_candidate_roman_json"] or "[]")]
            if projected is None or len(projected) != int(row["planning_candidate_variant_count"]):
                raise RuntimeError(f"candidate variant coverage differs: {token}")
            for variant_index, projected_row in enumerate(projected, 1):
                if (
                    int(projected_row["variant_index"]) != variant_index
                    or int(projected_row["variant_count"]) != len(projected)
                    or projected_row["pron_phones_mfa"] != phones[variant_index - 1]
                    or projected_row["pron_roman"] != roman[variant_index - 1]
                    or projected_row["planning_status"] != row["planning_status"]
                    or projected_row["planning_source"] != row["planning_source"]
                ):
                    raise RuntimeError(f"candidate readiness projection differs: {token}")
            type_count += 1
            occurrence_count += int(row["total_occurrences"])
            status_types[row["planning_status"]] += 1
            variant_distribution[len(projected)] += 1
    if projection_by_token:
        raise RuntimeError("projection has tokens absent from readiness")
    counts = manifest["counts"]
    if (
        type_count != int(counts["candidate_types"])
        or occurrence_count != int(counts["candidate_occurrences"])
        or len(dictionary_rows) != int(counts["dictionary_rows"])
        or {str(key): value for key, value in sorted(variant_distribution.items())} != counts["variant_count_distribution"]
        or dict(sorted(status_types.items())) != counts["planning_status_types"]
    ):
        raise RuntimeError("candidate manifest accounting differs")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_full_projection_and_dictionary_equivalence",
        "recorded_at": now_iso(),
        "inputs": {
            "candidate_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "readiness_v4": file_fingerprint(readiness_path, with_sha256=True),
            "candidate_projection": file_fingerprint(projection_path, with_sha256=True),
            "candidate_dictionary_not_adopted": file_fingerprint(dictionary_path, with_sha256=True),
            "frozen_acoustic_model": file_fingerprint(acoustic_path, with_sha256=True),
        },
        "checks": {
            "every_candidate_type_projected": True,
            "variant_order_and_count_equal": True,
            "dictionary_rows_equal_projection": True,
            "phones_inside_frozen_acoustic_inventory": True,
            "non_candidate_leakage": 0,
            "final_or_adopted_claims": 0,
        },
        "counts": {
            "candidate_types": type_count,
            "candidate_occurrences": occurrence_count,
            "dictionary_rows": len(dictionary_rows),
            "variant_count_distribution": {str(key): value for key, value in sorted(variant_distribution.items())},
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.candidate_manifest.resolve(), args.output.resolve())
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

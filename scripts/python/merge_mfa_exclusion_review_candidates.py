"""Merge immutable pending MFA exclusion snapshots without approving rows.

This is used when a later hard gate discovers new candidates after a researcher
approved an earlier snapshot.  The old snapshot stays unchanged; the result is
a new pending snapshot with complete provenance.  Duplicate utterances must
agree on reason and scope, while newly observed utterances are appended.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from mfa_exclusion_contract import REVIEW_FIELDS
from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint

SCHEMA_VERSION = "mfa_exclusion_review_candidates.v1"


def _load_snapshot(
    csv_path: Path, manifest_path: Path
) -> tuple[dict[str, object], list[dict[str, str]]]:
    csv_path = csv_path.resolve()
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "pending_researcher_review"
        or bool(manifest.get("automatic_approval_performed"))
    ):
        raise RuntimeError(f"pending candidate manifest 불일치: {manifest_path}")
    fingerprint = manifest.get("review_csv")
    if (
        not isinstance(fingerprint, dict)
        or Path(str(fingerprint.get("path") or "")).resolve() != csv_path
        or file_fingerprint(csv_path, with_sha256=True)["sha256"]
        != str(fingerprint.get("sha256") or "")
    ):
        raise RuntimeError(f"candidate CSV fingerprint 불일치: {csv_path}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if list(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError(f"candidate CSV schema 불일치: {csv_path}")
        for line_number, raw in enumerate(reader, 2):
            row = {
                field: str(raw.get(field, "") or "").strip()
                for field in REVIEW_FIELDS
            }
            if row["decision"] != "pending":
                raise RuntimeError(
                    f"pending snapshot에 미승인 이외 decision: {line_number}"
                )
            if not row["utt_id"] or row["utt_id"] in seen:
                raise RuntimeError(
                    f"candidate 빈/중복 utt_id: {line_number}"
                )
            seen.add(row["utt_id"])
            rows.append(row)
    if len(rows) != int(manifest.get("candidate_count", -1)):
        raise RuntimeError("candidate manifest row_count 불일치")
    return manifest, rows


def merge_snapshots(
    *,
    base_csv: Path,
    base_manifest: Path,
    addendum_csv: Path,
    addendum_manifest: Path,
    output_csv: Path,
    output_manifest: Path,
) -> dict[str, object]:
    base_data, base_rows = _load_snapshot(base_csv, base_manifest)
    addendum_data, addendum_rows = _load_snapshot(
        addendum_csv, addendum_manifest
    )
    identity = (
        str(base_data.get("year") or ""),
        str(base_data.get("input_contract_id") or ""),
    )
    if identity != (
        str(addendum_data.get("year") or ""),
        str(addendum_data.get("input_contract_id") or ""),
    ) or not all(identity):
        raise RuntimeError("base/addendum year 또는 input_contract_id 불일치")

    by_utt = {row["utt_id"]: row for row in base_rows}
    duplicate_count = 0
    added_count = 0
    for row in addendum_rows:
        prior = by_utt.get(row["utt_id"])
        if prior is not None:
            duplicate_count += 1
            if (
                prior["reason_code"] != row["reason_code"]
                or prior["exclusion_scope"] != row["exclusion_scope"]
            ):
                raise RuntimeError(
                    "중복 후보 reason/scope 충돌: "
                    f"{row['utt_id']}"
                )
            continue
        by_utt[row["utt_id"]] = row
        added_count += 1
    merged_rows = [by_utt[key] for key in sorted(by_utt)]
    output_csv = output_csv.resolve()
    output_manifest = output_manifest.resolve()
    with atomic_text_writer(
        output_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=REVIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(merged_rows)
    reason_counts = Counter(row["reason_code"] for row in merged_rows)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_review",
        "year": identity[0],
        "input_contract_id": identity[1],
        "merge_policy": "immutable_base_plus_new_ids; duplicate_reason_scope_equal",
        "base_candidate_manifest": file_fingerprint(
            base_manifest.resolve(), with_sha256=True
        ),
        "addendum_candidate_manifest": file_fingerprint(
            addendum_manifest.resolve(), with_sha256=True
        ),
        "base_candidate_count": len(base_rows),
        "addendum_candidate_count": len(addendum_rows),
        "duplicate_candidate_count": duplicate_count,
        "new_addendum_candidate_count": added_count,
        "review_csv": file_fingerprint(output_csv, with_sha256=True),
        "candidate_count": len(merged_rows),
        "candidate_counts_by_reason": dict(sorted(reason_counts.items())),
        "automatic_approval_performed": False,
    }
    atomic_write_json(output_manifest, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-csv", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--addendum-csv", type=Path, required=True)
    parser.add_argument("--addendum-manifest", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = merge_snapshots(
        base_csv=args.base_csv,
        base_manifest=args.base_manifest,
        addendum_csv=args.addendum_csv,
        addendum_manifest=args.addendum_manifest,
        output_csv=args.output_csv,
        output_manifest=args.output_manifest,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

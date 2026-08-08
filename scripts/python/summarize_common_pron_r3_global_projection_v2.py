"""Summarize audited global projection v2 and the refreshed readiness matrix."""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file  # noqa: E402


SCHEMA_VERSION = "common_pron_r3_global_projection_summary.v2"
CHANGE_CLASSES = ("candidate_gained", "candidate_lost", "candidate_phone_changed")


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


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def top_changes(path: Path, limit: int) -> dict[str, list[dict[str, object]]]:
    heaps: dict[str, list[tuple[int, str, dict[str, object]]]] = {
        key: [] for key in CHANGE_CLASSES
    }
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            category = row["comparison_class"]
            if category not in heaps:
                continue
            total = int(row["total_occurrences"])
            record: dict[str, object] = {
                "target_hangul": row["target_hangul"],
                "total_occurrences": total,
                "previous_projection_status": row["previous_projection_status"],
                "global_projection_status": row["global_projection_status"],
                "previous_projected_pron_phones_json": json.loads(
                    row["previous_projected_pron_phones_json"]
                ),
                "global_projected_pron_phones_json": json.loads(
                    row["global_projected_pron_phones_json"]
                ),
            }
            marker = (total, row["target_hangul"], record)
            if len(heaps[category]) < limit:
                heapq.heappush(heaps[category], marker)
            elif marker[:2] > heaps[category][0][:2]:
                heapq.heapreplace(heaps[category], marker)
    return {
        category: [item[2] for item in sorted(values, reverse=True)]
        for category, values in heaps.items()
    }


def summarize(
    *,
    global_manifest_path: Path,
    global_audit_path: Path,
    readiness_manifest_path: Path,
    readiness_audit_path: Path,
    output_path: Path,
    top_n: int,
) -> dict[str, object]:
    global_manifest = load_json(global_manifest_path)
    global_audit = load_json(global_audit_path)
    readiness = load_json(readiness_manifest_path)
    readiness_audit = load_json(readiness_audit_path)
    if (
        global_manifest.get("status") != "success_candidates_not_selected"
        or global_audit.get("status") != "passed_read_only"
        or readiness.get("status") != "success_planning_not_selected"
        or readiness_audit.get("status") != "passed_read_only"
    ):
        raise RuntimeError("audited global projection inputs are incomplete")
    if global_manifest["counts"] != global_audit["counts"]:
        raise RuntimeError("global projection/audit counts differ")
    if readiness["counts"] != readiness_audit["counts"]:
        raise RuntimeError("global readiness/audit counts differ")
    comparison_path = verify_record(
        global_manifest["outputs"]["projection_comparison"], label="projection comparison"
    )
    prior_readiness_manifest_path = verify_record(
        global_manifest["inputs"]["selection_readiness_manifest"],
        label="prior selection readiness manifest",
    )
    prior_readiness = load_json(prior_readiness_manifest_path)
    prior_counts = prior_readiness["counts"]
    current_counts = readiness["counts"]
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "audited_candidate_only_summary",
        "recorded_at": now_iso(),
        "scope": {
            "same_g2p_rerun_performed": False,
            "candidate_is_final_selection": False,
            "canonical_selection_performed": False,
            "adoption_performed": False,
            "annual_mfa_started": False,
            "textgrids_modified": False,
        },
        "global_projection_counts": global_manifest["counts"],
        "readiness_counts": current_counts,
        "readiness_delta_from_limited_donor": {
            "candidate_ready_types": int(current_counts["candidate_ready_types"])
            - int(prior_counts["candidate_ready_types"]),
            "candidate_ready_occurrences": int(current_counts["candidate_ready_occurrences"])
            - int(prior_counts["candidate_ready_occurrences"]),
            "policy_decision_types": int(current_counts["policy_decision_types"])
            - int(prior_counts["policy_decision_types"]),
            "policy_decision_occurrences": int(current_counts["policy_decision_occurrences"])
            - int(prior_counts["policy_decision_occurrences"]),
            "zero_fallback_hold_types": int(current_counts["zero_fallback_hold_types"])
            - int(prior_counts["zero_fallback_hold_types"]),
            "zero_fallback_hold_occurrences": int(current_counts["zero_fallback_hold_occurrences"])
            - int(prior_counts["zero_fallback_hold_occurrences"]),
        },
        "high_frequency_changes": top_changes(comparison_path, top_n),
        "regression_examples": global_audit["regression_examples"],
        "remaining_scope": {
            "target_projection_unresolved_types": int(
                current_counts["planning_status_types"]["hold_target_projection_unresolved"]
            ),
            "no_surface_rule_substantive_mismatch_types": int(
                current_counts["planning_status_types"]["hold_no_surface_rule_substantive_mismatch"]
            ),
            "multiple_variant_policy_types": int(current_counts["policy_decision_types"]),
            "next_allowed_action": "candidate-only design for previously unprojected no-surface-rule mismatches; no adoption or MFA",
        },
        "evidence": {
            "global_projection_manifest": file_fingerprint(global_manifest_path, with_sha256=True),
            "global_projection_audit": file_fingerprint(global_audit_path, with_sha256=True),
            "global_readiness_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "global_readiness_audit": file_fingerprint(readiness_audit_path, with_sha256=True),
            "prior_readiness_manifest": file_fingerprint(
                prior_readiness_manifest_path, with_sha256=True
            ),
        },
    }
    atomic_write_json(output_path, report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--global-manifest", type=Path, required=True)
    result.add_argument("--global-audit", type=Path, required=True)
    result.add_argument("--readiness-manifest", type=Path, required=True)
    result.add_argument("--readiness-audit", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--top-n", type=int, default=12)
    return result


def main() -> int:
    args = parser().parse_args()
    report = summarize(
        global_manifest_path=args.global_manifest.resolve(),
        global_audit_path=args.global_audit.resolve(),
        readiness_manifest_path=args.readiness_manifest.resolve(),
        readiness_audit_path=args.readiness_audit.resolve(),
        output_path=args.output.resolve(),
        top_n=args.top_n,
    )
    print(json.dumps(report["readiness_delta_from_limited_donor"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

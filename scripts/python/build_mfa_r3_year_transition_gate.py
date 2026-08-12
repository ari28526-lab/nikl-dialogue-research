"""Bind one completed r3 year to the next year's audited preflight.

This gate is deliberately aggregate-only: exact-ID inventories stay in their
release-scoped files, while the report records their contracts and SHA-256.
It never starts MFA and never edits a completed year.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso  # noqa: E402


SCHEMA_VERSION = "mfa_r3_year_transition_gate.v2"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object가 아님: {path}")
    return value


def build_gate(
    *,
    prior_year: str,
    next_year: str,
    prior_marker_path: Path,
    prior_qc_path: Path,
    next_input_path: Path,
    next_input_audit_path: Path,
    next_alignment_path: Path,
    next_alignment_audit_path: Path,
    next_research_audit_path: Path,
    next_preflight_path: Path,
    next_marker_path: Path,
    next_database_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    paths = {
        "prior_alignment_marker": prior_marker_path,
        "prior_qc_state": prior_qc_path,
        "next_year_input_contract": next_input_path,
        "next_year_input_audit": next_input_audit_path,
        "next_alignment_contract": next_alignment_path,
        "next_alignment_audit": next_alignment_audit_path,
        "next_research_database_audit": next_research_audit_path,
        "next_runner_preflight": next_preflight_path,
    }
    data = {name: read_json(path) for name, path in paths.items()}
    marker = data["prior_alignment_marker"]
    qc = data["prior_qc_state"]
    year_input = data["next_year_input_contract"]
    input_audit = data["next_year_input_audit"]
    alignment = data["next_alignment_contract"]
    alignment_audit = data["next_alignment_audit"]
    research = data["next_research_database_audit"]
    preflight = data["next_runner_preflight"]
    release_id = str(marker.get("release_id") or "")
    input_id = str(year_input.get("year_input_contract_id") or "")
    alignment_id = str(alignment.get("alignment_contract_id") or "")
    source_db = marker.get("source_db") if isinstance(marker.get("source_db"), dict) else {}
    source_db_path = Path(str(source_db.get("path") or ""))

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    add(
        "prior_alignment_frozen",
        marker.get("schema_version") == "mfa_r3_alignment_done.v1"
        and marker.get("status") == "passed"
        and str(marker.get("year")) == prior_year
        and marker.get("r3_full_realign") is True
        and marker.get("temp_deleted") is False
        and marker.get("database_deleted") is False,
        {"year": marker.get("year"), "alignment_contract_id": marker.get("alignment_contract_id")},
    )
    add(
        "prior_database_retained",
        source_db_path.is_file()
        and source_db_path.stat().st_size == int(source_db.get("bytes", -1))
        and str(source_db.get("sha256") or "")
        == str(qc.get("qc_input", {}).get("source_db_expected_sha256") or ""),
        {"path": str(source_db_path), "bytes": source_db.get("bytes"), "sha256": source_db.get("sha256")},
    )
    qc_counts = qc.get("counts") if isinstance(qc.get("counts"), dict) else {}
    add(
        "prior_independent_qc_frozen",
        qc.get("schema_version") == "mfa_r3_research_qc_state.v1"
        and qc.get("status") == "passed"
        and str(qc.get("year")) == prior_year
        and str(qc.get("release_id") or "") == release_id
        and qc.get("source_mutation_performed") is False
        and qc.get("mfa_recomputed") is False
        and qc.get("full_export_repeated") is False
        and int(qc_counts.get("sample_sessions", 0)) >= 5
        and int(qc_counts.get("sample_semantic_equal", -1)) == int(qc_counts.get("sample_sessions", 0))
        and int(qc_counts.get("sample_byte_equal", -1)) == int(qc_counts.get("sample_sessions", 0)),
        {"checkpoint": qc.get("qc_input_checkpoint_id"), "counts": qc_counts},
    )
    add(
        "next_year_input_audited",
        str(year_input.get("year")) == next_year
        and str(year_input.get("release_id") or "") == release_id
        and bool(input_id)
        and input_audit.get("status")
        == "passed_independent_exact_id_audit_pending_alignment_contract_gate_closed"
        and str(input_audit.get("year")) == next_year
        and input_audit.get("year_input_contract_id") == input_id
        and input_audit.get("verdict", {}).get("exact_id_partition_passed") is True
        and input_audit.get("checks", {}).get("expected_mfa_input_has_wav") is True,
        {"year_input_contract_id": input_id, "counts": input_audit.get("counts")},
    )
    add(
        "next_alignment_audited",
        str(alignment.get("year")) == next_year
        and alignment.get("identity", {}).get("pronunciation_release_id") == release_id
        and alignment.get("identity", {}).get("year_input_contract_id") == input_id
        and bool(alignment_id)
        and alignment_audit.get("status")
        == "passed_independent_identity_audit_pending_runner_and_release_gate"
        and alignment_audit.get("alignment_contract_id") == alignment_id
        and alignment_audit.get("verdict", {}).get("identity_recomputed_exact") is True
        and alignment_audit.get("checks", {}).get("r3_full_realign") is True,
        {"alignment_contract_id": alignment_id, "expected_mfa_input": alignment_audit.get("checks", {}).get("expected_mfa_input")},
    )
    add(
        "next_research_database_audited",
        research.get("schema_version") == "mfa_r3_pronunciation_occurrence_year_audit.v1"
        and research.get("status") == "passed"
        and str(research.get("year")) == next_year
        and research.get("release_id") == release_id
        and research.get("year_input_contract_id") == input_id
        and research.get("verdict", {}).get("all_source_utterances_accounted") is True
        and int(research.get("verdict", {}).get("unknown_nonempty_lab_tokens", -1)) == 0
        and research.get("verdict", {}).get("ready_for_mfa_preflight") is True,
        {"join_key": research.get("post_mfa_join_key"), "counts": research.get("counts")},
    )
    add(
        "next_runner_preflight_go",
        preflight.get("schema_version") == "mfa_r3_year_safe_body_preflight.v1"
        and preflight.get("status") == "go"
        and preflight.get("go") is True
        and str(preflight.get("year")) == next_year
        and preflight.get("release_id") == release_id
        and preflight.get("alignment_contract_id") == alignment_id
        and not preflight.get("failed_checks"),
        {"capacity": preflight.get("capacity"), "failed_checks": preflight.get("failed_checks")},
    )
    add(
        "next_year_not_started",
        not next_marker_path.exists() and not next_database_path.exists(),
        {"marker": str(next_marker_path), "database": str(next_database_path)},
    )
    failed = [row["name"] for row in checks if not row["passed"]]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_ready_for_researcher_start" if not failed else "failed",
        "recorded_at": now_iso(),
        "from_year": prior_year,
        "to_year": next_year,
        "release_id": release_id,
        "checks": checks,
        "failed_checks": failed,
        "from_year_frozen": {
            "alignment_marker": file_fingerprint(prior_marker_path, with_sha256=True),
            "qc_state": file_fingerprint(prior_qc_path, with_sha256=True),
            "source_db_recorded": source_db,
        },
        "to_year_contract": {
            "year_input_contract_id": input_id,
            "alignment_contract_id": alignment_id,
            "expected_mfa_input": input_audit.get("counts", {}).get("expected_mfa_input"),
            "year_input_contract": file_fingerprint(next_input_path, with_sha256=True),
            "year_input_audit": file_fingerprint(next_input_audit_path, with_sha256=True),
            "alignment_contract": file_fingerprint(next_alignment_path, with_sha256=True),
            "alignment_audit": file_fingerprint(next_alignment_audit_path, with_sha256=True),
            "research_database_audit": file_fingerprint(next_research_audit_path, with_sha256=True),
            "runner_preflight": file_fingerprint(next_preflight_path, with_sha256=True),
        },
        "invariants": {
            "prior_year_recomputed": False,
            "prior_year_outputs_modified": False,
            "raw_corpus_modified": False,
            "legacy_r2_db_or_intervals_reused": False,
            "target_mfa_started": False,
            "target_textgrid_started": False,
            "automatic_approval_performed": False,
        },
        "authorization": {
            "researcher_must_start_single_long_running_runner": not failed,
            "simultaneous_duplicate_runner_forbidden": True,
            "on_failure_preserve_corpus_temp_and_database": True,
        },
    }
    atomic_write_json(output_path.resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-year", required=True)
    parser.add_argument("--next-year", required=True)
    parser.add_argument("--prior-marker", type=Path, required=True)
    parser.add_argument("--prior-qc", type=Path, required=True)
    parser.add_argument("--next-input", type=Path, required=True)
    parser.add_argument("--next-input-audit", type=Path, required=True)
    parser.add_argument("--next-alignment", type=Path, required=True)
    parser.add_argument("--next-alignment-audit", type=Path, required=True)
    parser.add_argument("--next-research-audit", type=Path, required=True)
    parser.add_argument("--next-preflight", type=Path, required=True)
    parser.add_argument("--next-marker", type=Path, required=True)
    parser.add_argument("--next-database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_gate(
        prior_year=args.prior_year,
        next_year=args.next_year,
        prior_marker_path=args.prior_marker.resolve(),
        prior_qc_path=args.prior_qc.resolve(),
        next_input_path=args.next_input.resolve(),
        next_input_audit_path=args.next_input_audit.resolve(),
        next_alignment_path=args.next_alignment.resolve(),
        next_alignment_audit_path=args.next_alignment_audit.resolve(),
        next_research_audit_path=args.next_research_audit.resolve(),
        next_preflight_path=args.next_preflight.resolve(),
        next_marker_path=args.next_marker.resolve(),
        next_database_path=args.next_database.resolve(),
        output_path=args.output.resolve(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed_ready_for_researcher_start" else 1


if __name__ == "__main__":
    raise SystemExit(main())

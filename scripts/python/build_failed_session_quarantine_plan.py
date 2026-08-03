"""Quarantine every row in a duration-failed session before main-body MFA.

Duration matches inside a badly failed session can be accidental (for example,
a 48 kHz PCM payload wrapped with a 16 kHz WAV header).  This read-only helper
turns every row of such a session into ``target_unresolved`` while retaining
the existing row-level plan for sessions that passed the session gate.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "wav_failed_session_quarantine_plan.v1"
EXCLUSION_STATUSES = {"ambiguous_short_match", "target_unresolved"}
AUDIO_PAIRING_ISSUES = {
    "duration_residual_mismatch",
    "duration_wav_missing",
    "duration_wav_too_small",
    "wav_header_unreadable",
}


def audit_year(audit: dict[str, object], year: str) -> dict[str, object]:
    values = audit.get("years")
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, list):
        raise RuntimeError("audit years must be an object or list")
    rows = [row for row in values if isinstance(row, dict) and str(row.get("year")) == year]
    if len(rows) != 1:
        raise RuntimeError(f"audit year record must be unique: {year}")
    return rows[0]


def build_plan(
    *,
    year: str,
    audit_row: dict[str, object],
    plan_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    duration_audit = audit_row.get("duration_audit")
    if not isinstance(duration_audit, dict):
        raise RuntimeError("duration audit missing")
    failed_values = duration_audit.get("failed_sessions")
    if not isinstance(failed_values, list):
        raise RuntimeError("failed_sessions must be a list")
    failed_sessions = {
        str(row.get("session") or "").strip()
        for row in failed_values
        if isinstance(row, dict) and str(row.get("session") or "").strip()
    }
    issue_values = audit_row.get("issue_inventory")
    if not isinstance(issue_values, list):
        raise RuntimeError("issue_inventory must be a list")
    active_issue_ids = {
        str(row.get("utt_id") or "").strip()
        for row in issue_values
        if isinstance(row, dict)
        and str(row.get("issue") or "") in AUDIO_PAIRING_ISSUES
        and str(row.get("utt_id") or "").strip()
    }

    output: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    plan_sessions: Counter[str] = Counter()
    base_statuses: Counter[str] = Counter()
    output_statuses: Counter[str] = Counter()
    additional_quarantine = 0
    for raw in plan_rows:
        row = {key: str(value or "") for key, value in raw.items()}
        target = row.get("target_utt_id", "").strip()
        session = row.get("session", "").strip()
        if row.get("year") != year or not session:
            raise RuntimeError(f"plan row identity mismatch: {target!r}")
        if not target:
            if row.get("status") != "source_orphan":
                raise RuntimeError("blank target is allowed only for source_orphan")
            base_statuses[row.get("status", "")] += 1
            output_statuses[row.get("status", "")] += 1
            output.append(row)
            continue
        if target in seen_targets:
            raise RuntimeError(f"duplicate target: {target}")
        seen_targets.add(target)
        plan_sessions[session] += 1
        base_statuses[row.get("status", "")] += 1
        if session in failed_sessions:
            if row.get("status") not in EXCLUSION_STATUSES:
                additional_quarantine += 1
            row.update(
                {
                    "source_utt_id": "",
                    "status": "target_unresolved",
                    "block_length": "0",
                    "source_duration_seconds": "",
                    "duration_residual_seconds": "",
                    "source_wav": "",
                }
            )
        output_statuses[row.get("status", "")] += 1
        output.append(row)

    missing_failed_sessions = sorted(failed_sessions - set(plan_sessions))
    if missing_failed_sessions:
        raise RuntimeError(
            "failed sessions absent from base plan: "
            f"{missing_failed_sessions[:20]}"
        )
    excluded_ids = {
        row["target_utt_id"]
        for row in output
        if row.get("status") in EXCLUSION_STATUSES
    }
    uncovered = sorted(active_issue_ids - excluded_ids)
    if uncovered:
        raise RuntimeError(f"active audio issues not quarantined: {uncovered[:20]}")
    failed_session_rows = sum(plan_sessions[session] for session in failed_sessions)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "dry_run_plan_only",
        "year": year,
        "created_at": now_iso(),
        "mutates_wav": False,
        "approves_exclusions": False,
        "starts_mfa": False,
        "failed_session_count": len(failed_sessions),
        "failed_sessions": sorted(failed_sessions),
        "failed_session_rows": failed_session_rows,
        "active_audio_issue_count": len(active_issue_ids),
        "additional_session_quarantine_count": additional_quarantine,
        "final_audio_exclusion_count": len(excluded_ids),
        "uncovered_audio_issue_count": 0,
        "base_plan_status_counts": dict(sorted(base_statuses.items())),
        "output_plan_status_counts": dict(sorted(output_statuses.items())),
        "safe_to_auto_apply": False,
        "next_step": "범주 요약 연구자 승인 뒤 안전 본체 MFA",
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--base-plan", type=Path, required=True)
    parser.add_argument("--output-plan", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    audit_path = args.audit_report.resolve()
    base_path = args.base_plan.resolve()
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    with base_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    required = {"year", "session", "target_utt_id", "status"}
    if not required <= set(fields):
        raise RuntimeError(f"base plan fields missing: {sorted(required - set(fields))}")
    output, report = build_plan(
        year=str(args.year),
        audit_row=audit_year(audit, str(args.year)),
        plan_rows=rows,
    )
    report["audit_report"] = file_fingerprint(audit_path, with_sha256=True)
    report["base_plan"] = file_fingerprint(base_path, with_sha256=True)
    with atomic_text_writer(
        args.output_plan.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    atomic_write_json(args.output_report.resolve(), report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "year": report["year"],
                "failed_session_count": report["failed_session_count"],
                "failed_session_rows": report["failed_session_rows"],
                "active_audio_issue_count": report["active_audio_issue_count"],
                "additional_session_quarantine_count": report[
                    "additional_session_quarantine_count"
                ],
                "final_audio_exclusion_count": report["final_audio_exclusion_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

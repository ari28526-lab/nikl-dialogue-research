"""Independently audit Stage 19 safe-body/follow-up utterance routing."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import YEARS
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file
from realign_eojeol_build_corpus import form_to_lab


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_pre_adoption_routing_audit.v1"
EXPECTED_STAGE_SCHEMA = "common_pron_r3_pre_adoption_routing.v1"
EXPECTED_STAGE_STATUS = "success_read_only_routing_not_adopted"


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


def classify_readiness(row: dict[str, str]) -> str:
    status = clean(row.get("planning_status"))
    if status.startswith("candidate_"):
        if clean(row.get("planning_zero_fallback_hold")) != "false":
            raise RuntimeError(f"candidate also marked hold: {row['token']}")
        return "candidate"
    if clean(row.get("planning_zero_fallback_hold")) == "true":
        return "hold"
    if clean(row.get("planning_requires_policy_decision")) == "true" or status.startswith("policy_"):
        return "policy"
    raise RuntimeError(f"unclassified readiness token: {row['token']}")


def independent_route(hold: set[str], policy: set[str], unknown: set[str], empty: bool) -> str:
    labels: list[str] = []
    if hold:
        labels.append("hold")
    if policy:
        labels.append("policy")
    if unknown:
        labels.append("unknown")
    if empty:
        labels.append("empty_reference")
    return "+".join(labels) if labels else "safe"


def audit(manifest_path: Path, output_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != EXPECTED_STAGE_SCHEMA or manifest.get("status") != EXPECTED_STAGE_STATUS:
        raise RuntimeError("Stage 19 manifest identity differs")
    if any(
        manifest["scope"].get(key) is not False
        for key in ("adoption_performed", "annual_mfa_started", "textgrids_modified", "source_files_modified")
    ):
        raise RuntimeError("Stage 19 scope exceeds read-only routing")

    readiness_path = Path(str(manifest["inputs"]["readiness_v4"]["path"])).resolve()
    blocked_path = Path(str(manifest["outputs"]["blocked_utterance_routing"]["path"])).resolve()
    token_path = Path(str(manifest["outputs"]["followup_token_observations"]["path"])).resolve()
    year_path = Path(str(manifest["outputs"]["year_routing_summary"]["path"])).resolve()
    meta_path = Path(str(manifest["inputs"]["search_master_build_meta"]["path"])).resolve()
    search_root = Path(str(manifest["inputs"]["search_master_inventory"]["root"])).resolve()
    verify(manifest["inputs"]["readiness_v4"], readiness_path, "readiness v4")
    verify(manifest["outputs"]["blocked_utterance_routing"], blocked_path, "blocked routing")
    verify(manifest["outputs"]["followup_token_observations"], token_path, "followup tokens")
    verify(manifest["outputs"]["year_routing_summary"], year_path, "year summary")
    verify(manifest["inputs"]["search_master_build_meta"], meta_path, "search meta")

    states: dict[str, str] = {}
    expected_occurrences: dict[str, int] = {}
    state_types: Counter[str] = Counter()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            token = row["token"]
            state = classify_readiness(row)
            states[token] = state
            expected_occurrences[token] = int(row["total_occurrences"])
            state_types[state] += 1
    if len(states) != 881237 or dict(state_types) != {"candidate": 795804, "hold": 85398, "policy": 35}:
        raise RuntimeError("readiness state accounting differs")

    files = [path for year in YEARS for path in sorted((search_root / year).glob("*.csv"))]
    if len(files) != 17156:
        raise RuntimeError("pre-MFA CSV inventory differs")
    totals: Counter[str] = Counter()
    routes: Counter[str] = Counter()
    years: dict[str, Counter[str]] = defaultdict(Counter)
    token_years: dict[str, Counter[str]] = defaultdict(Counter)

    with gzip.open(blocked_path, "rt", encoding="utf-8-sig", newline="") as blocked_stream:
        blocked_reader = csv.DictReader(blocked_stream)
        current_blocked = next(blocked_reader, None)
        for index, source_path in enumerate(files, 1):
            relative = source_path.relative_to(search_root).as_posix()
            with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    year = clean(row["year"])
                    lab = form_to_lab(row["pron_reference_form"])
                    forms = lab.split() if lab else []
                    source_n = int(clean(row["pron_reference_n_eojeol"]) or 0)
                    if source_n < len(forms):
                        raise RuntimeError(f"tokenizer expanded eojeol: {row['utt_id']}")
                    hold = {token for token in forms if states.get(token) == "hold"}
                    policy = {token for token in forms if states.get(token) == "policy"}
                    unknown = {token for token in forms if token not in states}
                    route = independent_route(hold, policy, unknown, not forms)
                    totals["utterances"] += 1
                    totals["pron_reference_eojeol"] += source_n
                    totals["lab_eojeol"] += len(forms)
                    year_count = years[year]
                    year_count["utterances"] += 1
                    year_count["pron_reference_eojeol"] += source_n
                    year_count["lab_eojeol"] += len(forms)
                    year_count["tokenizer_removed_eojeol"] += source_n - len(forms)
                    for token in forms:
                        state = states.get(token, "unknown")
                        totals[f"{state}_eojeol"] += 1
                        year_count[f"{state}_eojeol"] += 1
                        if state in {"hold", "policy"}:
                            token_years[token][year] += 1
                    if route == "safe":
                        totals["safe_utterances"] += 1
                        year_count["safe_utterances"] += 1
                        continue
                    totals["blocked_utterances"] += 1
                    year_count["blocked_utterances"] += 1
                    routes[route] += 1
                    if unknown:
                        year_count["unknown_involved_utterances"] += 1
                    elif not forms:
                        year_count["empty_reference_utterances"] += 1
                    elif hold and policy:
                        year_count["hold_and_policy_utterances"] += 1
                    elif hold:
                        year_count["hold_only_utterances"] += 1
                    else:
                        year_count["policy_only_utterances"] += 1
                    if current_blocked is None:
                        raise RuntimeError("blocked routing output ended early")
                    expected_row = {
                        "year": year,
                        "utt_id": row["utt_id"],
                        "source_csv": relative,
                        "pron_reference_status": row["pron_reference_status"],
                        "pron_reference_n_eojeol": str(source_n),
                        "lab_n_eojeol": str(len(forms)),
                        "routing_class": route,
                        "hold_tokens_json": json.dumps(sorted(hold), ensure_ascii=False),
                        "policy_tokens_json": json.dumps(sorted(policy), ensure_ascii=False),
                        "unknown_tokens_json": json.dumps(sorted(unknown), ensure_ascii=False),
                        "safe_body_included": "false",
                        "followup_required": "true",
                    }
                    if any(clean(current_blocked.get(key)) != clean(value) for key, value in expected_row.items()):
                        raise RuntimeError(f"blocked routing row differs: {row['utt_id']}")
                    current_blocked = next(blocked_reader, None)
            if index % 2000 == 0:
                print(f"[Stage19 audit] {index:,}/{len(files):,} CSV", flush=True)
        if current_blocked is not None:
            raise RuntimeError("blocked routing output has extra rows")

    expected_counts = manifest["counts"]
    count_checks = {
        "utterances": totals["utterances"],
        "pron_reference_eojeol": totals["pron_reference_eojeol"],
        "lab_eojeol": totals["lab_eojeol"],
        "tokenizer_removed_eojeol": totals["pron_reference_eojeol"] - totals["lab_eojeol"],
        "safe_utterances": totals["safe_utterances"],
        "blocked_utterances": totals["blocked_utterances"],
    }
    if any(int(expected_counts[key]) != value for key, value in count_checks.items()):
        raise RuntimeError("Stage 19 manifest count differs from independent scan")
    if dict(routes) != expected_counts["routing_class_utterances"]:
        raise RuntimeError("routing class accounting differs")
    if totals["unknown_eojeol"] != 0:
        raise RuntimeError("unknown token leaked into frozen readiness")

    with gzip.open(token_path, "rt", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected_tokens = sorted(token for token, state in states.items() if state in {"hold", "policy"})
    if [row["token"] for row in rows] != expected_tokens:
        raise RuntimeError("followup token inventory differs")
    for row in rows:
        token = row["token"]
        year_counts = token_years[token]
        if (
            row["readiness_state"] != states[token]
            or int(row["expected_occurrences"]) != expected_occurrences[token]
            or int(row["observed_occurrences"]) != sum(year_counts.values())
            or any(int(row[f"count_{year}"]) != year_counts[year] for year in YEARS)
        ):
            raise RuntimeError(f"followup token occurrence differs: {token}")

    with year_path.open("r", encoding="utf-8-sig", newline="") as stream:
        year_rows = {row["year"]: row for row in csv.DictReader(stream)}
    if set(year_rows) != set(YEARS):
        raise RuntimeError("year summary coverage differs")
    integer_fields = (
        "utterances", "pron_reference_eojeol", "lab_eojeol", "tokenizer_removed_eojeol",
        "safe_utterances", "blocked_utterances", "hold_only_utterances",
        "policy_only_utterances", "hold_and_policy_utterances",
        "unknown_involved_utterances", "empty_reference_utterances", "candidate_eojeol",
        "hold_eojeol", "policy_eojeol", "unknown_eojeol",
    )
    for year in YEARS:
        row = year_rows[year]
        if any(int(row[field]) != years[year][field] for field in integer_fields):
            raise RuntimeError(f"year summary differs: {year}")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_independent_full_scan",
        "recorded_at": now_iso(),
        "inputs": {
            "stage19_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "readiness_v4": file_fingerprint(readiness_path, with_sha256=True),
            "blocked_routing": file_fingerprint(blocked_path, with_sha256=True),
            "followup_tokens": file_fingerprint(token_path, with_sha256=True),
            "year_summary": file_fingerprint(year_path, with_sha256=True),
        },
        "checks": {
            "all_source_rows_rescanned": True,
            "blocked_rows_exact_identity": True,
            "no_safe_utterance_contains_hold_policy_unknown_or_empty": True,
            "readiness_occurrences_match": True,
            "followup_token_year_counts_match": True,
            "year_summary_matches": True,
            "unknown_eojeol": totals["unknown_eojeol"],
        },
        "counts": {**count_checks, "routing_class_utterances": dict(routes)},
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage19-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.stage19_manifest.resolve(), args.output.resolve())
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

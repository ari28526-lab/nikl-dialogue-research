"""Route search-master utterances by readiness-v4 candidate/hold/policy state."""

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
from build_common_pron_r3_selection_readiness_v3 import OUTPUT_FIELDS  # noqa: E402
from build_common_pron_r3_selection_readiness_v4 import (  # noqa: E402
    SCHEMA_VERSION as READINESS_SCHEMA,
    STATUS as READINESS_STATUS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from realign_eojeol_build_corpus import form_to_lab  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_pre_adoption_routing.v1"
POLICY_SCHEMA = "common_pron_r3_pre_adoption_routing_policy.v1"
STATUS = "success_read_only_routing_not_adopted"
SEARCH_REQUIRED_FIELDS = (
    "utt_id",
    "year",
    "pron_reference_form",
    "pron_reference_n_eojeol",
    "pron_reference_status",
)
BLOCKED_FIELDS = (
    "year",
    "utt_id",
    "source_csv",
    "pron_reference_status",
    "pron_reference_n_eojeol",
    "lab_n_eojeol",
    "routing_class",
    "hold_tokens_json",
    "policy_tokens_json",
    "unknown_tokens_json",
    "safe_body_included",
    "followup_required",
)
TOKEN_FIELDS = (
    "token",
    "readiness_state",
    "expected_occurrences",
    "observed_occurrences",
    *(f"count_{year}" for year in YEARS),
    "example_utt_ids_json",
    "followup_required",
)
YEAR_FIELDS = (
    "year",
    "search_master_csv_files",
    "utterances",
    "pron_reference_eojeol",
    "lab_eojeol",
    "tokenizer_removed_eojeol",
    "safe_utterances",
    "blocked_utterances",
    "hold_only_utterances",
    "policy_only_utterances",
    "hold_and_policy_utterances",
    "unknown_involved_utterances",
    "empty_reference_utterances",
    "candidate_eojeol",
    "hold_eojeol",
    "policy_eojeol",
    "unknown_eojeol",
    "safe_utterance_percent",
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


def validate_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "read_only_routing_audit"
        or tuple(str(item) for item in policy.get("scope_years", ())) != YEARS
    ):
        raise RuntimeError("Stage 19 routing policy identity differs")
    required = {
        "expected_readiness_types": 881237,
        "expected_readiness_occurrences": 27847068,
        "expected_candidate_types": 795804,
        "expected_candidate_occurrences": 27043261,
        "expected_hold_types": 85398,
        "expected_hold_occurrences": 803644,
        "expected_policy_types": 35,
        "expected_policy_occurrences": 163,
        "expected_search_master_csv_files": 17156,
        "expected_search_master_utterances": 5103356,
        "expected_search_master_eojeol": 27847068,
        "expected_unknown_eojeol": 0,
    }
    contract = policy.get("input_contract", {})
    if any(int(contract.get(key, -1)) != value for key, value in required.items()):
        raise RuntimeError("Stage 19 routing input contract differs")
    required_text = {
        "expected_search_master_run_id": "pre_mfa_v1_20260725",
        "source_field": "pron_reference_form",
        "source_eojeol_count_field": "pron_reference_n_eojeol",
        "tokenizer": "realign_eojeol_build_corpus.form_to_lab",
    }
    if any(clean(contract.get(key)) != value for key, value in required_text.items()):
        raise RuntimeError("Stage 19 routing text contract differs")
    if any(value is not True for value in policy.get("routing_policy", {}).values()):
        raise RuntimeError("Stage 19 routing policy differs")
    if any(value is not False for value in policy.get("invariants", {}).values()):
        raise RuntimeError("Stage 19 routing policy exceeds read-only scope")
    return policy


def readiness_state(row: dict[str, str]) -> str:
    if row["planning_status"].startswith("candidate_"):
        if row["planning_zero_fallback_hold"] != "false":
            raise RuntimeError(f"candidate is also a hold: {row['token']}")
        return "candidate"
    if row["planning_zero_fallback_hold"] == "true":
        return "hold"
    if row["planning_requires_policy_decision"] == "true" or row["planning_status"].startswith("policy_"):
        return "policy"
    raise RuntimeError(f"unclassified readiness row: {row['token']}")


def routing_class(
    hold: set[str], policy: set[str], unknown: set[str], *, empty_reference: bool = False
) -> str:
    labels = []
    if hold:
        labels.append("hold")
    if policy:
        labels.append("policy")
    if unknown:
        labels.append("unknown")
    if empty_reference:
        labels.append("empty_reference")
    return "+".join(labels) if labels else "safe"


def build(
    *, readiness_manifest_path: Path, search_master_root: Path,
    policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        manifest_path = output_root / "PRE_ADOPTION_ROUTING_MANIFEST.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"Stage 19 root exists without manifest: {output_root}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != STATUS:
            raise RuntimeError("existing Stage 19 routing differs")
        return manifest
    policy = validate_policy(policy_path)
    contract = policy["input_contract"]
    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    if readiness_manifest.get("schema_version") != READINESS_SCHEMA or readiness_manifest.get("status") != READINESS_STATUS:
        raise RuntimeError("readiness v4 identity differs")
    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v4"]["path"])).resolve()
    verify(readiness_manifest["outputs"]["selection_readiness_v4"], readiness_path, label="readiness v4")
    states: dict[str, str] = {}
    expected_occurrences: dict[str, int] = {}
    state_types: Counter[str] = Counter()
    state_occurrences: Counter[str] = Counter()
    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != OUTPUT_FIELDS:
            raise RuntimeError("readiness v4 columns differ")
        for row in reader:
            token = row["token"]
            if token in states:
                raise RuntimeError(f"duplicate readiness token: {token}")
            state = readiness_state(row)
            occurrences = int(row["total_occurrences"])
            states[token] = state
            expected_occurrences[token] = occurrences
            state_types[state] += 1
            state_occurrences[state] += occurrences
    expected_state_types = {
        "candidate": int(contract["expected_candidate_types"]),
        "hold": int(contract["expected_hold_types"]),
        "policy": int(contract["expected_policy_types"]),
    }
    expected_state_occurrences = {
        "candidate": int(contract["expected_candidate_occurrences"]),
        "hold": int(contract["expected_hold_occurrences"]),
        "policy": int(contract["expected_policy_occurrences"]),
    }
    if len(states) != int(contract["expected_readiness_types"]) or dict(state_types) != expected_state_types:
        raise RuntimeError("readiness state type accounting differs")
    if dict(state_occurrences) != expected_state_occurrences:
        raise RuntimeError("readiness state occurrence accounting differs")

    meta_path = search_master_root / "_build_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if (
        meta.get("status") != "success"
        or clean(meta.get("run_id")) != clean(contract["expected_search_master_run_id"])
    ):
        raise RuntimeError("pre-MFA search master identity differs")
    files = [
        path for year in YEARS
        for path in sorted((search_master_root / year).glob("*.csv"))
    ]
    if len(files) != int(contract["expected_search_master_csv_files"]):
        raise RuntimeError("search master file count differs")
    source_inventory = source_inventory_digest(files, search_master_root)

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    blocked_temp = temp_root / "blocked_utterance_routing.csv.gz"
    token_temp = temp_root / "followup_token_observations.csv.gz"
    year_temp = temp_root / "year_routing_summary.csv"
    blocked_final = output_root / blocked_temp.name
    token_final = output_root / token_temp.name
    year_final = output_root / year_temp.name

    year_counts: dict[str, Counter[str]] = defaultdict(Counter)
    observed: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[str]] = defaultdict(list)
    total_utterances = total_eojeol = total_reference_eojeol = 0
    blocked_utterances = safe_utterances = 0
    routing_counts: Counter[str] = Counter()
    with gzip_writer(blocked_temp) as blocked_stream:
        writer = csv.DictWriter(blocked_stream, fieldnames=BLOCKED_FIELDS, lineterminator="\n")
        writer.writeheader()
        for file_index, path in enumerate(files, 1):
            relative = path.relative_to(search_master_root).as_posix()
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not set(SEARCH_REQUIRED_FIELDS).issubset(reader.fieldnames or ()):
                    raise RuntimeError(f"search master columns differ: {path}")
                for row in reader:
                    year = clean(row["year"])
                    if year not in YEARS:
                        raise RuntimeError(f"unexpected search year: {year}")
                    lab_text = form_to_lab(row["pron_reference_form"])
                    forms = lab_text.split() if lab_text else []
                    expected = int(clean(row["pron_reference_n_eojeol"]) or 0)
                    if expected < len(forms):
                        raise RuntimeError(
                            "MFA tokenizer created more eojeol than pron_reference_n_eojeol: "
                            f"{row['utt_id']} expected={expected} observed={len(forms)}"
                        )
                    hold = {token for token in forms if states.get(token) == "hold"}
                    policy_tokens = {token for token in forms if states.get(token) == "policy"}
                    unknown = {token for token in forms if token not in states}
                    empty_reference = not forms
                    route = routing_class(
                        hold,
                        policy_tokens,
                        unknown,
                        empty_reference=empty_reference,
                    )
                    total_utterances += 1
                    total_eojeol += len(forms)
                    total_reference_eojeol += expected
                    counts = year_counts[year]
                    counts["utterances"] += 1
                    counts["pron_reference_eojeol"] += expected
                    counts["lab_eojeol"] += len(forms)
                    counts["tokenizer_removed_eojeol"] += expected - len(forms)
                    for token in forms:
                        state = states.get(token, "unknown")
                        counts[f"{state}_eojeol"] += 1
                        if state in {"hold", "policy"}:
                            observed[token][year] += 1
                            if len(examples[token]) < 5:
                                examples[token].append(row["utt_id"])
                    if route == "safe":
                        safe_utterances += 1
                        counts["safe_utterances"] += 1
                        continue
                    blocked_utterances += 1
                    counts["blocked_utterances"] += 1
                    routing_counts[route] += 1
                    if unknown:
                        counts["unknown_involved_utterances"] += 1
                    elif empty_reference:
                        counts["empty_reference_utterances"] += 1
                    elif hold and policy_tokens:
                        counts["hold_and_policy_utterances"] += 1
                    elif hold:
                        counts["hold_only_utterances"] += 1
                    elif policy_tokens:
                        counts["policy_only_utterances"] += 1
                    writer.writerow(
                        {
                            "year": year,
                            "utt_id": row["utt_id"],
                            "source_csv": relative,
                            "pron_reference_status": row["pron_reference_status"],
                            "pron_reference_n_eojeol": expected,
                            "lab_n_eojeol": len(forms),
                            "routing_class": route,
                            "hold_tokens_json": json.dumps(sorted(hold), ensure_ascii=False),
                            "policy_tokens_json": json.dumps(sorted(policy_tokens), ensure_ascii=False),
                            "unknown_tokens_json": json.dumps(sorted(unknown), ensure_ascii=False),
                            "safe_body_included": "false",
                            "followup_required": "true",
                        }
                    )
            if file_index % 1000 == 0:
                print(f"[Stage19] {file_index:,}/{len(files):,} CSV; {total_utterances:,} utterances", flush=True)

    if total_utterances != int(contract["expected_search_master_utterances"]):
        raise RuntimeError("search master utterance count differs")
    if total_eojeol != int(contract["expected_search_master_eojeol"]):
        raise RuntimeError(
            "pre-MFA search master eojeol count differs: "
            f"expected={int(contract['expected_search_master_eojeol']):,} "
            f"observed={total_eojeol:,}"
        )
    observed_state_occurrences = {
        state: sum(year_counts[year][f"{state}_eojeol"] for year in YEARS)
        for state in ("candidate", "hold", "policy", "unknown")
    }
    if observed_state_occurrences["unknown"] != int(contract["expected_unknown_eojeol"]):
        raise RuntimeError("unknown search-master eojeol detected")
    if {
        state: observed_state_occurrences[state] for state in ("candidate", "hold", "policy")
    } != expected_state_occurrences:
        raise RuntimeError("readiness/search-master occurrence identity differs")

    with gzip_writer(token_temp) as stream:
        writer = csv.DictWriter(stream, fieldnames=TOKEN_FIELDS, lineterminator="\n")
        writer.writeheader()
        for token in sorted(token for token, state in states.items() if state in {"hold", "policy"}):
            years = observed[token]
            writer.writerow(
                {
                    "token": token,
                    "readiness_state": states[token],
                    "expected_occurrences": expected_occurrences[token],
                    "observed_occurrences": sum(years.values()),
                    **{f"count_{year}": years[year] for year in YEARS},
                    "example_utt_ids_json": json.dumps(examples[token], ensure_ascii=False),
                    "followup_required": "true",
                }
            )

    with year_temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=YEAR_FIELDS, lineterminator="\n")
        writer.writeheader()
        for year in YEARS:
            counts = year_counts[year]
            writer.writerow(
                {
                    "year": year,
                    "search_master_csv_files": sum(path.parent.name == year for path in files),
                    "utterances": counts["utterances"],
                    "pron_reference_eojeol": counts["pron_reference_eojeol"],
                    "lab_eojeol": counts["lab_eojeol"],
                    "tokenizer_removed_eojeol": counts["tokenizer_removed_eojeol"],
                    "safe_utterances": counts["safe_utterances"],
                    "blocked_utterances": counts["blocked_utterances"],
                    "hold_only_utterances": counts["hold_only_utterances"],
                    "policy_only_utterances": counts["policy_only_utterances"],
                    "hold_and_policy_utterances": counts["hold_and_policy_utterances"],
                    "unknown_involved_utterances": counts["unknown_involved_utterances"],
                    "empty_reference_utterances": counts["empty_reference_utterances"],
                    "candidate_eojeol": counts["candidate_eojeol"],
                    "hold_eojeol": counts["hold_eojeol"],
                    "policy_eojeol": counts["policy_eojeol"],
                    "unknown_eojeol": counts["unknown_eojeol"],
                    "safe_utterance_percent": round(100 * counts["safe_utterances"] / counts["utterances"], 6),
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "scope": {
            "safe_body_definition": "every pron_reference_form lab eojeol candidate-ready in readiness v4",
            "routing_source_field": contract["source_field"],
            "routing_tokenizer": contract["tokenizer"],
            "followup_is_deferred_not_deleted": True,
            **policy["invariants"],
        },
        "inputs": {
            "readiness_v4_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "readiness_v4": file_fingerprint(readiness_path, with_sha256=True),
            "policy_contract": file_fingerprint(policy_path, with_sha256=True),
            "search_master_build_meta": file_fingerprint(meta_path, with_sha256=True),
            "search_master_inventory": source_inventory,
        },
        "counts": {
            "search_master_csv_files": len(files),
            "utterances": total_utterances,
            "pron_reference_eojeol": total_reference_eojeol,
            "lab_eojeol": total_eojeol,
            "tokenizer_removed_eojeol": total_reference_eojeol - total_eojeol,
            "safe_utterances": safe_utterances,
            "blocked_utterances": blocked_utterances,
            "safe_utterance_percent": round(100 * safe_utterances / total_utterances, 6),
            "routing_class_utterances": dict(sorted(routing_counts.items())),
            "readiness_state_types": dict(sorted(state_types.items())),
            "readiness_state_occurrences": dict(sorted(state_occurrences.items())),
            "observed_state_occurrences": dict(sorted(observed_state_occurrences.items())),
            "followup_token_types": state_types["hold"] + state_types["policy"],
        },
        "outputs": {
            "blocked_utterance_routing": fingerprint_for_final(blocked_temp, blocked_final),
            "followup_token_observations": fingerprint_for_final(token_temp, token_final),
            "year_routing_summary": fingerprint_for_final(year_temp, year_final),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "PRE_ADOPTION_ROUTING_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness-v4-manifest", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "common_pron_r3_pre_adoption_routing_v1.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(
        readiness_manifest_path=args.readiness_v4_manifest.resolve(),
        search_master_root=args.search_master_root.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

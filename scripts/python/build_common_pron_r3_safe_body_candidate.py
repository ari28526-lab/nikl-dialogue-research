"""Materialize the audited r3 safe-body pronunciation candidate, without adoption."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import acoustic_phone_inventory
from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_safe_body_candidate.v1"
POLICY_SCHEMA = "common_pron_r3_safe_body_candidate_policy.v1"
STATUS = "passed_candidate_only_not_adopted"
PROJECTION_FIELDS = (
    "token", "variant_index", "variant_count", "pron_phones_mfa", "pron_roman",
    "planning_status", "planning_source", "planning_reason", "total_occurrences",
    "count_2020", "count_2021", "count_2022", "count_2023", "count_2024", "count_2025",
    "candidate_only", "final_selection", "adopted",
)


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


def fingerprint_for_final(temp: Path, final: Path) -> dict[str, object]:
    record = file_fingerprint(temp, with_sha256=True)
    record["path"] = str(final.resolve())
    return record


@contextmanager
def gzip_writer(path: Path) -> Iterator[TextIO]:
    with gzip.open(path, "xt", encoding="utf-8-sig", newline="", compresslevel=6) as stream:
        yield stream


def parse_variants(row: dict[str, str]) -> tuple[list[str], list[str]]:
    phones = json.loads(row["planning_candidate_phones_json"] or "[]")
    roman = json.loads(row["planning_candidate_roman_json"] or "[]")
    expected = int(row["planning_candidate_variant_count"] or 0)
    if (
        not isinstance(phones, list)
        or not isinstance(roman, list)
        or expected < 1
        or len(phones) != expected
        or len(roman) != expected
        or any(not clean(value) for value in phones + roman)
        or len(set(map(clean, phones))) != expected
    ):
        raise RuntimeError(f"invalid candidate variants: {row['token']}")
    return [clean(value) for value in phones], [clean(value) for value in roman]


def build(
    *, readiness_manifest_path: Path, routing_manifest_path: Path,
    routing_audit_path: Path, decision_audit_path: Path, frozen_pin_path: Path,
    release_gate_path: Path, policy_path: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        existing = output_root / "SAFE_BODY_CANDIDATE_MANIFEST.json"
        if not existing.is_file():
            raise RuntimeError(f"candidate root exists without manifest: {output_root}")
        result = json.loads(existing.read_text(encoding="utf-8-sig"))
        if result.get("schema_version") != SCHEMA_VERSION or result.get("status") != STATUS:
            raise RuntimeError("existing safe-body candidate differs")
        return result

    policy = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    if policy.get("schema_version") != POLICY_SCHEMA or policy.get("status") != "candidate_only_not_adopted":
        raise RuntimeError("safe-body candidate policy identity differs")
    if any(value is not False for key, value in policy["gates"].items() if key.startswith("allow_")):
        raise RuntimeError("candidate policy improperly enables a downstream action")
    if policy["gates"].get("candidate_is_final_selection") is not False:
        raise RuntimeError("candidate policy claims final selection")

    readiness_manifest = json.loads(readiness_manifest_path.read_text(encoding="utf-8-sig"))
    routing_manifest = json.loads(routing_manifest_path.read_text(encoding="utf-8-sig"))
    routing_audit = json.loads(routing_audit_path.read_text(encoding="utf-8-sig"))
    decision_audit = json.loads(decision_audit_path.read_text(encoding="utf-8-sig"))
    pin = json.loads(frozen_pin_path.read_text(encoding="utf-8-sig"))
    release_gate = json.loads(release_gate_path.read_text(encoding="utf-8-sig"))
    if routing_manifest.get("status") != "success_read_only_routing_not_adopted":
        raise RuntimeError("Stage 19 routing is not ready")
    if routing_audit.get("status") != "passed_independent_full_scan":
        raise RuntimeError("Stage 19 independent audit is not passed")
    if decision_audit.get("status") != "no_reusable_decisions_found":
        raise RuntimeError("policy decision reuse state differs")
    if release_gate.get("status") != "blocked_pending_r3" or release_gate.get("allowed_release_ids"):
        raise RuntimeError("project adoption gate unexpectedly open")
    if pin.get("status") != "passed":
        raise RuntimeError("frozen model pin is not passed")

    readiness_path = Path(str(readiness_manifest["outputs"]["selection_readiness_v4"]["path"])).resolve()
    verify(readiness_manifest["outputs"]["selection_readiness_v4"], readiness_path, "readiness v4")
    acoustic_path = Path(str(pin["models"]["acoustic_model"]["path"])).resolve()
    verify(pin["models"]["acoustic_model"], acoustic_path, "frozen acoustic model")
    # The frozen pin hashes the 107 phones stored in acoustic meta.json.
    # The legacy loader adds sil/spn for dictionary validation convenience;
    # neither may occur inside a lexical candidate pronunciation here.
    inventory = acoustic_phone_inventory(acoustic_path) - {"sil", "spn"}
    inventory_sha = hashlib.sha256(("\n".join(sorted(inventory)) + "\n").encode("utf-8")).hexdigest()
    expected = policy["expected"]
    if len(inventory) != int(expected["acoustic_phone_count"]) or inventory_sha != expected["acoustic_phone_sorted_sha256"]:
        raise RuntimeError("frozen acoustic phone inventory differs")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    projection_temp = temp_root / "safe_body_candidate_projection.csv.gz"
    dictionary_temp = temp_root / "common_pron_r3_safe_body_candidate.NOT_ADOPTED.dict"
    projection_final = output_root / projection_temp.name
    dictionary_final = output_root / dictionary_temp.name
    type_count = occurrence_count = dictionary_rows = 0
    variant_distribution: Counter[int] = Counter()
    status_types: Counter[str] = Counter()
    outside: set[str] = set()
    lexical_special: set[str] = set()

    with gzip.open(readiness_path, "rt", encoding="utf-8-sig", newline="") as source, gzip_writer(projection_temp) as projection, dictionary_temp.open("x", encoding="utf-8", newline="\n") as dictionary:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(projection, fieldnames=PROJECTION_FIELDS, lineterminator="\n")
        writer.writeheader()
        previous = ""
        for row in reader:
            status = row["planning_status"]
            if not status.startswith("candidate_"):
                continue
            token = row["token"]
            if previous and token <= previous:
                raise RuntimeError("candidate tokens are not strictly sorted")
            previous = token
            if row["planning_zero_fallback_hold"] != "false" or row["planning_is_final_selection"] != "false":
                raise RuntimeError(f"candidate readiness flags differ: {token}")
            phones_list, roman_list = parse_variants(row)
            type_count += 1
            occurrence_count += int(row["total_occurrences"])
            variant_distribution[len(phones_list)] += 1
            status_types[status] += 1
            for variant_index, (phones, roman) in enumerate(zip(phones_list, roman_list), 1):
                phone_set = set(phones.split())
                outside.update(phone_set - inventory)
                lexical_special.update(phone_set & {"sil", "spn"})
                dictionary.write(f"{token}\t{phones}\n")
                dictionary_rows += 1
                writer.writerow(
                    {
                        "token": token,
                        "variant_index": variant_index,
                        "variant_count": len(phones_list),
                        "pron_phones_mfa": phones,
                        "pron_roman": roman,
                        "planning_status": status,
                        "planning_source": row["planning_source"],
                        "planning_reason": row["planning_reason"],
                        "total_occurrences": row["total_occurrences"],
                        **{f"count_{year}": row[f"count_{year}"] for year in range(2020, 2026)},
                        "candidate_only": "true",
                        "final_selection": "false",
                        "adopted": "false",
                    }
                )
    if type_count != int(expected["candidate_types"]) or occurrence_count != int(expected["candidate_occurrences"]):
        raise RuntimeError("candidate readiness accounting differs")
    if outside or lexical_special:
        raise RuntimeError(f"candidate phone gate failed: outside={sorted(outside)} special={sorted(lexical_special)}")

    contract_material = {
        "release_id": policy["release_id"],
        "readiness_sha256": sha256_file(readiness_path),
        "routing_manifest_sha256": sha256_file(routing_manifest_path),
        "routing_audit_sha256": sha256_file(routing_audit_path),
        "decision_audit_sha256": sha256_file(decision_audit_path),
        "frozen_acoustic_sha256": sha256_file(acoustic_path),
        "policy_sha256": sha256_file(policy_path),
    }
    contract_id = hashlib.sha256(json.dumps(contract_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "release_id": policy["release_id"],
        "candidate_contract_id": contract_id,
        "scope": {
            "candidate_only": True,
            "final_selection": False,
            "adopted": False,
            "allow_yearly_mfa": False,
            "allow_textgrid_materialization": False,
            "safe_body_definition": routing_manifest["scope"]["safe_body_definition"],
            "actual_realization_claimed": False,
        },
        "inputs": {
            "readiness_v4_manifest": file_fingerprint(readiness_manifest_path, with_sha256=True),
            "readiness_v4": file_fingerprint(readiness_path, with_sha256=True),
            "routing_manifest": file_fingerprint(routing_manifest_path, with_sha256=True),
            "routing_audit": file_fingerprint(routing_audit_path, with_sha256=True),
            "policy_decision_reuse_audit": file_fingerprint(decision_audit_path, with_sha256=True),
            "frozen_model_pin": file_fingerprint(frozen_pin_path, with_sha256=True),
            "frozen_acoustic_model": file_fingerprint(acoustic_path, with_sha256=True),
            "project_release_gate": file_fingerprint(release_gate_path, with_sha256=True),
            "policy": file_fingerprint(policy_path, with_sha256=True),
        },
        "counts": {
            "candidate_types": type_count,
            "candidate_occurrences": occurrence_count,
            "dictionary_rows": dictionary_rows,
            "variant_count_distribution": {str(key): value for key, value in sorted(variant_distribution.items())},
            "planning_status_types": dict(sorted(status_types.items())),
            "safe_utterances": routing_manifest["counts"]["safe_utterances"],
            "blocked_utterances": routing_manifest["counts"]["blocked_utterances"],
            "hold_types": expected["hold_types"],
            "policy_types": expected["policy_types"],
            "phones_outside_inventory": 0,
            "lexical_sil_or_spn": 0,
        },
        "model_contract": {
            "phone_count": len(inventory),
            "phone_sorted_sha256": inventory_sha,
        },
        "outputs": {
            "candidate_projection": fingerprint_for_final(projection_temp, projection_final),
            "candidate_dictionary_not_adopted": fingerprint_for_final(dictionary_temp, dictionary_final),
        },
        "remaining_gates": [
            "resolve or explicitly decide every zero-fallback hold and policy type before full adoption",
            "materialize a final selected table for all 881237 observed types",
            "pass byte-equivalence and targeted regression gates",
            "open the project pronunciation release gate explicitly",
        ],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "SAFE_BODY_CANDIDATE_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness-manifest", type=Path, required=True)
    parser.add_argument("--routing-manifest", type=Path, required=True)
    parser.add_argument("--routing-audit", type=Path, required=True)
    parser.add_argument("--decision-audit", type=Path, required=True)
    parser.add_argument("--frozen-pin", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, default=PROJECT_ROOT / "config" / "mfa_pronunciation_release_gate.json")
    parser.add_argument("--policy", type=Path, default=PROJECT_ROOT / "config" / "common_pron_r3_safe_body_candidate_v1.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        readiness_manifest_path=args.readiness_manifest.resolve(),
        routing_manifest_path=args.routing_manifest.resolve(),
        routing_audit_path=args.routing_audit.resolve(),
        decision_audit_path=args.decision_audit.resolve(),
        frozen_pin_path=args.frozen_pin.resolve(),
        release_gate_path=args.release_gate.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps({"candidate_contract_id": result["candidate_contract_id"], **result["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

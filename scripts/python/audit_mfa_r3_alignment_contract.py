"""Independently audit a materialized r3 alignment contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SCHEMA = "mfa_r3_alignment_contract.v1"
CONTRACT_STATUS = "materialized_pending_runner_preflight_and_release_gate"
SCHEMA_VERSION = "mfa_r3_alignment_contract_audit.v1"
STATUS = "passed_independent_identity_audit_pending_runner_and_release_gate"


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(record: Mapping[str, object], path: Path, label: str) -> None:
    if (
        Path(clean(record.get("path"))).resolve() != path.resolve()
        or not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def independent_identity(contract: Mapping[str, object]) -> dict:
    identity = contract.get("identity")
    if not isinstance(identity, Mapping):
        raise RuntimeError("r3 alignment identity missing")
    keys = (
        "pronunciation_release_id",
        "pronunciation_contract_id",
        "pronunciation_release_manifest_sha256",
        "staged_adoption_contract_sha256",
        "staged_adoption_audit_sha256",
        "researcher_approval_sha256",
        "safe_body_routing_contract_id",
        "year_input_contract_id",
        "year_input_contract_sha256",
        "expected_mfa_input_sha256",
        "followup_inventory_sha256",
        "corpus_contract_id",
        "frozen_model_pin_sha256",
        "mfa_dictionary_sha256",
        "acoustic_model_sha256",
        "g2p_model_sha256",
    )
    result = {key: clean(identity.get(key)) for key in keys}
    if any(not value for value in result.values()):
        raise RuntimeError("r3 alignment identity required field blank")
    runtime = identity.get("runtime")
    if not isinstance(runtime, Mapping):
        raise RuntimeError("r3 alignment runtime missing")
    result["runtime"] = dict(runtime)
    return {
        "schema_version": clean(contract.get("schema_version")),
        "year": clean(contract.get("year")),
        "pronunciation_mode": clean(contract.get("pronunciation_mode")),
        "alignment_origin": clean(contract.get("alignment_origin")),
        "r3_full_realign": contract.get("r3_full_realign"),
        **result,
    }


def independent_contract_id(contract: Mapping[str, object]) -> str:
    canonical = json.dumps(
        independent_identity(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit(contract_path: Path, output_path: Path) -> dict:
    contract = load_json(contract_path)
    if (
        contract.get("schema_version") != CONTRACT_SCHEMA
        or contract.get("status") != CONTRACT_STATUS
        or contract.get("r3_full_realign") is not True
        or contract.get("alignment_origin") != "fresh_r3_full_realign"
        or contract.get("scope", {}).get("production_mfa_allowed") is not False
        or contract.get("scope", {}).get("textgrid_materialization_allowed") is not False
        or contract.get("scope", {}).get("legacy_marker_reuse_allowed") is not False
        or contract.get("scope", {}).get("legacy_db_reuse_allowed") is not False
    ):
        raise RuntimeError("r3 alignment contract identity or closed gate differs")
    if independent_contract_id(contract) != clean(contract.get("alignment_contract_id")):
        raise RuntimeError("r3 alignment contract ID differs")

    for label, record in contract["inputs"].items():
        verify(record, Path(clean(record["path"])), f"alignment input {label}")
    for label, record in contract["models"].items():
        verify(record, Path(clean(record["path"])), f"alignment model {label}")
    for label in (
        "expected_mfa_input_ids",
        "pronunciation_followup_ids",
        "pre_mfa_exclusion_ids",
    ):
        record = contract["year_input"][label]
        verify(record, Path(clean(record["path"])), f"year input {label}")

    identity = contract["identity"]
    inputs = contract["inputs"]
    release_path = Path(clean(inputs["pronunciation_release_manifest"]["path"])).resolve()
    release = load_json(release_path)
    release_audit = load_json(Path(clean(inputs["staged_adoption_audit"]["path"])))
    year_contract_path = Path(clean(inputs["year_input_contract"]["path"])).resolve()
    year_contract = load_json(year_contract_path)
    year_audit = load_json(Path(clean(inputs["year_input_independent_audit"]["path"])))
    model_pin_path = Path(clean(inputs["frozen_model_pin"]["path"])).resolve()
    model_pin = load_json(model_pin_path)
    gate = load_json(Path(clean(inputs["release_gate_closed_at_build"]["path"])))

    dictionary = contract["models"]["dictionary"]
    acoustic = contract["models"]["acoustic"]
    g2p = contract["models"]["g2p_provenance"]
    cross_checks = (
        clean(identity["pronunciation_release_id"]) == clean(release["release_id"]),
        clean(identity["pronunciation_contract_id"])
        == clean(release["pronunciation_contract_id"]),
        clean(identity["pronunciation_release_manifest_sha256"])
        == sha256_file(release_path),
        clean(identity["staged_adoption_contract_sha256"])
        == clean(inputs["staged_adoption_contract"]["sha256"]),
        clean(identity["staged_adoption_audit_sha256"])
        == sha256_file(Path(clean(inputs["staged_adoption_audit"]["path"]))),
        clean(identity["researcher_approval_sha256"])
        == clean(inputs["researcher_approval"]["sha256"]),
        clean(identity["safe_body_routing_contract_id"])
        == clean(inputs["stage19_routing_manifest"]["sha256"]),
        clean(identity["year_input_contract_id"])
        == clean(year_contract["year_input_contract_id"]),
        clean(identity["year_input_contract_sha256"])
        == sha256_file(year_contract_path),
        clean(identity["expected_mfa_input_sha256"])
        == clean(year_contract["outputs"]["expected_mfa_input_ids"]["sha256"]),
        clean(identity["followup_inventory_sha256"])
        == clean(year_contract["outputs"]["pronunciation_followup_ids"]["sha256"]),
        clean(identity["corpus_contract_id"])
        == clean(year_contract["corpus_binding"]["corpus_contract_id"]),
        clean(identity["frozen_model_pin_sha256"]) == sha256_file(model_pin_path),
        clean(identity["mfa_dictionary_sha256"]) == clean(dictionary["sha256"]),
        clean(identity["acoustic_model_sha256"]) == clean(acoustic["sha256"]),
        clean(identity["g2p_model_sha256"]) == clean(g2p["sha256"]),
        clean(release["outputs"]["mfa_dictionary"]["sha256"])
        == clean(dictionary["sha256"]),
        clean(model_pin["models"]["acoustic_model"]["sha256"])
        == clean(acoustic["sha256"]),
        clean(model_pin["models"]["g2p_model"]["sha256"]) == clean(g2p["sha256"]),
        release_audit.get("verdict", {}).get("release_gate_remains_closed") is True,
        year_audit.get("verdict", {}).get("release_gate_remains_closed") is True,
        clean(year_audit.get("year_input_contract_id"))
        == clean(year_contract["year_input_contract_id"]),
        clean(gate.get("status")).startswith("blocked_"),
        gate.get("allowed_release_ids") == [],
    )
    if not all(cross_checks):
        raise RuntimeError("r3 alignment cross-contract identity differs")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "year": contract["year"],
        "pronunciation_release_id": identity["pronunciation_release_id"],
        "pronunciation_contract_id": identity["pronunciation_contract_id"],
        "alignment_contract_id": contract["alignment_contract_id"],
        "verdict": {
            "identity_recomputed_exact": True,
            "release_and_year_input_cross_checks_passed": True,
            "model_and_dictionary_fingerprints_passed": True,
            "production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "release_gate_remains_closed": True,
        },
        "checks": {
            "required_identity_fields": 17,
            "legacy_marker_reuse_allowed": False,
            "legacy_db_reuse_allowed": False,
            "r3_full_realign": True,
            "expected_mfa_input": int(contract["year_input"]["expected_mfa_input"]),
        },
        "inputs": {
            "alignment_contract": file_fingerprint(contract_path, with_sha256=True),
            "pronunciation_release_manifest": inputs["pronunciation_release_manifest"],
            "year_input_contract": inputs["year_input_contract"],
            "mfa_dictionary": dictionary,
            "acoustic_model": acoustic,
            "g2p_model": g2p,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.contract.resolve(), args.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

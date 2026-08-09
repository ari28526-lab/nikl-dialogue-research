"""Build an immutable r3 alignment identity without running MFA."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file


POLICY_SCHEMA = "mfa_r3_alignment_contract_policy.v1"
SCHEMA_VERSION = "mfa_r3_alignment_contract.v1"
STATUS = "materialized_pending_runner_preflight_and_release_gate"
RELEASE_SCHEMA = "common_pron_mfa_r3_staged_release.v1"
RELEASE_STATUS = "materialized_pending_independent_adoption_audit_and_release_gate"
RELEASE_AUDIT_STATUS = "passed_independent_staged_adoption_audit_pending_release_gate"
YEAR_INPUT_SCHEMA = "mfa_r3_year_input_contract.v1"
YEAR_INPUT_STATUS = "materialized_pending_independent_year_input_audit_gate_closed"
YEAR_AUDIT_STATUS = "passed_independent_exact_id_audit_pending_alignment_contract_gate_closed"


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


def installed_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not_installed"


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "montreal_forced_aligner": installed_version("montreal-forced-aligner"),
        "pynini": installed_version("pynini"),
    }


def alignment_identity_from_contract(contract: Mapping[str, object]) -> dict:
    required = (
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
    identity = contract.get("identity")
    if not isinstance(identity, Mapping):
        raise RuntimeError("alignment identity missing")
    values = {key: clean(identity.get(key)) for key in required}
    if any(not value for value in values.values()):
        raise RuntimeError("alignment identity has a blank required value")
    runtime = identity.get("runtime")
    if not isinstance(runtime, Mapping) or any(
        not clean(runtime.get(key))
        for key in ("python", "montreal_forced_aligner", "pynini")
    ):
        raise RuntimeError("alignment runtime identity differs")
    return {
        "schema_version": clean(contract.get("schema_version")),
        "year": clean(contract.get("year")),
        "pronunciation_mode": clean(contract.get("pronunciation_mode")),
        "alignment_origin": clean(contract.get("alignment_origin")),
        "r3_full_realign": contract.get("r3_full_realign"),
        **values,
        "runtime": dict(runtime),
    }


def recompute_alignment_contract_id(contract: Mapping[str, object]) -> str:
    canonical = json.dumps(
        alignment_identity_from_contract(contract),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_if_new(output: Path, contract: dict) -> bool:
    if output.exists():
        existing = load_json(output)
        expected = clean(contract["alignment_contract_id"])
        if (
            existing.get("schema_version") == SCHEMA_VERSION
            and existing.get("status") == STATUS
            and clean(existing.get("alignment_contract_id")) == expected
            and recompute_alignment_contract_id(existing) == expected
        ):
            return False
        raise RuntimeError("existing r3 alignment contract differs; immutable overwrite refused")
    atomic_write_json(output, contract)
    return True


def build_alignment_contract(
    *,
    year: str,
    policy_path: Path,
    release_manifest_path: Path,
    release_audit_path: Path,
    year_input_contract_path: Path,
    year_input_audit_path: Path,
    release_gate_path: Path,
    runtime: dict[str, str] | None = None,
) -> dict:
    policy = load_json(policy_path)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status") != "approved_contract_building_only_gate_closed"
        or year not in policy.get("scope", {}).get("years_enabled", [])
        or policy.get("scope", {}).get("production_mfa_allowed") is not False
        or policy.get("scope", {}).get("textgrid_materialization_allowed") is not False
        or policy.get("scope", {}).get("legacy_marker_reuse_allowed") is not False
        or policy.get("scope", {}).get("legacy_db_reuse_allowed") is not False
        or policy.get("r3_full_realign") is not True
    ):
        raise RuntimeError("r3 alignment policy identity or closed gate differs")
    release_id = clean(policy["pronunciation_release_id"])

    release = load_json(release_manifest_path)
    release_audit = load_json(release_audit_path)
    if (
        release.get("schema_version") != RELEASE_SCHEMA
        or release.get("status") != RELEASE_STATUS
        or clean(release.get("release_id")) != release_id
        or release.get("scope", {}).get("adopted") is not False
        or release.get("scope", {}).get("allow_yearly_mfa") is not False
        or release.get("scope", {}).get("allow_textgrid_materialization") is not False
        or release_audit.get("status") != RELEASE_AUDIT_STATUS
        or release_audit.get("verdict", {}).get("production_mfa_allowed") is not False
        or release_audit.get("verdict", {}).get("release_gate_remains_closed") is not True
    ):
        raise RuntimeError("staged r3 release identity or audit differs")
    verify(
        release_audit["inputs"]["release_manifest"],
        release_manifest_path,
        "release manifest through adoption audit",
    )

    year_contract = load_json(year_input_contract_path)
    year_audit = load_json(year_input_audit_path)
    if (
        year_contract.get("schema_version") != YEAR_INPUT_SCHEMA
        or year_contract.get("status") != YEAR_INPUT_STATUS
        or clean(year_contract.get("year")) != year
        or clean(year_contract.get("release_id")) != release_id
        or year_contract.get("scope", {}).get("production_mfa_allowed") is not False
        or year_audit.get("status") != YEAR_AUDIT_STATUS
        or clean(year_audit.get("year_input_contract_id"))
        != clean(year_contract.get("year_input_contract_id"))
        or year_audit.get("verdict", {}).get("exact_id_partition_passed") is not True
        or year_audit.get("verdict", {}).get("production_mfa_allowed") is not False
        or year_audit.get("verdict", {}).get("release_gate_remains_closed") is not True
    ):
        raise RuntimeError("year input contract or independent audit differs")
    verify(
        year_audit["inputs"]["year_input_contract"],
        year_input_contract_path,
        "year input contract through independent audit",
    )

    gate = load_json(release_gate_path)
    if (
        not clean(gate.get("status")).startswith("blocked_")
        or gate.get("allowed_release_ids") != []
    ):
        raise RuntimeError("release Gate must remain closed while building contract")

    dictionary_path = Path(clean(release["outputs"]["mfa_dictionary"]["path"])).resolve()
    verify(release["outputs"]["mfa_dictionary"], dictionary_path, "r3 MFA dictionary")
    model_pin_path = Path(clean(release["inputs"]["frozen_model_pin"]["path"])).resolve()
    verify(release["inputs"]["frozen_model_pin"], model_pin_path, "frozen model pin")
    model_pin = load_json(model_pin_path)
    if model_pin.get("status") != "passed":
        raise RuntimeError("frozen model pin status differs")
    acoustic_path = Path(clean(model_pin["models"]["acoustic_model"]["path"])).resolve()
    g2p_path = Path(clean(model_pin["models"]["g2p_model"]["path"])).resolve()
    verify(model_pin["models"]["acoustic_model"], acoustic_path, "acoustic model")
    verify(model_pin["models"]["g2p_model"], g2p_path, "G2P model")

    routing_record = release["inputs"]["stage19_routing_manifest"]
    adoption_record = release["inputs"]["v3_1_contract"]
    approval_record = release["inputs"]["researcher_approval"]
    for label, record in (
        ("Stage 19 routing", routing_record),
        ("staged adoption contract", adoption_record),
        ("researcher approval", approval_record),
    ):
        verify(record, Path(clean(record["path"])), label)

    runtime_record = dict(runtime or runtime_versions())
    identity = {
        "pronunciation_release_id": release_id,
        "pronunciation_contract_id": clean(release["pronunciation_contract_id"]),
        "pronunciation_release_manifest_sha256": sha256_file(release_manifest_path),
        "staged_adoption_contract_sha256": clean(adoption_record["sha256"]),
        "staged_adoption_audit_sha256": sha256_file(release_audit_path),
        "researcher_approval_sha256": clean(approval_record["sha256"]),
        "safe_body_routing_contract_id": clean(routing_record["sha256"]),
        "year_input_contract_id": clean(year_contract["year_input_contract_id"]),
        "year_input_contract_sha256": sha256_file(year_input_contract_path),
        "expected_mfa_input_sha256": clean(
            year_contract["outputs"]["expected_mfa_input_ids"]["sha256"]
        ),
        "followup_inventory_sha256": clean(
            year_contract["outputs"]["pronunciation_followup_ids"]["sha256"]
        ),
        "corpus_contract_id": clean(year_contract["corpus_binding"]["corpus_contract_id"]),
        "frozen_model_pin_sha256": sha256_file(model_pin_path),
        "mfa_dictionary_sha256": sha256_file(dictionary_path),
        "acoustic_model_sha256": sha256_file(acoustic_path),
        "g2p_model_sha256": sha256_file(g2p_path),
        "runtime": runtime_record,
    }
    contract: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "year": year,
        "pronunciation_mode": clean(policy["pronunciation_mode"]),
        "alignment_origin": clean(policy["alignment_origin"]),
        "r3_full_realign": True,
        "identity": identity,
        "alignment_contract_id": "",
        "scope": {
            "contract_materialized": True,
            "production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "legacy_marker_reuse_allowed": False,
            "legacy_db_reuse_allowed": False,
        },
        "models": {
            "acoustic": file_fingerprint(acoustic_path, with_sha256=True),
            "dictionary": file_fingerprint(dictionary_path, with_sha256=True),
            "g2p_provenance": file_fingerprint(g2p_path, with_sha256=True),
        },
        "inputs": {
            "alignment_policy": file_fingerprint(policy_path, with_sha256=True),
            "pronunciation_release_manifest": file_fingerprint(
                release_manifest_path, with_sha256=True
            ),
            "staged_adoption_contract": adoption_record,
            "staged_adoption_audit": file_fingerprint(
                release_audit_path, with_sha256=True
            ),
            "researcher_approval": approval_record,
            "stage19_routing_manifest": routing_record,
            "year_input_contract": file_fingerprint(
                year_input_contract_path, with_sha256=True
            ),
            "year_input_independent_audit": file_fingerprint(
                year_input_audit_path, with_sha256=True
            ),
            "release_gate_closed_at_build": file_fingerprint(
                release_gate_path, with_sha256=True
            ),
            "frozen_model_pin": file_fingerprint(model_pin_path, with_sha256=True),
        },
        "year_input": {
            "expected_mfa_input": int(year_contract["accounting"]["expected_mfa_input"]),
            "expected_mfa_input_ids": year_contract["outputs"]["expected_mfa_input_ids"],
            "pronunciation_followup_ids": year_contract["outputs"][
                "pronunciation_followup_ids"
            ],
            "pre_mfa_exclusion_ids": year_contract["outputs"]["pre_mfa_exclusion_ids"],
            "corpus_contract_id": identity["corpus_contract_id"],
            "recovered_wav_root": year_contract["corpus_binding"]["recovered_wav_root"],
        },
    }
    contract["alignment_contract_id"] = recompute_alignment_contract_id(contract)
    return contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--release-audit", type=Path, required=True)
    parser.add_argument("--year-input-contract", type=Path, required=True)
    parser.add_argument("--year-input-audit", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = build_alignment_contract(
        year=args.year,
        policy_path=args.policy.resolve(),
        release_manifest_path=args.release_manifest.resolve(),
        release_audit_path=args.release_audit.resolve(),
        year_input_contract_path=args.year_input_contract.resolve(),
        year_input_audit_path=args.year_input_audit.resolve(),
        release_gate_path=args.release_gate.resolve(),
    )
    wrote = write_if_new(args.output.resolve(), contract)
    print(
        f"r3 alignment contract: {contract['alignment_contract_id']} "
        f"({'written' if wrote else 'unchanged'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

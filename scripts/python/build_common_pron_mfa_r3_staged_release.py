"""Materialize the v3.1 pronunciation-safe staged r3 release.

This promotes the already audited Stage 20 candidate projection into a new,
release-scoped selected projection.  It does not open the project release Gate,
run MFA, modify Stage 01-21, or alter any r2 artifact.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_mfa_r3_staged_release.v1"
POLICY_SCHEMA = "common_pron_mfa_r3_staged_release_policy.v1"
STATUS = "materialized_pending_independent_adoption_audit_and_release_gate"
RELEASE_RE = re.compile(r"common_pron_mfa_r3_\d{8}$")
SOURCE_FIELDS = (
    "token",
    "variant_index",
    "variant_count",
    "pron_phones_mfa",
    "pron_roman",
    "planning_status",
    "planning_source",
    "planning_reason",
    "total_occurrences",
    "count_2020",
    "count_2021",
    "count_2022",
    "count_2023",
    "count_2024",
    "count_2025",
    "candidate_only",
    "final_selection",
    "adopted",
)
SELECTED_FIELDS = (
    "token",
    "variant_index",
    "variant_count",
    "selected_pron_phones_mfa",
    "selected_pron_roman",
    "source_candidate_status",
    "source_candidate_source",
    "source_candidate_reason",
    "selection_status",
    "selection_source",
    "selection_reason",
    "total_occurrences",
    "count_2020",
    "count_2021",
    "count_2022",
    "count_2023",
    "count_2024",
    "count_2025",
    "candidate_only",
    "final_selection",
    "adopted",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(record: dict, path: Path, label: str) -> None:
    if (
        Path(str(record.get("path", ""))).resolve() != path.resolve()
        or not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def fingerprint_for_final(temp: Path, final: Path) -> dict:
    record = file_fingerprint(temp, with_sha256=True)
    record["path"] = str(final.resolve())
    return record


@contextmanager
def deterministic_gzip_text_writer(path: Path) -> Iterator[TextIO]:
    with path.open("xb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", compresslevel=6, fileobj=raw, mtime=0
        ) as compressed:
            with io.TextIOWrapper(
                compressed, encoding="utf-8-sig", newline=""
            ) as stream:
                yield stream


def selected_row(row: dict[str, str]) -> dict[str, object]:
    if tuple(row) != SOURCE_FIELDS:
        raise RuntimeError("Stage 20 candidate projection field contract differs")
    if (
        row["candidate_only"] != "true"
        or row["final_selection"] != "false"
        or row["adopted"] != "false"
        or not row["planning_status"].startswith("candidate_")
    ):
        raise RuntimeError(f"Stage 20 candidate status differs: {row['token']}")
    return {
        "token": row["token"],
        "variant_index": row["variant_index"],
        "variant_count": row["variant_count"],
        "selected_pron_phones_mfa": row["pron_phones_mfa"],
        "selected_pron_roman": row["pron_roman"],
        "source_candidate_status": row["planning_status"],
        "source_candidate_source": row["planning_source"],
        "source_candidate_reason": row["planning_reason"],
        "selection_status": "selected_staged_safe_body_v3_1",
        "selection_source": "researcher_approved_v3_1_candidate_promotion",
        "selection_reason": (
            "candidate-ready type promoted only for the audited pronunciation-safe "
            "staged release; unresolved types remain follow-up"
        ),
        "total_occurrences": row["total_occurrences"],
        **{f"count_{year}": row[f"count_{year}"] for year in range(2020, 2026)},
        "candidate_only": "false",
        "final_selection": "true",
        "adopted": "false",
    }


def release_contract_id(identity: dict) -> str:
    canonical = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build(
    *,
    contract_path: Path,
    approval_path: Path,
    approval_provenance_path: Path,
    routing_manifest_path: Path,
    routing_audit_path: Path,
    candidate_manifest_path: Path,
    candidate_audit_path: Path,
    frozen_pin_path: Path,
    release_gate_path: Path,
    policy_path: Path,
    output_root: Path,
) -> dict:
    policy = load_json(policy_path)
    release_id = clean(policy.get("release_id"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status")
        != "approved_to_materialize_pending_independent_audit_and_gate"
        or not RELEASE_RE.fullmatch(release_id)
        or output_root.name != release_id
    ):
        raise RuntimeError("staged release policy identity differs")
    if output_root.exists():
        existing_path = output_root / "RELEASE_MANIFEST.json"
        if not existing_path.is_file():
            raise RuntimeError(f"release root exists without manifest: {output_root}")
        existing = load_json(existing_path)
        if (
            existing.get("schema_version") != SCHEMA_VERSION
            or existing.get("status") != STATUS
            or existing.get("release_id") != release_id
        ):
            raise RuntimeError("existing staged release identity differs")
        for label, record in existing.get("inputs", {}).items():
            verify(
                record,
                Path(str(record.get("path", ""))).resolve(),
                f"existing input {label}",
            )
        for label, record in existing.get("outputs", {}).items():
            verify(
                record,
                Path(str(record.get("path", ""))).resolve(),
                f"existing output {label}",
            )
        return existing

    contract = load_json(contract_path)
    approval = load_json(approval_path)
    provenance = load_json(approval_provenance_path)
    routing = load_json(routing_manifest_path)
    routing_audit = load_json(routing_audit_path)
    candidate = load_json(candidate_manifest_path)
    candidate_audit = load_json(candidate_audit_path)
    frozen_pin = load_json(frozen_pin_path)
    release_gate = load_json(release_gate_path)
    if (
        contract.get("schema_version")
        != "common_pronunciation_resource_contract.v3.1"
        or contract.get("status")
        != "researcher_approved_staged_scope_pending_release_materialization_and_independent_audit"
        or contract.get("invariants", {}).get("production_gate_opened_by_this_contract")
        is not False
    ):
        raise RuntimeError("v3.1 staged contract identity differs")
    approval_pin = contract["researcher_approval"]
    verify(approval_pin, approval_path, "immutable researcher approval")
    if (
        approval.get("status") != "passed_explicit_researcher_approval"
        or approval.get("approval_contract_id")
        != approval_pin["approval_contract_id"]
        or provenance.get("schema_version")
        != "common_pron_r3_researcher_approval_provenance.v2"
        or provenance.get("approval_contract_id")
        != approval["approval_contract_id"]
        or provenance.get("immutable_approval")
        != {"bytes": approval_pin["bytes"], "sha256": approval_pin["sha256"]}
        or not provenance.get("records")
    ):
        raise RuntimeError("researcher approval or provenance identity differs")
    if (
        routing.get("status") != "success_read_only_routing_not_adopted"
        or routing_audit.get("status") != "passed_independent_full_scan"
        or candidate.get("status") != "passed_candidate_only_not_adopted"
        or candidate_audit.get("status")
        != "passed_full_projection_and_dictionary_equivalence"
        or frozen_pin.get("status") != "passed"
        or not str(release_gate.get("status", "")).startswith("blocked_")
        or release_gate.get("allowed_release_ids")
    ):
        raise RuntimeError("staged release prerequisite status differs")

    candidate_projection = Path(
        str(candidate["outputs"]["candidate_projection"]["path"])
    ).resolve()
    candidate_dictionary = Path(
        str(candidate["outputs"]["candidate_dictionary_not_adopted"]["path"])
    ).resolve()
    acoustic_model = Path(
        str(candidate["inputs"]["frozen_acoustic_model"]["path"])
    ).resolve()
    verify(candidate["outputs"]["candidate_projection"], candidate_projection, "Stage 20 projection")
    verify(candidate["outputs"]["candidate_dictionary_not_adopted"], candidate_dictionary, "Stage 20 dictionary")
    verify(candidate["inputs"]["frozen_acoustic_model"], acoustic_model, "frozen acoustic model")
    verify(candidate_audit["inputs"]["candidate_manifest"], candidate_manifest_path, "Stage 20 audited manifest")

    expected = policy["expected"]
    staged_scope = contract["staged_selection_scope"]
    counts = candidate["counts"]
    if (
        int(staged_scope["candidate_types_to_promote"])
        != int(expected["selected_types"])
        or int(staged_scope["projected_dictionary_variant_rows"])
        != int(expected["dictionary_rows"])
        or int(staged_scope["pronunciation_safe_utterances"])
        != int(expected["safe_utterances"])
        or int(staged_scope["followup_utterances"])
        != int(expected["followup_utterances"])
        or int(counts["candidate_types"]) != int(expected["selected_types"])
        or int(counts["dictionary_rows"]) != int(expected["dictionary_rows"])
        or int(routing["counts"]["safe_utterances"])
        != int(expected["safe_utterances"])
        or int(routing["counts"]["blocked_utterances"])
        != int(expected["followup_utterances"])
    ):
        raise RuntimeError("staged release accounting differs")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    temp_root.mkdir(parents=True, exist_ok=False)
    projection_temp = temp_root / "selected_pronunciation_projection.csv.gz"
    dictionary_temp = temp_root / f"{release_id}.dict"
    projection_final = output_root / projection_temp.name
    dictionary_final = output_root / dictionary_temp.name
    type_count = dictionary_rows = occurrence_count = 0
    previous_token = ""
    variant_distribution: Counter[int] = Counter()
    with gzip.open(
        candidate_projection, "rt", encoding="utf-8-sig", newline=""
    ) as source, deterministic_gzip_text_writer(projection_temp) as target:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise RuntimeError("Stage 20 candidate projection field contract differs")
        writer = csv.DictWriter(target, fieldnames=SELECTED_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            promoted = selected_row(row)
            token = row["token"]
            variant_index = int(row["variant_index"])
            variant_count = int(row["variant_count"])
            if variant_index == 1:
                if previous_token and token <= previous_token:
                    raise RuntimeError("selected tokens are not strictly sorted")
                previous_token = token
                type_count += 1
                occurrence_count += int(row["total_occurrences"])
                variant_distribution[variant_count] += 1
            elif token != previous_token:
                raise RuntimeError("selected variant rows are not contiguous")
            dictionary_rows += 1
            writer.writerow(promoted)
    shutil.copyfile(candidate_dictionary, dictionary_temp)
    if (
        type_count != int(expected["selected_types"])
        or dictionary_rows != int(expected["dictionary_rows"])
        or occurrence_count != int(expected["selected_occurrences"])
        or sha256_file(dictionary_temp) != sha256_file(candidate_dictionary)
    ):
        raise RuntimeError("selected release materialization differs")

    inputs = {
        "v3_1_contract": file_fingerprint(contract_path, with_sha256=True),
        "researcher_approval": file_fingerprint(approval_path, with_sha256=True),
        "approval_provenance": file_fingerprint(
            approval_provenance_path, with_sha256=True
        ),
        "stage19_routing_manifest": file_fingerprint(
            routing_manifest_path, with_sha256=True
        ),
        "stage19_routing_audit": file_fingerprint(
            routing_audit_path, with_sha256=True
        ),
        "stage20_candidate_manifest": file_fingerprint(
            candidate_manifest_path, with_sha256=True
        ),
        "stage20_candidate_audit": file_fingerprint(
            candidate_audit_path, with_sha256=True
        ),
        "stage20_candidate_projection": file_fingerprint(
            candidate_projection, with_sha256=True
        ),
        "stage20_candidate_dictionary": file_fingerprint(
            candidate_dictionary, with_sha256=True
        ),
        "frozen_model_pin": file_fingerprint(frozen_pin_path, with_sha256=True),
        "frozen_acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        "closed_release_gate": file_fingerprint(release_gate_path, with_sha256=True),
        "release_policy": file_fingerprint(policy_path, with_sha256=True),
    }
    outputs = {
        "selected_projection": fingerprint_for_final(
            projection_temp, projection_final
        ),
        "mfa_dictionary": fingerprint_for_final(dictionary_temp, dictionary_final),
    }
    identity = {
        "schema_version": SCHEMA_VERSION,
        "release_id": release_id,
        "contract_sha256": inputs["v3_1_contract"]["sha256"],
        "approval_sha256": inputs["researcher_approval"]["sha256"],
        "routing_manifest_sha256": inputs["stage19_routing_manifest"]["sha256"],
        "candidate_manifest_sha256": inputs["stage20_candidate_manifest"]["sha256"],
        "candidate_audit_sha256": inputs["stage20_candidate_audit"]["sha256"],
        "selected_projection_sha256": outputs["selected_projection"]["sha256"],
        "mfa_dictionary_sha256": outputs["mfa_dictionary"]["sha256"],
        "frozen_acoustic_model_sha256": inputs["frozen_acoustic_model"]["sha256"],
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "release_id": release_id,
        "pronunciation_contract_id": release_contract_id(identity),
        "scope": {
            "staged_safe_body_selection": True,
            "full_corpus_selection": False,
            "selected": True,
            "adopted": False,
            "allow_yearly_mfa": False,
            "allow_textgrid_materialization": False,
            "actual_realization_claimed": False,
        },
        "inputs": inputs,
        "counts": {
            "canonical_types": int(
                contract["canonical_type_table"][
                    "full_canonical_type_coverage_required"
                ]
            ),
            "selected_types": type_count,
            "selected_occurrences": occurrence_count,
            "dictionary_rows": dictionary_rows,
            "variant_count_distribution": {
                str(key): value for key, value in sorted(variant_distribution.items())
            },
            "zero_fallback_hold_types": int(
                staged_scope["not_selected_for_staged_release"][
                    "zero_fallback_hold_types"
                ]
            ),
            "explicit_policy_types": int(
                staged_scope["not_selected_for_staged_release"][
                    "explicit_policy_types"
                ]
            ),
            "safe_utterances": int(expected["safe_utterances"]),
            "followup_utterances": int(expected["followup_utterances"]),
        },
        "model_contract": candidate["model_contract"],
        "outputs": outputs,
        "builder_checks": {
            "source_candidate_projection_preserved": True,
            "candidate_to_selected_row_count_equal": True,
            "mfa_dictionary_byte_identical_to_stage20_candidate_dictionary": True,
            "production_gate_was_closed": True,
            "stage01_through_21_modified": False,
            "r2_artifacts_modified": False,
        },
        "next_required": [
            "pass independent staged adoption audit",
            "build annual input and alignment contracts",
            "keep project release Gate closed until the final GO decision",
        ],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "RELEASE_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=PROJECT_ROOT
        / "config/common_pronunciation_resource_contract_v3_1.json",
    )
    parser.add_argument(
        "--approval",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json",
    )
    parser.add_argument(
        "--approval-provenance",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.provenance.v2.json",
    )
    parser.add_argument("--routing-manifest", type=Path, required=True)
    parser.add_argument("--routing-audit", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--candidate-audit", type=Path, required=True)
    parser.add_argument("--frozen-pin", type=Path, required=True)
    parser.add_argument(
        "--release-gate",
        type=Path,
        default=PROJECT_ROOT / "config/mfa_pronunciation_release_gate.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=PROJECT_ROOT / "config/common_pron_mfa_r3_staged_release_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(
        contract_path=args.contract.resolve(),
        approval_path=args.approval.resolve(),
        approval_provenance_path=args.approval_provenance.resolve(),
        routing_manifest_path=args.routing_manifest.resolve(),
        routing_audit_path=args.routing_audit.resolve(),
        candidate_manifest_path=args.candidate_manifest.resolve(),
        candidate_audit_path=args.candidate_audit.resolve(),
        frozen_pin_path=args.frozen_pin.resolve(),
        release_gate_path=args.release_gate.resolve(),
        policy_path=args.policy.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "release_id": manifest["release_id"],
                "pronunciation_contract_id": manifest[
                    "pronunciation_contract_id"
                ],
                **manifest["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

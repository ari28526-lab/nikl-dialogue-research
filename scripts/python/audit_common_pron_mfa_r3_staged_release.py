"""Independently audit the materialized v3.1 staged pronunciation release."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import (
    acoustic_phone_inventory,
    parse_mfa_dictionary_line,
)
from build_common_pron_mfa_r3_staged_release import (
    SCHEMA_VERSION as RELEASE_SCHEMA,
    SELECTED_FIELDS,
    SOURCE_FIELDS,
    STATUS as RELEASE_STATUS,
)
from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_mfa_r3_staged_release_audit.v1"
STATUS = "passed_independent_staged_adoption_audit_pending_release_gate"


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


def audit(manifest_path: Path, output_path: Path) -> dict:
    manifest = load_json(manifest_path)
    if (
        manifest.get("schema_version") != RELEASE_SCHEMA
        or manifest.get("status") != RELEASE_STATUS
        or manifest.get("scope", {}).get("selected") is not True
        or manifest.get("scope", {}).get("adopted") is not False
        or manifest.get("scope", {}).get("allow_yearly_mfa") is not False
        or manifest.get("scope", {}).get("allow_textgrid_materialization")
        is not False
    ):
        raise RuntimeError("staged release manifest identity differs")

    inputs = manifest["inputs"]
    for label, record in inputs.items():
        verify(record, Path(str(record["path"])).resolve(), f"input {label}")
    outputs = manifest["outputs"]
    selected_projection = Path(str(outputs["selected_projection"]["path"])).resolve()
    dictionary = Path(str(outputs["mfa_dictionary"]["path"])).resolve()
    verify(outputs["selected_projection"], selected_projection, "selected projection")
    verify(outputs["mfa_dictionary"], dictionary, "MFA dictionary")

    contract = load_json(Path(str(inputs["v3_1_contract"]["path"])))
    approval = load_json(Path(str(inputs["researcher_approval"]["path"])))
    provenance = load_json(Path(str(inputs["approval_provenance"]["path"])))
    routing = load_json(Path(str(inputs["stage19_routing_manifest"]["path"])))
    candidate = load_json(Path(str(inputs["stage20_candidate_manifest"]["path"])))
    candidate_audit = load_json(Path(str(inputs["stage20_candidate_audit"]["path"])))
    gate = load_json(Path(str(inputs["closed_release_gate"]["path"])))
    if (
        contract.get("schema_version")
        != "common_pronunciation_resource_contract.v3.1"
        or approval.get("approval_contract_id")
        != contract["researcher_approval"]["approval_contract_id"]
        or provenance.get("approval_contract_id")
        != approval["approval_contract_id"]
        or routing.get("status") != "success_read_only_routing_not_adopted"
        or candidate.get("status") != "passed_candidate_only_not_adopted"
        or candidate_audit.get("status")
        != "passed_full_projection_and_dictionary_equivalence"
        or not str(gate.get("status", "")).startswith("blocked_")
        or gate.get("allowed_release_ids")
    ):
        raise RuntimeError("staged release bound contract status differs")

    candidate_projection = Path(
        str(inputs["stage20_candidate_projection"]["path"])
    ).resolve()
    candidate_dictionary = Path(
        str(inputs["stage20_candidate_dictionary"]["path"])
    ).resolve()
    acoustic_model = Path(str(inputs["frozen_acoustic_model"]["path"])).resolve()
    inventory = acoustic_phone_inventory(acoustic_model) - {"sil", "spn"}
    if sha256_file(dictionary) != sha256_file(candidate_dictionary):
        raise RuntimeError("release dictionary is not byte-identical to Stage 20")

    type_count = row_count = occurrence_count = 0
    previous_token = ""
    variant_distribution: Counter[int] = Counter()
    outside: set[str] = set()
    with gzip.open(
        candidate_projection, "rt", encoding="utf-8-sig", newline=""
    ) as candidate_stream, gzip.open(
        selected_projection, "rt", encoding="utf-8-sig", newline=""
    ) as selected_stream, dictionary.open(
        "r", encoding="utf-8-sig"
    ) as dictionary_stream:
        candidate_reader = csv.DictReader(candidate_stream)
        selected_reader = csv.DictReader(selected_stream)
        if (
            tuple(candidate_reader.fieldnames or ()) != SOURCE_FIELDS
            or tuple(selected_reader.fieldnames or ()) != SELECTED_FIELDS
        ):
            raise RuntimeError("release projection field contract differs")
        rows = zip_longest(
            candidate_reader,
            selected_reader,
            dictionary_stream,
            fillvalue=None,
        )
        for row_number, (source, selected, dictionary_line) in enumerate(rows, 1):
            if source is None or selected is None or dictionary_line is None:
                raise RuntimeError("candidate/selected/dictionary row count differs")
            token, phones, probabilities = parse_mfa_dictionary_line(
                dictionary_line,
                path=dictionary,
                line_number=row_number,
            )
            if probabilities:
                raise RuntimeError("release dictionary has probability columns")
            same_fields = (
                selected["token"] == source["token"] == token
                and selected["variant_index"] == source["variant_index"]
                and selected["variant_count"] == source["variant_count"]
                and selected["selected_pron_phones_mfa"]
                == source["pron_phones_mfa"]
                and tuple(selected["selected_pron_phones_mfa"].split()) == phones
                and selected["selected_pron_roman"] == source["pron_roman"]
                and selected["source_candidate_status"]
                == source["planning_status"]
                and selected["source_candidate_source"]
                == source["planning_source"]
                and selected["source_candidate_reason"]
                == source["planning_reason"]
                and selected["total_occurrences"] == source["total_occurrences"]
                and all(
                    selected[f"count_{year}"] == source[f"count_{year}"]
                    for year in range(2020, 2026)
                )
            )
            if not same_fields:
                raise RuntimeError(f"selected projection differs at row {row_number}")
            if (
                source["candidate_only"] != "true"
                or source["final_selection"] != "false"
                or source["adopted"] != "false"
                or selected["selection_status"]
                != "selected_staged_safe_body_v3_1"
                or selected["selection_source"]
                != "researcher_approved_v3_1_candidate_promotion"
                or selected["candidate_only"] != "false"
                or selected["final_selection"] != "true"
                or selected["adopted"] != "false"
            ):
                raise RuntimeError(f"selected status differs at row {row_number}")
            outside.update(set(phones) - inventory)
            variant_index = int(selected["variant_index"])
            variant_count = int(selected["variant_count"])
            if variant_index == 1:
                if previous_token and token <= previous_token:
                    raise RuntimeError("selected tokens are not strictly sorted")
                previous_token = token
                type_count += 1
                occurrence_count += int(selected["total_occurrences"])
                variant_distribution[variant_count] += 1
            elif token != previous_token:
                raise RuntimeError("selected variant rows are not contiguous")
            row_count += 1
    if outside:
        raise RuntimeError(f"phones outside frozen inventory: {sorted(outside)}")

    counts = manifest["counts"]
    if (
        type_count != int(counts["selected_types"])
        or row_count != int(counts["dictionary_rows"])
        or occurrence_count != int(counts["selected_occurrences"])
        or {str(key): value for key, value in sorted(variant_distribution.items())}
        != counts["variant_count_distribution"]
        or type_count + int(counts["zero_fallback_hold_types"])
        + int(counts["explicit_policy_types"])
        != int(counts["canonical_types"])
    ):
        raise RuntimeError("staged release count contract differs")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "release_id": manifest["release_id"],
        "pronunciation_contract_id": manifest["pronunciation_contract_id"],
        "verdict": {
            "staged_release_materialization_passed": True,
            "selected_projection_passed": True,
            "production_mfa_allowed": False,
            "textgrid_materialization_allowed": False,
            "release_gate_remains_closed": True,
            "full_corpus_completion_claimed": False,
        },
        "checks": {
            "stage19_and_stage20_sha_pinned": True,
            "researcher_approval_sha_pinned": True,
            "candidate_to_selected_projection_exact": True,
            "dictionary_byte_identical_to_stage20": True,
            "dictionary_row_projection_exact": True,
            "phones_inside_frozen_inventory": True,
            "lexical_sil_or_spn": 0,
            "candidate_source_modified": False,
            "release_gate_opened": False,
        },
        "counts": {
            "canonical_types": int(counts["canonical_types"]),
            "selected_types": type_count,
            "selected_occurrences": occurrence_count,
            "dictionary_rows": row_count,
            "safe_utterances": int(counts["safe_utterances"]),
            "followup_utterances": int(counts["followup_utterances"]),
        },
        "inputs": {
            "release_manifest": file_fingerprint(manifest_path, with_sha256=True),
            "selected_projection": file_fingerprint(
                selected_projection, with_sha256=True
            ),
            "mfa_dictionary": file_fingerprint(dictionary, with_sha256=True),
            "stage20_candidate_projection": file_fingerprint(
                candidate_projection, with_sha256=True
            ),
            "stage20_candidate_dictionary": file_fingerprint(
                candidate_dictionary, with_sha256=True
            ),
            "frozen_acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
            "closed_release_gate": file_fingerprint(
                Path(str(inputs["closed_release_gate"]["path"])), with_sha256=True
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.release_manifest.resolve(), args.output.resolve())
    print(
        json.dumps(
            {
                "status": report["status"],
                "release_id": report["release_id"],
                **report["counts"],
                **report["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the only contract allowed to authorize yearly MFA with r2."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso
from verify_frozen_mfa_bundle import verify_frozen_bundle


SCHEMA_VERSION = "common_pron_mfa_adoption.v3"
APPROVAL_SCHEMA_VERSION = "common_pron_mfa_researcher_approval.v2"
DIFFERENCE_SCHEMA_VERSION = "common_pron_mfa_difference_inventory.v2"
LEXICON_SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"
NO_PATH_SCHEMA_VERSION = "common_pron_g2p_no_path_supplement.v1"
APPLICATION_SCHEMA_VERSION = (
    "common_pron_researcher_decision_application.v1"
)
VALIDATION_SCHEMA_VERSION = (
    "common_pron_researcher_decision_validation.v1"
)
APPLICATION_KIND = "common_pron_researcher_decision_application"
EXPECTED_APPLICATION_COUNTS = {
    "normalized_decisions": 27,
    "no_path_existing_approved_preserved": 1,
    "no_path_new_approved": 23,
    "no_path_total_approved": 24,
    "jamo_new_approved": 4,
    "correction_registry_rows": 2,
}
EXPECTED_APPLICATION_GATES = {
    "exclusive_runner_lock_held": True,
    "originals_archived_before_promotion": True,
    "no_path_post_write_verified": True,
    "jamo_post_write_verified": True,
    "correction_registry_hash_verified": True,
    "raw_corpus_modified": False,
    "g2p_shards_modified": False,
    "final_dictionary_created": False,
}
EXPECTED_CORRECTIONS = {
    "외곬수적인": {
        "correction_kind": "source_spelling",
        "raw_search_token": "외곬수적인",
        "normalized_search_token": "외골수적인",
    },
    "천구백칤비육": {
        "correction_kind": "numeric_placeholder",
        "raw_search_token": "천구백칤비육",
        "normalized_search_token": "천구백칠십육",
    },
}
AFFIRMATIVE_DECISIONS = {
    "approve_recommended",
    "approve_alternative",
    "approve_custom",
}
NO_PATH_FIELDS = (
    "surface",
    "respelled",
    "rule_id",
    "evidence_source",
    "evidence_detail",
    "pron_phones_mfa",
    "approved_pron_phones_mfa",
    "approved_phone_evidence",
    "decision",
    "notes",
)
LEGACY_NO_PATH_FIELDS = (
    "surface",
    "respelled",
    "rule_id",
    "evidence_source",
    "evidence_detail",
    "pron_phones_mfa",
    "decision",
    "notes",
)
JAMO_FIELDS = (
    "token",
    "model_input",
    "pron_phones_mfa",
    "approved_pron_phones_mfa",
    "decision",
    "evidence_source",
    "notes",
)
DECISION_FIELDS = (
    "review_order",
    "category",
    "token",
    "model_input",
    "model_candidate_phone",
    "recommendation_action",
    "researcher_decision",
    "approved_pron_phones_mfa",
    "approved_phone_source",
    "approved_phone_provenance",
    "researcher_notes",
    "source_handling",
    "source_url",
    "reason",
    "example_utt_id",
    "review_wav",
)
CORRECTION_FIELDS = (
    "review_order",
    "token",
    "correction_kind",
    "raw_search_token",
    "normalized_search_token",
    "source_notation",
    "approved_pron_phones_mfa",
    "researcher_decision",
    "researcher_notes",
    "example_utt_id",
)
REQUIRED_JAMO_LS_WORDS = {
    "외곬수적인",
    "외곬을",
    "외곬의",
    "천구백칤비육",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _clean(value: object) -> str:
    return str(value or "").strip()


def _verify_record(record: dict, *, label: str) -> dict:
    path = Path(_clean(record.get("path")))
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    if (
        actual["sha256"] != record.get("sha256")
        or actual["bytes"] != record.get("bytes")
    ):
        raise RuntimeError(f"{label} fingerprint mismatch")
    return actual


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != fields:
            raise RuntimeError(
                f"CSV field contract mismatch: {path} "
                f"{reader.fieldnames}"
            )
        return [
            {field: _clean(row.get(field)) for field in fields}
            for row in reader
        ]


def _read_no_path_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = tuple(reader.fieldnames or ())
        if fieldnames not in {NO_PATH_FIELDS, LEGACY_NO_PATH_FIELDS}:
            raise RuntimeError(
                f"no-path CSV field contract mismatch: {path} "
                f"{reader.fieldnames}"
            )
        rows = []
        for raw in reader:
            row = {
                field: _clean(raw.get(field)) for field in NO_PATH_FIELDS
            }
            if (
                fieldnames == LEGACY_NO_PATH_FIELDS
                and row["decision"] == "approved"
            ):
                row["approved_pron_phones_mfa"] = row[
                    "pron_phones_mfa"
                ]
                row["approved_phone_evidence"] = (
                    "legacy_same_frozen_jamo_candidate"
                )
            rows.append(row)
        return rows


def _same_record(left: dict, right: dict) -> bool:
    return (
        left.get("sha256") == right.get("sha256")
        and left.get("bytes") == right.get("bytes")
    )


def _canonical_no_path_review_row(row: dict) -> dict[str, str]:
    """Normalize repair v1/v2 and review rows to the review-ledger schema."""
    model_candidate = _clean(
        row.get("model_candidate_pron_phones_mfa")
        or row.get("pron_phones_mfa")
    )
    approved = _clean(
        row.get("approved_pron_phones_mfa")
        or row.get("pron_phones_mfa")
    )
    approved_evidence = _clean(row.get("approved_phone_evidence"))
    if (
        not approved_evidence
        and _clean(row.get("decision")) == "approved"
        and approved == model_candidate
    ):
        approved_evidence = "legacy_same_frozen_jamo_candidate"
    normalized = {
        field: _clean(row.get(field)) for field in NO_PATH_FIELDS
    }
    normalized["pron_phones_mfa"] = model_candidate
    normalized["approved_pron_phones_mfa"] = approved
    normalized["approved_phone_evidence"] = approved_evidence
    return normalized


def _same_no_path_row(left: dict, right: dict) -> bool:
    left_normalized = _canonical_no_path_review_row(left)
    right_normalized = _canonical_no_path_review_row(right)
    return all(
        left_normalized[field] == right_normalized[field]
        for field in NO_PATH_FIELDS
    )


def _approved_jamo_ls_pronunciations(release: dict) -> dict[str, str]:
    review_record = (
        release.get("dictionary_contract", {})
        .get("jamo_ls_researcher_review", {})
    )
    review_path = Path(str(review_record.get("path", "")))
    if not review_path.is_file():
        raise RuntimeError("r2 Jamo ㄽ review file missing")
    review_actual = file_fingerprint(
        review_path, with_sha256=True
    )
    if (
        review_actual["sha256"] != review_record.get("sha256")
        or review_actual["bytes"] != review_record.get("bytes")
    ):
        raise RuntimeError("r2 Jamo ㄽ review fingerprint mismatch")
    with review_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    pronunciations = {
        str(row.get("token", "")).strip(): str(
            row.get("approved_pron_phones_mfa", "")
        ).strip()
        for row in rows
        if str(row.get("decision", "")).strip() == "approved"
    }
    if (
        set(pronunciations) != REQUIRED_JAMO_LS_WORDS
        or any(not phones for phones in pronunciations.values())
        or len(rows) != len(REQUIRED_JAMO_LS_WORDS)
    ):
        raise RuntimeError("r2 Jamo ㄽ review approval rows invalid")

    approved_record = (
        release.get("dictionary_contract", {})
        .get("jamo_ls_approved_pronunciations", {})
    )
    approved_path = Path(str(approved_record.get("path", "")))
    if not approved_path.is_file():
        raise RuntimeError("r2 Jamo ㄽ approved dictionary missing")
    approved_actual = file_fingerprint(
        approved_path, with_sha256=True
    )
    if (
        approved_actual["sha256"] != approved_record.get("sha256")
        or approved_actual["bytes"] != approved_record.get("bytes")
    ):
        raise RuntimeError(
            "r2 Jamo ㄽ approved dictionary fingerprint mismatch"
        )
    approved_dictionary: dict[str, str] = {}
    for line in approved_path.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2 or parts[0] in approved_dictionary:
            raise RuntimeError(
                "r2 Jamo ㄽ approved dictionary row invalid"
            )
        approved_dictionary[parts[0]] = " ".join(parts[1:])
    if approved_dictionary != pronunciations:
        raise RuntimeError(
            "r2 Jamo ㄽ review and approved dictionary mismatch"
        )
    return pronunciations


def _verified_no_path_supplement(release: dict) -> dict:
    count = int(release.get("counts", {}).get(
        "g2p_reviewed_no_path_words", 0
    ))
    manual_count = int(release.get("counts", {}).get(
        "g2p_reviewed_no_path_manual_override_words", 0
    ))
    if count == 0:
        if manual_count != 0:
            raise RuntimeError(
                "r2 no-path manual override count without reviewed words"
            )
        return {
            "status": "not_applicable",
            "counts": {
                "reviewed_no_path_words": 0,
                "manual_phone_override_words": 0,
            },
        }
    record = (
        release.get("method_supplements", {})
        .get("reviewed_g2p_no_path", {})
    )
    path = Path(str(record.get("path", "")))
    actual = file_fingerprint(path, with_sha256=True)
    if (
        actual["sha256"] != record.get("sha256")
        or actual["bytes"] != record.get("bytes")
    ):
        raise RuntimeError("r2 no-path supplement fingerprint mismatch")
    supplement = _load(path)
    policy = supplement.get("policy", {})
    output_cache = supplement.get("outputs", {}).get("g2p_cache", {})
    release_cache = release.get("outputs", {}).get("g2p_cache", {})
    if (
        manual_count < 0
        or manual_count > count
        or supplement.get("schema_version") != NO_PATH_SCHEMA_VERSION
        or supplement.get("status") != "success"
        or supplement.get("kind")
        != "reviewed_g2p_no_path_method_supplement"
        or supplement.get("production_release_contract_id")
        != release.get("release_contract_id")
        or int(supplement.get("counts", {}).get(
            "reviewed_no_path_words", -1
        ))
        != count
        or policy.get("same_frozen_jamo_g2p_required") is not True
        or policy.get(
            "researcher_approved_standard_respelling_required"
        )
        is not True
        or policy.get(
            "manual_phone_override_same_acoustic_inventory_only"
        )
        is not True
        or int(supplement.get("counts", {}).get(
            "manual_phone_override_words", -1
        ))
        != manual_count
        or policy.get("only_missing_surface_keys_added") is not True
        or policy.get("existing_model_pronunciations_replaced") != 0
        or policy.get("final_spn_words") != 0
        or policy.get("phone_inventory_changed") is not False
        or output_cache.get("sha256") != release_cache.get("sha256")
        or output_cache.get("bytes") != release_cache.get("bytes")
        or release.get("counts", {}).get(
            "g2p_existing_model_pronunciations_replaced"
        )
        != 0
    ):
        raise RuntimeError("r2 no-path supplement hard gate failed")
    for repair in supplement.get("inputs", {}).get(
        "repair_manifests", []
    ):
        repair_path = Path(str(repair.get("path", "")))
        if not repair_path.is_file():
            raise RuntimeError("r2 no-path repair manifest missing")
        repair_actual = file_fingerprint(
            repair_path, with_sha256=True
        )
        if (
            repair_actual["sha256"] != repair.get("sha256")
            or repair_actual["bytes"] != repair.get("bytes")
        ):
            raise RuntimeError(
                "r2 no-path repair manifest fingerprint mismatch"
            )
    return {
        "status": "passed",
        "supplement": actual,
        "counts": {
            "reviewed_no_path_words": count,
            "manual_phone_override_words": manual_count,
        },
    }


def _verified_decision_application(
    *,
    release: dict,
    approved_jamo_pronunciations: dict[str, str],
    no_path: dict,
    application_path: Path,
) -> dict:
    """Prove workbook decisions reached every final pronunciation artifact."""
    application_path = application_path.resolve()
    application = _load(application_path)
    counts = application.get("counts", {})
    gates = application.get("gates", {})
    if (
        application.get("schema_version") != APPLICATION_SCHEMA_VERSION
        or application.get("status") != "applied"
        or application.get("kind") != APPLICATION_KIND
        or application.get("release_id") != release.get("release_id")
        or any(
            counts.get(key) != expected
            for key, expected in EXPECTED_APPLICATION_COUNTS.items()
        )
        or any(
            gates.get(key) is not expected
            for key, expected in EXPECTED_APPLICATION_GATES.items()
        )
    ):
        raise RuntimeError("researcher decision application hard gate failed")

    application_actual = file_fingerprint(
        application_path, with_sha256=True
    )
    outputs = application.get("outputs", {})
    output_actual = {
        label: _verify_record(
            outputs.get(label, {}), label=f"application {label}"
        )
        for label in (
            "no_path_review",
            "jamo_review",
            "correction_registry",
        )
    }
    for label in ("no_path_review", "jamo_review"):
        _verify_record(
            application.get("archives", {}).get(label, {}),
            label=f"application original {label} archive",
        )
        proposal = application.get("proposals", {}).get(label, {})
        _verify_record(
            proposal, label=f"application proposed {label}"
        )
        if not _same_record(proposal, output_actual[label]):
            raise RuntimeError(
                f"application proposed/output {label} mismatch"
            )
    correction_proposal = application.get("proposals", {}).get(
        "correction_registry", {}
    )
    _verify_record(
        correction_proposal,
        label="application proposed correction registry",
    )
    if not _same_record(
        correction_proposal, output_actual["correction_registry"]
    ):
        raise RuntimeError(
            "application proposed/output correction registry mismatch"
        )

    evidence = (
        application.get("archives", {}).get("decision_evidence", {})
    )
    required_evidence = {
        "validation_manifest",
        "template_manifest",
        "clean_template",
        "filled_workbook",
        "model_bundle",
        "normalized_decisions",
        "correction_registry",
    }
    if not required_evidence.issubset(evidence):
        raise RuntimeError(
            "application decision evidence archive is incomplete"
        )
    evidence_actual = {
        label: _verify_record(
            evidence[label], label=f"application evidence {label}"
        )
        for label in sorted(required_evidence)
    }
    validation_input = application.get("inputs", {}).get(
        "validation_manifest", {}
    )
    if not _same_record(
        validation_input, evidence_actual["validation_manifest"]
    ):
        raise RuntimeError(
            "application validation input/archive mismatch"
        )
    validation = _load(
        Path(evidence_actual["validation_manifest"]["path"])
    )
    if (
        validation.get("schema_version") != VALIDATION_SCHEMA_VERSION
        or validation.get("status") != "ready_for_apply"
        or validation.get("kind")
        != "common_pron_r2_researcher_decision_validation"
        or validation.get("ready_for_apply") is not True
        or validation.get("counts", {}).get(
            "normalized_decisions"
        )
        != 27
        or validation.get("counts", {}).get(
            "correction_registry_rows"
        )
        != 2
    ):
        raise RuntimeError(
            "archived researcher decision validation hard gate failed"
        )
    validation_inputs = validation.get("inputs", {})
    validation_outputs = validation.get("outputs", {})
    evidence_input_map = {
        "clean_template": "clean_template",
        "filled_workbook": "filled_workbook",
        "template_manifest": "template_manifest",
        "model_bundle": "model_bundle",
    }
    for validation_label, evidence_label in evidence_input_map.items():
        if not _same_record(
            validation_inputs.get(validation_label, {}),
            evidence_actual[evidence_label],
        ):
            raise RuntimeError(
                "validation input/evidence archive mismatch: "
                f"{validation_label}"
            )
    if not _same_record(
        validation_outputs.get("normalized_decisions", {}),
        evidence_actual["normalized_decisions"],
    ):
        raise RuntimeError(
            "validation decisions/evidence archive mismatch"
        )
    if not _same_record(
        validation_outputs.get("correction_registry", {}),
        evidence_actual["correction_registry"],
    ):
        raise RuntimeError(
            "validation correction/evidence archive mismatch"
        )
    if not _same_record(
        evidence_actual["correction_registry"],
        output_actual["correction_registry"],
    ):
        raise RuntimeError(
            "validated/applied correction registry mismatch"
        )

    decisions = _read_csv(
        Path(evidence_actual["normalized_decisions"]["path"]),
        DECISION_FIELDS,
    )
    decision_by_token = {
        row["token"]: row for row in decisions
    }
    if (
        len(decisions) != 27
        or len(decision_by_token) != 27
        or sum(row["category"] == "no_path" for row in decisions)
        != 23
        or sum(row["category"] == "jamo_ls" for row in decisions)
        != 4
        or any(
            row["researcher_decision"] not in AFFIRMATIVE_DECISIONS
            for row in decisions
        )
    ):
        raise RuntimeError(
            "normalized researcher decision contract mismatch"
        )

    no_path_rows = _read_no_path_csv(
        Path(output_actual["no_path_review"]["path"])
    )
    no_path_by_surface = {
        row["surface"]: row for row in no_path_rows
    }
    if (
        len(no_path_rows) != 24
        or len(no_path_by_surface) != 24
        or any(
            row["decision"] != "approved"
            or not row["approved_pron_phones_mfa"]
            for row in no_path_rows
        )
        or "읊어" not in no_path_by_surface
    ):
        raise RuntimeError(
            "applied no-path researcher review contract mismatch"
        )
    for token, decision in decision_by_token.items():
        if decision["category"] != "no_path":
            continue
        row = no_path_by_surface.get(token)
        if (
            row is None
            or decision["model_input"] != row["respelled"]
            or decision["model_candidate_phone"]
            != row["pron_phones_mfa"]
            or decision["approved_pron_phones_mfa"]
            != row["approved_pron_phones_mfa"]
        ):
            raise RuntimeError(
                f"normalized/applied no-path decision mismatch: {token}"
            )

    jamo_rows = _read_csv(
        Path(output_actual["jamo_review"]["path"]), JAMO_FIELDS
    )
    jamo_by_token = {row["token"]: row for row in jamo_rows}
    if (
        len(jamo_rows) != 4
        or len(jamo_by_token) != 4
        or set(jamo_by_token) != REQUIRED_JAMO_LS_WORDS
        or any(
            row["decision"] != "approved"
            or not row["approved_pron_phones_mfa"]
            for row in jamo_rows
        )
        or {
            token: row["approved_pron_phones_mfa"]
            for token, row in jamo_by_token.items()
        }
        != approved_jamo_pronunciations
    ):
        raise RuntimeError(
            "applied/final Jamo researcher review mismatch"
        )
    for token, row in jamo_by_token.items():
        decision = decision_by_token.get(token)
        if (
            decision is None
            or decision["category"] != "jamo_ls"
            or decision["model_input"] != row["model_input"]
            or decision["model_candidate_phone"]
            != row["pron_phones_mfa"]
            or decision["approved_pron_phones_mfa"]
            != row["approved_pron_phones_mfa"]
        ):
            raise RuntimeError(
                f"normalized/applied Jamo decision mismatch: {token}"
            )

    corrections = _read_csv(
        Path(output_actual["correction_registry"]["path"]),
        CORRECTION_FIELDS,
    )
    correction_by_token = {
        row["token"]: row for row in corrections
    }
    if (
        len(corrections) != 2
        or set(correction_by_token) != set(EXPECTED_CORRECTIONS)
    ):
        raise RuntimeError("applied correction registry token mismatch")
    for token, expected in EXPECTED_CORRECTIONS.items():
        row = correction_by_token[token]
        jamo_row = jamo_by_token[token]
        decision = decision_by_token[token]
        if (
            any(row.get(key) != value for key, value in expected.items())
            or row["researcher_decision"] not in AFFIRMATIVE_DECISIONS
            or row["researcher_decision"]
            != decision["researcher_decision"]
            or row["approved_pron_phones_mfa"]
            != jamo_row["approved_pron_phones_mfa"]
        ):
            raise RuntimeError(
                f"applied correction registry row mismatch: {token}"
            )

    if (
        no_path.get("status") != "passed"
        or no_path.get("counts", {}).get("reviewed_no_path_words")
        != 24
    ):
        raise RuntimeError(
            "final no-path supplement does not contain 24 approvals"
        )
    supplement = _load(Path(no_path["supplement"]["path"]))
    reviewed_candidates = supplement.get("reviewed_candidates", [])
    candidate_by_surface = {
        _clean(row.get("surface")): row
        for row in reviewed_candidates
    }
    if (
        len(reviewed_candidates) != 24
        or len(candidate_by_surface) != 24
        or set(candidate_by_surface) != set(no_path_by_surface)
        or any(
            not _same_no_path_row(
                candidate_by_surface[surface],
                no_path_by_surface[surface],
            )
            for surface in no_path_by_surface
        )
    ):
        raise RuntimeError(
            "application/final no-path candidate rows mismatch"
        )

    repaired_surfaces: set[str] = set()
    for repair_record in supplement.get("inputs", {}).get(
        "repair_manifests", []
    ):
        repair_actual = _verify_record(
            repair_record, label="final no-path repair manifest"
        )
        repair = _load(Path(repair_actual["path"]))
        if (
            repair.get("status") != "success"
            or repair.get("kind") != "reviewed_no_path_shard_repair"
        ):
            raise RuntimeError(
                "final no-path repair manifest contract mismatch"
            )
        snapshot_record = repair.get("inputs", {}).get(
            "approved_review_snapshot", {}
        )
        snapshot_actual = _verify_record(
            snapshot_record, label="final no-path approval snapshot"
        )
        snapshot_rows = _read_no_path_csv(
            Path(snapshot_actual["path"])
        )
        used_candidates = repair.get("used_candidates", [])
        if len(snapshot_rows) != len(used_candidates):
            raise RuntimeError(
                "final no-path repair snapshot/candidate count mismatch"
            )
        manifest_surfaces: set[str] = set()
        for snapshot_row in snapshot_rows:
            surface = snapshot_row["surface"]
            application_row = no_path_by_surface.get(surface)
            used = next(
                (
                    row
                    for row in used_candidates
                    if _clean(row.get("surface")) == surface
                ),
                None,
            )
            if (
                not surface
                or surface in repaired_surfaces
                or application_row is None
                or used is None
                or not _same_no_path_row(
                    snapshot_row, application_row
                )
                or not _same_no_path_row(used, application_row)
            ):
                raise RuntimeError(
                    "application/repair no-path row mismatch: "
                    f"{surface}"
                )
            repaired_surfaces.add(surface)
            manifest_surfaces.add(surface)
        if manifest_surfaces - {"읊어"}:
            researcher_review = repair.get("inputs", {}).get(
                "researcher_review", {}
            )
            if not _same_record(
                researcher_review, output_actual["no_path_review"]
            ):
                raise RuntimeError(
                    "new no-path repair did not use applied review ledger"
                )
    if repaired_surfaces != set(no_path_by_surface):
        raise RuntimeError(
            "final no-path repairs do not cover every approved surface"
        )

    return {
        "application": application_actual,
        "validation": evidence_actual["validation_manifest"],
        "filled_workbook": evidence_actual["filled_workbook"],
        "correction_registry": output_actual["correction_registry"],
        "counts": dict(EXPECTED_APPLICATION_COUNTS),
        "gates": {
            "decision_evidence_archived": True,
            "normalized_decisions_match_ledgers": True,
            "corrections_match_final_jamo": True,
            "no_path_repairs_match_application": True,
        },
    }


def build_adoption_contract(
    *,
    common_manifest_path: Path,
    frozen_bundle_contract_path: Path,
    decision_application_path: Path,
    difference_inventory_path: Path,
    researcher_approval_path: Path,
) -> dict:
    common_manifest_path = common_manifest_path.resolve()
    decision_application_path = decision_application_path.resolve()
    difference_inventory_path = difference_inventory_path.resolve()
    researcher_approval_path = researcher_approval_path.resolve()
    release = _load(common_manifest_path)
    counts = release.get("counts", {})
    if (
        release.get("schema_version") != LEXICON_SCHEMA_VERSION
        or release.get("status") != "success"
        or not str(release.get("release_id", "")).startswith(
            "common_pron_mfa_r2_"
        )
        or counts.get("g2p_missing") != 0
        or counts.get("g2p_spn_words") != 0
        or counts.get("phone_outside_acoustic_inventory") != 0
        or counts.get("observed_oov_coverage_missing") != 0
        or counts.get("g2p_jamo_ls_rewrite_words") != 4
        or (
            counts.get("g2p_jamo_ls_model_candidate_accepted_words", -1)
            + counts.get("g2p_jamo_ls_manual_override_words", -1)
        )
        != 4
        or release.get("dictionary_contract", {}).get(
            "jamo_ls_surface_key_restoration"
        )
        is not True
        or release.get("dictionary_contract", {}).get(
            "jamo_ls_manual_override_policy"
        )
        != "researcher_approved_same_acoustic_inventory_only"
    ):
        raise RuntimeError("r2 common dictionary hard gate failed")
    approved_pronunciations = _approved_jamo_ls_pronunciations(release)
    no_path = _verified_no_path_supplement(release)
    decision_application = _verified_decision_application(
        release=release,
        approved_jamo_pronunciations=approved_pronunciations,
        no_path=no_path,
        application_path=decision_application_path,
    )

    pin = verify_frozen_bundle(
        contract_path=frozen_bundle_contract_path
    )
    inputs = release.get("inputs", {})
    if (
        inputs.get("acoustic_model", {}).get("sha256")
        != pin["models"]["acoustic_model"]["sha256"]
        or inputs.get("g2p_model", {}).get("sha256")
        != pin["models"]["g2p_model"]["sha256"]
        or inputs.get("base_dictionary", {}).get("sha256")
        != pin["models"]["dictionary"]["sha256"]
    ):
        raise RuntimeError("r2 release does not use the frozen model pin")

    dictionary_record = release.get("outputs", {}).get("dictionary", {})
    dictionary_path = Path(str(dictionary_record.get("path", "")))
    dictionary_actual = file_fingerprint(
        dictionary_path, with_sha256=True
    )
    if (
        dictionary_actual["sha256"] != dictionary_record.get("sha256")
        or dictionary_actual["bytes"] != dictionary_record.get("bytes")
    ):
        raise RuntimeError("r2 dictionary fingerprint mismatch")

    difference = _load(difference_inventory_path)
    common_manifest_actual = file_fingerprint(
        common_manifest_path, with_sha256=True
    )
    if (
        difference.get("schema_version") != DIFFERENCE_SCHEMA_VERSION
        or difference.get("status") != "differences_inventoried"
        or difference.get("mode") != "difference-inventory"
        or not difference.get("gate", {}).get(
            "difference_inventory_complete"
        )
        or difference.get("gate", {}).get("allow_yearly_mfa")
        or difference.get("common_release", {})
        .get("manifest", {})
        .get("sha256")
        != common_manifest_actual["sha256"]
    ):
        raise RuntimeError("2020/2021 difference inventory gate failed")

    difference_actual = file_fingerprint(
        difference_inventory_path, with_sha256=True
    )
    approval = _load(researcher_approval_path)
    jamo_ls = approval.get("jamo_ls", {})
    if (
        approval.get("schema_version") != APPROVAL_SCHEMA_VERSION
        or approval.get("status") != "approved"
        or approval.get("approved") is not True
        or approval.get("common_manifest_sha256")
        != common_manifest_actual["sha256"]
        or approval.get("difference_inventory_sha256")
        != difference_actual["sha256"]
        or approval.get("decision_application_sha256")
        != decision_application["application"]["sha256"]
        or approval.get("correction_registry_sha256")
        != decision_application["correction_registry"]["sha256"]
        or jamo_ls.get("decision") != "approved"
        or jamo_ls.get("phone_inventory_changed") is not False
        or set(jamo_ls.get("required_words", []))
        != REQUIRED_JAMO_LS_WORDS
        or set(jamo_ls.get("reviewed_words", []))
        != REQUIRED_JAMO_LS_WORDS
        or jamo_ls.get("reviewed_pronunciations")
        != approved_pronunciations
    ):
        raise RuntimeError("researcher approval gate failed")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "recorded_at": now_iso(),
        "policy": "latest_jamo_common_dictionary_required",
        "common_release": {
            "manifest": common_manifest_actual,
            "dictionary": dictionary_actual,
            "release_id": release.get("release_id"),
        },
        "frozen_model_pin": {
            "commit": pin["expected"]["commit"],
            "contract": pin["contract"],
            "models": pin["models"],
        },
        "difference_inventory": difference_actual,
        "researcher_approval": file_fingerprint(
            researcher_approval_path, with_sha256=True
        ),
        "researcher_decision_application": decision_application,
        "reviewed_no_path": no_path,
        "gate": {
            "dictionary_missing": 0,
            "dictionary_spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
            "difference_inventory_complete": True,
            "jamo_ls_researcher_approval": True,
            "researcher_decision_application": True,
            "source_correction_registry": True,
            "reviewed_no_path_method_supplement": (
                no_path["status"] in {"passed", "not_applicable"}
            ),
            "allow_yearly_mfa": True,
            "legacy_inline_g2p_default": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common-manifest", type=Path, required=True)
    parser.add_argument(
        "--frozen-bundle-contract", type=Path, required=True
    )
    parser.add_argument(
        "--decision-application", type=Path, required=True
    )
    parser.add_argument(
        "--difference-inventory", type=Path, required=True
    )
    parser.add_argument(
        "--researcher-approval", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = build_adoption_contract(
        common_manifest_path=args.common_manifest,
        frozen_bundle_contract_path=args.frozen_bundle_contract,
        decision_application_path=args.decision_application,
        difference_inventory_path=args.difference_inventory,
        researcher_approval_path=args.researcher_approval,
    )
    atomic_write_json(args.output, contract)
    print(
        "[OK] common pronunciation adoption contract: "
        f"{contract['common_release']['release_id']} -> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

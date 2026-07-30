"""Materialize prior explicit researcher decisions as an approval contract."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "common_pron_mfa_researcher_approval.v2"
APPLICATION_SCHEMA_VERSION = (
    "common_pron_researcher_decision_application.v1"
)
DIFFERENCE_SCHEMA_VERSION = "common_pron_mfa_difference_inventory.v2"
LEXICON_SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"
REQUIRED_JAMO_LS_WORDS = {
    "외곬수적인",
    "외곬을",
    "외곬의",
    "천구백칤비육",
}
JAMO_FIELDS = (
    "token",
    "model_input",
    "pron_phones_mfa",
    "approved_pron_phones_mfa",
    "decision",
    "evidence_source",
    "notes",
)
REQUIRED_APPLICATION_GATES = {
    "exclusive_runner_lock_held": True,
    "originals_archived_before_promotion": True,
    "no_path_post_write_verified": True,
    "jamo_post_write_verified": True,
    "correction_registry_hash_verified": True,
    "raw_corpus_modified": False,
    "g2p_shards_modified": False,
    "final_dictionary_created": False,
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _verify_record(record: dict, *, label: str) -> dict:
    path = Path(str(record.get("path", "")))
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    if (
        actual["sha256"] != record.get("sha256")
        or actual["bytes"] != record.get("bytes")
    ):
        raise RuntimeError(f"{label} fingerprint mismatch")
    return actual


def _read_approved_jamo(path: Path) -> tuple[dict[str, str], list[dict]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != JAMO_FIELDS:
            raise RuntimeError("Jamo researcher review field contract mismatch")
        rows = [
            {
                field: str(row.get(field, "") or "").strip()
                for field in JAMO_FIELDS
            }
            for row in reader
        ]
    by_word = {row["token"]: row for row in rows}
    if (
        len(rows) != 4
        or len(by_word) != 4
        or set(by_word) != REQUIRED_JAMO_LS_WORDS
        or any(
            row["decision"] != "approved"
            or not row["approved_pron_phones_mfa"]
            or not row["evidence_source"]
            or not row["notes"]
            for row in rows
        )
    ):
        raise RuntimeError("Jamo researcher approval rows invalid")
    return (
        {
            word: by_word[word]["approved_pron_phones_mfa"]
            for word in sorted(by_word)
        },
        rows,
    )


def build_researcher_approval(
    *,
    common_manifest_path: Path,
    difference_inventory_path: Path,
    decision_application_path: Path,
    decision_record_path: Path,
) -> dict:
    common_manifest_path = common_manifest_path.resolve()
    difference_inventory_path = difference_inventory_path.resolve()
    decision_application_path = decision_application_path.resolve()
    decision_record_path = decision_record_path.resolve()

    common = _load(common_manifest_path)
    difference = _load(difference_inventory_path)
    application = _load(decision_application_path)
    if (
        common.get("schema_version") != LEXICON_SCHEMA_VERSION
        or common.get("status") != "success"
    ):
        raise RuntimeError("common pronunciation manifest gate failed")
    if (
        difference.get("schema_version") != DIFFERENCE_SCHEMA_VERSION
        or difference.get("status") != "differences_inventoried"
        or difference.get("gate", {}).get(
            "difference_inventory_complete"
        )
        is not True
        or difference.get("gate", {}).get("allow_yearly_mfa") is not False
    ):
        raise RuntimeError("difference inventory gate failed")
    if (
        application.get("schema_version")
        != APPLICATION_SCHEMA_VERSION
        or application.get("status") != "applied"
        or any(
            application.get("gates", {}).get(key) is not expected
            for key, expected in REQUIRED_APPLICATION_GATES.items()
        )
    ):
        raise RuntimeError("researcher decision application gate failed")

    correction = _verify_record(
        application.get("outputs", {}).get("correction_registry", {}),
        label="correction registry",
    )
    jamo_record = (
        common.get("dictionary_contract", {})
        .get("jamo_ls_researcher_review", {})
    )
    jamo_actual = _verify_record(
        jamo_record, label="Jamo researcher review"
    )
    pronunciations, rows = _read_approved_jamo(
        Path(jamo_actual["path"])
    )
    phone_inventory = set(
        application.get("phone_inventory_contract", {}).get("phones", [])
    )
    if not phone_inventory or any(
        phone not in phone_inventory
        for row in rows
        for phone in row["approved_pron_phones_mfa"].split()
    ):
        raise RuntimeError("approved Jamo phone outside frozen inventory")

    decision_text = decision_record_path.read_text(encoding="utf-8-sig")
    if (
        "상태: 확정" not in decision_text
        or "2020–2025 여섯 연도 전부" not in decision_text
        or "difference inventory는 구결과 재사용 여부를 결정하는" not in
        decision_text
    ):
        raise RuntimeError("binding six-year decision record gate failed")

    common_actual = file_fingerprint(
        common_manifest_path, with_sha256=True
    )
    difference_actual = file_fingerprint(
        difference_inventory_path, with_sha256=True
    )
    application_actual = file_fingerprint(
        decision_application_path, with_sha256=True
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "approved",
        "approved": True,
        "recorded_at": now_iso(),
        "approval_basis": (
            "prior_explicit_researcher_decision_record_and_approved_workbook"
        ),
        "scope": {
            "common_pronunciation_release": common.get("release_id"),
            "years": [2020, 2021, 2022, 2023, 2024, 2025],
            "realign_all_six_years": True,
            "difference_inventory_is_transition_audit": True,
            "g2p_phone_is_not_realization_judgment": True,
        },
        "common_manifest_sha256": common_actual["sha256"],
        "difference_inventory_sha256": difference_actual["sha256"],
        "decision_application_sha256": application_actual["sha256"],
        "correction_registry_sha256": correction["sha256"],
        "jamo_ls": {
            "decision": "approved",
            "phone_inventory_changed": False,
            "required_words": sorted(REQUIRED_JAMO_LS_WORDS),
            "reviewed_words": sorted(pronunciations),
            "reviewed_pronunciations": pronunciations,
        },
        "evidence": {
            "binding_decision_record": file_fingerprint(
                decision_record_path, with_sha256=True
            ),
            "common_manifest": common_actual,
            "difference_inventory": difference_actual,
            "decision_application": application_actual,
            "correction_registry": correction,
            "jamo_researcher_review": jamo_actual,
            "filled_workbook": _verify_record(
                application.get("archives", {})
                .get("decision_evidence", {})
                .get("filled_workbook", {}),
                label="filled researcher workbook",
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--common-manifest", type=Path, required=True)
    parser.add_argument("--difference-inventory", type=Path, required=True)
    parser.add_argument("--decision-application", type=Path, required=True)
    parser.add_argument("--decision-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    approval = build_researcher_approval(
        common_manifest_path=args.common_manifest,
        difference_inventory_path=args.difference_inventory,
        decision_application_path=args.decision_application,
        decision_record_path=args.decision_record,
    )
    atomic_write_json(args.output, approval)
    print(
        "[OK] researcher approval contract: "
        f"{approval['scope']['common_pronunciation_release']} -> "
        f"{args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

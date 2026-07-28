"""Build the only contract allowed to authorize yearly MFA with r2."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso
from verify_frozen_mfa_bundle import verify_frozen_bundle


SCHEMA_VERSION = "common_pron_mfa_adoption.v2"
APPROVAL_SCHEMA_VERSION = "common_pron_mfa_researcher_approval.v1"
DIFFERENCE_SCHEMA_VERSION = "common_pron_mfa_difference_inventory.v2"
LEXICON_SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"
NO_PATH_SCHEMA_VERSION = "common_pron_g2p_no_path_supplement.v1"
REQUIRED_JAMO_LS_WORDS = {
    "외곬수적인",
    "외곬을",
    "외곬의",
    "천구백칤비육",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _approved_jamo_ls_pronunciations(release: dict) -> dict[str, str]:
    record = (
        release.get("dictionary_contract", {})
        .get("jamo_ls_researcher_review", {})
    )
    path = Path(str(record.get("path", "")))
    if not path.is_file():
        raise RuntimeError("r2 no-path supplement file missing")
    actual = file_fingerprint(path, with_sha256=True)
    if (
        actual["sha256"] != record.get("sha256")
        or actual["bytes"] != record.get("bytes")
    ):
        raise RuntimeError("r2 Jamo ㄽ review fingerprint mismatch")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    pronunciations = {
        str(row.get("token", "")).strip(): str(
            row.get("pron_phones_mfa", "")
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
    return pronunciations


def _verified_no_path_supplement(release: dict) -> dict:
    count = int(release.get("counts", {}).get(
        "g2p_reviewed_no_path_words", 0
    ))
    if count == 0:
        return {
            "status": "not_applicable",
            "counts": {"reviewed_no_path_words": 0},
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
        supplement.get("schema_version") != NO_PATH_SCHEMA_VERSION
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
        "counts": {"reviewed_no_path_words": count},
    }


def build_adoption_contract(
    *,
    common_manifest_path: Path,
    frozen_bundle_contract_path: Path,
    difference_inventory_path: Path,
    researcher_approval_path: Path,
) -> dict:
    common_manifest_path = common_manifest_path.resolve()
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
        or release.get("dictionary_contract", {}).get(
            "jamo_ls_surface_key_restoration"
        )
        is not True
    ):
        raise RuntimeError("r2 common dictionary hard gate failed")
    approved_pronunciations = _approved_jamo_ls_pronunciations(release)
    no_path = _verified_no_path_supplement(release)

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
        "reviewed_no_path": no_path,
        "gate": {
            "dictionary_missing": 0,
            "dictionary_spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
            "difference_inventory_complete": True,
            "jamo_ls_researcher_approval": True,
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

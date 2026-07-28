"""Attach reviewed G2P no-path provenance to a completed r2 release.

``build_common_pron_mfa_lexicon.py`` is frozen in the prepare manifest and
therefore must not be edited while the 35 long-running shards are in flight.
Its generic finalizer can verify a repaired shard, but it cannot know that a
small number of keys came from researcher-approved standard-pronunciation
respellings.  This post-finalization supplement makes that provenance explicit.

The supplement:

* verifies every repair manifest, original partial backup, approval snapshot,
  final repaired shard, and final release shard fingerprint;
* relabels only the corresponding rows in ``g2p_cache.csv``;
* preserves the final dictionary and every phone sequence;
* creates a new production release contract ID derived from the frozen prepare
  contract and the reviewed repair manifests; and
* atomically updates the release manifest so downstream adoption cannot mistake
  a reviewed fallback for direct surface-form G2P.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from build_common_pron_mfa_lexicon import (
    canonical_identity,
    read_generated_dictionary,
    write_csv,
)
from common_pron_no_path_review import (
    REVIEW_FIELDS,
    SCHEMA_VERSION as REPAIR_SCHEMA_VERSION,
    read_review,
)
from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEXICON_SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"
SUPPLEMENT_SCHEMA_VERSION = "common_pron_g2p_no_path_supplement.v1"
FALLBACK_SOURCE = (
    "korean_mfa_jamo_g2p_v3.2.0_1best_from_"
    "researcher_approved_standard_respelling"
)
DIRECT_SOURCE = "korean_mfa_jamo_g2p_v3.2.0_1best_strict"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _verify_fingerprint(record: dict, *, label: str) -> dict:
    path = Path(str(record.get("path", "")))
    if not path.is_file():
        raise RuntimeError(f"{label} 파일 없음: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    for key in ("bytes", "sha256"):
        if str(actual[key]).lower() != str(record.get(key, "")).lower():
            raise RuntimeError(f"{label} fingerprint 불일치: {path} {key}")
    return actual


def _ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root = root.resolve()
    if resolved != root and root not in resolved.parents:
        raise RuntimeError(f"경로 경계 위반: {resolved} (root={root})")
    return resolved


def _read_cache(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        rows = [
            {field: str(row.get(field, "")) for field in fields}
            for row in reader
        ]
    required = {"token", "pron_phones_mfa", "pron_source"}
    if not required.issubset(fields):
        raise RuntimeError(f"G2P cache 필수 열 누락: {sorted(required-set(fields))}")
    tokens = [row["token"].strip() for row in rows]
    if not rows or len(tokens) != len(set(tokens)) or any(not x for x in tokens):
        raise RuntimeError("G2P cache token이 비었거나 중복됨")
    return fields, rows


def _repair_records(release_root: Path, release: dict) -> list[dict]:
    repair_root = release_root / "_state" / "no_path_repairs"
    paths = sorted(repair_root.glob("oov_*/repair_manifest.json"))
    if not paths:
        return []
    release_shards = {
        str(record.get("sha256", "")): record
        for record in release.get("g2p_output_shards", [])
        if str(record.get("sha256", ""))
    }
    records = []
    seen_surfaces: set[str] = set()
    for path in paths:
        manifest = _load_json(path)
        if (
            manifest.get("schema_version") != REPAIR_SCHEMA_VERSION
            or manifest.get("status") != "success"
            or manifest.get("kind") != "reviewed_no_path_shard_repair"
        ):
            raise RuntimeError(f"no-path repair manifest 계약 불일치: {path}")
        inputs = manifest.get("inputs", {})
        output = manifest.get("output", {})
        partial = inputs.get("partial_output", {})
        backup = _verify_fingerprint(
            inputs.get("partial_output_backup", {}),
            label="no-path partial backup",
        )
        if (
            str(backup["sha256"]).lower()
            != str(partial.get("sha256", "")).lower()
            or int(backup["bytes"]) != int(partial.get("bytes", -1))
        ):
            raise RuntimeError(f"partial backup이 원 partial과 다름: {path}")
        snapshot_path = Path(
            str(inputs.get("approved_review_snapshot", {}).get("path", ""))
        )
        _verify_fingerprint(
            inputs.get("approved_review_snapshot", {}),
            label="no-path approval snapshot",
        )
        snapshot = read_review(snapshot_path)
        used = list(manifest.get("used_candidates", []))
        snapshot_by_surface = {row["surface"]: row for row in snapshot}
        if (
            len(snapshot_by_surface) != len(snapshot)
            or len(used) != len(snapshot)
            or int(manifest.get("counts", {}).get(
                "reviewed_fallback_words", -1
            ))
            != len(used)
        ):
            raise RuntimeError(f"no-path 승인 snapshot 수량 불일치: {path}")
        repaired = _verify_fingerprint(
            output.get("repaired_shard", {}),
            label="no-path repaired shard",
        )
        if repaired["sha256"] not in release_shards:
            raise RuntimeError(
                f"final release가 repaired shard SHA를 참조하지 않음: {path}"
            )
        dictionary_rows = read_generated_dictionary(Path(repaired["path"]))
        for candidate in used:
            surface = str(candidate.get("surface", "")).strip()
            phones = str(candidate.get("pron_phones_mfa", "")).strip()
            snapshot_row = snapshot_by_surface.get(surface)
            if (
                not surface
                or surface in seen_surfaces
                or snapshot_row is None
                or snapshot_row.get("decision") != "approved"
                or snapshot_row.get("respelled")
                != str(candidate.get("respelled", "")).strip()
                or snapshot_row.get("pron_phones_mfa") != phones
                or " ".join(dictionary_rows.get(surface, ())) != phones
            ):
                raise RuntimeError(
                    f"no-path 승인 후보/최종 shard 불일치: {surface}"
                )
            seen_surfaces.add(surface)
        records.append(
            {
                "manifest": file_fingerprint(path, with_sha256=True),
                "repair": manifest,
            }
        )
    return records


def _candidate_generation_contract(
    release_root: Path, release: dict
) -> dict:
    path = (
        release_root
        / "00_contract"
        / "g2p_no_path_review_manifest.json"
    )
    if not path.is_file():
        raise RuntimeError("no-path candidate generation contract 없음")
    manifest = _load_json(path)
    if (
        manifest.get("schema_version") != REPAIR_SCHEMA_VERSION
        or manifest.get("status") not in {"review_pending", "approved"}
        or manifest.get("kind")
        != "reviewed_standard_pronunciation_no_path_candidates"
    ):
        raise RuntimeError("no-path candidate generation contract 불일치")
    inputs = manifest.get("inputs", {})
    for key in (
        "helper_code",
        "mapping",
        "respelled_g2p",
        "acoustic_model",
        "g2p_model",
        "frozen_model_pin",
    ):
        _verify_fingerprint(
            inputs.get(key, {}), label=f"no-path candidate {key}"
        )
    _verify_fingerprint(
        manifest.get("output", {}).get("researcher_review", {}),
        label="no-path researcher review",
    )
    release_inputs = release.get("inputs", {})
    if (
        inputs["g2p_model"].get("sha256")
        != release_inputs.get("g2p_model", {}).get("sha256")
        or inputs["acoustic_model"].get("sha256")
        != release_inputs.get("acoustic_model", {}).get("sha256")
    ):
        raise RuntimeError(
            "no-path 후보와 r2 final의 동결 model SHA 불일치"
        )
    return file_fingerprint(path, with_sha256=True)


def _patch_release(
    *,
    release: dict,
    prepared_contract_id: str,
    production_contract_id: str,
    supplement_record: dict,
    cache_record: dict,
    fallback_count: int,
) -> dict:
    patched = dict(release)
    patched["prepared_release_contract_id"] = prepared_contract_id
    patched["release_contract_id"] = production_contract_id
    patched["phone_policy"] = (
        "preserve base dictionary rows; add direct frozen Korean Jamo G2P "
        "v3.2.0 1-best strict OOV; deterministic no-path surfaces may use "
        "phones generated by the same frozen model from an explicitly "
        "documented standard-pronunciation respelling only after researcher "
        "approval; never replace an existing model pronunciation; no "
        "Urimalsaem variants"
    )
    g2p_contract = dict(patched.get("g2p_contract", {}))
    g2p_contract["deterministic_no_path_policy"] = {
        "status": "reviewed_fallback_applied",
        "same_frozen_model_required": True,
        "researcher_approval_required": True,
        "existing_model_pronunciations_replaced": 0,
        "final_spn_allowed": False,
        "supplement": supplement_record,
    }
    patched["g2p_contract"] = g2p_contract
    dictionary_contract = dict(patched.get("dictionary_contract", {}))
    dictionary_contract["reviewed_no_path_fallback"] = {
        "status": "passed",
        "words": fallback_count,
        "changes_phone_inventory": False,
        "existing_model_pronunciations_replaced": 0,
        "supplement": supplement_record,
    }
    patched["dictionary_contract"] = dictionary_contract
    counts = dict(patched.get("counts", {}))
    output_words = int(counts.get("g2p_output_words", 0))
    jamo_ls_words = int(counts.get("g2p_jamo_ls_rewrite_words", 0))
    direct_words = output_words - jamo_ls_words - fallback_count
    if direct_words < 0:
        raise RuntimeError("no-path supplement direct G2P 수량이 음수")
    counts["g2p_direct_surface_model_words"] = direct_words
    counts["g2p_reviewed_no_path_words"] = fallback_count
    counts["g2p_existing_model_pronunciations_replaced"] = 0
    patched["counts"] = counts
    outputs = dict(patched.get("outputs", {}))
    outputs["g2p_cache"] = cache_record
    patched["outputs"] = outputs
    required = dict(patched.get("required_before_mfa", {}))
    required["reviewed_no_path_method_supplement"] = "passed"
    patched["required_before_mfa"] = required
    patched["method_supplements"] = {
        **dict(patched.get("method_supplements", {})),
        "reviewed_g2p_no_path": supplement_record,
    }
    return patched


def finalize_supplement(release_root: Path) -> dict:
    release_root = release_root.resolve()
    release_manifest_path = _ensure_within(
        release_root / "00_contract" / "release_manifest.json",
        release_root,
    )
    supplement_path = _ensure_within(
        release_root
        / "00_contract"
        / "g2p_no_path_method_supplement.json",
        release_root,
    )
    if not release_manifest_path.is_file():
        raise RuntimeError("r2 final release manifest가 아직 없음")
    release = _load_json(release_manifest_path)
    if (
        release.get("schema_version") != LEXICON_SCHEMA_VERSION
        or release.get("status") != "success"
    ):
        raise RuntimeError("r2 final release manifest 계약 불일치")

    dictionary_record = _verify_fingerprint(
        release.get("outputs", {}).get("dictionary", {}),
        label="r2 final dictionary",
    )
    cache_manifest_record = release.get("outputs", {}).get("g2p_cache", {})
    cache_path = Path(str(cache_manifest_record.get("path", "")))
    if not cache_path.is_file():
        raise RuntimeError(f"r2 G2P cache 파일 없음: {cache_path}")
    cache_record_before = file_fingerprint(cache_path, with_sha256=True)
    repairs = _repair_records(release_root, release)
    if not repairs:
        return {
            "schema_version": SUPPLEMENT_SCHEMA_VERSION,
            "status": "not_applicable",
            "counts": {"reviewed_no_path_words": 0},
        }
    candidate_contract = _candidate_generation_contract(
        release_root, release
    )

    used: dict[str, dict] = {}
    for record in repairs:
        for candidate in record["repair"]["used_candidates"]:
            surface = str(candidate["surface"]).strip()
            if surface in used:
                raise RuntimeError(f"no-path surface 중복 보수: {surface}")
            used[surface] = candidate

    fields, cache_rows = _read_cache(cache_path)
    cache_by_token = {row["token"].strip(): row for row in cache_rows}
    for surface, candidate in used.items():
        row = cache_by_token.get(surface)
        phones = str(candidate["pron_phones_mfa"]).strip()
        if row is None or row["pron_phones_mfa"].strip() != phones:
            raise RuntimeError(f"G2P cache no-path 후보 불일치: {surface}")
        source = row["pron_source"].strip()
        if source not in {DIRECT_SOURCE, FALLBACK_SOURCE}:
            raise RuntimeError(
                f"G2P cache no-path source 계약 불일치: {surface} {source}"
            )

    prepared_contract_id = str(
        release.get(
            "prepared_release_contract_id",
            release.get("release_contract_id", ""),
        )
    )
    if not prepared_contract_id:
        raise RuntimeError("r2 prepared release contract ID 누락")
    repair_manifest_records = [
        record["manifest"] for record in repairs
    ]
    if supplement_path.is_file():
        existing = _load_json(supplement_path)
        if (
            existing.get("schema_version") != SUPPLEMENT_SCHEMA_VERSION
            or existing.get("status") != "success"
            or existing.get("kind")
            != "reviewed_g2p_no_path_method_supplement"
            or existing.get("prepared_release_contract_id")
            != prepared_contract_id
        ):
            raise RuntimeError("기존 no-path method supplement 계약 불일치")
        expected_repairs = [
            (record["bytes"], record["sha256"])
            for record in repair_manifest_records
        ]
        actual_repairs = [
            (record.get("bytes"), record.get("sha256"))
            for record in existing.get("inputs", {}).get(
                "repair_manifests", []
            )
        ]
        existing_candidate_contract = (
            existing.get("inputs", {})
            .get("candidate_generation_contract", {})
        )
        existing_candidates = {
            str(row.get("surface", "")).strip(): row
            for row in existing.get("reviewed_candidates", [])
        }
        if (
            actual_repairs != expected_repairs
            or (
                existing_candidate_contract.get("bytes"),
                existing_candidate_contract.get("sha256"),
            )
            != (
                candidate_contract["bytes"],
                candidate_contract["sha256"],
            )
            or set(existing_candidates) != set(used)
            or any(
                str(existing_candidates[surface].get(
                    "pron_phones_mfa", ""
                )).strip()
                != str(candidate["pron_phones_mfa"]).strip()
                for surface, candidate in used.items()
            )
        ):
            raise RuntimeError(
                "기존 no-path method supplement repair 계약 불일치"
            )
        existing_cache = existing.get("outputs", {}).get("g2p_cache", {})
        if any(
            str(cache_record_before[key]).lower()
            != str(existing_cache.get(key, "")).lower()
            for key in ("bytes", "sha256")
        ):
            raise RuntimeError(
                "기존 no-path method supplement cache fingerprint 불일치"
            )
        for surface in used:
            if cache_by_token[surface]["pron_source"] != FALLBACK_SOURCE:
                raise RuntimeError(
                    f"기존 no-path cache source가 fallback이 아님: {surface}"
                )
        supplement_record = file_fingerprint(
            supplement_path, with_sha256=True
        )
        production_contract_id = str(
            existing.get("production_release_contract_id", "")
        )
        if not production_contract_id:
            raise RuntimeError("기존 production release contract ID 누락")
        release_reference = (
            release.get("method_supplements", {})
            .get("reviewed_g2p_no_path", {})
        )
        release_current = (
            release.get("release_contract_id") == production_contract_id
            and release.get("counts", {}).get(
                "g2p_reviewed_no_path_words"
            )
            == len(used)
            and str(release_reference.get("sha256", "")).lower()
            == str(supplement_record["sha256"]).lower()
            and str(
                release.get("outputs", {})
                .get("g2p_cache", {})
                .get("sha256", "")
            ).lower()
            == str(cache_record_before["sha256"]).lower()
        )
        if not release_current:
            patched_release = _patch_release(
                release=release,
                prepared_contract_id=prepared_contract_id,
                production_contract_id=production_contract_id,
                supplement_record=supplement_record,
                cache_record=cache_record_before,
                fallback_count=len(used),
            )
            atomic_write_json(release_manifest_path, patched_release)
        return existing

    for surface in used:
        cache_by_token[surface]["pron_source"] = FALLBACK_SOURCE
    write_csv(cache_path, fields, cache_rows)
    cache_record = file_fingerprint(cache_path, with_sha256=True)

    identity_payload = {
        "schema_version": SUPPLEMENT_SCHEMA_VERSION,
        "prepared_release_contract_id": prepared_contract_id,
        "policy": (
            "same_frozen_jamo_g2p_on_researcher_approved_"
            "standard_respelling_for_deterministic_no_path_only"
        ),
        "repair_manifests": [
            {
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            }
            for record in repair_manifest_records
        ],
        "candidate_generation_contract": {
            "bytes": candidate_contract["bytes"],
            "sha256": candidate_contract["sha256"],
        },
        "dictionary": {
            "bytes": dictionary_record["bytes"],
            "sha256": dictionary_record["sha256"],
        },
        "g2p_cache": {
            "bytes": cache_record["bytes"],
            "sha256": cache_record["sha256"],
        },
    }
    production_contract_id = canonical_identity(identity_payload)
    supplement = {
        "schema_version": SUPPLEMENT_SCHEMA_VERSION,
        "status": "success",
        "kind": "reviewed_g2p_no_path_method_supplement",
        "recorded_at": now_iso(),
        "release_id": release.get("release_id"),
        "prepared_release_contract_id": prepared_contract_id,
        "production_release_contract_id": production_contract_id,
        "policy": {
            "same_frozen_jamo_g2p_required": True,
            "researcher_approved_standard_respelling_required": True,
            "only_missing_surface_keys_added": True,
            "existing_model_pronunciations_replaced": 0,
            "final_spn_words": 0,
            "phone_inventory_changed": False,
        },
        "counts": {
            "repair_manifests": len(repairs),
            "reviewed_no_path_words": len(used),
            "existing_model_pronunciations_replaced": 0,
        },
        "reviewed_candidates": [
            used[surface] for surface in sorted(used)
        ],
        "inputs": {
            "helper_code": file_fingerprint(
                Path(__file__), with_sha256=True
            ),
            "repair_manifests": repair_manifest_records,
            "candidate_generation_contract": candidate_contract,
            "dictionary": dictionary_record,
        },
        "outputs": {"g2p_cache": cache_record},
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(supplement_path, supplement)
    supplement_record = file_fingerprint(
        supplement_path, with_sha256=True
    )
    patched_release = _patch_release(
        release=release,
        prepared_contract_id=prepared_contract_id,
        production_contract_id=production_contract_id,
        supplement_record=supplement_record,
        cache_record=cache_record,
        fallback_count=len(used),
    )
    atomic_write_json(release_manifest_path, patched_release)
    return supplement


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, required=True)
    args = parser.parse_args()
    payload = finalize_supplement(args.release_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

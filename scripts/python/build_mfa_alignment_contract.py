"""MFA 정렬 입력의 모델·런타임 fingerprint 계약을 만든다.

기존 ``lab_input_contract_id``는 검색 CSV와 lab 생성 정책을 고정하지만,
같은 이름의 acoustic/dictionary/G2P 파일이 교체되는 경우를 구분하지 못했다.
이 스크립트는 세 모델 파일의 SHA256과 MFA/Pynini/Python 판본을 결합해
``alignment_contract_id``를 만들고 원자적으로 기록한다.

모델 경로·파일명·mtime은 감사용 기록에는 남기되, 같은 내용의 파일을 다른
기계나 경로로 옮겨도 계약 ID가 바뀌지 않도록 ID 계산에서는 제외한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso
from verify_frozen_mfa_bundle import verify_frozen_bundle

SCHEMA_VERSION = "mfa_alignment_contract.v1"


def installed_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not_installed"


def runtime_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "montreal_forced_aligner": installed_version(
            "montreal-forced-aligner"
        ),
        "pynini": installed_version("pynini"),
    }


def model_fingerprint(
    *, role: str, requested_name: str, path: Path
) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"{role} 모델 파일 없음: {path}")
    result = file_fingerprint(path, with_sha256=True)
    return {
        "role": role,
        "requested_name": requested_name,
        "path": result["path"],
        "filename": path.name,
        "bytes": result["bytes"],
        "mtime_ns": result["mtime_ns"],
        "sha256": result["sha256"],
    }


def build_alignment_contract(
    *,
    year: str,
    lab_input_contract_id: str,
    acoustic_model_path: Path,
    dictionary_model_path: Path,
    g2p_model_path: Path,
    acoustic_model_name: str = "korean_mfa",
    dictionary_model_name: str = "korean_mfa",
    g2p_model_name: str = "korean_mfa",
    frozen_bundle_contract_path: Path | None = None,
    common_pron_manifest_path: Path | None = None,
    common_pron_adoption_path: Path | None = None,
    allow_legacy_inline_g2p: bool = False,
    runtime: dict[str, str] | None = None,
) -> dict:
    if not year.strip():
        raise ValueError("year가 비어 있음")
    if not lab_input_contract_id.strip():
        raise ValueError("lab_input_contract_id가 비어 있음")

    if frozen_bundle_contract_path is None:
        raise ValueError("frozen_bundle_contract_path is required")

    models = {
        "acoustic": model_fingerprint(
            role="acoustic",
            requested_name=acoustic_model_name,
            path=acoustic_model_path,
        ),
        "dictionary": model_fingerprint(
            role="dictionary",
            requested_name=dictionary_model_name,
            path=dictionary_model_path,
        ),
        "g2p": model_fingerprint(
            role="g2p",
            requested_name=g2p_model_name,
            path=g2p_model_path,
        ),
    }
    frozen_pin = verify_frozen_bundle(
        contract_path=frozen_bundle_contract_path
    )
    if (
        models["acoustic"]["sha256"]
        != frozen_pin["models"]["acoustic_model"]["sha256"]
        or models["g2p"]["sha256"]
        != frozen_pin["models"]["g2p_model"]["sha256"]
    ):
        raise RuntimeError(
            "alignment acoustic/G2P does not match frozen MFA pin"
        )

    common_release = None
    common_adoption = None
    if common_pron_manifest_path is not None:
        if common_pron_adoption_path is None:
            raise RuntimeError(
                "common pronunciation adoption contract is required"
            )
        common_release = json.loads(
            common_pron_manifest_path.read_text(encoding="utf-8-sig")
        )
        common_adoption = json.loads(
            common_pron_adoption_path.read_text(encoding="utf-8-sig")
        )
        counts = common_release.get("counts", {})
        if (
            common_release.get("schema_version")
            != "common_pron_mfa_lexicon.v2"
            or common_release.get("status") != "success"
            or not str(common_release.get("release_id", "")).startswith(
                "common_pron_mfa_r2_"
            )
            or counts.get("g2p_missing") != 0
            or counts.get("g2p_spn_words") != 0
            or counts.get("phone_outside_acoustic_inventory") != 0
            or counts.get("g2p_jamo_ls_rewrite_words") != 4
            or common_release.get("dictionary_contract", {}).get(
                "jamo_ls_surface_key_restoration"
            )
            is not True
        ):
            raise RuntimeError("common pronunciation manifest hard gate failed")
        inputs = common_release.get("inputs", {})
        if (
            inputs.get("acoustic_model", {}).get("sha256")
            != frozen_pin["models"]["acoustic_model"]["sha256"]
            or inputs.get("g2p_model", {}).get("sha256")
            != frozen_pin["models"]["g2p_model"]["sha256"]
            or inputs.get("base_dictionary", {}).get("sha256")
            != frozen_pin["models"]["dictionary"]["sha256"]
            or common_release.get("outputs", {})
            .get("dictionary", {})
            .get("sha256")
            != models["dictionary"]["sha256"]
        ):
            raise RuntimeError(
                "common pronunciation release does not match frozen MFA pin"
            )
        common_manifest_fingerprint = file_fingerprint(
            common_pron_manifest_path, with_sha256=True
        )
        if (
            common_adoption.get("schema_version")
            != "common_pron_mfa_adoption.v2"
            or common_adoption.get("status") != "passed"
            or not common_adoption.get("gate", {}).get(
                "allow_yearly_mfa"
            )
            or common_adoption.get("common_release", {})
            .get("manifest", {})
            .get("sha256")
            != common_manifest_fingerprint["sha256"]
        ):
            raise RuntimeError(
                "common pronunciation adoption contract hard gate failed"
            )
    elif not allow_legacy_inline_g2p:
        raise RuntimeError(
            "common pronunciation manifest is required; legacy inline G2P "
            "must be explicitly enabled"
        )
    elif (
        models["dictionary"]["sha256"]
        != frozen_pin["models"]["dictionary"]["sha256"]
    ):
        raise RuntimeError(
            "legacy inline G2P base dictionary does not match frozen MFA pin"
        )

    runtime_record = dict(runtime or runtime_versions())
    identity = {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "lab_input_contract_id": lab_input_contract_id,
        "runtime": runtime_record,
        "frozen_model_pin": {
            "commit": frozen_pin["expected"]["commit"],
            "contract_sha256": frozen_pin["contract"]["sha256"],
            "base_dictionary_sha256": frozen_pin["models"]["dictionary"][
                "sha256"
            ],
        },
        "pronunciation_mode": (
            "common_pronunciation"
            if common_release is not None
            else "legacy_inline_g2p_explicit"
        ),
        "common_pron_adoption_sha256": (
            file_fingerprint(
                common_pron_adoption_path, with_sha256=True
            )["sha256"]
            if common_pron_adoption_path is not None
            else None
        ),
        "models": {
            role: {
                "requested_name": record["requested_name"],
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            }
            for role, record in models.items()
        },
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "recorded_at": now_iso(),
        "year": year,
        "lab_input_contract_id": lab_input_contract_id,
        "alignment_contract_id": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "runtime": runtime_record,
        "models": models,
        "frozen_model_pin": {
            "commit": frozen_pin["expected"]["commit"],
            "contract": frozen_pin["contract"],
            "models": frozen_pin["models"],
        },
        "common_pron_manifest": (
            file_fingerprint(
                common_pron_manifest_path, with_sha256=True
            )
            if common_pron_manifest_path is not None
            else None
        ),
        "common_pron_adoption_contract": (
            file_fingerprint(
                common_pron_adoption_path, with_sha256=True
            )
            if common_pron_adoption_path is not None
            else None
        ),
        "pronunciation_mode": identity["pronunciation_mode"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--lab-input-contract-id", required=True)
    parser.add_argument("--acoustic-model-path", type=Path, required=True)
    parser.add_argument("--dictionary-model-path", type=Path, required=True)
    parser.add_argument("--g2p-model-path", type=Path, required=True)
    parser.add_argument("--acoustic-model-name", default="korean_mfa")
    parser.add_argument("--dictionary-model-name", default="korean_mfa")
    parser.add_argument("--g2p-model-name", default="korean_mfa")
    parser.add_argument(
        "--frozen-bundle-contract", type=Path, required=True
    )
    parser.add_argument("--common-pron-manifest", type=Path)
    parser.add_argument(
        "--common-pron-adoption-contract", type=Path
    )
    parser.add_argument(
        "--allow-legacy-inline-g2p", action="store_true"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = build_alignment_contract(
        year=args.year,
        lab_input_contract_id=args.lab_input_contract_id,
        acoustic_model_path=args.acoustic_model_path,
        dictionary_model_path=args.dictionary_model_path,
        g2p_model_path=args.g2p_model_path,
        acoustic_model_name=args.acoustic_model_name,
        dictionary_model_name=args.dictionary_model_name,
        g2p_model_name=args.g2p_model_name,
        frozen_bundle_contract_path=args.frozen_bundle_contract,
        common_pron_manifest_path=args.common_pron_manifest,
        common_pron_adoption_path=args.common_pron_adoption_contract,
        allow_legacy_inline_g2p=args.allow_legacy_inline_g2p,
    )
    atomic_write_json(args.output, contract)
    print(
        "alignment contract: "
        f"{contract['alignment_contract_id'][:12]} -> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

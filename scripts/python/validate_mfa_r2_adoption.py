"""공통발음사전 MFA r2 채택 계약과 실제 모델 파일을 재검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import atomic_write_json, now_iso, sha256_file


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON 읽기 실패: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON 객체가 아님: {path}")
    return data


def _verified_file(record: dict, label: str) -> dict[str, object]:
    path = Path(str(record.get("path") or "")).resolve()
    expected = str(record.get("sha256") or "")
    if not path.is_file() or len(expected) != 64:
        raise RuntimeError(f"{label} 파일/해시 계약 누락: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"{label} SHA256 불일치: expected={expected} actual={actual}"
        )
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": actual,
    }


def validate_adoption(
    manifest_path: Path,
    adoption_path: Path,
) -> dict[str, object]:
    manifest_path = manifest_path.resolve()
    adoption_path = adoption_path.resolve()
    manifest = _load(manifest_path)
    adoption = _load(adoption_path)

    if (
        manifest.get("schema_version") != "common_pron_mfa_lexicon.v2"
        or manifest.get("status") != "success"
    ):
        raise RuntimeError("공통발음사전 r2 release manifest가 success가 아님")
    if (
        adoption.get("schema_version") != "common_pron_mfa_adoption.v3"
        or adoption.get("status") != "passed"
        or adoption.get("policy")
        != "latest_jamo_common_dictionary_required"
    ):
        raise RuntimeError("공통발음사전 adoption v3 계약이 passed가 아님")
    gate = adoption.get("gate") or {}
    if (
        not gate.get("allow_yearly_mfa")
        or gate.get("legacy_inline_g2p_default")
        or int(gate.get("dictionary_missing", -1)) != 0
        or int(gate.get("dictionary_spn_words", -1)) != 0
        or int(gate.get("phone_outside_acoustic_inventory", -1)) != 0
    ):
        raise RuntimeError("adoption v3 연도별 MFA gate가 닫혀 있음")

    manifest_fingerprint = _verified_file(
        adoption["common_release"]["manifest"],
        "release manifest",
    )
    if Path(str(manifest_fingerprint["path"])) != manifest_path:
        raise RuntimeError("adoption이 가리키는 release manifest가 인자와 다름")

    dictionary = _verified_file(
        adoption["common_release"]["dictionary"],
        "common dictionary",
    )
    acoustic = _verified_file(
        adoption["frozen_model_pin"]["models"]["acoustic_model"],
        "frozen acoustic model",
    )
    g2p = _verified_file(
        adoption["frozen_model_pin"]["models"]["g2p_model"],
        "frozen Jamo G2P model",
    )
    frozen_bundle = _verified_file(
        adoption["frozen_model_pin"]["contract"],
        "frozen model bundle contract",
    )
    if dictionary["sha256"] != manifest["outputs"]["dictionary"]["sha256"]:
        raise RuntimeError("manifest/adoption 공통사전 해시 불일치")
    if acoustic["sha256"] != manifest["inputs"]["acoustic_model"]["sha256"]:
        raise RuntimeError("manifest/adoption 음향모델 해시 불일치")
    if g2p["sha256"] != manifest["inputs"]["g2p_model"]["sha256"]:
        raise RuntimeError("manifest/adoption G2P 모델 해시 불일치")

    return {
        "schema_version": "mfa_r2_runtime_adoption_validation.v1",
        "status": "passed",
        "validated_at": now_iso(),
        "pronunciation_mode": "common_pron_mfa_r2_latest_jamo",
        "release_id": manifest["release_id"],
        "release_contract_id": manifest["release_contract_id"],
        "phone_inventory_contract": manifest["phone_inventory_contract"],
        "manifest": manifest_fingerprint,
        "adoption_contract": {
            "path": str(adoption_path),
            "bytes": adoption_path.stat().st_size,
            "sha256": sha256_file(adoption_path),
        },
        "dictionary": dictionary,
        "acoustic_model": acoustic,
        "g2p_model_reference_only": g2p,
        "frozen_model_bundle_contract": frozen_bundle,
        "inline_g2p_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--adoption-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_adoption(args.manifest, args.adoption_contract)
    atomic_write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

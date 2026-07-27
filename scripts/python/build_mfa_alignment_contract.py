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
    runtime: dict[str, str] | None = None,
) -> dict:
    if not year.strip():
        raise ValueError("year가 비어 있음")
    if not lab_input_contract_id.strip():
        raise ValueError("lab_input_contract_id가 비어 있음")

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
    runtime_record = dict(runtime or runtime_versions())
    identity = {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "lab_input_contract_id": lab_input_contract_id,
        "runtime": runtime_record,
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

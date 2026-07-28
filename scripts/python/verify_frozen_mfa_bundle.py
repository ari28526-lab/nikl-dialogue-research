"""Verify the exact frozen Korean MFA model bundle used by this project.

The committed bundle JSON is evidence, but it is not sufficient to merely
record whatever happens to be installed.  This module pins the official
repository commit and the three production artifacts used by the pipeline,
then hashes the actual files before any G2P or alignment run may start.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "frozen_korean_mfa_model_pin.v1"
EXPECTED_PIN = {
    "repository": "MontrealCorpusTools/korean_mfa",
    "commit": "0091ffa1f1ef7df380a4f799b3fb5bc80c3f65cd",
    "acoustic_version": "3.3.0",
    "g2p_version": "3.2.0",
    "unicode_decomposition": True,
    "phone_count": 107,
    "phone_sorted_sha256": (
        "6fbbb2cf1853573e0c387b286ddabfe6073ad64e42282317f73fdef95418940d"
    ),
    "outputs": {
        "acoustic_model": (
            "94bd6cc56d7b019294ba3966620be01ba24a73863bc2c7cc11301ba3cabb159c"
        ),
        "g2p_model": (
            "4df7c5fa90da1f401e7a44af360be56158a581a54202e38baedeca53cfed38ff"
        ),
        "dictionary": (
            "49e223fddb518bc441baa4cb9fec1a108e80dae9a2b54e5834dbff30e89c7d34"
        ),
    },
}


def _require_equal(label: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise RuntimeError(
            f"frozen MFA pin mismatch: {label}={actual!r}, "
            f"expected={expected!r}"
        )


def verify_frozen_bundle(
    *,
    contract_path: Path,
    model_paths: Mapping[str, Path] | None = None,
    expected_pin: Mapping[str, object] = EXPECTED_PIN,
) -> dict:
    contract_path = contract_path.resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    _require_equal(
        "schema_version",
        contract.get("schema_version"),
        "hf_korean_mfa_frozen_bundle.v1",
    )
    _require_equal("status", contract.get("status"), "success")

    source = contract.get("source", {})
    _require_equal(
        "source.repository",
        source.get("repository"),
        expected_pin["repository"],
    )
    _require_equal(
        "source.commit",
        source.get("commit"),
        expected_pin["commit"],
    )

    method = contract.get("contract", {})
    for key in (
        "acoustic_version",
        "g2p_version",
        "unicode_decomposition",
        "phone_count",
        "phone_sorted_sha256",
    ):
        _require_equal(
            f"contract.{key}",
            method.get(key),
            expected_pin[key],
        )
    _require_equal(
        "contract.acoustic_g2p_phone_inventory_equal",
        method.get("acoustic_g2p_phone_inventory_equal"),
        True,
    )
    _require_equal(
        "contract.symbol_files_cr_count",
        method.get("symbol_files_cr_count"),
        0,
    )
    _require_equal(
        "contract.dictionary.unsupported_phone_count",
        method.get("dictionary", {}).get("unsupported_phone_count"),
        0,
    )

    output_contract = contract.get("outputs", {})
    actual_models: dict[str, dict] = {}
    expected_outputs = expected_pin["outputs"]
    assert isinstance(expected_outputs, Mapping)
    for role in ("acoustic_model", "g2p_model", "dictionary"):
        record = output_contract.get(role, {})
        expected_sha = str(expected_outputs[role])
        _require_equal(
            f"outputs.{role}.sha256",
            str(record.get("sha256", "")).lower(),
            expected_sha,
        )
        path = (
            Path(model_paths[role])
            if model_paths and role in model_paths
            else Path(str(record.get("path", "")))
        )
        if not path.is_file():
            raise RuntimeError(f"frozen MFA file missing: {role}={path}")
        fingerprint = file_fingerprint(path, with_sha256=True)
        _require_equal(
            f"actual.{role}.sha256",
            fingerprint["sha256"],
            expected_sha,
        )
        if not model_paths or role not in model_paths:
            _require_equal(
                f"actual.{role}.bytes",
                fingerprint["bytes"],
                int(record.get("bytes", -1)),
            )
        actual_models[role] = fingerprint

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "recorded_at": now_iso(),
        "expected": {
            "repository": expected_pin["repository"],
            "commit": expected_pin["commit"],
            "acoustic_version": expected_pin["acoustic_version"],
            "g2p_version": expected_pin["g2p_version"],
            "unicode_decomposition": expected_pin[
                "unicode_decomposition"
            ],
            "phone_count": expected_pin["phone_count"],
            "phone_sorted_sha256": expected_pin[
                "phone_sorted_sha256"
            ],
        },
        "contract": file_fingerprint(
            contract_path, with_sha256=True
        ),
        "models": actual_models,
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path)
    parser.add_argument("--g2p-model", type=Path)
    parser.add_argument("--base-dictionary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    overrides = {
        role: path.resolve()
        for role, path in {
            "acoustic_model": args.acoustic_model,
            "g2p_model": args.g2p_model,
            "dictionary": args.base_dictionary,
        }.items()
        if path is not None
    }
    report = verify_frozen_bundle(
        contract_path=args.contract,
        model_paths=overrides or None,
    )
    atomic_write_json(args.output, report)
    print(
        "[OK] frozen Korean MFA pin: "
        f"{report['expected']['commit'][:12]} -> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

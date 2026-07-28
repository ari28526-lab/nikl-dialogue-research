"""Prove that 2020–2025 MFA used one pronunciation/model standard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_cross_year_method_consistency.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")


def _load_contract(path: Path, year: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        payload.get("schema_version") != "mfa_alignment_contract.v1"
        or payload.get("status") != "passed"
        or str(payload.get("year")) != year
        or payload.get("pronunciation_mode") != "common_pronunciation"
    ):
        raise RuntimeError(f"{year} alignment contract gate failed: {path}")
    return payload


def _method_key(contract: dict) -> dict:
    return {
        "runtime": contract.get("runtime"),
        "models": {
            role: {
                "bytes": contract["models"][role]["bytes"],
                "sha256": contract["models"][role]["sha256"],
            }
            for role in ("acoustic", "dictionary", "g2p")
        },
        "frozen_commit": contract["frozen_model_pin"]["commit"],
        "frozen_contract_sha256": contract[
            "frozen_model_pin"
        ]["contract"]["sha256"],
        "common_pron_manifest_sha256": contract[
            "common_pron_manifest"
        ]["sha256"],
        "common_pron_adoption_sha256": contract[
            "common_pron_adoption_contract"
        ]["sha256"],
    }


def audit_cross_year_contracts(
    *,
    contracts_directory: Path,
) -> dict:
    contracts_directory = contracts_directory.resolve()
    contracts: dict[str, dict] = {}
    records: dict[str, dict] = {}
    for year in YEARS:
        path = contracts_directory / f"{year}.json"
        if not path.is_file():
            raise RuntimeError(f"연도별 alignment contract 누락: {path}")
        contracts[year] = _load_contract(path, year)
        records[year] = file_fingerprint(path, with_sha256=True)

    reference = _method_key(contracts[YEARS[0]])
    mismatches = {
        year: _method_key(contracts[year])
        for year in YEARS[1:]
        if _method_key(contracts[year]) != reference
    }
    if mismatches:
        raise RuntimeError(
            "연도 간 MFA 방법 계약 불일치: "
            + ", ".join(sorted(mismatches))
        )

    # 계약에 기록된 실물도 감사 시점에 다시 hash한다. 경로가 바뀐
    # 재현 환경에서는 새 계약을 만들고 이 감사를 다시 수행해야 한다.
    verified_model_files: dict[str, dict] = {}
    for role in ("acoustic", "dictionary", "g2p"):
        expected = contracts[YEARS[0]]["models"][role]
        actual = file_fingerprint(
            Path(expected["path"]), with_sha256=True
        )
        if (
            actual["sha256"] != expected["sha256"]
            or actual["bytes"] != expected["bytes"]
        ):
            raise RuntimeError(f"공통 {role} 실물 fingerprint 불일치")
        verified_model_files[role] = actual

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "recorded_at": now_iso(),
        "years": list(YEARS),
        "methodological_claim": (
            "2020-2025 use the same frozen acoustic model, final common "
            "dictionary, Jamo G2P model, MFA/Pynini/Python runtime, common "
            "dictionary manifest, and adoption contract; year and lab "
            "input contract are intentionally year-specific."
        ),
        "common_method_contract": reference,
        "alignment_contracts": records,
        "verified_model_files": verified_model_files,
        "gate": {
            "years_expected": len(YEARS),
            "years_observed": len(contracts),
            "cross_year_method_mismatches": 0,
            "same_phone_generation_standard": True,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contracts-directory", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_cross_year_contracts(
        contracts_directory=args.contracts_directory
    )
    atomic_write_json(args.output, report)
    print(
        "[OK] 2020-2025 MFA method consistency: "
        f"{report['gate']['years_observed']} years -> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

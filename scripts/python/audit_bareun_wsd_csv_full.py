#!/usr/bin/env python3
"""Independently audit completed full Bareun morphology or WSD CSV outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SCRIPTS = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PYTHON_SCRIPTS))

from preflight_bareun_wsd_environment import expand_config_path, load_config  # noqa: E402
from run_bareun_wsd_pilot import sha256_file  # noqa: E402


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_wsd_reanalysis_v1.json"
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "outputs"
    / "reports"
    / "AUDIT_bareun_wsd_csv_full_20260828.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    config = load_config(args.config)
    with_sense = bool(config["api"].get("with_sense", True))
    analysis_mode = "wsd" if with_sense else "morph"
    input_root = expand_config_path(str(config["input"]["root"]))
    output_root = expand_config_path(str(config["output"]["root"]))
    final_root = output_root / "bulk_csv_v1"
    errors: list[str] = []
    manifest_path = final_root / "FINAL_MANIFEST.json"
    inventory_path = final_root / "RECEIPT_INVENTORY.tsv"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    if not inventory_path.is_file():
        raise FileNotFoundError(inventory_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_file(inventory_path) != manifest["receipt_inventory_sha256"]:
        errors.append("receipt_inventory_sha_mismatch")

    inventory_rows = [
        line.split("\t", 1)
        for line in inventory_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(inventory_rows) != config["input"]["expected_csv_files"]:
        errors.append("receipt_inventory_count_mismatch")
    totals = {
        "utterances": 0,
        "input_eojeol": 0,
        "tokens": 0,
        "morphemes": 0,
        "morphemes_with_sense": 0,
    }
    output_bytes = 0
    for relative, expected_receipt_sha in inventory_rows:
        receipt_path = final_root / relative
        if not receipt_path.is_file():
            errors.append(f"receipt_missing:{relative}")
            continue
        if sha256_file(receipt_path) != expected_receipt_sha:
            errors.append(f"receipt_sha_mismatch:{relative}")
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        source_path = input_root / receipt["source_file"]
        if not source_path.is_file():
            errors.append(f"source_missing:{receipt['source_file']}")
        elif sha256_file(source_path) != receipt["source_sha256"]:
            errors.append(f"protected_source_changed:{receipt['source_file']}")
        for key in totals:
            totals[key] += int(receipt["counts"][key])
        for name, contract in receipt["outputs"].items():
            path = receipt_path.parent / name
            if not path.is_file():
                errors.append(f"output_missing:{path.relative_to(final_root).as_posix()}")
                continue
            if path.stat().st_size != int(contract["bytes"]):
                errors.append(f"output_size_mismatch:{path.relative_to(final_root).as_posix()}")
            elif sha256_file(path) != contract["sha256"]:
                errors.append(f"output_sha_mismatch:{path.relative_to(final_root).as_posix()}")
            output_bytes += path.stat().st_size

    if totals["utterances"] != config["input"]["expected_rows"]:
        errors.append("utterance_count_mismatch")
    if totals["input_eojeol"] != config["input"]["expected_input_eojeol"]:
        errors.append("input_eojeol_count_mismatch")
    if totals != manifest["counts"]:
        errors.append("manifest_count_mismatch")
    if output_bytes != manifest["total_compressed_csv_bytes"]:
        errors.append("manifest_output_bytes_mismatch")
    if not manifest.get("fresh_morphology_analysis"):
        errors.append("fresh_morphology_contract_missing")
    if bool(manifest.get("with_sense")) != with_sense:
        errors.append("analysis_mode_contract_mismatch")
    if not with_sense and totals["morphemes_with_sense"] != 0:
        errors.append("unexpected_sense_count_in_morphology_only_run")
    if manifest.get("textgrid_or_wav_accessed"):
        errors.append("unexpected_textgrid_or_wav_access")

    report: dict[str, Any] = {
        "schema": f"bareun_{analysis_mode}_csv_full_audit.v1",
        "passed": not errors,
        "analysis_mode": analysis_mode,
        "with_sense": with_sense,
        "final_root": str(final_root),
        "server_contract": manifest["server_contract"],
        "source_csv_files": len(inventory_rows),
        "counts": totals,
        "total_compressed_csv_bytes": output_bytes,
        "protected_source_csv_unchanged": not any(
            error.startswith("protected_source_changed") for error in errors
        ),
        "textgrid_or_wav_accessed": False,
        "errors": errors,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

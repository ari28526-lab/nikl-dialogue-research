#!/usr/bin/env python3
"""Read-only preflight for the Bareun homonym-sense reanalysis environment.

This command never performs a bulk API call and never prints or stores the API
key. A live check, when explicitly requested, sends exactly one short sentence.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_wsd_reanalysis_v1.json"
DEFAULT_REPORT = (
    PROJECT_ROOT
    / "work"
    / "bareun_wsd_full_20260828"
    / "PREFLIGHT.json"
)
GIB = 1024**3


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_config_path(value: str) -> Path:
    return Path(os.path.expandvars(value.replace("/", os.sep)))


def load_api_key(secret_config: dict[str, Any]) -> tuple[str | None, str]:
    """Load a key without exposing it; return only key and source label."""
    variable = str(secret_config.get("environment_variable", "BAREUN_API_KEY"))
    environment_value = os.environ.get(variable, "").strip()
    if environment_value:
        return environment_value, f"environment:{variable}"

    for candidate in secret_config.get("candidate_files", []):
        path = expand_config_path(str(candidate))
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig").strip()
        if not text:
            continue
        if "=" in text:
            values: dict[str, str] = {}
            for line in text.splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or "=" not in clean:
                    continue
                name, value = clean.split("=", 1)
                values[name.strip()] = value.strip().strip('"').strip("'")
            text = values.get(variable, "").strip()
        if text:
            return text, f"file:{path.name}"
    return None, "not_found"


def installed_client() -> dict[str, Any]:
    result: dict[str, Any] = {
        "package": "bareunpy",
        "installed": False,
        "version": None,
        "direct_url_commit": None,
    }
    try:
        distribution = importlib.metadata.distribution("bareunpy")
    except importlib.metadata.PackageNotFoundError:
        return result

    result["installed"] = True
    result["version"] = distribution.version
    for item in distribution.files or []:
        if str(item).replace("\\", "/").endswith("direct_url.json"):
            direct_path = Path(distribution.locate_file(item))
            try:
                direct = json.loads(direct_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                break
            result["direct_url_commit"] = (
                direct.get("vcs_info", {}).get("commit_id")
            )
            break
    return result


def inventory_csv(root: Path, full_scan: bool) -> dict[str, Any]:
    files = sorted(
        path
        for path in root.rglob("*.csv")
        if path.is_file() and not path.name.startswith("_")
    )
    result: dict[str, Any] = {
        "root_exists": root.is_dir(),
        "csv_files": len(files),
        "full_scan": full_scan,
        "rows": None,
        "input_eojeol": None,
        "missing_required_columns_files": 0,
    }
    if not full_scan:
        return result

    rows = 0
    eojeol = 0
    missing_headers = 0
    for path in files:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            if not {"utt_id", "speaker_id", "form"}.issubset(headers):
                missing_headers += 1
                continue
            for row in reader:
                rows += 1
                eojeol += len((row.get("form") or "").split())
    result.update(
        {
            "rows": rows,
            "input_eojeol": eojeol,
            "missing_required_columns_files": missing_headers,
        }
    )
    return result


def storage_status(output_root: Path) -> dict[str, Any]:
    anchor = Path(output_root.anchor or output_root)
    usage = shutil.disk_usage(anchor)
    return {
        "volume": str(anchor),
        "free_gib": round(usage.free / GIB, 3),
        "total_gib": round(usage.total / GIB, 3),
    }


def live_smoke(config: dict[str, Any], api_key: str) -> dict[str, Any]:
    from bareunpy import Tagger

    endpoint = config["endpoint"]
    options = config["api"]
    tagger = Tagger(
        api_key,
        host=str(endpoint["host"]),
        port=int(endpoint["port"]),
    )
    sentence = "다리를 건넜다."
    tagged = tagger.tag(
        sentence,
        auto_split=bool(options["auto_split"]),
        auto_spacing=bool(options["auto_spacing"]),
        auto_jointing=bool(options["auto_jointing"]),
        with_sense=bool(options["with_sense"]),
    )
    message = tagged.msg()
    preview: list[dict[str, Any]] = []
    sense_count = 0
    for sentence_item in message.sentences:
        for token in sentence_item.tokens:
            for morph in token.morphemes:
                has_sense = morph.HasField("sense")
                if has_sense:
                    sense_count += 1
                preview.append(
                    {
                        "text": morph.text.content,
                        "tag": morph.tag,
                        "sense_no": morph.sense.sense_no if has_sense else None,
                        "probability": morph.sense.probability if has_sense else None,
                    }
                )
    return {
        "performed": True,
        "sentences_sent": 1,
        "with_sense": True,
        "morphemes": len(preview),
        "morphemes_with_sense": sense_count,
        "preview_without_meanings": preview,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    expected_client = config["client"]
    expected_input = config["input"]
    storage_rules = config["storage"]
    input_root = expand_config_path(str(expected_input["root"]))
    output_root = expand_config_path(str(config["output"]["root"]))

    client = installed_client()
    inventory = inventory_csv(input_root, args.full_input_scan)
    storage = storage_status(output_root)
    api_key, key_source = load_api_key(config["secret"])
    errors: list[str] = []
    warnings: list[str] = []

    if not client["installed"]:
        errors.append("bareunpy_not_installed")
    if client["version"] != expected_client["version"]:
        errors.append("bareunpy_version_mismatch")
    if client["direct_url_commit"] != expected_client["git_commit"]:
        errors.append("bareunpy_commit_mismatch")
    if not inventory["root_exists"]:
        errors.append("input_root_missing")
    if inventory["csv_files"] != expected_input["expected_csv_files"]:
        errors.append("input_csv_file_count_mismatch")
    if args.full_input_scan:
        if inventory["rows"] != expected_input["expected_rows"]:
            errors.append("input_row_count_mismatch")
        if inventory["input_eojeol"] != expected_input["expected_input_eojeol"]:
            errors.append("input_eojeol_count_mismatch")
        if inventory["missing_required_columns_files"]:
            errors.append("input_required_columns_missing")
    if storage["free_gib"] < float(storage_rules["minimum_environment_free_gib"]):
        errors.append("insufficient_environment_storage")
    if storage["free_gib"] < float(storage_rules["minimum_bulk_free_gib"]):
        warnings.append("bulk_storage_gate_not_met")
    if not api_key:
        errors.append("api_key_not_found")

    smoke: dict[str, Any] = {"performed": False, "sentences_sent": 0}
    if args.live_api and api_key:
        try:
            smoke = live_smoke(config, api_key)
        except Exception as exc:  # API failures must be explicit but key-safe.
            errors.append(f"live_smoke_failed:{type(exc).__name__}")

    environment_ready = not errors
    bulk_ready = all(
        [
            environment_ready,
            args.full_input_scan,
            bool(smoke.get("performed")),
            storage["free_gib"] >= float(storage_rules["minimum_bulk_free_gib"]),
            config["approval"]["bulk_status"] == "approved",
        ]
    )
    return {
        "schema": "bareun_wsd_environment_preflight.v1",
        "run_id": config["run_id"],
        "bulk_call_performed": False,
        "client": client,
        "input": inventory,
        "storage": storage,
        "secret": {"available": bool(api_key), "source": key_source},
        "live_smoke": smoke,
        "environment_ready": environment_ready,
        "bulk_ready": bulk_ready,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--full-input-scan", action="store_true")
    parser.add_argument("--live-api", action="store_true")
    parser.add_argument("--require-bulk-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    success = report["environment_ready"] and (
        not args.require_bulk_ready or report["bulk_ready"]
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

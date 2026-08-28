#!/usr/bin/env python3
"""Checkpointed full Bareun v3.1.0+ morphology and WSD CSV reanalysis.

The cloud server performs a fresh morphology analysis for every utterance and
returns WSD fields in the same response. The old CSV morphology is never reused
as analysis input; only utt_id, speaker_id, and form are read. Bulk execution is
single-worker because four concurrent WSD batches failed the production pilot.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Iterable
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SCRIPTS = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PYTHON_SCRIPTS))

from preflight_bareun_wsd_environment import (  # noqa: E402
    expand_config_path,
    installed_client,
    load_api_key,
    load_config,
)
from run_bareun_wsd_pilot import (  # noqa: E402
    MORPH_FIELDS,
    SENSE_FIELDS,
    UTTERANCE_FIELDS,
    analyze_batch,
    parse_analysis,
    sha256_file,
    year_from_name,
)


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_wsd_reanalysis_v1.json"
PILOT_AUDIT = (
    PROJECT_ROOT
    / "outputs"
    / "reports"
    / "AUDIT_bareun_wsd_pilot_p1_20260828.json"
)
APPROVAL_TOKEN = "BAREUN_WSD_CSV_FULL_20260828"
GIB = 1024**3
SENSE_ONLY_MORPH_FIELDS = {"sense_no", "sense_probability", "urimal_target_id"}


def analysis_mode(config: dict[str, Any]) -> str:
    return "wsd" if bool(config["api"].get("with_sense", True)) else "morph"


def schema_name(config: dict[str, Any], suffix: str) -> str:
    return f"bareun_{analysis_mode(config)}_csv_full_{suffix}.v1"


def bulk_roots(config: dict[str, Any]) -> tuple[Path, Path, Path]:
    output_root = expand_config_path(str(config["output"]["root"]))
    building_name = str(
        config["output"].get("bulk_building_subdirectory", "bulk_csv_v1.building")
    )
    final_name = str(config["output"].get("bulk_final_subdirectory", "bulk_csv_v1"))
    return output_root, output_root / building_name, output_root / final_name


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def gzip_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, mtime=0
        ) as compressed:
            text_output = io.TextIOWrapper(
                compressed, encoding="utf-8", newline="", write_through=True
            )
            try:
                writer = csv.DictWriter(
                    text_output, fieldnames=fields, lineterminator="\n"
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow({field: row.get(field, "") for field in fields})
                text_output.flush()
            finally:
                text_output.detach()
        raw_output.flush()
        os.fsync(raw_output.fileno())
    os.replace(partial, path)


def read_input_rows(path: Path, input_root: Path) -> list[dict[str, Any]]:
    relative = path.relative_to(input_root).as_posix()
    year = year_from_name(relative.split("/", 1)[0])
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"utt_id", "speaker_id", "form"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"missing required columns: {relative}")
        for row_index, row in enumerate(reader, start=1):
            form = (row.get("form") or "").strip()
            if not form:
                raise RuntimeError(f"empty form: {relative}:{row_index}")
            rows.append(
                {
                    "year": year,
                    "source_file": relative,
                    "source_row_index": row_index,
                    "utt_id": row.get("utt_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "form": form,
                }
            )
    if not rows:
        raise RuntimeError(f"source CSV has no rows: {relative}")
    if len({row["utt_id"] for row in rows}) != len(rows):
        raise RuntimeError(f"duplicate utt_id within source CSV: {relative}")
    return rows


def source_output_dir(run_root: Path, source: Path, input_root: Path) -> Path:
    relative = source.relative_to(input_root)
    return run_root / "files" / relative.parent / relative.stem


def ensure_output_contract(
    project_root: Path,
    output_root: Path,
    protected_roots: list[str],
) -> None:
    resolved = output_root.resolve()
    if resolved.drive.lower() == project_root.resolve().drive.lower():
        raise RuntimeError("bulk CSV output must be on the external drive")
    for protected in protected_roots:
        protected_path = expand_config_path(protected).resolve()
        if resolved == protected_path or protected_path in resolved.parents:
            raise RuntimeError(f"output overlaps protected root: {protected_path}")


def pilot_gate() -> dict[str, Any]:
    if not PILOT_AUDIT.is_file():
        raise RuntimeError(f"pilot audit missing: {PILOT_AUDIT}")
    audit = json.loads(PILOT_AUDIT.read_text(encoding="utf-8"))
    if not audit.get("passed"):
        raise RuntimeError("pilot audit did not pass")
    if audit.get("counts", {}).get("utterances") != 240:
        raise RuntimeError("pilot audit utterance count mismatch")
    if not audit.get("protected_csv_unchanged"):
        raise RuntimeError("pilot did not preserve source CSV")
    return audit


def list_sources(input_root: Path) -> list[Path]:
    return sorted(
        path
        for path in input_root.rglob("*.csv")
        if path.is_file() and not path.name.startswith("_")
    )


def read_receipt(final_dir: Path, source: Path) -> dict[str, Any]:
    receipt_path = final_dir / "RECEIPT.json"
    if not receipt_path.is_file():
        raise RuntimeError(f"final file directory lacks receipt: {final_dir}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("source_sha256") != sha256_file(source):
        raise RuntimeError(f"completed source SHA changed: {source}")
    for name, contract in receipt.get("outputs", {}).items():
        path = final_dir / name
        if not path.is_file():
            raise RuntimeError(f"completed output missing: {path}")
        if path.stat().st_size != contract["bytes"]:
            raise RuntimeError(f"completed output size changed: {path}")
        if sha256_file(path) != contract["sha256"]:
            raise RuntimeError(f"completed output SHA changed: {path}")
    return receipt


def archive_interrupted(building_dir: Path, run_root: Path, input_root: Path) -> None:
    if not building_dir.exists():
        return
    relative = building_dir.relative_to(run_root / "files")
    archive = (
        run_root
        / "interrupted"
        / relative.parent
        / f"{relative.name}.{datetime.now():%Y%m%dT%H%M%S}.{uuid.uuid4().hex[:8]}"
    )
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        raise RuntimeError(f"interrupted archive collision: {archive}")
    os.replace(building_dir, archive)


def acquire_lock(path: Path, resume: bool) -> None:
    if path.exists():
        if not resume:
            raise RuntimeError("bulk lock exists; inspect status and use --resume")
        old = json.loads(path.read_text(encoding="utf-8"))
        old_pid = int(old.get("pid", -1))
        alive = False
        if old_pid > 0:
            try:
                os.kill(old_pid, 0)
                alive = True
            except OSError:
                alive = False
        if alive:
            raise RuntimeError(f"bulk process is still alive: pid={old_pid}")
        stale = path.with_name(
            f"RUN.lock.stale.{datetime.now():%Y%m%dT%H%M%S}.{uuid.uuid4().hex[:8]}.json"
        )
        os.replace(path, stale)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        payload = json.dumps(
            {"pid": os.getpid(), "started_at": utc_now()}, ensure_ascii=True
        ).encode("utf-8")
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def process_source(
    tagger: Any,
    source: Path,
    input_root: Path,
    run_root: Path,
    batch_size: int,
    max_retries: int,
    with_sense: bool = True,
    auto_spacing: bool = True,
    auto_jointing: bool = True,
) -> dict[str, Any]:
    final_dir = source_output_dir(run_root, source, input_root)
    if final_dir.exists():
        return read_receipt(final_dir, source)
    building_dir = final_dir.with_name(final_dir.name + ".building")
    archive_interrupted(building_dir, run_root, input_root)
    building_dir.mkdir(parents=True, exist_ok=False)
    source_sha_before = sha256_file(source)
    samples = read_input_rows(source, input_root)
    utterance_rows: list[dict[str, Any]] = []
    morph_rows: list[dict[str, Any]] = []
    sense_by_key: dict[str, dict[str, Any]] = {}
    api_stats = {
        "batches": 0,
        "batch_retries": 0,
        "single_fallbacks": 0,
        "single_retries": 0,
        "api_calls": 0,
    }
    started = time.time()
    try:
        for start in range(0, len(samples), batch_size):
            part = samples[start : start + batch_size]
            sentences, stats = analyze_batch(
                tagger,
                [sample["form"] for sample in part],
                max_retries=max_retries,
                with_sense=with_sense,
                auto_spacing=auto_spacing,
                auto_jointing=auto_jointing,
            )
            api_stats["batches"] += 1
            for key in ["batch_retries", "single_fallbacks", "single_retries", "api_calls"]:
                api_stats[key] += stats[key]
            for sample, sentence in zip(part, sentences, strict=True):
                utterance, morphs, senses = parse_analysis(sample, sentence)
                utterance_rows.append(utterance)
                morph_rows.extend(morphs)
                for sense in senses:
                    existing = sense_by_key.get(sense["sense_key"])
                    if existing is not None and existing != sense:
                        raise RuntimeError("sense key collision")
                    sense_by_key[sense["sense_key"]] = sense
        if len(utterance_rows) != len(samples):
            raise RuntimeError("source zero-drop check failed")
        source_sha_after = sha256_file(source)
        if source_sha_after != source_sha_before:
            raise RuntimeError("protected source CSV changed during analysis")

        utterance_fields = (
            UTTERANCE_FIELDS
            if with_sense
            else [field for field in UTTERANCE_FIELDS if field != "response_sense_count"]
        )
        morph_fields = (
            MORPH_FIELDS
            if with_sense
            else [field for field in MORPH_FIELDS if field not in SENSE_ONLY_MORPH_FIELDS]
        )
        output_rows = {
            "utterances.csv.gz": (utterance_fields, utterance_rows),
            "morphemes.csv.gz": (morph_fields, morph_rows),
        }
        if with_sense:
            output_rows["sense_dictionary.csv.gz"] = (
                SENSE_FIELDS,
                sorted(sense_by_key.values(), key=lambda row: row["sense_key"]),
            )
        outputs: dict[str, Any] = {}
        for name, (fields, rows) in output_rows.items():
            path = building_dir / name
            gzip_csv(path, fields, rows)
            outputs[name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        receipt = {
            "schema": (
                "bareun_wsd_csv_file_receipt.v1"
                if with_sense
                else "bareun_morph_csv_file_receipt.v1"
            ),
            "status": "completed",
            "with_sense": with_sense,
            "completed_at": utc_now(),
            "source_file": source.relative_to(input_root).as_posix(),
            "source_sha256": source_sha_before,
            "counts": {
                "utterances": len(utterance_rows),
                "input_eojeol": sum(row["input_eojeol"] for row in utterance_rows),
                "tokens": sum(row["response_token_count"] for row in utterance_rows),
                "morphemes": len(morph_rows),
                "morphemes_with_sense": sum(
                    row["response_sense_count"] for row in utterance_rows
                ),
                "unique_senses_in_file": len(sense_by_key),
            },
            "api": api_stats,
            "elapsed_seconds": round(time.time() - started, 3),
            "outputs": outputs,
            "protected_source_unchanged": True,
            "textgrid_or_wav_accessed": False,
        }
        atomic_json(building_dir / "RECEIPT.json", receipt)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        os.replace(building_dir, final_dir)
        return receipt
    except Exception as exc:
        atomic_json(
            building_dir / "FAILURE.json",
            {
                "schema": (
                    "bareun_wsd_csv_file_failure.v1"
                    if with_sense
                    else "bareun_morph_csv_file_failure.v1"
                ),
                "failed_at": utc_now(),
                "with_sense": with_sense,
                "source_file": source.relative_to(input_root).as_posix(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "api": api_stats,
            },
        )
        raise


def sum_counts(total: dict[str, int], receipt: dict[str, Any]) -> None:
    for key in [
        "utterances",
        "input_eojeol",
        "tokens",
        "morphemes",
        "morphemes_with_sense",
    ]:
        total[key] += int(receipt["counts"][key])


def preflight(config: dict[str, Any], resume: bool) -> dict[str, Any]:
    input_root = expand_config_path(str(config["input"]["root"]))
    output_root, run_root, final_root = bulk_roots(config)
    with_sense = bool(config["api"].get("with_sense", True))
    ensure_output_contract(PROJECT_ROOT, output_root, config["protected_roots"])
    sources = list_sources(input_root)
    client = installed_client()
    key, key_source = load_api_key(config["secret"])
    pilot = pilot_gate()
    free_gib = shutil.disk_usage(output_root.anchor).free / GIB
    errors: list[str] = []
    if len(sources) != config["input"]["expected_csv_files"]:
        errors.append("source_file_count_mismatch")
    if client["version"] != config["client"]["version"]:
        errors.append("client_version_mismatch")
    if client["direct_url_commit"] != config["client"]["git_commit"]:
        errors.append("client_commit_mismatch")
    if not key:
        errors.append("api_key_not_found")
    if free_gib < float(config["storage"]["minimum_bulk_csv_free_gib"]):
        errors.append("insufficient_csv_bulk_storage")
    if final_root.exists():
        errors.append("final_bulk_root_already_exists")
    if run_root.exists() and not resume:
        errors.append("building_root_exists_resume_required")
    return {
        "schema": schema_name(config, "preflight"),
        "ready": not errors,
        "api_call_performed": False,
        "server_contract": "api.bareun.ai Bareun server v3.1.0 or newer",
        "fresh_morphology_analysis": True,
        "with_sense": with_sense,
        "client": client,
        "source_csv_files": len(sources),
        "pilot_passed": pilot["passed"],
        "pilot_estimated_full_compressed_gib": pilot["estimated_full_compressed_gib"],
        "free_gib": round(free_gib, 3),
        "minimum_free_gib": config["storage"]["minimum_bulk_csv_free_gib"],
        "key_available": bool(key),
        "key_source": key_source,
        "run_root": str(run_root),
        "final_root": str(final_root),
        "resume": resume,
        "workers": 1,
        "batch_size": config["api"]["batch_size"],
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    report = preflight(config, args.resume)
    report["batch_size"] = args.batch_size
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    if not args.execute:
        return 0 if report["ready"] else 1
    if not report["ready"]:
        return 1
    expected_token = str(config.get("approval", {}).get("execution_token", APPROVAL_TOKEN))
    if args.approval_token != expected_token:
        raise RuntimeError("exact bulk approval token required")
    if not args.approved_by.strip():
        raise RuntimeError("--approved-by is required")
    frozen_batch_size = int(config["api"]["batch_size"])
    if args.batch_size != frozen_batch_size:
        raise RuntimeError(f"production batch size is frozen at {frozen_batch_size}")

    input_root = expand_config_path(str(config["input"]["root"]))
    output_root, run_root, final_root = bulk_roots(config)
    with_sense = bool(config["api"].get("with_sense", True))
    if not run_root.exists():
        run_root.mkdir(parents=True, exist_ok=False)
        atomic_json(
            run_root / "RUN_CONTRACT.json",
            {
                "schema": schema_name(config, "run_contract"),
                "run_id": config["run_id"],
                "created_at": utc_now(),
                "approved_by": args.approved_by.strip(),
                "server_contract": report["server_contract"],
                "fresh_morphology_analysis": True,
                "with_sense": with_sense,
                "client": report["client"],
                "workers": 1,
                "batch_size": frozen_batch_size,
                "source_csv_files": report["source_csv_files"],
                "expected_rows": config["input"]["expected_rows"],
                "expected_input_eojeol": config["input"]["expected_input_eojeol"],
                "protected_roots": config["protected_roots"],
                "textgrid_or_wav_accessed": False,
            },
        )
    lock_path = run_root / "RUN.lock.json"
    acquire_lock(lock_path, args.resume)
    from bareunpy import Tagger

    api_key, _ = load_api_key(config["secret"])
    assert api_key
    tagger = Tagger(
        api_key,
        host=str(config["endpoint"]["host"]),
        port=int(config["endpoint"]["port"]),
    )
    sources = list_sources(input_root)
    totals = {
        "utterances": 0,
        "input_eojeol": 0,
        "tokens": 0,
        "morphemes": 0,
        "morphemes_with_sense": 0,
    }
    session_started = time.time()
    session_processed = 0
    completed_files = 0
    try:
        for file_index, source in enumerate(sources, start=1):
            final_dir = source_output_dir(run_root, source, input_root)
            existed = final_dir.exists()
            receipt = process_source(
                tagger,
                source,
                input_root,
                run_root,
                args.batch_size,
                args.max_retries,
                with_sense=with_sense,
                auto_spacing=bool(config["api"].get("auto_spacing", True)),
                auto_jointing=bool(config["api"].get("auto_jointing", True)),
            )
            completed_files += 1
            sum_counts(totals, receipt)
            if not existed:
                session_processed += receipt["counts"]["utterances"]
            elapsed = max(time.time() - session_started, 0.001)
            session_rate = session_processed / elapsed
            remaining_rows = max(
                config["input"]["expected_rows"] - totals["utterances"], 0
            )
            eta_seconds = remaining_rows / session_rate if session_rate > 0 else None
            event = {
                "recorded_at": utc_now(),
                "file_index": file_index,
                "source_file": source.relative_to(input_root).as_posix(),
                "status": "skipped_verified" if existed else "completed",
                "completed_files": completed_files,
                "total_files": len(sources),
                "counts": totals.copy(),
                "session_utterances": session_processed,
                "session_rate_utterances_per_second": round(session_rate, 3),
                "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
            }
            append_jsonl(run_root / "PROGRESS.jsonl", event)
            atomic_json(
                run_root / "STATE.json",
                {
                    "schema": schema_name(config, "state"),
                    **event,
                    "status": "running",
                    "free_gib": round(shutil.disk_usage(output_root.anchor).free / GIB, 3),
                },
            )
            print(json.dumps(event, ensure_ascii=True), flush=True)

        errors: list[str] = []
        if completed_files != config["input"]["expected_csv_files"]:
            errors.append("completed_file_count_mismatch")
        if totals["utterances"] != config["input"]["expected_rows"]:
            errors.append("utterance_count_mismatch")
        if totals["input_eojeol"] != config["input"]["expected_input_eojeol"]:
            errors.append("input_eojeol_count_mismatch")
        if errors:
            raise RuntimeError(",".join(errors))
        receipt_rows: list[str] = []
        total_output_bytes = 0
        for receipt_path in sorted((run_root / "files").rglob("RECEIPT.json")):
            receipt_rows.append(
                f"{receipt_path.relative_to(run_root).as_posix()}\t{sha256_file(receipt_path)}"
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            total_output_bytes += sum(
                int(value["bytes"]) for value in receipt["outputs"].values()
            )
        inventory_path = run_root / "RECEIPT_INVENTORY.tsv"
        inventory_path.write_text("\n".join(receipt_rows) + "\n", encoding="utf-8")
        final_manifest = {
            "schema": schema_name(config, "manifest"),
            "status": "completed",
            "completed_at": utc_now(),
            "run_id": config["run_id"],
            "server_contract": report["server_contract"],
            "fresh_morphology_analysis": True,
            "with_sense": with_sense,
            "source_csv_files": completed_files,
            "counts": totals,
            "receipt_inventory_sha256": sha256_file(inventory_path),
            "total_compressed_csv_bytes": total_output_bytes,
            "total_compressed_csv_gib": total_output_bytes / GIB,
            "protected_source_csv_modified": False,
            "textgrid_or_wav_accessed": False,
        }
        atomic_json(run_root / "FINAL_MANIFEST.json", final_manifest)
        atomic_json(
            run_root / "STATE.json",
            {"schema": schema_name(config, "state"), **final_manifest},
        )
        lock_path.unlink()
        os.replace(run_root, final_root)
        print(json.dumps(final_manifest, ensure_ascii=True, indent=2), flush=True)
        return 0
    except Exception as exc:
        atomic_json(
            run_root / "STATE.json",
            {
                "schema": schema_name(config, "state"),
                "status": "failed_safe_to_resume",
                "with_sense": with_sense,
                "failed_at": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_files": completed_files,
                "counts": totals,
            },
        )
        raise
    finally:
        if lock_path.exists():
            try:
                lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
                if int(lock_data.get("pid", -1)) == os.getpid():
                    lock_path.unlink()
            except (OSError, ValueError, json.JSONDecodeError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())

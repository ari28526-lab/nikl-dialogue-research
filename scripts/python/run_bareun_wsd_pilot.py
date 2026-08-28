#!/usr/bin/env python3
"""Run the deterministic 240-utterance Bareun WSD CSV pilot.

The script reads completed legacy CSV files without modifying them and writes
only to a new, run-scoped directory on the configured external drive. It never
prints or persists the API key.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_wsd_reanalysis_v1.json"
PREFLIGHT_MODULE = PROJECT_ROOT / "scripts" / "python"
if str(PREFLIGHT_MODULE) not in sys.path:
    sys.path.insert(0, str(PREFLIGHT_MODULE))

from preflight_bareun_wsd_environment import (  # noqa: E402
    expand_config_path,
    load_api_key,
    load_config,
)


UTTERANCE_FIELDS = [
    "year",
    "source_file",
    "source_row_index",
    "utt_id",
    "speaker_id",
    "form",
    "input_eojeol",
    "response_text",
    "response_begin_utf32",
    "response_token_count",
    "response_morph_count",
    "response_sense_count",
]
MORPH_FIELDS = [
    "year",
    "source_file",
    "source_row_index",
    "utt_id",
    "token_index",
    "morph_index",
    "token_surface",
    "token_begin_utf32",
    "token_length_utf32",
    "token_modified",
    "morph_surface",
    "pos",
    "morph_begin_utf32",
    "morph_length_utf32",
    "morph_probability",
    "out_of_vocab",
    "sense_no",
    "sense_probability",
    "urimal_target_id",
]
SENSE_FIELDS = [
    "sense_key",
    "morph_surface",
    "pos",
    "sense_no",
    "urimal_target_id",
    "meaning",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def deterministic_positions(length: int, count: int = 4) -> list[int]:
    if length < count:
        raise ValueError(f"need at least {count} files, got {length}")
    return [round(index * (length - 1) / (count - 1)) for index in range(count)]


def year_from_name(name: str) -> str:
    for year in range(2020, 2026):
        if str(year) in name:
            return str(year)
    raise ValueError(f"year not found in directory name: {name}")


def select_sample(input_root: Path, rows_per_file: int = 10) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sample: list[dict[str, Any]] = []
    source_contracts: list[dict[str, Any]] = []
    year_dirs = sorted(path for path in input_root.iterdir() if path.is_dir())
    if len(year_dirs) != 6:
        raise RuntimeError(f"expected 6 year directories, got {len(year_dirs)}")

    for year_dir in year_dirs:
        year = year_from_name(year_dir.name)
        files = sorted(
            path
            for path in year_dir.rglob("*.csv")
            if path.is_file() and not path.name.startswith("_")
        )
        selected_files = [files[index] for index in deterministic_positions(len(files))]
        year_count = 0
        for path in selected_files:
            relative = path.relative_to(input_root).as_posix()
            source_sha = sha256_file(path)
            source_contracts.append(
                {
                    "year": year,
                    "source_file": relative,
                    "sha256_before": source_sha,
                    "size_bytes": path.stat().st_size,
                }
            )
            chosen = 0
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"utt_id", "speaker_id", "form"}
                if not required.issubset(set(reader.fieldnames or [])):
                    raise RuntimeError(f"missing required columns: {relative}")
                for row_index, row in enumerate(reader, start=1):
                    form = (row.get("form") or "").strip()
                    if not form:
                        continue
                    sample.append(
                        {
                            "year": year,
                            "source_file": relative,
                            "source_path": path,
                            "source_row_index": row_index,
                            "utt_id": row.get("utt_id", ""),
                            "speaker_id": row.get("speaker_id", ""),
                            "form": form,
                        }
                    )
                    chosen += 1
                    year_count += 1
                    if chosen == rows_per_file:
                        break
            if chosen != rows_per_file:
                raise RuntimeError(
                    f"not enough non-empty rows: {relative}: {chosen}/{rows_per_file}"
                )
        if year_count != rows_per_file * 4:
            raise RuntimeError(f"pilot year count mismatch: {year}: {year_count}")
    if len(sample) != 240:
        raise RuntimeError(f"pilot sample count mismatch: {len(sample)}")
    if len({row["utt_id"] for row in sample}) != len(sample):
        raise RuntimeError("pilot sample contains duplicate utt_id")
    return sample, source_contracts


def atomic_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    with partial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


def deterministic_gzip(source: Path, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    with source.open("rb") as source_handle, partial.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, mtime=0
        ) as gzip_output:
            shutil.copyfileobj(source_handle, gzip_output)
        raw_output.flush()
        os.fsync(raw_output.fileno())
    os.replace(partial, destination)


def enum_name(message: Any, field: str, value: int) -> str:
    descriptor = message.DESCRIPTOR.fields_by_name[field].enum_type
    item = descriptor.values_by_number.get(value)
    return item.name if item is not None else str(value)


def analyze_single(
    tagger: Any,
    text: str,
    max_retries: int = 3,
    *,
    with_sense: bool = True,
    auto_spacing: bool = True,
    auto_jointing: bool = True,
) -> tuple[Any, int]:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = tagger.tag(
                text,
                auto_split=False,
                auto_spacing=auto_spacing,
                auto_jointing=auto_jointing,
                with_sense=with_sense,
            ).msg()
            sentences = list(response.sentences)
            if len(sentences) != 1:
                raise RuntimeError(
                    f"single AnalyzeSyntax cardinality mismatch: {len(sentences)}/1"
                )
            return sentences[0], attempt
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max_retries:
                time.sleep(2 ** (attempt + 1))
    assert last_error is not None
    raise last_error


def analyze_batch(
    tagger: Any,
    texts: list[str],
    max_retries: int = 3,
    *,
    with_sense: bool = True,
    auto_spacing: bool = True,
    auto_jointing: bool = True,
) -> tuple[list[Any], dict[str, int]]:
    """Use the proven legacy ``tags`` path, then fall back to ordered singles."""
    last_error: Exception | None = None
    api_calls = 0
    for attempt in range(max_retries):
        try:
            api_calls += 1
            response = tagger.tags(
                texts,
                auto_split=False,
                auto_spacing=auto_spacing,
                auto_jointing=auto_jointing,
                with_sense=with_sense,
            ).msg()
            sentences = list(response.sentences)
            if len(sentences) != len(texts):
                raise RuntimeError(
                    f"batch AnalyzeSyntax cardinality mismatch: {len(sentences)}/{len(texts)}"
                )
            return sentences, {
                "batch_retries": attempt,
                "single_fallbacks": 0,
                "single_retries": 0,
                "api_calls": api_calls,
            }
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max_retries:
                time.sleep(2 ** (attempt + 1))

    sentences = []
    single_retries = 0
    for text in texts:
        sentence, retries = analyze_single(
            tagger,
            text,
            max_retries=max_retries,
            with_sense=with_sense,
            auto_spacing=auto_spacing,
            auto_jointing=auto_jointing,
        )
        sentences.append(sentence)
        single_retries += retries
        api_calls += retries + 1
    if len(sentences) != len(texts):
        assert last_error is not None
        raise last_error
    return sentences, {
        "batch_retries": max_retries - 1,
        "single_fallbacks": len(texts),
        "single_retries": single_retries,
        "api_calls": api_calls,
    }


def parse_analysis(sample: dict[str, Any], sentence: Any) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    morph_rows: list[dict[str, Any]] = []
    sense_rows: list[dict[str, Any]] = []
    sense_count = 0
    morph_index = 0
    sentence_base = sentence.text.begin_offset
    for token_index, token in enumerate(sentence.tokens):
        for morph in token.morphemes:
            has_sense = morph.HasField("sense")
            pos = enum_name(morph, "tag", morph.tag)
            oov = enum_name(morph, "out_of_vocab", morph.out_of_vocab)
            sense_no: int | str = ""
            sense_probability: float | str = ""
            urimal_target_id = ""
            if has_sense:
                sense_no = morph.sense.sense_no
                sense_probability = morph.sense.probability
                urimal_target_id = str(morph.sense.urimal_target_id)
                sense_key_source = "\u241f".join(
                    [
                        morph.text.content,
                        pos,
                        str(sense_no),
                        urimal_target_id,
                        morph.sense.meaning,
                    ]
                )
                sense_key = hashlib.sha256(
                    sense_key_source.encode("utf-8")
                ).hexdigest()[:24]
                sense_rows.append(
                    {
                        "sense_key": sense_key,
                        "morph_surface": morph.text.content,
                        "pos": pos,
                        "sense_no": sense_no,
                        "urimal_target_id": urimal_target_id,
                        "meaning": morph.sense.meaning,
                    }
                )
                sense_count += 1
            morph_rows.append(
                {
                    "year": sample["year"],
                    "source_file": sample["source_file"],
                    "source_row_index": sample["source_row_index"],
                    "utt_id": sample["utt_id"],
                    "token_index": token_index,
                    "morph_index": morph_index,
                    "token_surface": token.text.content,
                    "token_begin_utf32": token.text.begin_offset - sentence_base,
                    "token_length_utf32": token.text.length,
                    "token_modified": token.modified,
                    "morph_surface": morph.text.content,
                    "pos": pos,
                    "morph_begin_utf32": morph.text.begin_offset - sentence_base,
                    "morph_length_utf32": morph.text.length,
                    "morph_probability": morph.probability,
                    "out_of_vocab": oov,
                    "sense_no": sense_no,
                    "sense_probability": sense_probability,
                    "urimal_target_id": urimal_target_id,
                }
            )
            morph_index += 1
    utterance_row = {
        "year": sample["year"],
        "source_file": sample["source_file"],
        "source_row_index": sample["source_row_index"],
        "utt_id": sample["utt_id"],
        "speaker_id": sample["speaker_id"],
        "form": sample["form"],
        "input_eojeol": len(sample["form"].split()),
        "response_text": sentence.text.content,
        "response_begin_utf32": sentence_base,
        "response_token_count": len(sentence.tokens),
        "response_morph_count": len(morph_rows),
        "response_sense_count": sense_count,
    }
    return utterance_row, morph_rows, sense_rows


def ensure_safe_output(config: dict[str, Any], output: Path) -> None:
    configured_root = expand_config_path(str(config["output"]["root"])).resolve()
    resolved = output.resolve()
    if configured_root not in resolved.parents:
        raise RuntimeError("pilot output must be below configured external output root")
    for protected in config.get("protected_roots", []):
        protected_path = expand_config_path(str(protected)).resolve()
        if resolved == protected_path or protected_path in resolved.parents:
            raise RuntimeError(f"pilot output overlaps protected root: {protected_path}")
    if resolved.exists():
        raise FileExistsError(f"pilot output already exists: {resolved}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    input_root = expand_config_path(str(config["input"]["root"]))
    output_root = expand_config_path(str(config["output"]["root"]))
    pilot_root = output_root / "pilot_p1_20260828"
    ensure_safe_output(config, pilot_root)
    building_root = pilot_root.with_name(pilot_root.name + ".building")
    ensure_safe_output(config, building_root)

    sample, source_contracts = select_sample(input_root)
    preflight = {
        "sample_utterances": len(sample),
        "sample_by_year": {
            year: sum(1 for row in sample if row["year"] == year)
            for year in [str(value) for value in range(2020, 2026)]
        },
        "source_files": len(source_contracts),
        "output": str(pilot_root),
        "api_call_performed": False,
    }
    if not args.execute:
        print(json.dumps(preflight, ensure_ascii=True, indent=2))
        return 0

    api_key, key_source = load_api_key(config["secret"])
    if not api_key:
        raise RuntimeError("Bareun API key not found")
    from bareunpy import Tagger

    tagger = Tagger(
        api_key,
        host=str(config["endpoint"]["host"]),
        port=int(config["endpoint"]["port"]),
    )
    building_root.mkdir(parents=True, exist_ok=False)
    atomic_csv(building_root / "PILOT_SAMPLE.csv", UTTERANCE_FIELDS[:6], sample)

    utterance_rows: list[dict[str, Any]] = []
    morph_rows: list[dict[str, Any]] = []
    sense_by_key: dict[str, dict[str, Any]] = {}
    batch_retries = 0
    single_fallbacks = 0
    single_retries = 0
    api_calls = 0
    api_batches = 0
    started = time.time()
    for start in range(0, len(sample), args.batch_size):
        part = sample[start : start + args.batch_size]
        sentences, batch_stats = analyze_batch(
            tagger,
            [row["form"] for row in part],
            max_retries=args.max_retries,
        )
        batch_retries += batch_stats["batch_retries"]
        single_fallbacks += batch_stats["single_fallbacks"]
        single_retries += batch_stats["single_retries"]
        api_calls += batch_stats["api_calls"]
        api_batches += 1
        for sample_row, sentence in zip(part, sentences, strict=True):
            utterance, morphs, senses = parse_analysis(sample_row, sentence)
            utterance_rows.append(utterance)
            morph_rows.extend(morphs)
            for sense in senses:
                existing = sense_by_key.get(sense["sense_key"])
                if existing is not None and existing != sense:
                    raise RuntimeError("sense key collision")
                sense_by_key[sense["sense_key"]] = sense
        print(
            json.dumps(
                {
                    "pilot_progress": min(start + len(part), len(sample)),
                    "pilot_total": len(sample),
                    "batch_size": len(part),
                    "batch_retries": batch_stats["batch_retries"],
                    "single_fallbacks": batch_stats["single_fallbacks"],
                    "elapsed_seconds": round(time.time() - started, 3),
                },
                ensure_ascii=True,
            ),
            flush=True,
        )

    if len(utterance_rows) != len(sample):
        raise RuntimeError("pilot response zero-drop check failed")

    atomic_csv(building_root / "utterances.csv", UTTERANCE_FIELDS, utterance_rows)
    atomic_csv(building_root / "morphemes.csv", MORPH_FIELDS, morph_rows)
    atomic_csv(
        building_root / "sense_dictionary.csv",
        SENSE_FIELDS,
        sorted(sense_by_key.values(), key=lambda row: row["sense_key"]),
    )
    for name in ["utterances.csv", "morphemes.csv", "sense_dictionary.csv"]:
        deterministic_gzip(building_root / name, building_root / f"{name}.gz")
    for contract in source_contracts:
        source_path = input_root / contract["source_file"]
        contract["sha256_after"] = sha256_file(source_path)
        contract["unchanged"] = contract["sha256_before"] == contract["sha256_after"]
    if not all(item["unchanged"] for item in source_contracts):
        raise RuntimeError("a protected pilot source CSV changed during the run")

    outputs: dict[str, Any] = {}
    output_names = [
        "PILOT_SAMPLE.csv",
        "utterances.csv",
        "morphemes.csv",
        "sense_dictionary.csv",
        "utterances.csv.gz",
        "morphemes.csv.gz",
        "sense_dictionary.csv.gz",
    ]
    for name in output_names:
        path = building_root / name
        outputs[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    uncompressed_names = ["utterances.csv", "morphemes.csv", "sense_dictionary.csv"]
    compressed_names = [f"{name}.gz" for name in uncompressed_names]
    uncompressed_bytes = sum(outputs[name]["bytes"] for name in uncompressed_names)
    compressed_bytes = sum(outputs[name]["bytes"] for name in compressed_names)
    manifest = {
        "schema": "bareun_wsd_csv_pilot.v1",
        "status": "completed_pending_independent_audit",
        "run_id": config["run_id"],
        "client": {
            "version": importlib.metadata.version("bareunpy"),
            "git_commit": config["client"]["git_commit"],
        },
        "api": {
            "method": "AnalyzeSyntax",
            "client_method": "tags",
            "fallback_method": "tag",
            "with_sense": True,
            "batch_size": args.batch_size,
            "batches": api_batches,
            "batch_retries": batch_retries,
            "single_fallbacks": single_fallbacks,
            "single_retries": single_retries,
            "api_calls": api_calls,
            "sentences_sent": len(sample),
            "key_source": key_source,
        },
        "counts": {
            "utterances": len(utterance_rows),
            "input_eojeol": sum(row["input_eojeol"] for row in utterance_rows),
            "tokens": sum(row["response_token_count"] for row in utterance_rows),
            "morphemes": len(morph_rows),
            "morphemes_with_sense": sum(row["response_sense_count"] for row in utterance_rows),
            "unique_senses": len(sense_by_key),
        },
        "sample_by_year": preflight["sample_by_year"],
        "source_contracts": source_contracts,
        "outputs": outputs,
        "uncompressed_output_bytes": uncompressed_bytes,
        "compressed_output_bytes": compressed_bytes,
        "uncompressed_bytes_per_utterance": uncompressed_bytes / len(utterance_rows),
        "compressed_bytes_per_utterance": compressed_bytes / len(utterance_rows),
        "estimated_full_uncompressed_gib": (
            uncompressed_bytes / len(utterance_rows) * config["input"]["expected_rows"] / 1024**3
        ),
        "estimated_full_compressed_gib": (
            compressed_bytes / len(utterance_rows) * config["input"]["expected_rows"] / 1024**3
        ),
        "elapsed_seconds": round(time.time() - started, 3),
        "protected_csv_changed": False,
        "textgrid_or_wav_accessed": False,
    }
    manifest_path = building_root / "PILOT_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(building_root, pilot_root)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": str(pilot_root),
                "counts": manifest["counts"],
                "estimated_full_uncompressed_gib": round(
                    manifest["estimated_full_uncompressed_gib"], 3
                ),
                "estimated_full_compressed_gib": round(
                    manifest["estimated_full_compressed_gib"], 3
                ),
                "elapsed_seconds": manifest["elapsed_seconds"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

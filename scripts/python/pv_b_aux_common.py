"""Shared fail-closed helpers for stage-2 PV-B auxiliary model pilots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import wave
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


PHENOMENA = ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")
INPUT_SCHEMA = "stage2_pv_b_input.v1"
SAFE_PV_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
REQUIRED_FIELDS = (
    "schema_version",
    "pv_id",
    "phenomenon_code",
    "occurrence_id",
    "utt_id",
    "wav_path",
    "text",
    "sex",
    "source_wav_sha256",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_new(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"existing output is never overwritten: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_jsonl_new(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"existing output is never overwritten: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")


def wav_metadata(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
    except (wave.Error, EOFError) as exc:
        raise RuntimeError(f"PCM WAV metadata read failed: {path.name}: {exc}") from exc
    if rate <= 0:
        raise RuntimeError(f"invalid WAV sample rate: {path.name}")
    return {
        "frames": frames,
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": width,
        "duration_seconds": frames / rate,
    }


def load_input_manifest(
    path: Path,
    *,
    limit: int,
    max_total: int = 70,
    max_per_phenomenon: int = 10,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"input manifest not found: {path}")
    if limit < 1 or limit > max_total:
        raise RuntimeError(f"limit must be between 1 and {max_total}")

    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            if not raw_line.strip():
                continue
            value = json.loads(raw_line)
            if not isinstance(value, dict):
                raise RuntimeError(f"row {line_number}: JSON object required")
            missing = [field for field in REQUIRED_FIELDS if field not in value]
            if missing:
                raise RuntimeError(f"row {line_number}: missing fields {missing}")
            if value["schema_version"] != INPUT_SCHEMA:
                raise RuntimeError(f"row {line_number}: unsupported schema")
            phenomenon = str(value["phenomenon_code"])
            if phenomenon not in PHENOMENA:
                raise RuntimeError(f"row {line_number}: invalid phenomenon {phenomenon}")
            if str(value["sex"]) not in {"M", "F", "U"}:
                raise RuntimeError(f"row {line_number}: sex must be M, F, or U")
            for field in ("pv_id", "occurrence_id", "utt_id", "wav_path"):
                if not str(value[field]).strip():
                    raise RuntimeError(f"row {line_number}: blank {field}")
            if not SAFE_PV_ID.fullmatch(str(value["pv_id"])):
                raise RuntimeError(f"row {line_number}: unsafe pv_id")
            wav_path = Path(str(value["wav_path"])).expanduser().resolve()
            if not wav_path.is_file() or wav_path.suffix.lower() != ".wav":
                raise RuntimeError(f"row {line_number}: WAV unavailable")
            actual_sha = sha256_file(wav_path)
            declared_sha = value.get("source_wav_sha256")
            if declared_sha is not None and str(declared_sha).lower() != actual_sha:
                raise RuntimeError(f"row {line_number}: source WAV SHA mismatch")
            normalized = dict(value)
            normalized["_wav_path"] = wav_path
            normalized["_wav_sha256"] = actual_sha
            normalized["_wav_bytes"] = wav_path.stat().st_size
            normalized["_wav_metadata"] = wav_metadata(wav_path)
            rows.append(normalized)
            if len(rows) >= limit:
                break

    if not rows:
        raise RuntimeError("input manifest has no usable rows")
    pv_ids = [str(row["pv_id"]) for row in rows]
    if len(pv_ids) != len(set(pv_ids)):
        raise RuntimeError("pv_id values must be unique")
    counts = Counter(str(row["phenomenon_code"]) for row in rows)
    over = {key: value for key, value in counts.items() if value > max_per_phenomenon}
    if over:
        raise RuntimeError(f"per-phenomenon cap exceeded: {over}")
    return rows


def input_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row["phenomenon_code"]) for row in rows)
    return {
        "row_count": len(rows),
        "phenomenon_counts": dict(sorted(counts.items())),
        "unique_utterance_count": len({str(row["utt_id"]) for row in rows}),
        "total_wav_bytes": sum(int(row["_wav_bytes"]) for row in rows),
        "total_audio_seconds": round(
            sum(float(row["_wav_metadata"]["duration_seconds"]) for row in rows),
            6,
        ),
        "sample_rates": sorted(
            {int(row["_wav_metadata"]["sample_rate"]) for row in rows}
        ),
    }


def public_input_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "pv_id": row["pv_id"],
                "phenomenon_code": row["phenomenon_code"],
                "occurrence_id": row["occurrence_id"],
                "utt_id": row["utt_id"],
                "source_wav_sha256": row["_wav_sha256"],
                "source_wav_bytes": row["_wav_bytes"],
                "wav_metadata": row["_wav_metadata"],
            }
        )
    return records


def require_new_output_root(output_dir: Path) -> Path:
    target = output_dir.resolve()
    partial = target.with_name(target.name + ".partial")
    if target.exists():
        raise FileExistsError(f"existing output is never overwritten: {target}")
    if partial.exists():
        raise FileExistsError(f"existing partial output is preserved: {partial}")
    return partial


def promote_partial(partial: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"promotion target already exists: {target}")
    os.replace(str(partial), str(target))

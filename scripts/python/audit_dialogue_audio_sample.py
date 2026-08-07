"""Create a non-destructive, session-stratified WAV quality profile.

The metrics are screening evidence, not linguistic judgments.  In particular,
``low_energy_floor_dbfs`` is only a reproducible noise proxy: continuous speech,
music, or overlapping talk can also raise it.  The script therefore ranks
sessions for review and never approves an exclusion.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import tempfile
import wave
from collections import Counter
from io import TextIOWrapper
from pathlib import Path
from typing import TextIO

import numpy as np

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "nikl_dialogue_audio_sample_audit.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")

SAMPLE_FIELDS = (
    "year",
    "session_id",
    "utt_id",
    "wav_path",
    "wav_bytes",
    "sample_rate",
    "channels",
    "sample_width_bytes",
    "duration_sec",
    "low_energy_floor_dbfs",
    "median_frame_dbfs",
    "high_energy_dbfs",
    "dynamic_range_db",
    "start_edge_dbfs",
    "end_edge_dbfs",
    "start_edge_relative_high_db",
    "end_edge_relative_high_db",
    "digital_clip_fraction",
    "dc_offset",
    "read_status",
    "researcher_decision",
)

SESSION_FIELDS = (
    "year",
    "session_id",
    "wav_count",
    "sampled_wav_count",
    "readable_wav_count",
    "invalid_wav_count",
    "full_session_profile",
    "researcher_reported_noise",
    "median_low_energy_floor_dbfs",
    "median_dynamic_range_db",
    "median_start_edge_relative_high_db",
    "median_end_edge_relative_high_db",
    "active_start_edge_pct",
    "active_end_edge_pct",
    "noise_proxy_percentile",
    "review_priority",
    "researcher_decision",
)


class DeterministicGzipCsv:
    def __init__(self, destination: Path, fields: tuple[str, ...]) -> None:
        self.destination = destination
        self.fields = fields
        self.temp: Path | None = None
        self.raw = None
        self.compressed = None
        self.text: TextIO | None = None
        self.writer: csv.DictWriter | None = None

    def __enter__(self) -> csv.DictWriter:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{self.destination.name}.",
            suffix=".partial",
            dir=self.destination.parent,
        )
        os.close(handle)
        self.temp = Path(temp_name)
        self.raw = open(self.temp, "wb")
        self.compressed = gzip.GzipFile(
            filename="", mode="wb", fileobj=self.raw, mtime=0
        )
        self.text = TextIOWrapper(
            self.compressed, encoding="utf-8-sig", newline=""
        )
        self.writer = csv.DictWriter(self.text, fieldnames=self.fields)
        self.writer.writeheader()
        return self.writer

    def __exit__(self, exc_type, exc, traceback) -> None:
        assert self.temp is not None
        if self.text is not None:
            self.text.flush()
            self.text.close()
        elif self.compressed is not None:
            self.compressed.close()
        if self.raw is not None and not self.raw.closed:
            self.raw.close()
        if exc_type is None:
            os.replace(self.temp, self.destination)


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-12))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _format(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def read_wav_metrics(path: Path, *, frame_ms: float, edge_ms: float) -> dict[str, object]:
    stat = path.stat()
    with wave.open(str(path), "rb") as stream:
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        rate = stream.getframerate()
        frame_count = stream.getnframes()
        compression = stream.getcomptype()
        raw = stream.readframes(frame_count)
    if channels <= 0 or rate <= 0 or frame_count <= 0:
        raise ValueError("invalid WAV header")
    if compression != "NONE" or width != 2:
        raise ValueError(
            f"unsupported WAV encoding compression={compression} width={width}"
        )
    expected = frame_count * channels * width
    if len(raw) != expected:
        raise ValueError(f"truncated WAV payload expected={expected} actual={len(raw)}")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    samples /= 32768.0
    window = max(1, int(round(rate * frame_ms / 1000.0)))
    usable = (samples.size // window) * window
    if usable:
        framed = samples[:usable].reshape(-1, window)
        rms = np.sqrt(np.mean(framed * framed, axis=1))
    else:
        rms = np.asarray([math.sqrt(float(np.mean(samples * samples)))])
    frame_db = np.asarray([_dbfs(value) for value in rms], dtype=np.float64)
    low = float(np.percentile(frame_db, 10))
    median = float(np.percentile(frame_db, 50))
    high = float(np.percentile(frame_db, 90))
    edge_frames = max(1, min(samples.size, int(round(rate * edge_ms / 1000.0))))
    start_edge = _dbfs(math.sqrt(float(np.mean(samples[:edge_frames] ** 2))))
    end_edge = _dbfs(math.sqrt(float(np.mean(samples[-edge_frames:] ** 2))))
    return {
        "wav_bytes": stat.st_size,
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": width,
        "duration_sec": frame_count / rate,
        "low_energy_floor_dbfs": low,
        "median_frame_dbfs": median,
        "high_energy_dbfs": high,
        "dynamic_range_db": high - low,
        "start_edge_dbfs": start_edge,
        "end_edge_dbfs": end_edge,
        "start_edge_relative_high_db": start_edge - high,
        "end_edge_relative_high_db": end_edge - high,
        "digital_clip_fraction": float(np.mean(np.abs(samples) >= 0.999)),
        "dc_offset": float(np.mean(samples)),
    }


def deterministic_sample(files: list[Path], count: int) -> list[Path]:
    ordered = sorted(files, key=lambda path: path.name)
    if count <= 0 or len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[0]]
    indexes = {
        int(round(index * (len(ordered) - 1) / (count - 1)))
        for index in range(count)
    }
    return [ordered[index] for index in sorted(indexes)]


def load_sessions(structural_session_summary: Path) -> list[str]:
    sessions: list[str] = []
    with gzip.open(
        structural_session_summary,
        "rt",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        for row in csv.DictReader(stream):
            session = str(row.get("session_id") or "").strip()
            if not session:
                raise RuntimeError("structural session summary has empty session_id")
            sessions.append(session)
    if len(sessions) != len(set(sessions)):
        raise RuntimeError("duplicate session_id in structural session summary")
    return sessions


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """Return stable 0..100 ranks; a higher value means a higher noise proxy."""
    ordered = sorted((value, session) for session, value in values.items())
    size = len(ordered)
    if size <= 1:
        return {session: 50.0 for _, session in ordered}
    result: dict[str, float] = {}
    index = 0
    while index < size:
        end = index + 1
        while end < size and ordered[end][0] == ordered[index][0]:
            end += 1
        mean_rank = ((index + end - 1) / 2) / (size - 1) * 100.0
        for _, session in ordered[index:end]:
            result[session] = mean_rank
        index = end
    return result


def run_audit(
    *,
    year: str,
    wav_root: Path,
    structural_session_summary: Path,
    output_root: Path,
    samples_per_session: int = 16,
    full_sessions: set[str] | None = None,
    researcher_reported_noise_sessions: set[str] | None = None,
    frame_ms: float = 20.0,
    edge_ms: float = 50.0,
) -> dict[str, object]:
    if year not in YEARS:
        raise ValueError(year)
    wav_root = wav_root.resolve()
    structural_session_summary = structural_session_summary.resolve()
    output_root = output_root.resolve()
    if not wav_root.is_dir():
        raise FileNotFoundError(wav_root)
    if not structural_session_summary.is_file():
        raise FileNotFoundError(structural_session_summary)
    if output_root.exists():
        raise FileExistsError(f"existing output protected: {output_root}")
    output_root.mkdir(parents=True)
    full_sessions = set(full_sessions or ())
    reported = set(researcher_reported_noise_sessions or ())
    sessions = load_sessions(structural_session_summary)
    unknown = (full_sessions | reported) - set(sessions)
    if unknown:
        raise RuntimeError(f"unknown session ids: {sorted(unknown)}")

    sample_rows: list[dict[str, object]] = []
    session_rows: list[dict[str, object]] = []
    totals = Counter()
    for index, session in enumerate(sessions, start=1):
        session_dir = wav_root / session
        files = (
            sorted(session_dir.glob("*.wav"), key=lambda path: path.name)
            if session_dir.is_dir()
            else []
        )
        selected = (
            files
            if session in full_sessions
            else deterministic_sample(files, samples_per_session)
        )
        metrics: list[dict[str, object]] = []
        invalid = 0
        for path in selected:
            base = {
                "year": year,
                "session_id": session,
                "utt_id": path.stem,
                "wav_path": str(path),
                "researcher_decision": "pending",
            }
            try:
                measured = read_wav_metrics(
                    path, frame_ms=frame_ms, edge_ms=edge_ms
                )
                metrics.append(measured)
                row = {
                    **base,
                    **{
                        key: _format(value)
                        if isinstance(value, float)
                        else value
                        for key, value in measured.items()
                    },
                    "read_status": "readable",
                }
            except (OSError, EOFError, wave.Error, ValueError) as exc:
                invalid += 1
                row = {
                    **base,
                    **{field: "" for field in SAMPLE_FIELDS if field not in base},
                    "read_status": f"invalid:{type(exc).__name__}:{exc}",
                    "researcher_decision": "pending",
                }
            sample_rows.append(row)
        lows = [float(item["low_energy_floor_dbfs"]) for item in metrics]
        dynamics = [float(item["dynamic_range_db"]) for item in metrics]
        starts = [float(item["start_edge_relative_high_db"]) for item in metrics]
        ends = [float(item["end_edge_relative_high_db"]) for item in metrics]
        # Edge within 12 dB of the utterance's high-energy frames is a review
        # signal only, not proof of clipping.
        active_start = sum(value >= -12.0 for value in starts)
        active_end = sum(value >= -12.0 for value in ends)
        readable = len(metrics)
        session_rows.append(
            {
                "year": year,
                "session_id": session,
                "wav_count": len(files),
                "sampled_wav_count": len(selected),
                "readable_wav_count": readable,
                "invalid_wav_count": invalid,
                "full_session_profile": str(session in full_sessions).lower(),
                "researcher_reported_noise": str(session in reported).lower(),
                "median_low_energy_floor_dbfs": _format(_median(lows)),
                "median_dynamic_range_db": _format(_median(dynamics)),
                "median_start_edge_relative_high_db": _format(_median(starts)),
                "median_end_edge_relative_high_db": _format(_median(ends)),
                "active_start_edge_pct": _format(
                    100 * active_start / readable if readable else None
                ),
                "active_end_edge_pct": _format(
                    100 * active_end / readable if readable else None
                ),
                "noise_proxy_percentile": "",
                "review_priority": "pending_ranking",
                "researcher_decision": "pending",
            }
        )
        totals["sessions"] += 1
        totals["wav_files"] += len(files)
        totals["sampled_wavs"] += len(selected)
        totals["readable_wavs"] += readable
        totals["invalid_wavs"] += invalid
        if not files:
            totals["sessions_without_wav"] += 1
        if index % 250 == 0 or index == len(sessions):
            print(
                f"[{year}] {index:,}/{len(sessions):,} sessions · "
                f"{totals['sampled_wavs']:,} WAV sampled",
                flush=True,
            )

    rank_inputs = {
        str(row["session_id"]): float(row["median_low_energy_floor_dbfs"])
        for row in session_rows
        if row["median_low_energy_floor_dbfs"] != ""
    }
    ranks = percentile_ranks(rank_inputs)
    for row in session_rows:
        session = str(row["session_id"])
        rank = ranks.get(session)
        row["noise_proxy_percentile"] = _format(rank)
        if row["invalid_wav_count"]:
            row["review_priority"] = "invalid_wav_review"
        elif row["researcher_reported_noise"] == "true":
            row["review_priority"] = "researcher_reported_noise_review"
        elif rank is not None and rank >= 95.0:
            row["review_priority"] = "high_noise_proxy_review"
        else:
            row["review_priority"] = "routine"

    sample_path = output_root / "01_AUDIO_SAMPLE_METRICS.csv.gz"
    session_path = output_root / "02_SESSION_AUDIO_SUMMARY.csv.gz"
    with DeterministicGzipCsv(sample_path, SAMPLE_FIELDS) as writer:
        writer.writerows(sample_rows)
    with DeterministicGzipCsv(session_path, SESSION_FIELDS) as writer:
        writer.writerows(session_rows)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_quality_review",
        "created_at": now_iso(),
        "year": year,
        "policy": {
            "samples_per_session": samples_per_session,
            "full_sessions": sorted(full_sessions),
            "researcher_reported_noise_sessions": sorted(reported),
            "frame_ms": frame_ms,
            "edge_ms": edge_ms,
            "active_edge_relative_high_threshold_db": -12.0,
            "noise_proxy": (
                "median per-utterance 10th-percentile 20ms frame energy; "
                "rank is review-only and not an SNR measurement"
            ),
            "automatic_exclusion_performed": False,
            "denoising_or_audio_modification_performed": False,
            "actual_phonological_realization_judged": False,
        },
        "source": {
            "wav_root": str(wav_root),
            "structural_session_summary": file_fingerprint(
                structural_session_summary, with_sha256=True
            ),
        },
        "counts": dict(sorted(totals.items())),
        "outputs": {
            "sample_metrics": file_fingerprint(sample_path, with_sha256=True),
            "session_summary": file_fingerprint(session_path, with_sha256=True),
        },
        "next_step": (
            "Review ranked sessions and join confirmed source overlap/MFA state; "
            "do not approve exclusion from the proxy alone."
        ),
    }
    atomic_write_json(output_root / "MANIFEST.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, choices=YEARS)
    parser.add_argument("--wav-root", required=True, type=Path)
    parser.add_argument(
        "--structural-session-summary", required=True, type=Path
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--samples-per-session", type=int, default=16)
    parser.add_argument("--full-session", action="append", default=[])
    parser.add_argument(
        "--researcher-reported-noise-session", action="append", default=[]
    )
    parser.add_argument("--frame-ms", type=float, default=20.0)
    parser.add_argument("--edge-ms", type=float, default=50.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.samples_per_session <= 0 or args.frame_ms <= 0 or args.edge_ms <= 0:
        raise ValueError("sample count and time windows must be positive")
    run_audit(
        year=args.year,
        wav_root=args.wav_root,
        structural_session_summary=args.structural_session_summary,
        output_root=args.output_root,
        samples_per_session=args.samples_per_session,
        full_sessions=set(args.full_session),
        researcher_reported_noise_sessions=set(
            args.researcher_reported_noise_session
        ),
        frame_ms=args.frame_ms,
        edge_ms=args.edge_ms,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

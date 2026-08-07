"""Summarize the common 2020--2025 dialogue-audio quality audits.

This report is deliberately descriptive.  It does not turn screening metrics
into exclusions, does not approve a researcher decision, and does not modify
source audio, MFA databases, or TextGrids.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "nikl_dialogue_audio_quality_summary.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")

FIELDS = (
    "year",
    "utterances",
    "sessions",
    "confirmed_source_overlap",
    "confirmed_source_overlap_pct",
    "source_time_invalid",
    "boundary_abut_review",
    "boundary_abut_review_pct",
    "wav_files",
    "sampled_wavs",
    "readable_sampled_wavs",
    "invalid_sampled_wavs",
    "full_scan_bad_wavs",
    "sessions_without_wav",
    "high_noise_proxy_review_sessions",
    "invalid_wav_review_sessions",
    "researcher_reported_noise_sessions",
    "automatic_exclusion_performed",
    "researcher_decision",
)


def _load_json(path: Path) -> dict[str, object]:
    with open(path, encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def _pct(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.6f}" if denominator else ""


def summarize_year(year_root: Path, year: str) -> tuple[dict[str, object], dict[str, object]]:
    structural_path = year_root / "MANIFEST.json"
    audio_root = year_root / "03_AUDIO_SAMPLE"
    audio_manifest_path = audio_root / "MANIFEST.json"
    audio_session_path = audio_root / "02_SESSION_AUDIO_SUMMARY.csv.gz"
    bad_wav_path = year_root / "05_BAD_WAV_FULL_SCAN.csv"
    for path in (
        structural_path,
        audio_manifest_path,
        audio_session_path,
        bad_wav_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    structural = _load_json(structural_path)
    audio = _load_json(audio_manifest_path)
    if str(structural.get("year")) != year or str(audio.get("year")) != year:
        raise RuntimeError(f"year mismatch under {year_root}")
    structural_counts = structural.get("counts")
    audio_counts = audio.get("counts")
    audio_policy = audio.get("policy")
    if not all(isinstance(value, dict) for value in (structural_counts, audio_counts, audio_policy)):
        raise RuntimeError(f"manifest contract missing under {year_root}")

    priorities: Counter[str] = Counter()
    with gzip.open(audio_session_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for record in csv.DictReader(stream):
            priorities[str(record.get("review_priority") or "")] += 1

    with open(bad_wav_path, encoding="utf-8-sig", newline="") as stream:
        bad_wav_rows = list(csv.DictReader(stream))
    invalid_sizes = [
        row.get("size_bytes", "")
        for row in bad_wav_rows
        if not str(row.get("size_bytes", "")).isdigit()
        or int(str(row["size_bytes"])) > 44
    ]
    if invalid_sizes:
        raise RuntimeError(
            f"full bad-WAV inventory contains invalid sizes: {invalid_sizes[:10]}"
        )

    utterances = int(structural_counts.get("utterances", 0))
    overlaps = int(structural_counts.get("confirmed_overlap_union", 0))
    abut = int(structural_counts.get("boundary_abut_members", 0))
    automatic = bool(audio_policy.get("automatic_exclusion_performed"))
    row: dict[str, object] = {
        "year": year,
        "utterances": utterances,
        "sessions": int(structural_counts.get("sessions", 0)),
        "confirmed_source_overlap": overlaps,
        "confirmed_source_overlap_pct": _pct(overlaps, utterances),
        "source_time_invalid": int(structural_counts.get("source_time_invalid", 0)),
        "boundary_abut_review": abut,
        "boundary_abut_review_pct": _pct(abut, utterances),
        "wav_files": int(audio_counts.get("wav_files", 0)),
        "sampled_wavs": int(audio_counts.get("sampled_wavs", 0)),
        "readable_sampled_wavs": int(audio_counts.get("readable_wavs", 0)),
        "invalid_sampled_wavs": int(audio_counts.get("invalid_wavs", 0)),
        "full_scan_bad_wavs": len(bad_wav_rows),
        "sessions_without_wav": int(audio_counts.get("sessions_without_wav", 0)),
        "high_noise_proxy_review_sessions": priorities["high_noise_proxy_review"],
        "invalid_wav_review_sessions": priorities["invalid_wav_review"],
        "researcher_reported_noise_sessions": priorities["researcher_reported_noise_review"],
        "automatic_exclusion_performed": str(automatic).lower(),
        "researcher_decision": "pending",
    }
    evidence = {
        "structural_manifest": file_fingerprint(structural_path, with_sha256=True),
        "audio_manifest": file_fingerprint(audio_manifest_path, with_sha256=True),
        "audio_session_summary": file_fingerprint(audio_session_path, with_sha256=True),
        "full_bad_wav_inventory": file_fingerprint(bad_wav_path, with_sha256=True),
    }
    return row, evidence


def build_summary(*, audit_root: Path, output_csv: Path, output_manifest: Path) -> dict[str, object]:
    audit_root = audit_root.resolve()
    output_csv = output_csv.resolve()
    output_manifest = output_manifest.resolve()
    if output_csv.exists() or output_manifest.exists():
        raise FileExistsError("existing summary output protected")

    rows: list[dict[str, object]] = []
    inputs: dict[str, object] = {}
    for year in YEARS:
        row, evidence = summarize_year(audit_root / year, year)
        rows.append(row)
        inputs[year] = evidence

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_quality_review",
        "created_at": now_iso(),
        "years": list(YEARS),
        "policy": {
            "boundary_abut_is_not_clipping_proof": True,
            "noise_proxy_is_not_snr_or_exclusion_proof": True,
            "automatic_exclusion_performed": False,
            "actual_phonological_realization_judged": False,
        },
        "inputs": inputs,
        "output": file_fingerprint(output_csv, with_sha256=True),
        "next_step": (
            "Join source-overlap, exact utterance edge evidence, MFA state, and "
            "researcher decisions before creating any exclusion contract."
        ),
    }
    atomic_write_json(output_manifest, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-root", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_summary(
        audit_root=args.audit_root,
        output_csv=args.output_csv,
        output_manifest=args.output_manifest,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

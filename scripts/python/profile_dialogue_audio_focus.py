"""Join exact utterance audio metrics with structural and session evidence.

The output is a researcher-review inventory.  It never writes an exclusion
contract and never converts a proxy or a boundary touch into an approved
quality judgment.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import wave
from pathlib import Path

from audit_dialogue_audio_sample import read_wav_metrics
from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "nikl_dialogue_audio_focus_profile.v1"

FIELDS = (
    "year",
    "utt_id",
    "session_id",
    "focus_sources",
    "candidate_review_order",
    "pilot_review_order",
    "sample_role",
    "input_reason_code",
    "normalized_text",
    "wav_path",
    "wav_read_status",
    "wav_duration_sec",
    "structural_reason_codes",
    "structural_evidence_class",
    "max_time_overlap_sec",
    "boundary_abut_prev",
    "boundary_abut_next",
    "start_edge_relative_high_db",
    "end_edge_relative_high_db",
    "active_start_edge_review",
    "active_end_edge_review",
    "session_noise_proxy_percentile",
    "session_audio_review_priority",
    "review_signals",
    "scope_if_researcher_approves",
    "researcher_decision",
    "researcher_notes",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def load_focus(paths: list[Path]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            is_pilot = "sample_role" in (reader.fieldnames or ())
            for row in reader:
                utt_id = _text(row.get("utt_id"))
                if not utt_id:
                    raise RuntimeError(f"empty utt_id: {path}")
                record = result.setdefault(
                    utt_id,
                    {
                        "focus_sources": [],
                        "candidate_review_order": "",
                        "pilot_review_order": "",
                        "sample_role": "",
                        "input_reason_code": "",
                        "normalized_text": "",
                    },
                )
                record["focus_sources"].append(path.name)
                order = _text(row.get("review_order"))
                if order:
                    record[
                        "pilot_review_order" if is_pilot else "candidate_review_order"
                    ] = order
                for output_key, source_key in (
                    ("sample_role", "sample_role"),
                    ("input_reason_code", "reason_code"),
                    ("normalized_text", "normalized_text"),
                ):
                    value = _text(row.get(source_key))
                    if value:
                        record[output_key] = value
    return result


def load_structural_flags(path: Path, target_ids: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            utt_id = _text(row.get("utt_id"))
            if utt_id in target_ids:
                result[utt_id] = row
    return result


def load_session_audio(path: Path, sessions: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            session = _text(row.get("session_id"))
            if session in sessions:
                result[session] = row
    missing = sessions - set(result)
    if missing:
        raise RuntimeError(f"session audio summary missing: {sorted(missing)[:10]}")
    return result


def _format(value: object) -> str:
    return f"{value:.6f}" if isinstance(value, float) else _text(value)


def build_profile(
    *,
    year: str,
    focus_csvs: list[Path],
    wav_root: Path,
    structural_flags: Path,
    audio_session_summary: Path,
    output_csv: Path,
    output_manifest: Path,
    frame_ms: float = 20.0,
    edge_ms: float = 50.0,
    active_edge_threshold_db: float = -12.0,
) -> dict[str, object]:
    for path in (*focus_csvs, structural_flags, audio_session_summary):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not wav_root.is_dir():
        raise FileNotFoundError(wav_root)
    if output_csv.exists() or output_manifest.exists():
        raise FileExistsError("existing focus output protected")

    focus = load_focus(focus_csvs)
    sessions = {utt_id.split(".", 1)[0] for utt_id in focus}
    structures = load_structural_flags(structural_flags, set(focus))
    session_audio = load_session_audio(audio_session_summary, sessions)
    rows: list[dict[str, str]] = []
    counts = {
        "focus_utterances": len(focus),
        "readable_wavs": 0,
        "invalid_or_missing_wavs": 0,
        "confirmed_source_overlap": 0,
        "boundary_edge_review": 0,
        "high_noise_proxy_review": 0,
        "alignment_and_analysis_if_approved": 0,
        "analysis_only_if_approved": 0,
    }
    for utt_id in sorted(focus):
        metadata = focus[utt_id]
        session = utt_id.split(".", 1)[0]
        wav_path = wav_root / session / f"{utt_id}.wav"
        try:
            metrics = read_wav_metrics(wav_path, frame_ms=frame_ms, edge_ms=edge_ms)
            wav_status = "readable"
            counts["readable_wavs"] += 1
        except (OSError, EOFError, ValueError, wave.Error) as exc:
            metrics = {}
            wav_status = f"invalid_or_missing:{type(exc).__name__}:{exc}"
            counts["invalid_or_missing_wavs"] += 1

        structural = structures.get(utt_id, {})
        session_row = session_audio[session]
        confirmed_overlap = structural.get("evidence_class") == "confirmed_source_overlap"
        abut = structural.get("boundary_abut_prev") == "true" or structural.get("boundary_abut_next") == "true"
        start_relative = metrics.get("start_edge_relative_high_db")
        end_relative = metrics.get("end_edge_relative_high_db")
        active_start = isinstance(start_relative, float) and start_relative >= active_edge_threshold_db
        active_end = isinstance(end_relative, float) and end_relative >= active_edge_threshold_db
        boundary_edge = abut and (active_start or active_end)
        session_priority = _text(session_row.get("review_priority"))
        high_noise = session_priority in {
            "high_noise_proxy_review",
            "researcher_reported_noise_review",
        }
        signals: list[str] = []
        if confirmed_overlap:
            signals.append("confirmed_source_overlap")
            counts["confirmed_source_overlap"] += 1
        if boundary_edge:
            signals.append("boundary_edge_audio_review")
            counts["boundary_edge_review"] += 1
        if high_noise:
            signals.append("high_noise_proxy_review")
            counts["high_noise_proxy_review"] += 1
        if wav_status != "readable":
            signals.append("invalid_or_missing_wav")

        input_reason = _text(metadata.get("input_reason_code"))
        if input_reason == "mfa_alignment_missing" or wav_status != "readable":
            scope = "alignment_and_analysis_candidate"
            counts["alignment_and_analysis_if_approved"] += 1
        elif signals:
            scope = "analysis_only_candidate"
            counts["analysis_only_if_approved"] += 1
        else:
            scope = "retain_pending_other_evidence"

        rows.append(
            {
                "year": year,
                "utt_id": utt_id,
                "session_id": session,
                "focus_sources": "|".join(sorted(set(metadata["focus_sources"]))),
                "candidate_review_order": _text(metadata.get("candidate_review_order")),
                "pilot_review_order": _text(metadata.get("pilot_review_order")),
                "sample_role": _text(metadata.get("sample_role")),
                "input_reason_code": input_reason,
                "normalized_text": _text(metadata.get("normalized_text")),
                "wav_path": str(wav_path),
                "wav_read_status": wav_status,
                "wav_duration_sec": _format(metrics.get("duration_sec")),
                "structural_reason_codes": _text(structural.get("reason_codes")),
                "structural_evidence_class": _text(structural.get("evidence_class")),
                "max_time_overlap_sec": _text(structural.get("max_time_overlap_sec")),
                "boundary_abut_prev": _text(structural.get("boundary_abut_prev")),
                "boundary_abut_next": _text(structural.get("boundary_abut_next")),
                "start_edge_relative_high_db": _format(start_relative),
                "end_edge_relative_high_db": _format(end_relative),
                "active_start_edge_review": str(active_start).lower(),
                "active_end_edge_review": str(active_end).lower(),
                "session_noise_proxy_percentile": _text(session_row.get("noise_proxy_percentile")),
                "session_audio_review_priority": session_priority,
                "review_signals": "|".join(signals),
                "scope_if_researcher_approves": scope,
                "researcher_decision": "pending",
                "researcher_notes": "",
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_quality_review",
        "created_at": now_iso(),
        "year": year,
        "policy": {
            "active_edge_threshold_db": active_edge_threshold_db,
            "boundary_edge_is_review_signal_not_clipping_proof": True,
            "session_noise_proxy_is_review_signal_not_exclusion_proof": True,
            "automatic_exclusion_performed": False,
            "source_or_mfa_output_modified": False,
        },
        "counts": counts,
        "inputs": {
            "focus_csvs": [file_fingerprint(path, with_sha256=True) for path in focus_csvs],
            "structural_flags": file_fingerprint(structural_flags, with_sha256=True),
            "audio_session_summary": file_fingerprint(audio_session_summary, with_sha256=True),
            "wav_root": str(wav_root.resolve()),
        },
        "output": file_fingerprint(output_csv, with_sha256=True),
    }
    atomic_write_json(output_manifest, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--focus-csv", required=True, action="append", type=Path)
    parser.add_argument("--wav-root", required=True, type=Path)
    parser.add_argument("--structural-flags", required=True, type=Path)
    parser.add_argument("--audio-session-summary", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_profile(
        year=args.year,
        focus_csvs=args.focus_csv,
        wav_root=args.wav_root,
        structural_flags=args.structural_flags,
        audio_session_summary=args.audio_session_summary,
        output_csv=args.output_csv,
        output_manifest=args.output_manifest,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

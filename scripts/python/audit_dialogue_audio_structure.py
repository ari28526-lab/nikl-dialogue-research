"""Audit NIKL dialogue utterance timing/overlap without modifying sources.

The audit deliberately separates two kinds of evidence:

* ``overlapping_speech``: the source JSON explicitly marks overlap or two
  utterance time spans overlap.  This is a strong candidate for exclusion from
  single-speaker acoustic analysis, but this script does not approve it.
* ``boundary_abut_review``: adjacent source intervals meet within a small
  tolerance.  This is only a review candidate because an exact annotation
  boundary does not by itself prove that speech was clipped.

One run handles one year and writes deterministic gzip CSV tables plus a
manifest.  No WAV, JSON, MFA database, TextGrid, or approval contract is
modified.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from typing import TextIO

from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "nikl_dialogue_audio_structure_audit.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
OVERLAP_NOTE_TOKEN = "발화겹침"

FLAG_FIELDS = (
    "year",
    "session_id",
    "utt_id",
    "speaker_id",
    "start_sec",
    "end_sec",
    "duration_sec",
    "json_note",
    "json_overlap_note",
    "time_overlap",
    "max_time_overlap_sec",
    "boundary_abut_prev",
    "boundary_abut_next",
    "prev_gap_sec",
    "next_gap_sec",
    "reason_codes",
    "evidence_class",
    "recommended_scope",
    "researcher_decision",
)

SESSION_FIELDS = (
    "year",
    "session_id",
    "source_json",
    "utterance_count",
    "source_time_invalid_count",
    "json_overlap_note_count",
    "time_overlap_member_count",
    "confirmed_overlap_union_count",
    "confirmed_overlap_union_pct",
    "boundary_abut_member_count",
    "boundary_abut_member_pct",
    "nonempty_note_count",
    "min_gap_sec",
    "median_gap_sec",
    "max_gap_sec",
    "session_review_priority",
    "researcher_decision",
)


@dataclass(frozen=True)
class Utterance:
    year: str
    session_id: str
    utt_id: str
    speaker_id: str
    start: float
    end: float
    note: str

    @property
    def duration(self) -> float:
        return self.end - self.start


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object, *, label: str, source: Path) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{source}: invalid {label}={value!r}") from exc
    if not (result == result and abs(result) != float("inf")):
        raise RuntimeError(f"{source}: non-finite {label}={value!r}")
    return result


def parse_json_bytes(
    *, year: str, source: Path, raw: bytes
) -> list[Utterance]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON read failure: {source}: {exc}") from exc
    documents = payload.get("document")
    if not isinstance(documents, list) or not documents:
        raise RuntimeError(f"{source}: document list missing")
    rows: list[Utterance] = []
    seen: set[str] = set()
    for document in documents:
        utterances = document.get("utterance") if isinstance(document, dict) else None
        if not isinstance(utterances, list):
            raise RuntimeError(f"{source}: utterance list missing")
        for raw_row in utterances:
            if not isinstance(raw_row, dict):
                raise RuntimeError(f"{source}: non-object utterance")
            utt_id = _clean_text(raw_row.get("id"))
            if not utt_id or utt_id in seen:
                raise RuntimeError(f"{source}: empty/duplicate utterance id {utt_id!r}")
            seen.add(utt_id)
            start = _number(raw_row.get("start"), label="start", source=source)
            end = _number(raw_row.get("end"), label="end", source=source)
            session_id = utt_id.split(".", 1)[0]
            rows.append(
                Utterance(
                    year=year,
                    session_id=session_id,
                    utt_id=utt_id,
                    speaker_id=_clean_text(raw_row.get("speaker_id")),
                    start=start,
                    end=end,
                    note=_clean_text(raw_row.get("note")),
                )
            )
    if not rows:
        raise RuntimeError(f"{source}: zero utterances")
    session_ids = {row.session_id for row in rows}
    if len(session_ids) != 1:
        raise RuntimeError(f"{source}: multiple session ids {sorted(session_ids)}")
    return rows


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        return 0.0
    middle = size // 2
    if size % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def classify_session(
    rows: list[Utterance],
    *,
    overlap_tolerance: float,
    abut_tolerance: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return flagged utterances and one session summary.

    All interval-overlap memberships are found with an active interval set, so
    a long turn overlapping more than one short turn is not missed.
    """

    invalid_rows = [row for row in rows if row.start < 0 or row.end <= row.start]
    ordered = sorted(
        (row for row in rows if row.start >= 0 and row.end > row.start),
        key=lambda row: (row.start, row.end, row.utt_id),
    )
    overlaps: dict[str, float] = {row.utt_id: 0.0 for row in ordered}
    active: list[Utterance] = []
    for row in ordered:
        active = [
            previous
            for previous in active
            if previous.end > row.start + overlap_tolerance
        ]
        for previous in active:
            amount = min(previous.end, row.end) - max(previous.start, row.start)
            if amount > overlap_tolerance:
                overlaps[row.utt_id] = max(overlaps[row.utt_id], amount)
                overlaps[previous.utt_id] = max(overlaps[previous.utt_id], amount)
        active.append(row)

    prev_gaps: dict[str, float | None] = {row.utt_id: None for row in ordered}
    next_gaps: dict[str, float | None] = {row.utt_id: None for row in ordered}
    abut_prev: set[str] = set()
    abut_next: set[str] = set()
    adjacency_gaps: list[float] = []
    for previous, current in zip(ordered, ordered[1:]):
        gap = current.start - previous.end
        adjacency_gaps.append(gap)
        prev_gaps[current.utt_id] = gap
        next_gaps[previous.utt_id] = gap
        if abs(gap) <= abut_tolerance:
            abut_next.add(previous.utt_id)
            abut_prev.add(current.utt_id)

    flagged: list[dict[str, object]] = []
    note_overlap_ids: set[str] = set()
    time_overlap_ids = {utt_id for utt_id, value in overlaps.items() if value > 0}
    abut_ids = abut_prev | abut_next
    nonempty_notes = sum(1 for row in rows if row.note)
    for row in ordered:
        note_overlap = OVERLAP_NOTE_TOKEN in row.note
        if note_overlap:
            note_overlap_ids.add(row.utt_id)
        time_overlap = row.utt_id in time_overlap_ids
        boundary_candidate = row.utt_id in abut_ids
        if not (note_overlap or time_overlap or boundary_candidate):
            continue
        reason_codes: list[str] = []
        if note_overlap:
            reason_codes.append("source_note_overlap")
        if time_overlap:
            reason_codes.append("source_time_overlap")
        if boundary_candidate:
            reason_codes.append("boundary_abut_review")
        confirmed_overlap = note_overlap or time_overlap
        flagged.append(
            {
                "year": row.year,
                "session_id": row.session_id,
                "utt_id": row.utt_id,
                "speaker_id": row.speaker_id,
                "start_sec": f"{row.start:.6f}",
                "end_sec": f"{row.end:.6f}",
                "duration_sec": f"{row.duration:.6f}",
                "json_note": row.note,
                "json_overlap_note": str(note_overlap).lower(),
                "time_overlap": str(time_overlap).lower(),
                "max_time_overlap_sec": f"{overlaps[row.utt_id]:.6f}",
                "boundary_abut_prev": str(row.utt_id in abut_prev).lower(),
                "boundary_abut_next": str(row.utt_id in abut_next).lower(),
                "prev_gap_sec": "" if prev_gaps[row.utt_id] is None else f"{prev_gaps[row.utt_id]:.6f}",
                "next_gap_sec": "" if next_gaps[row.utt_id] is None else f"{next_gaps[row.utt_id]:.6f}",
                "reason_codes": "|".join(reason_codes),
                "evidence_class": (
                    "confirmed_source_overlap"
                    if confirmed_overlap
                    else "audio_review_required"
                ),
                "recommended_scope": (
                    "exclude_single_speaker_acoustic_analysis"
                    if confirmed_overlap
                    else "retain_pending_audio_edge_review"
                ),
                "researcher_decision": "pending",
            }
        )

    for row in invalid_rows:
        note_overlap = OVERLAP_NOTE_TOKEN in row.note
        reason_codes = ["source_time_invalid"]
        if note_overlap:
            note_overlap_ids.add(row.utt_id)
            reason_codes.append("source_note_overlap")
        flagged.append(
            {
                "year": row.year,
                "session_id": row.session_id,
                "utt_id": row.utt_id,
                "speaker_id": row.speaker_id,
                "start_sec": f"{row.start:.6f}",
                "end_sec": f"{row.end:.6f}",
                "duration_sec": f"{row.duration:.6f}",
                "json_note": row.note,
                "json_overlap_note": str(note_overlap).lower(),
                "time_overlap": "false",
                "max_time_overlap_sec": "0.000000",
                "boundary_abut_prev": "false",
                "boundary_abut_next": "false",
                "prev_gap_sec": "",
                "next_gap_sec": "",
                "reason_codes": "|".join(reason_codes),
                "evidence_class": "confirmed_source_time_invalid",
                "recommended_scope": "exclude_alignment_and_acoustic_analysis",
                "researcher_decision": "pending",
            }
        )

    flagged.sort(
        key=lambda item: (
            float(item["start_sec"]),
            float(item["end_sec"]),
            str(item["utt_id"]),
        )
    )

    confirmed_union = note_overlap_ids | time_overlap_ids
    count = len(rows)
    session_priority = "routine"
    if count and len(confirmed_union) / count >= 0.25:
        session_priority = "high_overlap_session_review"
    elif confirmed_union:
        session_priority = "utterance_overlap_review"
    elif invalid_rows:
        session_priority = "source_time_invalid_review"
    summary = {
        "year": rows[0].year,
        "session_id": rows[0].session_id,
        "utterance_count": count,
        "source_time_invalid_count": len(invalid_rows),
        "json_overlap_note_count": len(note_overlap_ids),
        "time_overlap_member_count": len(time_overlap_ids),
        "confirmed_overlap_union_count": len(confirmed_union),
        "confirmed_overlap_union_pct": f"{100 * len(confirmed_union) / count:.6f}",
        "boundary_abut_member_count": len(abut_ids),
        "boundary_abut_member_pct": f"{100 * len(abut_ids) / count:.6f}",
        "nonempty_note_count": nonempty_notes,
        "min_gap_sec": f"{min(adjacency_gaps):.6f}" if adjacency_gaps else "",
        "median_gap_sec": f"{_median(adjacency_gaps):.6f}" if adjacency_gaps else "",
        "max_gap_sec": f"{max(adjacency_gaps):.6f}" if adjacency_gaps else "",
        "session_review_priority": session_priority,
        "researcher_decision": "pending",
    }
    return flagged, summary


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
        try:
            if self.text is not None:
                self.text.flush()
                self.text.close()
            elif self.compressed is not None:
                self.compressed.close()
            if self.raw is not None and not self.raw.closed:
                self.raw.close()
            if exc_type is None:
                os.replace(self.temp, self.destination)
        finally:
            if exc_type is not None and self.temp.exists():
                # Keep partial evidence for diagnosis; never promote it.
                pass


def _json_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.json"), key=lambda path: path.as_posix())
    if not files:
        raise RuntimeError(f"zero JSON files: {root}")
    return files


def run_audit(
    *,
    year: str,
    json_root: Path,
    output_root: Path,
    overlap_tolerance: float = 0.001,
    abut_tolerance: float = 0.020,
) -> dict[str, object]:
    if year not in YEARS:
        raise ValueError(f"unsupported year: {year}")
    json_root = json_root.resolve()
    output_root = output_root.resolve()
    if not json_root.is_dir():
        raise FileNotFoundError(json_root)
    if output_root.exists():
        raise FileExistsError(f"existing output protected: {output_root}")
    output_root.mkdir(parents=True)

    flag_path = output_root / "01_UTTERANCE_STRUCTURAL_FLAGS.csv.gz"
    session_path = output_root / "02_SESSION_SUMMARY.csv.gz"
    manifest_path = output_root / "MANIFEST.json"
    files = _json_files(json_root)
    source_digest = hashlib.sha256()
    totals = Counter()
    examples: dict[str, list[str]] = {}
    seen_session_ids: set[str] = set()

    with DeterministicGzipCsv(flag_path, FLAG_FIELDS) as flag_writer, \
            DeterministicGzipCsv(session_path, SESSION_FIELDS) as session_writer:
        for index, source in enumerate(files, start=1):
            raw = source.read_bytes()
            relative = source.relative_to(json_root).as_posix()
            content_sha = hashlib.sha256(raw).hexdigest()
            source_digest.update(relative.encode("utf-8"))
            source_digest.update(b"\0")
            source_digest.update(content_sha.encode("ascii"))
            source_digest.update(b"\n")
            rows = parse_json_bytes(year=year, source=source, raw=raw)
            session_id = rows[0].session_id
            if session_id in seen_session_ids:
                raise RuntimeError(f"duplicate session id across JSON: {session_id}")
            seen_session_ids.add(session_id)
            flagged, session = classify_session(
                rows,
                overlap_tolerance=overlap_tolerance,
                abut_tolerance=abut_tolerance,
            )
            session["source_json"] = relative
            session_writer.writerow(session)
            totals["json_files"] += 1
            totals["sessions"] += 1
            totals["utterances"] += len(rows)
            totals["flagged_rows"] += len(flagged)
            totals["source_time_invalid"] += int(session["source_time_invalid_count"])
            totals["json_overlap_note"] += int(session["json_overlap_note_count"])
            totals["time_overlap_members"] += int(session["time_overlap_member_count"])
            totals["confirmed_overlap_union"] += int(session["confirmed_overlap_union_count"])
            totals["boundary_abut_members"] += int(session["boundary_abut_member_count"])
            if session["session_review_priority"] == "high_overlap_session_review":
                totals["high_overlap_sessions"] += 1
            for row in flagged:
                flag_writer.writerow(row)
                for code in str(row["reason_codes"]).split("|"):
                    totals[f"reason_{code}"] += 1
                    bucket = examples.setdefault(code, [])
                    if len(bucket) < 20:
                        bucket.append(str(row["utt_id"]))
            if index % 500 == 0 or index == len(files):
                print(
                    f"[{year}] {index:,}/{len(files):,} JSON · "
                    f"{totals['utterances']:,} utterances · "
                    f"{totals['confirmed_overlap_union']:,} overlap",
                    flush=True,
                )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_policy_review",
        "created_at": now_iso(),
        "year": year,
        "policy": {
            "overlap_tolerance_seconds": overlap_tolerance,
            "boundary_abut_tolerance_seconds": abut_tolerance,
            "confirmed_overlap": (
                "source JSON note contains 발화겹침 OR source time spans overlap"
            ),
            "boundary_abut": (
                "review candidate only; never treated as confirmed clipping "
                "without audio-edge evidence"
            ),
            "automatic_exclusion_performed": False,
            "actual_phonological_realization_judged": False,
            "source_files_modified": False,
        },
        "source": {
            "json_root": str(json_root),
            "json_files": len(files),
            "aggregate_content_identity_sha256": source_digest.hexdigest(),
        },
        "counts": dict(sorted(totals.items())),
        "examples": examples,
        "outputs": {
            "utterance_flags": file_fingerprint(flag_path, with_sha256=True),
            "session_summary": file_fingerprint(session_path, with_sha256=True),
        },
        "next_step": (
            "Join WAV edge/noise evidence and existing MFA/input contracts, then "
            "present exact categories and counts for explicit researcher approval."
        ),
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, choices=YEARS)
    parser.add_argument("--json-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overlap-tolerance", type=float, default=0.001)
    parser.add_argument("--abut-tolerance", type=float, default=0.020)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.overlap_tolerance < 0 or args.abut_tolerance < 0:
        raise ValueError("tolerances must be non-negative")
    run_audit(
        year=args.year,
        json_root=args.json_root,
        output_root=args.output_root,
        overlap_tolerance=args.overlap_tolerance,
        abut_tolerance=args.abut_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Backfill a seventh pronunciation-reference tier without changing 6-tier sources.

Work is checkpointed by session.  A failed or interrupted session is rebuilt in
its own derived staging directory; completed sessions are never regenerated.
MFA databases, WAV, LAB, source CSV, and existing 6-tier TextGrids are read-only.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import sys
import time
import uuid
from collections import Counter
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dictionary_pronunciation_registry import (  # noqa: E402
    atomic_gzip_text_writer,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
import research_textgrid_v2 as textgrid_v2  # noqa: E402


SCHEMA_VERSION = "pron_reference_textgrid_backfill.v1"
OUTPUT_TEXTGRID_SCHEMA_VERSION = "research_textgrid_pron_reference.v1"
TIER_NAME = "pron_reference_utt"
ALIGNMENT_REQUIRED = {
    "utt_id",
    "year",
    "session_id",
    "textgrid_relative_path",
}
INDEX_REQUIRED = {
    "utt_id",
    "year",
    "session_id",
    "pron_reference_utt_label",
    "textgrid_label_schema_version",
}
SESSION_TABLE_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "source_textgrid_relative_path",
    "output_textgrid_relative_path",
    "pron_reference_utt_label",
    "textgrid_label_schema_version",
    "source_textgrid_schema_version",
    "output_textgrid_schema_version",
    "first_six_tiers_semantically_unchanged",
    "pron_reference_utt_boundary_matches_utterance",
]

csv.field_size_limit(20_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def natural_key(value: str):
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", value)
        if part != ""
    )


def contract_id(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def grouped_index_rows(reader: csv.DictReader):
    for session_id, rows in groupby(
        reader, key=lambda row: clean(row.get("session_id"))
    ):
        if not session_id:
            raise RuntimeError("blank utterance-index session_id")
        lookup: dict[str, dict[str, str]] = {}
        for row in rows:
            utt_id = clean(row.get("utt_id"))
            if not utt_id or utt_id in lookup:
                raise RuntimeError(
                    f"blank/duplicate utterance-index key: {session_id}/{utt_id}"
                )
            lookup[utt_id] = row
        yield session_id, lookup


class SessionIndexCursor:
    """Join an index by session, independent of utterance ordering within it.

    The six-tier alignment table is lexically sorted by utterance ID, whereas
    the pronunciation index follows numeric utterance order.  Index rows also
    contain MFA-excluded utterances.  Loading one session at a time keeps the
    join bounded without requiring either source to be regenerated or sorted.
    """

    def __init__(self, reader: csv.DictReader):
        self.reader = iter(grouped_index_rows(reader))
        self.current = next(self.reader, None)

    def take(self, session_id: str) -> dict[str, dict[str, str]]:
        target = natural_key(session_id)
        while self.current is not None and natural_key(self.current[0]) < target:
            self.current = next(self.reader, None)
        if self.current is None or self.current[0] != session_id:
            observed = None if self.current is None else self.current[0]
            raise RuntimeError(
                "alignment/index session coverage mismatch: "
                f"expected={session_id}, observed={observed}"
            )
        _observed_session, result = self.current
        self.current = next(self.reader, None)
        return result


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("status") != "success":
        raise RuntimeError(f"successful manifest required: {path}")
    return payload


def validate_source_and_output(
    *, source_path: Path, output_path: Path, label: str
) -> tuple[float, dict[str, list[tuple]], dict[str, list[tuple]]]:
    source_duration, source_tiers = parse_mfa_textgrid(source_path)
    if source_duration is None or list(source_tiers) != textgrid_v2.BASE_TIERS:
        raise RuntimeError(
            f"source 6-tier contract mismatch: {source_path} {list(source_tiers)}"
        )
    for name in textgrid_v2.BASE_TIERS:
        if not textgrid_v2._continuous(source_tiers[name], source_duration):
            raise RuntimeError(f"source tier not continuous: {source_path}/{name}")
    output_duration, output_tiers = parse_mfa_textgrid(output_path)
    expected_names = textgrid_v2.BASE_TIERS + [TIER_NAME]
    if output_duration is None or abs(output_duration - source_duration) > 1e-6:
        raise RuntimeError(f"output duration mismatch: {output_path}")
    if list(output_tiers) != expected_names:
        raise RuntimeError(f"output tier order mismatch: {output_path}")
    for name in textgrid_v2.BASE_TIERS:
        if not textgrid_v2._same_intervals(
            source_tiers[name], output_tiers[name]
        ):
            raise RuntimeError(f"source tier changed during backfill: {name}")
    if not textgrid_v2._same_edges(
        output_tiers["utterance"], output_tiers[TIER_NAME]
    ):
        raise RuntimeError("pron_reference_utt boundary differs from utterance")
    labeled = [row for row in output_tiers[TIER_NAME] if clean(row[2])]
    if len(labeled) != 1 or clean(labeled[0][2]) != label:
        raise RuntimeError("pron_reference_utt label mismatch")
    if not textgrid_v2._continuous(output_tiers[TIER_NAME], output_duration):
        raise RuntimeError("pron_reference_utt not continuous 0-xmax")
    return source_duration, source_tiers, output_tiers


def write_one(
    *,
    source_path: Path,
    destination: Path,
    label: str,
) -> None:
    duration, tiers = parse_mfa_textgrid(source_path)
    if duration is None or list(tiers) != textgrid_v2.BASE_TIERS:
        raise RuntimeError(f"source 6-tier contract mismatch: {source_path}")
    pron_tier = textgrid_v2._relabel_utterance_tier(
        tiers["utterance"], label, TIER_NAME
    )
    tier_data = [(name, list(tiers[name])) for name in textgrid_v2.BASE_TIERS]
    tier_data.append((TIER_NAME, pron_tier))
    textgrid_v2.write_textgrid_exact(
        destination, duration=float(duration), tier_data=tier_data
    )
    validate_source_and_output(
        source_path=source_path, output_path=destination, label=label
    )


def session_rows(reader: csv.DictReader):
    for session_id, rows in groupby(
        reader, key=lambda row: clean(row.get("session_id"))
    ):
        if not session_id:
            raise RuntimeError("blank alignment session_id")
        yield session_id, list(rows)


def _session_checkpoint_valid(
    path: Path, *, expected_contract_id: str, final_dir: Path
) -> bool:
    if not path.is_file() or not final_dir.is_dir():
        return False
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return False
    if (
        payload.get("status") != "success"
        or payload.get("backfill_contract_id") != expected_contract_id
    ):
        return False
    expected = int(payload.get("counts", {}).get("textgrids", -1))
    observed = sum(1 for _ in final_dir.glob("*.TextGrid"))
    return expected >= 0 and observed == expected


def build(args: argparse.Namespace) -> dict:
    year = str(args.year)
    source_root = args.source_textgrid_root.resolve()
    alignment_path = args.utterance_alignment.resolve()
    tables_manifest_path = args.tables_manifest.resolve()
    index_path = args.utterance_index.resolve()
    index_manifest_path = args.utterance_index_manifest.resolve()
    output_root = args.output_root.resolve()
    year_root = output_root / year
    checkpoint_root = year_root / "_checkpoints"
    staging_root = year_root / "_session_staging"
    tables_root = year_root / "_tables"

    tables_manifest = load_manifest(tables_manifest_path)
    index_manifest = load_manifest(index_manifest_path)
    if str(tables_manifest.get("year")) != year or str(index_manifest.get("year")) != year:
        raise RuntimeError("input manifest year mismatch")
    alignment_fp = file_fingerprint(alignment_path, with_sha256=True)
    index_fp = file_fingerprint(index_path, with_sha256=True)
    if alignment_fp["sha256"] != tables_manifest["tables"]["utterances"]["sha256"]:
        raise RuntimeError("utterance alignment SHA mismatch")
    if index_fp["sha256"] != index_manifest["outputs"]["index"]["sha256"]:
        raise RuntimeError("utterance index SHA mismatch")
    contract_payload = {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "source_textgrid_schema_version": tables_manifest[
            "textgrid_schema_version"
        ],
        "output_textgrid_schema_version": OUTPUT_TEXTGRID_SCHEMA_VERSION,
        "source_tiers": textgrid_v2.BASE_TIERS,
        "added_tier": TIER_NAME,
        "utterance_alignment_sha256": alignment_fp["sha256"],
        "utterance_index_sha256": index_fp["sha256"],
        "label_schema_version": index_manifest[
            "textgrid_label_schema_version"
        ],
    }
    backfill_contract_id = contract_id(contract_payload)
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "year": year,
        "backfill_contract_id": backfill_contract_id,
        "mutation_scope": "new derived output root only; source 6-tier/DB/WAV/LAB/CSV unchanged",
        "inputs": {
            "source_textgrid_root": str(source_root),
            "utterance_alignment": alignment_fp,
            "tables_manifest": file_fingerprint(
                tables_manifest_path, with_sha256=True
            ),
            "utterance_index": index_fp,
            "utterance_index_manifest": file_fingerprint(
                index_manifest_path, with_sha256=True
            ),
        },
        "output_root": str(output_root),
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    year_root.mkdir(parents=True, exist_ok=True)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    staging_root.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    run_counts: Counter = Counter()
    session_checkpoint_paths: list[Path] = []
    with gzip.open(
        alignment_path, "rt", encoding="utf-8-sig", newline=""
    ) as alignment_stream, gzip.open(
        index_path, "rt", encoding="utf-8-sig", newline=""
    ) as index_stream:
        alignment_reader = csv.DictReader(alignment_stream)
        index_reader = csv.DictReader(index_stream)
        for label, reader, required in (
            ("alignment", alignment_reader, ALIGNMENT_REQUIRED),
            ("utterance index", index_reader, INDEX_REQUIRED),
        ):
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(f"{label} fields missing: {sorted(missing)}")
        index_cursor = SessionIndexCursor(index_reader)
        for session_number, (session_id, alignments) in enumerate(
            session_rows(alignment_reader), 1
        ):
            # A bounded pilot is a stable prefix of the annual session set.
            # It must not expand by another N sessions every time it resumes.
            if args.max_sessions is not None and session_number > args.max_sessions:
                break
            if any(clean(row.get("year")) != year for row in alignments):
                raise RuntimeError(f"alignment year mismatch: {session_id}")
            index_lookup = index_cursor.take(session_id)
            index_rows = []
            for row in alignments:
                utt_id = clean(row["utt_id"])
                index_row = index_lookup.get(utt_id)
                if index_row is None:
                    raise RuntimeError(
                        f"alignment/index utterance coverage mismatch: {utt_id}"
                    )
                index_rows.append(index_row)
            run_counts["index_rows_not_in_alignment"] += (
                len(index_lookup) - len(index_rows)
            )
            checkpoint = checkpoint_root / f"{session_id}.json"
            final_dir = year_root / session_id
            if _session_checkpoint_valid(
                checkpoint,
                expected_contract_id=backfill_contract_id,
                final_dir=final_dir,
            ):
                run_counts["sessions_skipped_checkpoint"] += 1
                run_counts["textgrids_skipped_checkpoint"] += len(alignments)
                session_checkpoint_paths.append(checkpoint)
                continue
            if final_dir.exists():
                raise RuntimeError(
                    f"session output exists without valid checkpoint: {final_dir}"
                )
            stale = sorted(staging_root.glob(f"{session_id}.*.partial"))
            for path in stale:
                resolved = path.resolve()
                if resolved.parent != staging_root or not resolved.name.endswith(".partial"):
                    raise RuntimeError(f"unsafe stale staging path: {resolved}")
                shutil.rmtree(resolved)
                run_counts["stale_session_staging_removed"] += 1
            temp_dir = staging_root / f"{session_id}.{uuid.uuid4().hex}.partial"
            temp_dir.mkdir(parents=False)
            session_table = temp_dir / "pron_reference_utterance.csv.gz"
            session_counts: Counter = Counter()
            with atomic_gzip_text_writer(session_table) as table_stream:
                writer = csv.DictWriter(
                    table_stream,
                    fieldnames=SESSION_TABLE_FIELDS,
                    lineterminator="\n",
                )
                writer.writeheader()
                for alignment, index_row in zip(alignments, index_rows):
                    utt_id = clean(alignment["utt_id"])
                    if clean(index_row["session_id"]) != session_id:
                        raise RuntimeError(f"index session mismatch: {utt_id}")
                    if clean(index_row["year"]) != year:
                        raise RuntimeError(f"index year mismatch: {utt_id}")
                    relative = Path(clean(alignment["textgrid_relative_path"]))
                    if relative.is_absolute() or ".." in relative.parts:
                        raise RuntimeError(
                            f"unsafe source TextGrid relative path: {relative}"
                        )
                    if not relative.parts or relative.parts[0] != year:
                        raise RuntimeError(
                            f"source TextGrid year path mismatch: {relative}"
                        )
                    source_path = source_root / relative
                    if not source_path.is_file():
                        raise FileNotFoundError(source_path)
                    destination = temp_dir / f"{utt_id}.TextGrid"
                    label = clean(index_row["pron_reference_utt_label"])
                    if not label:
                        raise RuntimeError(f"empty pron_reference_utt label: {utt_id}")
                    write_one(
                        source_path=source_path,
                        destination=destination,
                        label=label,
                    )
                    output_relative = Path(year) / session_id / destination.name
                    writer.writerow(
                        {
                            "utt_id": utt_id,
                            "year": year,
                            "session_id": session_id,
                            "source_textgrid_relative_path": relative.as_posix(),
                            "output_textgrid_relative_path": output_relative.as_posix(),
                            "pron_reference_utt_label": label,
                            "textgrid_label_schema_version": clean(
                                index_row["textgrid_label_schema_version"]
                            ),
                            "source_textgrid_schema_version": tables_manifest[
                                "textgrid_schema_version"
                            ],
                            "output_textgrid_schema_version": OUTPUT_TEXTGRID_SCHEMA_VERSION,
                            "first_six_tiers_semantically_unchanged": "true",
                            "pron_reference_utt_boundary_matches_utterance": "true",
                        }
                    )
                    session_counts["textgrids"] += 1
            if session_counts["textgrids"] != len(alignments):
                raise RuntimeError(f"session output count mismatch: {session_id}")
            shutil.move(str(temp_dir), str(final_dir))
            checkpoint_payload = {
                "schema_version": SCHEMA_VERSION,
                "status": "success",
                "recorded_at": now_iso(),
                "year": year,
                "session_id": session_id,
                "backfill_contract_id": backfill_contract_id,
                "counts": dict(session_counts),
                "session_table": file_fingerprint(
                    final_dir / session_table.name, with_sha256=True
                ),
            }
            atomic_write_json(checkpoint, checkpoint_payload)
            session_checkpoint_paths.append(checkpoint)
            run_counts["sessions_created"] += 1
            run_counts["textgrids_created"] += session_counts["textgrids"]
            print(
                f"[{year}] pron tier session {session_number}: "
                f"{session_id} ({session_counts['textgrids']:,})",
                flush=True,
            )
    full_scope = args.max_sessions is None
    if full_scope:
        expected_sessions = len(session_checkpoint_paths)
        tables_root.mkdir(parents=True, exist_ok=True)
        annual_table = tables_root / "pron_reference_utterance.csv.gz"
        if annual_table.exists():
            raise FileExistsError(annual_table)
        annual_rows = 0
        with atomic_gzip_text_writer(annual_table) as destination:
            writer = csv.DictWriter(
                destination,
                fieldnames=SESSION_TABLE_FIELDS,
                lineterminator="\n",
            )
            writer.writeheader()
            for checkpoint in sorted(session_checkpoint_paths):
                session_id = checkpoint.stem
                session_table = year_root / session_id / "pron_reference_utterance.csv.gz"
                with gzip.open(
                    session_table, "rt", encoding="utf-8-sig", newline=""
                ) as stream:
                    for row in csv.DictReader(stream):
                        writer.writerow(row)
                        annual_rows += 1
        expected_rows = int(tables_manifest["counts"]["utterances"])
        if annual_rows != expected_rows:
            raise RuntimeError(
                f"annual companion coverage mismatch: {annual_rows} != {expected_rows}"
            )
        annual_manifest = {
            **preflight,
            "status": "success",
            "recorded_at": now_iso(),
            "counts": {
                **dict(run_counts),
                "sessions_total": expected_sessions,
                "textgrids_total": annual_rows,
            },
            "outputs": {
                "annual_companion": file_fingerprint(
                    annual_table, with_sha256=True
                )
            },
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
        }
        atomic_write_json(
            tables_root / "PRON_REFERENCE_BACKFILL_MANIFEST.json",
            annual_manifest,
        )
        print(
            f"[OK] {year} pron_reference_utt backfill: "
            f"{annual_rows:,} TextGrids",
            flush=True,
        )
        return annual_manifest

    run_report = {
        **preflight,
        "status": "bounded_pilot_success",
        "recorded_at": now_iso(),
        "counts": dict(run_counts),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(year_root / "PILOT_RUN_MANIFEST.json", run_report)
    return run_report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--source-textgrid-root", type=Path, required=True)
    result.add_argument("--utterance-alignment", type=Path, required=True)
    result.add_argument("--tables-manifest", type=Path, required=True)
    result.add_argument("--utterance-index", type=Path, required=True)
    result.add_argument("--utterance-index-manifest", type=Path, required=True)
    result.add_argument("--output-root", type=Path, required=True)
    result.add_argument("--max-sessions", type=int)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.max_sessions is not None and args.max_sessions <= 0:
        raise ValueError("--max-sessions must be positive")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stage a small, immutable WAV bundle for common-pronunciation review.

The source corpus is read only.  Each unique utterance is copied under the
release review directory, verified by SHA-256, and joined back to every target
occurrence.  Existing destination WAVs are reused only when they are
byte-identical to the source.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_researcher_review_bundle.v1"
YEARS = {str(year) for year in range(2020, 2026)}
OUTPUT_FIELDS = (
    "review_order",
    "source_kind",
    "target_token",
    "year",
    "utt_id",
    "session_id",
    "dialogue_id",
    "speaker_id",
    "form",
    "original_form",
    "pron_reference_hangul",
    "pron_reference_source",
    "pron_reference_status",
    "raw_json_match_status",
    "original_wav",
    "review_wav",
    "wav_bytes",
    "wav_sha256",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(
            f"review bundle path boundary violation: {resolved}"
        ) from exc
    return resolved


def read_occurrences(path: Path, source_kind: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "target_token",
            "year",
            "utt_id",
            "session_id",
            "dialogue_id",
            "speaker_id",
            "form",
            "original_form",
            "pron_reference_hangul",
            "pron_reference_source",
            "pron_reference_status",
            "raw_json_match_status",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"occurrence CSV required columns missing: "
                f"{sorted(missing)} ({path})"
            )
        rows = []
        for raw in reader:
            row = {key: clean(value) for key, value in raw.items()}
            row["source_kind"] = source_kind
            if (
                row["year"] not in YEARS
                or not row["target_token"]
                or not row["utt_id"]
                or not row["session_id"]
                or row["raw_json_match_status"] != "exact"
            ):
                raise RuntimeError(
                    "occurrence row is not usable for review: "
                    f"{source_kind} {row.get('target_token')} "
                    f"{row.get('utt_id')}"
                )
            rows.append(row)
    if not rows:
        raise RuntimeError(f"occurrence CSV is empty: {path}")
    return rows


def source_wav(
    *,
    wav_root: Path,
    year: str,
    session_id: str,
    utt_id: str,
) -> Path:
    path = (
        wav_root
        / year
        / session_id
        / f"{utt_id}.wav"
    ).resolve()
    try:
        path.relative_to(wav_root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"WAV path boundary violation: {path}") from exc
    if not path.is_file() or path.stat().st_size < 44:
        raise RuntimeError(f"source WAV missing or invalid: {path}")
    return path


def copy_verified(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_record = file_fingerprint(source, with_sha256=True)
    if destination.exists():
        destination_record = file_fingerprint(
            destination, with_sha256=True
        )
        if (
            destination_record["bytes"] != source_record["bytes"]
            or destination_record["sha256"] != source_record["sha256"]
        ):
            raise RuntimeError(
                f"existing review WAV differs from source: {destination}"
            )
        return destination_record
    partial = destination.with_name(
        f"{destination.name}.{os.getpid()}.partial"
    )
    if partial.exists():
        raise RuntimeError(f"stale review WAV partial exists: {partial}")
    try:
        shutil.copy2(source, partial)
        partial_record = file_fingerprint(partial, with_sha256=True)
        if (
            partial_record["bytes"] != source_record["bytes"]
            or partial_record["sha256"] != source_record["sha256"]
        ):
            raise RuntimeError(
                f"copied review WAV hash mismatch: {destination}"
            )
        os.replace(partial, destination)
    finally:
        if partial.exists():
            partial.unlink()
    return file_fingerprint(destination, with_sha256=True)


def stage_bundle(
    *,
    no_path_occurrences: Path,
    jamo_occurrences: Path,
    wav_root: Path,
    release_root: Path,
    output_root: Path,
) -> dict:
    release_root = release_root.resolve()
    output_root = ensure_within(output_root, release_root)
    occurrence_csv = output_root / "review_occurrences.csv"
    manifest_path = output_root / "manifest.json"
    if occurrence_csv.exists() or manifest_path.exists():
        raise FileExistsError(
            f"review bundle output already exists: {output_root}"
        )

    rows = [
        *read_occurrences(no_path_occurrences, "no_path"),
        *read_occurrences(jamo_occurrences, "jamo_ls"),
    ]
    rows.sort(
        key=lambda row: (
            row["source_kind"],
            row["target_token"],
            row["year"],
            row["utt_id"],
        )
    )
    staged_by_utt: dict[tuple[str, str, str], dict] = {}
    output_rows: list[dict[str, object]] = []
    for order, row in enumerate(rows, start=1):
        key = (row["year"], row["session_id"], row["utt_id"])
        source = source_wav(
            wav_root=wav_root,
            year=row["year"],
            session_id=row["session_id"],
            utt_id=row["utt_id"],
        )
        destination = (
            output_root
            / "wav"
            / row["year"]
            / row["session_id"]
            / source.name
        )
        if key not in staged_by_utt:
            record = copy_verified(source, destination)
            staged_by_utt[key] = {
                "source": file_fingerprint(source, with_sha256=True),
                "review_copy": record,
            }
        record = staged_by_utt[key]["review_copy"]
        output_rows.append(
            {
                "review_order": order,
                "source_kind": row["source_kind"],
                "target_token": row["target_token"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "session_id": row["session_id"],
                "dialogue_id": row["dialogue_id"],
                "speaker_id": row["speaker_id"],
                "form": row["form"],
                "original_form": row["original_form"],
                "pron_reference_hangul": row[
                    "pron_reference_hangul"
                ],
                "pron_reference_source": row[
                    "pron_reference_source"
                ],
                "pron_reference_status": row[
                    "pron_reference_status"
                ],
                "raw_json_match_status": row[
                    "raw_json_match_status"
                ],
                "original_wav": str(source),
                "review_wav": str(destination.resolve()),
                "wav_bytes": int(record["bytes"]),
                "wav_sha256": record["sha256"],
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(
        occurrence_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "kind": "common_pron_researcher_review_wav_bundle",
        "recorded_at": now_iso(),
        "counts": {
            "target_occurrences": len(output_rows),
            "unique_wavs": len(staged_by_utt),
            "source_mismatch_rows": 0,
            "missing_or_invalid_wavs": 0,
        },
        "inputs": {
            "no_path_occurrences": file_fingerprint(
                no_path_occurrences, with_sha256=True
            ),
            "jamo_occurrences": file_fingerprint(
                jamo_occurrences, with_sha256=True
            ),
            "wav_root": str(wav_root.resolve()),
        },
        "outputs": {
            "occurrences": file_fingerprint(
                occurrence_csv, with_sha256=True
            ),
            "wav_files": [
                {
                    "year": key[0],
                    "session_id": key[1],
                    "utt_id": key[2],
                    "source": records["source"],
                    "review_copy": records["review_copy"],
                }
                for key, records in sorted(staged_by_utt.items())
            ],
        },
        "gates": {
            "all_source_wavs_found": True,
            "all_review_copies_hash_equal_source": all(
                records["source"]["bytes"]
                == records["review_copy"]["bytes"]
                and records["source"]["sha256"]
                == records["review_copy"]["sha256"]
                for records in staged_by_utt.values()
            ),
            "source_corpus_modified": False,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "공통발음 r2 예외 발화 WAV를 원본 해시와 함께 검토 폴더에 복사"
        )
    )
    parser.add_argument("--no-path-occurrences", type=Path, required=True)
    parser.add_argument("--jamo-occurrences", type=Path, required=True)
    parser.add_argument("--wav-root", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = stage_bundle(
        no_path_occurrences=args.no_path_occurrences.resolve(),
        jamo_occurrences=args.jamo_occurrences.resolve(),
        wav_root=args.wav_root.resolve(),
        release_root=args.release_root.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

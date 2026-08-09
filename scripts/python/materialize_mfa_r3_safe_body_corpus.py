"""Materialize a release-scoped MFA corpus from an exact r3 input list.

WAV files are hard-linked on the same D: volume and never modified.  LAB files
are created only inside the r3 release namespace.  A contract-bound building
marker permits interruption-safe resume without deleting completed work.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file
from realign_eojeol_build_corpus import form_to_lab, normalized_lab_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_r3_safe_body_corpus.v1"
STATUS = "passed_release_scoped_hardlink_corpus"
EXPECTED_FIELDS = ("year", "utt_id", "session_id", "source_csv")


def clean(value: object) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify(record: dict, path: Path, label: str) -> None:
    if (
        Path(clean(record.get("path"))).resolve() != path.resolve()
        or not path.is_file()
        or int(record.get("bytes", -1)) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def expected_groups(path: Path, year: str):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EXPECTED_FIELDS:
            raise RuntimeError("expected MFA input exact-ID fields differ")
        seen_sources: set[str] = set()
        for source_csv, rows in groupby(reader, key=lambda row: clean(row["source_csv"])):
            if not source_csv or source_csv in seen_sources:
                raise RuntimeError("expected input source_csv ordering/identity differs")
            seen_sources.add(source_csv)
            group = list(rows)
            if any(clean(row["year"]) != year for row in group):
                raise RuntimeError(f"expected input wrong-year row: {source_csv}")
            yield source_csv, group


def verify_completed(manifest: dict, alignment_id: str, output_root: Path) -> dict:
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != STATUS
        or clean(manifest.get("alignment_contract_id")) != alignment_id
        or Path(clean(manifest.get("output_corpus_year"))).resolve()
        != output_root.resolve()
    ):
        raise RuntimeError("existing r3 corpus manifest identity differs")
    expected = int(manifest["counts"]["expected_mfa_input"])
    wav_count = sum(1 for _ in output_root.rglob("*.wav"))
    lab_count = sum(1 for _ in output_root.rglob("*.lab"))
    if wav_count != expected or lab_count != expected:
        raise RuntimeError("existing r3 corpus physical count differs")
    return manifest


def materialize(
    *,
    year: str,
    alignment_contract_path: Path,
    output_root: Path,
    state_root: Path,
) -> dict:
    alignment = load_json(alignment_contract_path)
    if (
        alignment.get("schema_version") != "mfa_r3_alignment_contract.v1"
        or alignment.get("status")
        != "materialized_pending_runner_preflight_and_release_gate"
        or clean(alignment.get("year")) != year
        or alignment.get("r3_full_realign") is not True
    ):
        raise RuntimeError("r3 alignment contract identity differs")
    alignment_id = clean(alignment["alignment_contract_id"])
    year_contract_path = Path(
        clean(alignment["inputs"]["year_input_contract"]["path"])
    ).resolve()
    verify(
        alignment["inputs"]["year_input_contract"],
        year_contract_path,
        "year input contract",
    )
    year_contract = load_json(year_contract_path)
    expected_path = Path(
        clean(year_contract["outputs"]["expected_mfa_input_ids"]["path"])
    ).resolve()
    verify(
        year_contract["outputs"]["expected_mfa_input_ids"],
        expected_path,
        "expected MFA input IDs",
    )
    expected_count = int(year_contract["accounting"]["expected_mfa_input"])
    search_root = Path(
        clean(year_contract["inputs"]["frozen_search_master_inventory"]["root"])
    ).resolve()
    recovered_root = Path(
        clean(year_contract["corpus_binding"]["recovered_wav_root"])
    ).resolve()
    if not search_root.is_dir() or not recovered_root.is_dir():
        raise RuntimeError("search master or recovered WAV root missing")

    state_root.mkdir(parents=True, exist_ok=True)
    final_manifest_path = state_root / f"CORPUS_MATERIALIZATION_{year}.json"
    building_path = state_root / f"CORPUS_MATERIALIZATION_{year}.building.json"
    if final_manifest_path.is_file():
        return verify_completed(
            load_json(final_manifest_path), alignment_id, output_root
        )
    building_identity = {
        "schema_version": "mfa_r3_safe_body_corpus_building.v1",
        "status": "building_resume_allowed",
        "year": year,
        "alignment_contract_id": alignment_id,
        "expected_mfa_input_sha256": year_contract["outputs"][
            "expected_mfa_input_ids"
        ]["sha256"],
        "output_corpus_year": str(output_root.resolve()),
        "source_wav_tree_modified": False,
    }
    if output_root.exists():
        if not building_path.is_file():
            raise RuntimeError("existing corpus root has no matching building contract")
        if load_json(building_path) != building_identity:
            raise RuntimeError("existing corpus building contract differs")
    else:
        output_root.mkdir(parents=True, exist_ok=False)
        atomic_write_json(building_path, building_identity)

    seen_ids: set[str] = set()
    linked = existing_links = created_labs = existing_labs = 0
    source_groups = 0
    for source_groups, (source_csv, expected_rows) in enumerate(
        expected_groups(expected_path, year), 1
    ):
        source_path = (search_root / Path(source_csv)).resolve()
        try:
            source_path.relative_to(search_root)
        except ValueError as exc:
            raise RuntimeError(f"source_csv escaped frozen search root: {source_csv}") from exc
        if not source_path.is_file():
            raise RuntimeError(f"frozen search CSV missing: {source_path}")
        expected_ids = {clean(row["utt_id"]) for row in expected_rows}
        if len(expected_ids) != len(expected_rows) or seen_ids & expected_ids:
            raise RuntimeError(f"duplicate expected utterance ID: {source_csv}")
        seen_ids.update(expected_ids)
        with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
            source_rows = {
                clean(row["utt_id"]): row
                for row in csv.DictReader(stream)
                if clean(row.get("utt_id")) in expected_ids
            }
        if set(source_rows) != expected_ids:
            raise RuntimeError(f"expected IDs missing from frozen search CSV: {source_csv}")
        for expected_row in expected_rows:
            utt_id = clean(expected_row["utt_id"])
            session = clean(expected_row["session_id"])
            source_row = source_rows[utt_id]
            if not session or clean(source_row.get("session_id")) != session:
                raise RuntimeError(f"session identity differs: {utt_id}")
            lab_text = form_to_lab(clean(source_row.get("pron_reference_form")))
            if not lab_text:
                raise RuntimeError(f"eligible r3 utterance has empty LAB text: {utt_id}")
            source_wav = recovered_root / session / f"{utt_id}.wav"
            if not source_wav.is_file():
                raise RuntimeError(f"eligible r3 source WAV missing: {source_wav}")
            target_dir = output_root / session
            target_dir.mkdir(parents=True, exist_ok=True)
            target_wav = target_dir / f"{utt_id}.wav"
            target_lab = target_dir / f"{utt_id}.lab"
            if target_wav.exists():
                if not os.path.samefile(source_wav, target_wav):
                    raise RuntimeError(f"existing r3 WAV is not source hardlink: {utt_id}")
                existing_links += 1
            else:
                os.link(source_wav, target_wav)
                if not os.path.samefile(source_wav, target_wav):
                    raise RuntimeError(f"new r3 WAV hardlink verification failed: {utt_id}")
                linked += 1
            if target_lab.exists():
                existing = normalized_lab_text(
                    target_lab.read_text(encoding="utf-8-sig")
                )
                if existing != normalized_lab_text(lab_text):
                    raise RuntimeError(f"existing r3 LAB content differs: {utt_id}")
                existing_labs += 1
            else:
                with atomic_text_writer(
                    target_lab, encoding="utf-8", newline="\n"
                ) as (stream, _):
                    stream.write(lab_text)
                created_labs += 1
        if source_groups % 250 == 0:
            print(
                f"[{year}] corpus {source_groups:,} source CSV; "
                f"{len(seen_ids):,}/{expected_count:,} utterances",
                flush=True,
            )

    if len(seen_ids) != expected_count:
        raise RuntimeError("materialized corpus expected-ID count differs")
    wav_ids = {path.stem for path in output_root.rglob("*.wav")}
    lab_ids = {path.stem for path in output_root.rglob("*.lab")}
    if wav_ids != seen_ids or lab_ids != seen_ids:
        raise RuntimeError("materialized corpus physical exact-ID inventory differs")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "year": year,
        "alignment_contract_id": alignment_id,
        "pronunciation_release_id": alignment["identity"][
            "pronunciation_release_id"
        ],
        "year_input_contract_id": year_contract["year_input_contract_id"],
        "output_corpus_year": str(output_root.resolve()),
        "counts": {
            "expected_mfa_input": expected_count,
            "source_csv_groups": source_groups,
            "wav_hardlinks_created": linked,
            "wav_hardlinks_reused": existing_links,
            "lab_created": created_labs,
            "lab_reused": existing_labs,
            "physical_wav": len(wav_ids),
            "physical_lab": len(lab_ids),
        },
        "safety": {
            "wav_materialization": "same-volume hardlink",
            "source_wav_tree_modified": False,
            "source_search_master_modified": False,
            "legacy_corpus_modified": False,
            "resume_only_when_building_contract_matches": True,
        },
        "inputs": {
            "alignment_contract": file_fingerprint(
                alignment_contract_path, with_sha256=True
            ),
            "year_input_contract": file_fingerprint(
                year_contract_path, with_sha256=True
            ),
            "expected_mfa_input_ids": file_fingerprint(
                expected_path, with_sha256=True
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(final_manifest_path, manifest)
    building_path.unlink()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = materialize(
        year=args.year,
        alignment_contract_path=args.alignment_contract.resolve(),
        output_root=args.output_root.resolve(),
        state_root=args.state_root.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

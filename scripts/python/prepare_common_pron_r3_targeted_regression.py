"""Prepare four frozen 2022 reviewed utterances for r3 targeted regression."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot, sha256_file
from realign_eojeol_build_corpus import form_to_lab


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_targeted_regression_preparation.v1"
FIELDS = (
    "review_id", "year", "session", "utt_id", "target_word", "pron_reference_form",
    "lab_text", "target_candidate_phones", "source_wav", "source_wav_sha256",
    "source_lab", "source_lab_sha256", "source_lab_equal_generated", "corpus_wav",
    "corpus_lab", "prior_r2_textgrid", "prior_issue",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify(record: dict[str, object], path: Path, label: str) -> None:
    if (
        Path(str(record["path"])).resolve() != path.resolve()
        or not path.is_file()
        or int(record["bytes"]) != path.stat().st_size
        or clean(record.get("sha256")).lower() != sha256_file(path).lower()
    ):
        raise RuntimeError(f"fingerprint mismatch: {label}")


def load_dictionary(path: Path, needed: set[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {token: set() for token in needed}
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] in result:
                result[parts[0]].add(" ".join(parts[1:]))
    return result


def build(
    *, config_path: Path, candidate_manifest_path: Path, search_root: Path,
    wav_root: Path, prior_textgrid_root: Path, output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        manifest_path = output_root / "PREPARATION_MANIFEST.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"targeted regression root exists without manifest: {output_root}")
        result = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if result.get("schema_version") != SCHEMA_VERSION or result.get("status") != "passed_ready_to_align":
            raise RuntimeError("existing targeted regression preparation differs")
        return result
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != "common_pron_r3_targeted_regression_2022.v1" or config.get("status") != "frozen_reviewed_samples":
        raise RuntimeError("targeted regression config differs")
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8-sig"))
    if candidate.get("status") != "passed_candidate_only_not_adopted":
        raise RuntimeError("safe-body candidate is not ready")
    dictionary_path = Path(str(candidate["outputs"]["candidate_dictionary_not_adopted"]["path"])).resolve()
    verify(candidate["outputs"]["candidate_dictionary_not_adopted"], dictionary_path, "candidate dictionary")

    source_rows: dict[str, dict[str, str]] = {}
    for spec in config["samples"]:
        utt_id = spec["utt_id"]
        session = utt_id.split(".", 1)[0]
        source_csv = search_root / "2022" / f"{session}.csv"
        with source_csv.open("r", encoding="utf-8-sig", newline="") as stream:
            matches = [row for row in csv.DictReader(stream) if row["utt_id"] == utt_id]
        if len(matches) != 1:
            raise RuntimeError(f"target utterance identity differs: {utt_id}")
        source_rows[utt_id] = matches[0]
    needed = {
        token
        for row in source_rows.values()
        for token in form_to_lab(row["pron_reference_form"]).split()
    }
    dictionary = load_dictionary(dictionary_path, needed)
    missing = sorted(token for token, variants in dictionary.items() if not variants)
    if missing:
        raise RuntimeError(f"targeted regression LAB tokens absent from candidate dictionary: {missing}")

    temp_root = output_root.with_name(f".{output_root.name}.{uuid.uuid4().hex}.partial")
    corpus_root = temp_root / "corpus"
    rows: list[dict[str, object]] = []
    source_fingerprints: list[dict[str, object]] = []
    for spec in config["samples"]:
        utt_id = spec["utt_id"]
        session = utt_id.split(".", 1)[0]
        row = source_rows[utt_id]
        lab_text = form_to_lab(row["pron_reference_form"])
        if spec["target_word"] not in lab_text.split():
            raise RuntimeError(f"target word absent from LAB: {utt_id}")
        if spec["expected_candidate_phones"] not in dictionary[spec["target_word"]]:
            raise RuntimeError(f"target candidate phones differ: {spec['target_word']}")
        source_wav = wav_root / "2022" / session / f"{utt_id}.wav"
        source_lab = wav_root / "2022" / session / f"{utt_id}.lab"
        prior_textgrid = prior_textgrid_root / "2022" / session / f"{utt_id}.TextGrid"
        for required in (source_wav, source_lab, prior_textgrid):
            if not required.is_file():
                raise RuntimeError(f"targeted regression source missing: {required}")
        existing_lab = source_lab.read_text(encoding="utf-8-sig").strip()
        if existing_lab != lab_text:
            raise RuntimeError(f"frozen source LAB differs from pron_reference_form: {utt_id}")
        destination = corpus_root / session
        destination.mkdir(parents=True, exist_ok=True)
        corpus_wav = destination / source_wav.name
        corpus_lab = destination / source_lab.name
        shutil.copy2(source_wav, corpus_wav)
        corpus_lab.write_text(lab_text + "\n", encoding="utf-8", newline="\n")
        source_fingerprints.extend(
            [
                file_fingerprint(source_wav, with_sha256=True),
                file_fingerprint(source_lab, with_sha256=True),
                file_fingerprint(prior_textgrid, with_sha256=True),
            ]
        )
        rows.append(
            {
                "review_id": spec["review_id"], "year": "2022", "session": session,
                "utt_id": utt_id, "target_word": spec["target_word"],
                "pron_reference_form": row["pron_reference_form"], "lab_text": lab_text,
                "target_candidate_phones": spec["expected_candidate_phones"],
                "source_wav": str(source_wav.resolve()), "source_wav_sha256": sha256_file(source_wav),
                "source_lab": str(source_lab.resolve()), "source_lab_sha256": sha256_file(source_lab),
                "source_lab_equal_generated": "true", "corpus_wav": str((output_root / "corpus" / session / source_wav.name).resolve()),
                "corpus_lab": str((output_root / "corpus" / session / source_lab.name).resolve()),
                "prior_r2_textgrid": str(prior_textgrid.resolve()), "prior_issue": spec["prior_issue"],
            }
        )
    inventory_path = temp_root / "targeted_regression_samples.csv"
    with inventory_path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    final_inventory = output_root / inventory_path.name
    inventory_fingerprint = file_fingerprint(inventory_path, with_sha256=True)
    inventory_fingerprint["path"] = str(final_inventory.resolve())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_ready_to_align",
        "recorded_at": now_iso(),
        "scope": {
            **config["invariants"],
            "targeted_review_ids": [spec["review_id"] for spec in config["samples"]],
            "candidate_contract_id": candidate["candidate_contract_id"],
        },
        "inputs": {
            "config": file_fingerprint(config_path, with_sha256=True),
            "candidate_manifest": file_fingerprint(candidate_manifest_path, with_sha256=True),
            "candidate_dictionary_not_adopted": file_fingerprint(dictionary_path, with_sha256=True),
            "search_master_build_meta": file_fingerprint(search_root / "_build_meta.json", with_sha256=True),
            "sources": source_fingerprints,
        },
        "counts": {"samples": len(rows), "sessions": len({row["session"] for row in rows}), "lab_tokens": sum(len(str(row["lab_text"]).split()) for row in rows)},
        "outputs": {"corpus_root": str((output_root / "corpus").resolve()), "sample_inventory": inventory_fingerprint},
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(temp_root / "PREPARATION_MANIFEST.json", manifest)
    os.replace(temp_root, output_root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "common_pron_r3_targeted_regression_2022_v1.json")
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--wav-root", type=Path, required=True)
    parser.add_argument("--prior-textgrid-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        config_path=args.config.resolve(), candidate_manifest_path=args.candidate_manifest.resolve(),
        search_root=args.search_root.resolve(), wav_root=args.wav_root.resolve(),
        prior_textgrid_root=args.prior_textgrid_root.resolve(), output_root=args.output_root.resolve(),
    )
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

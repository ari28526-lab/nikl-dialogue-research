"""Verify resumable 1-best G2P candidate shards for common pronunciation r3.

This phase only produces *candidates*.  A generated pronunciation is accepted
into the canonical r3 inventory later, and only when its broad Roman sequence
matches the independently computed rule target.  Therefore a small number of
FST no-path words is recorded as missing here instead of being silently filled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import (  # noqa: E402
    acoustic_phone_inventory,
    parse_mfa_dictionary_line,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARD_SCHEMA = "common_pron_r3_g2p_candidate_shard.v1"
PHASE_SCHEMA = "common_pron_r3_g2p_candidate_phase.v1"
TARGET_SCHEMA = "common_pron_r3_g2p_targets.v1"
MAX_MISSING_FRACTION = 0.01


def read_input_words(path: Path) -> list[str]:
    words = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not words:
        raise RuntimeError(f"G2P input shard is empty: {path}")
    if len(words) != len(set(words)):
        raise RuntimeError(f"G2P input shard contains duplicate keys: {path}")
    return words


def read_one_best_output(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    generated: dict[str, tuple[str, ...]] = {}
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            word, phones, _ = parse_mfa_dictionary_line(
                line, path=path, line_number=line_number
            )
            if word in generated:
                raise RuntimeError(
                    f"1-best output contains a duplicate word: {word} ({path})"
                )
            generated[word] = phones
    return generated


def verify_shard(
    *,
    input_shard: Path,
    output_shard: Path,
    acoustic_model: Path,
    report: Path,
    max_missing_fraction: float = MAX_MISSING_FRACTION,
) -> dict[str, object]:
    words = read_input_words(input_shard)
    generated = read_one_best_output(output_shard)
    input_set = set(words)
    output_set = set(generated)
    extras = sorted(output_set - input_set)
    missing = sorted(input_set - output_set)
    if extras:
        raise RuntimeError(
            f"G2P output contains {len(extras)} keys outside its input shard"
        )
    missing_fraction = len(missing) / len(words)
    if missing_fraction > max_missing_fraction:
        raise RuntimeError(
            "G2P no-path fraction exceeds the candidate-stage safety limit: "
            f"{len(missing)}/{len(words)} ({missing_fraction:.4%})"
        )
    inventory = acoustic_phone_inventory(acoustic_model)
    unknown = sorted(
        {
            phone
            for phones in generated.values()
            for phone in phones
            if phone not in inventory
        }
    )
    if unknown:
        raise RuntimeError(
            f"G2P output phones are outside the frozen acoustic inventory: {unknown}"
        )
    spn_words = sorted(
        word for word, phones in generated.items() if "spn" in phones
    )
    if spn_words:
        raise RuntimeError(f"G2P candidate output contains spn: {len(spn_words)}")
    result: dict[str, object] = {
        "schema_version": SHARD_SCHEMA,
        "status": "success_candidate_output",
        "recorded_at": now_iso(),
        "candidate_is_final_selection": False,
        "counts": {
            "input_words": len(words),
            "output_words": len(generated),
            "missing_no_path_words": len(missing),
            "extras": 0,
            "duplicate_word_lines": 0,
            "spn_words": 0,
            "phones_outside_acoustic_inventory": 0,
        },
        "missing_no_path_words": missing,
        "inputs": {
            "input_shard": file_fingerprint(input_shard, with_sha256=True),
            "output_shard": file_fingerprint(output_shard, with_sha256=True),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(report, result)
    return result


def verify_existing_report(
    *,
    input_shard: Path,
    output_shard: Path,
    acoustic_model: Path,
    report: Path,
) -> dict[str, object]:
    """Validate a completion report without blessing an interrupted output.

    The runner writes the report only after MFA G2P exits with code zero.  A
    partial dictionary left by a closed console has no valid matching report
    and must be archived and recomputed.
    """
    result = json.loads(report.read_text(encoding="utf-8-sig"))
    if (
        result.get("schema_version") != SHARD_SCHEMA
        or result.get("status") != "success_candidate_output"
        or result.get("candidate_is_final_selection") is not False
    ):
        raise RuntimeError(f"Invalid G2P candidate completion report: {report}")
    expected = {
        "input_shard": input_shard,
        "output_shard": output_shard,
        "acoustic_model": acoustic_model,
    }
    for key, path in expected.items():
        recorded = result["inputs"][key]
        if (
            Path(recorded["path"]).resolve() != path.resolve()
            or int(recorded["bytes"]) != path.stat().st_size
            or recorded["sha256"].lower() != sha256_file(path).lower()
        ):
            raise RuntimeError(
                f"G2P candidate completion report fingerprint mismatch: {key}"
            )
    return result


def verify_target_manifest(path: Path) -> dict[str, object]:
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != TARGET_SCHEMA:
        raise RuntimeError(f"Unexpected G2P target manifest schema: {path}")
    if manifest.get("status") != "prepared":
        raise RuntimeError(f"G2P target manifest is not prepared: {path}")
    for record in manifest["outputs"]["input_shards"]:
        shard = Path(record["path"])
        if sha256_file(shard) != record["sha256"]:
            raise RuntimeError(f"G2P target shard fingerprint mismatch: {shard}")
    return manifest


def finalize_phase(
    *,
    target_manifest_path: Path,
    output_root: Path,
    acoustic_model: Path,
    phase_manifest_path: Path,
) -> dict[str, object]:
    target = verify_target_manifest(target_manifest_path)
    reports: list[dict[str, object]] = []
    output_records: list[dict[str, object]] = []
    total_input = 0
    total_output = 0
    total_missing = 0
    for shard in target["outputs"]["input_shards"]:
        index = int(shard["shard_index"])
        input_path = Path(shard["path"])
        output_path = output_root / "output_shards" / str(
            shard["expected_output_name"]
        )
        report_path = (
            output_root
            / "shard_reports"
            / f"g2p_target_{index:05d}.json"
        )
        result = verify_shard(
            input_shard=input_path,
            output_shard=output_path,
            acoustic_model=acoustic_model,
            report=report_path,
        )
        counts = result["counts"]
        total_input += int(counts["input_words"])
        total_output += int(counts["output_words"])
        total_missing += int(counts["missing_no_path_words"])
        reports.append(file_fingerprint(report_path, with_sha256=True))
        output_records.append(
            {
                **file_fingerprint(output_path, with_sha256=True),
                "shard_index": index,
                "input_words": int(counts["input_words"]),
                "output_words": int(counts["output_words"]),
                "missing_no_path_words": int(
                    counts["missing_no_path_words"]
                ),
            }
        )
    expected = int(target["counts"]["unique_targets"])
    if total_input != expected or total_output + total_missing != expected:
        raise RuntimeError(
            "G2P candidate phase coverage mismatch: "
            f"expected={expected}, input={total_input}, output={total_output}, "
            f"missing={total_missing}"
        )
    result = {
        "schema_version": PHASE_SCHEMA,
        "status": "success_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "candidate_is_final_selection": False,
            "next_required_gate": (
                "exact broad-Roman agreement with the explicit rule target"
            ),
            "source_files_modified": False,
            "textgrids_modified": False,
        },
        "counts": {
            "shards": len(output_records),
            "input_words": total_input,
            "output_candidate_words": total_output,
            "missing_no_path_words": total_missing,
        },
        "inputs": {
            "target_manifest": file_fingerprint(
                target_manifest_path, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "outputs": {
            "output_shards": output_records,
            "shard_reports": reports,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(phase_manifest_path, result)
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-shard")
    verify.add_argument("--input-shard", type=Path, required=True)
    verify.add_argument("--output-shard", type=Path, required=True)
    verify.add_argument("--acoustic-model", type=Path, required=True)
    verify.add_argument("--report", type=Path, required=True)
    existing = sub.add_parser("verify-existing-report")
    existing.add_argument("--input-shard", type=Path, required=True)
    existing.add_argument("--output-shard", type=Path, required=True)
    existing.add_argument("--acoustic-model", type=Path, required=True)
    existing.add_argument("--report", type=Path, required=True)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--target-manifest", type=Path, required=True)
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--acoustic-model", type=Path, required=True)
    finalize.add_argument("--phase-manifest", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "verify-shard":
        result = verify_shard(
            input_shard=args.input_shard.resolve(),
            output_shard=args.output_shard.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
            report=args.report.resolve(),
        )
    elif args.command == "verify-existing-report":
        result = verify_existing_report(
            input_shard=args.input_shard.resolve(),
            output_shard=args.output_shard.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
            report=args.report.resolve(),
        )
    else:
        result = finalize_phase(
            target_manifest_path=args.target_manifest.resolve(),
            output_root=args.output_root.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
            phase_manifest_path=args.phase_manifest.resolve(),
        )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

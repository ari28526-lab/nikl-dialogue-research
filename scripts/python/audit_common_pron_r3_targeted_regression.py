"""Audit the four reviewed 2022 r3 targeted-regression TextGrids."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, runtime_snapshot
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_targeted_regression_audit.v1"
RESULT_FIELDS = (
    "review_id", "utt_id", "target_word", "prior_r2_phones", "r3_candidate_phones",
    "r3_aligned_phones", "candidate_phone_exact", "word_begin", "word_end",
    "phone_boundary_contiguous", "word_phone_edges_equal", "spn_count",
    "automatic_verdict", "manual_audio_boundary_review",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def labeled(intervals: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    return [(float(begin), float(end), clean(label)) for begin, end, label in intervals if clean(label)]


def target_sequence(
    path: Path, target: str, *, phone_tier: str
) -> tuple[str, float, float, bool, bool, int]:
    duration, tiers = parse_mfa_textgrid(path)
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"invalid TextGrid duration: {path}")
    words = labeled(tiers.get("words", []))
    phones = labeled(tiers.get(phone_tier, []))
    targets = [(begin, end) for begin, end, label in words if label == target]
    if len(targets) != 1:
        raise RuntimeError(f"target word interval count differs: {path} {target} {len(targets)}")
    begin, end = targets[0]
    selected = [
        (phone_begin, phone_end, label)
        for phone_begin, phone_end, label in phones
        if phone_begin >= begin - 1e-6 and phone_end <= end + 1e-6
    ]
    if not selected:
        raise RuntimeError(f"target phone intervals absent: {path} {target}")
    contiguous = all(abs(selected[index - 1][1] - selected[index][0]) <= 1e-6 for index in range(1, len(selected)))
    edge_equal = abs(selected[0][0] - begin) <= 1e-6 and abs(selected[-1][1] - end) <= 1e-6
    spn_count = sum(label == "spn" for _phone_begin, _phone_end, label in phones)
    return " ".join(label for _phone_begin, _phone_end, label in selected), begin, end, contiguous, edge_equal, spn_count


def audit(preparation_manifest_path: Path, raw_root: Path, output_root: Path) -> dict[str, object]:
    preparation = json.loads(preparation_manifest_path.read_text(encoding="utf-8-sig"))
    if preparation.get("schema_version") != "common_pron_r3_targeted_regression_preparation.v1" or preparation.get("status") != "passed_ready_to_align":
        raise RuntimeError("targeted regression preparation identity differs")
    inventory_path = Path(str(preparation["outputs"]["sample_inventory"]["path"])).resolve()
    with inventory_path.open("r", encoding="utf-8-sig", newline="") as stream:
        samples = list(csv.DictReader(stream))
    if len(samples) != 4:
        raise RuntimeError("targeted regression sample count differs")
    textgrids = sorted(raw_root.rglob("*.TextGrid"))
    if len(textgrids) != 4:
        raise RuntimeError(f"targeted regression TextGrid count differs: {len(textgrids)}")
    by_name = {path.stem: path for path in textgrids}
    results: list[dict[str, object]] = []
    new_fingerprints: list[dict[str, object]] = []
    old_fingerprints: list[dict[str, object]] = []
    for sample in samples:
        utt_id = sample["utt_id"]
        target = sample["target_word"]
        new_path = by_name.get(utt_id)
        old_path = Path(sample["prior_r2_textgrid"]).resolve()
        if new_path is None or not old_path.is_file():
            raise RuntimeError(f"targeted regression pair missing: {utt_id}")
        new_phones, begin, end, contiguous, edge_equal, spn_count = target_sequence(new_path, target, phone_tier="phones")
        old_phones, *_ = target_sequence(old_path, target, phone_tier="phones_mfa")
        expected = sample["target_candidate_phones"]
        exact = new_phones == expected
        verdict = "pass" if exact and contiguous and edge_equal and spn_count == 0 else "fail"
        results.append(
            {
                "review_id": sample["review_id"], "utt_id": utt_id, "target_word": target,
                "prior_r2_phones": old_phones, "r3_candidate_phones": expected,
                "r3_aligned_phones": new_phones, "candidate_phone_exact": str(exact).lower(),
                "word_begin": f"{begin:.6f}", "word_end": f"{end:.6f}",
                "phone_boundary_contiguous": str(contiguous).lower(),
                "word_phone_edges_equal": str(edge_equal).lower(), "spn_count": spn_count,
                "automatic_verdict": verdict, "manual_audio_boundary_review": "pending",
            }
        )
        new_fingerprints.append(file_fingerprint(new_path, with_sha256=True))
        old_fingerprints.append(file_fingerprint(old_path, with_sha256=True))
    failures = [row for row in results if row["automatic_verdict"] != "pass"]
    if failures:
        raise RuntimeError(f"targeted regression automatic checks failed: {[row['utt_id'] for row in failures]}")
    result_path = output_root / "targeted_regression_results.csv"
    if result_path.exists():
        raise FileExistsError(result_path)
    with result_path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_automatic_checks_pending_researcher_audio_review",
        "recorded_at": now_iso(),
        "scope": {
            "review_ids": [row["review_id"] for row in results],
            "repeat_broad_pilot": False,
            "candidate_adopted": False,
            "production_mfa_started": False,
            "existing_r2_textgrids_modified": False,
            "automatic_phone_check_is_actual_realization_judgment": False,
        },
        "inputs": {
            "preparation_manifest": file_fingerprint(preparation_manifest_path, with_sha256=True),
            "sample_inventory": file_fingerprint(inventory_path, with_sha256=True),
            "prior_r2_textgrids": old_fingerprints,
            "r3_targeted_textgrids": new_fingerprints,
        },
        "checks": {
            "sample_count": len(results),
            "candidate_phone_exact": sum(row["candidate_phone_exact"] == "true" for row in results),
            "phone_boundary_contiguous": sum(row["phone_boundary_contiguous"] == "true" for row in results),
            "word_phone_edges_equal": sum(row["word_phone_edges_equal"] == "true" for row in results),
            "spn_total": sum(int(row["spn_count"]) for row in results),
            "automatic_pass": len(results),
            "manual_audio_boundary_review_pending": len(results),
        },
        "results": results,
        "outputs": {"results_csv": file_fingerprint(result_path, with_sha256=True)},
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_root / "TARGETED_REGRESSION_AUDIT.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation-manifest", type=Path, required=True)
    parser.add_argument("--raw-textgrid-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.preparation_manifest.resolve(), args.raw_textgrid_root.resolve(), args.output_root.resolve())
    print(json.dumps({"status": report["status"], **report["checks"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

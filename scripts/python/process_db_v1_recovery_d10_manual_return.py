"""Validate and freeze the D10 researcher TextGrid return without DB adoption."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

from praatio import textgrid
from praatio.data_classes.interval_tier import IntervalTier
from praatio.utilities.constants import Interval

from materialize_db_v1_recovery_d10_manual_overlay import (
    DEFAULT_GATE_ROOT,
    DEFAULT_SOURCE_ROOT,
    FINAL_TIERS,
    audit_target as audit_initial_target,
    row_stem,
    validate_contract,
)
from pipeline_common import atomic_write_json, now_iso, runtime_snapshot, sha256_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INITIAL_ROOT = Path(
    r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809\D10_MANUAL_OVERLAY_0001"
)
DEFAULT_RETURN_ROOT = Path(
    r"C:\Users\ari30\Dropbox\04_MFA_배치결과"
    r"\DB_V1_RECOVERY_D10_MANUAL_OVERLAY_16_20260818\work_flat"
)
DEFAULT_TARGET_ROOT = Path(
    r"D:\mfa_eojeol\recovery\common_pron_mfa_r3_20260809"
    r"\D10_RESEARCHER_RETURN_0001"
)
EXPECTED_COUNTS = {
    "tier_remap_from_proposed": 4,
    "exact_word_sequence": 6,
    "same_characters_different_word_segmentation": 1,
    "researcher_manual_transcription_override": 5,
}


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def entries_equal(left: tuple, right: tuple, tolerance: float = 1e-9) -> bool:
    return len(left) == len(right) and all(
        a.label == b.label
        and abs(a.start - b.start) <= tolerance
        and abs(a.end - b.end) <= tolerance
        for a, b in zip(left, right)
    )


def nonempty_labels(entries: tuple) -> list[str]:
    return [entry.label.strip() for entry in entries if entry.label.strip()]


def validate_tier_coverage(tier, duration: float, *, label: str) -> None:
    entries = tuple(tier.entries)
    if not entries:
        raise RuntimeError(f"empty interval tier: {label}")
    if abs(entries[0].start) > 1e-9 or abs(entries[-1].end - duration) > 1e-9:
        raise RuntimeError(f"tier outer boundary mismatch: {label}")
    for previous, current in zip(entries, entries[1:]):
        if abs(previous.end - current.start) > 1e-9:
            raise RuntimeError(
                f"tier gap/overlap: {label} previous_end={previous.end} "
                f"current_start={current.start}"
            )
        if current.end < current.start:
            raise RuntimeError(f"negative interval: {label}")


def returned_name(row: dict) -> str:
    return (
        f"{int(row['review_order']):02d}_{int(row['year'])}_"
        f"{row['utt_id'].replace('.', '_')}_manual_working.TextGrid"
    )


def normalized_name(row: dict) -> str:
    return f"{row_stem(row)}.manual_overlay.TextGrid"


def classify_return(grid, row: dict) -> tuple[str, list[str], list[str]]:
    expected = str(row["proposed_transcription"]).split()
    working = nonempty_labels(grid.getTier("words_manual_working").entries)
    proposed = nonempty_labels(grid.getTier("transcript_proposed").entries)
    if not working and proposed == expected:
        return "tier_remap_from_proposed", expected, working
    if working == expected:
        return "exact_word_sequence", expected, working
    if "".join(working) == "".join(expected):
        return "same_characters_different_word_segmentation", expected, working
    return "researcher_manual_transcription_override", expected, working


def validate_inputs(
    gate_root: Path,
    d9_review_root: Path,
    initial_root: Path,
    return_root: Path,
) -> dict:
    contract = validate_contract(gate_root, d9_review_root)
    initial_audit = audit_initial_target(initial_root, contract, require_done=True)
    if initial_audit["status"] != "passed_materialization_pending_researcher_manual_overlay":
        raise RuntimeError("unexpected initial D10 audit status")

    rows = []
    classifications: Counter[str] = Counter()
    seen_names: set[str] = set()
    for row in contract["queue"]["rows"]:
        name = returned_name(row)
        path = return_root / name
        if name in seen_names:
            raise RuntimeError(f"duplicate returned filename contract: {name}")
        seen_names.add(name)
        if not path.is_file():
            raise RuntimeError(f"researcher return missing: {path}")
        initial_path = initial_root / "work_flat" / f"{row_stem(row)}.manual_working.TextGrid"
        baseline = textgrid.openTextgrid(
            str(initial_path), includeEmptyIntervals=True, reportingMode="error"
        )
        returned = textgrid.openTextgrid(
            str(path), includeEmptyIntervals=True, reportingMode="error"
        )
        if tuple(returned.tierNames) != FINAL_TIERS:
            raise RuntimeError(f"returned tier contract mismatch: {name}")
        if abs(returned.maxTimestamp - baseline.maxTimestamp) > 1e-9:
            raise RuntimeError(f"returned duration changed: {name}")
        for tier_name in FINAL_TIERS:
            validate_tier_coverage(
                returned.getTier(tier_name), returned.maxTimestamp, label=f"{name}:{tier_name}"
            )
        for tier_name in ("words_d9_reference", "phones_d9_reference"):
            if not entries_equal(
                tuple(returned.getTier(tier_name).entries),
                tuple(baseline.getTier(tier_name).entries),
            ):
                raise RuntimeError(f"reference tier changed: {name}:{tier_name}")
        classification, expected, working = classify_return(returned, row)
        if not working and classification != "tier_remap_from_proposed":
            raise RuntimeError(f"returned working tier is empty without remap evidence: {name}")
        classifications[classification] += 1
        rows.append(
            {
                **row,
                "returned_filename": name,
                "returned_bytes": path.stat().st_size,
                "returned_sha256": sha256_file(path),
                "return_classification": classification,
                "proposed_words": expected,
                "researcher_working_words_before_normalization": working,
                "duration_seconds": returned.maxTimestamp,
            }
        )
    if dict(classifications) != EXPECTED_COUNTS:
        raise RuntimeError(
            f"return classification counts changed: expected={EXPECTED_COUNTS} "
            f"actual={dict(classifications)}"
        )
    unexpected = sorted(
        path.name
        for path in return_root.glob("*_manual_working.TextGrid")
        if ".manual_working." not in path.name and path.name not in seen_names
    )
    if unexpected:
        raise RuntimeError(f"unexpected researcher return files: {unexpected}")
    return {
        "contract": contract,
        "initial_root": initial_root.resolve(),
        "return_root": return_root.resolve(),
        "rows": rows,
        "classification_counts": dict(classifications),
    }


def normalize_grid(source: Path, destination: Path, row: dict) -> None:
    grid = textgrid.openTextgrid(
        str(source), includeEmptyIntervals=True, reportingMode="error"
    )
    duration = grid.maxTimestamp
    if row["return_classification"] == "tier_remap_from_proposed":
        researcher_entries = tuple(grid.getTier("transcript_proposed").entries)
        grid.replaceTier(
            "transcript_proposed",
            IntervalTier(
                "transcript_proposed",
                [Interval(0.0, duration, row["proposed_transcription"])],
                minT=0.0,
                maxT=duration,
            ),
            reportingMode="error",
        )
        grid.replaceTier(
            "words_manual_working",
            IntervalTier(
                "words_manual_working",
                researcher_entries,
                minT=0.0,
                maxT=duration,
            ),
            reportingMode="error",
        )
    grid.save(
        str(destination),
        format="long_textgrid",
        includeBlankSpaces=True,
        reportingMode="error",
    )


def audit_output(target_root: Path, input_state: dict, *, require_done: bool) -> dict:
    target_root = target_root.resolve()
    state_root = target_root / "state"
    queue = load_json(state_root / "D10_RESEARCHER_RETURN_QUEUE.json")
    if len(queue.get("rows", [])) != 16:
        raise RuntimeError("frozen researcher return queue must contain 16 rows")
    if queue.get("source_decisions_sha256") != input_state["contract"]["decisions_sha256"]:
        raise RuntimeError("researcher return queue decision hash mismatch")
    queue_by_order = {int(row["review_order"]): row for row in queue["rows"]}
    counts: Counter[str] = Counter()
    files = []
    rows = []
    for source_row in input_state["rows"]:
        order = int(source_row["review_order"])
        row = queue_by_order[order]
        raw = target_root / "raw_return" / row["returned_filename"]
        normalized = target_root / "normalized" / normalized_name(row)
        for kind, path in (("raw_return", raw), ("normalized", normalized)):
            if not path.is_file():
                raise RuntimeError(f"D10 frozen output missing: {path}")
            files.append(
                {
                    "kind": kind,
                    "path": str(path.relative_to(target_root)).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        if sha256_file(raw) != row["returned_sha256"]:
            raise RuntimeError(f"raw researcher return SHA changed: order={order}")
        baseline_path = (
            input_state["initial_root"]
            / "work_flat"
            / f"{row_stem(row)}.manual_working.TextGrid"
        )
        baseline = textgrid.openTextgrid(
            str(baseline_path), includeEmptyIntervals=True, reportingMode="error"
        )
        grid = textgrid.openTextgrid(
            str(normalized), includeEmptyIntervals=True, reportingMode="error"
        )
        if tuple(grid.tierNames) != FINAL_TIERS:
            raise RuntimeError(f"normalized tier mismatch: order={order}")
        if abs(grid.maxTimestamp - baseline.maxTimestamp) > 1e-9:
            raise RuntimeError(f"normalized duration mismatch: order={order}")
        for tier_name in FINAL_TIERS:
            validate_tier_coverage(
                grid.getTier(tier_name), grid.maxTimestamp, label=f"normalized:{order}:{tier_name}"
            )
        for tier_name in ("words_d9_reference", "phones_d9_reference"):
            if not entries_equal(
                tuple(grid.getTier(tier_name).entries),
                tuple(baseline.getTier(tier_name).entries),
            ):
                raise RuntimeError(f"normalized reference changed: order={order}:{tier_name}")
        proposed = nonempty_labels(grid.getTier("transcript_proposed").entries)
        if proposed != [row["proposed_transcription"]]:
            raise RuntimeError(f"normalized proposed tier changed: order={order}")
        final_words = nonempty_labels(grid.getTier("words_manual_working").entries)
        if not final_words:
            raise RuntimeError(f"normalized working tier empty: order={order}")
        if row["return_classification"] == "tier_remap_from_proposed":
            if final_words != row["proposed_words"]:
                raise RuntimeError(f"tier remap lost researcher words: order={order}")
        else:
            if final_words != row["researcher_working_words_before_normalization"]:
                raise RuntimeError(f"normalization changed researcher working words: order={order}")
        counts[row["return_classification"]] += 1
        rows.append(
            {
                "review_order": order,
                "year": row["year"],
                "utt_id": row["utt_id"],
                "classification": row["return_classification"],
                "proposed_words": row["proposed_words"],
                "final_manual_words": final_words,
                "duration_seconds": grid.maxTimestamp,
                "status": "passed_frozen_manual_overlay_no_adoption",
            }
        )
    if dict(counts) != EXPECTED_COUNTS:
        raise RuntimeError(f"normalized classification count mismatch: {dict(counts)}")
    if require_done:
        audit_path = state_root / "FINAL_AUDIT.json"
        done = load_json(state_root / "FROZEN_DONE.json")
        if done.get("status") != "frozen_researcher_return_pending_adoption_gate":
            raise RuntimeError("unexpected D10 researcher return completion status")
        if done.get("final_audit_sha256") != sha256_file(audit_path):
            raise RuntimeError("D10 researcher return completion/audit SHA mismatch")
    return {
        "schema_version": "research_db_v1_recovery_d10_researcher_return_audit.v1",
        "status": "passed_frozen_researcher_return_pending_adoption_gate",
        "recorded_at": now_iso(),
        "target_root": str(target_root),
        "counts": {
            "rows": 16,
            "raw_return_textgrids": 16,
            "normalized_textgrids": 16,
            **EXPECTED_COUNTS,
        },
        "rows": rows,
        "files": sorted(files, key=lambda item: item["path"]),
        "safety": {
            "dropbox_return_modified": False,
            "initial_d10_modified": False,
            "r3_main_body_modified": False,
            "research_6tier_modified": False,
            "db_v1_modified": False,
            "automatic_adoption_performed": False,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
        "script_sha256": sha256_file(Path(__file__).resolve()),
    }


def materialize(target_root: Path, input_state: dict) -> dict:
    target_root = target_root.resolve()
    if target_root.exists():
        if (target_root / "state" / "FROZEN_DONE.json").is_file():
            audit = audit_output(target_root, input_state, require_done=True)
            audit["idempotent_existing_target"] = True
            return audit
        raise RuntimeError(f"target exists without completion marker: {target_root}")
    target_root.parent.mkdir(parents=True, exist_ok=True)
    partial = target_root.with_name(f".{target_root.name}.partial.{os.getpid()}")
    if partial.exists():
        raise RuntimeError(f"partial target exists: {partial}")
    raw_root = partial / "raw_return"
    normalized_root = partial / "normalized"
    state_root = partial / "state"
    raw_root.mkdir(parents=True)
    normalized_root.mkdir(parents=True)
    state_root.mkdir(parents=True)
    queue = {
        "schema_version": "research_db_v1_recovery_d10_researcher_return_queue.v1",
        "status": "frozen_researcher_return_pending_adoption_gate",
        "recorded_at": now_iso(),
        "source_decisions_sha256": input_state["contract"]["decisions_sha256"],
        "classification_counts": input_state["classification_counts"],
        "rows": input_state["rows"],
        "automatic_adoption_performed": False,
    }
    atomic_write_json(state_root / "D10_RESEARCHER_RETURN_QUEUE.json", queue)
    for row in input_state["rows"]:
        source = input_state["return_root"] / row["returned_filename"]
        raw = raw_root / row["returned_filename"]
        shutil.copy2(source, raw)
        normalize_grid(source, normalized_root / normalized_name(row), row)
    readme = (
        "# D10 researcher return — frozen, not adopted\n\n"
        "`raw_return`은 연구자가 Dropbox에 저장한 16개 TextGrid의 byte-exact 사본이다.\n"
        "`normalized`는 1–4번의 잘못 선택된 tier 위치만 기계 교정한 작업본이다.\n"
        "나머지 수동 word label과 경계는 변경하지 않았다. 제안 전사와 다른 label은\n"
        "오류로 덮어쓰지 않고 researcher manual override로 장부에 보존했다.\n\n"
        "이 폴더는 아직 r3·6-tier·DB v1에 채택되지 않았다. 별도 adoption Gate가 필요하다.\n"
    )
    (partial / "00_READ_ME_FIRST.md").write_text(readme, encoding="utf-8", newline="\n")
    staging_audit = audit_output(partial, input_state, require_done=False)
    atomic_write_json(state_root / "STAGING_AUDIT.json", staging_audit)
    os.replace(partial, target_root)
    final_audit = audit_output(target_root, input_state, require_done=False)
    atomic_write_json(target_root / "state" / "FINAL_AUDIT.json", final_audit)
    done = {
        "schema_version": "research_db_v1_recovery_d10_researcher_return_done.v1",
        "status": "frozen_researcher_return_pending_adoption_gate",
        "recorded_at": now_iso(),
        "target_root": str(target_root),
        "source_decisions_sha256": input_state["contract"]["decisions_sha256"],
        "final_audit_sha256": sha256_file(target_root / "state" / "FINAL_AUDIT.json"),
        "automatic_adoption_performed": False,
    }
    atomic_write_json(target_root / "state" / "FROZEN_DONE.json", done)
    return audit_output(target_root, input_state, require_done=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-root", type=Path, default=DEFAULT_GATE_ROOT)
    parser.add_argument("--d9-review-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--initial-root", type=Path, default=DEFAULT_INITIAL_ROOT)
    parser.add_argument("--return-root", type=Path, default=DEFAULT_RETURN_ROOT)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_TARGET_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        input_state = validate_inputs(
            args.gate_root.resolve(),
            args.d9_review_root.resolve(),
            args.initial_root.resolve(),
            args.return_root.resolve(),
        )
        if args.preflight_only:
            result = {
                "status": "preflight_passed_no_materialization",
                "rows": len(input_state["rows"]),
                "classification_counts": input_state["classification_counts"],
                "target_root": str(args.target_root.resolve()),
                "automatic_adoption_performed": False,
            }
        elif args.audit_only:
            result = audit_output(args.target_root, input_state, require_done=True)
        else:
            result = materialize(args.target_root, input_state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

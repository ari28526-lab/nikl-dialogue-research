#!/usr/bin/env python3
"""Build a fail-closed 12-file pilot that updates only morph_analysis_utt.

The frozen Bareun morphology final and the existing r3 six-tier TextGrids are
read-only.  Derived TextGrids are written to a new workspace pilot root.  The
first five tiers and every tier boundary are preserved semantically; no MFA or
WAV access is performed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from pipeline_common import now_iso, sha256_file  # noqa: E402
from research_textgrid_v2 import (  # noqa: E402
    BASE_TIERS,
    normalize_search_label_for_textgrid,
    parse_mfa_textgrid,
    write_textgrid_exact,
)


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "bareun_morph_textgrid_pilot_v1.json"
FIRST_FIVE = BASE_TIERS[:5]
EOJEOL_SEPARATOR = " | "
MORPH_SEPARATOR = " + "


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "bareun_morph_textgrid_pilot_config.v1":
        raise RuntimeError("pilot config schema mismatch")
    if config["contract"]["tier_order"] != BASE_TIERS:
        raise RuntimeError("six-tier contract mismatch")
    return config


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def same_intervals(
    left: Sequence[tuple[float, float, str]],
    right: Sequence[tuple[float, float, str]],
    tolerance: float = 1e-6,
) -> bool:
    if len(left) != len(right):
        return False
    return all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        and str(a[2]) == str(b[2])
        for a, b in zip(left, right)
    )


def same_edges(
    left: Sequence[tuple[float, float, str]],
    right: Sequence[tuple[float, float, str]],
    tolerance: float = 1e-6,
) -> bool:
    if len(left) != len(right):
        return False
    return all(
        abs(float(a[0]) - float(b[0])) <= tolerance
        and abs(float(a[1]) - float(b[1])) <= tolerance
        for a, b in zip(left, right)
    )


def build_new_morph_label(
    rows: Sequence[Mapping[str, str]], expected_token_count: int
) -> tuple[str, int]:
    """Serialize frozen per-morpheme rows in the existing canonical display form."""

    if not rows:
        raise ValueError("morpheme rows missing")
    token_rows: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    global_morph_indices: list[int] = []
    for row in rows:
        token_index = int(row["token_index"])
        morph_index = int(row["morph_index"])
        surface = str(row["morph_surface"])
        pos = str(row["pos"])
        if not surface or not pos:
            raise ValueError("empty morph surface or POS")
        token_rows[token_index].append((morph_index, surface, pos))
        global_morph_indices.append(morph_index)
    if sorted(token_rows) != list(range(expected_token_count)):
        raise ValueError(
            f"token index mismatch: {sorted(token_rows)} expected={expected_token_count}"
        )
    if sorted(global_morph_indices) != list(range(len(global_morph_indices))):
        raise ValueError("global morph indices are not contiguous")
    eojeols: list[str] = []
    for token_index in range(expected_token_count):
        morphs = sorted(token_rows[token_index], key=lambda item: item[0])
        eojeols.append(
            MORPH_SEPARATOR.join(f"{surface}/{pos}" for _, surface, pos in morphs)
        )
    raw_label = EOJEOL_SEPARATOR.join(eojeols)
    return normalize_search_label_for_textgrid(raw_label), len(global_morph_indices)


def one_labeled_interval(
    intervals: Sequence[tuple[float, float, str]], tier_name: str
) -> tuple[int, str]:
    labeled = [(index, str(row[2])) for index, row in enumerate(intervals) if str(row[2])]
    if len(labeled) != 1:
        raise ValueError(f"{tier_name} must have exactly one labeled interval")
    return labeled[0]


def derive_textgrid(source: Path, destination: Path, new_label: str) -> dict[str, Any]:
    if destination.exists():
        raise FileExistsError(destination)
    duration, source_tiers = parse_mfa_textgrid(source)
    if duration is None or list(source_tiers) != BASE_TIERS:
        raise ValueError(f"source six-tier contract mismatch: {source}")
    morph_intervals = list(source_tiers["morph_analysis_utt"])
    label_index, old_label = one_labeled_interval(
        morph_intervals, "morph_analysis_utt"
    )
    begin, end, _ = morph_intervals[label_index]
    morph_intervals[label_index] = (begin, end, new_label)
    tier_data = [
        (name, list(source_tiers[name])) for name in FIRST_FIVE
    ] + [("morph_analysis_utt", morph_intervals)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_textgrid_exact(destination, duration=float(duration), tier_data=tier_data)

    derived_duration, derived_tiers = parse_mfa_textgrid(destination)
    if derived_duration is None or list(derived_tiers) != BASE_TIERS:
        raise RuntimeError("derived six-tier contract mismatch")
    first_five_unchanged = all(
        same_intervals(source_tiers[name], derived_tiers[name]) for name in FIRST_FIVE
    )
    morph_boundaries_unchanged = same_edges(
        source_tiers["morph_analysis_utt"], derived_tiers["morph_analysis_utt"]
    )
    _, derived_label = one_labeled_interval(
        derived_tiers["morph_analysis_utt"], "derived morph_analysis_utt"
    )
    if not first_five_unchanged or not morph_boundaries_unchanged:
        raise RuntimeError("protected tier or boundary changed")
    if derived_label != new_label:
        raise RuntimeError("derived morphology label mismatch")
    return {
        "duration": float(duration),
        "old_label": old_label,
        "new_label": new_label,
        "first_five_unchanged": first_five_unchanged,
        "morph_boundaries_unchanged": morph_boundaries_unchanged,
    }


def read_inventory(final_root: Path) -> list[tuple[str, str]]:
    inventory = final_root / "RECEIPT_INVENTORY.tsv"
    rows: list[tuple[str, str]] = []
    for line_number, line in enumerate(
        inventory.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0] or len(parts[1]) != 64:
            raise RuntimeError(f"invalid receipt inventory line {line_number}")
        rows.append((parts[0], parts[1]))
    return rows


def read_gzip_dicts(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_receipt_rows(
    final_root: Path, receipt_relative: str, expected_receipt_sha: str
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    receipt_path = final_root / receipt_relative
    if sha256_file(receipt_path) != expected_receipt_sha:
        raise RuntimeError(f"receipt SHA mismatch: {receipt_relative}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    parent = receipt_path.parent
    utterance_path = parent / "utterances.csv.gz"
    morpheme_path = parent / "morphemes.csv.gz"
    for name, path in (
        ("utterances.csv.gz", utterance_path),
        ("morphemes.csv.gz", morpheme_path),
    ):
        contract = receipt["outputs"][name]
        if path.stat().st_size != int(contract["bytes"]):
            raise RuntimeError(f"output size mismatch: {path}")
        if sha256_file(path) != contract["sha256"]:
            raise RuntimeError(f"output SHA mismatch: {path}")
    utterances = read_gzip_dicts(utterance_path)
    morph_by_utt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_gzip_dicts(morpheme_path):
        morph_by_utt[row["utt_id"]].append(row)
    return receipt, utterances, morph_by_utt


def select_samples(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    final_root = resolve_path(config["input"]["bareun_final_root"])
    textgrid_root = resolve_path(config["input"]["source_textgrid_root"])
    inventory = read_inventory(final_root)
    maximum = int(config["selection"]["max_receipts_per_year"])
    selected: list[dict[str, Any]] = []
    all_stats: dict[str, Any] = {}
    for year in config["input"]["expected_years"]:
        wanted = {"changed": 1, "unchanged": 1}
        found: dict[str, dict[str, Any]] = {}
        stats: Counter[str] = Counter()
        year_receipts = [
            row for row in inventory if f"NIKL_DIALOGUE_{year}" in row[0]
        ]
        for receipt_relative, receipt_sha in year_receipts[:maximum]:
            stats["receipts_scanned"] += 1
            receipt, utterances, morph_by_utt = load_receipt_rows(
                final_root, receipt_relative, receipt_sha
            )
            session = Path(receipt["source_file"]).stem
            receipt_parent = Path(receipt_relative).parent
            for utterance in utterances:
                stats["utterances_scanned"] += 1
                utt_id = utterance["utt_id"]
                source_textgrid = textgrid_root / str(year) / session / f"{utt_id}.TextGrid"
                if not source_textgrid.is_file():
                    stats["no_mfa_alignment"] += 1
                    continue
                try:
                    duration, tiers = parse_mfa_textgrid(source_textgrid)
                    if duration is None or list(tiers) != BASE_TIERS:
                        raise ValueError("source tier contract")
                    _, old_label = one_labeled_interval(
                        tiers["morph_analysis_utt"], "morph_analysis_utt"
                    )
                    expected_tokens = int(utterance["response_token_count"])
                    new_label, morph_count = build_new_morph_label(
                        morph_by_utt.get(utt_id, []), expected_tokens
                    )
                    labeled_words = sum(
                        1 for _, _, label in tiers["words"] if str(label)
                    )
                    if labeled_words != expected_tokens:
                        stats["word_token_count_mismatch"] += 1
                        continue
                except (ValueError, KeyError) as exc:
                    stats[f"candidate_contract_error:{type(exc).__name__}"] += 1
                    continue
                category = "changed" if old_label != new_label else "unchanged"
                stats[f"eligible_{category}"] += 1
                if category not in found:
                    found[category] = {
                        "year": str(year),
                        "session": session,
                        "utt_id": utt_id,
                        "source_row_index": utterance["source_row_index"],
                        "form": utterance["form"],
                        "response_token_count": expected_tokens,
                        "morph_count": morph_count,
                        "labeled_word_count": labeled_words,
                        "category": category,
                        "old_label": old_label,
                        "new_label": new_label,
                        "label_normalized_for_textgrid": False,
                        "source_textgrid": str(source_textgrid.resolve()),
                        "receipt_relative": receipt_relative,
                        "receipt_sha256": receipt_sha,
                        "utterances_relative": str(
                            (receipt_parent / "utterances.csv.gz").as_posix()
                        ),
                        "morphemes_relative": str(
                            (receipt_parent / "morphemes.csv.gz").as_posix()
                        ),
                    }
                if all(category in found for category in wanted):
                    break
            if all(category in found for category in wanted):
                break
        if set(found) != set(wanted):
            raise RuntimeError(
                f"{year} balanced pilot unavailable: found={sorted(found)} stats={dict(stats)}"
            )
        selected.extend([found["changed"], found["unchanged"]])
        stats["selected_changed"] = 1
        stats["selected_unchanged"] = 1
        all_stats[str(year)] = dict(sorted(stats.items()))
    return selected, all_stats


def markdown_code(value: str) -> str:
    return "`" + json.dumps(str(value), ensure_ascii=False).replace("`", "\\`") + "`"


def choose_user_review(samples: Sequence[Mapping[str, Any]], count: int) -> list[Mapping[str, Any]]:
    changed = [row for row in samples if row["category"] == "changed"]
    unchanged = [row for row in samples if row["category"] == "unchanged"]
    candidates: list[Mapping[str, Any]] = []
    if changed:
        candidates.append(changed[0])
    if unchanged:
        candidates.append(unchanged[len(unchanged) // 2])
    if changed:
        candidates.append(changed[-1])
    for row in samples:
        if row not in candidates:
            candidates.append(row)
    return candidates[:count]


def write_user_todo(path: Path, samples: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# 사용자 최소 확인 TODO",
        "",
        "기계 검토는 12/12에 대해 완료된다. 아래 세 건만 보고 각 번호에",
        "`OK` 또는 `보류: 이유`로 답하면 된다. 형태소 tier는 발화 전체 표시이며",
        "형태소별 음향 시간경계를 뜻하지 않는다.",
        "",
    ]
    for index, row in enumerate(samples, 1):
        lines.extend(
            [
                f"## {index}. {row['year']} · {row['category']} · {row['utt_id']}",
                "",
                f"- [ ] 문장과 새 형태소 분석이 연구용 표시로 자연스러운지 확인",
                f"- [ ] 이상하면 `보류`하고 한 줄 이유만 기록",
                f"- 파생 TextGrid: `{row['derived_textgrid']}`",
                f"- 원본 TextGrid: `{row['source_textgrid']}`",
                f"- 문장: {markdown_code(row['form'])}",
                f"- 기존 형태소: {markdown_code(row['old_label'])}",
                f"- 새 v3.1 형태소: {markdown_code(row['new_label'])}",
                "",
                f"답변: `{index} OK` 또는 `{index} 보류: ...`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty CSV")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def preflight(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    final_root = resolve_path(config["input"]["bareun_final_root"])
    textgrid_root = resolve_path(config["input"]["source_textgrid_root"])
    output_root = resolve_path(config["output"]["root"])
    building_root = output_root.with_name(output_root.name + ".building")
    final_manifest = final_root / "FINAL_MANIFEST.json"
    inventory = final_root / "RECEIPT_INVENTORY.tsv"
    checks = {
        "bareun_final_manifest": final_manifest.is_file(),
        "bareun_receipt_inventory": inventory.is_file(),
        "source_textgrid_root": textgrid_root.is_dir(),
        "output_absent": not output_root.exists(),
        "building_absent": not building_root.exists(),
        "year_roots": all((textgrid_root / year).is_dir() for year in config["input"]["expected_years"]),
    }
    return {
        "schema": "bareun_morph_textgrid_pilot_preflight.v1",
        "ready": all(checks.values()),
        "checks": checks,
        "config_sha256": sha256_file(config_path),
        "source_or_wav_mutation": False,
        "mfa_rerun": False,
    }


def execute(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    check = preflight(config_path, config)
    if not check["ready"]:
        raise RuntimeError(f"preflight failed: {check}")
    final_root = resolve_path(config["input"]["bareun_final_root"])
    output_root = resolve_path(config["output"]["root"])
    building_root = output_root.with_name(output_root.name + ".building")
    building_root.parent.mkdir(parents=True, exist_ok=True)
    building_root.mkdir()
    selected, selection_stats = select_samples(config)
    source_manifest = final_root / "FINAL_MANIFEST.json"
    source_manifest_payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for sample_number, sample in enumerate(selected, 1):
        source = Path(sample["source_textgrid"])
        source_sha = sha256_file(source)
        derived_relative = (
            Path("textgrids")
            / sample["year"]
            / sample["session"]
            / f"{sample['utt_id']}.TextGrid"
        )
        destination = building_root / derived_relative
        derived = derive_textgrid(source, destination, sample["new_label"])
        if sha256_file(source) != source_sha:
            raise RuntimeError(f"source TextGrid changed: {source}")
        source_hashes[str(source.resolve())] = source_sha
        rows.append(
            {
                "sample_number": sample_number,
                "year": sample["year"],
                "session": sample["session"],
                "utt_id": sample["utt_id"],
                "category": sample["category"],
                "form": sample["form"],
                "response_token_count": sample["response_token_count"],
                "morph_count": sample["morph_count"],
                "labeled_word_count": sample["labeled_word_count"],
                "old_label": derived["old_label"],
                "new_label": derived["new_label"],
                "old_label_sha256": hash_text(derived["old_label"]),
                "new_label_sha256": hash_text(derived["new_label"]),
                "source_textgrid": str(source.resolve()),
                "source_textgrid_sha256": source_sha,
                "derived_textgrid": str((output_root / derived_relative).resolve()),
                "derived_relative": derived_relative.as_posix(),
                "derived_textgrid_sha256": sha256_file(destination),
                "receipt_relative": sample["receipt_relative"],
                "receipt_sha256": sample["receipt_sha256"],
                "utterances_relative": sample["utterances_relative"],
                "morphemes_relative": sample["morphemes_relative"],
                "first_five_unchanged": str(derived["first_five_unchanged"]).lower(),
                "morph_boundaries_unchanged": str(derived["morph_boundaries_unchanged"]).lower(),
                "source_textgrid_unchanged": "true",
                "wav_accessed": "false",
                "mfa_rerun": "false",
            }
        )
    write_csv(building_root / "PILOT_JOIN.csv", rows)
    review_rows = choose_user_review(
        rows, int(config["selection"]["user_review_cases"])
    )
    write_user_todo(building_root / "USER_TODO.md", review_rows)

    derived_bytes = sum(
        (building_root / row["derived_relative"]).stat().st_size for row in rows
    )
    mean_bytes = derived_bytes / len(rows)
    estimated_total_bytes = round(
        mean_bytes * int(config["input"]["expected_aligned_textgrids"])
    )
    free_d_bytes = shutil.disk_usage("D:/").free
    receipt = {
        "schema": "bareun_morph_textgrid_pilot_build.v1",
        "status": "built_pending_independent_audit",
        "built_at": now_iso(),
        "run_id": config["run_id"],
        "sample_count": len(rows),
        "years": list(config["input"]["expected_years"]),
        "selection": {"changed": 6, "unchanged": 6},
        "selection_stats": selection_stats,
        "source_bareun_manifest_sha256": sha256_file(source_manifest),
        "source_bareun_receipt_inventory_sha256": source_manifest_payload[
            "receipt_inventory_sha256"
        ],
        "source_textgrid_sha256": source_hashes,
        "derived_textgrid_bytes": derived_bytes,
        "estimated_full_textgrid_bytes": estimated_total_bytes,
        "estimated_full_textgrid_gib": round(estimated_total_bytes / 1024**3, 3),
        "free_d_gib_before": round(free_d_bytes / 1024**3, 3),
        "estimated_free_d_gib_after": round(
            (free_d_bytes - estimated_total_bytes) / 1024**3, 3
        ),
        "source_textgrid_modified": False,
        "source_wav_accessed": False,
        "mfa_rerun": False,
        "first_five_semantically_unchanged": True,
        "morph_boundaries_unchanged": True,
        "updated_tier": "morph_analysis_utt",
        "morph_tier_interpretation": "utterance_level_display_not_acoustic_boundaries",
        "config_sha256": sha256_file(config_path),
        "builder_sha256": sha256_file(Path(__file__)),
    }
    (building_root / "BUILD_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksum_targets = sorted(
        path
        for path in building_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    (building_root / "SHA256SUMS.txt").write_text(
        "".join(
            f"{sha256_file(path)}\t{path.relative_to(building_root).as_posix()}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
    )
    os.replace(building_root, output_root)
    receipt["status"] = "built_promoted_pending_independent_audit"
    receipt["output_root"] = str(output_root)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    result = (
        preflight(config_path, config)
        if args.preflight_only
        else execute(config_path, config)
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ready", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

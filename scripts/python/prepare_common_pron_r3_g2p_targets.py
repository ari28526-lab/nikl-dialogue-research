"""r3 미선택 규칙형을 중복 제거해 재개 가능한 G2P target shard로 만든다."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import (  # noqa: E402
    JAMO_LS,
    analyze_g2p_word,
    g2p_grapheme_contract,
    rewrite_jamo_ls_for_model,
)
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from resolve_common_pron_r3_surface_donors import (  # noqa: E402
    OUTPUT_FIELDS as DONOR_FIELDS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_g2p_targets.v1"
ELIGIBLE_STATUSES = {
    "candidate_replace_rule_dictionary_agree",
    "review_rule_dictionary_conflict",
    "review_rule_sensitive_no_attested_agreement",
}
STATUS_PRIORITY = {
    "candidate_replace_rule_dictionary_agree": 0,
    "review_rule_dictionary_conflict": 1,
    "review_rule_sensitive_no_attested_agreement": 2,
}
TARGET_FIELDS = (
    "target_hangul",
    "g2p_model_input",
    "rule_pron_roman",
    "source_type_count",
    "total_occurrences",
    "source_selection_statuses_json",
    "priority",
    "rewrite_rule",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def verify_source(path: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != "common_pron_r3_surface_donor_candidates.v1":
        raise RuntimeError("surface donor manifest schema 불일치")
    if manifest.get("status") != "success_candidates_not_selected":
        raise RuntimeError("surface donor 후보 상태 오류")
    expected = clean(manifest["outputs"]["candidate_inventory"].get("sha256"))
    if not expected or sha256_file(path).lower() != expected.lower():
        raise RuntimeError("surface donor 후보 CSV SHA256 불일치")
    return manifest


def build_targets(
    *,
    candidate_inventory: Path,
    candidate_manifest: Path,
    g2p_model: Path,
    output_root: Path,
    shard_size: int,
) -> dict[str, object]:
    if shard_size < 100:
        raise ValueError("shard_size는 100 이상이어야 함")
    manifest_path = output_root / "G2P_TARGETS_MANIFEST.json"
    inventory_path = output_root / "g2p_rule_targets.csv.gz"
    shards_root = output_root / "input_shards"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise RuntimeError("기존 G2P target manifest schema 불일치")
        for record in (manifest["inputs"].values()):
            if sha256_file(Path(record["path"])) != record["sha256"]:
                raise RuntimeError("기존 G2P target 입력 fingerprint 불일치")
        for record in manifest["outputs"]["input_shards"]:
            if sha256_file(Path(record["path"])) != record["sha256"]:
                raise RuntimeError("기존 G2P target shard fingerprint 불일치")
        if sha256_file(inventory_path) != manifest["outputs"]["target_inventory"]["sha256"]:
            raise RuntimeError("기존 G2P target inventory fingerprint 불일치")
        return manifest
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"manifest 없는 G2P target root를 덮어쓰지 않음: {output_root}")
    source_manifest = verify_source(candidate_inventory, candidate_manifest)
    graphemes, model_contract = g2p_grapheme_contract(g2p_model)
    grouped: dict[str, dict[str, object]] = {}
    with gzip.open(
        candidate_inventory, "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != DONOR_FIELDS:
            raise RuntimeError("surface donor candidate 열 계약 불일치")
        for row in reader:
            status = clean(row["selection_status"])
            if (
                row["selected_variant_count"] != "0"
                or row["candidate_status"] != "none"
                or status not in ELIGIBLE_STATUSES
            ):
                continue
            target = clean(row["rule_pron_hangul"])
            roman = clean(row["rule_pron_roman"])
            if not target or not roman:
                raise RuntimeError(f"G2P target/roman 누락: {row['token']}")
            record = grouped.setdefault(
                target,
                {
                    "romans": set(),
                    "statuses": set(),
                    "source_type_count": 0,
                    "total_occurrences": 0,
                    "priority": 99,
                },
            )
            record["romans"].add(roman)
            record["statuses"].add(status)
            record["source_type_count"] += 1
            record["total_occurrences"] += int(row["total_occurrences"])
            record["priority"] = min(record["priority"], STATUS_PRIORITY[status])
    rows: list[dict[str, object]] = []
    model_inputs: set[str] = set()
    rewrite_counts: defaultdict[str, int] = defaultdict(int)
    for target, record in grouped.items():
        romans = sorted(record["romans"])
        if len(romans) != 1:
            raise RuntimeError(f"동일 target의 Roman 충돌: {target} {romans}")
        _, missing = analyze_g2p_word(
            target,
            graphemes=graphemes,
            unicode_decomposition=bool(model_contract["unicode_decomposition"]),
        )
        model_input = target
        rewrite_rule = "none"
        if missing == {JAMO_LS}:
            model_input = rewrite_jamo_ls_for_model(target)
            _, rewritten_missing = analyze_g2p_word(
                model_input,
                graphemes=graphemes,
                unicode_decomposition=bool(model_contract["unicode_decomposition"]),
            )
            if rewritten_missing:
                raise RuntimeError(f"U+11B3 rewrite 뒤 미지원: {target}")
            rewrite_rule = "NFKD U+11B3 -> U+11AF U+11BA -> NFKC"
        elif missing:
            raise RuntimeError(
                f"r3 G2P target 미지원 grapheme: {target} "
                + " ".join(f"U+{ord(value):04X}" for value in sorted(missing))
            )
        if model_input in model_inputs:
            raise RuntimeError(f"r3 G2P model input 충돌: {target} -> {model_input}")
        model_inputs.add(model_input)
        rewrite_counts[rewrite_rule] += 1
        rows.append(
            {
                "target_hangul": target,
                "g2p_model_input": model_input,
                "rule_pron_roman": romans[0],
                "source_type_count": str(record["source_type_count"]),
                "total_occurrences": str(record["total_occurrences"]),
                "source_selection_statuses_json": json.dumps(
                    sorted(record["statuses"]), ensure_ascii=False
                ),
                "priority": str(record["priority"]),
                "rewrite_rule": rewrite_rule,
            }
        )
    rows.sort(
        key=lambda row: (
            int(row["priority"]),
            -int(row["total_occurrences"]),
            row["target_hangul"],
        )
    )
    output_root.mkdir(parents=True, exist_ok=False)
    shards_root.mkdir()
    with gzip.open(
        inventory_path, "xt", encoding="utf-8-sig", newline="", compresslevel=6
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=TARGET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    shard_records: list[dict[str, object]] = []
    for index in range(math.ceil(len(rows) / shard_size)):
        shard_rows = rows[index * shard_size : (index + 1) * shard_size]
        path = shards_root / f"g2p_target_{index + 1:05d}.txt"
        with atomic_text_writer(path, encoding="utf-8", newline="\n") as (stream, _):
            for row in shard_rows:
                stream.write(f"{row['g2p_model_input']}\n")
        fingerprint = file_fingerprint(path, with_sha256=True)
        fingerprint.update(
            {
                "shard_index": index + 1,
                "row_count": len(shard_rows),
                "expected_output_name": f"g2p_target_{index + 1:05d}.dict",
            }
        )
        shard_records.append(fingerprint)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "recorded_at": now_iso(),
        "scope": {
            "candidate_is_final_selection": False,
            "num_pronunciations_phase": 1,
            "target_unit": "unique_rule_pron_hangul",
            "source_files_modified": False,
        },
        "inputs": {
            "candidate_inventory": file_fingerprint(
                candidate_inventory, with_sha256=True
            ),
            "candidate_manifest": file_fingerprint(
                candidate_manifest, with_sha256=True
            ),
            "g2p_model": file_fingerprint(g2p_model, with_sha256=True),
        },
        "counts": {
            "source_candidate_types": sum(
                int(row["source_type_count"]) for row in rows
            ),
            "unique_targets": len(rows),
            "total_occurrences": sum(int(row["total_occurrences"]) for row in rows),
            "shards": len(shard_records),
            "shard_size": shard_size,
            "rewrite_rules": dict(sorted(rewrite_counts.items())),
        },
        "g2p_model_contract": model_contract,
        "source_manifest_status": source_manifest["status"],
        "outputs": {
            "target_inventory": file_fingerprint(inventory_path, with_sha256=True),
            "input_shards": shard_records,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-inventory", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path, required=True)
    parser.add_argument("--g2p-model", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--shard-size", type=int, default=25_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_targets(
        candidate_inventory=args.candidate_inventory.resolve(),
        candidate_manifest=args.candidate_manifest.resolve(),
        g2p_model=args.g2p_model.resolve(),
        output_root=args.output_root.resolve(),
        shard_size=args.shard_size,
    )
    print(
        "[OK] r3 G2P target prepare: "
        f"targets={manifest['counts']['unique_targets']:,}; "
        f"shards={manifest['counts']['shards']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

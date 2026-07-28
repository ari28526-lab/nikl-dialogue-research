"""공통 발음 registry 구축 전 enriched/legacy 사전 원천을 전수 감사한다."""
from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)

ENRICHED_REQUIRED = {
    "word",
    "word_stem",
    "pos_tag",
    "sense_no",
    "urimal_id",
    "pron_1",
    "pron_2",
}
LEGACY_REQUIRED = {
    "word",
    "word_stem",
    "pos_tag",
    "sense_no",
    "urimal_id",
    "pron_1",
    "pron_2",
    "pron_g2p",
}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def audit_sources(
    *,
    enriched_path: Path,
    legacy_path: Path,
    output_path: Path,
    progress_every: int = 250_000,
) -> dict:
    if output_path.exists():
        raise FileExistsError(f"기존 원천 감사 보고서를 덮어쓰지 않음: {output_path}")
    for path in (enriched_path, legacy_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    started = time.perf_counter()
    legacy_counts = Counter()
    legacy_by_urimal: dict[str, set[str]] = defaultdict(set)
    legacy_keys = Counter()
    with legacy_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = LEGACY_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"legacy 필수 열 누락 {sorted(missing)}")
        for row_number, row in enumerate(reader, start=1):
            legacy_counts["rows"] += 1
            urimal_id = clean(row.get("urimal_id"))
            word = clean(row.get("word"))
            pos = clean(row.get("pos_tag"))
            sense = clean(row.get("sense_no"))
            pron_1 = clean(row.get("pron_1"))
            pron_2 = clean(row.get("pron_2"))
            pron_g2p = clean(row.get("pron_g2p"))
            if urimal_id:
                legacy_counts["rows_with_urimal_id"] += 1
                if pron_g2p:
                    legacy_by_urimal[urimal_id].add(pron_g2p)
            if pron_1:
                legacy_counts["rows_with_pron_1"] += 1
            if pron_2:
                legacy_counts["rows_with_pron_2"] += 1
            if pron_g2p:
                legacy_counts["rows_with_pron_g2p"] += 1
            legacy_keys[(word, pos, sense, urimal_id)] += 1
            if progress_every and row_number % progress_every == 0:
                print(
                    f"[source-audit] legacy rows={row_number:,}",
                    flush=True,
                )

    enriched_counts = Counter()
    enriched_keys = Counter()
    enriched_missing_urimal: set[str] = set()
    fallback_variant_hist = Counter()
    with enriched_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = ENRICHED_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"enriched 필수 열 누락 {sorted(missing)}")
        for row_number, row in enumerate(reader, start=1):
            enriched_counts["rows"] += 1
            urimal_id = clean(row.get("urimal_id"))
            word = clean(row.get("word"))
            pos = clean(row.get("pos_tag"))
            sense = clean(row.get("sense_no"))
            pron_1 = clean(row.get("pron_1"))
            pron_2 = clean(row.get("pron_2"))
            if urimal_id:
                enriched_counts["rows_with_urimal_id"] += 1
            if pron_1:
                enriched_counts["rows_with_pron_1"] += 1
            if pron_2:
                enriched_counts["rows_with_pron_2"] += 1
            if pron_1 or pron_2:
                enriched_counts["rows_with_any_attested_candidate"] += 1
            else:
                enriched_counts["rows_without_pron_1_2"] += 1
                variants = legacy_by_urimal.get(urimal_id, set())
                if urimal_id and variants:
                    enriched_counts["missing_pron_with_legacy_g2p"] += 1
                    fallback_variant_hist[len(variants)] += 1
                else:
                    enriched_counts["missing_pron_without_legacy_g2p"] += 1
                    if urimal_id:
                        enriched_missing_urimal.add(urimal_id)
            enriched_keys[(word, pos, sense, urimal_id)] += 1
            if progress_every and row_number % progress_every == 0:
                print(
                    f"[source-audit] enriched rows={row_number:,}",
                    flush=True,
                )

    elapsed = time.perf_counter() - started
    legacy_urimal_variant_hist = Counter(
        len(values) for values in legacy_by_urimal.values()
    )
    project_root = Path(__file__).resolve().parents[2]
    report = {
        "schema_version": 1,
        "kind": "common_pronunciation_source_audit",
        "status": "success",
        "recorded_at": now_iso(),
        "scope": "full_lexicon_sources_before_registry_build",
        "sources": {
            "enriched": file_fingerprint(
                enriched_path, with_sha256=True
            ),
            "legacy": file_fingerprint(legacy_path, with_sha256=True),
        },
        "enriched": {
            **dict(enriched_counts),
            "duplicate_word_pos_sense_urimal_keys": sum(
                count - 1 for count in enriched_keys.values() if count > 1
            ),
            "duplicate_key_groups": sum(
                count > 1 for count in enriched_keys.values()
            ),
        },
        "legacy": {
            **dict(legacy_counts),
            "unique_urimal_ids_with_g2p": len(legacy_by_urimal),
            "urimal_g2p_variant_count_distribution": {
                str(key): value
                for key, value in sorted(legacy_urimal_variant_hist.items())
            },
            "duplicate_word_pos_sense_urimal_keys": sum(
                count - 1 for count in legacy_keys.values() if count > 1
            ),
            "duplicate_key_groups": sum(
                count > 1 for count in legacy_keys.values()
            ),
        },
        "fallback_linkage": {
            "enriched_missing_pron_with_legacy_g2p": enriched_counts[
                "missing_pron_with_legacy_g2p"
            ],
            "enriched_missing_pron_without_legacy_g2p": enriched_counts[
                "missing_pron_without_legacy_g2p"
            ],
            "unmatched_enriched_urimal_ids": len(enriched_missing_urimal),
            "legacy_variant_count_distribution_for_fallback_rows": {
                str(key): value
                for key, value in sorted(fallback_variant_hist.items())
            },
            "interpretation": (
                "legacy pron_g2p는 기계 생성 보완 후보이며 "
                "우리말샘 등재 발음으로 분류하지 않음"
            ),
        },
        "elapsed_seconds": round(elapsed, 3),
        "runtime": runtime_snapshot(project_root),
    }
    atomic_write_json(output_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--enriched",
        type=Path,
        default=Path(
            r"D:\00_RAW\reference\00_DICTIONARY"
            r"\01_NIKL_lexicon_full_v2.csv"
        ),
    )
    parser.add_argument(
        "--legacy",
        type=Path,
        default=Path(
            r"D:\00_RAW\reference\03_lexicon_1기"
            r"\01_NIKL_lexicon_full.csv"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=250_000)
    args = parser.parse_args()
    try:
        report = audit_sources(
            enriched_path=args.enriched.resolve(),
            legacy_path=args.legacy.resolve(),
            output_path=args.output.resolve(),
            progress_every=max(args.progress_every, 0),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(
        "[OK] 사전 원천 전수 감사: "
        f"enriched={report['enriched']['rows']:,}, "
        f"legacy={report['legacy']['rows']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

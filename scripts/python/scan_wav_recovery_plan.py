"""Run the corpus-wide structural scan of a recovery plan before listening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_wav_recovery_corpus import read_plan, scan_corpus
from pipeline_common import atomic_write_json, file_fingerprint, now_iso


SCHEMA_VERSION = "wav_recovery_plan_scan.v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--plan-csv", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--source-wav-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    plan_path = args.plan_csv.resolve()
    plan_rows, plan_by_target = read_plan(plan_path, str(args.year))
    scan = scan_corpus(
        year=str(args.year),
        search_master_root=args.search_master_root.resolve(),
        source_wav_root=args.source_wav_root.resolve(),
        plan_rows=plan_rows,
        plan_by_target=plan_by_target,
    )
    if int(scan["unique_corpus_source_files"]) != int(scan["corpus_entries"]):
        raise RuntimeError("최종 포함 target 수와 고유 source WAV 수가 다름")
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "scan_only_passed",
        "created_at": now_iso(),
        "year": str(args.year),
        "mutates_wav": False,
        "plan_csv": file_fingerprint(plan_path, with_sha256=True),
        "search_master_root": str(args.search_master_root.resolve()),
        "source_wav_root": str(args.source_wav_root.resolve()),
        "scan": scan,
        "safe_to_apply": False,
        "next_step": "manifest에 고정된 층화 청취 검토",
    }
    atomic_write_json(args.report.resolve(), report)
    console_summary = {
        "schema_version": SCHEMA_VERSION,
        "status": report["status"],
        "year": report["year"],
        "report": str(args.report.resolve()),
        "search_sessions": scan["search_sessions"],
        "search_utterances": scan["search_utterances"],
        "affected_sessions": scan["affected_sessions"],
        "corpus_entries": scan["corpus_entries"],
        "omitted_for_review": scan["omitted_for_review"],
        "unique_corpus_source_files": scan["unique_corpus_source_files"],
        "mapping_counts": scan["mapping_counts"],
        "logical_source_gib": scan["logical_source_gib"],
        "safe_to_apply": report["safe_to_apply"],
        "next_step": report["next_step"],
    }
    print(json.dumps(console_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

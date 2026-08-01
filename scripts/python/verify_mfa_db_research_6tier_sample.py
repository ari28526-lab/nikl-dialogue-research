"""보존 MFA DB에서 연구 6-tier 표본을 재수출해 final과 독립 대조한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

from export_mfa_db_research_6tier import (
    _db_inventory,
    _session_intervals,
    load_alignment_contract,
    load_session_rows,
    open_readonly,
)
from mfa_exclusion_contract import load_contract as load_exclusion_contract
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import atomic_text_writer, atomic_write_json, file_fingerprint, now_iso, sha256_file
from research_textgrid_v2 import write_base_textgrid_from_intervals
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid

SCHEMA_VERSION = "mfa_db_research_6tier_sample_equivalence.v1"


def _sample(
    connection: sqlite3.Connection,
    *,
    year: str,
    sample_size: int,
    excluded_ids: set[str],
) -> tuple[list[tuple[int, str, str, float]], dict[str, int]]:
    best: dict[str, tuple[bytes, int, str, str, float]] = {}
    eligible = 0
    for uid, name, relative, duration in connection.execute(
        """
        SELECT u.id, f.name, f.relative_path, sf.duration
        FROM utterance u
        JOIN file f ON f.id=u.file_id
        JOIN sound_file sf ON sf.file_id=f.id
        WHERE u.ignored=0
          AND EXISTS(SELECT 1 FROM word_interval wi WHERE wi.utterance_id=u.id)
          AND EXISTS(SELECT 1 FROM phone_interval pi WHERE pi.utterance_id=u.id)
        ORDER BY u.id
        """
    ):
        name = str(name)
        if name in excluded_ids:
            continue
        session = str(relative or name.split(".", 1)[0])
        digest = hashlib.sha256(
            f"{year}\0{session}\0{name}".encode("utf-8")
        ).digest()
        candidate = (digest, int(uid), name, session, float(duration))
        if session not in best or candidate[:3] < best[session][:3]:
            best[session] = candidate
        eligible += 1
    chosen = sorted(best.values())[:sample_size]
    return (
        [(uid, name, session, duration) for _d, uid, name, session, duration in chosen],
        {
            "eligible_utterances": eligible,
            "eligible_sessions": len(best),
            "selected_utterances": len(chosen),
            "selected_sessions": len({row[3] for row in chosen}),
        },
    )


def _payload(path: Path) -> dict[str, object]:
    duration, tiers = parse_mfa_textgrid(path)
    return {
        "duration": duration,
        "tier_order": list(tiers),
        "tiers": {
            name: [list(interval) for interval in intervals]
            for name, intervals in tiers.items()
        },
    }


def verify_sample(
    *,
    db_path: Path,
    year: str,
    search_master_root: Path,
    final_root: Path,
    scratch_root: Path,
    acoustic_model: Path,
    alignment_contract: Path,
    approved_exclusions_contract: Path,
    report_path: Path,
    sample_csv_path: Path,
    sample_size: int = 24,
) -> dict[str, object]:
    started = time.monotonic()
    if scratch_root.exists() and next(scratch_root.rglob("*.TextGrid"), None):
        raise FileExistsError(f"scratch에 기존 TextGrid가 있음: {scratch_root}")
    alignment_id, alignment_data = load_alignment_contract(
        alignment_contract, year
    )
    input_id = str(alignment_data.get("lab_input_contract_id", "") or "")
    _exclusion_data, exclusions = load_exclusion_contract(
        approved_exclusions_contract,
        year=year,
        input_contract_id=input_id,
    )
    alignment_excluded = {
        uid for uid, row in exclusions.items()
        if row["exclusion_scope"] == "alignment_and_analysis"
    }
    groups = model_group_lookup(load_acoustic_meta(acoustic_model))

    connection = open_readonly(db_path)
    try:
        selected, selection_counts = _sample(
            connection,
            year=year,
            sample_size=sample_size,
            excluded_ids=alignment_excluded,
        )
        if len(selected) != sample_size:
            raise RuntimeError(
                f"선택 세션 부족: {len(selected)}/{sample_size}"
            )
        word_labels, phone_labels = _db_inventory(connection)
        grouped: dict[str, list[tuple]] = defaultdict(list)
        for uid, name, session, duration in selected:
            grouped[session].append((uid, name, duration))
        for session, utterances in sorted(grouped.items()):
            search_rows = load_session_rows(search_master_root, year, session)
            words_by_utt, phones_by_utt = _session_intervals(
                connection,
                [row[0] for row in utterances],
                word_labels,
                phone_labels,
            )
            for uid, name, duration in utterances:
                row = search_rows.get(name)
                if row is None:
                    raise RuntimeError(f"search row missing: {name}")
                words = [(b, e, label) for _iid, b, e, label in words_by_utt[uid]]
                phones = [(b, e, label) for _iid, b, e, label, _wid in phones_by_utt[uid]]
                write_base_textgrid_from_intervals(
                    scratch_root / year / session / f"{name}.TextGrid",
                    duration=duration,
                    words=words,
                    phones=phones,
                    row=row,
                    phone_mapper=lambda phone: classify_phone(
                        phone, groups
                    ).phone_class_r_auto,
                )
    finally:
        connection.close()

    comparisons: list[dict[str, object]] = []
    for _uid, name, session, _duration in selected:
        final = final_root / year / session / f"{name}.TextGrid"
        regenerated = scratch_root / year / session / f"{name}.TextGrid"
        semantic_equal = final.is_file() and _payload(final) == _payload(regenerated)
        byte_equal = (
            semantic_equal and sha256_file(final) == sha256_file(regenerated)
        )
        comparisons.append(
            {
                "year": year,
                "session": session,
                "utt_id": name,
                "status": (
                    "exact_match" if byte_equal else
                    "semantic_match" if semantic_equal else "mismatch"
                ),
                "semantic_equal": str(semantic_equal).lower(),
                "byte_equal": str(byte_equal).lower(),
                "final_path": str(final),
                "regenerated_path": str(regenerated),
                "final_sha256": sha256_file(final) if final.is_file() else "",
                "regenerated_sha256": sha256_file(regenerated),
            }
        )
    with atomic_text_writer(
        sample_csv_path.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    semantic_count = sum(row["semantic_equal"] == "true" for row in comparisons)
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success" if semantic_count == sample_size else "failed",
        "read_only_sources": True,
        "generated_at": now_iso(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "year": year,
        "input_contract_id": input_id,
        "alignment_contract_id": alignment_id,
        "selection_counts": selection_counts,
        "comparison_counts": {
            "compared": len(comparisons),
            "semantic_equal": semantic_count,
            "byte_equal": sum(row["byte_equal"] == "true" for row in comparisons),
        },
        "db": file_fingerprint(db_path.resolve()),
        "final_root": str(final_root.resolve()),
        "scratch_root": str(scratch_root.resolve()),
        "sample_csv": file_fingerprint(sample_csv_path.resolve(), with_sha256=True),
    }
    atomic_write_json(report_path.resolve(), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--final-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--alignment-contract", type=Path, required=True)
    parser.add_argument("--approved-exclusions-contract", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--sample-csv", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=24)
    args = parser.parse_args()
    report = verify_sample(
        db_path=args.db,
        year=args.year,
        search_master_root=args.search_master_root,
        final_root=args.final_root,
        scratch_root=args.scratch_root,
        acoustic_model=args.acoustic_model,
        alignment_contract=args.alignment_contract,
        approved_exclusions_contract=args.approved_exclusions_contract,
        report_path=args.report,
        sample_csv_path=args.sample_csv,
        sample_size=args.sample_size,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

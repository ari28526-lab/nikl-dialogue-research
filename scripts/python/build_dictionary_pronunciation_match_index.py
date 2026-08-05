"""Build a normalized morphology-to-dictionary-pronunciation match index.

The large pronunciation registry remains the candidate authority.  This index
stores one group per ``(morph surface, corpus POS)`` and one compact membership
row per candidate.  Corpus occurrences can therefore store a group ID instead
of repeating candidate strings or exploding one occurrence into many senses.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dictionary_pronunciation_registry import (  # noqa: E402
    atomic_gzip_text_writer,
)
from common_pronunciation_contract import PREDICATE_POS  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "dictionary_pronunciation_match_index.v1"
REGISTRY_REQUIRED = {
    "dict_pron_candidate_id",
    "headword",
    "word_stem",
    "pos_tag",
    "pron_hangul",
    "is_dictionary_attested",
    "is_legacy_fallback",
}
GROUP_FIELDS = [
    "candidate_group_id",
    "morph_surface",
    "corpus_pos",
    "match_type",
    "candidate_count",
    "dictionary_attested_count",
    "legacy_fallback_count",
    "headword_count",
    "pronunciation_count_all",
    "preferred_source_tier",
    "preferred_candidate_count",
    "preferred_pronunciation_count",
    "pronunciation_resolution_status",
]
MEMBER_FIELDS = [
    "candidate_group_id",
    "dict_pron_candidate_id",
    "member_priority",
]

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def group_identity(match_type: str, surface: str, pos: str) -> str:
    value = "\0".join((SCHEMA_VERSION, match_type, surface, pos))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_match_key(row: dict[str, str]) -> tuple[str, str, str] | None:
    pos = clean(row.get("pos_tag"))
    if not pos:
        return None
    if pos in PREDICATE_POS:
        surface = clean(row.get("word_stem"))
        match_type = "predicate_stem_exact_pos"
    else:
        surface = clean(row.get("headword"))
        match_type = "headword_exact_pos"
    if not surface:
        return None
    return surface, pos, match_type


def resolution_status(
    *, preferred_candidate_count: int, preferred_pronunciation_count: int
) -> str:
    if preferred_candidate_count == 1 and preferred_pronunciation_count == 1:
        return "unique_candidate_unique_pronunciation"
    if preferred_pronunciation_count == 1:
        return "multiple_senses_same_pronunciation"
    return "multiple_pronunciations_unresolved"


def _create_database(path: Path) -> sqlite3.Connection:
    if path.exists():
        raise FileExistsError(f"기존 임시 DB 덮어쓰기 금지: {path}")
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        CREATE TABLE members (
            candidate_group_id TEXT NOT NULL,
            morph_surface TEXT NOT NULL,
            corpus_pos TEXT NOT NULL,
            match_type TEXT NOT NULL,
            dict_pron_candidate_id TEXT NOT NULL PRIMARY KEY,
            headword TEXT NOT NULL,
            pron_hangul TEXT NOT NULL,
            is_dictionary_attested INTEGER NOT NULL,
            is_legacy_fallback INTEGER NOT NULL
        );
        """
    )
    return connection


def _load_registry(
    *, registry_path: Path, connection: sqlite3.Connection, progress_every: int
) -> Counter:
    counts: Counter = Counter()
    batch: list[tuple] = []
    with gzip.open(
        registry_path, "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        missing = REGISTRY_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"registry 필수 열 누락: {sorted(missing)}")
        for row_number, row in enumerate(reader, 1):
            counts["registry_rows"] += 1
            key = candidate_match_key(row)
            if key is None:
                counts["unindexed_missing_surface_or_pos"] += 1
                continue
            surface, pos, match_type = key
            group_id = group_identity(match_type, surface, pos)
            batch.append(
                (
                    group_id,
                    surface,
                    pos,
                    match_type,
                    clean(row.get("dict_pron_candidate_id")),
                    clean(row.get("headword")),
                    clean(row.get("pron_hangul")),
                    int(clean(row.get("is_dictionary_attested")) == "true"),
                    int(clean(row.get("is_legacy_fallback")) == "true"),
                )
            )
            if len(batch) >= 10_000:
                connection.executemany(
                    "INSERT INTO members VALUES (?,?,?,?,?,?,?,?,?)", batch
                )
                connection.commit()
                counts["indexed_candidates"] += len(batch)
                batch.clear()
            if progress_every and row_number % progress_every == 0:
                print(
                    f"[match-index] registry {row_number:,}행 · "
                    f"indexed {counts['indexed_candidates'] + len(batch):,}",
                    flush=True,
                )
    if batch:
        connection.executemany(
            "INSERT INTO members VALUES (?,?,?,?,?,?,?,?,?)", batch
        )
        connection.commit()
        counts["indexed_candidates"] += len(batch)
    connection.execute(
        "CREATE INDEX members_group_idx ON members(candidate_group_id, "
        "dict_pron_candidate_id)"
    )
    connection.commit()
    return counts


def _write_outputs(
    *, connection: sqlite3.Connection, groups_path: Path, members_path: Path
) -> Counter:
    counts: Counter = Counter()
    query = """
        SELECT candidate_group_id, morph_surface, corpus_pos, match_type,
               dict_pron_candidate_id, headword, pron_hangul,
               is_dictionary_attested, is_legacy_fallback
        FROM members
        ORDER BY candidate_group_id, dict_pron_candidate_id
    """
    with atomic_gzip_text_writer(groups_path) as group_stream, \
            atomic_gzip_text_writer(members_path) as member_stream:
        group_writer = csv.DictWriter(
            group_stream, fieldnames=GROUP_FIELDS, lineterminator="\n"
        )
        member_writer = csv.DictWriter(
            member_stream, fieldnames=MEMBER_FIELDS, lineterminator="\n"
        )
        group_writer.writeheader()
        member_writer.writeheader()
        cursor = connection.execute(query)
        for group_id, grouped in groupby(cursor, key=lambda row: row[0]):
            rows = list(grouped)
            first = rows[0]
            attested = [row for row in rows if row[7] == 1]
            fallback = [row for row in rows if row[8] == 1]
            preferred = attested if attested else fallback
            preferred_tier = (
                "dictionary_attested" if attested else "legacy_fallback_only"
            )
            all_prons = {row[6] for row in rows if row[6]}
            preferred_prons = {row[6] for row in preferred if row[6]}
            status = resolution_status(
                preferred_candidate_count=len(preferred),
                preferred_pronunciation_count=len(preferred_prons),
            )
            group_writer.writerow(
                {
                    "candidate_group_id": group_id,
                    "morph_surface": first[1],
                    "corpus_pos": first[2],
                    "match_type": first[3],
                    "candidate_count": len(rows),
                    "dictionary_attested_count": len(attested),
                    "legacy_fallback_count": len(fallback),
                    "headword_count": len({row[5] for row in rows}),
                    "pronunciation_count_all": len(all_prons),
                    "preferred_source_tier": preferred_tier,
                    "preferred_candidate_count": len(preferred),
                    "preferred_pronunciation_count": len(preferred_prons),
                    "pronunciation_resolution_status": status,
                }
            )
            counts["groups"] += 1
            counts[f"groups_{preferred_tier}"] += 1
            counts[f"groups_{status}"] += 1
            for row in rows:
                priority = (
                    "preferred"
                    if (row[7] == 1 or not attested)
                    else "retained_fallback"
                )
                member_writer.writerow(
                    {
                        "candidate_group_id": group_id,
                        "dict_pron_candidate_id": row[4],
                        "member_priority": priority,
                    }
                )
                counts["members"] += 1
                counts[f"members_{priority}"] += 1
    return counts


def build(args: argparse.Namespace) -> dict:
    registry_path = args.registry.resolve()
    registry_manifest_path = args.registry_manifest.resolve()
    output_dir = args.output_dir.resolve()
    groups_path = output_dir / "dictionary_pronunciation_match_groups.csv.gz"
    members_path = output_dir / "dictionary_pronunciation_match_group_members.csv.gz"
    manifest_path = output_dir / "dictionary_pronunciation_match_index_manifest.json"
    sqlite_path = output_dir / ".dictionary_pronunciation_match_index.sqlite.partial"

    for path in (registry_path, registry_manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    with registry_manifest_path.open("r", encoding="utf-8") as stream:
        registry_manifest = json.load(stream)
    if registry_manifest.get("status") != "success":
        raise RuntimeError("성공한 registry manifest가 아님")
    expected = registry_manifest.get("outputs", {}).get("registry", {})
    actual = file_fingerprint(registry_path, with_sha256=False)
    if any(actual.get(field) != expected.get(field) for field in ("bytes", "mtime_ns")):
        raise RuntimeError("registry가 manifest 생성 후 변경됨")

    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "inputs": {
            "registry": {**actual, "sha256": expected.get("sha256", "")},
            "registry_manifest": file_fingerprint(
                registry_manifest_path, with_sha256=True
            ),
        },
        "outputs": {
            "groups": str(groups_path),
            "members": str(members_path),
            "manifest": str(manifest_path),
        },
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if any(path.exists() for path in (groups_path, members_path, manifest_path, sqlite_path)):
        raise FileExistsError(f"기존 match index 산출물 덮어쓰기 금지: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    connection = _create_database(sqlite_path)
    try:
        load_counts = _load_registry(
            registry_path=registry_path,
            connection=connection,
            progress_every=args.progress_every,
        )
        output_counts = _write_outputs(
            connection=connection,
            groups_path=groups_path,
            members_path=members_path,
        )
    finally:
        connection.close()
    if output_counts["members"] != load_counts["indexed_candidates"]:
        raise RuntimeError("match group member coverage 불일치")
    sqlite_path.unlink()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "dictionary_pronunciation_match_index",
        "status": "success",
        "recorded_at": now_iso(),
        "policy": {
            "predicate_match": "word_stem + exact POS",
            "other_match": "headword + exact POS",
            "sense_selection": "none; all candidates retained",
            "attested_precedence": "preferred; fallback retained but not competing",
            "mfa_dictionary_activation": False,
        },
        "inputs": preflight["inputs"],
        "counts": {**dict(load_counts), **dict(output_counts)},
        "outputs": {
            "groups": file_fingerprint(groups_path, with_sha256=True),
            "members": file_fingerprint(members_path, with_sha256=True),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] pronunciation match index: {output_counts['groups']:,} groups, "
        f"{output_counts['members']:,} members",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--registry", type=Path, required=True)
    result.add_argument("--registry-manifest", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--progress-every", type=int, default=250_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.progress_every < 0:
        raise ValueError("--progress-every는 0 이상이어야 함")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

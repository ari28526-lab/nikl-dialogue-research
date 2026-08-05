"""Build compact, non-selecting summaries for pronunciation match groups.

The registry and group-member tables remain authoritative.  This derived table
collects distinct preferred pronunciations and stable candidate references so
that occurrence-level audit views can show dictionary evidence without
expanding every corpus morph occurrence by dictionary sense.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
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
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "dictionary_pronunciation_group_summaries.v1"
REGISTRY_FIELDS = {
    "dict_pron_candidate_id",
    "headword",
    "word_stem",
    "pos_tag",
    "sense_no",
    "urimal_id",
    "stdict_target_code",
    "stdict_sense_code",
    "pron_hangul",
    "pron_roman_search",
    "source_name",
    "source_field",
}
GROUP_FIELDS = {
    "candidate_group_id",
    "morph_surface",
    "corpus_pos",
    "match_type",
    "preferred_source_tier",
    "preferred_candidate_count",
    "preferred_pronunciation_count",
    "pronunciation_resolution_status",
}
MEMBER_FIELDS = {
    "candidate_group_id",
    "dict_pron_candidate_id",
    "member_priority",
}
OUTPUT_FIELDS = [
    "candidate_group_id",
    "morph_surface",
    "corpus_pos",
    "match_type",
    "preferred_source_tier",
    "preferred_candidate_count",
    "preferred_pronunciation_count",
    "pronunciation_resolution_status",
    "preferred_candidate_ids_json",
    "preferred_headwords_json",
    "preferred_sense_refs_json",
    "preferred_pron_hangul_json",
    "preferred_pron_roman_search_json",
    "preferred_source_refs_json",
    "retained_fallback_candidate_ids_json",
    "retained_fallback_pron_hangul_json",
    "retained_fallback_pron_roman_search_json",
]

csv.field_size_limit(20_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def json_values(values) -> str:
    return json.dumps(
        sorted({clean(value) for value in values if clean(value)}),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sense_ref(row: tuple) -> str:
    # Query columns are documented in _write_summaries.
    parts = [
        f"headword={clean(row[3])}",
        f"pos={clean(row[5])}",
        f"sense={clean(row[6]) or 'NA'}",
    ]
    for name, index in (
        ("urimal", 7),
        ("stdict_target", 8),
        ("stdict_sense", 9),
    ):
        if clean(row[index]):
            parts.append(f"{name}={clean(row[index])}")
    return ";".join(parts)


def source_ref(row: tuple) -> str:
    return ":".join(
        value for value in (clean(row[12]), clean(row[13])) if value
    )


def _load_success_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("status") != "success":
        raise RuntimeError(f"successful manifest required: {path}")
    return payload


def _check_manifest_file(path: Path, expected: dict, label: str) -> dict:
    actual = file_fingerprint(path, with_sha256=False)
    if any(
        actual.get(field) != expected.get(field)
        for field in ("bytes", "mtime_ns")
    ):
        raise RuntimeError(f"{label} changed after manifest creation")
    return {**actual, "sha256": expected.get("sha256", "")}


def _create_database(path: Path) -> sqlite3.Connection:
    if path.exists():
        raise FileExistsError(path)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        CREATE TABLE registry (
            candidate_id TEXT PRIMARY KEY,
            headword TEXT NOT NULL,
            word_stem TEXT NOT NULL,
            pos_tag TEXT NOT NULL,
            sense_no TEXT NOT NULL,
            urimal_id TEXT NOT NULL,
            stdict_target_code TEXT NOT NULL,
            stdict_sense_code TEXT NOT NULL,
            pron_hangul TEXT NOT NULL,
            pron_roman_search TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_field TEXT NOT NULL
        );
        CREATE TABLE groups (
            group_id TEXT PRIMARY KEY,
            morph_surface TEXT NOT NULL,
            corpus_pos TEXT NOT NULL,
            match_type TEXT NOT NULL,
            preferred_source_tier TEXT NOT NULL,
            preferred_candidate_count INTEGER NOT NULL,
            preferred_pronunciation_count INTEGER NOT NULL,
            pronunciation_resolution_status TEXT NOT NULL
        );
        CREATE TABLE members (
            group_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            member_priority TEXT NOT NULL,
            PRIMARY KEY (group_id, candidate_id)
        );
        """
    )
    return connection


def _load_csv(
    *,
    path: Path,
    required: set[str],
    insert_sql: str,
    transform,
    connection: sqlite3.Connection,
    counter_name: str,
    counts: Counter,
    progress_every: int,
) -> None:
    batch: list[tuple] = []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"{counter_name} required fields missing: {sorted(missing)}")
        for row_number, row in enumerate(reader, 1):
            batch.append(transform(row))
            if len(batch) >= 10_000:
                connection.executemany(insert_sql, batch)
                counts[counter_name] += len(batch)
                batch.clear()
            if progress_every and row_number % progress_every == 0:
                print(
                    f"[group-summary] {counter_name} {row_number:,} rows",
                    flush=True,
                )
    if batch:
        connection.executemany(insert_sql, batch)
        counts[counter_name] += len(batch)
    connection.commit()


def _write_summaries(
    *, connection: sqlite3.Connection, output_path: Path, counts: Counter
) -> None:
    missing_registry = connection.execute(
        "SELECT COUNT(*) FROM members m LEFT JOIN registry r "
        "ON r.candidate_id=m.candidate_id WHERE r.candidate_id IS NULL"
    ).fetchone()[0]
    if missing_registry:
        raise RuntimeError(f"member candidates missing from registry: {missing_registry}")
    missing_groups = connection.execute(
        "SELECT COUNT(*) FROM members m LEFT JOIN groups g "
        "ON g.group_id=m.group_id WHERE g.group_id IS NULL"
    ).fetchone()[0]
    if missing_groups:
        raise RuntimeError(f"member groups missing from group table: {missing_groups}")

    query = """
        SELECT m.group_id, m.candidate_id, m.member_priority,
               r.headword, r.word_stem, r.pos_tag, r.sense_no, r.urimal_id,
               r.stdict_target_code, r.stdict_sense_code, r.pron_hangul,
               r.pron_roman_search, r.source_name, r.source_field
        FROM members m JOIN registry r ON r.candidate_id=m.candidate_id
        ORDER BY m.group_id, m.member_priority DESC, m.candidate_id
    """
    group_rows = {
        row[0]: row
        for row in connection.execute(
            "SELECT group_id,morph_surface,corpus_pos,match_type,"
            "preferred_source_tier,preferred_candidate_count,"
            "preferred_pronunciation_count,pronunciation_resolution_status "
            "FROM groups"
        )
    }
    with atomic_gzip_text_writer(output_path) as destination:
        writer = csv.DictWriter(
            destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for group_id, grouped in groupby(
            connection.execute(query), key=lambda row: row[0]
        ):
            rows = list(grouped)
            preferred = [row for row in rows if row[2] == "preferred"]
            fallback = [
                row for row in rows if row[2] == "retained_fallback"
            ]
            group = group_rows.pop(group_id, None)
            if group is None:
                raise RuntimeError(f"unknown group during summary: {group_id}")
            if len(preferred) != int(group[5]):
                raise RuntimeError(f"preferred candidate count mismatch: {group_id}")
            writer.writerow(
                {
                    "candidate_group_id": group_id,
                    "morph_surface": group[1],
                    "corpus_pos": group[2],
                    "match_type": group[3],
                    "preferred_source_tier": group[4],
                    "preferred_candidate_count": group[5],
                    "preferred_pronunciation_count": group[6],
                    "pronunciation_resolution_status": group[7],
                    "preferred_candidate_ids_json": json_values(
                        row[1] for row in preferred
                    ),
                    "preferred_headwords_json": json_values(
                        row[3] for row in preferred
                    ),
                    "preferred_sense_refs_json": json_values(
                        sense_ref(row) for row in preferred
                    ),
                    "preferred_pron_hangul_json": json_values(
                        row[10] for row in preferred
                    ),
                    "preferred_pron_roman_search_json": json_values(
                        row[11] for row in preferred
                    ),
                    "preferred_source_refs_json": json_values(
                        source_ref(row) for row in preferred
                    ),
                    "retained_fallback_candidate_ids_json": json_values(
                        row[1] for row in fallback
                    ),
                    "retained_fallback_pron_hangul_json": json_values(
                        row[10] for row in fallback
                    ),
                    "retained_fallback_pron_roman_search_json": json_values(
                        row[11] for row in fallback
                    ),
                }
            )
            counts["summary_groups"] += 1
            counts["preferred_candidates"] += len(preferred)
            counts["retained_fallback_candidates"] += len(fallback)
    if group_rows:
        raise RuntimeError(f"groups without members in summary: {len(group_rows)}")


def build(args: argparse.Namespace) -> dict:
    registry = args.registry.resolve()
    registry_manifest_path = args.registry_manifest.resolve()
    groups = args.match_groups.resolve()
    members = args.match_members.resolve()
    match_manifest_path = args.match_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output = output_dir / "dictionary_pronunciation_group_summaries.csv.gz"
    manifest_path = output_dir / "dictionary_pronunciation_group_summaries_manifest.json"
    sqlite_path = output_dir / ".dictionary_pronunciation_group_summaries.sqlite.partial"

    registry_manifest = _load_success_manifest(registry_manifest_path)
    match_manifest = _load_success_manifest(match_manifest_path)
    inputs = {
        "registry": _check_manifest_file(
            registry,
            registry_manifest["outputs"]["registry"],
            "registry",
        ),
        "registry_manifest": file_fingerprint(
            registry_manifest_path, with_sha256=True
        ),
        "match_groups": _check_manifest_file(
            groups, match_manifest["outputs"]["groups"], "match groups"
        ),
        "match_members": _check_manifest_file(
            members, match_manifest["outputs"]["members"], "match members"
        ),
        "match_manifest": file_fingerprint(
            match_manifest_path, with_sha256=True
        ),
    }
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "inputs": inputs,
        "outputs": {"summaries": str(output), "manifest": str(manifest_path)},
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if any(path.exists() for path in (output, manifest_path, sqlite_path)):
        raise FileExistsError(f"existing group summary output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    counts: Counter = Counter()
    connection = _create_database(sqlite_path)
    try:
        _load_csv(
            path=registry,
            required=REGISTRY_FIELDS,
            insert_sql="INSERT INTO registry VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            transform=lambda row: (
                clean(row["dict_pron_candidate_id"]),
                clean(row["headword"]),
                clean(row["word_stem"]),
                clean(row["pos_tag"]),
                clean(row["sense_no"]),
                clean(row["urimal_id"]),
                clean(row["stdict_target_code"]),
                clean(row["stdict_sense_code"]),
                clean(row["pron_hangul"]),
                clean(row["pron_roman_search"]),
                clean(row["source_name"]),
                clean(row["source_field"]),
            ),
            connection=connection,
            counter_name="registry_rows",
            counts=counts,
            progress_every=args.progress_every,
        )
        _load_csv(
            path=groups,
            required=GROUP_FIELDS,
            insert_sql="INSERT INTO groups VALUES (?,?,?,?,?,?,?,?)",
            transform=lambda row: (
                clean(row["candidate_group_id"]),
                clean(row["morph_surface"]),
                clean(row["corpus_pos"]),
                clean(row["match_type"]),
                clean(row["preferred_source_tier"]),
                int(row["preferred_candidate_count"]),
                int(row["preferred_pronunciation_count"]),
                clean(row["pronunciation_resolution_status"]),
            ),
            connection=connection,
            counter_name="group_rows",
            counts=counts,
            progress_every=args.progress_every,
        )
        _load_csv(
            path=members,
            required=MEMBER_FIELDS,
            insert_sql="INSERT INTO members VALUES (?,?,?)",
            transform=lambda row: (
                clean(row["candidate_group_id"]),
                clean(row["dict_pron_candidate_id"]),
                clean(row["member_priority"]),
            ),
            connection=connection,
            counter_name="member_rows",
            counts=counts,
            progress_every=args.progress_every,
        )
        connection.execute("CREATE INDEX members_candidate_idx ON members(candidate_id)")
        connection.commit()
        _write_summaries(
            connection=connection, output_path=output, counts=counts
        )
    finally:
        connection.close()
    if sqlite_path.exists():
        sqlite_path.unlink()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "dictionary_pronunciation_group_summaries",
        "status": "success",
        "recorded_at": now_iso(),
        "policy": {
            "authority": "registry + match group members",
            "sense_selection": "none",
            "preferred_pronunciation_selection": "distinct values retained",
            "retained_fallback": "reported separately",
            "mfa_dictionary_activation": False,
        },
        "inputs": inputs,
        "counts": dict(sorted(counts.items())),
        "outputs": {"summaries": file_fingerprint(output, with_sha256=True)},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] pronunciation group summaries: {counts['summary_groups']:,}",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--registry", type=Path, required=True)
    result.add_argument("--registry-manifest", type=Path, required=True)
    result.add_argument("--match-groups", type=Path, required=True)
    result.add_argument("--match-members", type=Path, required=True)
    result.add_argument("--match-manifest", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--progress-every", type=int, default=250_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build an overlay-aware, reproducible target-candidate manifest.

The builder streams frozen annual gzip tables, applies declarative conditions,
joins RC0 status and the RC1 exception-only active view, and writes references
to WAV/TextGrid assets.  It never decides whether a phonological process was
realized and never edits or copies the source assets.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERY_SET = (
    PROJECT_ROOT
    / "config"
    / "target_queries"
    / "db_v1_target_manifest_pilot_20260818.json"
)
DEFAULT_MORPH_ROOT = Path(
    r"D:\10_LAYERS\09_morph_search_v3_staging\morph_search_v3_20260801"
)
DEFAULT_RC0_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_0_0_rc0_20260815"
)
DEFAULT_ACTIVE_VIEW_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_active_view_contract_v1_20260818"
)
DEFAULT_R3_ROOT = Path(r"D:\mfa_eojeol\r3\common_pron_mfa_r3_20260809")
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "db_v1_target_manifest_pilot_20260818"
)

SUPPORTED_TABLES = {
    "utterance_master_v2",
    "morph_tokens",
    "morph_units",
    "morph_boundaries",
    "orth_eojeol_tokens",
    "eojeol_tokens",
    "symbol_readings",
}
SUPPORTED_OPERATORS = {"eq", "in", "nonempty", "truthy", "contains", "regex"}

OUTPUT_FIELDS = [
    "study_id",
    "query_set_id",
    "query_id",
    "query_version",
    "query_role",
    "year",
    "utt_id",
    "target_occurrence_id",
    "matched_table",
    "occurrence_index",
    "session_id",
    "speaker_id",
    "base_form",
    "active_form",
    "active_form_source",
    "base_orth_roman_v2",
    "active_orth_roman_v2",
    "base_primary_status",
    "base_status_family",
    "recovery_status",
    "recovery_family",
    "active_annotation_source",
    "active_annotation_revision",
    "wav_path",
    "base_textgrid_path",
    "curated_textgrid_path",
    "active_textgrid_path",
    "target_xmin",
    "target_xmax",
    "timing_status",
    "quality_flags_json",
    "inclusion_status",
    "interpretation_limit",
    "match_evidence_json",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object expected: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def condition_matches(row: Mapping[str, str], condition: Mapping[str, Any]) -> bool:
    field = str(condition["field"])
    operator = str(condition["op"])
    if operator not in SUPPORTED_OPERATORS:
        raise RuntimeError(f"unsupported query operator: {operator}")
    if field not in row:
        raise RuntimeError(f"query field is absent from source table: {field}")
    value = str(row.get(field, ""))
    if operator == "eq":
        return value == str(condition.get("value", ""))
    if operator == "in":
        return value in {str(item) for item in condition.get("values", [])}
    if operator == "nonempty":
        return bool(value.strip())
    if operator == "truthy":
        return truthy(value)
    if operator == "contains":
        return str(condition.get("value", "")) in value
    if operator == "regex":
        return re.search(str(condition.get("pattern", "")), value) is not None
    raise AssertionError(operator)


def row_matches(row: Mapping[str, str], conditions: Iterable[Mapping[str, Any]]) -> bool:
    return all(condition_matches(row, condition) for condition in conditions)


def read_csv_map(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[tuple[int, str], dict[str, str]] = {}
    for row in rows:
        item_key = (int(row["year"]), row["utt_id"])
        if item_key in result:
            raise RuntimeError(f"duplicate active-view key: {item_key}")
        result[item_key] = row
    return result


def validate_query_set(value: dict[str, Any]) -> None:
    if value.get("schema_version") != "nikl_dialogue_target_query_set.v1":
        raise RuntimeError("unsupported query-set schema")
    seen: set[str] = set()
    for query in value.get("queries", []):
        query_id = str(query.get("query_id", ""))
        if not query_id or query_id in seen:
            raise RuntimeError(f"blank or duplicate query_id: {query_id!r}")
        seen.add(query_id)
        if query.get("source_table") not in SUPPORTED_TABLES:
            raise RuntimeError(f"unsupported source table: {query.get('source_table')}")
        if not query.get("years"):
            raise RuntimeError(f"query has no years: {query_id}")
        if not query.get("conditions"):
            raise RuntimeError(f"query has no conditions: {query_id}")


def scan_query_hits(
    *, morph_root: Path, query: Mapping[str, Any]
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    hits: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    source_table = str(query["source_table"])
    for year_value in query["years"]:
        year = int(year_value)
        annual_root = morph_root / str(year) / "annual_tables"
        manifest_path = annual_root / "YEAR_MANIFEST.json"
        manifest = load_json(manifest_path)
        if manifest.get("status") != "success":
            raise RuntimeError(f"morph annual table is not successful: {year}")
        manifest_key = "master" if source_table == "utterance_master_v2" else source_table
        table_record = manifest["tables"].get(manifest_key)
        if not table_record:
            raise RuntimeError(f"table absent from annual manifest: {year} {source_table}")
        table_path = annual_root / f"{source_table}.csv.gz"
        if table_path.stat().st_size != table_record["bytes"]:
            raise RuntimeError(f"annual table byte mismatch: {table_path}")
        limit = int(query.get("max_occurrences_per_year", 0) or 0)
        year_hits = 0
        with gzip.open(table_path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                if not row_matches(row, query["conditions"]):
                    continue
                copied = dict(row)
                copied["__year"] = str(year)
                hits.append(copied)
                year_hits += 1
                if limit and year_hits >= limit:
                    break
        if year_hits == 0:
            raise RuntimeError(f"query returned no pilot hits: {query['query_id']} {year}")
        sources.append(
            {
                "year": year,
                "table": source_table,
                "path": str(table_path),
                "bytes": table_record["bytes"],
                "declared_sha256": table_record["sha256"],
                "annual_manifest_sha256": sha256_file(manifest_path),
                "pilot_hit_rows": year_hits,
                "scan_stopped_at_limit": bool(limit and year_hits >= limit),
            }
        )
    return hits, sources


def select_rows_by_id(
    path: Path, ids: set[str]
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            utt_id = row["utt_id"]
            if utt_id in ids:
                if utt_id in result:
                    raise RuntimeError(f"duplicate utt_id in source table: {utt_id}")
                result[utt_id] = row
                if len(result) == len(ids):
                    break
    missing = ids - set(result)
    if missing:
        raise RuntimeError(f"selected IDs missing from table {path}: {sorted(missing)[:5]}")
    return result


def build_rows(
    *,
    query_set: Mapping[str, Any],
    query: Mapping[str, Any],
    hits: list[dict[str, str]],
    masters: Mapping[str, Mapping[str, str]],
    ledgers: Mapping[str, Mapping[str, str]],
    active_exceptions: Mapping[tuple[int, str], Mapping[str, str]],
    r3_root: Path,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen_occurrences: set[str] = set()
    index_field = str(query["occurrence_index_field"])
    for hit in hits:
        year = int(hit["__year"])
        utt_id = hit["utt_id"]
        occurrence_index = hit.get(index_field, "")
        occurrence_id = (
            f"{query['query_id']}:{year}:{utt_id}:{occurrence_index}"
        )
        if occurrence_id in seen_occurrences:
            raise RuntimeError(f"duplicate target occurrence: {occurrence_id}")
        seen_occurrences.add(occurrence_id)
        master = masters[utt_id]
        ledger = ledgers[utt_id]
        exception = active_exceptions.get((year, utt_id))
        session_id = master["session_id"]
        wav_path = r3_root / "corpus" / str(year) / session_id / f"{utt_id}.wav"
        base_tg_candidate = (
            r3_root
            / "research_6tier"
            / str(year)
            / session_id
            / f"{utt_id}.TextGrid"
        )
        base_tg = (
            str(base_tg_candidate)
            if truthy(ledger["textgrid_available"])
            else ""
        )
        if exception and exception["active_annotation_source"] == "curated":
            active_source = "curated"
            active_form = exception["active_transcript"]
            active_roman = exception["active_orth_roman_v2"]
            curated_tg = exception["active_textgrid_path"]
            active_tg = curated_tg
            active_revision = exception["active_annotation_revision"]
        else:
            active_source = "base"
            active_form = master["form"]
            active_roman = master["form_roman_v2"]
            curated_tg = ""
            active_tg = base_tg
            active_revision = ""
        flags = [
            f"base_status:{ledger['primary_status']}",
            f"active_annotation:{active_source}",
        ]
        if master.get("align_warn"):
            flags.append(f"align_warn:{master['align_warn']}")
        if exception:
            if exception.get("phone_layer_status") == "d9_reference_only_not_adopted":
                flags.append("d9_phone_reference_only")
            if exception.get("morph_enrichment_status", "").startswith("pending_"):
                flags.append("curated_morphology_pending")
        if not base_tg and not curated_tg:
            flags.append("active_textgrid_unavailable")
        asset_ready = wav_path.is_file() and bool(active_tg) and Path(active_tg).is_file()
        result.append(
            {
                "study_id": query_set["study_id"],
                "query_set_id": query_set["query_set_id"],
                "query_id": query["query_id"],
                "query_version": query["query_version"],
                "query_role": query["query_role"],
                "year": year,
                "utt_id": utt_id,
                "target_occurrence_id": occurrence_id,
                "matched_table": query["source_table"],
                "occurrence_index": occurrence_index,
                "session_id": session_id,
                "speaker_id": master["speaker_id"],
                "base_form": master["form"],
                "active_form": active_form,
                "active_form_source": active_source,
                "base_orth_roman_v2": master["form_roman_v2"],
                "active_orth_roman_v2": active_roman,
                "base_primary_status": ledger["primary_status"],
                "base_status_family": ledger["status_family"],
                "recovery_status": exception["recovery_status"] if exception else "",
                "recovery_family": exception["recovery_family"] if exception else "",
                "active_annotation_source": active_source,
                "active_annotation_revision": active_revision,
                "wav_path": str(wav_path),
                "base_textgrid_path": base_tg,
                "curated_textgrid_path": curated_tg,
                "active_textgrid_path": active_tg,
                "target_xmin": "",
                "target_xmax": "",
                "timing_status": "pending_textgrid_interval_link",
                "quality_flags_json": json.dumps(flags, ensure_ascii=False),
                "inclusion_status": (
                    "candidate_ready_for_manual_realization_review"
                    if asset_ready
                    else "candidate_metadata_only_pending_alignment_or_recovery"
                ),
                "interpretation_limit": query["interpretation"],
                "match_evidence_json": json.dumps(
                    {k: v for k, v in hit.items() if not k.startswith("__")},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(
    *,
    query_set_path: Path,
    morph_root: Path,
    rc0_root: Path,
    active_view_root: Path,
    r3_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    query_set = load_json(query_set_path)
    validate_query_set(query_set)
    active_manifest_path = active_view_root / "ACTIVE_VIEW_MANIFEST.json"
    active_manifest = load_json(active_manifest_path)
    if active_manifest["status"] != "materialized_exception_only_contract":
        raise RuntimeError("active-view contract is not materialized")
    active_exceptions = read_csv_map(
        active_view_root / "ACTIVE_RECOVERY_EXCEPTIONS.csv"
    )
    partial = output_root.with_name(output_root.name + ".partial")
    if output_root.exists() or partial.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_root}")

    all_rows: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []
    query_counts: dict[str, int] = {}
    for query in query_set["queries"]:
        hits, sources = scan_query_hits(morph_root=morph_root, query=query)
        all_sources.extend({"query_id": query["query_id"], **source} for source in sources)
        by_year: dict[int, set[str]] = {}
        for hit in hits:
            by_year.setdefault(int(hit["__year"]), set()).add(hit["utt_id"])
        masters: dict[str, dict[str, str]] = {}
        ledgers: dict[str, dict[str, str]] = {}
        for year, ids in by_year.items():
            annual = morph_root / str(year) / "annual_tables"
            masters.update(
                select_rows_by_id(annual / "utterance_master_v2.csv.gz", ids)
            )
            ledgers.update(
                select_rows_by_id(
                    rc0_root / "ledgers" / f"{year}_utterance_status.csv.gz", ids
                )
            )
        rows = build_rows(
            query_set=query_set,
            query=query,
            hits=hits,
            masters=masters,
            ledgers=ledgers,
            active_exceptions=active_exceptions,
            r3_root=r3_root,
        )
        query_counts[str(query["query_id"])] = len(rows)
        all_rows.extend(rows)

    partial.mkdir(parents=True)
    try:
        manifest_csv = partial / "TARGET_CANDIDATES.csv"
        query_copy = partial / "QUERY_SET.json"
        readme_path = partial / "README.md"
        write_csv(manifest_csv, all_rows)
        query_copy.write_text(
            json.dumps(query_set, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        readme_path.write_text(
            "# DB v1 target manifest pilot\n\n"
            "This pilot proves declarative candidate search and RC0+RC1 active "
            "annotation precedence. It does not judge phonological realization. "
            "Target times remain blank until a separate TextGrid occurrence-link "
            "step. WAV and TextGrid assets are referenced, not copied or edited.\n",
            encoding="utf-8",
        )
        files = []
        for path in (manifest_csv, query_copy, readme_path):
            files.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        manifest = {
            "schema_version": "nikl_dialogue_target_manifest_build.v1",
            "status": "pilot_candidates_built_no_realization_judgement",
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "query_set_sha256": sha256_file(query_set_path),
            "active_view_manifest_sha256": sha256_file(active_manifest_path),
            "source_release_id": "nikl_dialogue_research_db_v1_0_0_rc0_20260815",
            "active_sidecar_id": active_manifest["rc1_release_id"],
            "counts": {
                "queries": len(query_set["queries"]),
                "candidate_rows": len(all_rows),
                "candidate_utterances": len({(row["year"], row["utt_id"]) for row in all_rows}),
                "curated_rows": sum(row["active_annotation_source"] == "curated" for row in all_rows),
            },
            "query_counts": query_counts,
            "sources": all_sources,
            "files": files,
            "safety": {
                "realization_judgement_performed": False,
                "target_times_claimed": False,
                "source_assets_copied": False,
                "source_assets_modified": False,
                "mfa_run": False,
                "base_or_sidecar_modified": False,
            },
        }
        manifest_path = partial / "TARGET_MANIFEST_BUILD.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        partial.replace(output_root)
        return manifest
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-set", type=Path, default=DEFAULT_QUERY_SET)
    parser.add_argument("--morph-root", type=Path, default=DEFAULT_MORPH_ROOT)
    parser.add_argument("--rc0-root", type=Path, default=DEFAULT_RC0_ROOT)
    parser.add_argument("--active-view-root", type=Path, default=DEFAULT_ACTIVE_VIEW_ROOT)
    parser.add_argument("--r3-root", type=Path, default=DEFAULT_R3_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = build(
            query_set_path=args.query_set.resolve(),
            morph_root=args.morph_root.resolve(),
            rc0_root=args.rc0_root.resolve(),
            active_view_root=args.active_view_root.resolve(),
            r3_root=args.r3_root.resolve(),
            output_root=args.output_root.resolve(),
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

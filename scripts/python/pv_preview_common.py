"""Shared safety and schema helpers for the seven-phenomena PV-A pilot.

The helpers are deliberately standard-library only except where an existing
project linker is imported by a caller.  They never edit source corpus assets
and never infer phonological realization.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pipeline_common import atomic_text_writer, now_iso, sha256_file

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = (
    PROJECT_ROOT
    / "config"
    / "target_queries"
    / "pv_preview_boundary_20260819.json"
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
    / "pv_seven_phenomena_20260819"
)

EXPECTED_HEADERS: dict[str, tuple[str, ...]] = {
    "morph_units": (
        "utt_id",
        "year",
        "eojeol_idx",
        "morph_idx_in_eojeol",
        "morph_idx_in_utterance",
        "morph_surface",
        "pos",
        "unit_idx_in_morph",
        "unit_count_in_morph",
        "unit_idx_in_utterance",
        "unit_surface",
        "unit_type",
        "onset_jamo",
        "nucleus_jamo",
        "coda_jamo",
    ),
    "morph_boundaries": (
        "utt_id",
        "year",
        "boundary_idx_in_utterance",
        "boundary_scope",
        "left_eojeol_idx",
        "left_morph_surface",
        "left_pos",
        "right_eojeol_idx",
        "right_morph_surface",
        "right_pos",
        "left_unit_type",
        "left_coda_jamo",
        "right_unit_type",
        "right_onset_jamo",
        "right_nucleus_jamo",
        "right_onset_zero",
    ),
    "orth_eojeol_tokens": (
        "utt_id",
        "year",
        "orth_eojeol_idx",
        "orth_eojeol_form",
    ),
    "utterance_master_v2": (
        "utt_id",
        "year",
        "session_id",
        "utt_seq",
        "dialogue_id",
        "speaker_id",
        "form",
        "start",
        "end",
        "dur",
        "note",
    ),
}

PHENOMENON_LABELS = {
    "PT": "경음화",
    "NAN": "ㄴ앞 비음화",
    "NAL": "ㄹ앞 비음화",
    "NI": "ㄴ삽입",
    "LLN": "ㄴㄹ·ㄹㄴ",
    "VH": "모음조화",
    "HIA": "모음충돌",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object expected: {path}")
    return value


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"existing output is never overwritten: {path}")
    with atomic_text_writer(path, encoding="utf-8", newline="\n") as (stream, _):
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def atomic_write_text(path: Path, text: str, *, bom: bool = False) -> None:
    if path.exists():
        raise FileExistsError(f"existing output is never overwritten: {path}")
    encoding = "utf-8-sig" if bom else "utf-8"
    with atomic_text_writer(path, encoding=encoding, newline="\n") as (stream, _):
        stream.write(text)


def atomic_write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    if path.exists():
        raise FileExistsError(f"existing output is never overwritten: {path}")
    with atomic_text_writer(path, encoding="utf-8-sig", newline="") as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=list(fieldnames),
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def validate_config(config: Mapping[str, Any]) -> None:
    if config.get("schema_version") != "nikl_dialogue_target_query_set.v1":
        raise RuntimeError("unsupported PV query schema")
    safety = config.get("safety", {})
    row_cap = int(safety.get("max_rows_scanned_per_table_year", 0))
    candidate_cap = int(
        safety.get("max_materialized_candidates_per_query_year", 0)
    )
    if row_cap != 200_000:
        raise RuntimeError(f"approved hard row cap must be 200000, got {row_cap}")
    if candidate_cap <= 0:
        raise RuntimeError("materialized candidate cap must be positive")
    allocation = config.get("pilot_allocation", {})
    years = [int(value) for value in allocation.get("years", [])]
    if years != list(range(2020, 2026)):
        raise RuntimeError(f"PV years must be 2020..2025: {years}")
    if int(allocation.get("unique_physical_packages_per_year", 0)) != 30:
        raise RuntimeError("approved annual physical package quota must be 30")
    phenomena = list(allocation.get("phenomenon_order", []))
    if phenomena != list(PHENOMENON_LABELS):
        raise RuntimeError(f"unexpected phenomenon order: {phenomena}")
    exceptions = allocation.get("approved_primary_quota_exceptions", {})
    if not isinstance(exceptions, Mapping):
        raise RuntimeError("approved quota exceptions must be an object")
    for year_text, exception in exceptions.items():
        try:
            exception_year = int(year_text)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid approved quota exception year: {year_text}") from exc
        if exception_year not in years or str(exception_year) != str(year_text):
            raise RuntimeError(f"approved quota exception outside pilot years: {year_text}")
        if not isinstance(exception, Mapping) or not str(exception.get("reason", "")).strip():
            raise RuntimeError(f"approved quota exception lacks reason: {year_text}")
        deltas = exception.get("deltas", {})
        if not isinstance(deltas, Mapping) or not deltas:
            raise RuntimeError(f"approved quota exception lacks deltas: {year_text}")
        unknown = sorted(set(deltas) - set(phenomena))
        if unknown:
            raise RuntimeError(
                f"approved quota exception has unknown phenomena: {year_text} {unknown}"
            )
        if any(type(value) is not int for value in deltas.values()):
            raise RuntimeError(f"approved quota deltas must be integers: {year_text}")
        if sum(deltas.values()) != 0:
            raise RuntimeError(f"approved quota deltas must sum to zero: {year_text}")
    for year in years:
        annual_primary_quotas(config, year)
    seen: set[str] = set()
    for query in config.get("queries", []):
        query_id = str(query.get("query_id", ""))
        if not query_id.startswith("PV_") or query_id in seen:
            raise RuntimeError(f"invalid or duplicate preview query id: {query_id}")
        seen.add(query_id)
        if query.get("query_role") != "preview_environment_sweep":
            raise RuntimeError(f"non-preview query role: {query_id}")
        if query.get("phenomenon_code") not in PHENOMENON_LABELS:
            raise RuntimeError(f"unknown phenomenon: {query_id}")
        if int(query.get("max_occurrences_per_year", 0)) > candidate_cap:
            raise RuntimeError(f"query candidate cap exceeds safety cap: {query_id}")


def annual_table_contract(
    morph_root: Path, year: int, table: str
) -> tuple[Path, dict[str, Any], Path]:
    annual = morph_root / str(year) / "annual_tables"
    manifest_path = annual / "YEAR_MANIFEST.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "success":
        raise RuntimeError(f"annual source manifest is not successful: {year}")
    manifest_key = "master" if table == "utterance_master_v2" else table
    record = manifest.get("tables", {}).get(manifest_key)
    if not record:
        raise RuntimeError(f"annual table contract missing: {year} {table}")
    table_path = annual / f"{table}.csv.gz"
    if not table_path.is_file():
        raise FileNotFoundError(table_path)
    if table_path.stat().st_size != int(record["bytes"]):
        raise RuntimeError(f"annual table byte mismatch: {table_path}")
    return table_path, dict(record), manifest_path


def read_header(path: Path) -> list[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        try:
            return next(reader)
        except StopIteration as exc:
            raise RuntimeError(f"empty CSV: {path}") from exc


def validate_header(path: Path, table: str) -> list[str]:
    header = read_header(path)
    missing = [name for name in EXPECTED_HEADERS[table] if name not in header]
    if missing:
        raise RuntimeError(f"{table} measured header missing {missing}: {path}")
    return header


def source_receipt(
    path: Path,
    record: Mapping[str, Any],
    manifest_path: Path,
    *,
    rows_scanned: int = 0,
    stopped_at_row_cap: bool = False,
) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "declared_sha256": str(record.get("sha256", "")),
        "annual_manifest_path": str(manifest_path),
        "annual_manifest_sha256": sha256_file(manifest_path),
        "rows_scanned": rows_scanned,
        "scan_stopped_at_hard_row_cap": stopped_at_row_cap,
    }


def stable_rank(seed: str, *parts: object) -> str:
    payload = "|".join([seed, *(str(part) for part in parts)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def physical_occurrence_ref(
    table: str, year: int | str, utt_id: str, index: str
) -> str:
    return f"{table}:{year}:{utt_id}:{index}"


def session_from_utt(utt_id: str) -> str:
    return utt_id.split(".", 1)[0]


def numeric_utt_seq(value: object) -> tuple[int, str]:
    text = str(value or "").strip()
    try:
        return int(text), text
    except ValueError:
        return 2**63 - 1, text


def annual_primary_quotas(config: Mapping[str, Any], year: int) -> dict[str, int]:
    allocation = config["pilot_allocation"]
    base = int(allocation["base_primary_quota_per_phenomenon_year"])
    quotas = {code: base for code in allocation["phenomenon_order"]}
    for code in allocation["rotating_extra_primary_phenomena"][str(year)]:
        quotas[code] += 1
    exception = allocation.get("approved_primary_quota_exceptions", {}).get(
        str(year), {}
    )
    for code, delta in exception.get("deltas", {}).items():
        quotas[code] += int(delta)
    negative = {code: value for code, value in quotas.items() if value < 0}
    if negative:
        raise RuntimeError(f"annual quota contains negative values: {year} {negative}")
    expected = int(allocation["unique_physical_packages_per_year"])
    if sum(quotas.values()) != expected:
        raise RuntimeError(f"annual quota does not sum to {expected}: {year} {quotas}")
    return quotas


def scope_quotas(
    weights: Mapping[str, int], total: int, *, rotation: int = 0
) -> dict[str, int]:
    """Largest-remainder allocation with deterministic rotating tie breaks."""

    items = list(weights.items())
    weight_sum = sum(int(value) for _, value in items)
    if total < 0 or weight_sum <= 0:
        raise ValueError("invalid scope allocation")
    exact = {key: total * int(value) / weight_sum for key, value in items}
    result = {key: int(value) for key, value in exact.items()}
    remaining = total - sum(result.values())
    order_index = {key: index for index, (key, _) in enumerate(items)}
    ranked = sorted(
        result,
        key=lambda key: (
            -(exact[key] - result[key]),
            (order_index[key] - rotation) % len(items),
        ),
    )
    for key in ranked[:remaining]:
        result[key] += 1
    return result


def capped_rows_by_id(
    path: Path,
    identifiers: set[str],
    *,
    max_rows: int,
) -> tuple[dict[str, dict[str, str]], int]:
    """Read selected utt rows without silently crossing the approved row cap."""

    result: dict[str, dict[str, str]] = {}
    opener = gzip.open if path.suffix == ".gz" else open
    rows_scanned = 0
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if "utt_id" not in (reader.fieldnames or []):
            raise RuntimeError(f"utt_id missing: {path}")
        for row in reader:
            rows_scanned += 1
            utt_id = row["utt_id"]
            if utt_id in identifiers:
                if utt_id in result:
                    raise RuntimeError(f"duplicate utt_id: {path} {utt_id}")
                result[utt_id] = dict(row)
                if len(result) == len(identifiers):
                    break
            if rows_scanned >= max_rows:
                break
    missing = identifiers - set(result)
    if missing:
        raise RuntimeError(
            f"selected IDs not found within {max_rows} rows of {path}: "
            f"{sorted(missing)[:5]}"
        )
    return result, rows_scanned


def capped_rows_by_id_allow_missing(
    path: Path,
    identifiers: set[str],
    *,
    max_rows: int,
) -> tuple[dict[str, dict[str, str]], int, set[str]]:
    """Read a capped ID subset and return, rather than discard, missing IDs.

    This variant is for broad exploratory candidate sweeps whose source layer
    can legitimately contain utterances absent from a downstream release
    ledger.  Callers must materialize an explicit status for every missing ID.
    """

    result: dict[str, dict[str, str]] = {}
    opener = gzip.open if path.suffix == ".gz" else open
    rows_scanned = 0
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if "utt_id" not in (reader.fieldnames or []):
            raise RuntimeError(f"utt_id missing: {path}")
        for row in reader:
            rows_scanned += 1
            utt_id = row["utt_id"]
            if utt_id in identifiers:
                if utt_id in result:
                    raise RuntimeError(f"duplicate utt_id: {path} {utt_id}")
                result[utt_id] = dict(row)
                if len(result) == len(identifiers):
                    break
            if rows_scanned >= max_rows:
                break
    return result, rows_scanned, identifiers - set(result)


def read_active_exceptions(active_view_root: Path) -> dict[tuple[int, str], dict[str, str]]:
    manifest_path = active_view_root / "ACTIVE_VIEW_MANIFEST.json"
    manifest = load_json(manifest_path)
    if manifest.get("status") != "materialized_exception_only_contract":
        raise RuntimeError("active-view contract is not materialized")
    path = active_view_root / "ACTIVE_RECOVERY_EXCEPTIONS.csv"
    result: dict[tuple[int, str], dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (int(row["year"]), row["utt_id"])
            if key in result:
                raise RuntimeError(f"duplicate active exception: {key}")
            result[key] = dict(row)
    return result


def manifest_file_record(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def count_by(rows: Iterable[Mapping[str, Any]], *fields: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        key = "|".join(str(row.get(field, "")) for field in fields)
        counts[key] += 1
    return dict(sorted(counts.items()))


def base_build_receipt(config_path: Path) -> dict[str, Any]:
    return {
        "recorded_at": now_iso(),
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "safety": {
            "realization_judgement_performed": False,
            "source_assets_modified": False,
            "mfa_run": False,
            "koina_run": False,
            "wav2vec2_run": False,
        },
    }


def require_under(path: Path, root: Path) -> None:
    resolved = path.resolve()
    allowed = root.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError(f"output must remain under {allowed}: {resolved}") from exc


def promote_directory(partial: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"existing output is never overwritten: {destination}")
    if partial.parent.resolve() != destination.parent.resolve():
        raise RuntimeError("directory promotion must stay on the same volume")
    os.replace(partial, destination)

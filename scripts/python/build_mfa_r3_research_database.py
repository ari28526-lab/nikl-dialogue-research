"""Build the normalized r3 pronunciation/search database before MFA.

The builder never edits the frozen morphology tables, the adopted dictionary,
raw audio, MFA databases, or TextGrids.  It materializes two missing links:

* one release-level pronunciation type catalog; and
* annual utterance routing plus reference-eojeol occurrence tables.

Annual work is checkpointed by the already frozen morphology-search shards.
An existing checkpoint is reused only when its source and output SHA-256
fingerprints still match.  Partial files are preserved for diagnosis.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from realign_eojeol_build_corpus import MISSING, form_to_lab_mapping  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_r3_research_database_build.v1"
CATALOG_SCHEMA = "mfa_r3_pronunciation_type_catalog.v1"
YEAR_SCHEMA = "mfa_r3_pronunciation_occurrence_year.v1"
SHARD_SCHEMA = "mfa_r3_pronunciation_occurrence_shard.v1"

CATALOG_EXTRA_FIELDS = (
    "pronunciation_release_id",
    "pronunciation_contract_id",
    "release_selection_class",
    "release_selected_variant_count",
    "release_selected_pron_phones_json",
    "release_selected_pron_roman_json",
    "release_selection_status",
    "release_selection_source",
    "release_selection_reason",
)
SCOPE_FIELDS = (
    "year",
    "utt_id",
    "session_id",
    "pronunciation_release_id",
    "pronunciation_contract_id",
    "year_input_contract_id",
    "alignment_scope",
    "alignment_layer_expected",
    "pron_reference_form",
    "pron_reference_n_eojeol",
    "lab_n_eojeol",
    "pron_reference_status",
    "routing_class",
    "hold_tokens_json",
    "policy_tokens_json",
    "unknown_tokens_json",
    "pre_mfa_reason_codes_json",
)
OCCURRENCE_FIELDS = (
    "year",
    "utt_id",
    "session_id",
    "reference_eojeol_idx",
    "reference_eojeol_count",
    "reference_eojeol",
    "pronunciation_token",
    "included_in_mfa",
    "mfa_word_idx",
    "orth_eojeol_idx_if_count_aligned",
    "morph_eojeol_idx_if_count_aligned",
    "coordinate_link_status",
    "pronunciation_release_id",
    "pronunciation_contract_id",
    "year_input_contract_id",
    "release_selection_class",
    "alignment_scope",
    "alignment_layer_expected",
)

csv.field_size_limit(20_000_000)


def clean(value: object) -> str:
    return str(value or "").strip()


def csv_bool(value: bool) -> str:
    return "true" if value else "false"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def verify_fingerprint(record: Mapping[str, object], path: Path) -> bool:
    return bool(
        path.is_file()
        and Path(clean(record.get("path"))).resolve() == path.resolve()
        and int(record.get("bytes", -1)) == path.stat().st_size
        and clean(record.get("sha256")).lower() == sha256_file(path).lower()
    )


@contextmanager
def deterministic_gzip_writer(path: Path, fields: tuple[str, ...] | list[str]) -> Iterator[csv.DictWriter]:
    """Write an atomic, deterministic gzip CSV and preserve failures."""

    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{uuid.uuid4().hex}.partial")
    raw = open(partial, "xb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n")
    try:
        writer.writeheader()
        yield writer
        text.flush()
        text.detach()
        gz.close()
        raw.flush()
        os.fsync(raw.fileno())
        raw.close()
        os.replace(partial, path)
    except BaseException:
        try:
            text.close()
        except Exception:
            pass
        try:
            raw.close()
        except Exception:
            pass
        raise


def load_policy(config_path: Path) -> dict:
    policy = load_json(config_path)
    if (
        policy.get("schema_version") != "mfa_r3_research_database.v1"
        or policy.get("status") != "approved_fail_closed_before_first_r3_alignment"
    ):
        raise RuntimeError("r3 research database policy identity differs")
    return policy


def validate_frozen_inputs(policy: Mapping[str, object]) -> dict[str, Path]:
    paths = {name: resolve_config_path(clean(value)) for name, value in policy["paths"].items()}
    required = (
        "release_root",
        "readiness_table",
        "selected_projection",
        "release_manifest",
        "release_gate",
        "morph_search_root",
        "year_input_contract_root",
    )
    missing = [name for name in required if not paths[name].exists()]
    if missing:
        raise RuntimeError("missing frozen r3 inputs: " + ", ".join(missing))
    release = load_json(paths["release_manifest"])
    gate = load_json(paths["release_gate"])
    if (
        clean(release.get("release_id")) != clean(policy.get("release_id"))
        or clean(release.get("pronunciation_contract_id"))
        != clean(policy.get("pronunciation_contract_id"))
        or clean(gate.get("status")) != "adopted"
        or gate.get("allowed_release_ids") != [clean(policy.get("release_id"))]
    ):
        raise RuntimeError("adopted r3 release identity differs")
    return paths


def selection_class(row: Mapping[str, str]) -> str:
    status = clean(row.get("planning_status"))
    if status.startswith("candidate_"):
        if clean(row.get("planning_zero_fallback_hold")) != "false":
            raise RuntimeError(f"candidate also marked hold: {row.get('token')}")
        return "selected"
    if clean(row.get("planning_zero_fallback_hold")) == "true":
        return "zero_fallback_hold"
    if clean(row.get("planning_requires_policy_decision")) == "true" or status.startswith("policy_"):
        return "explicit_policy_hold"
    raise RuntimeError(f"unclassified readiness token: {row.get('token')}")


def projection_groups(path: Path) -> Iterator[tuple[str, list[dict[str, str]]]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        current = ""
        rows: list[dict[str, str]] = []
        previous = ""
        for row in reader:
            token = clean(row.get("token"))
            if not token:
                raise RuntimeError("empty token in selected projection")
            if current and token != current:
                if token <= previous:
                    raise RuntimeError("selected projection is not strictly token-sorted")
                yield current, rows
                previous = current
                rows = []
            current = token
            rows.append(row)
        if current:
            yield current, rows


def validate_projection_group(token: str, rows: list[dict[str, str]]) -> dict[str, str]:
    expected = len(rows)
    indices = [int(row["variant_index"]) for row in rows]
    if indices != list(range(1, expected + 1)) or any(int(row["variant_count"]) != expected for row in rows):
        raise RuntimeError(f"variant sequence mismatch: {token}")
    invariant_fields = (
        "source_candidate_status",
        "source_candidate_source",
        "source_candidate_reason",
        "selection_status",
        "selection_source",
        "selection_reason",
    )
    if any(len({clean(row[field]) for row in rows}) != 1 for field in invariant_fields):
        raise RuntimeError(f"variant provenance mismatch: {token}")
    if any(clean(row.get("final_selection")) != "true" for row in rows):
        raise RuntimeError(f"non-final row in release projection: {token}")
    return {
        "release_selected_variant_count": str(expected),
        "release_selected_pron_phones_json": json.dumps(
            [clean(row["selected_pron_phones_mfa"]) for row in rows], ensure_ascii=False
        ),
        "release_selected_pron_roman_json": json.dumps(
            [clean(row["selected_pron_roman"]) for row in rows], ensure_ascii=False
        ),
        "release_selection_status": clean(rows[0]["selection_status"]),
        "release_selection_source": clean(rows[0]["selection_source"]),
        "release_selection_reason": clean(rows[0]["selection_reason"]),
    }


def build_catalog(*, policy: Mapping[str, object], paths: Mapping[str, Path]) -> dict:
    output_root = paths["output_root"]
    catalog_path = output_root / "pronunciation_type_catalog.csv.gz"
    manifest_path = output_root / "TYPE_CATALOG_MANIFEST.json"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        if (
            manifest.get("schema_version") == CATALOG_SCHEMA
            and manifest.get("status") == "success"
            and verify_fingerprint(manifest["output"], catalog_path)
            and verify_fingerprint(manifest["inputs"]["readiness_table"], paths["readiness_table"])
            and verify_fingerprint(manifest["inputs"]["selected_projection"], paths["selected_projection"])
        ):
            return manifest
        raise RuntimeError("existing type catalog checkpoint differs; no overwrite performed")

    projection_iter = iter(projection_groups(paths["selected_projection"]))
    next_projection = next(projection_iter, None)
    counts: Counter[str] = Counter()
    previous_token = ""
    with gzip.open(paths["readiness_table"], "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        source_fields = list(reader.fieldnames or ())
        fields = source_fields + list(CATALOG_EXTRA_FIELDS)
        with deterministic_gzip_writer(catalog_path, fields) as writer:
            for row in reader:
                token = clean(row.get("token"))
                if not token or (previous_token and token <= previous_token):
                    raise RuntimeError("readiness table token order/uniqueness differs")
                previous_token = token
                klass = selection_class(row)
                selected = {
                    "release_selected_variant_count": "0",
                    "release_selected_pron_phones_json": "[]",
                    "release_selected_pron_roman_json": "[]",
                    "release_selection_status": "not_selected",
                    "release_selection_source": "",
                    "release_selection_reason": clean(row.get("planning_reason")),
                }
                if klass == "selected":
                    if next_projection is None or next_projection[0] != token:
                        raise RuntimeError(f"selected token missing from release projection: {token}")
                    selected = validate_projection_group(token, next_projection[1])
                    counts["selected_variant_rows"] += len(next_projection[1])
                    next_projection = next(projection_iter, None)
                elif next_projection is not None and next_projection[0] == token:
                    raise RuntimeError(f"hold token unexpectedly projected: {token}")
                writer.writerow(
                    {
                        **row,
                        "pronunciation_release_id": policy["release_id"],
                        "pronunciation_contract_id": policy["pronunciation_contract_id"],
                        "release_selection_class": klass,
                        **selected,
                    }
                )
                counts["types"] += 1
                counts[klass] += 1
    if next_projection is not None:
        raise RuntimeError(f"projection contains extra token: {next_projection[0]}")
    expected = policy["invariants"]
    actual = {
        "types": counts["types"],
        "selected": counts["selected"],
        "selected_variant_rows": counts["selected_variant_rows"],
        "zero_fallback_hold": counts["zero_fallback_hold"],
        "explicit_policy_hold": counts["explicit_policy_hold"],
    }
    required = {
        "types": int(expected["canonical_types"]),
        "selected": int(expected["selected_types"]),
        "selected_variant_rows": int(expected["selected_variant_rows"]),
        "zero_fallback_hold": int(expected["zero_fallback_hold_types"]),
        "explicit_policy_hold": int(expected["explicit_policy_hold_types"]),
    }
    if actual != required:
        raise RuntimeError(f"type catalog partition mismatch: {actual} != {required}")
    manifest = {
        "schema_version": CATALOG_SCHEMA,
        "status": "success",
        "recorded_at": now_iso(),
        "release_id": policy["release_id"],
        "pronunciation_contract_id": policy["pronunciation_contract_id"],
        "counts": actual,
        "inputs": {
            "readiness_table": file_fingerprint(paths["readiness_table"], with_sha256=True),
            "selected_projection": file_fingerprint(paths["selected_projection"], with_sha256=True),
            "release_manifest": file_fingerprint(paths["release_manifest"], with_sha256=True),
            "release_gate": file_fingerprint(paths["release_gate"], with_sha256=True),
        },
        "output": file_fingerprint(catalog_path, with_sha256=True),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def read_id_rows(path: Path, year: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            utt_id = clean(row.get("utt_id"))
            if clean(row.get("year")) != year or not utt_id or utt_id in result:
                raise RuntimeError(f"invalid/duplicate exact ID row: {path}: {utt_id}")
            result[utt_id] = row
    return result


def load_type_classes(catalog_path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with gzip.open(catalog_path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            token = clean(row.get("token"))
            if token in result:
                raise RuntimeError(f"duplicate type catalog token: {token}")
            result[token] = clean(row.get("release_selection_class"))
    return result


def source_reference_form(row: Mapping[str, str]) -> str:
    form = clean(row.get("form"))
    reference = clean(row.get("pron_reference_form"))
    return form if reference in MISSING else reference


def coordinate_links(row: Mapping[str, str], index: int, reference_count: int) -> tuple[str, str, str]:
    def integer(name: str) -> int | None:
        value = clean(row.get(name))
        return int(value) if value.isdigit() else None

    orth_count = integer("orth_eojeol_count_structured")
    morph_count = integer("morph_eojeol_count_structured")
    orth_idx = str(index) if orth_count == reference_count else ""
    morph_idx = str(index) if morph_count == reference_count else ""
    if orth_idx and morph_idx:
        status = "reference_orth_morph_counts_equal"
    elif orth_idx:
        status = "reference_orth_counts_equal_morph_unlinked"
    elif morph_idx:
        status = "reference_morph_counts_equal_orth_unlinked"
    else:
        status = "reference_only_no_silent_index_guess"
    return orth_idx, morph_idx, status


def build_year_shard(
    *,
    year: str,
    shard_root: Path,
    destination: Path,
    policy: Mapping[str, object],
    year_contract_id: str,
    type_classes: Mapping[str, str],
    scopes: Mapping[str, tuple[str, Mapping[str, str]]],
) -> dict:
    source_path = shard_root / "tables" / "utterance_master_v2.csv.gz"
    source_manifest = shard_root / "SHARD_MANIFEST.json"
    manifest_path = destination / "SHARD_MANIFEST.json"
    scope_path = destination / "utterance_pronunciation_scope.csv.gz"
    occurrence_path = destination / "pronunciation_occurrences.csv.gz"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        if (
            manifest.get("schema_version") == SHARD_SCHEMA
            and manifest.get("status") == "success"
            and clean(manifest.get("year_input_contract_id")) == year_contract_id
            and verify_fingerprint(manifest["inputs"]["source_master"], source_path)
            and verify_fingerprint(manifest["outputs"]["utterance_scope"], scope_path)
            and verify_fingerprint(manifest["outputs"]["occurrences"], occurrence_path)
        ):
            return manifest
        raise RuntimeError(f"existing shard checkpoint differs: {destination}")

    counts: Counter[str] = Counter()
    seen: set[str] = set()
    with gzip.open(source_path, "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        with deterministic_gzip_writer(scope_path, SCOPE_FIELDS) as scope_writer, deterministic_gzip_writer(
            occurrence_path, OCCURRENCE_FIELDS
        ) as occurrence_writer:
            for row in reader:
                utt_id = clean(row.get("utt_id"))
                session_id = clean(row.get("session_id"))
                if clean(row.get("year")) != year or not utt_id or utt_id in seen:
                    raise RuntimeError(f"invalid shard utterance: {utt_id}")
                seen.add(utt_id)
                scope_record = scopes.get(utt_id)
                if scope_record is None:
                    raise RuntimeError(f"utterance absent from year input partition: {utt_id}")
                alignment_scope, detail = scope_record
                if clean(detail.get("session_id")) and clean(detail.get("session_id")) != session_id:
                    raise RuntimeError(f"session mismatch for {utt_id}")
                reference = source_reference_form(row)
                mappings = form_to_lab_mapping(reference)
                declared = clean(row.get("pron_reference_n_eojeol"))
                if declared.isdigit() and int(declared) != len(mappings):
                    raise RuntimeError(f"reference eojeol count mismatch: {utt_id}")
                reference_count = len(mappings)
                lab_count = sum(bool(item["included_in_mfa"]) for item in mappings)
                expected = alignment_scope == "r3_safe_body_input"
                scope_writer.writerow(
                    {
                        "year": year,
                        "utt_id": utt_id,
                        "session_id": session_id,
                        "pronunciation_release_id": policy["release_id"],
                        "pronunciation_contract_id": policy["pronunciation_contract_id"],
                        "year_input_contract_id": year_contract_id,
                        "alignment_scope": alignment_scope,
                        "alignment_layer_expected": csv_bool(expected),
                        "pron_reference_form": reference,
                        "pron_reference_n_eojeol": reference_count,
                        "lab_n_eojeol": lab_count,
                        "pron_reference_status": clean(row.get("pron_reference_status")),
                        "routing_class": clean(detail.get("routing_class")),
                        "hold_tokens_json": clean(detail.get("hold_tokens_json")) or "[]",
                        "policy_tokens_json": clean(detail.get("policy_tokens_json")) or "[]",
                        "unknown_tokens_json": clean(detail.get("unknown_tokens_json")) or "[]",
                        "pre_mfa_reason_codes_json": clean(detail.get("reason_codes_json")) or "[]",
                    }
                )
                counts["utterances"] += 1
                counts[f"scope_{alignment_scope}"] += 1
                for item in mappings:
                    index = int(item["source_eojeol_index"]) + 1
                    token = clean(item["lab_token"])
                    included = bool(item["included_in_mfa"])
                    if included:
                        klass = type_classes.get(token, "")
                        if not klass:
                            raise RuntimeError(f"unknown nonempty LAB token: {utt_id}: {token}")
                    else:
                        klass = "not_applicable_empty_lab"
                    if alignment_scope in {"r3_safe_body_input", "pre_mfa_excluded"} and included and klass != "selected":
                        raise RuntimeError(f"safe-body occurrence is not selected: {utt_id}: {token}: {klass}")
                    orth_idx, morph_idx, link_status = coordinate_links(row, index, reference_count)
                    occurrence_writer.writerow(
                        {
                            "year": year,
                            "utt_id": utt_id,
                            "session_id": session_id,
                            "reference_eojeol_idx": index,
                            "reference_eojeol_count": reference_count,
                            "reference_eojeol": clean(item["source_token"]),
                            "pronunciation_token": token,
                            "included_in_mfa": csv_bool(included),
                            "mfa_word_idx": (
                                str(int(item["mfa_word_index"]) + 1) if included else ""
                            ),
                            "orth_eojeol_idx_if_count_aligned": orth_idx,
                            "morph_eojeol_idx_if_count_aligned": morph_idx,
                            "coordinate_link_status": link_status,
                            "pronunciation_release_id": policy["release_id"],
                            "pronunciation_contract_id": policy["pronunciation_contract_id"],
                            "year_input_contract_id": year_contract_id,
                            "release_selection_class": klass,
                            "alignment_scope": alignment_scope,
                            "alignment_layer_expected": csv_bool(expected),
                        }
                    )
                    counts["occurrences"] += 1
                    counts[f"type_{klass}"] += 1

    manifest = {
        "schema_version": SHARD_SCHEMA,
        "status": "success",
        "recorded_at": now_iso(),
        "year": year,
        "shard": shard_root.name,
        "release_id": policy["release_id"],
        "year_input_contract_id": year_contract_id,
        "counts": dict(counts),
        "inputs": {
            "source_master": file_fingerprint(source_path, with_sha256=True),
            "source_shard_manifest": file_fingerprint(source_manifest, with_sha256=True),
        },
        "outputs": {
            "utterance_scope": file_fingerprint(scope_path, with_sha256=True),
            "occurrences": file_fingerprint(occurrence_path, with_sha256=True),
        },
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def merge_shard_tables(shards: list[Path], name: str, fields: tuple[str, ...], destination: Path) -> int:
    count = 0
    with deterministic_gzip_writer(destination, fields) as writer:
        for shard in shards:
            path = shard / name
            with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if tuple(reader.fieldnames or ()) != fields:
                    raise RuntimeError(f"shard field order mismatch: {path}")
                for row in reader:
                    writer.writerow(row)
                    count += 1
    return count


def build_year(*, year: str, policy: Mapping[str, object], paths: Mapping[str, Path], catalog: Mapping[str, object]) -> dict:
    if year not in tuple(str(value) for value in policy["scope_years"]):
        raise RuntimeError(f"year outside r3 scope: {year}")
    year_contract_root = paths["year_input_contract_root"] / year
    year_contract_path = year_contract_root / f"YEAR_INPUT_CONTRACT_{year}.json"
    year_contract = load_json(year_contract_path)
    year_contract_id = clean(year_contract.get("year_input_contract_id"))
    if (
        clean(year_contract.get("release_id")) != clean(policy["release_id"])
        or clean(year_contract.get("pronunciation_contract_id")) != clean(policy["pronunciation_contract_id"])
        or clean(year_contract.get("year")) != year
        or not year_contract_id
    ):
        raise RuntimeError("year input contract identity differs")

    expected_path = year_contract_root / f"expected_mfa_input_ids_{year}.csv.gz"
    excluded_path = year_contract_root / f"pre_mfa_exclusion_ids_{year}.csv.gz"
    followup_path = year_contract_root / f"pronunciation_followup_ids_{year}.csv.gz"
    safe_path = year_contract_root / f"pronunciation_safe_ids_{year}.csv.gz"
    expected = read_id_rows(expected_path, year)
    excluded = read_id_rows(excluded_path, year)
    followup = read_id_rows(followup_path, year)
    safe = read_id_rows(safe_path, year)
    if set(safe) != set(expected) | set(excluded) or set(expected) & set(excluded):
        raise RuntimeError("pronunciation-safe exact-ID partition differs")
    if set(safe) & set(followup):
        raise RuntimeError("safe/followup exact-ID sets overlap")
    scopes: dict[str, tuple[str, Mapping[str, str]]] = {}
    scopes.update({key: ("r3_safe_body_input", value) for key, value in expected.items()})
    scopes.update({key: ("pre_mfa_excluded", value) for key, value in excluded.items()})
    scopes.update({key: ("pronunciation_followup", value) for key, value in followup.items()})

    catalog_path = Path(clean(catalog["output"]["path"])).resolve()
    type_classes = load_type_classes(catalog_path)
    source_year = paths["morph_search_root"] / year
    shard_sources = sorted(
        (path for path in (source_year / "shards").glob("shard_*") if path.is_dir()),
        key=lambda path: path.name,
    )
    if not shard_sources:
        raise RuntimeError(f"no frozen morphology shards: {source_year}")
    year_root = paths["output_root"] / year
    manifest_path = year_root / f"YEAR_DATABASE_MANIFEST_{year}.json"
    scope_path = year_root / "utterance_pronunciation_scope.csv.gz"
    occurrence_path = year_root / "pronunciation_occurrences.csv.gz"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        if (
            manifest.get("schema_version") == YEAR_SCHEMA
            and manifest.get("status") == "success_pending_independent_audit"
            and clean(manifest.get("year_input_contract_id")) == year_contract_id
            and verify_fingerprint(manifest["outputs"]["utterance_scope"], scope_path)
            and verify_fingerprint(manifest["outputs"]["occurrences"], occurrence_path)
            and verify_fingerprint(manifest["inputs"]["type_catalog"], catalog_path)
        ):
            return manifest
        raise RuntimeError("existing annual research database differs; no overwrite performed")

    checkpoint_roots: list[Path] = []
    aggregate: Counter[str] = Counter()
    for index, source_shard in enumerate(shard_sources, 1):
        destination = year_root / "checkpoints" / source_shard.name
        manifest = build_year_shard(
            year=year,
            shard_root=source_shard,
            destination=destination,
            policy=policy,
            year_contract_id=year_contract_id,
            type_classes=type_classes,
            scopes=scopes,
        )
        aggregate.update({key: int(value) for key, value in manifest["counts"].items()})
        checkpoint_roots.append(destination)
        print(f"[{year}] pronunciation DB shard {index}/{len(shard_sources)}: {source_shard.name}", flush=True)

    if aggregate["utterances"] != len(scopes):
        raise RuntimeError(f"annual utterance accounting differs: {aggregate['utterances']} != {len(scopes)}")
    merged_scope = merge_shard_tables(
        checkpoint_roots, "utterance_pronunciation_scope.csv.gz", SCOPE_FIELDS, scope_path
    )
    merged_occurrences = merge_shard_tables(
        checkpoint_roots, "pronunciation_occurrences.csv.gz", OCCURRENCE_FIELDS, occurrence_path
    )
    if merged_scope != aggregate["utterances"] or merged_occurrences != aggregate["occurrences"]:
        raise RuntimeError("annual merge count differs from shard checkpoints")
    manifest = {
        "schema_version": YEAR_SCHEMA,
        "status": "success_pending_independent_audit",
        "recorded_at": now_iso(),
        "year": year,
        "release_id": policy["release_id"],
        "pronunciation_contract_id": policy["pronunciation_contract_id"],
        "year_input_contract_id": year_contract_id,
        "counts": dict(aggregate),
        "checkpoint_count": len(checkpoint_roots),
        "inputs": {
            "type_catalog": file_fingerprint(catalog_path, with_sha256=True),
            "year_input_contract": file_fingerprint(year_contract_path, with_sha256=True),
            "expected_ids": file_fingerprint(expected_path, with_sha256=True),
            "pre_mfa_excluded_ids": file_fingerprint(excluded_path, with_sha256=True),
            "pronunciation_followup_ids": file_fingerprint(followup_path, with_sha256=True),
            "pronunciation_safe_ids": file_fingerprint(safe_path, with_sha256=True),
        },
        "outputs": {
            "utterance_scope": file_fingerprint(scope_path, with_sha256=True),
            "occurrences": file_fingerprint(occurrence_path, with_sha256=True),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "mfa_r3_research_database_v1.json",
    )
    parser.add_argument("--year", choices=("2020", "2021", "2022", "2023", "2024", "2025"))
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    policy = load_policy(args.config.resolve())
    paths = validate_frozen_inputs(policy)
    if args.preflight_only:
        print(
            f"[GO] r3 research DB preflight: release={policy['release_id']} "
            f"year={args.year or 'catalog-only'} output={paths['output_root']}"
        )
        return 0
    catalog = build_catalog(policy=policy, paths=paths)
    print(f"[OK] type catalog: {catalog['counts']['types']:,} types", flush=True)
    if args.catalog_only:
        return 0
    if not args.year:
        raise RuntimeError("--year is required unless --catalog-only is used")
    manifest = build_year(year=args.year, policy=policy, paths=paths, catalog=catalog)
    print(
        f"[OK] {args.year} pronunciation DB: "
        f"utterances={manifest['counts']['utterances']:,}, "
        f"occurrences={manifest['counts']['occurrences']:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

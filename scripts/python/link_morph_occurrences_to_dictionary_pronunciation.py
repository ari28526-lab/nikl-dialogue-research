"""Link annual morph occurrences to normalized pronunciation candidate groups."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dictionary_pronunciation_registry import (  # noqa: E402
    atomic_gzip_text_writer,
)
from common_pronunciation_contract import PUNCTUATION_POS  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "morph_dictionary_pronunciation_occurrences.v1"
MORPH_REQUIRED = {
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_idx_in_utterance",
    "morph_surface",
    "pos",
    "has_literal",
    "has_standalone_jamo",
}
GROUP_REQUIRED = {
    "candidate_group_id",
    "morph_surface",
    "corpus_pos",
    "match_type",
    "candidate_count",
    "preferred_source_tier",
    "preferred_candidate_count",
    "preferred_pronunciation_count",
    "pronunciation_resolution_status",
}
OUTPUT_FIELDS = [
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_idx_in_utterance",
    "morph_surface",
    "pos",
    "candidate_group_id",
    "dict_match_status",
    "match_type",
    "candidate_count",
    "preferred_source_tier",
    "preferred_candidate_count",
    "preferred_pronunciation_count",
    "pronunciation_resolution_status",
    "sense_match_status",
]

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("status") != "success":
        raise RuntimeError(f"성공한 {label} manifest가 아님: {path}")
    return payload


def _verify_manifest_file(
    *, path: Path, expected: dict, label: str
) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = file_fingerprint(path, with_sha256=False)
    if int(actual["bytes"]) != int(expected["bytes"]):
        raise RuntimeError(f"{label} bytes가 manifest와 다름")
    return {**actual, "sha256": expected.get("sha256", "")}


def load_groups(path: Path) -> tuple[dict[tuple[str, str], dict], set[str]]:
    groups: dict[tuple[str, str], dict] = {}
    surfaces: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = GROUP_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"match group 필수 열 누락: {sorted(missing)}")
        for row in reader:
            surface = clean(row.get("morph_surface"))
            pos = clean(row.get("corpus_pos"))
            key = (surface, pos)
            if not surface or not pos or key in groups:
                raise RuntimeError(f"비어 있거나 중복된 match group key: {key}")
            groups[key] = row
            surfaces.add(surface)
    if not groups:
        raise RuntimeError("match group가 비어 있음")
    return groups, surfaces


def classify_occurrence(
    row: dict[str, str],
    *,
    groups: dict[tuple[str, str], dict],
    surfaces: set[str],
) -> tuple[str, dict | None]:
    surface = clean(row.get("morph_surface"))
    pos = clean(row.get("pos"))
    group = groups.get((surface, pos))
    if group is not None:
        return "matched_exact_surface_pos", group
    if pos in PUNCTUATION_POS:
        return "not_applicable_punctuation", None
    if clean(row.get("has_literal")) == "True" or clean(
        row.get("has_standalone_jamo")
    ) == "True":
        return "not_applicable_nonstandard_surface", None
    if not surface or not pos:
        return "unresolved_empty_surface_or_pos", None
    if surface in surfaces:
        return "surface_found_pos_mismatch", None
    return "dictionary_surface_not_found", None


def build(args: argparse.Namespace) -> dict:
    morph_path = args.morph_tokens.resolve()
    year_manifest_path = args.year_manifest.resolve()
    groups_path = args.match_groups.resolve()
    match_manifest_path = args.match_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_path = output_dir / "morph_dictionary_pron_occurrences.csv.gz"
    manifest_path = output_dir / "morph_dictionary_pron_occurrences_manifest.json"

    year_manifest = _load_json(year_manifest_path, "morph year")
    match_manifest = _load_json(match_manifest_path, "pronunciation match")
    if str(year_manifest.get("year")) != args.year:
        raise RuntimeError("요청 연도와 morph year manifest 연도가 다름")
    morph_expected = year_manifest.get("tables", {}).get("morph_tokens")
    group_expected = match_manifest.get("outputs", {}).get("groups")
    if not morph_expected or not group_expected:
        raise RuntimeError("입력 manifest fingerprint 누락")
    morph_fp = _verify_manifest_file(
        path=morph_path, expected=morph_expected, label="morph_tokens"
    )
    group_fp = _verify_manifest_file(
        path=groups_path, expected=group_expected, label="match_groups"
    )
    with gzip.open(
        morph_path, "rt", encoding="utf-8-sig", newline=""
    ) as stream:
        header = next(csv.reader(stream), [])
    missing = MORPH_REQUIRED - set(header)
    if missing:
        raise RuntimeError(f"morph_tokens 필수 열 누락: {sorted(missing)}")

    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "year": args.year,
        "inputs": {
            "morph_tokens": morph_fp,
            "year_manifest": file_fingerprint(
                year_manifest_path, with_sha256=True
            ),
            "match_groups": group_fp,
            "match_manifest": file_fingerprint(
                match_manifest_path, with_sha256=True
            ),
        },
        "expected_full_rows": int(morph_expected["rows"]),
        "max_rows": args.max_rows,
        "outputs": {
            "occurrences": str(output_path),
            "manifest": str(manifest_path),
        },
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError(f"기존 occurrence 산출물 덮어쓰기 금지: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    groups, surfaces = load_groups(groups_path)
    started = time.perf_counter()
    counts: Counter = Counter()
    with gzip.open(
        morph_path, "rt", encoding="utf-8-sig", newline=""
    ) as source, atomic_gzip_text_writer(output_path) as destination:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(
            destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for row_number, row in enumerate(reader, 1):
            if args.max_rows is not None and row_number > args.max_rows:
                break
            if clean(row.get("year")) != args.year:
                raise RuntimeError(
                    f"morph_tokens 내부 연도 불일치 row={row_number}"
                )
            status, group = classify_occurrence(
                row, groups=groups, surfaces=surfaces
            )
            output = {
                field: clean(row.get(field))
                for field in (
                    "utt_id",
                    "year",
                    "eojeol_idx",
                    "morph_idx_in_eojeol",
                    "morph_idx_in_utterance",
                    "morph_surface",
                    "pos",
                )
            }
            output["dict_match_status"] = status
            if group is not None:
                for field in (
                    "candidate_group_id",
                    "match_type",
                    "candidate_count",
                    "preferred_source_tier",
                    "preferred_candidate_count",
                    "preferred_pronunciation_count",
                    "pronunciation_resolution_status",
                ):
                    output[field] = clean(group.get(field))
                output["sense_match_status"] = "corpus_sense_unavailable"
            else:
                output["sense_match_status"] = "not_linked"
            writer.writerow(output)
            counts["rows"] += 1
            counts[f"status_{status}"] += 1
            if group is not None:
                counts[
                    "matched_preferred_" + group["preferred_source_tier"]
                ] += 1
                counts[
                    "matched_" + group["pronunciation_resolution_status"]
                ] += 1
            if args.progress_every and row_number % args.progress_every == 0:
                print(
                    f"[{args.year}] morph links {row_number:,}행 · "
                    f"matched {counts['status_matched_exact_surface_pos']:,}",
                    flush=True,
                )

    full_scope = args.max_rows is None
    if full_scope and counts["rows"] != int(morph_expected["rows"]):
        raise RuntimeError(
            f"morph occurrence coverage 불일치: {counts['rows']} != "
            f"{morph_expected['rows']}"
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "morph_dictionary_pronunciation_occurrences",
        "status": "success",
        "recorded_at": now_iso(),
        "year": args.year,
        "scope": "full_year" if full_scope else "bounded_pilot",
        "coverage_complete": full_scope,
        "policy": {
            "match": "exact morph_surface + exact POS via normalized group index",
            "sense_selection": "none; corpus sense unavailable",
            "candidate_expansion": "none; group_id join",
            "mfa_dictionary_activation": False,
        },
        "inputs": preflight["inputs"],
        "counts": dict(sorted(counts.items())),
        "outputs": {
            "occurrences": file_fingerprint(output_path, with_sha256=True)
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] {args.year} morph pronunciation links: "
        f"{counts['rows']:,} rows",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--morph-tokens", type=Path, required=True)
    result.add_argument("--year-manifest", type=Path, required=True)
    result.add_argument("--match-groups", type=Path, required=True)
    result.add_argument("--match-manifest", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--max-rows", type=int)
    result.add_argument("--progress-every", type=int, default=250_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.max_rows is not None and args.max_rows <= 0:
        raise ValueError("--max-rows는 양수여야 함")
    if args.progress_every < 0:
        raise ValueError("--progress-every는 0 이상이어야 함")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

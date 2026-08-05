"""Aggregate eojeol pronunciation evidence for a seventh TextGrid tier."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
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


SCHEMA_VERSION = "pron_reference_utterance_index.v1"
TIER_LABEL_SCHEMA_VERSION = "pron_reference_utt.v1"
MASTER_REQUIRED = {
    "utt_id",
    "year",
    "session_id",
    "n_eojeol",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_source",
    "pron_reference_status",
}
COMPARE_REQUIRED = {
    "utt_id",
    "year",
    "eojeol_idx",
    "eojeol_count",
    "dict_layer_status",
    "pron_audit_issue_codes",
    "mfa_available",
    "rule_mfa_roman_compare_status",
}
OUTPUT_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "source_eojeol_count",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_source",
    "pron_reference_status",
    "dict_morph_coordinate_linked_eojeol_count",
    "dict_morph_coordinate_unlinked_eojeol_count",
    "dict_all_morphs_linked_eojeol_count",
    "dict_partially_linked_eojeol_count",
    "dict_multiple_pronunciation_eojeol_count",
    "dict_legacy_fallback_eojeol_count",
    "dict_no_exact_link_eojeol_count",
    "mfa_available_eojeol_count",
    "rule_mfa_same_eojeol_count",
    "rule_mfa_different_eojeol_count",
    "rule_mfa_unavailable_eojeol_count",
    "pron_audit_issue_codes",
    "pron_reference_utt_label",
    "textgrid_label_schema_version",
]

csv.field_size_limit(20_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def grouped_compare(reader: csv.DictReader):
    for utt_id, rows in groupby(reader, key=lambda row: clean(row.get("utt_id"))):
        if not utt_id:
            raise RuntimeError("blank compare utt_id")
        yield utt_id, list(rows)


def make_label(master: dict[str, str], counts: Counter) -> str:
    rule_h = clean(master["pron_reference_hangul"]) or "∅"
    rule_r = clean(master["pron_reference_roman"]) or "∅"
    source = clean(master["pron_reference_source"]) or "unknown"
    status = clean(master["pron_reference_status"]) or "unknown"
    return " || ".join(
        (
            f"[RULE_H] {rule_h}",
            f"[RULE_R] {rule_r}",
            f"[SOURCE] {source}",
            f"[RULE_STATUS] {status}",
            "[DICT] "
            f"linked={counts['dict_morph_coordinate_linked']}/"
            f"{counts['eojeol']}; "
            f"coord_unlinked={counts['dict_morph_coordinate_unlinked']}; "
            f"ambiguous={counts['dict_multiple_pronunciation']}; "
            f"fallback={counts['dict_legacy_fallback']}; "
            f"no_exact={counts['dict_no_exact_link']}",
            "[MFA_COMPARE] "
            f"same={counts['rule_mfa_same']}; "
            f"different={counts['rule_mfa_different']}; "
            f"unavailable={counts['rule_mfa_unavailable']}",
        )
    )


def summarize(master: dict[str, str], rows: list[dict[str, str]]) -> dict[str, str | int]:
    expected_count = int(clean(master["n_eojeol"]))
    observed_indices = [int(clean(row["eojeol_idx"])) for row in rows]
    if observed_indices != list(range(1, expected_count + 1)):
        raise RuntimeError(f"compare eojeol coverage mismatch: {master['utt_id']}")
    if any(int(clean(row["eojeol_count"])) != expected_count for row in rows):
        raise RuntimeError(f"compare eojeol count mismatch: {master['utt_id']}")
    counts: Counter = Counter(eojeol=len(rows))
    issue_set: set[str] = set()
    for row in rows:
        dict_status = clean(row["dict_layer_status"])
        coordinate_linked = dict_status != "morph_coordinate_not_linked"
        counts[
            "dict_morph_coordinate_linked"
            if coordinate_linked
            else "dict_morph_coordinate_unlinked"
        ] += 1
        if dict_status in (
            "all_morphs_linked",
            "all_morphs_linked_with_ambiguity",
        ):
            counts["dict_all_morphs_linked"] += 1
        if dict_status == "partially_linked":
            counts["dict_partially_linked"] += 1
        issues = {
            issue.strip()
            for issue in clean(row["pron_audit_issue_codes"]).split("|")
            if issue.strip()
        }
        issue_set.update(issues)
        if "dictionary_multiple_pronunciations" in issues:
            counts["dict_multiple_pronunciation"] += 1
        if "dictionary_legacy_fallback_only" in issues:
            counts["dict_legacy_fallback"] += 1
        if "dictionary_no_exact_surface_pos_link" in issues:
            counts["dict_no_exact_link"] += 1
        if clean(row["mfa_available"]).lower() == "true":
            counts["mfa_available"] += 1
        comparison = clean(row["rule_mfa_roman_compare_status"])
        if comparison == "same_roman_token_sequence":
            counts["rule_mfa_same"] += 1
        elif comparison == "different_roman_token_sequence":
            counts["rule_mfa_different"] += 1
        else:
            counts["rule_mfa_unavailable"] += 1
    return {
        "utt_id": clean(master["utt_id"]),
        "year": clean(master["year"]),
        "session_id": clean(master["session_id"]),
        "source_eojeol_count": expected_count,
        "pron_reference_hangul": clean(master["pron_reference_hangul"]),
        "pron_reference_roman": clean(master["pron_reference_roman"]),
        "pron_reference_source": clean(master["pron_reference_source"]),
        "pron_reference_status": clean(master["pron_reference_status"]),
        "dict_morph_coordinate_linked_eojeol_count": counts[
            "dict_morph_coordinate_linked"
        ],
        "dict_morph_coordinate_unlinked_eojeol_count": counts[
            "dict_morph_coordinate_unlinked"
        ],
        "dict_all_morphs_linked_eojeol_count": counts["dict_all_morphs_linked"],
        "dict_partially_linked_eojeol_count": counts["dict_partially_linked"],
        "dict_multiple_pronunciation_eojeol_count": counts[
            "dict_multiple_pronunciation"
        ],
        "dict_legacy_fallback_eojeol_count": counts["dict_legacy_fallback"],
        "dict_no_exact_link_eojeol_count": counts["dict_no_exact_link"],
        "mfa_available_eojeol_count": counts["mfa_available"],
        "rule_mfa_same_eojeol_count": counts["rule_mfa_same"],
        "rule_mfa_different_eojeol_count": counts["rule_mfa_different"],
        "rule_mfa_unavailable_eojeol_count": counts["rule_mfa_unavailable"],
        "pron_audit_issue_codes": " | ".join(sorted(issue_set)),
        "pron_reference_utt_label": make_label(master, counts),
        "textgrid_label_schema_version": TIER_LABEL_SCHEMA_VERSION,
    }


def build(args: argparse.Namespace) -> dict:
    master_path = args.utterance_master.resolve()
    year_manifest_path = args.year_manifest.resolve()
    compare_path = args.compare.resolve()
    compare_manifest_path = args.compare_manifest.resolve()
    output_dir = args.output_dir.resolve()
    output_path = output_dir / "pron_reference_utterance.csv.gz"
    manifest_path = output_dir / "pron_reference_utterance_manifest.json"
    with year_manifest_path.open("r", encoding="utf-8") as stream:
        year_manifest = json.load(stream)
    with compare_manifest_path.open("r", encoding="utf-8") as stream:
        compare_manifest = json.load(stream)
    if year_manifest.get("status") != "success" or compare_manifest.get("status") != "success":
        raise RuntimeError("successful input manifests required")
    if str(year_manifest.get("year")) != str(args.year) or str(compare_manifest.get("year")) != str(args.year):
        raise RuntimeError("input manifest year mismatch")
    inputs = {
        "utterance_master": file_fingerprint(master_path, with_sha256=True),
        "year_manifest": file_fingerprint(year_manifest_path, with_sha256=True),
        "compare": file_fingerprint(compare_path, with_sha256=True),
        "compare_manifest": file_fingerprint(compare_manifest_path, with_sha256=True),
    }
    if inputs["utterance_master"]["sha256"] != year_manifest["tables"]["master"]["sha256"]:
        raise RuntimeError("utterance master SHA mismatch")
    if inputs["compare"]["sha256"] != compare_manifest["outputs"]["compare"]["sha256"]:
        raise RuntimeError("compare SHA mismatch")
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "year": str(args.year),
        "inputs": inputs,
        "outputs": {"index": str(output_path), "manifest": str(manifest_path)},
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError(f"existing utterance index output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    counts: Counter = Counter()
    with gzip.open(master_path, "rt", encoding="utf-8-sig", newline="") as master_stream, \
            gzip.open(compare_path, "rt", encoding="utf-8-sig", newline="") as compare_stream, \
            atomic_gzip_text_writer(output_path) as destination:
        master_reader = csv.DictReader(master_stream)
        compare_reader = csv.DictReader(compare_stream)
        for label, reader, required in (
            ("master", master_reader, MASTER_REQUIRED),
            ("compare", compare_reader, COMPARE_REQUIRED),
        ):
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(f"{label} fields missing: {sorted(missing)}")
        compare_groups = iter(grouped_compare(compare_reader))
        current = next(compare_groups, None)
        writer = csv.DictWriter(destination, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row_number, master in enumerate(master_reader, 1):
            utt_id = clean(master["utt_id"])
            if current is None or current[0] != utt_id:
                observed = None if current is None else current[0]
                raise RuntimeError(
                    f"master/compare coverage mismatch: expected={utt_id}, observed={observed}"
                )
            output = summarize(master, current[1])
            writer.writerow(output)
            counts["utterances"] += 1
            if int(output["dict_morph_coordinate_unlinked_eojeol_count"]):
                counts["utterances_with_unlinked_morph_coordinates"] += 1
            if int(output["dict_multiple_pronunciation_eojeol_count"]):
                counts["utterances_with_dictionary_ambiguity"] += 1
            if int(output["rule_mfa_different_eojeol_count"]):
                counts["utterances_with_rule_mfa_difference"] += 1
            current = next(compare_groups, None)
            if args.max_utterances is not None and counts["utterances"] >= args.max_utterances:
                break
            if args.progress_every and row_number % args.progress_every == 0:
                print(
                    f"[{args.year}] utterance pronunciation index "
                    f"{row_number:,}",
                    flush=True,
                )
        full_scope = args.max_utterances is None
        if full_scope and current is not None:
            raise RuntimeError(f"unconsumed compare group: {current[0]}")
    full_scope = args.max_utterances is None
    expected_rows = int(year_manifest["tables"]["master"]["rows"])
    if full_scope and counts["utterances"] != expected_rows:
        raise RuntimeError("utterance index coverage mismatch")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pron_reference_utterance_index",
        "status": "success",
        "recorded_at": now_iso(),
        "year": str(args.year),
        "scope": "full_year" if full_scope else "bounded_pilot",
        "coverage_complete": full_scope,
        "textgrid_label_schema_version": TIER_LABEL_SCHEMA_VERSION,
        "policy": {
            "tier_role": "utterance-level reference/search aid; no phone timing claim",
            "candidate_details": "normalized registry/group/occurrence CSV authority",
            "mfa_dictionary_activation": False,
        },
        "counts": dict(sorted(counts.items())),
        "inputs": inputs,
        "outputs": {"index": file_fingerprint(output_path, with_sha256=True)},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] {args.year} pron_reference_utterance index: "
        f"{counts['utterances']:,}",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--year", required=True)
    result.add_argument("--utterance-master", type=Path, required=True)
    result.add_argument("--year-manifest", type=Path, required=True)
    result.add_argument("--compare", type=Path, required=True)
    result.add_argument("--compare-manifest", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--max-utterances", type=int)
    result.add_argument("--progress-every", type=int, default=100_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.max_utterances is not None and args.max_utterances <= 0:
        raise ValueError("--max-utterances must be positive")
    if args.progress_every < 0:
        raise ValueError("--progress-every must be non-negative")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Independent stage-2 G3 audit for the 2020 n-insertion candidate build+join.

Separate from the generators: re-verifies frozen-SHA binding, re-evaluates the
frozen query conditions on every candidate row's evidence, checks occurrence-id
uniqueness and zero-drop accounting, independently recounts join statuses, and
re-derives A2/A3 joins for a deterministic row sample directly from the sources.
Read-only on all inputs; writes a single audit JSON.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SENSE_COLUMNS = ["sense_id", "sense_confidence", "sense_method", "sense_candidates"]
A2_SOURCE_COLS = ("sense_id", "confidence", "method", "candidates")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def import_builder():
    path = PROJECT_ROOT / "scripts" / "python" / "build_db_v1_target_manifest.py"
    spec = importlib.util.spec_from_file_location("builder_for_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-root", type=Path, required=True)
    parser.add_argument("--joined-root", type=Path, required=True)
    parser.add_argument("--query-set", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--sense-root", type=Path,
                        default=Path(r"D:\10_LAYERS\02_sense_annotated"))
    parser.add_argument("--freq-dict", type=Path,
                        default=Path(r"D:\10_LAYERS\03_freq_dictionaries\morpheme_freq_dictionary.csv"))
    parser.add_argument("--sample-every", type=int, default=500)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if not ok:
            failures.append(f"{name}: {detail}")
        print(("PASS " if ok else "FAIL ") + name + ((" — " + detail) if detail and not ok else ""))

    builder = import_builder()
    query_set = load_json(args.query_set)
    contract = load_json(args.contract)
    build_manifest = load_json(args.candidates_root / "TARGET_MANIFEST_BUILD.json")
    join_manifest = load_json(args.joined_root / "JOIN_MANIFEST.json")

    frozen_sha = sha256_file(args.query_set)
    check("frozen_query_sha_matches_build",
          build_manifest["query_set_sha256"] == frozen_sha,
          build_manifest["query_set_sha256"])
    check("contract_bound_to_same_query",
          contract["bound_query_set"]["sha256"] == frozen_sha)
    check("join_bound_to_same_query",
          join_manifest["bound_query_set_sha256"] == frozen_sha)
    check("contract_sha_matches_join",
          join_manifest["contract_sha256"] == sha256_file(args.contract))

    queries = {q["query_id"]: q for q in query_set["queries"]}

    # --- candidate rows: re-evaluate conditions, uniqueness ---
    cand_csv = args.candidates_root / "TARGET_CANDIDATES.csv"
    seen_ids: set[str] = set()
    cond_fail = dup = 0
    per_query: dict[str, int] = {}
    scope_mismatch = 0
    n_cand = 0
    with cand_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            n_cand += 1
            evidence = json.loads(row["match_evidence_json"])
            query = queries[row["query_id"]]
            if not builder.row_matches(evidence, query["conditions"]):
                cond_fail += 1
            oid = row["target_occurrence_id"]
            if oid in seen_ids:
                dup += 1
            seen_ids.add(oid)
            per_query[row["query_id"]] = per_query.get(row["query_id"], 0) + 1
            expect_scope = "intra_eojeol" if "INTRA" in row["query_id"] else "inter_eojeol"
            if evidence["boundary_scope"] != expect_scope:
                scope_mismatch += 1
    check("all_rows_rematch_frozen_conditions", cond_fail == 0, f"{cond_fail} rows")
    check("occurrence_ids_unique", dup == 0, f"{dup} duplicates")
    check("boundary_scope_consistent_with_query", scope_mismatch == 0)
    check("build_row_count_matches_manifest",
          n_cand == build_manifest["counts"]["candidate_rows"])

    # --- joined rows: zero-drop, id identity, independent status recount ---
    joined_csv = args.joined_root / "CANDIDATES_WITH_VARIABLES.csv"
    joined_ids: set[str] = set()
    recount: dict[str, int] = {}
    n_joined = 0
    sample_rows: list[dict[str, str]] = []
    with joined_csv.open(encoding="utf-8-sig", newline="") as stream:
        for i, row in enumerate(csv.DictReader(stream)):
            n_joined += 1
            joined_ids.add(row["target_occurrence_id"])
            for side in ("left", "right"):
                recount[f"{side}_sense:{row[f'{side}_sense_join_status']}"] = (
                    recount.get(f"{side}_sense:{row[f'{side}_sense_join_status']}", 0) + 1)
                recount[f"{side}_etym:{row[f'{side}_etym_join_status']}"] = (
                    recount.get(f"{side}_etym:{row[f'{side}_etym_join_status']}", 0) + 1)
            recount[f"class:{row['boundary_etym_class']}"] = (
                recount.get(f"class:{row['boundary_etym_class']}", 0) + 1)
            if i % args.sample_every == 0:
                sample_rows.append(row)
    check("zero_drop_rows", n_joined == n_cand, f"cand={n_cand} joined={n_joined}")
    check("occurrence_id_sets_identical", joined_ids == seen_ids)
    check("join_manifest_rows_match", join_manifest["rows_in"] == n_cand
          and join_manifest["rows_out"] == n_joined)
    check("status_counts_reproduced", recount == join_manifest["status_counts"])

    # --- deterministic sample: re-derive joins directly from sources ---
    freq: dict[tuple[str, str], dict[str, str]] = {}
    with args.freq_dict.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            freq[(row["morph"], row["tag"])] = row
    year_dirs = contract["joins"]["sense_a2"]["year_release_dirs"]
    sense_cache: dict[str, dict[tuple[str, str, str], dict[str, str]]] = {}

    def sense_row(year: str, utt_id: str, widx: str, midx: str):
        file_id = utt_id.split(".", 1)[0]
        cache_key = f"{year}/{file_id}"
        if cache_key not in sense_cache:
            path = args.sense_root / year_dirs[str(year)] / f"{file_id}.csv"
            table: dict[tuple[str, str, str], dict[str, str]] = {}
            if path.is_file():
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    for srow in csv.DictReader(stream):
                        table[(srow["utt_id"], srow["word_idx"], srow["morph_idx"])] = srow
            sense_cache[cache_key] = table
        return sense_cache[cache_key].get((utt_id, widx, midx))

    sample_mismatch = 0
    for row in sample_rows:
        evidence = json.loads(row["match_evidence_json"])
        for side in ("left", "right"):
            surface = evidence[f"{side}_morph_surface"]
            pos = evidence[f"{side}_pos"]
            srow = sense_row(row["year"], row["utt_id"],
                             evidence[f"{side}_eojeol_idx"],
                             evidence[f"{side}_morph_idx_in_eojeol"])
            if srow and srow["morph"] == surface and srow["tag"] == pos:
                for col, src in zip(SENSE_COLUMNS, A2_SOURCE_COLS):
                    if row[f"{side}_{col}"] != srow[src]:
                        sample_mismatch += 1
            frow = freq.get((surface, pos))
            expect = frow["etym_type"] if frow else ""
            if row[f"{side}_etym_type"] != expect:
                sample_mismatch += 1
    check("sample_rederivation_consistent", sample_mismatch == 0,
          f"{sample_mismatch} field mismatches in {len(sample_rows)} sampled rows")

    result = {
        "schema_version": "stage2_g3_n_insertion_audit.v1",
        "status": "passed" if not failures else "failed",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "frozen_query_sha256": frozen_sha,
        "counts": {
            "candidate_rows": n_cand,
            "per_query": per_query,
            "joined_rows": n_joined,
            "sampled_rows": len(sample_rows),
        },
        "distributions": dict(sorted(recount.items())),
        "failures": failures,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "candidate_rows": n_cand,
                      "per_query": per_query}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

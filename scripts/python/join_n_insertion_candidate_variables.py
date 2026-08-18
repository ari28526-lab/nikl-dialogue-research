"""Attach A2 sense and A3 etymology/frequency variables to n-insertion candidates.

Implements config/join_contracts/n_insertion_variable_join_contract_v1_20260818.json.
Zero-drop: every candidate row is emitted exactly once; joins only add columns and
status fields. Sources (A2/A3) are read-only. Never overwrites existing output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (
    PROJECT_ROOT
    / "config"
    / "join_contracts"
    / "n_insertion_variable_join_contract_v1_20260818.json"
)

FREQ_COLUMNS = [
    "etym_type", "etym_origin", "freq_total",
    "freq_2020", "freq_2021", "freq_2022", "freq_2023", "freq_2024", "freq_2025",
    "freq_LS_spoken", "freq_ML2025_spoken", "freq_KoFREN_all", "KoFREN_log10",
]
SENSE_COLUMNS = ["sense_id", "sense_confidence", "sense_method", "sense_candidates"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_freq_dict(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    result: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            result[(row["morph"], row["tag"])] = {c: row[c] for c in FREQ_COLUMNS}
    return result


def evidence_side(evidence: dict, side: str) -> dict[str, str]:
    return {
        "surface": evidence[f"{side}_morph_surface"],
        "pos": evidence[f"{side}_pos"],
        "eojeol_idx": evidence[f"{side}_eojeol_idx"],
        "morph_idx": evidence[f"{side}_morph_idx_in_eojeol"],
    }


def derive_boundary_etym_class(scope: str, left: dict, right: dict) -> str:
    lt, rt = left.get("etym_type", ""), right.get("etym_type", "")
    l_ok = left.get("_joined") and lt != ""
    r_ok = right.get("_joined") and rt != ""
    if not (l_ok and r_ok):
        return "etym_unknown"
    if "외래어" in (lt, rt):
        return "loan_involved"
    if lt == "한자어" and rt == "한자어" and scope == "intra_eojeol":
        return "sino_internal_candidate"
    if lt == "고유어" and rt == "고유어":
        return "native_compound_candidate"
    return "mixed"


def run(*, candidates_root: Path, contract_path: Path, sense_root: Path,
        freq_dict_path: Path, output_root: Path) -> dict:
    contract = load_json(contract_path)
    build_manifest = load_json(candidates_root / "TARGET_MANIFEST_BUILD.json")
    bound_sha = contract["bound_query_set"]["sha256"]
    if build_manifest["query_set_sha256"] != bound_sha:
        raise RuntimeError(
            "candidate build is not bound to the contract's frozen query SHA: "
            f"{build_manifest['query_set_sha256']} != {bound_sha}"
        )
    year_dirs = contract["joins"]["sense_a2"]["year_release_dirs"]

    candidates_csv = candidates_root / "TARGET_CANDIDATES.csv"
    with candidates_csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        base_fields = list(reader.fieldnames or [])
        rows = list(reader)
    rows_in = len(rows)

    freq = load_freq_dict(freq_dict_path)

    # Group candidate rows by (year, session file id) for one-pass A2 reads.
    by_file: dict[tuple[str, str], list[int]] = {}
    for i, row in enumerate(rows):
        file_id = row["utt_id"].split(".", 1)[0]
        by_file.setdefault((row["year"], file_id), []).append(i)

    sense_lookup: dict[tuple[str, str, str, str], dict[str, str]] = {}
    missing_files: set[str] = set()
    for (year, file_id), indices in sorted(by_file.items()):
        release_dir = year_dirs[str(year)]
        path = sense_root / release_dir / f"{file_id}.csv"
        if not path.is_file():
            missing_files.add(f"{year}/{file_id}")
            continue
        needed_utts = {rows[i]["utt_id"] for i in indices}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for srow in csv.DictReader(stream):
                if srow["utt_id"] in needed_utts:
                    key = (year, srow["utt_id"], srow["word_idx"], srow["morph_idx"])
                    sense_lookup[key] = srow

    status_counts: dict[str, int] = {}

    def bump(name: str) -> None:
        status_counts[name] = status_counts.get(name, 0) + 1

    out_fields = list(base_fields)
    for side in ("left", "right"):
        out_fields += [f"{side}_{c}" for c in SENSE_COLUMNS]
        out_fields.append(f"{side}_sense_join_status")
        out_fields += [f"{side}_{c}" for c in FREQ_COLUMNS]
        out_fields.append(f"{side}_etym_join_status")
    out_fields.append("boundary_etym_class")

    out_rows: list[dict[str, str]] = []
    for row in rows:
        evidence = json.loads(row["match_evidence_json"])
        year = row["year"]
        file_id = row["utt_id"].split(".", 1)[0]
        out = dict(row)
        side_info: dict[str, dict] = {}
        for side in ("left", "right"):
            sd = evidence_side(evidence, side)
            # --- A2 sense join ---
            if f"{year}/{file_id}" in missing_files:
                s_status, srow = "session_file_missing", None
            else:
                srow = sense_lookup.get((year, row["utt_id"], sd["eojeol_idx"], sd["morph_idx"]))
                if srow is None:
                    s_status = "no_row_at_position"
                elif srow["morph"] != sd["surface"] or srow["tag"] != sd["pos"]:
                    s_status, srow = "morph_tag_mismatch", None
                elif srow["method"] == "not_target":
                    s_status = "joined_not_target"
                else:
                    s_status = "joined"
            for col, src in zip(SENSE_COLUMNS, ("sense_id", "confidence", "method", "candidates")):
                out[f"{side}_{col}"] = srow[src] if srow else ""
            out[f"{side}_sense_join_status"] = s_status
            bump(f"{side}_sense:{s_status}")
            # --- A3 etym/freq join ---
            frow = freq.get((sd["surface"], sd["pos"]))
            e_status = "joined" if frow else "not_in_dictionary"
            for col in FREQ_COLUMNS:
                out[f"{side}_{col}"] = frow[col] if frow else ""
            out[f"{side}_etym_join_status"] = e_status
            bump(f"{side}_etym:{e_status}")
            side_info[side] = {"_joined": bool(frow), "etym_type": (frow or {}).get("etym_type", "")}
        klass = derive_boundary_etym_class(
            evidence["boundary_scope"], side_info["left"], side_info["right"]
        )
        out["boundary_etym_class"] = klass
        bump(f"class:{klass}")
        out_rows.append(out)

    if len(out_rows) != rows_in:
        raise RuntimeError(f"zero-drop violated: in={rows_in} out={len(out_rows)}")

    partial = output_root.with_name(output_root.name + ".partial")
    if output_root.exists() or partial.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_root}")
    partial.mkdir(parents=True)
    try:
        out_csv = partial / "CANDIDATES_WITH_VARIABLES.csv"
        with out_csv.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=out_fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(out_rows)
        manifest = {
            "schema_version": "n_insertion_variable_join.v1",
            "status": "joined_zero_drop_no_realization_judgement",
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "contract_sha256": sha256_file(contract_path),
            "candidates_input_sha256": sha256_file(candidates_csv),
            "bound_query_set_sha256": bound_sha,
            "rows_in": rows_in,
            "rows_out": len(out_rows),
            "session_files_missing": sorted(missing_files),
            "status_counts": dict(sorted(status_counts.items())),
            "output": {
                "path": out_csv.name,
                "bytes": out_csv.stat().st_size,
                "sha256": sha256_file(out_csv),
            },
            "safety": {
                "sources_modified": False,
                "rows_dropped": 0,
                "sense_auto_disambiguated": False,
                "realization_judged": False,
            },
        }
        (partial / "JOIN_MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        partial.replace(output_root)
        return manifest
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--sense-root", type=Path,
                        default=Path(r"D:\10_LAYERS\02_sense_annotated"))
    parser.add_argument("--freq-dict", type=Path,
                        default=Path(r"D:\10_LAYERS\03_freq_dictionaries\morpheme_freq_dictionary.csv"))
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = run(
            candidates_root=args.candidates_root.resolve(),
            contract_path=args.contract.resolve(),
            sense_root=args.sense_root.resolve(),
            freq_dict_path=args.freq_dict.resolve(),
            output_root=args.output_root.resolve(),
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

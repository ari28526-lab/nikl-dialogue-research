"""Materialize the DB v1 base-plus-sidecar active-view exception contract.

This does not copy the 5.1M-row RC0 ledger.  RC0 remains the default view and
only RC1 exception keys are materialized.  Downstream consumers resolve a row
as ``curated pointer if present, otherwise RC0 base``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RC1_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_0_0_rc1_20260818"
)
DEFAULT_RC1_AUDIT = (
    PROJECT_ROOT
    / "outputs"
    / "reports"
    / "AUDIT_db_v1_rc1_recovery_sidecar_20260818.json"
)
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "releases"
    / "nikl_dialogue_research_db_v1_active_view_contract_v1_20260818"
)

VIEW_FIELDS = [
    "year",
    "utt_id",
    "session_id",
    "base_primary_status",
    "base_status_family",
    "base_reason_codes_json",
    "recovery_status",
    "recovery_family",
    "recovery_visibility",
    "recovery_outcome_source",
    "recovery_evidence_path",
    "recovery_evidence_sha256",
    "active_annotation_source",
    "active_annotation_revision",
    "active_textgrid_path",
    "active_textgrid_sha256",
    "active_transcript",
    "active_orth_roman_v2",
    "manual_edit_count",
    "annotation_resolution_status",
    "phone_layer_status",
    "phoneme_layer_status",
    "morph_enrichment_status",
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


def key(row: Mapping[str, Any]) -> tuple[int, str]:
    return int(row["year"]), str(row["utt_id"])


def unique_map(
    rows: Iterable[Mapping[str, Any]], *, label: str
) -> dict[tuple[int, str], Mapping[str, Any]]:
    result: dict[tuple[int, str], Mapping[str, Any]] = {}
    for row in rows:
        item_key = key(row)
        if item_key in result:
            raise RuntimeError(f"duplicate {label} key: {item_key}")
        result[item_key] = row
    return result


def resolve_rows(
    *,
    status_rows: list[dict[str, Any]],
    pointer_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve exception rows without changing RC0 base categories."""

    statuses = unique_map(status_rows, label="status")
    pointers = unique_map(pointer_rows, label="pointer")
    snapshots = unique_map(snapshot_rows, label="snapshot")
    if set(pointers) != set(snapshots):
        raise RuntimeError("curated pointer/snapshot exact-ID set mismatch")
    if not set(pointers) <= set(statuses):
        raise RuntimeError("curated pointer is outside recovery status overlay")

    output: list[dict[str, Any]] = []
    for item_key in sorted(statuses):
        status = statuses[item_key]
        pointer = pointers.get(item_key)
        snapshot = snapshots.get(item_key)
        if pointer is not None:
            if status["proposed_recovery_family"] != "curated_recovery":
                raise RuntimeError(f"curated family mismatch: {item_key}")
            if pointer["active_annotation_source"] != "curated":
                raise RuntimeError(f"active source is not curated: {item_key}")
            if (
                pointer["active_textgrid_sha256"]
                != snapshot["active_textgrid_sha256"]
            ):
                raise RuntimeError(f"TextGrid SHA mismatch: {item_key}")
            active_source = "curated"
            active_revision = pointer["active_annotation_revision"]
            active_path = pointer["active_textgrid_path"]
            active_sha = pointer["active_textgrid_sha256"]
            active_transcript = snapshot["final_transcript"]
            active_roman = snapshot["orth_roman_v2"]
            manual_edit_count = pointer["manual_edit_count"]
            resolution = "curated_pointer_applied"
            phoneme_status = pointer["phoneme_layer_status"]
            morph_status = pointer["morph_enrichment_status"]
            phone_status = pointer["phone_layer_status"]
        else:
            active_source = "base"
            active_revision = ""
            active_path = ""
            active_sha = ""
            active_transcript = ""
            active_roman = ""
            manual_edit_count = 0
            resolution = "base_preserved_no_curated_pointer"
            phoneme_status = "not_applicable_no_curated_pointer"
            morph_status = "not_applicable_no_curated_pointer"
            phone_status = status["phone_layer_status"]

        output.append(
            {
                "year": item_key[0],
                "utt_id": item_key[1],
                "session_id": status["session_id"],
                "base_primary_status": status["base_primary_status"],
                "base_status_family": status["base_status_family"],
                "base_reason_codes_json": status["base_reason_codes_json"],
                "recovery_status": status["proposed_recovery_status"],
                "recovery_family": status["proposed_recovery_family"],
                "recovery_visibility": status["proposed_visibility"],
                "recovery_outcome_source": status["outcome_source"],
                "recovery_evidence_path": status["evidence_path"],
                "recovery_evidence_sha256": status["evidence_sha256"],
                "active_annotation_source": active_source,
                "active_annotation_revision": active_revision,
                "active_textgrid_path": active_path,
                "active_textgrid_sha256": active_sha,
                "active_transcript": active_transcript,
                "active_orth_roman_v2": active_roman,
                "manual_edit_count": manual_edit_count,
                "annotation_resolution_status": resolution,
                "phone_layer_status": phone_status,
                "phoneme_layer_status": phoneme_status,
                "morph_enrichment_status": morph_status,
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=VIEW_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def materialize(
    *, rc1_root: Path, rc1_audit_path: Path, output_root: Path
) -> dict[str, Any]:
    rc1_root = rc1_root.resolve()
    rc1_audit_path = rc1_audit_path.resolve()
    output_root = output_root.resolve()
    partial = output_root.with_name(output_root.name + ".partial")
    if output_root.exists() or partial.exists():
        raise FileExistsError(f"existing output is never overwritten: {output_root}")

    manifest_path = rc1_root / "RC1_RELEASE_MANIFEST.json"
    status_path = rc1_root / "overlays" / "RECOVERY_STATUS_OVERLAY.json"
    pointer_path = rc1_root / "overlays" / "ACTIVE_ANNOTATION_POINTERS.json"
    snapshot_path = rc1_root / "overlays" / "MANUAL_ANNOTATION_SNAPSHOTS.json"
    manifest = load_json(manifest_path)
    audit = load_json(rc1_audit_path)
    if manifest["status"] != "internal_rc1_recovery_sidecar_adopted":
        raise RuntimeError("RC1 release is not adopted")
    if audit["status"] != "passed_internal_rc1_append_only_sidecar":
        raise RuntimeError("RC1 independent audit has not passed")
    if audit["manifest_sha256"] != sha256_file(manifest_path):
        raise RuntimeError("RC1 manifest SHA does not match its audit")

    status_doc = load_json(status_path)
    pointer_doc = load_json(pointer_path)
    snapshot_doc = load_json(snapshot_path)
    rows = resolve_rows(
        status_rows=status_doc["rows"],
        pointer_rows=pointer_doc["rows"],
        snapshot_rows=snapshot_doc["rows"],
    )
    curated_count = sum(
        row["active_annotation_source"] == "curated" for row in rows
    )
    if len(rows) != 55 or curated_count != 16:
        raise RuntimeError(
            f"frozen scope mismatch: rows={len(rows)} curated={curated_count}"
        )

    partial.mkdir(parents=True)
    try:
        view_path = partial / "ACTIVE_RECOVERY_EXCEPTIONS.csv"
        write_csv(view_path, rows)
        readme_path = partial / "README.md"
        readme_path.write_text(
            "# DB v1 active annotation view contract v1\n\n"
            "RC0 is the default for every utterance. Join this exception table "
            "on `(year, utt_id)`. If `active_annotation_source=curated`, use the "
            "curated transcript, orthographic Roman, and TextGrid pointer. "
            "Otherwise preserve RC0. Diagnostic evidence is never promoted to "
            "an active annotation. D9 phones remain reference-only and pending "
            "morph/phoneme fields are not synthesized.\n",
            encoding="utf-8",
        )
        files = []
        for path in (view_path, readme_path):
            files.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        result = {
            "schema_version": "nikl_dialogue_research_db_v1_active_view_contract.v1",
            "status": "materialized_exception_only_contract",
            "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "base_resolution_rule": "RC0 default; RC1 curated pointer wins only on exact (year, utt_id)",
            "rc1_release_id": manifest["release_id"],
            "inputs": {
                "rc1_manifest_sha256": sha256_file(manifest_path),
                "rc1_audit_sha256": sha256_file(rc1_audit_path),
                "status_overlay_sha256": sha256_file(status_path),
                "pointer_overlay_sha256": sha256_file(pointer_path),
                "snapshot_overlay_sha256": sha256_file(snapshot_path),
            },
            "counts": {
                "exception_rows": len(rows),
                "curated_pointer_rows": curated_count,
                "base_preserved_exception_rows": len(rows) - curated_count,
                "full_base_rows_copied": 0,
            },
            "safety": {
                "rc0_modified": False,
                "rc1_modified": False,
                "r3_modified": False,
                "textgrid_modified": False,
                "mfa_run": False,
                "phone_adopted": False,
                "morphology_rebuilt": False,
            },
            "files": files,
        }
        result_path = partial / "ACTIVE_VIEW_MANIFEST.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        partial.replace(output_root)
        return result
    except Exception:
        if partial.exists():
            shutil.rmtree(partial)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rc1-root", type=Path, default=DEFAULT_RC1_ROOT)
    parser.add_argument("--rc1-audit", type=Path, default=DEFAULT_RC1_AUDIT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = materialize(
            rc1_root=args.rc1_root,
            rc1_audit_path=args.rc1_audit,
            output_root=args.output_root,
        )
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

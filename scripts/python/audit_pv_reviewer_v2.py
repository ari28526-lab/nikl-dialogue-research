"""Independently audit the approved PV reviewer v2 derivative."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "pv_seven_phenomena_reviewer_v2_20260822"
)
HTML_NAME = "PV_REVIEWER_V2.html"
BUILD_NAME = "PV_REVIEWER_V2_BUILD.json"
IMPORTED_NAME = "PV_REVIEWER_V1_IMPORTED.jsonl"
DIALOGUE_NAME = "PV_REVIEWER_V2_DIALOGUES.jsonl"
AUDIT_NAME = "PV_REVIEWER_V2_AUDIT.json"
MANIFEST_NAME = "PV_REVIEWER_V2_SHA256_MANIFEST.csv"
EXPECTED_CODES = ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")
SAFETY_FALSE_FIELDS = (
    "source_files_modified",
    "audio_transcoded",
    "whole_dialogue_audio_embedded",
    "automatic_realization_judgement",
    "formal_ledger_written",
    "mfa_run",
    "koina_run",
    "wav2vec2_run",
    "existing_output_overwritten",
    "automatic_scan_cap_increase",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_jsonl(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label} {line_no}행 JSON 파싱 실패: {exc}") from exc
        if not isinstance(row, dict):
            raise RuntimeError(f"{label} {line_no}행은 JSON object가 아님")
        rows.append(row)
    return rows


def semantic_fingerprint(row: Mapping[str, Any]) -> str:
    ignored = {
        "reviewed_at",
        "event_uuid",
        "revision_seq",
        "supersedes_event_uuid",
        "possible_duplicate_of",
        "import_source_path",
        "import_source_sha256",
    }
    return json.dumps(
        {key: row[key] for key in sorted(row) if key not in ignored},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def compare_receipted_file(
    *,
    path: Path,
    receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> dict[str, Any]:
    payload = path.read_bytes()
    measured = {"path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload)}
    if len(payload) != int(receipt.get("bytes", -1)):
        errors.append(f"{label} byte count differs from build receipt")
    if measured["sha256"] != receipt.get("sha256"):
        errors.append(f"{label} SHA-256 differs from build receipt")
    return measured


def source_audio_hashes(
    *, run_root: Path, records: Iterable[Mapping[str, Any]], errors: list[str]
) -> list[str]:
    bundle = run_root / "bundle"
    packages_by_pv: dict[str, list[Path]] = defaultdict(list)
    for package in bundle.iterdir():
        manifest_path = package / "PACKAGE_MANIFEST.json"
        if not package.is_dir() or not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        packages_by_pv[str(manifest.get("pv_id", ""))].append(package)
    hashes: list[str] = []
    for record in records:
        pv_id = str(record.get("pv_id", ""))
        packages = packages_by_pv.get(pv_id, [])
        if len(packages) != 1:
            errors.append(f"{pv_id}: source package count={len(packages)}")
            hashes.extend(["", ""])
            continue
        for filename, field in (
            ("target.wav", "target_wav_sha256"),
            ("context_pm2.wav", "context_wav_sha256"),
        ):
            source = packages[0] / filename
            measured = sha256_file(source)
            hashes.append(measured)
            if measured != record.get(field):
                errors.append(f"{pv_id}/{filename}: source WAV SHA differs from receipt")
    return hashes


def audit(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve(strict=True)
    approved_parent = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if input_dir.parent != approved_parent:
        raise RuntimeError(f"v2 derivative must be a direct child of outputs/pilots: {input_dir}")

    build_path = input_dir / BUILD_NAME
    html_path = input_dir / HTML_NAME
    imported_path = input_dir / IMPORTED_NAME
    dialogue_path = input_dir / DIALOGUE_NAME
    build = json.loads(build_path.read_text(encoding="utf-8"))
    html_bytes = html_path.read_bytes()
    document = html_bytes.decode("utf-8")
    imported_bytes = imported_path.read_bytes()
    dialogue_bytes = dialogue_path.read_bytes()
    errors: list[str] = []

    if build.get("status") != "built_pending_independent_audit":
        errors.append(f"unexpected build status: {build.get('status')}")
    output_receipt = build.get("output", {})
    measured_files = {
        "html": compare_receipted_file(
            path=html_path,
            receipt=output_receipt.get("html", {}),
            errors=errors,
            label="HTML",
        ),
        "imported_jsonl": compare_receipted_file(
            path=imported_path,
            receipt=output_receipt.get("imported_jsonl", {}),
            errors=errors,
            label="imported JSONL",
        ),
        "dialogue_jsonl": compare_receipted_file(
            path=dialogue_path,
            receipt=output_receipt.get("dialogue_jsonl", {}),
            errors=errors,
            label="dialogue JSONL",
        ),
    }

    records = build.get("selection", {}).get("records", [])
    if len(records) != 14 or len({row.get("pv_id") for row in records}) != 14:
        errors.append("selection is not 14 unique pv_id values")
    expected_cells = {(code, year) for code in EXPECTED_CODES for year in (2020, 2025)}
    actual_cells = {
        (row.get("phenomenon_code"), int(row.get("year", 0))) for row in records
    }
    if actual_cells != expected_cells:
        errors.append(f"phenomenon/year cells differ: {sorted(actual_cells)}")

    imported_rows = parse_jsonl(imported_bytes, IMPORTED_NAME)
    imported_event_ids = [str(row.get("review_event_id", "")) for row in imported_rows]
    duplicate_groups = sum(count - 1 for count in Counter(map(semantic_fingerprint, imported_rows)).values())
    if len(imported_rows) != 15:
        errors.append(f"imported history rows={len(imported_rows)}")
    if len(set(imported_event_ids)) != 14:
        errors.append(f"imported history unique review_event_id={len(set(imported_event_ids))}")
    if duplicate_groups != 1:
        errors.append(f"imported history semantic duplicate rows={duplicate_groups}")
    source_jsonl = Path(build.get("source", {}).get("user_jsonl_path", ""))
    if not source_jsonl.is_file():
        errors.append(f"user source JSONL missing: {source_jsonl}")
    else:
        source_bytes = source_jsonl.read_bytes()
        if imported_bytes != source_bytes:
            errors.append("imported JSONL is not byte-for-byte identical to user source")
        if sha256_bytes(source_bytes) != build.get("source", {}).get("user_jsonl_sha256"):
            errors.append("user source JSONL SHA differs from build receipt")

    dialogue_rows = parse_jsonl(dialogue_bytes, DIALOGUE_NAME)
    dialogues_by_pv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dialogue_rows:
        dialogues_by_pv[str(row.get("pv_id", ""))].append(row)
    receipt_dialogue = build.get("dialogue", {})
    if len(dialogues_by_pv) != 14:
        errors.append(f"dialogue pv_id count={len(dialogues_by_pv)}")
    if len(dialogue_rows) != int(receipt_dialogue.get("total_rows", -1)):
        errors.append("dialogue total row count differs from build receipt")
    target_exact_matches = 0
    for record in records:
        pv_id = str(record.get("pv_id", ""))
        rows = dialogues_by_pv.get(pv_id, [])
        expected_rows = int(receipt_dialogue.get("rows_by_pv_id", {}).get(pv_id, -1))
        if len(rows) != expected_rows:
            errors.append(f"{pv_id}: dialogue rows={len(rows)}, receipt={expected_rows}")
        targets = [row for row in rows if row.get("is_target") is True]
        if len(targets) != 1:
            errors.append(f"{pv_id}: exact target rows={len(targets)}")
        else:
            target_exact_matches += 1
            if targets[0].get("utt_id") != record.get("utt_id"):
                errors.append(f"{pv_id}: target utt_id differs from selection")

    embedded = re.findall(rb"data:audio/wav;base64,([A-Za-z0-9+/=]+)", html_bytes)
    embedded_hashes: list[str] = []
    for index, encoded in enumerate(embedded):
        try:
            payload = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            errors.append(f"embedded audio {index}: invalid base64 {exc}")
            continue
        if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
            errors.append(f"embedded audio {index}: not RIFF/WAVE")
        embedded_hashes.append(sha256_bytes(payload))
    if len(embedded) != 28:
        errors.append(f"embedded audio payload count={len(embedded)}")
    run_root = Path(build.get("source", {}).get("run_root", "")).resolve(strict=True)
    source_hashes = source_audio_hashes(run_root=run_root, records=records, errors=errors)
    if embedded_hashes != source_hashes:
        errors.append("embedded WAV hashes differ from source WAV hashes or order")

    structural_counts = {
        "review_forms": document.count('id="review-form"'),
        "audio_elements": document.count("<audio "),
        "candidate_containers": document.count('id="candidate-buttons"'),
        "dialogue_search_controls": document.count('id="dialogue-search"'),
    }
    if structural_counts != {
        "review_forms": 1,
        "audio_elements": 2,
        "candidate_containers": 1,
        "dialogue_search_controls": 1,
    }:
        errors.append(f"one-candidate HTML structural counts differ: {structural_counts}")
    for forbidden in ('src="http', "fetch(", "XMLHttpRequest", "WebSocket"):
        if forbidden in document:
            errors.append(f"external/network behavior found: {forbidden}")
    for required in (
        "PV_REVIEWER_V2_TEST_API",
        'id="candidate-search"',
        'id="priority-filter"',
        'id="prev"',
        'id="next"',
        'id="morph-display"',
        'id="speaker-run-panel"',
        'id="dialogue-panel"',
        'id="social-panel"',
        'id="pron-panel"',
        'id="literature-panel"',
        'id="export"',
        'id="copy"',
        "자동 실현 판정",
        "실제 들린 발음이나 자동 실현 정답이 아닙니다",
    ):
        if required not in document:
            errors.append(f"required reviewer behavior/limit missing: {required}")

    morph = build.get("morph_display", {})
    if int(morph.get("direct_from_existing_match_evidence", -1)) != 12:
        errors.append("direct morph display count is not 12")
    if int(morph.get("hia_requested", -1)) != 2:
        errors.append("HIA bounded morph join request count is not 2")
    hia_links = morph.get("hia_links", {})
    hia_statuses = {pv_id: row.get("status", "") for pv_id, row in hia_links.items()}
    if set(hia_links) != {"PV0027", "PV0177"}:
        errors.append(f"HIA morph status records are not the exact two samples: {hia_statuses}")
    if not str(hia_statuses.get("PV0177", "")).startswith("linked"):
        errors.append(f"PV0177 HIA morph link is not linked: {hia_statuses.get('PV0177')}")
    if hia_statuses.get("PV0027") != "unavailable_form_tagged_count_mismatch_zero_drop":
        errors.append(
            "PV0027 HIA known form/tagged mismatch is not preserved as zero-drop status: "
            f"{hia_statuses.get('PV0027')}"
        )

    literature = build.get("literature", {})
    if int(literature.get("not_found_rows_excluded", -1)) != 1:
        errors.append("literature not_found exclusion count is not 1")
    if int(literature.get("cited_source_rows_not_primary_verified", -1)) != 10:
        errors.append("literature cited-source exclusion count is not 10")
    if '"relation":"not_found"' in document or '"evidence_owner":"cited_source"' in document:
        errors.append("excluded literature evidence appears in positive HTML payload")

    safety = build.get("safety", {})
    for field in SAFETY_FALSE_FIELDS:
        if safety.get(field) is not False:
            errors.append(f"safety assertion is not false: {field}")
    if int(safety.get("scan_cap_per_table_year", -1)) != 200000:
        errors.append("scan cap is not the approved 200000 rows")

    return {
        "schema_version": "pv_reviewer_v2_audit.v1",
        "passed": not errors,
        "errors": errors,
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "counts": {
            **structural_counts,
            "selection_records": len(records),
            "balanced_cells": len(actual_cells),
            "imported_rows": len(imported_rows),
            "imported_unique_review_events": len(set(imported_event_ids)),
            "imported_semantic_duplicate_rows": duplicate_groups,
            "dialogue_rows": len(dialogue_rows),
            "dialogue_pv_ids": len(dialogues_by_pv),
            "dialogue_exact_targets": target_exact_matches,
            "embedded_wav_payloads": len(embedded),
            "embedded_wav_source_sha_matches": sum(
                left == right for left, right in zip(embedded_hashes, source_hashes)
            ),
            "morph_direct": morph.get("direct_from_existing_match_evidence"),
            "morph_hia_status_records": len(hia_links),
            "morph_hia_linked": sum(
                str(row.get("status", "")).startswith("linked")
                for row in hia_links.values()
            ),
            "morph_hia_zero_drop_unavailable": sum(
                str(row.get("status", "")).endswith("zero_drop")
                for row in hia_links.values()
            ),
            "literature_positive": literature.get("positive_common_method_rows"),
            "external_sources": 0
            if not any(token in document for token in ('src="http', "fetch("))
            else 1,
        },
        "files": {
            **measured_files,
            "build": {
                "path": str(build_path),
                "bytes": build_path.stat().st_size,
                "sha256": sha256_file(build_path),
            },
        },
    }


def write_atomic(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    partial.replace(path)


def write_audit_and_manifest(input_dir: Path, result: Mapping[str, Any]) -> None:
    audit_path = input_dir / "audit" / AUDIT_NAME
    write_atomic(
        audit_path,
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    manifest_path = input_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    partial = manifest_path.with_name(manifest_path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    rows = []
    for path in sorted(item for item in input_dir.rglob("*") if item.is_file()):
        if path == manifest_path or path == partial:
            continue
        rows.append(
            {
                "relative_path": path.relative_to(input_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    with partial.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["relative_path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    partial.replace(manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--write-audit", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(args.input_dir)
        if args.write_audit:
            write_audit_and_manifest(args.input_dir.resolve(strict=True), result)
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

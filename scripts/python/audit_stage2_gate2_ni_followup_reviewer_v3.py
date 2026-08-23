"""Independently audit the Stage 2 Gate 2 NI follow-up reviewer v3."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "pilots"
    / "stage2_gate2_ni_followup_reviewer_v3_20260823"
)

HTML_NAME = "STAGE2_GATE2_NI_REVIEWER_V3.html"
BUILD_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_BUILD.json"
IMPORTED_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_IMPORTED_BASE.jsonl"
DIALOGUE_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_DIALOGUES.jsonl"
AUDIT_NAME = "STAGE2_GATE2_NI_REVIEWER_V3_AUDIT.json"
MANIFEST_NAME = "SHA256SUMS_stage2_gate2_ni_followup_reviewer_v3_20260823.txt"

SOURCE_HTML = "PV_REVIEWER_V2_1.html"
SOURCE_IMPORTED = "PV_REVIEWER_V2_1_IMPORTED_BASE.jsonl"
SOURCE_DIALOGUES = "PV_REVIEWER_V2_1_DIALOGUES.jsonl"

EXPECTED_SHA256 = {
    "source_html": "4ac9edd77fd8889aaeb73b8c15afc6c2ee1a3c0eb5cca1e4d2b24e862da98a7e",
    "source_build": "3db5b74367a43a2f79babfdc67f6700e0e5a06105da112321823dcb631955a7c",
    "source_audit": "3a47c2e3509dae16852ff90dcf295ddc602c89f6773e0198a9e9e700b242fc78",
    "samples_csv": "31bea32b1cd44f5e9e77baa84259a6fa3566a192f866a5b006371700fa1fe93f",
    "pv_manifest": "acb8772e1f4ab8860ebc0631517f616eeb2b2e0f5eeb8e1d890abf462248ad51",
    "zero_drop_dictionary": "f87a5684d4c7f21752ad9c4c023c28264471436eae9885a93cbd7a34e601c173",
    "additional_information_schema": "b1992e21f9431e5d066e396264eb61b89dff652d950f4e6fa7a6bb9d1b14c3f3",
    "approved_plan": "22ec8d8ca8ba286f93bcf027b25e97bf9a312bb53f73acb9f21e24833ced1bd9",
}

EXPECTED_TIERS = [
    "words",
    "phones_mfa",
    "phoneme_r_auto",
    "utterance",
    "utterance_orth_r",
    "morph_analysis_utt",
]
EXPECTED_NI_IDS = ["PV0015", "PV0163"]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_json_constant(document: str, name: str, next_name: str) -> Any:
    match = re.search(
        rf"const {re.escape(name)}=(.*?);\nconst {re.escape(next_name)}=",
        document,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"HTML JSON constant missing: {name}")
    return json.loads(match.group(1))


def parse_jsonl(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label} line {line_number} parse failure") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"{label} line {line_number} is not an object")
        rows.append(value)
    return rows


def compare_receipted_file(
    path: Path, receipt: Mapping[str, Any], errors: list[str], label: str
) -> dict[str, Any]:
    payload = path.read_bytes()
    measured = {"path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload)}
    if len(payload) != int(receipt.get("bytes", -1)):
        errors.append(f"{label} byte count differs from build receipt")
    if measured["sha256"] != receipt.get("sha256"):
        errors.append(f"{label} SHA-256 differs from build receipt")
    return measured


def independent_textgrid_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    if 'File type = "ooTextFile"' not in text or 'Object class = "TextGrid"' not in text:
        raise RuntimeError("invalid TextGrid header")
    names = [value.replace('""', '"') for value in re.findall(r'(?m)^        name = "((?:""|[^"])*)"\s*$', text)]
    xmax_match = re.search(r"(?m)^xmax = ([+\-0-9.eE]+)\s*$", text)
    if not xmax_match:
        raise RuntimeError("TextGrid xmax missing")
    return {"tier_names": names, "xmax": float(xmax_match.group(1))}


def _safe_project_path(identifier: str) -> Path:
    path = (PROJECT_ROOT / identifier).resolve(strict=True)
    try:
        path.relative_to(PROJECT_ROOT.resolve(strict=True))
    except ValueError as exc:
        raise RuntimeError(f"asset identifier escapes project root: {identifier}") from exc
    return path


def audit(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve(strict=True)
    approved_parent = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if input_dir.parent != approved_parent:
        raise RuntimeError(f"Gate 2 output must be a direct outputs/pilots child: {input_dir}")
    build_path = input_dir / BUILD_NAME
    html_path = input_dir / HTML_NAME
    imported_path = input_dir / IMPORTED_NAME
    dialogue_path = input_dir / DIALOGUE_NAME
    build = json.loads(build_path.read_text(encoding="utf-8"))
    html_bytes = html_path.read_bytes()
    document = html_bytes.decode("utf-8")
    errors: list[str] = []

    if build.get("schema_version") != "stage2_gate2_ni_followup_reviewer_v3_build.v1":
        errors.append("unexpected build schema")
    if build.get("status") != "built_pending_independent_audit":
        errors.append("unexpected build status")
    scope = build.get("scope", {})
    expected_scope = {
        "samples": 14,
        "ni_method_reference": 2,
        "cross_phenomenon_ui_regression_only": 12,
        "new_candidate_extraction": False,
        "g5_g6_run": False,
        "inter_eojeol_ni_method_sample": False,
    }
    if scope != expected_scope:
        errors.append(f"Gate 2 scope differs: {scope}")
    for key, expected in EXPECTED_SHA256.items():
        measured = build.get("pinned_inputs", {}).get(key, {}).get("sha256")
        if measured != expected:
            errors.append(f"pinned input SHA differs in receipt: {key}")

    output = build.get("output", {})
    measured_files = {
        "html": compare_receipted_file(html_path, output.get("html", {}), errors, "HTML"),
        "imported_jsonl": compare_receipted_file(
            imported_path, output.get("imported_jsonl", {}), errors, "imported JSONL"
        ),
        "dialogue_jsonl": compare_receipted_file(
            dialogue_path, output.get("dialogue_jsonl", {}), errors, "dialogue JSONL"
        ),
    }

    source_root = Path(build.get("source_v2_1", {}).get("root", "")).resolve(strict=True)
    source_html_path = source_root / SOURCE_HTML
    source_imported_path = source_root / SOURCE_IMPORTED
    source_dialogue_path = source_root / SOURCE_DIALOGUES
    if sha256_file(source_html_path) != EXPECTED_SHA256["source_html"]:
        errors.append("source v2.1 HTML no longer matches pinned SHA")
    if imported_path.read_bytes() != source_imported_path.read_bytes():
        errors.append("legacy 15-row JSONL is not byte-identical to v2.1")
    if dialogue_path.read_bytes() != source_dialogue_path.read_bytes():
        errors.append("dialogue JSONL is not byte-identical to v2.1")
    source_html_bytes = source_html_path.read_bytes()
    source_document = source_html_bytes.decode("utf-8")

    samples = extract_json_constant(document, "SAMPLES", "TEXTGRID_ASSETS")
    assets = extract_json_constant(document, "TEXTGRID_ASSETS", "GATE2_META")
    gate2_meta = extract_json_constant(document, "GATE2_META", "DIALOGUES")
    source_samples = extract_json_constant(source_document, "SAMPLES", "DIALOGUES")
    if samples != source_samples:
        errors.append("embedded SAMPLES changed from v2.1")
    if len(samples) != 14 or len({row.get("pv_id") for row in samples}) != 14:
        errors.append("output does not retain 14 unique samples")
    ni_ids = [row.get("pv_id") for row in samples if row.get("phenomenon_code") == "NI"]
    if ni_ids != EXPECTED_NI_IDS:
        errors.append(f"NI method sample IDs differ: {ni_ids}")
    if gate2_meta.get("record_role") != "exploratory_gate2_followup_need_not_formal_realization_ledger":
        errors.append("embedded Gate 2 record role differs")
    if gate2_meta.get("source_v2_1_html_sha256") != EXPECTED_SHA256["source_html"]:
        errors.append("embedded source v2.1 SHA differs")

    for name, next_name in (
        ("DIALOGUES", "BASE_HISTORY"),
        ("BASE_HISTORY", "LITERATURE"),
        ("LITERATURE", "BUILD_META"),
    ):
        if extract_json_constant(document, name, next_name) != extract_json_constant(
            source_document, name, next_name
        ):
            errors.append(f"embedded {name} changed from v2.1")

    source_audio = re.findall(rb"data:audio/wav;base64,([A-Za-z0-9+/=]+)", source_html_bytes)
    output_audio = re.findall(rb"data:audio/wav;base64,([A-Za-z0-9+/=]+)", html_bytes)
    source_audio_hashes = [sha256_bytes(base64.b64decode(value, validate=True)) for value in source_audio]
    output_audio_hashes = [sha256_bytes(base64.b64decode(value, validate=True)) for value in output_audio]
    if len(output_audio) != 28:
        errors.append(f"embedded WAV count differs: {len(output_audio)}")
    if output_audio_hashes != source_audio_hashes:
        errors.append("embedded WAV hashes/order changed from v2.1")

    imported_rows = parse_jsonl(imported_path.read_bytes(), IMPORTED_NAME)
    dialogue_rows = parse_jsonl(dialogue_path.read_bytes(), DIALOGUE_NAME)
    if len(imported_rows) != 15 or len({row.get("review_event_id") for row in imported_rows}) != 14:
        errors.append("legacy imported history is not 15 rows/14 events")
    if any(row.get("schema_version") is not None for row in imported_rows):
        errors.append("legacy imported rows were rewritten with a schema version")
    if len(dialogue_rows) != 4060:
        errors.append(f"dialogue row count differs: {len(dialogue_rows)}")

    if len(assets) != 14 or len({row.get("pv_id") for row in assets}) != 14:
        errors.append("TextGrid asset projection is not 14 unique rows")
    role_counts = {
        "ni_method_reference": sum(row.get("gate_method_role") == "ni_method_reference" for row in assets),
        "cross_phenomenon_ui_regression_only": sum(
            row.get("gate_method_role") == "cross_phenomenon_ui_regression_only" for row in assets
        ),
    }
    if role_counts != {"ni_method_reference": 2, "cross_phenomenon_ui_regression_only": 12}:
        errors.append(f"Gate method roles differ: {role_counts}")
    asset_status_counts = {
        status: sum(row.get("textgrid_asset_status") == status for row in assets)
        for status in ("available", "unavailable", "blocked")
    }
    available_verified = 0
    for asset in assets:
        pv_id = str(asset.get("pv_id"))
        status = asset.get("textgrid_asset_status")
        if status not in {"available", "unavailable", "blocked"}:
            errors.append(f"{pv_id}: invalid asset status")
            continue
        if status != "available":
            if not asset.get("asset_issue_codes"):
                errors.append(f"{pv_id}: unavailable/blocked asset has no issue code")
            continue
        try:
            textgrid_path = _safe_project_path(str(asset["source_textgrid_identifier"]))
            wav_path = _safe_project_path(str(asset["source_wav_identifier"]))
            if sha256_file(textgrid_path) != asset.get("source_textgrid_sha256"):
                errors.append(f"{pv_id}: source TextGrid SHA differs")
            if sha256_file(wav_path) != asset.get("source_wav_sha256"):
                errors.append(f"{pv_id}: source WAV SHA differs")
            summary = independent_textgrid_summary(textgrid_path)
            if summary["tier_names"] != EXPECTED_TIERS:
                errors.append(f"{pv_id}: independent tier order differs")
            if not (0 <= float(asset["target_xmin"]) < float(asset["target_xmax"]) <= summary["xmax"] + 1e-9):
                errors.append(f"{pv_id}: target span outside independently measured TextGrid")
            textgrid = asset.get("textgrid") or {}
            if [tier.get("name") for tier in textgrid.get("tiers", [])] != EXPECTED_TIERS:
                errors.append(f"{pv_id}: embedded tier order differs")
            waveform = asset.get("waveform") or {}
            peaks = waveform.get("peaks") or []
            if waveform.get("bins") != 320 or len(peaks) != 320:
                errors.append(f"{pv_id}: waveform peak cardinality differs")
            if any(not isinstance(value, (int, float)) or value < 0 or value > 1 for value in peaks):
                errors.append(f"{pv_id}: waveform peak outside [0,1]")
            if asset.get("manual_task_status") != "not_created":
                errors.append(f"{pv_id}: formal/manual task status unexpectedly advanced")
            available_verified += 1
        except Exception as exc:
            errors.append(f"{pv_id}: independent asset verification failed: {type(exc).__name__}")
    if asset_status_counts != {"available": 14, "unavailable": 0, "blocked": 0}:
        errors.append(f"real asset status counts differ: {asset_status_counts}")

    required_markers = (
        "Stage 2 Gate 2 · NI 후속 TextGrid reviewer v3",
        'name="textgrid_review_need"',
        'name="textgrid_review_reasons_json"',
        'name="additional_information_requests_json"',
        'name="followup_need_confidence"',
        "read-only TextGrid·파형 후속 검토",
        "shouldOpenTextGrid",
        "makeGate2Revision",
        "buildQueueCandidates",
        "reviewCoverage",
        "exploratory_queue_candidate_not_manual_task",
        "이전 PV-A 표본 태그(연구 우선순위 아님)",
        "저장하지 않은 변경이 있습니다.",
        "beforeunload",
        "PV_REVIEWER_V3_TEST_API",
    )
    for marker in required_markers:
        if marker not in document:
            errors.append(f"required Gate 2 marker missing: {marker}")
    for forbidden in (
        '<label for="priority-filter">우선순위</label>',
        'id="priority-tag"',
        "contenteditable=",
        'src="http',
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "automatic_realization_judgement=true",
    ):
        if forbidden in document:
            errors.append(f"forbidden behavior remains: {forbidden}")

    safety = build.get("safety", {})
    for field in (
        "source_files_modified",
        "source_corpus_scanned",
        "source_audio_modified",
        "source_textgrid_modified",
        "textgrid_boundary_edit_enabled",
        "formal_manual_task_created",
        "automatic_realization_judgement",
        "formal_ledger_written",
        "mfa_run",
        "koina_run",
        "wav2vec2_run",
        "existing_output_overwritten",
    ):
        if safety.get(field) is not False:
            errors.append(f"safety assertion is not false: {field}")

    partials = [path for path in input_dir.rglob("*.partial")]
    if partials:
        errors.append(f"partial files remain in output: {len(partials)}")

    return {
        "schema_version": "stage2_gate2_ni_followup_reviewer_v3_audit.v1",
        "passed": not errors,
        "errors": errors,
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "counts": {
            "input_samples": len(samples),
            "output_samples": len(samples),
            "ni_method_reference": role_counts["ni_method_reference"],
            "cross_phenomenon_ui_regression_only": role_counts[
                "cross_phenomenon_ui_regression_only"
            ],
            "textgrid_asset_status": asset_status_counts,
            "available_assets_independently_verified": available_verified,
            "tier_count_per_available_asset": 6,
            "legacy_imported_rows": len(imported_rows),
            "legacy_unique_review_events": len(
                {row.get("review_event_id") for row in imported_rows}
            ),
            "dialogue_rows": len(dialogue_rows),
            "embedded_wav_payloads": len(output_audio),
            "embedded_wav_sha_matches_source": sum(
                left == right
                for left, right in zip(output_audio_hashes, source_audio_hashes)
            ),
            "new_candidate_extraction": 0,
            "g5_g6_runs": 0,
            "formal_manual_tasks": 0,
            "automatic_realization_judgements": 0,
            "formal_ledger_writes": 0,
        },
        "files": {
            **measured_files,
            "build": {
                "path": str(build_path),
                "bytes": build_path.stat().st_size,
                "sha256": sha256_file(build_path),
            },
            "source_v2_1_html": {
                "path": str(source_html_path),
                "bytes": source_html_path.stat().st_size,
                "sha256": sha256_file(source_html_path),
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


def manifest_rows(input_dir: Path, manifest_path: Path) -> list[tuple[str, int, str]]:
    partial = manifest_path.with_name(manifest_path.name + ".partial")
    rows = []
    for path in sorted(
        (item for item in input_dir.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(input_dir).as_posix(),
    ):
        if path in {manifest_path, partial}:
            continue
        rows.append(
            (
                path.relative_to(input_dir).as_posix(),
                path.stat().st_size,
                sha256_file(path),
            )
        )
    return rows


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
    rows = manifest_rows(input_dir, manifest_path)
    with partial.open("w", encoding="utf-8", newline="") as stream:
        for relative_path, size, digest in rows:
            stream.write(f"{digest}  {size}  {relative_path}\n")
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

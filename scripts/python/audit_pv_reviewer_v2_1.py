"""Independently audit the UI-only PV reviewer v2.1 derivative."""

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
    / "pv_seven_phenomena_reviewer_v2_1_20260822"
)
HTML_NAME = "PV_REVIEWER_V2_1.html"
BUILD_NAME = "PV_REVIEWER_V2_1_BUILD.json"
IMPORTED_NAME = "PV_REVIEWER_V2_1_IMPORTED_BASE.jsonl"
DIALOGUE_NAME = "PV_REVIEWER_V2_1_DIALOGUES.jsonl"
AUDIT_NAME = "PV_REVIEWER_V2_1_AUDIT.json"
MANIFEST_NAME = "PV_REVIEWER_V2_1_SHA256_MANIFEST.csv"
SOURCE_HTML = "PV_REVIEWER_V2.html"
SOURCE_IMPORTED = "PV_REVIEWER_V1_IMPORTED.jsonl"
SOURCE_DIALOGUES = "PV_REVIEWER_V2_DIALOGUES.jsonl"


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


def compare_receipted_file(
    path: Path, receipt: Mapping[str, Any], errors: list[str], label: str
) -> dict[str, Any]:
    payload = path.read_bytes()
    measured = {"path": str(path), "bytes": len(payload), "sha256": sha256_bytes(payload)}
    if len(payload) != int(receipt.get("bytes", -1)):
        errors.append(f"{label} bytes differ from build receipt")
    if measured["sha256"] != receipt.get("sha256"):
        errors.append(f"{label} SHA-256 differs from build receipt")
    return measured


def parse_jsonl(payload: bytes, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"{label} {line_no}행 is not an object")
        rows.append(value)
    return rows


def normalized_source_sample(sample: Mapping[str, Any]) -> dict[str, Any]:
    added = {
        "target_word_indices",
        "target_word_labels",
        "target_word_tokens_measured",
    }
    return {key: value for key, value in sample.items() if key not in added}


def audit(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve(strict=True)
    approved_parent = (PROJECT_ROOT / "outputs" / "pilots").resolve(strict=True)
    if input_dir.parent != approved_parent:
        raise RuntimeError(f"v2.1 derivative must be a direct child of outputs/pilots: {input_dir}")

    build_path = input_dir / BUILD_NAME
    html_path = input_dir / HTML_NAME
    imported_path = input_dir / IMPORTED_NAME
    dialogue_path = input_dir / DIALOGUE_NAME
    build = json.loads(build_path.read_text(encoding="utf-8"))
    html_bytes = html_path.read_bytes()
    document = html_bytes.decode("utf-8")
    errors: list[str] = []

    if build.get("schema_version") != "pv_reviewer_v2_1_build.v1":
        errors.append("unexpected build schema")
    if build.get("status") != "built_pending_independent_audit":
        errors.append("unexpected build status")
    if build.get("approval", {}).get("scope") != ["R01", "R06", "R07", "R08", "R09"]:
        errors.append("approved v2.1 scope differs")
    if build.get("approval", {}).get("r03_batch_builder_in_scope") is not False:
        errors.append("R03 unexpectedly entered v2.1 scope")
    if build.get("approval", {}).get("r04_scan_contract_change_in_scope") is not False:
        errors.append("R04 unexpectedly entered v2.1 scope")

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

    source_root = Path(build.get("source_v2", {}).get("root", "")).resolve(strict=True)
    source_html_path = source_root / SOURCE_HTML
    source_imported_path = source_root / SOURCE_IMPORTED
    source_dialogue_path = source_root / SOURCE_DIALOGUES
    source_audit_path = Path(build.get("source_v2", {}).get("audit_path", "")).resolve(strict=True)
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    if source_audit.get("passed") is not True or source_audit.get("errors") != []:
        errors.append("source v2 audit is not a clean pass")
    source_html_bytes = source_html_path.read_bytes()
    if sha256_bytes(source_html_bytes) != build.get("source_v2", {}).get("html", {}).get("sha256"):
        errors.append("source v2 HTML SHA differs from v2.1 receipt")
    if imported_path.read_bytes() != source_imported_path.read_bytes():
        errors.append("v2.1 imported history is not byte-identical to source v2")
    if dialogue_path.read_bytes() != source_dialogue_path.read_bytes():
        errors.append("v2.1 dialogue JSONL is not byte-identical to source v2")

    source_document = source_html_bytes.decode("utf-8")
    source_samples = extract_json_constant(source_document, "SAMPLES", "DIALOGUES")
    samples = extract_json_constant(document, "SAMPLES", "DIALOGUES")
    if len(samples) != 14 or len({row.get("pv_id") for row in samples}) != 14:
        errors.append("v2.1 SAMPLES is not 14 unique pv_id values")
    source_by_pv = {row["pv_id"]: row for row in source_samples}
    highlight_tokens = 0
    highlight_samples = 0
    for sample in samples:
        pv_id = sample.get("pv_id")
        if pv_id not in source_by_pv:
            errors.append(f"unexpected sample in v2.1: {pv_id}")
            continue
        if normalized_source_sample(sample) != source_by_pv[pv_id]:
            errors.append(f"{pv_id}: non-highlight sample payload changed")
        indices = sample.get("target_word_indices")
        labels = sample.get("target_word_labels")
        measured_tokens = sample.get("target_word_tokens_measured")
        if not isinstance(indices, list) or not indices:
            errors.append(f"{pv_id}: target indices missing")
            continue
        highlight_samples += 1
        highlight_tokens += len(indices)
        tokens = str(sample.get("active_form", "")).split()
        actual_tokens = [tokens[int(index) - 1] for index in indices]
        if measured_tokens != actual_tokens:
            errors.append(f"{pv_id}: measured target token evidence differs")
        if len(labels or []) != len(indices):
            errors.append(f"{pv_id}: target label/index count differs")
    if highlight_samples != 14 or highlight_tokens != 15:
        errors.append(
            f"highlight metadata counts differ: samples={highlight_samples}, tokens={highlight_tokens}"
        )

    unchanged_payloads = (
        ("DIALOGUES", "BASE_HISTORY"),
        ("BASE_HISTORY", "LITERATURE"),
        ("LITERATURE", "BUILD_META"),
    )
    for name, next_name in unchanged_payloads:
        if extract_json_constant(document, name, next_name) != extract_json_constant(
            source_document, name, next_name
        ):
            errors.append(f"embedded {name} payload changed from v2")

    source_audio = re.findall(rb"data:audio/wav;base64,([A-Za-z0-9+/=]+)", source_html_bytes)
    output_audio = re.findall(rb"data:audio/wav;base64,([A-Za-z0-9+/=]+)", html_bytes)
    source_audio_hashes = [sha256_bytes(base64.b64decode(item, validate=True)) for item in source_audio]
    output_audio_hashes = [sha256_bytes(base64.b64decode(item, validate=True)) for item in output_audio]
    if len(output_audio) != 28:
        errors.append(f"embedded WAV payload count={len(output_audio)}")
    if output_audio_hashes != source_audio_hashes:
        errors.append("embedded WAV payload hashes/order changed from v2")

    imported_rows = parse_jsonl(imported_path.read_bytes(), IMPORTED_NAME)
    dialogue_rows = parse_jsonl(dialogue_path.read_bytes(), DIALOGUE_NAME)
    if len(imported_rows) != 15 or len({row.get("review_event_id") for row in imported_rows}) != 14:
        errors.append("imported history is not the source 15-row/14-event contract")
    if len(dialogue_rows) != 4060:
        errors.append(f"dialogue row count={len(dialogue_rows)}")

    required_markers = (
        "PV 검토 화면 v2.1",
        "utterance mark",
        "highlightActiveForm",
        "requestActivate",
        "canDiscardDirty",
        "beforeunload",
        "reviewedAtMs",
        "Date.parse",
        "들린 형식·실현 인상에 대한 확신도",
        "표기 어절 수와 형태소 분석 어절 수가 달라 형태소를 연결하지 않았습니다.",
        "morphBoundaryLabel",
        "축약 음절",
        "저장하지 않은 변경이 있습니다.",
    )
    for marker in required_markers:
        if marker not in document:
            errors.append(f"required v2.1 behavior marker missing: {marker}")
    for forbidden in (
        "<title>PV 검토 화면 v2</title>",
        "<label>판단 확신도<select",
        "byId('active-form').textContent=s.active_form;",
        'src="http',
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
    ):
        if forbidden in document:
            errors.append(f"forbidden/obsolete behavior remains: {forbidden}")

    safety = build.get("safety", {})
    for field in (
        "source_v2_modified",
        "source_corpus_scanned",
        "source_files_modified",
        "audio_payload_changed",
        "automatic_realization_judgement",
        "formal_ledger_written",
        "mfa_run",
        "koina_run",
        "wav2vec2_run",
        "r03_batch_builder_implemented",
        "r04_scan_contract_changed",
        "existing_output_overwritten",
    ):
        if safety.get(field) is not False:
            errors.append(f"safety assertion is not false: {field}")

    return {
        "schema_version": "pv_reviewer_v2_1_audit.v1",
        "passed": not errors,
        "errors": errors,
        "recorded_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "counts": {
            "samples": len(samples),
            "highlight_samples": highlight_samples,
            "highlight_tokens": highlight_tokens,
            "imported_rows": len(imported_rows),
            "imported_unique_review_events": len(
                {row.get("review_event_id") for row in imported_rows}
            ),
            "dialogue_rows": len(dialogue_rows),
            "embedded_wav_payloads": len(output_audio),
            "embedded_wav_sha_matches_source": sum(
                left == right for left, right in zip(output_audio_hashes, source_audio_hashes)
            ),
            "accepted_recommendations": 5,
            "r03_implemented": 0,
            "r04_contract_changes": 0,
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
            "source_v2_html": {
                "path": str(source_html_path),
                "bytes": len(source_html_bytes),
                "sha256": sha256_bytes(source_html_bytes),
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
        if path in {manifest_path, partial}:
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

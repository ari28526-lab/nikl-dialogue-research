"""Independently audit the self-contained PV-A iPad derivative."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "work" / "pv_ipad_balanced14_20260820"
HTML_NAME = "PV_IPAD_BALANCED14_20260820.html"
RECEIPT_NAME = "PV_IPAD_BALANCED14_20260820_RECEIPT.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def audit(input_dir: Path) -> dict[str, Any]:
    input_dir = input_dir.resolve(strict=True)
    approved_work = (PROJECT_ROOT / "work").resolve(strict=True)
    if input_dir == approved_work or approved_work not in input_dir.parents:
        raise RuntimeError(f"iPad derivative must be under work: {input_dir}")
    html_path = input_dir / HTML_NAME
    receipt_path = input_dir / RECEIPT_NAME
    html_bytes = html_path.read_bytes()
    document = html_bytes.decode("utf-8")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    records = receipt.get("selection", {}).get("records", [])
    if len(records) != 14:
        errors.append(f"selection record count={len(records)}")
    if len({row.get("pv_id") for row in records}) != 14:
        errors.append("selected pv_id values are not 14 unique items")
    expected_cells = {
        (code, year)
        for code in ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")
        for year in (2020, 2025)
    }
    actual_cells = {
        (row.get("phenomenon_code"), int(row.get("year", 0))) for row in records
    }
    if actual_cells != expected_cells:
        errors.append("phenomenon/year balanced cells mismatch")

    audio_payloads = re.findall(
        rb'data:audio/wav;base64,([A-Za-z0-9+/=]+)', html_bytes
    )
    expected_audio_hashes: list[str] = []
    for row in records:
        expected_audio_hashes.extend(
            [row.get("target_wav_sha256", ""), row.get("context_wav_sha256", "")]
        )
    actual_audio_hashes: list[str] = []
    for index, encoded in enumerate(audio_payloads):
        try:
            payload = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            errors.append(f"embedded audio {index}: invalid base64 {exc}")
            continue
        if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
            errors.append(f"embedded audio {index}: not RIFF/WAVE")
        actual_audio_hashes.append(sha256_bytes(payload))
    if len(audio_payloads) != 28:
        errors.append(f"embedded audio count={len(audio_payloads)}")
    if actual_audio_hashes != expected_audio_hashes:
        errors.append("embedded WAV hashes do not match source receipts")

    structural_counts = {
        "sample_sections": document.count('<section class="sample"'),
        "review_forms": document.count('<form class="review"'),
        "audio_elements": document.count("<audio "),
    }
    if structural_counts != {
        "sample_sections": 14,
        "review_forms": 14,
        "audio_elements": 28,
    }:
        errors.append(f"HTML structural counts mismatch: {structural_counts}")
    for forbidden in ('src="http', "fetch(", "XMLHttpRequest", "WebSocket"):
        if forbidden in document:
            errors.append(f"external/network behavior found: {forbidden}")
    for required in (
        "localStorage",
        'id="export"',
        'id="copy"',
        'id="copy-text"',
        "자동 실현 판정을 하지 않습니다",
    ):
        if required not in document:
            errors.append(f"required iPad behavior/limit missing: {required}")
    output = receipt.get("output", {})
    if len(html_bytes) != int(output.get("bytes", -1)):
        errors.append("HTML byte count differs from receipt")
    if sha256_bytes(html_bytes) != output.get("sha256"):
        errors.append("HTML SHA differs from receipt")
    safety = receipt.get("safety", {})
    for field in (
        "source_files_modified",
        "audio_transcoded",
        "automatic_realization_judgement",
        "formal_ledger_written",
        "existing_output_overwritten",
    ):
        if safety.get(field) is not False:
            errors.append(f"safety assertion is not false: {field}")
    return {
        "schema_version": "pv_ipad_balanced14_audit.v1",
        "passed": not errors,
        "errors": errors,
        "counts": {
            **structural_counts,
            "embedded_wav_sha_matches": sum(
                left == right
                for left, right in zip(actual_audio_hashes, expected_audio_hashes)
            ),
            "external_sources": 0
            if not any(token in document for token in ('src="http', "fetch("))
            else 1,
        },
        "html": {
            "path": str(html_path),
            "bytes": len(html_bytes),
            "sha256": sha256_bytes(html_bytes),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    args = parser.parse_args()
    try:
        result = audit(args.input_dir)
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

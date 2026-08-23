from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")


class ReviewerAuditError(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
DEFAULT_PACKAGE = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/researcher_review_package_v1"
)
DEFAULT_OUTPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/reviewer_package_audit_v1"
)
DEFAULT_SCOPE_CARDS = Path("config/phenomenon_scope_cards_candidate_v1_20260823.jsonl")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewerAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewerAuditError(f"JSONL parse failure {path}:{line_number}: {exc}") from exc
            require(isinstance(row, dict), f"JSONL row is not object: {path}:{line_number}")
            rows.append(row)
    require(bool(rows), f"empty JSONL: {path}")
    return rows


def extract_json_script(document: str, element_id: str) -> Any:
    match = re.search(
        rf'<script id="{re.escape(element_id)}" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    require(match is not None, f"embedded JSON script missing: {element_id}")
    return json.loads(match.group(1).replace("<\\/", "</"))


def parse_manifest(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"manifest syntax line {line_number}")
        rows.append((match.group(1), match.group(2)))
    require(bool(rows), "empty SHA manifest")
    require(len({relative for _, relative in rows}) == len(rows), "duplicate manifest path")
    return rows


def extract_start_labels(document: str) -> dict[str, str]:
    matches = re.findall(
        r'<a href="STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW\.html\?phenomenon=([A-Z]+)">'
        r'\1 · (.*?) 시작</a>',
        document,
    )
    labels = {code: html.unescape(label) for code, label in matches}
    require(list(labels) == EXPECTED_CODES, f"START_HERE link codes/order: {list(labels)}")
    return labels


def audit(
    package_dir: Path, *, cards_path: Path,
    reference_package_dir: Path | None = None
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    require(package_dir.is_dir(), f"package missing: {package_dir}")
    manifest_path = package_dir / "SHA256SUMS.txt"
    manifest_rows = parse_manifest(manifest_path)
    hash_failures = []
    for expected, relative in manifest_rows:
        path = package_dir / Path(relative)
        if not path.is_file():
            hash_failures.append({"path": relative, "status": "missing"})
        else:
            measured = sha256_file(path)
            if measured != expected:
                hash_failures.append(
                    {"path": relative, "status": "sha_mismatch", "expected": expected, "measured": measured}
                )
    require(not hash_failures, f"manifest failures: {hash_failures[:3]}")

    receipt = load_json(package_dir / "BUILD_RECEIPT.json")
    require(receipt.get("passed") is True, "build receipt not passed")
    require(receipt.get("status") == "researcher_ready_no_listening_started", "build status")
    safety = receipt.get("safety", {})
    require(safety.get("wav_cut_or_transformed") is False, "WAV transformation safety")
    require(safety.get("automatic_realization_judgement") is False, "automatic realization safety")
    require(safety.get("formal_ledger_written") is False, "formal ledger safety")

    assets = read_csv(package_dir / "ASSET_MANIFEST.csv")
    require(len(assets) == 84, f"asset row count: {len(assets)}")
    for row in assets:
        wav = package_dir / row["bundle_wav_path"]
        source_tg = package_dir / row["bundle_source_textgrid_path"]
        work_tg = package_dir / row["praat_work_textgrid_path"]
        require(sha256_file(wav) == row["source_wav_sha256"] == row["bundle_wav_sha256"], f"WAV SHA {row['sample_id']}")
        require(
            sha256_file(source_tg)
            == row["source_textgrid_sha256"]
            == row["bundle_source_textgrid_sha256"],
            f"source TextGrid SHA {row['sample_id']}",
        )
        require(
            sha256_file(work_tg) == row["source_textgrid_sha256"] == row["praat_work_initial_sha256"],
            f"initial Praat TextGrid SHA {row['sample_id']}",
        )

    tasks = read_csv(package_dir / "PRAAT_TASKS.csv")
    require(len(tasks) == 84, f"Praat task row count: {len(tasks)}")
    require(len({row["sample_id"] for row in tasks}) == 84, "Praat task IDs not unique")
    require(all(not row["researcher_need_edit"] for row in tasks), "Praat task template prefilled")

    ps1 = (package_dir / "open_praat_sample.ps1").read_bytes()
    require(ps1[:3] == b"\xef\xbb\xbf", "PowerShell wrapper lacks UTF-8 BOM")
    ps1_text = ps1[3:].decode("utf-8")
    require("&&" not in ps1_text and "??" not in ps1_text, "PowerShell 5.1 incompatible operator")
    require("Start-Process" in ps1_text and "--open" in ps1_text, "Praat launch contract")

    html_path = package_dir / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    document = html_path.read_text(encoding="utf-8")
    samples = extract_json_script(document, "samples-data")
    dialogues = extract_json_script(document, "dialogues-data")
    metadata = extract_json_script(document, "metadata-data")
    literature = extract_json_script(document, "literature-data")
    textgrids = extract_json_script(document, "textgrids-data")
    build_meta = extract_json_script(document, "build-data")
    require(len(samples) == 84, "embedded sample count")
    require(len({row["sample_id"] for row in samples}) == 84, "embedded sample IDs")
    counts = Counter(row["phenomenon_code"] for row in samples)
    require(all(counts[code] == 12 for code in EXPECTED_CODES), f"embedded phenomenon counts: {counts}")
    require(set(literature) == set(EXPECTED_CODES), "embedded literature codes")
    require(len(textgrids) == 84, "embedded TextGrid projections")
    require(all(row["utt_id"] in dialogues for row in samples), "sample missing dialogue key")
    require(all(row["utt_id"] in metadata for row in samples), "sample missing metadata key")
    require(build_meta.get("automatic_realization_judgement") is False, "embedded realization safety")
    required_ui = [
        'id="order-mode"',
        'id="review-form"',
        'name="environment_confidence"',
        'name="realization_confidence"',
        'name="boundary_edit_need"',
        'id="dialogue-search"',
        "P2H_EXPLORATORY_REVIEWS.jsonl",
        "record_role:'exploratory_pilot_only_not_formal_realization_ledger'",
    ]
    require(all(fragment in document for fragment in required_ui), "required reviewer UI fragment missing")
    require(document.count('id="review-form"') == 1, "review form must be one case per screen")

    cards = read_jsonl(cards_path)
    require([row.get("phenomenon_code") for row in cards] == EXPECTED_CODES, "scope card order/codes")
    expected_labels = {str(row["phenomenon_code"]): str(row["label_ko"]) for row in cards}
    start_labels = extract_start_labels((package_dir / "START_HERE.html").read_text(encoding="utf-8"))
    require(start_labels == expected_labels, f"START_HERE label mismatch: {start_labels}")

    new_ui_checks = {
        "history_global_shadow_absent": re.search(r"\bconst\s+history\s*=", document) is None,
        "window_history_replace_state": "window.history.replaceState" in document,
        "target_jump_button": 'id="target-jump"' in document
        and "표적 구간으로 이동" in document
        and "audio.currentTime=target" in document
        and "canplay" in document,
        "phenomenon_summary_schema": "stage2_two_hour_phenomenon_summary.v1" in document,
        "phenomenon_summary_role": "phenomenon_summary_exploratory_only_not_formal_ledger" in document,
        "phenomenon_summary_button": 'id="phenomenon-summary-save"' in document,
        "summary_excluded_from_case_latest": "reviewRows().filter(isSampleRecord)" in document,
        "summary_import_supported": "if(isSummaryRecord(row))" in document,
        "literature_note_immediate_storage": "문헌 메모 자동 저장됨" in document,
        "shuffled_blind_recheck": "blindRecheck" in document and "1차 판정(들린 실현·청취 확신도)은 가려집니다" in document,
        "confidence_anchors": all(
            fragment in document
            for fragment in [
                "5 · 단서 명확·재청취 불필요",
                "4 · 단서 우세",
                "3 · 단서 있으나 상충",
                "2 · 인상 수준",
                "1 · 추측",
            ]
        ),
        "import_error_line_number": "불러오기 실패 — 행 ${lineNumber}" in document,
    }
    require(all(new_ui_checks.values()), f"v2 UI check failure: {new_ui_checks}")

    reference_checks: dict[str, bool] = {}
    if reference_package_dir is not None:
        reference_package_dir = reference_package_dir.resolve()
        require(reference_package_dir.is_dir(), f"reference package missing: {reference_package_dir}")
        reference_document = (
            reference_package_dir / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
        ).read_text(encoding="utf-8")
        for element_id, current in [
            ("samples-data", samples),
            ("dialogues-data", dialogues),
            ("metadata-data", metadata),
            ("literature-data", literature),
            ("textgrids-data", textgrids),
        ]:
            reference_checks[f"{element_id}_unchanged"] = (
                extract_json_script(reference_document, element_id) == current
            )
        for filename in [
            "ASSET_MANIFEST.csv",
            "PRAAT_TASKS.csv",
            "DIALOGUE_SOURCE_RECEIPTS.json",
            "open_praat_sample.ps1",
        ]:
            reference_checks[f"{filename}_byte_equal"] = (
                sha256_file(reference_package_dir / filename) == sha256_file(package_dir / filename)
            )
        require(all(reference_checks.values()), f"reference preservation failure: {reference_checks}")

    return {
        "schema_version": "stage2_two_hour_reviewer_independent_audit.v2",
        "passed": True,
        "status": "researcher_package_independently_verified",
        "package_dir": str(package_dir),
        "counts": {
            "manifest_records_verified": len(manifest_rows),
            "asset_rows": len(assets),
            "praat_tasks": len(tasks),
            "embedded_samples": len(samples),
            "embedded_dialogue_keys": len(dialogues),
            "embedded_metadata_keys": len(metadata),
            "embedded_literature_codes": len(literature),
            "embedded_textgrid_projections": len(textgrids),
        },
        "hashes": {
            "package_sha_manifest": sha256_file(manifest_path),
            "build_receipt": sha256_file(package_dir / "BUILD_RECEIPT.json"),
            "review_html": sha256_file(html_path),
            "samples_input": build_meta.get("samples_sha256"),
        },
        "checks": {
            "all_manifest_hashes_match": True,
            "all_asset_copy_hashes_match": True,
            "powershell_utf8_bom": True,
            "powershell_5_1_operator_check": True,
            "one_case_per_screen_contract": True,
            "grouped_and_shuffled_modes": True,
            "whole_dialogue_search": True,
            "literature_panel": True,
            "read_only_textgrid_panel": True,
            "separate_praat_work_copy": True,
            "automatic_realization_judgement": False,
            "formal_ledger_written": False,
            "start_here_labels_match_scope_cards": True,
            **new_ui_checks,
            **reference_checks,
        },
    }


def write_result(output_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    require(not output_dir.exists(), f"audit output already exists: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    require(not partial.exists(), f"audit partial exists: {partial}")
    partial.mkdir(parents=True, exist_ok=False)
    result_path = partial / "AUDIT_STAGE2_TWO_HOUR_REVIEWER.json"
    result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sha_path = partial / "SHA256SUMS.txt"
    sha_path.write_text(f"{sha256_file(result_path)}  {result_path.name}\n", encoding="utf-8")
    os.replace(partial, output_dir)
    return {
        **report,
        "audit_output": str(output_dir / result_path.name),
        "audit_output_sha256": sha256_file(output_dir / result_path.name),
        "audit_sha_manifest": str(output_dir / sha_path.name),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently audit the two-hour seven-phenomena reviewer")
    parser.add_argument("--package-dir", type=Path, default=PROJECT_ROOT / DEFAULT_PACKAGE)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--scope-cards", type=Path, default=PROJECT_ROOT / DEFAULT_SCOPE_CARDS)
    parser.add_argument("--reference-package", type=Path)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = audit(
            args.package_dir.resolve(),
            cards_path=args.scope_cards.resolve(),
            reference_package_dir=(args.reference_package.resolve() if args.reference_package else None),
        )
        if not args.check_only:
            report = write_result(args.output_dir.resolve(), report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

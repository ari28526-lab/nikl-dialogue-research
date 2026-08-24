#!/usr/bin/env python3
"""Audit reviewer v3 integrity, compatibility, and safety boundaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_ROOT = PROJECT_ROOT / "outputs/pilots/pv_seven_phenomena_20260819/two_hour_research_pilots_20260823"
DEFAULT_SOURCE = PILOT_ROOT / "researcher_review_package_v2"
DEFAULT_PACKAGE = PILOT_ROOT / "researcher_review_package_v3_systematic"
DEFAULT_EXISTING_JSONL = Path(r"C:\Users\ari30\Dropbox\00_연구_파일럿_임시\2026-08-24_stage2_research_first_remote_workspace_v1\P2H_EXPLORATORY_REVIEWS.jsonl")
EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def embedded_json(document: str, element_id: str) -> Any:
    match = re.search(
        rf'<script id="{re.escape(element_id)}" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    require(match is not None, f"missing embedded JSON: {element_id}")
    return json.loads(match.group(1).replace("<\\/", "</"))


def verify_manifest(package: Path) -> int:
    manifest = package / "SHA256SUMS.txt"
    require(manifest.is_file(), "output manifest missing")
    count = 0
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"manifest syntax line {line_number}")
        expected, relative = match.groups()
        path = package / Path(relative)
        require(path.is_file(), f"manifest target missing: {relative}")
        require(sha256_file(path) == expected, f"manifest mismatch: {relative}")
        count += 1
    require(count >= 270, f"manifest unexpectedly small: {count}")
    return count


def source_manifest_sha(source: Path) -> str:
    return sha256_file(source / "SHA256SUMS.txt")


def compare_reused_files(source: Path, package: Path) -> int:
    checked = 0
    for directory in ["assets", "praat_work"]:
        source_files = sorted(path for path in (source / directory).rglob("*") if path.is_file())
        target_files = sorted(path for path in (package / directory).rglob("*") if path.is_file())
        require([p.relative_to(source / directory) for p in source_files] == [p.relative_to(package / directory) for p in target_files], f"{directory} file inventory")
        for source_file, target_file in zip(source_files, target_files):
            require(sha256_file(source_file) == sha256_file(target_file), f"copied asset differs: {source_file.name}")
            checked += 1
    for name in ["ASSET_MANIFEST.csv", "PRAAT_TASKS.csv", "DIALOGUE_SOURCE_RECEIPTS.json", "open_praat_sample.ps1"]:
        require(sha256_file(source / name) == sha256_file(package / name), f"reused file differs: {name}")
        checked += 1
    return checked


def validate_existing_jsonl(path: Path, samples: set[str]) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "not_present", "path": str(path), "rows": 0}
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditError(f"existing JSONL parse error line {line_number}: {exc}") from exc
            is_summary = str(row.get("schema_version", "")).startswith("stage2_two_hour_phenomenon_summary.")
            if is_summary:
                require(row.get("phenomenon_code") in EXPECTED_CODES, f"summary code line {line_number}")
            else:
                require(row.get("sample_id") in samples, f"unknown sample line {line_number}")
            rows.append(row)
    require(rows, "existing JSONL is empty")
    return {"status": "compatible", "path": str(path), "rows": len(rows), "sha256": sha256_file(path)}


def javascript_syntax(document: str) -> dict[str, Any]:
    scripts = re.findall(r'<script(?: [^>]*)?>(.*?)</script>', document, flags=re.DOTALL)
    code = next((script for script in reversed(scripts) if "const SAMPLES=" in script), None)
    require(code is not None, "main JavaScript not found")
    node = shutil.which("node")
    if not node:
        return {"status": "node_not_available", "bytes": len(code.encode("utf-8"))}
    result = subprocess.run([node, "--check", "-"], input=code, text=True, capture_output=True, encoding="utf-8")
    require(result.returncode == 0, f"JavaScript syntax failure: {result.stderr.strip()}")
    return {"status": "passed", "node": node, "bytes": len(code.encode("utf-8"))}


def safe_launcher_check(package: Path, known_sample: str) -> dict[str, Any]:
    script = package / "run_reviewer_with_praat.py"
    text = script.read_text(encoding="utf-8")
    required = ["ALLOWED_SAMPLES", "sample_id not in ALLOWED_SAMPLES", "PACKAGE_ROOT.resolve() not in wav.parents", "subprocess.Popen([str(praat), \"--open\""]
    for marker in required:
        require(marker in text, f"launcher safety marker missing: {marker}")
    probe = (
        "import importlib.util, pathlib; "
        f"p=pathlib.Path({str(script)!r}); "
        "s=importlib.util.spec_from_file_location('reviewer_server',p); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        f"w,t=m.sample_paths({known_sample!r}); assert w.is_file() and t.is_file(); "
        "ok=False; "
        "\ntry: m.sample_paths('../escape')\nexcept ValueError: ok=True\nassert ok"
    )
    result = subprocess.run([sys.executable, "-c", probe], text=True, capture_output=True, encoding="utf-8")
    require(result.returncode == 0, f"launcher whitelist probe failed: {result.stderr.strip()}")
    return {"status": "passed", "known_sample": known_sample}


def audit(package: Path, source: Path, existing_jsonl: Path) -> dict[str, Any]:
    package = package.resolve(); source = source.resolve()
    require(package.is_dir(), f"package missing: {package}")
    require(source.is_dir(), f"source missing: {source}")
    receipt = json.loads((package / "BUILD_RECEIPT.json").read_text(encoding="utf-8"))
    require(receipt.get("passed") is True, "build receipt not passed")
    current_source_sha = source_manifest_sha(source)
    require(receipt.get("source_manifest_sha256_before") == current_source_sha, "source v2 manifest changed")
    require(receipt.get("source_manifest_sha256_after") == current_source_sha, "source v2 after SHA mismatch")
    manifest_files = verify_manifest(package)
    copied_files = compare_reused_files(source, package)
    html_path = package / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    document = html_path.read_text(encoding="utf-8")
    samples = embedded_json(document, "samples-data")
    literature = embedded_json(document, "literature-data")
    factors = embedded_json(document, "factor-data")
    sample_status = embedded_json(document, "sample-audit-data")
    build = embedded_json(document, "build-data")
    require(len(samples) == 84 and len({row["sample_id"] for row in samples}) == 84, "embedded samples")
    require(list(literature) == EXPECTED_CODES, "literature codes")
    require(list(factors) == EXPECTED_CODES, "factor codes")
    require(list(sample_status) == EXPECTED_CODES, "sample audit codes")
    require(build.get("claims_rows") == 173, "claim ledger row count not embedded")
    for code in EXPECTED_CODES:
        require(factors[code].get("research_questions"), f"research questions missing: {code}")
        require(factors[code].get("sampling_requirements"), f"sampling requirements missing: {code}")
        require(sample_status[code].get("status") == "exploratory_not_balanced", f"sample warning missing: {code}")
    for marker in [
        'name="research_observation"', 'name="research_morphology_hypothesis"',
        'name="research_prosody_hypothesis"', 'name="research_literature_link"',
        'name="research_next_action"', 'name="pt_post_obstruent_membership"',
        'name="pt_compound_tensification_membership"', 'name="pt_sai_siot_analysis"',
        'name="nan_c2_nasal"', 'name="nan_baseline_or_prosody"',
        "stage2_two_hour_exploratory_review.v2", "function renderThoughts()",
        "START_REVIEWER_WITH_PRAAT.cmd",
    ]:
        require(marker in document or marker in (package / "README.md").read_text(encoding="utf-8"), f"required marker missing: {marker}")
    manifest_rows = list(csv.DictReader((package / "ASSET_MANIFEST.csv").open("r", encoding="utf-8-sig", newline="")))
    require(len(manifest_rows) == 84, "asset manifest rows")
    sample_ids = {row["sample_id"] for row in samples}
    require(sample_ids == {row["sample_id"] for row in manifest_rows}, "asset/sample IDs")
    existing = validate_existing_jsonl(existing_jsonl, sample_ids)
    js = javascript_syntax(document)
    launcher = safe_launcher_check(package, samples[0]["sample_id"])
    required_support = [
        "00_READ_ME_FIRST.md", "SEVEN_PHENOMENA_RESEARCH_MAP.md", "CURRENT_SAMPLE_AUDIT.md",
        "CURRENT_SAMPLE_AUDIT.json", "CLAUDE_COWORK_HANDOFF.md", "CLAUDE_COWORK_4H_SESSION_PROMPT.txt",
        "FOUR_HOUR_LITERATURE_SYNTHESIS_TEMPLATE.md", "FOUR_HOUR_LITERATURE_SESSION.html",
        "SEVEN_PHENOMENA_RESEARCH_MAP.html", "LITERATURE_GAP_REGISTER.jsonl",
        "LITERATURE_GAP_REGISTER.csv", "SAMPLING_FRAME_CANDIDATE.csv",
    ]
    require(all((package / "RESEARCH_SYSTEM" / name).is_file() for name in required_support), "research support inventory")
    return {"passed": True, "package": str(package), "source_v2_manifest_sha256": current_source_sha, "manifest_files": manifest_files, "exact_reused_files_checked": copied_files, "samples": len(samples), "phenomena": len(factors), "claim_ledger_rows": build["claims_rows"], "existing_jsonl": existing, "javascript": js, "praat_launcher": launcher}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--existing-jsonl", type=Path, default=DEFAULT_EXISTING_JSONL)
    args = parser.parse_args()
    print(json.dumps(audit(args.package, args.source, args.existing_jsonl), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

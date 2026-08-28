#!/usr/bin/env python3
"""Independently audit the Stage2 actual research guide package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


EXPECTED_CODES = ("PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        if values.get("href"):
            self.links.append(values["href"] or "")


def audit_guides(guide_dir: Path, scope_cards: Path, reviewer_package: Path) -> dict:
    guide_dir = guide_dir.resolve()
    scope_cards = scope_cards.resolve()
    reviewer_package = reviewer_package.resolve()
    failures: list[str] = []

    required = [
        "START_HERE.html",
        "ACTUAL_RESEARCH_GUIDE.md",
        "ACTUAL_RESEARCH_GUIDE.html",
        "SESSION_CHECKLIST.md",
        "SESSION_CHECKLIST.html",
        "UI_REDESIGN_OBSERVATIONS_TEMPLATE.md",
        "UI_REDESIGN_OBSERVATIONS_TEMPLATE.html",
        "BUILD_RECEIPT.json",
        "SHA256SUMS.txt",
    ]
    for code in EXPECTED_CODES:
        required.extend((f"PHENOMENON_GUIDES/{code}.md", f"PHENOMENON_GUIDES/{code}.html"))
    for relative in required:
        if not (guide_dir / relative).is_file():
            failures.append(f"missing required file: {relative}")

    manifest_entries: dict[str, str] = {}
    manifest_path = guide_dir / "SHA256SUMS.txt"
    if manifest_path.is_file():
        for line_number, raw in enumerate(manifest_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                digest, relative = raw.split("  ", 1)
            except ValueError:
                failures.append(f"malformed manifest line {line_number}")
                continue
            manifest_entries[relative] = digest
        actual = {
            path.relative_to(guide_dir).as_posix(): sha256(path)
            for path in guide_dir.rglob("*")
            if path.is_file() and path != manifest_path
        }
        if set(actual) != set(manifest_entries):
            failures.append("manifest path set mismatch")
        for relative, digest in actual.items():
            if manifest_entries.get(relative) != digest:
                failures.append(f"manifest hash mismatch: {relative}")

    cards = [json.loads(line) for line in scope_cards.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    labels = {card["phenomenon_code"]: card["label_ko"] for card in cards}
    if set(labels) != set(EXPECTED_CODES):
        failures.append("scope card code set mismatch")

    counts: Counter[str] = Counter()
    with (reviewer_package / "ASSET_MANIFEST.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            counts[row["phenomenon_code"]] += 1
    if any(counts[code] != 12 for code in EXPECTED_CODES):
        failures.append(f"reviewer sample counts mismatch: {dict(counts)}")

    for code in EXPECTED_CODES:
        md_path = guide_dir / "PHENOMENON_GUIDES" / f"{code}.md"
        html_path = guide_dir / "PHENOMENON_GUIDES" / f"{code}.html"
        if md_path.is_file() and html_path.is_file():
            md = md_path.read_text(encoding="utf-8")
            rendered = html_path.read_text(encoding="utf-8")
            for token in (code, labels[code], "candidate", "열린 질문", "종료"):
                if token not in md or token not in rendered:
                    failures.append(f"{code} guide missing token: {token}")

    link_count = 0
    for html_path in guide_dir.rglob("*.html"):
        parser = LinkCollector()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for href in parser.links:
            parts = urlsplit(href)
            if parts.scheme or not parts.path or parts.path.startswith("#"):
                continue
            target = (html_path.parent / unquote(parts.path)).resolve()
            link_count += 1
            reviewer_target = reviewer_package / Path(unquote(parts.path)).name
            is_reviewer_link = reviewer_package.name in Path(unquote(parts.path)).parts
            if not target.is_file() and not (is_reviewer_link and reviewer_target.is_file()):
                failures.append(f"broken local link: {html_path.relative_to(guide_dir)} -> {href}")

    all_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in guide_dir.rglob("*") if path.is_file())
    if "D:\\" in all_text:
        failures.append("guide package contains a raw D: path")
    if "automatic_realization_judgement\": true" in all_text.lower():
        failures.append("automatic realization judgement unexpectedly enabled")

    receipt_path = guide_dir / "BUILD_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    if receipt.get("scope_cards_sha256") != sha256(scope_cards):
        failures.append("scope card receipt hash mismatch")
    reviewer_html = reviewer_package / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    if receipt.get("reviewer_html_sha256") != sha256(reviewer_html):
        failures.append("reviewer HTML receipt hash mismatch")

    return {
        "schema_version": "stage2_actual_research_guides_audit.v1",
        "passed": not failures,
        "status": "passed_research_guides_verified" if not failures else "failed",
        "guide_dir": str(guide_dir),
        "phenomenon_codes": list(EXPECTED_CODES),
        "phenomenon_guides_html": sum((guide_dir / "PHENOMENON_GUIDES" / f"{code}.html").is_file() for code in EXPECTED_CODES),
        "phenomenon_guides_markdown": sum((guide_dir / "PHENOMENON_GUIDES" / f"{code}.md").is_file() for code in EXPECTED_CODES),
        "sample_counts": {code: counts[code] for code in EXPECTED_CODES},
        "total_samples": sum(counts.values()),
        "manifest_records_verified": len(manifest_entries),
        "local_links_checked": link_count,
        "candidate_status_preserved": all("candidate" in card["card_status"] for card in cards),
        "raw_corpus_read": False,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guide-dir", required=True, type=Path)
    parser.add_argument("--scope-cards", required=True, type=Path)
    parser.add_argument("--reviewer-package", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit_guides(args.guide_dir, args.scope_cards, args.reviewer_package)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

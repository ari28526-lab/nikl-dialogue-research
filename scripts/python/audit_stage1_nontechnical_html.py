#!/usr/bin/env python3
"""Audit the standalone nontechnical stage-1 HTML guide."""

from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REQUIRED_TEXT = (
    "처음 보는 사람을 위한 자료구축 1단계 안내",
    "5,103,356",
    "4,286,046",
    "817,310",
    "D: 드라이브 자체 인계",
    "원자료 직접 확보형 코드 재현",
    "GitHub 공개는 아직 확정되지 않았습니다",
    "MFA가 어떤 phone을 어느 시간에 놓았다고 해서",
    "특정 현상을 찾는 query와 후보표",
)


class GuideParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.h1 = 0
        self.h2 = 0
        self.tables = 0
        self.details = 0
        self.cards = 0
        self.routes = 0
        self.links: list[str] = []
        self.resources: list[str] = []
        self.lang_ko = False
        self.statusbar_accessible = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag == "html" and values.get("lang", "").lower().startswith("ko"):
            self.lang_ko = True
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "h2":
            self.h2 += 1
        elif tag == "table":
            self.tables += 1
        elif tag == "details":
            self.details += 1
        if "card" in classes:
            self.cards += 1
        if "route" in classes:
            self.routes += 1
        if "statusbar" in classes:
            self.statusbar_accessible = (
                values.get("role") == "img" and bool(values.get("aria-label"))
            )
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag in {"img", "script", "link", "source", "video", "audio"}:
            for key in ("src", "href"):
                if values.get(key):
                    self.resources.append(values[key])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_external(value: str) -> bool:
    scheme = urlsplit(value).scheme.lower()
    return scheme in {"http", "https"} or value.startswith("//")


def audit(path: Path) -> dict[str, object]:
    path = path.resolve()
    html = path.read_text(encoding="utf-8")
    parser = GuideParser()
    parser.feed(html)

    missing_text = [text for text in REQUIRED_TEXT if text not in html]
    external_resources = sorted({value for value in parser.resources if is_external(value)})
    broken_local_links: list[str] = []
    for link in parser.links:
        parts = urlsplit(link)
        if parts.scheme or link.startswith(("#", "mailto:", "data:", "//")):
            continue
        target = (path.parent / unquote(parts.path)).resolve()
        if not target.exists():
            broken_local_links.append(link)

    checks = {
        "title_exact": "처음 보는 사람을 위한 자료구축 1단계 안내"
        in "".join(parser.title_parts),
        "lang_is_korean": parser.lang_ko,
        "required_text_complete": not missing_text,
        "three_stat_cards_present": parser.cards == 3,
        "two_distribution_routes_present": parser.routes == 2,
        "faq_details_at_least_five": parser.details >= 5,
        "tables_at_least_one": parser.tables >= 1,
        "section_headings_at_least_eight": parser.h2 >= 8,
        "status_bar_has_accessible_label": parser.statusbar_accessible,
        "external_resources_zero": not external_resources,
        "broken_local_links_zero": not broken_local_links,
        "standalone_size_over_100kb": path.stat().st_size > 100_000,
    }
    passed = all(checks.values())
    return {
        "schema_version": "stage1_nontechnical_html_audit.v1",
        "status": "passed" if passed else "failed",
        "html": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "checks": checks,
        "counts": {
            "h1": parser.h1,
            "h2": parser.h2,
            "tables": parser.tables,
            "details": parser.details,
            "cards": parser.cards,
            "routes": parser.routes,
            "links": len(parser.links),
            "resource_references": len(parser.resources),
        },
        "details": {
            "missing_required_text": missing_text,
            "external_resources": external_resources,
            "broken_local_links": sorted(set(broken_local_links)),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(args.html)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

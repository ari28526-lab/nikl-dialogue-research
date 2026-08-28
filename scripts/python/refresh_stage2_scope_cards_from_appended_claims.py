#!/usr/bin/env python3
"""Create a new scope-card version that exposes appended canonical claims.

The script never edits the base cards or claim ledger.  It adds a claim reference
to a phenomenon card when the claim was appended after the frozen prefix and the
claim's phenomenon_codes explicitly contain that phenomenon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON error at {path}:{line_number}: {exc}") from exc
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refresh_cards(
    cards: list[dict[str, Any]], claims: list[dict[str, Any]], frozen_prefix_rows: int
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    if [row.get("phenomenon_code") for row in cards] != EXPECTED_CODES:
        raise ValueError("scope card order/codes differ from the seven-phenomena contract")
    claim_ids = [str(row.get("claim_id", "")) for row in claims]
    expected = [f"CLM-{number:04d}" for number in range(1, len(claims) + 1)]
    if claim_ids != expected:
        raise ValueError("claim IDs are not unique, contiguous, and ordered")
    if len(claims) < frozen_prefix_rows:
        raise ValueError("claim ledger is shorter than the frozen prefix")

    additions: dict[str, list[str]] = {code: [] for code in EXPECTED_CODES}
    refreshed = [dict(row) for row in cards]
    by_code = {str(row["phenomenon_code"]): row for row in refreshed}
    for claim in claims[frozen_prefix_rows:]:
        claim_id = str(claim["claim_id"])
        phenomenon_codes = {str(code) for code in claim.get("phenomenon_codes", [])}
        for code in EXPECTED_CODES:
            if code not in phenomenon_codes:
                continue
            refs = list(by_code[code].get("evidence_refs", []))
            if claim_id not in refs:
                refs.append(claim_id)
                by_code[code]["evidence_refs"] = refs
                additions[code].append(claim_id)
    return refreshed, additions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-cards", required=True, type=Path)
    parser.add_argument("--claims", required=True, type=Path)
    parser.add_argument("--output-cards", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--frozen-prefix-rows", type=int, default=156)
    args = parser.parse_args()

    for output in (args.output_cards, args.receipt):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing output: {output}")

    cards = read_jsonl(args.base_cards)
    claims = read_jsonl(args.claims)
    refreshed, additions = refresh_cards(cards, claims, args.frozen_prefix_rows)

    args.output_cards.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in refreshed) + "\n"
    args.output_cards.write_text(text, encoding="utf-8")

    flat = [claim_id for code in EXPECTED_CODES for claim_id in additions[code]]
    receipt = {
        "schema_version": "stage2_scope_cards_claim_refresh.v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_cards": {"path": str(args.base_cards), "sha256": sha256(args.base_cards)},
        "claims": {"path": str(args.claims), "rows": len(claims), "sha256": sha256(args.claims)},
        "frozen_prefix_rows": args.frozen_prefix_rows,
        "appended_claim_rows_considered": len(claims) - args.frozen_prefix_rows,
        "additions_by_phenomenon": additions,
        "addition_reference_count": len(flat),
        "unique_appended_claims_exposed": len(set(flat)),
        "claim_reference_multiplicity": dict(sorted(Counter(flat).items())),
        "output_cards": {"path": str(args.output_cards), "sha256": sha256(args.output_cards)},
        "safety": {
            "base_cards_modified": False,
            "claim_ledger_modified": False,
            "semantic_population_contract_changed": False,
            "only_evidence_refs_appended": True,
        },
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

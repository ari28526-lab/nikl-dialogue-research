"""Build a compact, read-only category summary for yearly MFA exclusions.

The pending candidate CSV files remain immutable.  This helper reduces tens of
thousands of candidate rows to one row per year while retaining hashes and
input-contract identities.  It never approves exclusions or starts MFA.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    sha256_file,
)


SCHEMA_VERSION = "mfa_exclusion_category_summary.v1"
REASON_CODES = (
    "audio_pairing_unresolved",
    "empty_reference_unresolved_symbol",
    "text_duration_impossible",
)
OUTPUT_FIELDS = (
    "year",
    "search_rows",
    "safe_body_rows",
    "candidate_count",
    *REASON_CODES,
    "candidate_pct",
    "input_contract_id",
    "decision",
)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object expected: {path}")
    return value


def _audit_year(audit: dict[str, object], year: str) -> dict[str, object]:
    rows = audit.get("years")
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise RuntimeError("audit years must be an object or list")
    matches = [row for row in rows if isinstance(row, dict) and str(row.get("year")) == year]
    if len(matches) != 1:
        raise RuntimeError(f"audit year record must be unique: {year}")
    return matches[0]


def summarize_year(review_root: Path, year: str) -> dict[str, object]:
    year_root = review_root / year
    manifest_path = year_root / "03_RESEARCHER_REVIEW_MANIFEST.json"
    candidate_path = year_root / "03_RESEARCHER_REVIEW.csv"
    manifest = _read_json(manifest_path)
    if (
        manifest.get("schema_version") != "mfa_exclusion_review_candidates.v1"
        or manifest.get("status") != "pending_researcher_review"
        or bool(manifest.get("automatic_approval_performed"))
        or str(manifest.get("year")) != year
    ):
        raise RuntimeError(f"pending candidate manifest contract mismatch: {year}")
    input_contract_id = str(manifest.get("input_contract_id") or "")
    if not input_contract_id:
        raise RuntimeError(f"input contract missing: {year}")
    candidate_fp = manifest.get("review_csv")
    if not isinstance(candidate_fp, dict):
        raise RuntimeError(f"candidate fingerprint missing: {year}")
    if Path(str(candidate_fp.get("path") or "")).resolve() != candidate_path.resolve():
        raise RuntimeError(f"candidate path differs from manifest: {year}")
    if sha256_file(candidate_path) != str(candidate_fp.get("sha256") or ""):
        raise RuntimeError(f"candidate hash differs from manifest: {year}")

    counts: Counter[str] = Counter()
    row_count = 0
    with candidate_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "year", "input_contract_id", "utt_id", "reason_code",
            "exclusion_scope", "decision",
        }
        if not required <= set(reader.fieldnames or ()):
            raise RuntimeError(f"candidate CSV schema mismatch: {year}")
        seen: set[str] = set()
        for line_number, row in enumerate(reader, 2):
            if str(row.get("year")) != year:
                raise RuntimeError(f"candidate year mismatch: {year}:{line_number}")
            if str(row.get("input_contract_id")) != input_contract_id:
                raise RuntimeError(f"input contract mismatch: {year}:{line_number}")
            utt_id = str(row.get("utt_id") or "").strip()
            if not utt_id or utt_id in seen:
                raise RuntimeError(f"blank/duplicate utt_id: {year}:{line_number}")
            seen.add(utt_id)
            if str(row.get("decision")) != "pending":
                raise RuntimeError(f"candidate is not pending: {year}:{line_number}")
            if str(row.get("exclusion_scope")) != "alignment_and_analysis":
                raise RuntimeError(f"unexpected exclusion scope: {year}:{line_number}")
            reason = str(row.get("reason_code") or "")
            if reason not in REASON_CODES:
                raise RuntimeError(f"unexpected reason code: {year}:{reason}")
            counts[reason] += 1
            row_count += 1
    if row_count != int(manifest.get("candidate_count", -1)):
        raise RuntimeError(f"candidate count differs from manifest: {year}")

    audit_fp = manifest.get("audit_report")
    if not isinstance(audit_fp, dict):
        raise RuntimeError(f"audit fingerprint missing: {year}")
    audit_path = Path(str(audit_fp.get("path") or "")).resolve()
    if sha256_file(audit_path) != str(audit_fp.get("sha256") or ""):
        raise RuntimeError(f"audit hash differs from manifest: {year}")
    audit_row = _audit_year(_read_json(audit_path), year)
    audit_counts = audit_row.get("counts")
    if not isinstance(audit_counts, dict):
        raise RuntimeError(f"audit counts missing: {year}")
    search_rows = int(audit_counts.get("search_rows", -1))
    if search_rows < row_count:
        raise RuntimeError(f"candidate count exceeds search rows: {year}")
    safe_body_rows = search_rows - row_count
    return {
        "year": year,
        "search_rows": search_rows,
        "safe_body_rows": safe_body_rows,
        "candidate_count": row_count,
        **{reason: counts[reason] for reason in REASON_CODES},
        "candidate_pct": round(row_count / search_rows * 100, 4) if search_rows else 0.0,
        "input_contract_id": input_contract_id,
        "decision": "pending_researcher_category_approval",
        "candidate_manifest": file_fingerprint(manifest_path, with_sha256=True),
        "candidate_csv": file_fingerprint(candidate_path, with_sha256=True),
        "audit_report": file_fingerprint(audit_path, with_sha256=True),
    }


def write_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2021–2025 MFA 본체 우선 제외 범주 승인 요약",
        "",
        "이 문서는 승인 행을 자동으로 만들거나 MFA를 시작하지 않는다. 각 연도의",
        "원본 후보표·감사 보고서 SHA와 결속된 범주별 개수만 제시한다.",
        "",
        "| 연도 | 검색 발화 | 안전 본체 | 승인 후보 | 음원 대응 | 빈 참조 | 시간 불가능 | 후보 비율 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {year} | {search_rows:,} | {safe_body_rows:,} | "
            "{candidate_count:,} | {audio_pairing_unresolved:,} | "
            "{empty_reference_unresolved_symbol:,} | "
            "{text_duration_impossible:,} | {candidate_pct:.4f}% |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 세 범주의 뜻",
            "",
            "- `audio_pairing_unresolved`: JSON/CSV 발화와 같은 ID WAV가 같은 음성임을 보장할 수 없음. 본체 정렬에서 제외하고 회수 가능한 것만 후속 shard로 처리.",
            "- `empty_reference_unresolved_symbol`: MFA 입력으로 쓸 발음 참조가 비어 있음. 자동 추측하지 않고 제외.",
            "- `text_duration_impossible`: 원전 분절 시간에 비해 전사량이 물리적으로 불가능함. 잘못된 음원을 붙이지 않고 제외.",
            "",
            "승인은 5개년의 세 범주를 제외하는 방법론적 결정을 뜻한다. 원본 WAV/CSV를",
            "삭제하거나 바꾸지 않으며, 제외 ID·사유는 동반표와 manifest에 유지한다.",
        ]
    )
    with atomic_text_writer(path, encoding="utf-8", newline="") as (stream, _temp):
        stream.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-root", type=Path, required=True)
    parser.add_argument("--years", nargs="+", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    years = [str(value) for value in args.years]
    if len(set(years)) != len(years):
        raise RuntimeError("years must be unique")
    rows = [summarize_year(args.review_root.resolve(), year) for year in years]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pending_researcher_category_approval",
        "created_at": now_iso(),
        "mutates_inputs": False,
        "approves_exclusions": False,
        "starts_mfa": False,
        "years": years,
        "totals": {
            "search_rows": sum(int(row["search_rows"]) for row in rows),
            "safe_body_rows": sum(int(row["safe_body_rows"]) for row in rows),
            "candidate_count": sum(int(row["candidate_count"]) for row in rows),
            **{
                reason: sum(int(row[reason]) for row in rows)
                for reason in REASON_CODES
            },
        },
        "rows": rows,
    }
    with atomic_text_writer(
        args.output_csv.resolve(), encoding="utf-8-sig", newline=""
    ) as (stream, _temp):
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row[field] for field in OUTPUT_FIELDS} for row in rows)
    write_markdown(args.output_md.resolve(), rows)
    atomic_write_json(args.output_json.resolve(), report)
    print(
        json.dumps(
            {"status": report["status"], "totals": report["totals"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

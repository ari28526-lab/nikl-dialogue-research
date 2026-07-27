"""MFA 입력 감사의 형태소 원천 누락을 과거 원음 결함 근거와 조인한다.

``audit_mfa_year_readiness.py``의 발화별 inventory와
``source_pcm_check.csv``를 utt_id로 1:1 연결해, 배포 원음 자체가 짧거나
없는 제외 대상과 원음이 정상이라 형태소 정렬을 보완할 후보를 분리한다.
원자료·WAV·TextGrid는 읽기만 하고 CSV/JSON 보고서만 원자적으로 쓴다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    promote_staged,
    staged_text_writer,
)

EXCLUDE_CATEGORIES = {"원본짧음", "PCM없음"}
RECOVERY_CATEGORIES = {"원본정상"}
IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES = 10
IMPOSSIBLE_SPEECH_RATE_PER_SECOND = 40.0
FIELDS = [
    "year",
    "session",
    "utt_id",
    "morph_issue",
    "morph_path",
    "source_pcm_seconds",
    "source_pcm_category",
    "text_duration_status",
    "csv_duration_seconds",
    "hangul_syllables",
    "eojeol_count",
    "hangul_syllables_per_second",
    "eojeol_per_second",
    "exclusion_reason",
    "recommended_action",
]


def read_audit_issues(path: Path, year: str) -> list[dict[str, str]]:
    try:
        report = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"감사 보고서 읽기 실패: {path}: {exc}") from exc
    matches = [
        item
        for item in report.get("years", [])
        if str(item.get("year")) == year
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{year} 감사 결과가 정확히 1개가 아님: {len(matches)}"
        )
    issues = [
        item
        for item in matches[0].get("morph_source_issues", [])
        if item.get("issue") in {
            "morph_source_missing",
            "morph_source_zero_byte",
        }
    ]
    ids = [str(item.get("utt_id") or "") for item in issues]
    if any(not utt_id for utt_id in ids):
        raise RuntimeError("형태소 issue에 빈 utt_id")
    if len(ids) != len(set(ids)):
        raise RuntimeError("형태소 issue에 중복 utt_id")
    return issues


def read_pcm_index(path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"year", "utt_id", "pcm_sec", "category"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"{path}: 필수 열 누락 {sorted(missing)}")
        for row in reader:
            utt_id = (row.get("utt_id") or "").strip()
            if not utt_id:
                raise RuntimeError(f"{path}: 빈 utt_id")
            if utt_id in result:
                raise RuntimeError(f"{path}: 중복 utt_id {utt_id}")
            result[utt_id] = row
    return result


def read_search_metrics(
    search_master_root: Path | None,
    year: str,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, str | int | float]]:
    """관련 세션만 읽어 전사량과 CSV duration의 물리적 대응을 계산한다."""
    if search_master_root is None:
        return {}
    wanted_by_session: dict[str, set[str]] = {}
    for issue in issues:
        session = str(issue.get("session") or "")
        utt_id = str(issue.get("utt_id") or "")
        wanted_by_session.setdefault(session, set()).add(utt_id)
    result: dict[str, dict[str, str | int | float]] = {}
    for session, wanted in wanted_by_session.items():
        path = search_master_root / year / f"{session}.csv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {
                "utt_id",
                "form",
                "pron_reference_form",
                "dur",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"{path}: 검색 CSV 필수 열 누락 {sorted(missing)}"
                )
            for row in reader:
                utt_id = (row.get("utt_id") or "").strip()
                if utt_id not in wanted:
                    continue
                reference = (
                    row.get("pron_reference_form")
                    or row.get("form")
                    or ""
                ).strip()
                dur_raw = (row.get("dur") or "").strip()
                try:
                    duration = float(dur_raw)
                    duration_status = (
                        "ok" if duration > 0 else "nonpositive_duration"
                    )
                except ValueError:
                    duration = 0.0
                    duration_status = "invalid_duration"
                syllables = len(re.findall(r"[가-힣]", reference))
                eojeol = len(reference.split())
                result[utt_id] = {
                    "text_duration_status": duration_status,
                    "csv_duration_seconds": (
                        duration if duration_status == "ok" else dur_raw
                    ),
                    "hangul_syllables": syllables,
                    "eojeol_count": eojeol,
                    "hangul_syllables_per_second": (
                        syllables / duration
                        if duration_status == "ok"
                        else 0.0
                    ),
                    "eojeol_per_second": (
                        eojeol / duration
                        if duration_status == "ok"
                        else 0.0
                    ),
                }
    missing_ids = {
        str(issue["utt_id"]) for issue in issues
    } - set(result)
    if missing_ids:
        raise RuntimeError(
            "검색 CSV에서 형태소 issue ID 누락: "
            + ", ".join(sorted(missing_ids)[:20])
        )
    return result


def classify(
    *,
    audit_report: Path,
    source_pcm_check: Path,
    year: str,
    search_master_root: Path | None = None,
) -> tuple[list[dict[str, str]], dict]:
    issues = read_audit_issues(audit_report, year)
    pcm = read_pcm_index(source_pcm_check)
    search_metrics = read_search_metrics(
        search_master_root, year, issues
    )
    rows: list[dict[str, str]] = []
    categories: Counter = Counter()
    actions: Counter = Counter()
    exclusion_reasons: Counter = Counter()
    for issue in issues:
        utt_id = str(issue["utt_id"])
        prior = pcm.get(utt_id)
        category = (
            (prior.get("category") or "").strip()
            if prior is not None
            else "과거근거없음"
        )
        metrics = search_metrics.get(utt_id, {})
        syllables = int(metrics.get("hangul_syllables", 0))
        syllables_per_second = float(
            metrics.get("hangul_syllables_per_second", 0.0)
        )
        duration_status = str(
            metrics.get("text_duration_status", "")
        )
        impossible_segment = (
            duration_status == "ok"
            and syllables >= IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES
            and syllables_per_second
            >= IMPOSSIBLE_SPEECH_RATE_PER_SECOND
        )
        if category in EXCLUDE_CATEGORIES:
            action = "exclude_source_audio_unusable"
            exclusion_reason = (
                "source_pcm_missing"
                if category == "PCM없음"
                else "source_pcm_too_short"
            )
        elif category in RECOVERY_CATEGORIES and impossible_segment:
            action = "exclude_source_audio_unusable"
            exclusion_reason = (
                "source_segment_text_duration_impossible"
            )
        elif (
            category in RECOVERY_CATEGORIES
            and duration_status in {"", "ok"}
        ):
            action = "recover_morpheme_alignment_candidate"
            exclusion_reason = ""
        elif category in RECOVERY_CATEGORIES:
            action = "manual_review_unclassified"
            exclusion_reason = ""
        else:
            action = "manual_review_unclassified"
            exclusion_reason = ""
        categories[category] += 1
        actions[action] += 1
        if exclusion_reason:
            exclusion_reasons[exclusion_reason] += 1
        rows.append(
            {
                "year": year,
                "session": str(issue.get("session") or ""),
                "utt_id": utt_id,
                "morph_issue": str(issue.get("issue") or ""),
                "morph_path": str(issue.get("path") or ""),
                "source_pcm_seconds": (
                    (prior.get("pcm_sec") or "").strip()
                    if prior is not None
                    else ""
                ),
                "source_pcm_category": category,
                "text_duration_status": duration_status,
                "csv_duration_seconds": (
                    f"{float(metrics['csv_duration_seconds']):.6f}"
                    if metrics and duration_status == "ok"
                    else ""
                ),
                "hangul_syllables": (
                    str(metrics["hangul_syllables"]) if metrics else ""
                ),
                "eojeol_count": (
                    str(metrics["eojeol_count"]) if metrics else ""
                ),
                "hangul_syllables_per_second": (
                    f"{float(metrics['hangul_syllables_per_second']):.3f}"
                    if metrics
                    else ""
                ),
                "eojeol_per_second": (
                    f"{float(metrics['eojeol_per_second']):.3f}"
                    if metrics
                    else ""
                ),
                "exclusion_reason": exclusion_reason,
                "recommended_action": action,
            }
        )
    rows.sort(key=lambda row: (row["session"], row["utt_id"]))
    summary = {
        "schema_version": "mfa_input_issue_classification.v2",
        "year": year,
        "read_only": True,
        "audit_report": file_fingerprint(
            audit_report, with_sha256=True
        ),
        "source_pcm_check": file_fingerprint(
            source_pcm_check, with_sha256=True
        ),
        "counts": {
            "morph_source_issues": len(rows),
            "matched_prior_pcm_evidence": sum(
                row["source_pcm_category"] != "과거근거없음"
                for row in rows
            ),
            "source_audio_unusable_exclusions": actions[
                "exclude_source_audio_unusable"
            ],
            "morpheme_alignment_recovery_candidates": actions[
                "recover_morpheme_alignment_candidate"
            ],
            "manual_review_unclassified": actions[
                "manual_review_unclassified"
            ],
        },
        "by_source_pcm_category": dict(sorted(categories.items())),
        "by_recommended_action": dict(sorted(actions.items())),
        "by_exclusion_reason": dict(sorted(exclusion_reasons.items())),
        "text_duration_policy": {
            "enabled": search_master_root is not None,
            "search_master_root": (
                str(search_master_root.resolve())
                if search_master_root is not None
                else None
            ),
            "minimum_hangul_syllables": (
                IMPOSSIBLE_SPEECH_RATE_MIN_SYLLABLES
            ),
            "impossible_hangul_syllables_per_second": (
                IMPOSSIBLE_SPEECH_RATE_PER_SECOND
            ),
            "purpose": (
                "source segment와 전사 길이의 물리적 비대응만 제외; "
                "실제 발음 실현 판정에 사용하지 않음"
            ),
        },
        "all_issues_classified": (
            actions["manual_review_unclassified"] == 0
        ),
    }
    return rows, summary


def write_csv_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    with staged_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, temp):
        writer = csv.DictWriter(
            stream, fieldnames=FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    with open(temp, encoding="utf-8-sig", newline="") as stream:
        check = list(csv.DictReader(stream))
    if len(check) != len(rows):
        raise RuntimeError(
            f"분류 CSV 행수 검증 실패: {len(check)} != {len(rows)}"
        )
    promote_staged(temp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--source-pcm-check", type=Path, required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--search-master-root", type=Path)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    rows, summary = classify(
        audit_report=args.audit_report,
        source_pcm_check=args.source_pcm_check,
        year=args.year,
        search_master_root=args.search_master_root,
    )
    write_csv_atomic(args.output_csv, rows)
    summary["output_csv"] = str(args.output_csv.resolve())
    atomic_write_json(args.output_json, summary)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    return 0 if summary["all_issues_classified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

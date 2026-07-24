# -*- coding: utf-8 -*-
"""기존 search master를 수정하지 않고 원본 JSON·Bareun CSV와 전수 대조한다.

검사 범위
---------
1. 연도별 세션 파일 집합과 CSV 행 수
2. 원본 JSON → Bareun → search master의 utt_id 보존
3. form/tagged 보존, 중복·빈 ID, 출력 스키마
4. 2026-07-24에 복구한 네 세션의 문서 메타 반영 여부
5. coverage 열이 실제값인지 미계산/빈 값인지
6. lexicon v1의 발음 열 가용성과 builder 배선 여부

이 스크립트는 D: 입력을 읽기만 하고 프로젝트 outputs 아래에 JSON 보고서만 쓴다.
대량 CSV를 생성·수정·이동하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P
from pipeline_common import atomic_write_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

csv.field_size_limit(10_000_000)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECOVERED_META_SESSIONS = {
    "SDRW2300000445",
    "SDRW2300000457",
    "SDRW2300000473",
    "SDRW2300001337",
}
COVERAGE_COLS = ("has_wav", "has_tg_eojeol", "quarantined")
REQUIRED_MASTER_COLS = {
    "utt_id",
    "year",
    "session_id",
    "form",
    "tagged",
    "category_norm",
    "topic",
    *COVERAGE_COLS,
}


def year_folders(root: Path) -> dict[str, Path]:
    """연도 문자열이 포함된 직계 하위폴더를 {연도: 경로}로 반환한다."""
    result: dict[str, Path] = {}
    if not root.is_dir():
        return result
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        match = re.search(r"(20\d{2})", child.name)
        if match:
            year = match.group(1)
            if year in result:
                raise ValueError(
                    f"{root}: 연도 {year} 폴더가 둘 이상임: "
                    f"{result[year].name}, {child.name}"
                )
            result[year] = child
    return result


def csv_files(folder: Path) -> dict[str, Path]:
    """정식 세션 CSV만 stem 기준으로 색인한다."""
    if not folder.is_dir():
        return {}
    return {
        path.stem: path
        for path in sorted(folder.glob("*.csv"))
        if not path.name.startswith("_")
    }


def json_files_for_year(dialogue_root: Path, year: str) -> dict[str, Path]:
    """해당 연도 폴더 아래 JSON을 stem 기준으로 색인한다."""
    candidates = [
        folder
        for folder in sorted(dialogue_root.iterdir())
        if folder.is_dir() and year in folder.name
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"{dialogue_root}: {year} JSON 연도폴더가 1개가 아님: "
            f"{[p.name for p in candidates]}"
        )
    result: dict[str, Path] = {}
    for path in candidates[0].rglob("*.json"):
        if path.stem in result:
            raise ValueError(f"{year}: JSON stem 중복 {path.stem}")
        result[path.stem] = path
    return result


def read_json_utterances(path: Path) -> list[dict[str, object]]:
    """NIKL JSON의 모든 document.utterance를 원래 순서로 평탄화한다."""
    with open(path, encoding="utf-8") as stream:
        payload = json.load(stream)
    utterances: list[dict[str, object]] = []
    for document in payload.get("document", []):
        utterances.extend(document.get("utterance", []))
    return utterances


def _value_is_missing(value: str) -> bool:
    return value.strip() in {"", "미상"}


def audit_session(
    source_path: Path,
    master_path: Path,
    json_path: Path,
) -> dict[str, object]:
    """세 입력을 한 세션 단위로 읽어 ID와 핵심 필드를 대조한다."""
    result: dict[str, object] = {
        "source_rows": 0,
        "master_rows": 0,
        "json_rows": 0,
        "source_duplicate_ids": 0,
        "master_duplicate_ids": 0,
        "source_master_id_mismatch": 0,
        "source_master_form_mismatch": 0,
        "source_master_tagged_mismatch": 0,
        "json_missing_in_source": [],
        "source_missing_in_json": [],
        "header": [],
        "missing_required_cols": [],
        "coverage": {name: Counter() for name in COVERAGE_COLS},
        "meta_missing_rows": 0,
        "topic_missing_rows": 0,
        "category_values": Counter(),
        "topic_values": Counter(),
    }

    json_utts = read_json_utterances(json_path)
    result["json_rows"] = len(json_utts)
    json_ids = [str(row.get("id", "")) for row in json_utts]
    json_by_id = {str(row.get("id", "")): row for row in json_utts}

    with (
        open(source_path, encoding="utf-8-sig", newline="") as source_stream,
        open(master_path, encoding="utf-8-sig", newline="") as master_stream,
    ):
        source_reader = csv.DictReader(source_stream)
        master_reader = csv.DictReader(master_stream)
        header = master_reader.fieldnames or []
        result["header"] = header
        result["missing_required_cols"] = sorted(
            REQUIRED_MASTER_COLS - set(header)
        )

        source_seen: set[str] = set()
        master_seen: set[str] = set()
        source_ids: list[str] = []
        for source_row, master_row in zip_longest(
            source_reader, master_reader, fillvalue=None
        ):
            if source_row is not None:
                result["source_rows"] += 1
                source_id = source_row.get("utt_id", "")
                source_ids.append(source_id)
                if source_id in source_seen:
                    result["source_duplicate_ids"] += 1
                source_seen.add(source_id)
            else:
                source_id = ""

            if master_row is not None:
                result["master_rows"] += 1
                master_id = master_row.get("utt_id", "")
                if master_id in master_seen:
                    result["master_duplicate_ids"] += 1
                master_seen.add(master_id)
                for col in COVERAGE_COLS:
                    result["coverage"][col][master_row.get(col, "")] += 1
                category = master_row.get("category_norm", "")
                topic = master_row.get("topic", "")
                result["category_values"][category] += 1
                result["topic_values"][topic] += 1
                result["meta_missing_rows"] += _value_is_missing(category)
                result["topic_missing_rows"] += _value_is_missing(topic)
            else:
                master_id = ""

            if source_id != master_id:
                result["source_master_id_mismatch"] += 1
            if source_row is not None and master_row is not None:
                result["source_master_form_mismatch"] += (
                    source_row.get("form", "") != master_row.get("form", "")
                )
                result["source_master_tagged_mismatch"] += (
                    source_row.get("tagged", "") != master_row.get("tagged", "")
                )

    source_id_set = set(source_ids)
    json_id_set = set(json_ids)
    for utt_id in sorted(json_id_set - source_id_set):
        row = json_by_id.get(utt_id, {})
        result["json_missing_in_source"].append(
            {
                "utt_id": utt_id,
                "form_empty": not bool(str(row.get("form", "")).strip()),
                "original_form_empty": not bool(
                    str(row.get("original_form", "")).strip()
                ),
            }
        )
    result["source_missing_in_json"] = sorted(source_id_set - json_id_set)

    result["coverage"] = {
        name: dict(sorted(counter.items()))
        for name, counter in result["coverage"].items()
    }
    result["category_values"] = dict(
        sorted(result["category_values"].items())
    )
    result["topic_values"] = dict(sorted(result["topic_values"].items()))
    return result


def audit_lexicon(path: Path) -> dict[str, object]:
    """lexicon v1의 발음 열을 전수 집계한다."""
    counts = Counter()
    headers: list[str] = []
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        for row in reader:
            counts["rows"] += 1
            for col in ("pron_1", "pron_2", "pron_g2p", "morph_dict"):
                if (row.get(col) or "").strip():
                    counts[f"{col}_nonempty"] += 1
            if (row.get("pron_1") or "").strip():
                counts["preferred_pron_available"] += 1
            elif (row.get("pron_g2p") or "").strip():
                counts["preferred_pron_available"] += 1
                counts["g2p_fallback_only"] += 1
            else:
                counts["no_pron_available"] += 1
    return {
        "path": str(path),
        "header": headers,
        "counts": dict(counts),
    }


def audit_lexicon_wiring(
    builder_path: Path, predictor_path: Path, master_header: list[str]
) -> dict[str, object]:
    """실제 파일 로드·호출·출처 열 여부를 정적 확인한다."""
    builder = builder_path.read_text(encoding="utf-8")
    predictor = predictor_path.read_text(encoding="utf-8")
    source_cols = sorted(
        col
        for col in master_header
        if "lexicon" in col.lower() or "pron_source" in col.lower()
    )
    return {
        "predictor_has_index_helper": "def build_lexicon_index(" in predictor,
        "predictor_has_lookup_helper": "def lexicon_pron(" in predictor,
        "builder_mentions_lexicon_path": (
            'P("lexicon_full")' in builder
            or "P('lexicon_full')" in builder
        ),
        "builder_builds_lexicon_index": "build_lexicon_index(" in builder,
        "builder_passes_lexicon_to_predictor": (
            "lex_index=" in builder or "lexicon_index=" in builder
        ),
        "master_lexicon_source_columns": source_cols,
    }


def merge_counter(target: Counter, values: dict[str, int]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def compact_existing_report(
    report: dict[str, object],
    detail_session_limit: int,
    examples_per_session: int,
) -> dict[str, object]:
    """초기 상세판 보고서를 합계는 보존한 채 저장 친화적으로 축약한다."""
    mismatches = report.get("mismatches", {})
    json_sessions = mismatches.get("json_source_content_sessions", [])
    source_sessions = mismatches.get("source_master_content_sessions", [])
    totals = report.setdefault("totals", {})
    totals["json_source_mismatch_sessions"] = len(json_sessions)
    totals["source_master_mismatch_sessions"] = len(source_sessions)

    profile = Counter()
    compact_json_sessions = []
    for session in json_sessions:
        old_missing = session.get("json_missing_in_source", [])
        old_reverse = session.get("source_missing_in_json", [])
        for item in old_missing:
            profile["json_excluded_form_empty"] += bool(
                item.get("form_empty")
            )
            profile["json_excluded_original_form_empty"] += bool(
                item.get("original_form_empty")
            )
            profile["json_excluded_original_form_nonempty"] += not bool(
                item.get("original_form_empty")
            )
        if len(compact_json_sessions) < detail_session_limit:
            compact_json_sessions.append(
                {
                    "year": session.get("year"),
                    "session_id": session.get("session_id"),
                    "json_rows": session.get("json_rows"),
                    "source_rows": session.get("source_rows"),
                    "json_missing_in_source_count": len(old_missing),
                    "source_missing_in_json_count": len(old_reverse),
                    "json_missing_in_source_examples": old_missing[
                        :examples_per_session
                    ],
                    "source_missing_in_json_examples": old_reverse[
                        :examples_per_session
                    ],
                }
            )
    totals.update(profile)
    mismatches["json_source_content_sessions"] = compact_json_sessions
    mismatches["source_master_content_sessions"] = source_sessions[
        :detail_session_limit
    ]
    report["detail_limits"] = {
        "sessions_per_mismatch_type": detail_session_limit,
        "utterance_examples_per_session": examples_per_session,
        "compacted_from_initial_full_detail": True,
    }
    report["verdicts"]["source_master_content_match"] = (
        totals.get("source_master_mismatch_sessions", 0) == 0
    )
    report["verdicts"]["json_source_content_match"] = (
        totals.get("json_missing_in_source", 0) == 0
        and totals.get("source_missing_in_json", 0) == 0
    )
    return report


def audit_all(
    source_root: Path,
    search_root: Path,
    dialogue_root: Path,
    lexicon_path: Path,
    years: list[str],
    max_sessions: int | None = None,
    detail_session_limit: int = 100,
    examples_per_session: int = 5,
) -> dict[str, object]:
    source_years = year_folders(source_root)
    report: dict[str, object] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "read_only",
        "paths": {
            "source_root": str(source_root),
            "search_root": str(search_root),
            "dialogue_root": str(dialogue_root),
            "lexicon": str(lexicon_path),
        },
        "years": {},
        "totals": Counter(),
        "mismatches": {
            "missing_master_sessions": [],
            "extra_master_sessions": [],
            "source_master_content_sessions": [],
            "json_source_content_sessions": [],
            "header_variants": Counter(),
        },
        "detail_limits": {
            "sessions_per_mismatch_type": detail_session_limit,
            "utterance_examples_per_session": examples_per_session,
        },
        "recovered_meta_sessions": {},
    }
    coverage_totals = {name: Counter() for name in COVERAGE_COLS}
    first_header: list[str] = []

    for year in years:
        if year not in source_years:
            raise ValueError(f"{year}: Bareun 연도폴더 없음")
        search_year = search_root / year
        source_map = csv_files(source_years[year])
        master_map = csv_files(search_year)
        json_map = json_files_for_year(dialogue_root, year)
        source_ids = set(source_map)
        master_ids = set(master_map)
        json_sessions = set(json_map)
        missing_master = sorted(source_ids - master_ids)
        extra_master = sorted(master_ids - source_ids)
        missing_json = sorted(source_ids - json_sessions)
        extra_json = sorted(json_sessions - source_ids)
        report["mismatches"]["missing_master_sessions"].extend(missing_master)
        report["mismatches"]["extra_master_sessions"].extend(extra_master)

        common = sorted(source_ids & master_ids & json_sessions)
        if max_sessions:
            common = common[:max_sessions]
        year_total = Counter(
            source_sessions=len(source_map),
            master_sessions=len(master_map),
            json_sessions=len(json_map),
            audited_sessions=len(common),
            missing_master_sessions=len(missing_master),
            extra_master_sessions=len(extra_master),
            missing_json_sessions=len(missing_json),
            extra_json_sessions=len(extra_json),
        )
        print(
            f"[{year}] source={len(source_map):,} master={len(master_map):,} "
            f"json={len(json_map):,} audit={len(common):,}",
            flush=True,
        )

        for index, session_id in enumerate(common, 1):
            session = audit_session(
                source_map[session_id],
                master_map[session_id],
                json_map[session_id],
            )
            if not first_header:
                first_header = list(session["header"])
            header_key = "\t".join(session["header"])
            report["mismatches"]["header_variants"][header_key] += 1
            for key in (
                "source_rows",
                "master_rows",
                "json_rows",
                "source_duplicate_ids",
                "master_duplicate_ids",
                "source_master_id_mismatch",
                "source_master_form_mismatch",
                "source_master_tagged_mismatch",
                "meta_missing_rows",
                "topic_missing_rows",
            ):
                year_total[key] += int(session[key])
            year_total["json_missing_in_source"] += len(
                session["json_missing_in_source"]
            )
            year_total["source_missing_in_json"] += len(
                session["source_missing_in_json"]
            )
            for item in session["json_missing_in_source"]:
                year_total["json_excluded_form_empty"] += bool(
                    item["form_empty"]
                )
                year_total["json_excluded_original_form_empty"] += bool(
                    item["original_form_empty"]
                )
                year_total["json_excluded_original_form_nonempty"] += not bool(
                    item["original_form_empty"]
                )
            for col in COVERAGE_COLS:
                merge_counter(coverage_totals[col], session["coverage"][col])

            if any(
                int(session[key])
                for key in (
                    "source_master_id_mismatch",
                    "source_master_form_mismatch",
                    "source_master_tagged_mismatch",
                    "source_duplicate_ids",
                    "master_duplicate_ids",
                )
            ) or session["missing_required_cols"]:
                year_total["source_master_mismatch_sessions"] += 1
                if (
                    len(
                        report["mismatches"][
                            "source_master_content_sessions"
                        ]
                    )
                    < detail_session_limit
                ):
                    report["mismatches"][
                        "source_master_content_sessions"
                    ].append(
                        {"year": year, "session_id": session_id, **session}
                    )
            if (
                session["json_missing_in_source"]
                or session["source_missing_in_json"]
            ):
                year_total["json_source_mismatch_sessions"] += 1
                if (
                    len(
                        report["mismatches"][
                            "json_source_content_sessions"
                        ]
                    )
                    < detail_session_limit
                ):
                    report["mismatches"][
                        "json_source_content_sessions"
                    ].append(
                        {
                            "year": year,
                            "session_id": session_id,
                            "json_rows": session["json_rows"],
                            "source_rows": session["source_rows"],
                            "json_missing_in_source_count": len(
                                session["json_missing_in_source"]
                            ),
                            "source_missing_in_json_count": len(
                                session["source_missing_in_json"]
                            ),
                            "json_missing_in_source_examples": session[
                                "json_missing_in_source"
                            ][:examples_per_session],
                            "source_missing_in_json_examples": session[
                                "source_missing_in_json"
                            ][:examples_per_session],
                        }
                    )
            if session_id in RECOVERED_META_SESSIONS:
                report["recovered_meta_sessions"][session_id] = {
                    "rows": session["master_rows"],
                    "meta_missing_rows": session["meta_missing_rows"],
                    "topic_missing_rows": session["topic_missing_rows"],
                    "category_values": session["category_values"],
                    "topic_values": session["topic_values"],
                }
            if index % 250 == 0 or index == len(common):
                print(
                    f"  {index:,}/{len(common):,} "
                    f"source={year_total['source_rows']:,} "
                    f"master={year_total['master_rows']:,} "
                    f"json={year_total['json_rows']:,}",
                    flush=True,
                )

        report["years"][year] = dict(year_total)
        report["totals"].update(year_total)

    report["totals"] = dict(report["totals"])
    report["coverage_values"] = {
        name: dict(sorted(counter.items()))
        for name, counter in coverage_totals.items()
    }
    report["mismatches"]["header_variants"] = {
        f"variant_{index + 1}": {"count": count, "header": key.split("\t")}
        for index, (key, count) in enumerate(
            sorted(report["mismatches"]["header_variants"].items())
        )
    }
    report["lexicon"] = audit_lexicon(lexicon_path)
    report["lexicon_wiring"] = audit_lexicon_wiring(
        PROJECT_ROOT / "scripts" / "python" / "build_search_master.py",
        PROJECT_ROOT / "scripts" / "python" / "predict_pron.py",
        first_header,
    )

    totals = report["totals"]
    report["verdicts"] = {
        "session_sets_match": not (
            report["mismatches"]["missing_master_sessions"]
            or report["mismatches"]["extra_master_sessions"]
        ),
        "source_master_rows_match": (
            totals.get("source_rows") == totals.get("master_rows")
        ),
        "source_master_content_match": not report["mismatches"][
            "source_master_content_sessions"
        ]
        and totals.get("source_master_mismatch_sessions", 0) == 0,
        "json_source_rows_match": (
            totals.get("json_rows") == totals.get("source_rows")
        ),
        "json_source_content_match": (
            totals.get("json_missing_in_source", 0) == 0
            and totals.get("source_missing_in_json", 0) == 0
        ),
        "recovered_meta_applied_to_full_master": all(
            session_id in report["recovered_meta_sessions"]
            and report["recovered_meta_sessions"][session_id][
                "meta_missing_rows"
            ]
            == 0
            for session_id in RECOVERED_META_SESSIONS
        ),
        "coverage_computed": all(
            counter
            and not set(counter).issubset({"", "미계산"})
            for counter in report["coverage_values"].values()
        ),
        "lexicon_wired_to_builder": all(
            (
                report["lexicon_wiring"]["builder_mentions_lexicon_path"],
                report["lexicon_wiring"]["builder_builds_lexicon_index"],
                report["lexicon_wiring"][
                    "builder_passes_lexicon_to_predictor"
                ],
            )
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="기존 search master 읽기 전용 전수 감사"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        default=["2020", "2021", "2022", "2023", "2024", "2025"],
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        help="테스트용: 연도별 앞 N세션만 감사(생략 시 전수)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "reports"
        / "search_master_audit_20260724.json",
    )
    parser.add_argument(
        "--detail-session-limit",
        type=int,
        default=100,
        help="불일치 유형별 상세 기록 세션 상한(합계는 항상 전수 기록)",
    )
    parser.add_argument(
        "--examples-per-session",
        type=int,
        default=5,
        help="불일치 세션별 utt_id 예시 상한",
    )
    parser.add_argument(
        "--compact-existing",
        type=Path,
        help="초기 상세 JSON을 다시 스캔하지 않고 축약해 --output에 기록",
    )
    args = parser.parse_args()
    if args.compact_existing:
        with open(args.compact_existing, encoding="utf-8") as stream:
            report = json.load(stream)
        report = compact_existing_report(
            report,
            args.detail_session_limit,
            args.examples_per_session,
        )
        atomic_write_json(args.output, report)
        print(f"축약 보고서: {args.output}", flush=True)
        return 0
    report = audit_all(
        P("layers") / "01_bareun_raw",
        P("search_master"),
        P("dialogue_json"),
        P("lexicon_full"),
        args.years,
        args.max_sessions,
        args.detail_session_limit,
        args.examples_per_session,
    )
    atomic_write_json(args.output, report)
    print(f"\n보고서: {args.output}", flush=True)
    print(
        json.dumps(report["verdicts"], ensure_ascii=False, indent=2),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

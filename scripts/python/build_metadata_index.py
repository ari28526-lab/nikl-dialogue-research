"""A4: 파일/세션 메타데이터 인덱스 — 원본 JSON에서 안전하게 재생성.

핵심 좌표는 JSON 최상위 ``id``가 아니라 배포 파일명(stem)이다. 2023 원본 4개는
최상위 id가 직전 세션으로 잘못 기록되어 기존 빌더가 메타 4세션을 덮어썼다.
원본은 수정하지 않고 불일치를 기록하며, 출력은 임시파일 검증 후 원자 교체한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    archive_copy,
    atomic_write_json,
    new_run_id,
    promote_staged,
    staged_text_writer,
)

SRC = P("dialogue_json")
OUT_DIR = P("layers") / "04_metadata_index"
GOLD_INDEX = P("layers") / "06_multilayer_gold" / "gold_index.csv"
HEADER = [
    "file_id", "doc_id", "year", "category",
    "category_norm", "discourse_mode", "topic", "date", "relation",
    "n_speakers", "speaker_ids", "in_ml2025_gold", "source_top_id",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm_category(cat: str) -> str:
    """사용역 표기 변이를 정규화하되 원문은 ``category``에 보존."""
    cat = (cat or "").strip()
    if not cat:
        return ""
    parts = [part.strip().replace(" ", "") for part in cat.split(">")]
    return " > ".join(part for part in parts if part)


def discourse_mode(cat_norm: str) -> str:
    if not cat_norm:
        return "미상"
    return "독백" if cat_norm.split(">")[-1].strip() == "독백" else "대화"


def load_gold_fids(path: Path = GOLD_INDEX) -> set[str]:
    if not path.exists():
        print("  [참고] gold_index 없음 → in_ml2025_gold 전부 False")
        return set()
    with open(path, encoding="utf-8-sig") as stream:
        return {
            row["utt_id"].split(".")[0]
            for row in csv.DictReader(stream)
            if row.get("utt_id")
        }


def json_files(source: Path) -> list[tuple[str, Path]]:
    result = []
    for year_dir in sorted(source.iterdir()):
        if not year_dir.is_dir():
            continue
        match = re.search(r"(20\d\d)", year_dir.name)
        year = match.group(1) if match else ""
        result.extend((year, path) for path in sorted(year_dir.rglob("*.json")))
    return result


def validate_metadata_csv(path: Path, expected_ids: list[str]) -> dict:
    result = {"valid": False, "reasons": [], "rows": 0}
    try:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != HEADER:
                result["reasons"].append(
                    f"header mismatch: {reader.fieldnames!r}"
                )
            ids = [row.get("file_id", "") for row in reader]
        result["rows"] = len(ids)
        if ids != expected_ids:
            result["reasons"].append("file_id order/count mismatch")
        if len(ids) != len(set(ids)):
            result["reasons"].append("duplicate file_id")
        if any(not item for item in ids):
            result["reasons"].append("empty file_id")
        result["valid"] = not result["reasons"]
    except Exception as exc:
        result["reasons"].append(f"{type(exc).__name__}: {exc}")
    return result


def build_metadata(
    source: Path,
    output: Path,
    *,
    gold_index: Path = GOLD_INDEX,
    run_id: str,
    archive_existing: bool = True,
) -> dict:
    files = json_files(source)
    if not files:
        raise RuntimeError(f"JSON 입력 0개: {source}")
    gold_fids = load_gold_fids(gold_index)
    expected_ids = [path.stem for _year, path in files]
    if len(expected_ids) != len(set(expected_ids)):
        raise RuntimeError("서로 다른 JSON 경로에 중복 파일명(stem) 존재")

    mismatches = []
    parse_errors = []
    multi_document = []
    written_ids = []
    with staged_text_writer(
        output, encoding="utf-8-sig", newline=""
    ) as (stream, temp):
        writer = csv.DictWriter(stream, fieldnames=HEADER)
        writer.writeheader()
        for index, (year, json_path) in enumerate(files, 1):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                parse_errors.append({
                    "path": str(json_path),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue

            file_id = json_path.stem
            source_top_id = str(data.get("id") or "")
            if source_top_id != file_id:
                mismatches.append({
                    "path": str(json_path),
                    "file_id": file_id,
                    "source_top_id": source_top_id,
                })
            documents = data.get("document") or []
            if len(documents) != 1:
                multi_document.append({
                    "path": str(json_path), "documents": len(documents),
                })
                continue
            doc = documents[0]
            doc_id = str(doc.get("id") or "")
            # 문서·발화 좌표가 파일 stem과 다르면 조인 안전성을 보장할 수 없다.
            utterances = doc.get("utterance") or []
            bad_utt = next(
                (str(item.get("id") or "") for item in utterances
                 if not str(item.get("id") or "").startswith(file_id + ".")),
                None,
            )
            if not doc_id.startswith(file_id + ".") or bad_utt is not None:
                parse_errors.append({
                    "path": str(json_path),
                    "error": (
                        f"내부 ID 불일치: doc_id={doc_id!r} "
                        f"first_bad_utt={bad_utt!r}"
                    ),
                })
                continue

            top_meta = data.get("metadata") or {}
            doc_meta = doc.get("metadata") or {}
            category = str(top_meta.get("category") or "").strip()
            category_norm = norm_category(category)
            speakers = doc_meta.get("speaker") or []
            setting = doc_meta.get("setting") or {}
            writer.writerow({
                "file_id": file_id,
                "source_top_id": source_top_id,
                "doc_id": doc_id,
                "year": year,
                "category": category,
                "category_norm": category_norm,
                "discourse_mode": discourse_mode(category_norm),
                "topic": str(doc_meta.get("topic") or "").strip(),
                "date": str(doc_meta.get("date") or "").strip(),
                "relation": str(setting.get("relation") or "").strip(),
                "n_speakers": len(speakers),
                "speaker_ids": "|".join(
                    str(speaker.get("id") or "") for speaker in speakers
                ),
                "in_ml2025_gold": "True" if file_id in gold_fids else "False",
            })
            written_ids.append(file_id)
            if index % 1000 == 0:
                print(f"  {index:,}/{len(files):,} JSON", flush=True)

    blockers = []
    if parse_errors:
        blockers.append(f"parse/internal-id errors={len(parse_errors)}")
    if multi_document:
        blockers.append(f"document count != 1: {len(multi_document)}")
    validation = validate_metadata_csv(temp, expected_ids)
    if not validation["valid"]:
        blockers.extend(validation["reasons"])
    report = {
        "run_id": run_id,
        "source": str(source),
        "output": str(output),
        "input_json": len(files),
        "written_rows": len(written_ids),
        "top_id_mismatches": mismatches,
        "parse_errors": parse_errors,
        "multi_document": multi_document,
        "validation": validation,
        "status": "failed" if blockers else "success",
        "blockers": blockers,
    }
    report_path = output.parent / "_runs" / f"metadata_{run_id}.json"
    atomic_write_json(report_path, report)
    if blockers:
        raise RuntimeError(
            f"메타데이터 검증 실패({temp} 보존): " + "; ".join(blockers)
        )

    archived = None
    if output.exists() and archive_existing:
        archived = archive_copy(
            output,
            output.parent / "_archive" / run_id,
            Path(output.name),
        )
    promote_staged(temp, output)
    report["archive"] = str(archived) if archived else None
    report["status"] = "success"
    atomic_write_json(report_path, report)
    print(f"완료: JSON {len(files):,}개 → 메타 {len(written_ids):,}행")
    print(f"최상위 id 불일치: {len(mismatches)}건(원본 보존, file stem 사용)")
    print(f"출력: {output}\n보고서: {report_path}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=SRC)
    ap.add_argument("--output", type=Path,
                    default=OUT_DIR / "file_meta.csv")
    ap.add_argument("--run-id")
    ap.add_argument("--no-archive", action="store_true",
                    help="격리 파일럿 출력에만 사용. 기존 파일이 있으면 보존하지 않음")
    args = ap.parse_args()
    run_id = args.run_id or new_run_id("metadata")
    build_metadata(
        args.source.resolve(),
        args.output.resolve(),
        run_id=run_id,
        archive_existing=not args.no_archive,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

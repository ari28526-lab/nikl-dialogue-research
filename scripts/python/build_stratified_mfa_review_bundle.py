"""층화 MFA 파일럿을 연구자 수동 점검용 연도별 묶음으로 재구성한다.

원본 run은 읽기만 한다. 출력은 연도별 평면 폴더에 같은 basename의
WAV, lab, enriched TextGrid, 발화별 CSV를 나란히 둔다.

enriched TextGrid:
  words / phones / morphemes   원 4-tier의 시간·라벨 보존
  original_form                원본 JSON 전사(가능하면 어절 구간 정렬)
  pron_reference              숫자·기호 손실 시 original_form으로 보완한 기준 발음
  utterance                   정규화 form, 정렬 어절의 시작–끝 범위

pron_reference는 후보 검색·점검용 기준선이며 사전 등재 발음이나 실제 음향
실현 판정이 아니다. 대화 참여자도 직접 수신자가 아니라 같은 document의
공동 참여자다. 출처와 정렬 상태는 발화별 CSV와 INDEX.csv에 기록한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from merge_textgrid_v2 import interval_tier  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    git_commit,
    now_iso,
    sha256_file,
)
from predict_pron import predict_pron_reference  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402
from build_search_master import build_json_index, load_utt_extra  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
SILENCE = {"", "sil", "sp", "spn", "<eps>", "<unk>"}
REVIEW_TIERS = [
    "words",
    "phones",
    "morphemes",
    "original_form",
    "pron_reference",
    "utterance",
]
INDEX_FIELDS = [
    "year",
    "speaker_id",
    "session_id",
    "dialogue_id",
    "dialogue_speaker_ids",
    "n_dialogue_speakers",
    "co_speaker_ids",
    "n_co_speakers",
    "utt_id",
    "form",
    "original_form",
    "pron_pred_hangul_existing",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_source",
    "pron_reference_status",
    "original_form_align_status",
    "pron_reference_align_status",
    "tier_warning",
    "wav_relpath",
    "lab_relpath",
    "textgrid_relpath",
    "csv_relpath",
    "review_status",
    "review_note",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"필수 CSV 없음: {path}")
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(
    path: Path, rows: list[dict[str, object]], fieldnames: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def esc(text: object) -> str:
    return str(text).replace('"', '""')


def labeled_word_span(
    words: list[tuple[float, float, str]], duration: float
) -> tuple[float, float, int, int]:
    indices = [
        index
        for index, (_, _, label) in enumerate(words)
        if str(label).strip().lower() not in SILENCE
    ]
    if not indices:
        return 0.0, duration, 0, max(0, len(words) - 1)
    first, last = indices[0], indices[-1]
    return float(words[first][0]), float(words[last][1]), first, last


def split_at(
    intervals: list[tuple[float, float, str]], cuts: tuple[float, float]
) -> list[tuple[float, float, str]]:
    """근거 있는 어절 span 경계를 tier에 추가하되 기존 라벨은 바꾸지 않는다."""
    result: list[tuple[float, float, str]] = []
    for begin, end, label in intervals:
        points = [float(begin)]
        points.extend(cut for cut in cuts if begin + 1e-6 < cut < end - 1e-6)
        points.append(float(end))
        for left, right in zip(points, points[1:]):
            result.append((left, right, label))
    return result


def align_text_to_words(
    name: str,
    value: str,
    words: list[tuple[float, float, str]],
    duration: float,
) -> tuple[list[str], str, str]:
    """TextGrid tier lines, 정렬 상태, 경고를 반환한다.

    내부의 빈 words interval은 숫자·기호가 MFA에서 누락된 lexical slot일 수
    있으므로 먼저 첫–마지막 유표 어절 사이의 모든 slot과 토큰 수를 비교한다.
    """
    speech_start, speech_end, first, last = labeled_word_span(words, duration)
    tokens = (value or "").split()
    all_slots = list(range(first, last + 1))
    labeled_slots = [
        index
        for index in all_slots
        if str(words[index][2]).strip().lower() not in SILENCE
    ]
    assignments: dict[int, str] = {}
    if tokens and len(tokens) == len(all_slots):
        assignments = dict(zip(all_slots, tokens))
        status = "all_lexical_slots"
        warning = ""
    elif tokens and len(tokens) == len(labeled_slots):
        assignments = dict(zip(labeled_slots, tokens))
        status = "labeled_word_slots"
        warning = ""
    else:
        status = "utterance_fallback"
        warning = (
            f"{name}: tokens={len(tokens)}, lexical_slots={len(all_slots)}, "
            f"labeled_slots={len(labeled_slots)}"
        )
        label = f"[align≠] {value}".strip()
        return (
            interval_tier(name, [(speech_start, speech_end, label)], duration),
            status,
            warning,
        )
    intervals = [
        (float(begin), float(end), assignments.get(index, ""))
        for index, (begin, end, _label) in enumerate(words)
    ]
    return interval_tier(name, intervals, duration), status, warning


def write_review_textgrid(
    source: Path,
    destination: Path,
    *,
    form: str,
    original_form: str,
    pron_reference: str,
) -> tuple[str, str, str]:
    duration, tiers = parse_mfa_textgrid(source)
    if duration is None or duration <= 0:
        raise RuntimeError(f"TextGrid duration 누락: {source}")
    words = tiers.get("words", [])
    phones = tiers.get("phones", [])
    morphemes = tiers.get("morphemes", [])
    if not words or not phones or not morphemes:
        raise RuntimeError(f"기존 4-tier 핵심 tier 누락: {source}")
    speech_start, speech_end, _, _ = labeled_word_span(words, float(duration))
    cuts = (speech_start, speech_end)

    original_lines, original_status, original_warn = align_text_to_words(
        "original_form", original_form or form, words, float(duration)
    )
    pron_lines, pron_status, pron_warn = align_text_to_words(
        "pron_reference", pron_reference, words, float(duration)
    )
    ordered = [
        interval_tier("words", split_at(words, cuts), float(duration)),
        interval_tier("phones", split_at(phones, cuts), float(duration)),
        interval_tier("morphemes", split_at(morphemes, cuts), float(duration)),
        original_lines,
        pron_lines,
        interval_tier(
            "utterance",
            [(speech_start, speech_end, form)],
            float(duration),
        ),
    ]
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {float(duration):.6f}",
        "tiers? <exists>",
        f"size = {len(ordered)}",
        "item []:",
    ]
    for index, tier in enumerate(ordered, 1):
        lines.append(f"    item [{index}]:")
        lines.extend(tier)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")

    check_duration, check_tiers = parse_mfa_textgrid(destination)
    names = list(check_tiers)
    if names != REVIEW_TIERS:
        raise RuntimeError(f"review tier 순서 불일치: {names}")
    if check_duration is None or abs(check_duration - float(duration)) > 0.001:
        raise RuntimeError("review TextGrid duration 불일치")
    for tier_name, intervals in check_tiers.items():
        if not intervals:
            raise RuntimeError(f"review tier 비어 있음: {tier_name}")
        if abs(intervals[0][0]) > 1e-6:
            raise RuntimeError(f"review tier 시작 coverage 누락: {tier_name}")
        if abs(intervals[-1][1] - float(duration)) > 1e-6:
            raise RuntimeError(f"review tier 끝 coverage 누락: {tier_name}")
        for left, right in zip(intervals, intervals[1:]):
            if abs(left[1] - right[0]) > 1e-6:
                raise RuntimeError(f"review tier 비연속: {tier_name}")
    warnings = "; ".join(item for item in (original_warn, pron_warn) if item)
    return original_status, pron_status, warnings


def add_prefixed(
    destination: dict[str, object],
    source: dict[str, str],
    prefix: str,
    *,
    skip: set[str] | None = None,
) -> None:
    skip = skip or set()
    for key, value in source.items():
        if key not in skip:
            destination[f"{prefix}{key}"] = value


def load_maps(
    run_root: Path,
) -> tuple[
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str], dict[str, str]],
]:
    search: dict[tuple[str, str], dict[str, str]] = {}
    bareun: dict[tuple[str, str], dict[str, str]] = {}
    speakers: dict[tuple[str, str], dict[str, str]] = {}
    qc: dict[tuple[str, str], dict[str, str]] = {}
    for year in YEARS:
        csv_root = run_root / "csv" / year
        for row in read_csv(csv_root / "search_master_selected.csv"):
            search[(year, row["utt_id"])] = row
        for row in read_csv(csv_root / "bareun_selected.csv"):
            bareun[(year, row["utt_id"])] = row
        for row in read_csv(csv_root / "speaker_metadata_selected.csv"):
            speaker_key = row.get("speaker_id") or row.get("id")
            if not speaker_key:
                raise ValueError(
                    f"{year} speaker_metadata_selected.csv에 id 키 없음"
                )
            speakers[(year, speaker_key)] = row
        for row in read_csv(run_root / "qc" / f"{year}_utterance_qc.csv"):
            qc[(year, row["utt_id"])] = row
    return search, bareun, speakers, qc


def load_dialogue_context(
    manifest: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, object]]:
    """선정 발화의 document 참가자 문맥을 원본 JSON에서 읽는다."""
    contexts: dict[tuple[str, str], dict[str, object]] = {}
    sessions_by_year: dict[str, set[str]] = {}
    for row in manifest:
        sessions_by_year.setdefault(row["year"], set()).add(row["session_id"])
    for year, sessions in sessions_by_year.items():
        json_index = build_json_index(year)
        for session in sorted(sessions):
            json_path = json_index.get(session)
            if json_path is None:
                raise FileNotFoundError(f"대화 원본 JSON 없음: {year}/{session}")
            for utt_id, context in load_utt_extra(json_path).items():
                contexts[(year, utt_id)] = context
    return contexts


def safe_output_paths(run_root: Path, output_root: Path) -> None:
    run_root = run_root.resolve()
    output_root = output_root.resolve()
    if output_root == run_root or output_root in run_root.parents:
        raise ValueError("출력은 원본 run 또는 그 상위 폴더일 수 없음")
    if output_root.parent == output_root:
        raise ValueError("드라이브 루트에는 출력할 수 없음")
    if len(output_root.parts) < 4:
        raise ValueError(f"출력 경로가 지나치게 넓음: {output_root}")


def tree_hashes(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    exclude = exclude or set()
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and str(path.relative_to(root)) not in exclude
    }


def promote_staged_directory(
    staging: Path,
    output_root: Path,
    *,
    force_copy_fallback: bool = False,
) -> str:
    """staging 디렉터리를 승격한다.

    Dropbox가 Windows 디렉터리 rename을 일시 차단하면 최종 폴더에
    ``.INCOMPLETE``를 먼저 만들고 전 파일을 복사·SHA256 대조한다. 검증 전에는
    완료 표지를 제거하지 않으며, staging은 검증 성공 뒤에만 정리한다.
    """
    if output_root.exists():
        raise FileExistsError(f"승격 대상이 이미 존재함: {output_root}")
    if not force_copy_fallback:
        try:
            staging.replace(output_root)
            return "atomic_directory_rename"
        except PermissionError:
            pass

    output_root.mkdir(parents=False)
    incomplete = output_root / ".INCOMPLETE"
    incomplete.write_text(
        "Dropbox copy fallback 진행 중 — 이 파일이 있으면 미완료\n",
        encoding="utf-8",
    )
    try:
        for item in staging.iterdir():
            destination = output_root / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        source_hashes = tree_hashes(staging)
        copied_hashes = tree_hashes(
            output_root, exclude={".INCOMPLETE"}
        )
        if source_hashes != copied_hashes:
            raise RuntimeError(
                "Dropbox fallback 전 파일 SHA256 대조 실패; "
                ".INCOMPLETE를 보존하고 중단"
            )
        incomplete.unlink()
        try:
            shutil.rmtree(staging)
            return "verified_copy_fallback"
        except PermissionError:
            # Dropbox가 동기화 중인 staging 디렉터리 handle을 잡고 있을 수
            # 있다. 전 파일 검증과 완료 표지 제거가 끝났으므로 최종 산출은
            # 유효하며, 빈/중복 staging 정리만 후속 비치명 작업으로 남긴다.
            return "verified_copy_fallback_staging_retained"
    except BaseException:
        # 부분 출력과 .INCOMPLETE를 보존해 완료본으로 오인하지 않게 한다.
        raise


def collapse_adjacent(
    intervals: list[tuple[float, float, str]],
) -> list[tuple[float, float, str]]:
    """경계만 추가해 같은 라벨이 연속된 구간을 원 비교용으로 합친다."""
    collapsed: list[tuple[float, float, str]] = []
    for begin, end, label in intervals:
        if (
            collapsed
            and collapsed[-1][2] == label
            and abs(collapsed[-1][1] - begin) <= 1e-6
        ):
            collapsed[-1] = (collapsed[-1][0], end, label)
        else:
            collapsed.append((begin, end, label))
    return collapsed


def verify_existing_bundle(
    run_root: Path, output_root: Path, project_root: Path
) -> dict:
    """기존 점검 bundle을 D: 원 run과 다시 대조하고 보고서를 갱신한다."""
    safe_output_paths(run_root, output_root)
    if not output_root.is_dir():
        raise FileNotFoundError(f"기존 bundle 없음: {output_root}")
    if (output_root / ".INCOMPLETE").exists():
        raise RuntimeError("기존 bundle에 .INCOMPLETE가 있어 완료 검증 불가")
    manifest = read_csv(run_root / "selection_manifest.csv")
    index_rows = read_csv(output_root / "INDEX_ALL.csv")
    if len(manifest) != 60 or len(index_rows) != 60:
        raise RuntimeError(
            f"60발화 수량 불일치: manifest={len(manifest)}, "
            f"index={len(index_rows)}"
        )
    index_ids = {row["utt_id"] for row in index_rows}
    if index_ids != {row["utt_id"] for row in manifest}:
        raise RuntimeError("manifest–INDEX utt_id 집합 불일치")

    for item in manifest:
        year = item["year"]
        utt_id = item["utt_id"]
        speaker_id = item["speaker_id"]
        source_wav = run_root / item["corpus_wav_relpath"]
        source_lab = run_root / item["corpus_lab_relpath"]
        review_wav = output_root / year / f"{utt_id}.wav"
        review_lab = output_root / year / f"{utt_id}.lab"
        review_tg = output_root / year / f"{utt_id}.TextGrid"
        review_csv = output_root / year / f"{utt_id}.csv"
        for source, copied in (
            (source_wav, review_wav),
            (source_lab, review_lab),
        ):
            if not copied.is_file() or sha256_file(source) != sha256_file(copied):
                raise RuntimeError(f"복사 해시 불일치: {copied}")
        source_tg = (
            run_root
            / "textgrid_4tier"
            / year
            / speaker_id
            / f"{utt_id}.TextGrid"
        )
        _, source_tiers = parse_mfa_textgrid(source_tg)
        _, review_tiers = parse_mfa_textgrid(review_tg)
        if list(review_tiers) != REVIEW_TIERS:
            raise RuntimeError(f"review tier 불일치: {review_tg}")
        for tier_name in ("words", "phones", "morphemes"):
            if collapse_adjacent(source_tiers[tier_name]) != collapse_adjacent(
                review_tiers[tier_name]
            ):
                raise RuntimeError(
                    f"원 tier 의미 변경 감지: {utt_id}/{tier_name}"
                )
        detail = read_csv(review_csv)
        if len(detail) != 1 or detail[0].get("utt_id") != utt_id:
            raise RuntimeError(f"발화별 CSV 불일치: {review_csv}")

    report_path = output_root / "BUILD_REPORT.json"
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    expected_files = int(report.get("files_expected") or 0)
    actual_files = sum(1 for path in output_root.rglob("*") if path.is_file())
    if actual_files != expected_files:
        raise RuntimeError(
            f"bundle 파일 수 불일치: {actual_files}/{expected_files}"
        )
    report.update({
        "verified_at": now_iso(),
        "verified_git_commit": git_commit(project_root),
        "promotion_mode": report.get("promotion_mode")
        or "verified_copy_fallback_staging_retained",
        "verification": {
            "utterances": len(manifest),
            "wav_lab_sha256_match": len(manifest) * 2,
            "source_tier_semantic_match": len(manifest) * 3,
            "per_utterance_csv_match": len(manifest),
            "files": actual_files,
        },
        "status": "passed",
    })
    atomic_write_json(report_path, report)
    return report


def build_bundle(run_root: Path, output_root: Path, project_root: Path) -> dict:
    safe_output_paths(run_root, output_root)
    if output_root.exists():
        raise FileExistsError(
            f"출력 폴더가 이미 있음(자동 덮어쓰기 금지): {output_root}"
        )
    summary_path = run_root / "pilot_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    if summary.get("status") != "passed":
        raise RuntimeError("PASSED 파일럿만 점검 번들로 만들 수 있음")
    manifest = read_csv(run_root / "selection_manifest.csv")
    if len(manifest) != 60:
        raise RuntimeError(f"manifest 60행 아님: {len(manifest)}")
    search, bareun, speakers, qc = load_maps(run_root)
    dialogue_context = load_dialogue_context(manifest)

    staging = output_root.with_name(
        f".{output_root.name}.staging_{os.getpid()}"
    )
    if staging.exists():
        raise FileExistsError(f"이전 staging 존재: {staging}")
    staging.mkdir(parents=True)
    index_rows: list[dict[str, object]] = []
    detail_fieldnames: list[str] | None = None
    try:
        for item in manifest:
            year = item["year"]
            utt_id = item["utt_id"]
            speaker_id = item["speaker_id"]
            session_id = item["session_id"]
            key = (year, utt_id)
            search_row = search.get(key)
            bareun_row = bareun.get(key)
            qc_row = qc.get(key)
            speaker_row = speakers.get((year, speaker_id))
            context = dialogue_context.get(key)
            if not all((search_row, bareun_row, qc_row, speaker_row, context)):
                raise RuntimeError(f"CSV 조인 누락: {year}/{utt_id}")

            source_wav = run_root / item["corpus_wav_relpath"]
            source_lab = run_root / item["corpus_lab_relpath"]
            source_tg = (
                run_root
                / "textgrid_4tier"
                / year
                / speaker_id
                / f"{utt_id}.TextGrid"
            )
            for source in (source_wav, source_lab, source_tg):
                if not source.is_file():
                    raise FileNotFoundError(f"점검 원본 누락: {source}")

            year_root = staging / year
            year_root.mkdir(parents=True, exist_ok=True)
            dest_wav = year_root / f"{utt_id}.wav"
            dest_lab = year_root / f"{utt_id}.lab"
            dest_tg = year_root / f"{utt_id}.TextGrid"
            dest_csv = year_root / f"{utt_id}.csv"
            shutil.copy2(source_wav, dest_wav)
            shutil.copy2(source_lab, dest_lab)

            form = search_row.get("form") or bareun_row.get("form", "")
            original_form = search_row.get("original_form", "").strip()
            pron = predict_pron_reference(
                form,
                original_form,
                tagged=search_row.get("tagged", ""),
            )
            pron_reference = pron["reference"]["pron_pred_hangul"]
            pron_source = pron["reference_source"]
            original_status, pron_status, tier_warning = write_review_textgrid(
                source_tg,
                dest_tg,
                form=form,
                original_form=original_form,
                pron_reference=pron_reference,
            )

            rel_base = Path(year)
            index_row: dict[str, object] = {
                "year": year,
                "speaker_id": speaker_id,
                "session_id": session_id,
                "dialogue_id": context["dialogue_id"],
                "dialogue_speaker_ids": context["dialogue_speaker_ids"],
                "n_dialogue_speakers": context["n_dialogue_speakers"],
                "co_speaker_ids": context["co_speaker_ids"],
                "n_co_speakers": context["n_co_speakers"],
                "utt_id": utt_id,
                "form": form,
                "original_form": original_form,
                "pron_pred_hangul_existing": search_row.get(
                    "pron_pred_hangul", ""
                ),
                "pron_reference_form": pron["reference_form"],
                "pron_reference_hangul": pron_reference,
                "pron_reference_source": pron_source,
                "pron_reference_status": pron["reference_status"],
                "original_form_align_status": original_status,
                "pron_reference_align_status": pron_status,
                "tier_warning": tier_warning,
                "wav_relpath": str(rel_base / dest_wav.name),
                "lab_relpath": str(rel_base / dest_lab.name),
                "textgrid_relpath": str(rel_base / dest_tg.name),
                "csv_relpath": str(rel_base / dest_csv.name),
                "review_status": "",
                "review_note": "",
            }
            index_rows.append(index_row)

            detail: dict[str, object] = dict(index_row)
            add_prefixed(
                detail,
                search_row,
                "search_",
                skip={"utt_id", "year", "speaker_id", "session_id"},
            )
            add_prefixed(
                detail,
                bareun_row,
                "bareun_",
                skip={"utt_id", "speaker_id"},
            )
            add_prefixed(
                detail,
                speaker_row,
                "speaker_",
                skip={"speaker_id", "id"},
            )
            add_prefixed(
                detail,
                qc_row,
                "qc_",
                skip={"utt_id", "year", "speaker_id", "session_id"},
            )
            add_prefixed(
                detail,
                item,
                "pilot_",
                skip={"utt_id", "year", "speaker_id", "session_id"},
            )
            if detail_fieldnames is None:
                detail_fieldnames = list(detail)
            elif set(detail) != set(detail_fieldnames):
                raise RuntimeError(f"발화별 CSV 스키마 불일치: {utt_id}")
            write_csv(dest_csv, [detail], detail_fieldnames)

        for year in YEARS:
            year_rows = [row for row in index_rows if row["year"] == year]
            if len(year_rows) != 10:
                raise RuntimeError(f"{year} 점검 발화 10개 아님: {len(year_rows)}")
            write_csv(staging / year / "INDEX.csv", year_rows, INDEX_FIELDS)
        write_csv(staging / "INDEX_ALL.csv", index_rows, INDEX_FIELDS)

        readme = """# 층화 MFA 파일럿 수동 점검 묶음

각 연도 폴더에는 같은 발화 ID의 WAV, lab, TextGrid, CSV가 나란히 있다.

TextGrid tier:

1. `words`: MFA 어절 정렬
2. `phones`: MFA/G2P 대략적 음소 분절
3. `morphemes`: 기존 형태소 경계
4. `original_form`: 원본 JSON 전사
5. `pron_reference`: 숫자·기호 손실 시 원전사로 보완한 기준 발음 힌트
6. `utterance`: 정규화 form

`pron_reference`는 사전 등재 발음이나 실제 음향 실현 판정이 아니다. 후보 검색과
수동 점검을 돕는 기준선이며, 정확한 출처는 발화 CSV의
`pron_reference_source`에서 확인한다. 기존 search master의
`pron_pred_hangul`도 별도 열로 보존되어 있다.

발화 CSV의 `dialogue_speaker_ids`는 같은 원본 JSON document에 등장하는 전체
화자, `co_speaker_ids`는 현재 `speaker_id`를 제외한 공동 참여자다. 말뭉치에는
직접 수신자 표지가 없으므로 `co_speaker_ids`를 특정 발화의 수신자로 해석하지
않는다.

모든 tier는 TextGrid 전체 시간 0–xmax를 구조적으로 덮는다. `utterance`와 추가
tier는 첫–마지막 정렬 어절 범위 밖을 빈 interval로 두어 앞뒤 padding 경계를
보이게 한다. 원 `words/phones/morphemes` 라벨과 시간은 변경하지 않는다.
"""
        (staging / "README.md").write_text(readme, encoding="utf-8")
        report = {
            "schema_version": 1,
            "created_at": now_iso(),
            "source_run": str(run_root),
            "output_root": str(output_root),
            "git_commit": git_commit(project_root),
            "utterances": len(index_rows),
            "years": {
                year: sum(row["year"] == year for row in index_rows)
                for year in YEARS
            },
            "dialogue_speaker_count_distribution": {
                str(count): sum(
                    int(row["n_dialogue_speakers"]) == count
                    for row in index_rows
                )
                for count in sorted({
                    int(row["n_dialogue_speakers"]) for row in index_rows
                })
            },
            "files_expected": len(index_rows) * 4 + len(YEARS) + 3,
            "review_tiers": REVIEW_TIERS,
            "pronunciation_warning": (
                "pron_reference is a rule-based reference, not dictionary "
                "pronunciation or observed realization"
            ),
            "status": "passed",
        }
        atomic_write_json(staging / "BUILD_REPORT.json", report)
        promotion_mode = promote_staged_directory(staging, output_root)
        report["promotion_mode"] = promotion_mode
        atomic_write_json(output_root / "BUILD_REPORT.json", report)
        return report
    except BaseException:
        print(f"실패 staging 보존: {staging}", file=sys.stderr)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="기존 output을 D: run과 전수 대조하고 BUILD_REPORT를 갱신",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verify_existing:
        report = verify_existing_bundle(
            args.run_root.resolve(),
            args.output_root.resolve(),
            args.project_root.resolve(),
        )
        print(
            f"기존 점검 묶음 검증 완료: {report['utterances']}발화 / "
            f"{report['output_root']}"
        )
    else:
        report = build_bundle(
            args.run_root.resolve(),
            args.output_root.resolve(),
            args.project_root.resolve(),
        )
        print(
            f"점검 묶음 완료: {report['utterances']}발화 / "
            f"{report['output_root']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

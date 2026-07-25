# -*- coding: utf-8 -*-
"""build_search_master.py - 검색 마스터 v1 (05_search_master) 세션별 CSV 생성.

입력: 01_bareun_raw(형태소) + 04_metadata_index(file_meta·speakers_normalized)
      + 00_RAW/dialogue_json(original_form·start·end·note) + predict_pron
출력: D:/10_LAYERS/05_search_master/{연도}/{세션}.csv (utf-8-sig, 발화 1행)

설계: docs/decisions/DESIGN_search_master_layer.md
검증(내장): 행수=발화수 / 문자열 컬럼 어절수=n_eojeol / form-tagged same-length
가드(불일치는 align_warn, tagged 기반 컬럼만 '_') / 조인 결측은 '미상'.

파일럿:  python build_search_master.py --year 2020 --pilot 3
전량:    python build_search_master.py            (연도별·세션별 체크포인트 재개)
옵션:  --overwrite(기존 CSV 재생성)  --tagged-roman(형태소경계 roman 컬럼)
       --coverage(has_wav 등 채움; 기본 off — 파일럿은 텍스트/발음 층에 집중)
"""
import argparse
import csv
import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P
import predict_pron as pp
from pipeline_common import (
    archive_copy,
    atomic_write_json,
    file_fingerprint,
    new_run_id,
    promote_staged,
    runtime_snapshot,
    staged_text_writer,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(10_000_000)

MISSING = "미상"
NOT_COMPUTED = "미계산"
EOJEOL_SEP = " | "
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_BAREUN_COLS = {"utt_id", "speaker_id", "form", "tagged", "n_morphs"}

# 투명성: 산출과 함께 _build_meta.json에 "무슨 도구·자료·규칙으로 만들었나" 기록.
BUILD_PROVENANCE = {
    "layer": "05_search_master v1 (예측 발음열)",
    "표기_규약": "음소=공백 · 음절='_' · 형태소='+' · 어절='|' · 자리표시='∅' · 초성 대문자·종성 소문자",
    "입력_레이어": {
        "형태소분석(form/tagged)": {
            "source": "D:/10_LAYERS/01_bareun_raw",
            "tool": "바른(Bareun), 바이칼AI 클라우드 API",
            "client": "bareunpy 2.0.1 / Python 3.13",
            "run": "2026-07-09~10 (2020-2025 6개년 단일 실행, 동일 서버 모델)",
            "engine_version": "미고정 — 논문용 버전 문자열 확인 요망(METHODS §2 TODO)",
            "coverage": "17,156 파일, form 비어 있지 않은 분석대상 5,103,356 발화, 빈 분석 0",
            "validation": "형태소 F1 0.929 (2024/다층위 2025 gold 대조)",
        },
        "문서메타": "D:/10_LAYERS/04_metadata_index/file_meta.csv (category_norm·discourse_mode·topic·relation·date·in_ml2025_gold)",
        "화자메타": "D:/10_LAYERS/04_metadata_index/speakers_normalized.csv (_norm 컬럼)",
        "원전사·시간·비고": "D:/00_RAW/dialogue_json (original_form·start·end·note)",
        "대화참여자": "원본 JSON document별 utterance.speaker_id 집합 (직접 수신자 아님)",
        "IPA표": "D:/10_LAYERS/03_freq_dictionaries/_roman_mfa_to_ipa.csv (빈도사전 공유)",
    },
    "예측발음_규칙": {
        "적용순서": "격음화→ㅎ탈락→구개음화→연음→중화→겹받침단순화→비음/유음→경음화(+용언 어간+어미 경음화)",
        "미적용(수의)": "ㄹ비음화·ㄴ삽입·합성어경음화·위치동화 등",
        "테스트": "predict_pron.py --selftest 30/30 통과",
        "숫자·기호": "form 결과가 ∅일 때 original_form이 placeholder를 줄이는 경우만 reference에 채택; 그 외 unresolved_symbol",
    },
}

# 출력 컬럼(설계 §2 순서). tagged_roman은 --tagged-roman 시 form_roman 뒤 삽입.
BASE_COLS = [
    "utt_id", "year", "session_id", "utt_seq",
    "dialogue_id", "dialogue_speaker_ids", "n_dialogue_speakers",
    "co_speaker_ids", "n_co_speakers",
    "has_wav", "has_tg_eojeol", "quarantined",
    "category_norm", "discourse_mode", "topic", "relation", "date",
    "in_ml2025_gold",
    "speaker_id", "sex", "age_norm", "occupation_norm", "education_ord",
    "birthplace_norm", "current_residence_norm",
    "form", "tagged", "n_morphs", "n_eojeol",
    "original_form", "start", "end", "dur", "note",
    "form_roman", "pron_pred_hangul", "pron_pred_roman", "pron_pred_ipa",
    "pron_reference_form", "pron_reference_form_roman",
    "pron_reference_hangul", "pron_reference_roman", "pron_reference_ipa",
    "pron_reference_source", "pron_reference_status",
    "pron_reference_n_eojeol",
    "align_warn",
]
META_COLS = ["category_norm", "discourse_mode", "topic", "relation", "date",
             "in_ml2025_gold"]
SPK_MAP = {"sex": "sex_norm", "age_norm": "age_norm",
           "occupation_norm": "occupation_norm", "education_ord": "education_ord",
           "birthplace_norm": "birthplace_norm",
           "current_residence_norm": "current_residence_norm"}


def load_file_meta():
    path = P("layers") / "04_metadata_index" / "file_meta.csv"
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            file_id = r["file_id"]
            if not file_id:
                raise ValueError(f"{path}: 빈 file_id")
            if file_id in out:
                raise ValueError(f"{path}: 중복 file_id {file_id}")
            out[file_id] = r
    return out


def load_speakers():
    path = P("layers") / "04_metadata_index" / "speakers_normalized.csv"
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[(str(r["year"]), r["id"])] = r
    return out

def find_json_year_dir(year):
    """dialogue_json 아래에서 해당 연도의 폴더를 찾는다(이름에 연도 포함)."""
    root = P("dialogue_json")
    for d in sorted(root.iterdir()):
        if d.is_dir() and year in d.name:
            return d
    return None


def build_json_index(year):
    """{세션ID(stem): json경로} — 연도 폴더를 1회 walk(전량 실행도 효율적)."""
    ydir = find_json_year_dir(year)
    idx = {}
    if ydir is None:
        return idx
    for p in ydir.rglob("*.json"):
        idx[p.stem] = p
    return idx


def load_utt_extra(json_path):
    """세션 JSON -> 발화별 원전사·시간·document 공동 참여자 문맥."""
    extra = {}
    with open(json_path, encoding="utf-8") as f:
        doc = json.load(f)
    for d in doc.get("document", []):
        utterances = d.get("utterance", [])
        dialogue_id = d.get("id", "")
        participants = sorted({
            str(u.get("speaker_id", "")).strip()
            for u in utterances
            if str(u.get("speaker_id", "")).strip()
        })
        for u in utterances:
            utt_id = u.get("id", "")
            if not utt_id:
                continue
            if utt_id in extra:
                raise ValueError(f"{json_path}: 중복 발화 ID {utt_id}")
            current = str(u.get("speaker_id", "")).strip()
            co_speakers = [speaker for speaker in participants if speaker != current]
            extra[utt_id] = {
                "original_form": u.get("original_form", ""),
                "start": u.get("start", ""),
                "end": u.get("end", ""),
                "note": u.get("note", ""),
                "dialogue_id": dialogue_id,
                "dialogue_speaker_ids": " | ".join(participants),
                "n_dialogue_speakers": len(participants),
                "co_speaker_ids": " | ".join(co_speakers),
                "n_co_speakers": len(co_speakers),
            }
    return extra


def derive_ids(utt_id, year):
    """utt_id(SDRW2000000001.1.1.3) -> (session_id, utt_seq)."""
    parts = utt_id.split(".")
    session_id = parts[0]
    utt_seq = parts[-1] if len(parts) > 1 else ""
    return session_id, utt_seq

def build_row(u, year, meta, spk, extra, ipa_map, opts, stats):
    """바른 발화 1행 dict -> 마스터 행 dict + 검증 갱신."""
    utt_id = u["utt_id"]
    session_id, utt_seq = derive_ids(utt_id, year)
    form = u.get("form", "") or ""
    tagged = u.get("tagged", "") or ""
    n_eojeol = len(form.split())

    row = {c: "" for c in BASE_COLS}
    row.update(utt_id=utt_id, year=year, session_id=session_id,
               utt_seq=utt_seq, form=form, tagged=tagged,
               n_morphs=u.get("n_morphs", ""), n_eojeol=n_eojeol)
    # v1에서는 대용량 파일 존재 검사를 하지 않는다. 빈 문자열은 실제 결측처럼
    # 해석될 수 있으므로 계산하지 않았음을 명시한다.
    for col in ("has_wav", "has_tg_eojeol", "quarantined"):
        row[col] = NOT_COMPUTED

    # 문서 메타 조인
    m = meta.get(session_id)
    if m is None:
        stats["meta_missing"] += 1
        for c in META_COLS:
            row[c] = MISSING
    else:
        for c in META_COLS:
            row[c] = m.get(c, MISSING)

    # 화자 메타 조인
    sp = spk.get((str(year), u.get("speaker_id", "")))
    row["speaker_id"] = u.get("speaker_id", "")
    if sp is None:
        stats["speaker_missing"] += 1
        for c in SPK_MAP:
            row[c] = MISSING
    else:
        for c, src in SPK_MAP.items():
            row[c] = sp.get(src, MISSING)

    # 원본 JSON 필드
    ex = extra.get(utt_id)
    if ex is None:
        stats["json_missing"] += 1
        row["original_form"] = row["note"] = MISSING
        for col in (
            "dialogue_id",
            "dialogue_speaker_ids",
            "n_dialogue_speakers",
            "co_speaker_ids",
            "n_co_speakers",
        ):
            row[col] = MISSING
    else:
        for col in (
            "original_form",
            "start",
            "end",
            "note",
            "dialogue_id",
            "dialogue_speaker_ids",
            "n_dialogue_speakers",
            "co_speaker_ids",
            "n_co_speakers",
        ):
            row[col] = ex.get(col, "")
        try:
            row["dur"] = round(
                float(row["end"]) - float(row["start"]), 3
            )
        except (TypeError, ValueError):
            row["dur"] = ""
        participants = {
            item.strip()
            for item in row["dialogue_speaker_ids"].split("|")
            if item.strip()
        }
        co_speakers = {
            item.strip()
            for item in row["co_speaker_ids"].split("|")
            if item.strip()
        }
        if (
            row["speaker_id"] not in participants
            or row["speaker_id"] in co_speakers
            or len(participants) != int(row["n_dialogue_speakers"] or 0)
            or len(co_speakers) != int(row["n_co_speakers"] or 0)
        ):
            stats["dialogue_link_error"] += 1

    # 예측 발음. 기존 form 기반 열은 보존하고, 숫자·기호 때문에 어절 전체가
    # ∅로 소실될 때 original_form이 더 많은 정보를 제공하면 출처를 명시한
    # reference 열에만 채택한다. 숫자 읽기를 임의 추측하지 않는다.
    pron = pp.predict_pron_reference(
        form,
        row["original_form"],
        tagged=tagged,
        ipa_map=ipa_map,
    )
    d = pron["base"]
    ref = pron["reference"]
    row["form_roman"] = d["form_roman"]
    row["pron_pred_hangul"] = d["pron_pred_hangul"]
    row["pron_pred_roman"] = d["pron_pred_roman"]
    row["pron_pred_ipa"] = d["pron_pred_ipa"]
    row["pron_reference_form"] = pron["reference_form"]
    row["pron_reference_form_roman"] = ref["form_roman"]
    row["pron_reference_hangul"] = ref["pron_pred_hangul"]
    row["pron_reference_roman"] = ref["pron_pred_roman"]
    row["pron_reference_ipa"] = ref["pron_pred_ipa"]
    row["pron_reference_source"] = pron["reference_source"]
    row["pron_reference_status"] = pron["reference_status"]
    row["pron_reference_n_eojeol"] = ref["n_eojeol"]
    if pron["reference_status"] == "unresolved_symbol":
        stats["pron_reference_unresolved"] += 1
    row["align_warn"] = d["align_warn"]
    if d["align_warn"]:
        stats["align_warn"] += 1
    if opts.get("tagged_roman"):
        # tagged_roman = 형태소분석(tagged) 자체 구조의 로마자화 → form 정렬과 무관.
        # align_warn(form-tagged 어절수 불일치) 행도 채운다: 형태소 경계 검색(ㄴ삽입 등)
        # 커버리지 보존. 그 행은 pron 컬럼과 어절 위치가 1:1 대응 안 함(= align_warn이 표시).
        row["tagged_roman"] = tagged_to_roman(tagged)
    return row

def tagged_to_roman(tagged):
    """형태소 경계·태그 보존 roman(철자 전자). 발음열과 동일 4단 위계:
    음소=공백 · 음절=' _ ' · 형태소=' + ' · 어절=' | '. (사용자 확정 2026-07-23)"""
    out_groups = []
    for g in tagged.split(" "):
        out_m = []
        for m in g.split("+"):
            surf, _, tag = m.rpartition("/")
            if surf and all(pp.is_syllable(c) for c in surf):
                r = pp.romanize([pp.decompose(c) for c in surf],
                                pp.SPELL_CODA_ROMAN)
            else:
                r = surf or m
            out_m.append(f"{r}/{tag}" if tag else r)
        out_groups.append(" + ".join(out_m))
    return EOJEOL_SEP.join(out_groups)


def read_bareun(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_BAREUN_COLS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path.name} 필수 컬럼 누락: {sorted(missing)}")
        rows = list(reader)
    ids = [row.get("utt_id", "") for row in rows]
    if not rows:
        raise ValueError(f"{csv_path.name} 발화 0행")
    if any(not utt_id for utt_id in ids):
        raise ValueError(f"{csv_path.name} 빈 utt_id 존재")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{csv_path.name} 중복 utt_id 존재")
    return rows


def validate_session_csv(path, expected_cols, expected_ids):
    """완성 CSV의 스키마·행 순서·중복을 검증한다."""
    result = {
        "path": str(path), "valid": False, "reasons": [], "rows": 0,
        "meta_missing": 0, "speaker_missing": 0, "json_missing": 0,
        "align_warn": 0, "eojeol_mismatch": 0,
        "pron_reference_unresolved": 0,
        "dialogue_link_error": 0,
    }
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            if header != expected_cols:
                result["reasons"].append(
                    f"header mismatch: expected={expected_cols!r} actual={header!r}"
                )
            ids = []
            for row in reader:
                ids.append(row.get("utt_id", ""))
                result["meta_missing"] += row.get("category_norm") == MISSING
                result["speaker_missing"] += row.get("sex") == MISSING
                result["json_missing"] += row.get("original_form") == MISSING
                result["align_warn"] += bool(row.get("align_warn"))
                result["pron_reference_unresolved"] += (
                    row.get("pron_reference_status") == "unresolved_symbol"
                )
                if row.get("original_form") != MISSING:
                    participants = {
                        item.strip()
                        for item in row.get("dialogue_speaker_ids", "").split("|")
                        if item.strip()
                    }
                    co_speakers = {
                        item.strip()
                        for item in row.get("co_speaker_ids", "").split("|")
                        if item.strip()
                    }
                    try:
                        participant_count = int(
                            row.get("n_dialogue_speakers") or 0
                        )
                        co_count = int(row.get("n_co_speakers") or 0)
                    except ValueError:
                        participant_count = co_count = -1
                    if (
                        row.get("speaker_id") not in participants
                        or row.get("speaker_id") in co_speakers
                        or len(participants) != participant_count
                        or len(co_speakers) != co_count
                    ):
                        result["dialogue_link_error"] += 1
                try:
                    n_eojeol = int(row.get("n_eojeol") or 0)
                except ValueError:
                    n_eojeol = -1
                for col in ("form_roman", "pron_pred_roman", "pron_pred_ipa"):
                    value = row.get(col, "")
                    if n_eojeol < 0 or (
                        value and len(value.split(EOJEOL_SEP)) != n_eojeol
                    ):
                        result["eojeol_mismatch"] += 1
                        break
                try:
                    reference_n = int(
                        row.get("pron_reference_n_eojeol") or 0
                    )
                except ValueError:
                    reference_n = -1
                for col in (
                    "pron_reference_form_roman",
                    "pron_reference_roman",
                    "pron_reference_ipa",
                ):
                    value = row.get(col, "")
                    if reference_n < 0 or (
                        value
                        and len(value.split(EOJEOL_SEP)) != reference_n
                    ):
                        result["eojeol_mismatch"] += 1
                        break
        result["rows"] = len(ids)
        if ids != expected_ids:
            result["reasons"].append("utt_id sequence/count mismatch")
        if len(ids) != len(set(ids)):
            result["reasons"].append("duplicate utt_id")
        if any(not item for item in ids):
            result["reasons"].append("empty utt_id")
        result["valid"] = not result["reasons"]
    except Exception as exc:
        result["reasons"].append(f"{type(exc).__name__}: {exc}")
    return result


def build_session(bareun_csv, year, meta, spk, json_idx, ipa_map, opts):
    """세션 1개 -> 출력 CSV. 반환: 검증 통계 dict."""
    session_id = bareun_csv.stem
    utts = read_bareun(bareun_csv)
    extra = {}
    jp = json_idx.get(session_id)
    if jp is not None:
        try:
            extra = load_utt_extra(jp)
        except Exception as e:
            print(f"    [경고] JSON 파싱 실패 {session_id}: {e}", flush=True)

    cols = list(BASE_COLS)
    if opts.get("tagged_roman"):
        cols.insert(cols.index("form_roman") + 1, "tagged_roman")

    stats = {"session": session_id, "n_utt": len(utts), "n_row": 0,
             "meta_missing": 0, "speaker_missing": 0, "json_missing": 0,
             "align_warn": 0, "eojeol_mismatch": 0, "json_found": jp is not None,
             "pron_reference_unresolved": 0,
             "dialogue_link_error": 0,
             "status": "pending", "archive": "", "partial": ""}

    out_dir = opts["output_root"] / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.csv"
    expected_ids = [u["utt_id"] for u in utts]

    if out_path.exists():
        existing = validate_session_csv(out_path, cols, expected_ids)
        if existing["valid"] and not opts["overwrite"]:
            stats.update(
                status="validated_existing",
                n_row=existing["rows"],
                meta_missing=existing["meta_missing"],
                speaker_missing=existing["speaker_missing"],
                json_missing=existing["json_missing"],
                align_warn=existing["align_warn"],
                eojeol_mismatch=existing["eojeol_mismatch"],
                pron_reference_unresolved=existing[
                    "pron_reference_unresolved"
                ],
                dialogue_link_error=existing["dialogue_link_error"],
            )
            return stats
        stats["replace_reason"] = (
            "overwrite" if opts["overwrite"]
            else "invalid_existing: " + "; ".join(existing["reasons"])
        )

    temp_path = None
    with staged_text_writer(
        out_path, newline="", encoding="utf-8-sig"
    ) as (f, temp_path):
        stats["partial"] = str(temp_path)
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for u in utts:
            row = build_row(u, year, meta, spk, extra, ipa_map, opts, stats)
            # 검증: 문자열 컬럼 어절수 = n_eojeol
            ne = row["n_eojeol"]
            for col in ("form_roman", "pron_pred_roman", "pron_pred_ipa"):
                if row[col] and ne and len(row[col].split(EOJEOL_SEP)) != ne:
                    stats["eojeol_mismatch"] += 1
                    break
            reference_ne = row["pron_reference_n_eojeol"]
            for col in (
                "pron_reference_form_roman",
                "pron_reference_roman",
                "pron_reference_ipa",
            ):
                if (
                    row[col]
                    and reference_ne
                    and len(row[col].split(EOJEOL_SEP)) != reference_ne
                ):
                    stats["eojeol_mismatch"] += 1
                    break
            w.writerow(row)
            stats["n_row"] += 1

    staged = validate_session_csv(temp_path, cols, expected_ids)
    if not staged["valid"]:
        raise RuntimeError(
            f"{session_id} 임시 CSV 검증 실패({temp_path}): "
            + "; ".join(staged["reasons"])
        )

    if out_path.exists():
        relative = Path(str(year)) / out_path.name
        archived = archive_copy(out_path, opts["archive_root"], relative)
        stats["archive"] = str(archived)
    promote_staged(temp_path, out_path)
    stats["partial"] = ""
    stats["status"] = "created"
    stats["output"] = file_fingerprint(out_path)
    return stats

def year_folders():
    """01_bareun_raw 아래 연도 폴더 목록 -> {연도: 경로}."""
    raw = P("layers") / "01_bareun_raw"
    out = {}
    for d in sorted(raw.iterdir()):
        if not d.is_dir():
            continue
        m = re.search(r"(20\d\d)", d.name)
        if m:
            out[m.group(1)] = d
    return out


def session_files(ydir, sessions=None):
    files = sorted(p for p in ydir.glob("*.csv") if not p.name.startswith("_"))
    if sessions:
        want = set(sessions)
        files = [p for p in files if p.stem in want]
    return files


def main():
    ap = argparse.ArgumentParser(description="검색 마스터 v1 세션 CSV 생성")
    ap.add_argument("--year", help="특정 연도만 (예: 2020). 생략 시 전량")
    ap.add_argument("--pilot", type=int, help="연도별 앞 N개 세션만(파일럿)")
    ap.add_argument("--sessions", nargs="*", help="세션ID 직접 지정")
    ap.add_argument("--overwrite", action="store_true", help="기존 CSV 재생성")
    ap.add_argument("--no-tagged-roman", dest="tagged_roman",
                    action="store_false",
                    help="tagged_roman 컬럼 제외(기본 포함 — 사용자 확정)")
    ap.add_argument("--coverage", action="store_true",
                    help="현재 미구현. 빈 coverage를 실제값으로 오인하지 않도록 실패 처리")
    ap.add_argument("--output-root", type=Path,
                    help="격리 파일럿·테스트용 출력 루트(기본 paths.json search_master)")
    ap.add_argument("--run-id", help="외부 실행기가 부여한 실행 ID")
    ap.add_argument("--allow-missing-json", action="store_true",
                    help="JSON 발화·세션 결측이 있어도 완료 허용(기본은 연구 안전상 실패)")
    args = ap.parse_args()
    if args.coverage:
        ap.error("--coverage는 아직 구현되지 않았습니다. 빈 값을 실제 결측으로 "
                 "오인하지 않도록 현재는 실행을 차단합니다.")

    run_id = args.run_id or new_run_id("search_master")
    output_root = (args.output_root or P("search_master")).resolve()
    opts = {
        "tagged_roman": args.tagged_roman,
        "coverage": False,
        "overwrite": args.overwrite,
        "output_root": output_root,
        "archive_root": output_root / "_archive" / run_id,
        "run_id": run_id,
        "allow_missing_json": args.allow_missing_json,
    }
    ipa_path = P("layers") / "03_freq_dictionaries" / "_roman_mfa_to_ipa.csv"
    ipa_map = pp.load_ipa_map(str(ipa_path))
    print("메타데이터 로드(file_meta·speakers_normalized)...", flush=True)
    meta = load_file_meta()
    spk = load_speakers()

    yfolders = year_folders()
    if args.year and args.year not in yfolders:
        ap.error(f"{args.year}: 01_bareun_raw 연도 폴더가 없습니다. "
                 f"사용 가능: {sorted(yfolders)}")
    years = [args.year] if args.year else sorted(yfolders)
    if not years:
        ap.error("처리할 연도 폴더가 0개입니다.")
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    report = log_dir / f"build_search_master_{run_id}.txt"
    lines = [f"검색 마스터 빌드 — {run_id}",
              f"옵션: year={args.year} pilot={args.pilot} "
             f"tagged_roman={args.tagged_roman} coverage=False "
             f"overwrite={args.overwrite}",
             f"출력: {output_root}", ""]

    grand = {"n_utt": 0, "n_row": 0, "meta_missing": 0, "speaker_missing": 0,
             "json_missing": 0, "align_warn": 0, "eojeol_mismatch": 0,
             "pron_reference_unresolved": 0,
             "dialogue_link_error": 0,
             "sessions": 0, "created": 0, "validated_existing": 0,
             "archived": 0, "json_missing_sessions": 0}
    for year in years:
        json_idx = build_json_index(year)
        files = session_files(yfolders[year], args.sessions)
        if args.pilot:
            files = files[:args.pilot]
        if not files:
            raise RuntimeError(f"{year}: 처리 대상 세션 CSV가 0개")
        print(f"[{year}] 대상 세션 {len(files)}개 "
              f"(JSON 인덱스 {len(json_idx)})", flush=True)
        lines.append(f"[{year}] 대상 {len(files)}개")
        for i, bc in enumerate(files, 1):
            st = build_session(bc, year, meta, spk, json_idx, ipa_map, opts)
            grand["sessions"] += 1
            grand[st["status"]] += 1
            if st.get("archive"):
                grand["archived"] += 1
            for k in ("n_utt", "n_row", "meta_missing", "speaker_missing",
                      "json_missing", "align_warn", "eojeol_mismatch",
                      "pron_reference_unresolved", "dialogue_link_error"):
                grand[k] += st[k]
            if not st["json_found"]:
                grand["json_missing_sessions"] += 1
            flag = "" if st["n_utt"] == st["n_row"] else "  ★행수불일치"
            note = "" if st["json_found"] else "  ★JSON없음"
            msg = (f"  {i}/{len(files)} {st['session']}: 발화 {st['n_utt']} "
                   f"행 {st['n_row']} 정렬경고 {st['align_warn']} "
                   f"어절불일치 {st['eojeol_mismatch']} 상태 {st['status']}"
                   f"{flag}{note}")
            print(msg, flush=True)
            lines.append(msg)
    return grand, lines, report, opts


def summarize(grand, lines, report, opts):
    lines += ["", "── 합계 ──",
              f"  대상 세션: {grand['sessions']} (생성 {grand['created']}, "
              f"기존 검증 {grand['validated_existing']}, 구판 보존 {grand['archived']})",
              f"  발화(입력): {grand['n_utt']:,}  행(출력): {grand['n_row']:,}",
              f"  메타 결측: {grand['meta_missing']}  화자 결측: "
              f"{grand['speaker_missing']}  JSON 발화결측: {grand['json_missing']}",
              f"  JSON 없는 세션: {grand['json_missing_sessions']}",
              f"  정렬경고(form-tagged): {grand['align_warn']}  "
              f"어절수 불일치: {grand['eojeol_mismatch']}",
              f"  기준발음 미해결 숫자·기호: "
              f"{grand['pron_reference_unresolved']}",
              f"  대화 참여자 연결 오류: {grand['dialogue_link_error']}"]
    row_ok = grand["n_utt"] == grand["n_row"]
    eoj_ok = grand["eojeol_mismatch"] == 0
    meta_ok = grand["meta_missing"] == 0
    json_ok = (
        opts["allow_missing_json"]
        or (grand["json_missing"] == 0 and grand["json_missing_sessions"] == 0)
    )
    dialogue_ok = grand["dialogue_link_error"] == 0
    verdict_ok = row_ok and eoj_ok and meta_ok and json_ok and dialogue_ok
    verdict = "✅ 검증 통과" if verdict_ok else "❌ 검증 실패"
    lines += ["", f"판정: {verdict}"]
    report.parent.mkdir(parents=True, exist_ok=True)
    from pipeline_common import atomic_text_writer
    with atomic_text_writer(report, encoding="utf-8", newline="\n") as (stream, _):
        stream.write("\n".join(lines) + "\n")
    # 투명성 기록: 어떤 도구·자료·규칙으로 만든 CSV인지 산출 옆에 남김.
    meta = {
        **runtime_snapshot(PROJECT_ROOT),
        "run_id": opts["run_id"],
        "status": "success" if verdict_ok else "validation_failed",
        "verdict": verdict,
        "totals": grand,
        "options": {
            "tagged_roman": opts["tagged_roman"],
            "coverage": False,
            "overwrite": opts["overwrite"],
            "allow_missing_json": opts["allow_missing_json"],
        },
        "resolved_paths": {
            "output_root": str(opts["output_root"]),
            "dialogue_json": str(P("dialogue_json")),
            "layers": str(P("layers")),
            "ipa_map": str(P("layers") / "03_freq_dictionaries"
                           / "_roman_mfa_to_ipa.csv"),
        },
        **BUILD_PROVENANCE,
    }
    meta_path = opts["output_root"] / "_build_meta.json"
    run_path = opts["output_root"] / "_runs" / f"{opts['run_id']}.json"
    atomic_write_json(meta_path, meta)
    atomic_write_json(run_path, meta)
    print("\n".join(lines[-9:]))
    print(f"\n보고서: {report}\n출처 기록: {meta_path}\n실행 기록: {run_path}")
    return 0 if verdict_ok else 1


def write_crash_manifest(run_id, exc):
    payload = {
        **runtime_snapshot(PROJECT_ROOT),
        "run_id": run_id,
        "status": "crashed",
        "error": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc(),
    }
    path = PROJECT_ROOT / "logs" / f"build_search_master_{run_id}_crash.json"
    atomic_write_json(path, payload)
    return path


if __name__ == "__main__":
    _run_id = new_run_id("search_master")
    # --run-id가 있으면 main 내부에서 이를 사용하지만, 파싱 전 crash도 기록하기
    # 위해 외부 기본 ID를 하나 확보한다.
    try:
        _g, _l, _r, _o = main()
        raise SystemExit(summarize(_g, _l, _r, _o))
    except SystemExit:
        raise
    except Exception as _exc:
        _crash = write_crash_manifest(_run_id, _exc)
        print(f"\n치명 오류: {_exc}\ncrash manifest: {_crash}", file=sys.stderr)
        raise SystemExit(1)

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
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P
import predict_pron as pp

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(10_000_000)

MISSING = "미상"
EOJEOL_SEP = " | "

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
            "coverage": "17,156 파일=원본 JSON 전수, 총 5,103,358 발화, 빈 분석 0",
            "validation": "형태소 F1 0.929 (2024/다층위 2025 gold 대조)",
        },
        "문서메타": "D:/10_LAYERS/04_metadata_index/file_meta.csv (category_norm·discourse_mode·topic·relation·date·in_ml2025_gold)",
        "화자메타": "D:/10_LAYERS/04_metadata_index/speakers_normalized.csv (_norm 컬럼)",
        "원전사·시간·비고": "D:/00_RAW/dialogue_json (original_form·start·end·note)",
        "IPA표": "D:/10_LAYERS/03_freq_dictionaries/_roman_mfa_to_ipa.csv (빈도사전 공유)",
    },
    "예측발음_규칙": {
        "적용순서": "격음화→ㅎ탈락→구개음화→연음→중화→겹받침단순화→비음/유음→경음화(+용언 어간+어미 경음화)",
        "미적용(수의)": "ㄹ비음화·ㄴ삽입·합성어경음화·위치동화 등",
        "테스트": "predict_pron.py --selftest 30/30 통과",
    },
}

# 출력 컬럼(설계 §2 순서). tagged_roman은 --tagged-roman 시 form_roman 뒤 삽입.
BASE_COLS = [
    "utt_id", "year", "session_id", "utt_seq",
    "has_wav", "has_tg_eojeol", "quarantined",
    "category_norm", "discourse_mode", "topic", "relation", "date",
    "in_ml2025_gold",
    "speaker_id", "sex", "age_norm", "occupation_norm", "education_ord",
    "birthplace_norm", "current_residence_norm",
    "form", "tagged", "n_morphs", "n_eojeol",
    "original_form", "start", "end", "dur", "note",
    "form_roman", "pron_pred_hangul", "pron_pred_roman", "pron_pred_ipa",
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
            out[r["file_id"]] = r
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
    """세션 JSON -> {utt_id: (original_form, start, end, note)}."""
    extra = {}
    with open(json_path, encoding="utf-8") as f:
        doc = json.load(f)
    for d in doc.get("document", []):
        for u in d.get("utterance", []):
            extra[u.get("id", "")] = (
                u.get("original_form", ""), u.get("start", ""),
                u.get("end", ""), u.get("note", ""))
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
    else:
        of, st, en, note = ex
        row["original_form"], row["start"], row["end"], row["note"] = \
            of, st, en, note
        try:
            row["dur"] = round(float(en) - float(st), 3)
        except (TypeError, ValueError):
            row["dur"] = ""

    # 예측 발음
    d = pp.predict_pron(form, tagged=tagged, ipa_map=ipa_map)
    row["form_roman"] = d["form_roman"]
    row["pron_pred_hangul"] = d["pron_pred_hangul"]
    row["pron_pred_roman"] = d["pron_pred_roman"]
    row["pron_pred_ipa"] = d["pron_pred_ipa"]
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
        return list(csv.DictReader(f))


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
             "align_warn": 0, "eojeol_mismatch": 0, "json_found": jp is not None}

    out_dir = P("search_master") / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
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
            w.writerow(row)
            stats["n_row"] += 1
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
                    help="has_wav 등 coverage 컬럼 채움(기본 off)")
    args = ap.parse_args()

    opts = {"tagged_roman": args.tagged_roman, "coverage": args.coverage}
    ipa_path = P("layers") / "03_freq_dictionaries" / "_roman_mfa_to_ipa.csv"
    ipa_map = pp.load_ipa_map(str(ipa_path))
    print("메타데이터 로드(file_meta·speakers_normalized)...", flush=True)
    meta = load_file_meta()
    spk = load_speakers()

    yfolders = year_folders()
    years = [args.year] if args.year else sorted(yfolders)
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = log_dir / f"build_search_master_{stamp}.txt"
    lines = [f"검색 마스터 빌드 — {stamp}",
             f"옵션: year={args.year} pilot={args.pilot} "
             f"tagged_roman={args.tagged_roman} coverage={args.coverage}", ""]

    grand = {"n_utt": 0, "n_row": 0, "meta_missing": 0, "speaker_missing": 0,
             "json_missing": 0, "align_warn": 0, "eojeol_mismatch": 0,
             "sessions": 0, "skipped": 0, "json_missing_sessions": 0}
    for year in years:
        if year not in yfolders:
            print(f"[건너뜀] {year}: bareun 폴더 없음", flush=True)
            continue
        json_idx = build_json_index(year)
        files = session_files(yfolders[year], args.sessions)
        if args.pilot:
            files = files[:args.pilot]
        print(f"[{year}] 대상 세션 {len(files)}개 "
              f"(JSON 인덱스 {len(json_idx)})", flush=True)
        lines.append(f"[{year}] 대상 {len(files)}개")
        for i, bc in enumerate(files, 1):
            out_path = P("search_master") / str(year) / f"{bc.stem}.csv"
            if out_path.exists() and not args.overwrite:
                grand["skipped"] += 1
                continue
            st = build_session(bc, year, meta, spk, json_idx, ipa_map, opts)
            grand["sessions"] += 1
            for k in ("n_utt", "n_row", "meta_missing", "speaker_missing",
                      "json_missing", "align_warn", "eojeol_mismatch"):
                grand[k] += st[k]
            if not st["json_found"]:
                grand["json_missing_sessions"] += 1
            flag = "" if st["n_utt"] == st["n_row"] else "  ★행수불일치"
            note = "" if st["json_found"] else "  ★JSON없음"
            msg = (f"  {i}/{len(files)} {st['session']}: 발화 {st['n_utt']} "
                   f"행 {st['n_row']} 정렬경고 {st['align_warn']} "
                   f"어절불일치 {st['eojeol_mismatch']}{flag}{note}")
            print(msg, flush=True)
            lines.append(msg)
    return grand, lines, report


def summarize(grand, lines, report):
    lines += ["", "── 합계 ──",
              f"  생성 세션: {grand['sessions']} (건너뜀 {grand['skipped']})",
              f"  발화(입력): {grand['n_utt']:,}  행(출력): {grand['n_row']:,}",
              f"  메타 결측: {grand['meta_missing']}  화자 결측: "
              f"{grand['speaker_missing']}  JSON 발화결측: {grand['json_missing']}",
              f"  JSON 없는 세션: {grand['json_missing_sessions']}",
              f"  정렬경고(form-tagged): {grand['align_warn']}  "
              f"어절수 불일치: {grand['eojeol_mismatch']}"]
    row_ok = grand["n_utt"] == grand["n_row"]
    eoj_ok = grand["eojeol_mismatch"] == 0
    verdict = "✅ 검증 통과" if (row_ok and eoj_ok) else "★ 검토 필요"
    lines += ["", f"판정: {verdict}"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 투명성 기록: 어떤 도구·자료·규칙으로 만든 CSV인지 산출 옆에 남김.
    meta = {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "verdict": verdict, "totals": grand, **BUILD_PROVENANCE}
    meta_path = P("search_master") / "_build_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print("\n".join(lines[-9:]))
    print(f"\n보고서: {report}\n출처 기록: {meta_path}")
    return 0 if (row_ok and eoj_ok) else 1


if __name__ == "__main__":
    _g, _l, _r = main()
    raise SystemExit(summarize(_g, _l, _r))

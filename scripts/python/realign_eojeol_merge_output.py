"""어절 재정렬 MFA 출력 + 기존 형태소 경계 → 4-tier 표준 TextGrid (목적 B).

한 파일에 다 담는다:
  tier1 words     = 어절            (신규 어절 MFA 정렬)
  tier2 phones    = 연결 실제 발음   (신규, 교정된 것: 것을→거슬)
  tier3 morphemes = 형태소 경계      (기존 06_textgrid_merged의 words tier 재사용)
  tier4 utterance = form
입력: D:/mfa_eojeol/out/{year}/{session}/{utt}.TextGrid  (신규 어절 정렬)
      D:/20_AUDIO/06_textgrid_merged/{year}/{session}/{utt}.TextGrid (기존 형태소, 읽기만)
      01_bareun_raw (form)
출력: D:/20_AUDIO/06_textgrid_eojeol/{year}/{session}/{utt}.TextGrid  (4-tier)
  ※ 기존 형태소 폴더(06_textgrid_merged)는 읽기 전용 — 절대 안 건드림.
  ※ 형태소 정렬이 없는 발화는 morphemes tier를 빈 채로 두고 표시(morph_missing 집계).
재개 가능(대상 위치에 이미 있으면 건너뜀).
실행: python realign_eojeol_merge_output.py --year 2020
"""
import argparse
import csv
import os
import sys
import time
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 형제 모듈 import 보장
from merge_textgrid_v2 import interval_tier              # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid, YEAR_DIRS  # noqa: E402

MFA_OUT = Path(r"D:\mfa_eojeol\out")
MORPH_TG = Path(r"D:\20_AUDIO\06_textgrid_merged")   # 기존 형태소 경계 소스(불변)
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
OUT_ROOT = Path(r"D:\20_AUDIO\06_textgrid_eojeol")
YEAR_DIRS = {**YEAR_DIRS, "2025": "NIKL_DIALOGUE_2025_v1.0"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def write_4tier(path, dur, words, phones, morphemes, form):
    tiers = [
        interval_tier("words", words, dur),
        interval_tier("phones", phones, dur),
        interval_tier("morphemes", morphemes or [(0.0, dur, "")], dur),
        interval_tier("utterance", [(0.0, dur, form)], dur),
    ]
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {dur:.6f}", "tiers? <exists>",
             f"size = {len(tiers)}", "item []:"]
    for i, tier in enumerate(tiers, 1):
        lines.append(f"    item [{i}]:")
        lines.extend(tier)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_forms(year, sessions):
    forms = {}
    ydir = RAW / YEAR_DIRS[year]
    for s in sessions:
        fp = ydir / f"{s}.csv"
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                forms[row["utt_id"]] = row["form"]
    return forms


def morpheme_tier(year, session, utt):
    """기존 형태소 TextGrid에서 words tier(=형태소 경계) 추출. 없으면 None."""
    fp = MORPH_TG / year / session / f"{utt}.TextGrid"
    if not fp.exists():
        return None
    try:
        _, tiers = parse_mfa_textgrid(fp)
        return tiers.get("words", [])
    except Exception:
        return None


def iter_session_tgs(src_year: Path):
    """(세션명, TextGrid 경로 목록) 생성 — 세션 하위폴더·평면 모두 지원.
    ★ 2026-07-17 실측: wav 코퍼스가 평면인 연도(2020·2021·2025)는 MFA 출력도
    평면(루트에 TextGrid 직접) → 기존 '세션 폴더만' 가정이면 세션 0개로 조용히
    무시됨. 평면이면 파일명에서 세션명 유도(utt.split('.')[0])."""
    dir_names, tg_names = [], []
    for e in os.scandir(src_year):
        if e.is_dir():
            dir_names.append(e.name)
        elif e.name.endswith(".TextGrid"):
            tg_names.append(e.name)
    if dir_names:  # 세션 하위폴더 구조
        nsess = len(dir_names)
        for sname in sorted(dir_names):
            yield nsess, sname, sorted((src_year / sname).glob("*.TextGrid"))
    if tg_names:   # 평면 구조
        tg_names.sort()
        nsess = len({n.split(".")[0] for n in tg_names})
        for sname, grp in groupby(tg_names, key=lambda n: n.split(".")[0]):
            yield nsess, sname, [src_year / n for n in grp]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, choices=sorted(YEAR_DIRS))
    ap.add_argument("--mfa-out", default=str(MFA_OUT),
                    help="MFA 원출력 루트 (기본 D:; 러너는 C: SSD를 넘김)")
    args = ap.parse_args()

    src_year = Path(args.mfa_out) / args.year
    if not src_year.exists():
        sys.exit(f"어절 재정렬 출력 없음: {src_year}")
    print(f"[{args.year}] form 로드 (전 세션)...", flush=True)
    forms = load_forms(args.year, {p.stem for p in
                                   (RAW / YEAR_DIRS[args.year]).glob("*.csv")
                                   if not p.name.startswith("_")})
    print(f"  form {len(forms):,}개", flush=True)

    made = skipped = failed = morph_missing = 0
    t0 = time.time()
    for si, (nsess, sname, tgs) in enumerate(iter_session_tgs(src_year), 1):
        out_dir = OUT_ROOT / args.year / sname
        out_dir.mkdir(parents=True, exist_ok=True)
        for tg in tgs:
            out_path = out_dir / tg.name
            if out_path.exists():
                skipped += 1
                continue
            try:
                dur, tiers = parse_mfa_textgrid(tg)
                words = tiers.get("words", [])      # 어절
                phones = tiers.get("phones", [])    # 연결 발음
                if dur is None or not words or not phones:
                    failed += 1
                    continue
                morphs = morpheme_tier(args.year, sname, tg.stem)
                if morphs is None:
                    morph_missing += 1
                write_4tier(out_path, dur, words, phones, morphs,
                            forms.get(tg.stem, ""))
                made += 1
            except Exception as e:
                failed += 1
                print(f"  !! {tg.name}: {type(e).__name__}: {e}", flush=True)
        if si % 50 == 0:
            rate = made / (time.time() - t0) if made else 0
            print(f"  세션 {si:,}/{nsess:,} (생성 {made:,}, "
                  f"형태소없음 {morph_missing:,}, {rate:.0f}/s)", flush=True)
    print(f"완료[{args.year}]: 생성 {made:,} / 건너뜀 {skipped:,} / "
          f"실패 {failed:,} / 형태소tier없음 {morph_missing:,}")
    if made == 0 and skipped == 0:
        print(f"!! 처리 0건 — {src_year} 구조 확인 필요", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""어절(語節) 전량 재정렬용 MFA 코퍼스 구성 (2020-2025).

배경: 기존 정렬은 .lab을 '형태소' 단위로 넣어(make_labs), MFA가 형태소마다 따로
G2P → phone 라벨이 '고립형'이 됨(것을→[걷을], 연음 [거슬] 아님). 경계 음운현상
(연음·경음화·ㄴ첨가)이 라벨에 안 담김. 교정: .lab을 '어절'(form 표층)로 생성 →
MFA가 어절 단위 연결 발음으로 G2P(것을 → 거슬). 표준 MFA 사용법.

- wav은 individual에서 하드링크(무복사, 같은 볼륨 D:). 세션 하위폴더=화자 단위.
- 어절 lab = form을 공백 분리 후 어절별 '한글만' 유지(문장부호/숫자/외국어 제외
  = 기존 형태소 lab의 S* 제외와 대응). 빈 어절 버림.
출력: D:/mfa_eojeol/corpus/{year}/{session}/{utt}.wav(링크) + {utt}.lab
재개 가능(짝 이미 있으면 건너뜀).
실행: python realign_eojeol_build_corpus.py --year 2020   (또는 all)
"""
import argparse
import csv
import os
import re
import shutil
import sys
from pathlib import Path

WAV_ROOT = Path(r"D:\20_AUDIO\03_wav\individual")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
CORPUS_ROOT = Path(r"D:\mfa_eojeol\corpus")
YEAR_DIRS = {
    "2020": "NIKL_DIALOGUE_2020_v1.4", "2021": "NIKL_DIALOGUE_2021_v1.1",
    "2022": "NIKL_DIALOGUE_2022_v1.0_JSON", "2023": "NIKL_DIALOGUE_2023_v1.1",
    "2024": "NIKL_DIALOGUE_2024_v1.0", "2025": "NIKL_DIALOGUE_2025_v1.0",
}
HANGUL = re.compile(r"[가-힣]+")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def form_to_lab(form: str) -> str:
    """표층 form -> 어절 lab. 어절별 한글만 유지(문장부호/숫자/외국어 제외)."""
    toks = []
    for w in (form or "").split():
        h = "".join(HANGUL.findall(w))
        if h:
            toks.append(h)
    return " ".join(toks)


def wav_path(year: str, utt: str):
    """발화 wav 경로 (세션 하위폴더 우선, 없으면 평면=2025)."""
    sess = utt.split(".")[0]
    nested = WAV_ROOT / year / sess / f"{utt}.wav"
    if nested.exists():
        return nested
    flat = WAV_ROOT / year / f"{utt}.wav"
    if flat.exists():
        return flat
    return None


def link_or_copy(src: Path, dst: Path):
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_year(year: str) -> None:
    raw_dir = RAW / YEAR_DIRS[year]
    files = sorted(p for p in raw_dir.glob("*.csv")
                   if not p.name.startswith("_"))
    print(f"[{year}] 세션 {len(files):,}개 코퍼스 구성...", flush=True)
    made = skipped = no_wav = empty = 0
    for k, fp in enumerate(files, 1):
        sess = fp.stem
        out_sess = CORPUS_ROOT / year / sess
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                u = row["utt_id"]
                dst_wav = out_sess / f"{u}.wav"
                dst_lab = out_sess / f"{u}.lab"
                if dst_wav.exists() and dst_lab.exists():
                    skipped += 1
                    continue
                lab = form_to_lab(row.get("form", ""))
                if not lab.strip():
                    empty += 1
                    continue
                src = wav_path(year, u)
                if src is None:
                    no_wav += 1
                    continue
                out_sess.mkdir(parents=True, exist_ok=True)
                if not dst_wav.exists():
                    link_or_copy(src, dst_wav)
                dst_lab.write_text(lab, encoding="utf-8")
                made += 1
        if k % 500 == 0:
            print(f"  {k}/{len(files)} (구성 {made:,})", flush=True)
    print(f"[{year}] 완료: 구성 {made:,} / 건너뜀 {skipped:,} / "
          f"wav없음 {no_wav:,} / 빈lab {empty:,}", flush=True)
    print(f"  코퍼스: {CORPUS_ROOT / year}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    args = ap.parse_args()
    years = sorted(YEAR_DIRS) if args.year == "all" else [args.year]
    for y in years:
        if y not in YEAR_DIRS:
            sys.exit(f"알 수 없는 연도: {y}")
        build_year(y)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

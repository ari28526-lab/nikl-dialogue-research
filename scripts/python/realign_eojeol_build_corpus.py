"""어절(語節) 전량 재정렬용 .lab 생성 — 제자리(in-place) 방식 (2020-2025).

★ 원래 파이프라인(make_labs)과 동일하게 lab을 wav '옆에' 직접 쓴다. 하드링크 없음.
   (하드링크 코퍼스 방식은 USB에서 느려 폐기 — 이 스크립트가 그걸 대체.)
교정 요점: lab을 '형태소'가 아니라 '어절'(form 표층)로 → MFA가 어절 단위 연결
발음으로 정렬(것을→거슬). 어절별 한글만 유지(문장부호/숫자/외국어 제외).

wav 위치(=lab 위치): individual/{year}/{session}/{utt}.wav (2020-2024)
                     individual/2025/{utt}.wav (평면)
→ MFA 코퍼스 = individual/{year} 폴더 그대로.
재개 가능(.lab 이미 있으면 건너뜀). wav 없는 발화는 lab 안 만듦.
실행: python realign_eojeol_build_corpus.py --year 2020   (또는 all)
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

WAV_ROOT = Path(r"D:\20_AUDIO\03_wav\individual")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
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


def build_year(year: str) -> None:
    raw_dir = RAW / YEAR_DIRS[year]
    files = sorted(p for p in raw_dir.glob("*.csv")
                   if not p.name.startswith("_"))
    nfiles = len(files)
    print(f"[{year}] 세션 {nfiles:,}개 — lab 제자리 생성...", flush=True)
    made = skipped = no_wav = empty = 0
    t0 = time.time()
    for k, fp in enumerate(files, 1):
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                u = row["utt_id"]
                wav = wav_path(year, u)
                if wav is None:
                    no_wav += 1
                    continue
                lab = wav.with_suffix(".lab")
                if lab.exists():
                    skipped += 1
                    continue
                text = form_to_lab(row.get("form", ""))
                if not text.strip():
                    empty += 1
                    continue
                lab.write_text(text, encoding="utf-8")
                made += 1
        # 자주(10세션마다) 속도·남은시간 출력 → 실시간 진행 확인
        if k % 10 == 0 or k == nfiles:
            el = time.time() - t0
            proc = made + skipped        # 실제로 훑은 발화(신규+기존)
            rate = proc / el if el > 0 else 0
            eta_min = (nfiles - k) / (k / el) / 60 if el > 0 and k else 0
            print(f"  {year} {k}/{nfiles}세션 · 신규lab {made:,} · "
                  f"{rate:.0f}발화/s · 이 연도 남은 ~{eta_min:.0f}분", flush=True)
    print(f"[{year}] 완료: lab {made:,} / 건너뜀 {skipped:,} / "
          f"wav없음 {no_wav:,} / 빈form {empty:,}", flush=True)
    print(f"  코퍼스(=wav폴더): {WAV_ROOT / year}", flush=True)


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

"""재정렬 MFA 출력 → 표준 3-tier TextGrid → 06_textgrid_merged 병합.

입력: {MFA_OUT}/{year}/{session}/{utt}.TextGrid  (mfa align 재정렬 원출력)
      + 01_bareun_raw (utterance tier용 form)
출력: 06_textgrid_merged/{year}/{session}/{utt}.TextGrid  (표준 v2, 3-tier)
      ※ 기존 파일은 절대 덮어쓰지 않음 — 회수분(빈칸)만 채움.
변환기는 기존 파이프라인 것을 그대로 재사용(형식 완전 일치):
  retrofit_textgrid_2020_2024.parse_mfa_textgrid + merge_textgrid_v2.write_textgrid

재개 가능(대상 위치에 이미 있으면 건너뜀).
실행: python realign_merge_output.py --year 2023
"""
import argparse
import csv
import sys
import time
from pathlib import Path

from merge_textgrid_v2 import write_textgrid
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid, YEAR_DIRS

MFA_OUT = Path(r"D:\mfa_realign\out")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
MERGED = Path(r"D:\20_AUDIO\06_textgrid_merged")
# 2025 원자료 매핑 보강 (retrofit YEAR_DIRS는 2020-2024만)
YEAR_DIRS = {**YEAR_DIRS, "2025": "NIKL_DIALOGUE_2025_v1.0"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_forms(year: str, sessions: set[str]) -> dict:
    """해당 세션들의 form만 로드 (utterance tier용)."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, choices=sorted(YEAR_DIRS))
    args = ap.parse_args()

    src_year = MFA_OUT / args.year
    if not src_year.exists():
        sys.exit(f"재정렬 출력 없음: {src_year}")
    sessions = sorted(d.name for d in src_year.iterdir() if d.is_dir())
    print(f"[{args.year}] 재정렬 세션 {len(sessions):,}개 form 로드...", flush=True)
    forms = load_forms(args.year, set(sessions))
    print(f"  form {len(forms):,}개", flush=True)

    made = skipped = failed = 0
    t0 = time.time()
    for si, sname in enumerate(sessions, 1):
        sdir = src_year / sname
        out_dir = MERGED / args.year / sname
        out_dir.mkdir(parents=True, exist_ok=True)
        for tg in sdir.glob("*.TextGrid"):
            out_path = out_dir / tg.name
            if out_path.exists():
                skipped += 1  # 기존 정상 정렬 — 보존
                continue
            try:
                dur, tiers = parse_mfa_textgrid(tg)
                words = tiers.get("words", [])
                phones = tiers.get("phones", [])
                if dur is None or not words or not phones:
                    failed += 1
                    continue
                write_textgrid(out_path, dur, words, phones,
                               forms.get(tg.stem, ""))
                made += 1
            except Exception as e:
                failed += 1
                print(f"  !! {tg.name}: {type(e).__name__}: {e}", flush=True)
        if si % 50 == 0:
            rate = made / (time.time() - t0) if made else 0
            print(f"  세션 {si:,}/{len(sessions):,} (회수 {made:,}, "
                  f"{rate:.0f}/s)", flush=True)
    print(f"완료[{args.year}]: 회수(신규 생성) {made:,} / 기존보존 {skipped:,} / "
          f"실패 {failed:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

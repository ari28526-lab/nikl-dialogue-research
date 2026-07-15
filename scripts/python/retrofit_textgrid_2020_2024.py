"""2020-2024 TextGrid를 표준 v2(3-tier)로 소급 재생성.

원천: 20_AUDIO/05_mfa_output/{연도}/... (MFA 원출력: words/phones만)
      + 10_LAYERS/01_bareun_raw (utterance tier용 form)
출력: 20_AUDIO/06_textgrid_merged_v2/{연도}/{세션}/{utt_id}.TextGrid
완료 후 구판(06_textgrid_merged/{연도})은 90_ARCHIVE로 이동 예정.

세션 단위 재개 가능. 연도별 분할 실행:
  python retrofit_textgrid_2020_2024.py --year 2020
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

MFA_OUT = Path(r"D:\20_AUDIO\05_mfa_output")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
OUT = Path(r"D:\20_AUDIO\06_textgrid_merged_v2")
YEAR_DIRS = {"2020": "NIKL_DIALOGUE_2020_v1.4", "2021": "NIKL_DIALOGUE_2021_v1.1",
             "2022": "NIKL_DIALOGUE_2022_v1.0_JSON", "2023": "NIKL_DIALOGUE_2023_v1.1",
             "2024": "NIKL_DIALOGUE_2024_v1.0"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def esc(t: str) -> str:
    return t.replace('"', '""')

from merge_textgrid_v2 import write_textgrid  # 표준 v2 작성기 재사용

IV_RE = re.compile(
    r'xmin = ([\d.eE+-]+)\s*\n\s*xmax = ([\d.eE+-]+)\s*\n\s*text = "(.*?)"\s*\n',
    re.S)
TIER_RE = re.compile(r'name = "([^"]+)"(.*?)(?=item \[\d+\]:|\Z)', re.S)


def parse_mfa_textgrid(path: Path):
    """MFA 출력(long TextGrid)에서 (duration, {tier: [(b,e,text)]}) 추출."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"xmax = ([\d.eE+-]+)", text)
    if not m:
        return None, {}
    dur = float(m.group(1))
    tiers = {}
    for tm in TIER_RE.finditer(text):
        name, body = tm.group(1), tm.group(2)
        tiers[name] = [(float(a), float(b), c.replace('""', '"'))
                       for a, b, c in IV_RE.findall(body)]
    return dur, tiers


def load_forms(year: str):
    forms = {}
    ydir = RAW / YEAR_DIRS[year]
    for fp in ydir.glob("*.csv"):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                forms[row["utt_id"]] = row["form"]
    return forms


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, choices=sorted(YEAR_DIRS))
    ap.add_argument("--limit-sessions", type=int, default=0)
    args = ap.parse_args()

    src_year = MFA_OUT / args.year
    if not src_year.exists():
        sys.exit(f"원천 없음: {src_year}")
    print(f"[{args.year}] form 로드...", flush=True)
    forms = load_forms(args.year)
    print(f"  {len(forms):,}개", flush=True)

    sessions = sorted(d for d in src_year.iterdir() if d.is_dir())
    if args.limit_sessions:
        sessions = sessions[: args.limit_sessions]
    print(f"세션 {len(sessions):,}개 처리 시작", flush=True)

    made = skipped = failed = 0
    t0 = time.time()
    for si, sdir in enumerate(sessions, 1):
        out_dir = OUT / args.year / sdir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for tg in sdir.glob("*.TextGrid"):
            out_path = out_dir / tg.name
            if out_path.exists():
                skipped += 1
                continue
            try:
                dur, tiers = parse_mfa_textgrid(tg)
                words = tiers.get("words", [])
                phones = tiers.get("phones", [])
                if dur is None or not words or not phones:
                    failed += 1
                    continue
                utt_id = tg.stem
                write_textgrid(out_path, dur, words, phones,
                               forms.get(utt_id, ""))
                made += 1
            except Exception as e:
                failed += 1
                print(f"  !! {tg.name}: {type(e).__name__}: {e}", flush=True)
        if si % 100 == 0:
            rate = made / (time.time() - t0) if made else 0
            print(f"  세션 {si:,}/{len(sessions):,} (생성 {made:,}, "
                  f"{rate:.0f}/s)", flush=True)
    print(f"완료[{args.year}]: 생성 {made:,} / 건너뜀 {skipped:,} / 실패 {failed:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""A3b: 의미별 빈도표 — 02_sense_annotated(의미번호 레이어) 기반.

(형태소, 태그, 의미번호) 단위 코퍼스 사용빈도 + 부여 방법(method) 집계.
LS 의미별 빈도(08_ALL_morpheme_freq.csv)와 비교 컬럼 포함.
※ 보완 패스(supplement_sense_layer.py) 완료 후 실행할 것.

출력: 03_freq_dictionaries/sense_freq_dictionary.csv
실행: python build_sense_freq.py [--year 2020]
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"D:\10_LAYERS")
SENSE_DIR = BASE / "02_sense_annotated"
OUT_DIR = BASE / "03_freq_dictionaries"
LS_FREQ = Path(r"D:\00_RAW\reference\02_NIKL_LS\08_ALL_morpheme_freq.csv")
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_ls():
    t = defaultdict(lambda: [0, 0])  # (word, pos, sense) -> [SXLS, ALL]
    with open(LS_FREQ, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w, p, s = r["word"], r["pos"], r["sense_id"]
            if not w or w == "[]" or not s:
                continue
            try:
                freq = int(r["freq"])
            except ValueError:
                continue
            e = t[(w, p, s)]
            e[1] += freq
            if r.get("corpus_type") == "SXLS":
                e[0] += freq
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year")
    args = ap.parse_args()

    counts = defaultdict(lambda: [0] * len(YEARS))  # (m,t,sense,method)->년도별
    conf = {}
    n_rows = 0
    for ydir in sorted(SENSE_DIR.iterdir()):
        if not ydir.is_dir() or (args.year and args.year not in ydir.name):
            continue
        m = re.search(r"(20\d\d)", ydir.name)
        if not m:
            continue
        yi = YEARS.index(m.group(1))
        files = sorted(p for p in ydir.glob("*.csv") if not p.name.startswith("_"))
        print(f"[{ydir.name}] {len(files)}개 파일 집계...", flush=True)
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    method = r["method"]
                    key = (r["morph"], r["tag"], r["sense_id"], method)
                    counts[key][yi] += 1
                    n_rows += 1
                    if r.get("confidence"):
                        conf[key] = r["confidence"]

    print("LS 비교 빈도 로드...", flush=True)
    ls = load_ls()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "sense_freq_dictionary.csv"
    rows = sorted(counts.items(), key=lambda kv: -sum(kv[1]))
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["morph", "tag", "sense_id", "method", "confidence"]
                   + [f"freq_{y}" for y in YEARS]
                   + ["freq_total", "freq_LS_spoken", "freq_LS_all"])
        for (mo, tg, s, me), per_year in rows:
            ls_e = ls.get((mo, tg, s), [0, 0]) if s else [0, 0]
            w.writerow([mo, tg, s, me, conf.get((mo, tg, s, me), "")]
                       + per_year + [sum(per_year), ls_e[0], ls_e[1]])

    print(f"완료: 토큰 {n_rows:,}개 → 고유 (형태소,태그,의미) {len(rows):,}행")
    print(f"출력: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

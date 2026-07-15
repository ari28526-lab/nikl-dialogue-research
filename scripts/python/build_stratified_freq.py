"""A5: 사회언어 층화 빈도사전 — 성별 x 연령대 x 사용역별 형태소 빈도.

- 사용역(category)은 표기 변이(공백)를 정규화: '사적-일상대화' 등
- 각 층의 raw 빈도 + per-million(층 내 토큰 규모 정규화)
- 분산도: (형태소,태그)별 출현 문서 수 n_docs (contextual diversity)
- RAM 대비 2단계: --stage count --year YYYY (연도별) -> --stage merge

출력: 03_freq_dictionaries/
  morph_freq_stratified.csv  (long: morph, tag, dim, stratum, freq, per_million)
  _strata_totals.csv         (층별 토큰 합계)
  morph_dispersion.csv       (morph, tag, n_docs)
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"D:\10_LAYERS")
RAW_DIR = BASE / "01_bareun_raw"
META = BASE / "04_metadata_index" / "file_meta.csv"
OUT_DIR = BASE / "03_freq_dictionaries"
PART = OUT_DIR / "_partials_strat"
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm_register(cat: str) -> str:
    """'구어 > 사적 대화 > 일상 대화' -> '사적-일상대화'"""
    parts = [p.replace(" ", "") for p in cat.split(">")]
    if len(parts) >= 3:
        return parts[1].replace("대화", "") + "-" + parts[2]
    return cat.replace(" ", "") or "미상"


def load_meta():
    """file_id -> register(정규화)"""
    reg = {}
    with open(META, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            reg[r["file_id"]] = norm_register(r["category"])
    return reg


def load_speakers(ydir: Path):
    """speaker_id -> (sex, age)"""
    spk = {}
    fp = ydir / "_speakers.csv"
    if fp.exists():
        with open(fp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                spk[r["id"]] = (r.get("sex", "") or "미상",
                                r.get("age", "") or "미상")
    return spk


def iter_morphs(tagged: str):
    for tok in tagged.split(" "):
        for unit in tok.split("+"):
            mo, _, tg = unit.rpartition("/")
            if mo:
                yield mo, tg


def stage_count(year: str, reg_map):
    PART.mkdir(parents=True, exist_ok=True)
    for ydir in sorted(RAW_DIR.iterdir()):
        if not ydir.is_dir():
            continue
        m = re.search(r"(20\d\d)", ydir.name)
        if not m or m.group(1) != year:
            continue
        spk_map = load_speakers(ydir)
        counts = Counter()      # (mo, tg, dim, stratum) -> freq
        disp = Counter()        # (mo, tg) -> n_docs (파일=문서 단위)
        files = sorted(p for p in ydir.glob("*.csv") if not p.name.startswith("_"))
        print(f"[{ydir.name}] {len(files)}파일...", flush=True)
        for k, fp in enumerate(files, 1):
            register = reg_map.get(fp.stem, "미상")
            seen_in_doc = set()
            with open(fp, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    sex, age = spk_map.get(row["speaker_id"], ("미상", "미상"))
                    for mo, tg in iter_morphs(row["tagged"]):
                        counts[(mo, tg, "reg", register)] += 1
                        counts[(mo, tg, "sex", sex)] += 1
                        counts[(mo, tg, "age", age)] += 1
                        counts[(mo, tg, "sexage", f"{sex}|{age}")] += 1
                        if (mo, tg) not in seen_in_doc:
                            seen_in_doc.add((mo, tg))
                            disp[(mo, tg)] += 1
            if k % 500 == 0:
                print(f"  {k}/{len(files)}", flush=True)
        with open(PART / f"strat_{year}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for (mo, tg, dim, st), c in counts.items():
                w.writerow([mo, tg, dim, st, c])
        with open(PART / f"disp_{year}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for (mo, tg), c in disp.items():
                w.writerow([mo, tg, c])
        print(f"{year} 완료: 층화 항목 {len(counts):,}, 형태소 {len(disp):,}")


def stage_merge():
    counts = defaultdict(int)
    disp = defaultdict(int)
    for y in YEARS:
        sf = PART / f"strat_{y}.csv"
        if not sf.exists():
            print(f"  [경고] {y} 중간 파일 없음 — 건너뜀")
            continue
        with open(sf, encoding="utf-8") as f:
            for mo, tg, dim, st, c in csv.reader(f):
                counts[(mo, tg, dim, st)] += int(c)
        with open(PART / f"disp_{y}.csv", encoding="utf-8") as f:
            for mo, tg, c in csv.reader(f):
                disp[(mo, tg)] += int(c)
        print(f"  {y} 병합", flush=True)

    totals = defaultdict(int)  # (dim, stratum) -> 토큰 합
    for (mo, tg, dim, st), c in counts.items():
        totals[(dim, st)] += c

    with open(OUT_DIR / "morph_freq_stratified.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["morph", "tag", "dim", "stratum", "freq", "per_million"])
        for (mo, tg, dim, st), c in sorted(counts.items(),
                                           key=lambda kv: -kv[1]):
            pm = c / totals[(dim, st)] * 1_000_000
            w.writerow([mo, tg, dim, st, c, f"{pm:.2f}"])

    with open(OUT_DIR / "_strata_totals.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["dim", "stratum", "tokens"])
        for (dim, st), c in sorted(totals.items()):
            w.writerow([dim, st, c])

    with open(OUT_DIR / "morph_dispersion.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["morph", "tag", "n_docs"])
        for (mo, tg), c in sorted(disp.items(), key=lambda kv: -kv[1]):
            w.writerow([mo, tg, c])

    print(f"완료: 층화 행 {len(counts):,} / 층 {len(totals)}개 / "
          f"형태소 {len(disp):,}")
    for (dim, st), c in sorted(totals.items()):
        print(f"  [{dim}] {st}: {c:,}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["count", "merge"], required=True)
    ap.add_argument("--year")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.stage == "count":
        if not args.year:
            sys.exit("--stage count에는 --year 필요")
        stage_count(args.year, load_meta())
    else:
        stage_merge()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

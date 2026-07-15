"""전수 커버리지 인벤토리: 발화별 wav·TextGrid 유무 (2020-2025).

연도별로 01_bareun_raw의 발화 목록을 기준으로 wav(03_wav)와
TextGrid(06_textgrid_merged) 존재 여부를 전수 대조.
출력: D:/10_LAYERS/05_audio_index/coverage_{연도}.csv + _summary.txt
※ 디스크 전수 열거 — 밤새 실행 권장. 연도 단위 재개 가능(완료 연도 건너뜀).
실행: python coverage_inventory.py
"""
import csv
import re
import sys
import time
from pathlib import Path

RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
WAV = Path(r"D:\20_AUDIO\03_wav\individual")
TG = Path(r"D:\20_AUDIO\06_textgrid_merged")
OUT = Path(r"D:\10_LAYERS\05_audio_index")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def utt_ids_for_year(ydir: Path):
    for fp in sorted(ydir.glob("*.csv")):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                yield row["utt_id"]


def scan_names(root: Path, suffix: str):
    """폴더 트리에서 해당 확장자 파일의 stem 집합."""
    names = set()
    if not root.exists():
        return names
    for p in root.rglob(f"*{suffix}"):
        names.add(p.name[: -len(suffix)])
    return names


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for ydir in sorted(RAW.iterdir()):
        if not ydir.is_dir():
            continue
        m = re.search(r"(20\d\d)", ydir.name)
        if not m:
            continue
        year = m.group(1)
        out_csv = OUT / f"coverage_{year}.csv"
        if out_csv.exists():
            print(f"[{year}] 이미 완료 — 건너뜀", flush=True)
            continue
        t0 = time.time()
        print(f"[{year}] wav 목록 스캔...", flush=True)
        wavs = scan_names(WAV / year, ".wav")
        print(f"  wav {len(wavs):,}개 ({time.time()-t0:.0f}s). "
              f"TextGrid 스캔...", flush=True)
        tgs = scan_names(TG / year, ".TextGrid")
        print(f"  TextGrid {len(tgs):,}개 ({time.time()-t0:.0f}s). 대조...",
              flush=True)
        n = both = w_only = t_only = neither = 0
        tmp = out_csv.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["utt_id", "has_wav", "has_textgrid"])
            for uid in utt_ids_for_year(ydir):
                hw, ht = uid in wavs, uid in tgs
                w.writerow([uid, int(hw), int(ht)])
                n += 1
                both += hw and ht
                w_only += hw and not ht
                t_only += ht and not hw
                neither += (not hw) and (not ht)
        tmp.replace(out_csv)
        line = (f"[{year}] 발화 {n:,} | wav+TG {both:,} ({both/n*100:.2f}%) | "
                f"wav만 {w_only:,} | TG만 {t_only:,} | 둘다없음 {neither:,} | "
                f"{(time.time()-t0)/60:.0f}분")
        print(line, flush=True)
        summary.append(line)
        wavs.clear()
        tgs.clear()
    (OUT / "_coverage_summary.txt").write_text("\n".join(summary),
                                               encoding="utf-8")
    print("전체 완료 → 05_audio_index/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

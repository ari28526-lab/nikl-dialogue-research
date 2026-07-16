r"""미회수 발화의 원본 PCM 실측 — 재추출 가능/불가 확정 (전 연도).

대상: 재정렬 후에도 여전히 미회수인 발화(coverage has_wav=1 & has_textgrid=0,
      alignment_quality_realign 에 없음) 전부.
방법: 원본 PCM `…\{year}_pcm\{utt_id}.pcm` 를 직접 stat(열거 없음).
      PCM 길이 = 바이트/32000 (16kHz·16bit·mono).
분류:
  - 원본짧음(<0.3s): 원본 자체가 토막 → 재추출해도 못 살림(회수 불가 확정)
  - 원본정상(>=0.3s): 원본은 온전 → wav/정렬 문제 → 재추출/재정렬로 회수 여지
  - PCM없음: 평면 경로에 없음 → 별도 확인 필요
출력: 05_audio_index/source_pcm_check.csv + 화면 연도별 요약

실행: python check_source_pcm.py
"""
import csv
import sys
from pathlib import Path

COV = Path(r"D:\10_LAYERS\05_audio_index")
PCM_ROOT = Path(r"D:\00_RAW\dialogue_audio\modu_corpus_dialogue_audio")
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
BYTES_PER_SEC = 16000 * 2  # 16kHz, 16bit mono
SHORT_SEC = 0.3
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def recovered(year):
    fp = COV / f"alignment_quality_realign_{year}.csv"
    if not fp.exists():
        return set()
    with open(fp, encoding="utf-8-sig") as f:
        return {r["file"] for r in csv.DictReader(f)}


def still_missing(year):
    rec = recovered(year)
    out = []
    with open(COV / f"coverage_{year}.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r["has_wav"] == "1" and r["has_textgrid"] == "0"
                    and r["utt_id"] not in rec):
                out.append(r["utt_id"])
    return out


def main() -> int:
    out_rows = []
    print(f"{'연도':<6}{'미회수':>8}{'원본짧음':>9}{'원본정상':>9}{'PCM없음':>9}")
    print("-" * 42)
    g = [0, 0, 0, 0]
    for year in YEARS:
        pcm_dir = PCM_ROOT / f"{year}_pcm"
        miss = still_missing(year)
        c_short = c_full = c_none = 0
        for u in miss:
            p = pcm_dir / f"{u}.pcm"
            try:
                sz = p.stat().st_size
            except OSError:
                c_none += 1
                out_rows.append([year, u, "", "PCM없음"])
                continue
            sec = sz / BYTES_PER_SEC
            if sec < SHORT_SEC:
                c_short += 1
                cat = "원본짧음"
            else:
                c_full += 1
                cat = "원본정상"
            out_rows.append([year, u, f"{sec:.3f}", cat])
        print(f"{year:<6}{len(miss):>8}{c_short:>9}{c_full:>9}{c_none:>9}")
        g[0] += len(miss); g[1] += c_short; g[2] += c_full; g[3] += c_none
    print("-" * 42)
    print(f"{'합계':<6}{g[0]:>8}{g[1]:>9}{g[2]:>9}{g[3]:>9}")

    out_csv = COV / "source_pcm_check.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["year", "utt_id", "pcm_sec", "category"])
        w.writerows(out_rows)
    print(f"\n원본짧음 = 재추출해도 회수 불가(원본 토막) 확정")
    print(f"원본정상 = 원본 온전 → 재추출/재정렬 여지")
    print(f"→ 상세: {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

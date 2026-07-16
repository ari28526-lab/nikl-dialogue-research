"""재정렬 회수 요약: 연도별 원래 실패 vs 회수 vs 남은 미회수.

원래 실패: coverage_{year}.csv 의 has_wav=1 & has_textgrid=0 수.
회수:      alignment_quality_realign_{year}.csv 행 수 (정렬 성공분).
남은:      실패 - 회수 (여전히 TextGrid 없는 발화).
출력: 화면 표 + 05_audio_index/realign_summary.txt

실행: python realign_summary.py
"""
import csv
import sys
from pathlib import Path

COV = Path(r"D:\10_LAYERS\05_audio_index")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def count_failed(year: str) -> int:
    fp = COV / f"coverage_{year}.csv"
    if not fp.exists():
        return -1
    n = 0
    with open(fp, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["has_wav"] == "1" and r["has_textgrid"] == "0":
                n += 1
    return n


def count_recovered(year: str) -> int:
    fp = COV / f"alignment_quality_realign_{year}.csv"
    if not fp.exists():
        return -1
    with open(fp, encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # 헤더 제외


def main() -> int:
    lines = []
    lines.append(f"{'연도':<6}{'원래실패':>10}{'회수':>10}{'남은미회수':>12}{'회수율':>9}")
    lines.append("-" * 47)
    t_fail = t_rec = 0
    for year in ["2020", "2021", "2022", "2023", "2024", "2025"]:
        fail = count_failed(year)
        rec = count_recovered(year)
        if fail < 0:
            lines.append(f"{year:<6}{'커버리지 없음':>20}")
            continue
        if rec < 0:
            lines.append(f"{year:<6}{fail:>10,}{'(미실행)':>10}")
            continue
        left = fail - rec
        rate = rec / fail * 100 if fail else 0
        lines.append(f"{year:<6}{fail:>10,}{rec:>10,}{left:>12,}{rate:>8.1f}%")
        t_fail += fail
        t_rec += rec
    lines.append("-" * 47)
    if t_fail:
        lines.append(f"{'합계':<6}{t_fail:>10,}{t_rec:>10,}{t_fail-t_rec:>12,}"
                     f"{t_rec/t_fail*100:>8.1f}%")
    text = "\n".join(lines)
    print(text)
    (COV / "realign_summary.txt").write_text(text, encoding="utf-8")
    print(f"\n→ 저장: {COV / 'realign_summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

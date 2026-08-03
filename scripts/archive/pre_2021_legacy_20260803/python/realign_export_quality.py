"""재정렬 MFA 작업DB → 정렬 품질통계 CSV (사후 필터링용).

MFA 3.4는 align 완료 후 품질통계를 작업DB(utterance 테이블)에만 기록하고
CSV로 자동 내보내지 않는다. 이 스크립트가 DB에서 뽑아 기존
alignment_quality_2025.csv 와 동일 스키마로 저장한다.
DB 위치: {MFA_ROOT}/{year}/{year}.db  (코퍼스 폴더 leaf명 = 연도)

컬럼: file, begin, end, speaker, overall_log_likelihood,
      speech_log_likelihood, phone_duration_deviation, snr
※ alignment_log_likelihood 가 NULL = 정렬 실패(회수 안 됨) → 제외.
출력: 05_audio_index/alignment_quality_realign_{year}.csv

실행: python realign_export_quality.py --year 2023
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

MFA_ROOT = Path(r"C:\Users\ari30\Documents\MFA")
OUT = Path(r"D:\10_LAYERS\05_audio_index")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    args = ap.parse_args()

    db = MFA_ROOT / args.year / f"{args.year}.db"
    if not db.exists():
        sys.exit(f"MFA 작업DB 없음: {db}\n"
                 f"  (align 후 --clean 하기 전에 실행해야 함)")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT f.name, u.begin, u.end, s.name, "
        "u.alignment_log_likelihood, u.speech_log_likelihood, "
        "u.duration_deviation, u.snr "
        "FROM utterance u "
        "JOIN file f ON u.file_id = f.id "
        "LEFT JOIN speaker s ON u.speaker_id = s.id "
        "WHERE u.alignment_log_likelihood IS NOT NULL "
        "ORDER BY f.name").fetchall()
    con.close()

    out_csv = OUT / f"alignment_quality_realign_{args.year}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "begin", "end", "speaker",
                    "overall_log_likelihood", "speech_log_likelihood",
                    "phone_duration_deviation", "snr"])
        w.writerows(rows)
    print(f"[{args.year}] 품질통계 {len(rows):,}발화 → {out_csv.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

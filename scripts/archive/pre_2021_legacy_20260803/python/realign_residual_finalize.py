r"""잔여 재시도(빔 300/1000) 산출 마무리: 표준 3-tier 병합 + 품질 CSV 추가.

입력: D:\mfa_realign\residual_out\{year}\{session}\{utt}.TextGrid (재시도 회수분)
      + MFA 작업DB Documents\MFA\{year}\{year}.db (현재 잔여 정렬 결과)
동작: (1) TG → 표준 3-tier → 06_textgrid_merged (기존 미덮어씀)
      (2) 회수분 품질행을 alignment_quality_realign_{year}.csv 에 append(중복 제거)

실행: python realign_residual_finalize.py --year all
"""
import argparse
import csv
import sqlite3
import sys
from pathlib import Path

from merge_textgrid_v2 import write_textgrid
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid, YEAR_DIRS

RESID_OUT = Path(r"D:\mfa_realign\residual_out")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
MERGED = Path(r"D:\20_AUDIO\06_textgrid_merged")
MFA_ROOT = Path(r"C:\Users\ari30\Documents\MFA")
COV = Path(r"D:\10_LAYERS\05_audio_index")
YEAR_DIRS = {**YEAR_DIRS, "2025": "NIKL_DIALOGUE_2025_v1.0"}
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_forms(year, sessions):
    forms = {}
    ydir = RAW / YEAR_DIRS[year]
    for s in sessions:
        fp = ydir / f"{s}.csv"
        if fp.exists():
            with open(fp, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    forms[row["utt_id"]] = row["form"]
    return forms


def merge_tgs(year) -> int:
    src = RESID_OUT / year
    if not src.exists():
        return 0
    sessions = [d.name for d in src.iterdir() if d.is_dir()]
    forms = load_forms(year, set(sessions))
    made = 0
    for sname in sessions:
        out_dir = MERGED / year / sname
        out_dir.mkdir(parents=True, exist_ok=True)
        for tg in (src / sname).glob("*.TextGrid"):
            out_path = out_dir / tg.name
            if out_path.exists():
                continue
            dur, tiers = parse_mfa_textgrid(tg)
            w, p = tiers.get("words", []), tiers.get("phones", [])
            if dur is None or not w or not p:
                continue
            write_textgrid(out_path, dur, w, p, forms.get(tg.stem, ""))
            made += 1
    return made


def append_quality(year) -> int:
    db = MFA_ROOT / year / f"{year}.db"
    if not db.exists():
        return 0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=120)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT f.name, u.begin, u.end, s.name, u.alignment_log_likelihood, "
        "u.speech_log_likelihood, u.duration_deviation, u.snr "
        "FROM utterance u JOIN file f ON u.file_id=f.id "
        "LEFT JOIN speaker s ON u.speaker_id=s.id "
        "WHERE u.alignment_log_likelihood IS NOT NULL").fetchall()
    con.close()
    if not rows:
        return 0
    qf = COV / f"alignment_quality_realign_{year}.csv"
    existing = set()
    if qf.exists():
        with open(qf, encoding="utf-8-sig") as f:
            existing = {r["file"] for r in csv.DictReader(f)}
    new = [r for r in rows if r[0] not in existing]
    write_header = not qf.exists()
    with open(qf, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["file", "begin", "end", "speaker",
                        "overall_log_likelihood", "speech_log_likelihood",
                        "phone_duration_deviation", "snr"])
        w.writerows(new)
    return len(new)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True)
    args = ap.parse_args()
    years = YEARS if args.year == "all" else [args.year]
    for y in years:
        m = merge_tgs(y)
        q = append_quality(y)
        print(f"[{y}] 병합 {m} / 품질추가 {q}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

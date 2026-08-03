r"""잔여(정상 wav인데 미회수) 발화만 모아 재시도용 코퍼스 구성.

1차 재정렬(빔 100/400) 후에도 남은 미회수 중, wav가 정상(>=0.3s)인 것만
추린다. 깨진 wav(<0.3s, 재추출 필요)와 빈 lab은 제외.
소스: 기존 재정렬 코퍼스 D:\mfa_realign\corpus\{year}\{session}\ (wav+lab 존재)
출력: D:\mfa_realign\residual\{year}\{session}\ (wav 하드링크 + lab 복사)

실행: python realign_residual_build.py --year all
"""
import argparse
import csv
import os
import shutil
import sys
import wave
from pathlib import Path

COV = Path(r"D:\10_LAYERS\05_audio_index")
CORP = Path(r"D:\mfa_realign\corpus")
RESID = Path(r"D:\mfa_realign\residual")
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def recovered_set(year: str) -> set:
    fp = COV / f"alignment_quality_realign_{year}.csv"
    if not fp.exists():
        return set()
    with open(fp, encoding="utf-8-sig") as f:
        return {r["file"] for r in csv.DictReader(f)}


def still_missing(year: str) -> list:
    rec = recovered_set(year)
    out = []
    with open(COV / f"coverage_{year}.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r["has_wav"] == "1" and r["has_textgrid"] == "0"
                    and r["utt_id"] not in rec):
                out.append(r["utt_id"])
    return out


def wav_ok(path: Path) -> bool:
    """정상 음성(>=0.3s)인지."""
    try:
        with wave.open(str(path)) as wf:
            return wf.getnframes() / wf.getframerate() >= 0.3
    except Exception:
        return False


def build_year(year: str) -> None:
    miss = still_missing(year)
    made = short = nowav = 0
    for u in miss:
        s = u.split(".")[0]
        src_wav = CORP / year / s / f"{u}.wav"
        src_lab = CORP / year / s / f"{u}.lab"
        if not src_wav.exists() or not src_lab.exists():
            nowav += 1
            continue
        if not wav_ok(src_wav):
            short += 1  # 깨진 wav — 재추출 대상, 여기선 제외
            continue
        out_sess = RESID / year / s
        out_sess.mkdir(parents=True, exist_ok=True)
        dst_wav = out_sess / f"{u}.wav"
        if not dst_wav.exists():
            try:
                os.link(src_wav, dst_wav)
            except OSError:
                shutil.copy2(src_wav, dst_wav)
        shutil.copy2(src_lab, out_sess / f"{u}.lab")
        made += 1
    print(f"[{year}] 잔여 정상wav {made} 구성 / 깨진wav 제외 {short} / "
          f"코퍼스없음 {nowav}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    args = ap.parse_args()
    years = YEARS if args.year == "all" else [args.year]
    for y in years:
        build_year(y)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

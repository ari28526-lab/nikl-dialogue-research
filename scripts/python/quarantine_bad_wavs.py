"""깨진(0바이트/헤더 미만) wav 격리 — MFA 로딩 전체 실패 방지 (2026-07-18).

배경: MFA 3.4는 코퍼스 로딩 워커가 soundfile로 못 여는 wav(예: 0바이트)를
만나면 그 파일만 건너뛰지 않고 **로딩 말미에 전체를 실패**시킨다
(acoustic_corpus.py error_dict → raise). 7/17·7/18 두 차례 본실행이
`SDRW2000000521.1.1.175.wav`(0바이트, 2026-01 변환 산물)로 죽었음.

동작: 연도 wav 폴더(평면/세션 하위폴더 모두)를 훑어 크기 < min-bytes(기본
44=WAV 헤더 최소)인 .wav를 D:\\mfa_eojeol\\quarantine\\{year}\\로 이동(짝 .lab
동반). 기본은 dry-run(목록만), --apply 시 실제 이동. CSV 기록 남김.
스캔은 디렉토리 열거만으로 크기를 얻으므로(Windows scandir) 추가 I/O 없음.

실행: python quarantine_bad_wavs.py --year 2020 [--apply]
      (all = 6개년 전부. 격리 복원은 CSV의 원경로로 되돌리면 됨.)
"""
import argparse
import csv
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402

QUARANTINE_ROOT = Path(r"D:\mfa_eojeol\quarantine")
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def scan_year(year: str, min_bytes: int, apply: bool) -> int:
    root = P("wav") / "individual" / year
    if not root.is_dir():
        print(f"[{year}] 폴더 없음: {root} — 건너뜀", flush=True)
        return 0
    qdir = QUARANTINE_ROOT / year
    bad = []          # (wav Path, size)
    seen = 0
    t0 = time.time()
    for dirpath, _dirnames, _filenames in os.walk(root):
        # os.walk가 내부적으로 scandir을 쓰지만 크기는 다시 stat이 필요하므로
        # 폴더별 scandir 1회로 크기까지 한 번에 얻는다 (USB 왕복 최소화).
        with os.scandir(dirpath) as it:
            for e in it:
                if not e.is_file() or not e.name.endswith(".wav"):
                    continue
                seen += 1
                if e.stat().st_size < min_bytes:
                    bad.append((Path(e.path), e.stat().st_size))
                if seen % 200_000 == 0:
                    el = time.time() - t0
                    print(f"  [{year}] {seen:,}개 확인 ({seen/el:,.0f}개/s) · "
                          f"불량 {len(bad)}건", flush=True)
    print(f"[{year}] 스캔 완료: wav {seen:,}개 중 불량(<{min_bytes}B) "
          f"{len(bad)}건 ({time.time()-t0:,.0f}초)", flush=True)
    for p, size in bad:
        print(f"  - {p.relative_to(root)} ({size}B)", flush=True)
    if not bad:
        return 0
    if not apply:
        print(f"[{year}] dry-run — 이동하려면 --apply", flush=True)
        return len(bad)
    qdir.mkdir(parents=True, exist_ok=True)
    log_path = qdir / "quarantine_log.csv"
    new_log = not log_path.exists()
    with open(log_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_log:
            w.writerow(["moved_at", "name", "size_bytes", "orig_path", "lab_moved"])
        for p, size in bad:
            lab = p.with_suffix(".lab")
            lab_moved = lab.exists()
            shutil.move(str(p), str(qdir / p.name))
            if lab_moved:
                shutil.move(str(lab), str(qdir / lab.name))
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), p.name, size,
                        str(p), lab_moved])
    print(f"[{year}] {len(bad)}건 격리 완료 → {qdir} (기록: {log_path})",
          flush=True)
    return len(bad)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    ap.add_argument("--min-bytes", type=int, default=44,
                    help="이 크기 미만이면 불량 (기본 44=WAV 헤더 최소)")
    ap.add_argument("--apply", action="store_true", help="실제 이동 (기본 dry-run)")
    args = ap.parse_args()
    years = YEARS if args.year == "all" else [args.year]
    total = 0
    for y in years:
        if y not in YEARS:
            sys.exit(f"알 수 없는 연도: {y}")
        total += scan_year(y, args.min_bytes, args.apply)
    print(f"총 불량 {total}건" + ("" if args.apply else " (dry-run)"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

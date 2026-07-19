"""평면 wav 연도 → 세션 하위폴더 재구성 (2026-07-19, SSD 이전과 함께 실행).

배경(★1화자 사고): MFA는 화자를 폴더 구조로 추론한다("하위폴더 1개=화자 1명").
평면 연도(2020 실측: 87만 파일 한 폴더)는 연도 전체가 화자 1명으로 잡혀
① SAT·CMVN이 무력화(경계 정밀도 하락 — SAT off를 기각한 결정과 모순)
② 병렬이 num_jobs와 무관하게 1job으로 강등(4배 느림)됐다 (7/19 발견, 실행 중단).
해법: 우회 옵션(--speaker_characters) 대신 **물리 구조를 세션 폴더로 통일** —
06_textgrid_merged(6개년 모두 세션 구조 실측)와 레이아웃이 일치하게 되고,
파일럿·2023과 같은 조건(세션=화자)이 되며, 연도별 접두사 길이 차이도 무관해짐.

동작: {root}/{year} 바로 아래의 *.wav/*.lab을 세션(파일명 첫 '.' 앞)별
하위폴더로 이동. 같은 볼륨 내 rename이라 SSD에서 수 분. 이미 세션 폴더인
연도(2023 등)는 루트에 파일이 없으므로 자동으로 할 일 없음. 재개 가능
(중단 후 재실행하면 남은 루트 파일만 처리). 마커 등 다른 파일은 안 건드림.

실행(SSD 복사 후, SSD 루트에서):
  python restructure_wav_sessions.py --root E:\\20_AUDIO\\03_wav\\individual --year all --apply
  (--apply 없으면 dry-run: 이동 대상 집계만 출력)
검증: 완료 후 각 연도 루트에 wav/lab이 0개인지, 세션 폴더 수를 출력.
"""
import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def restructure_year(ydir: Path, apply: bool) -> tuple:
    """연도 루트의 wav/lab을 세션 폴더로 이동. (이동수, 세션수, 루트잔여) 반환."""
    per_session = defaultdict(list)   # 세션 → 파일명 목록
    other_root_files = 0
    with os.scandir(ydir) as it:
        for e in it:
            if not e.is_file():
                continue
            if e.name.endswith((".wav", ".lab")):
                sess = e.name.split(".")[0]
                if sess and sess != e.name:      # '.' 없는 이상 파일명 방어
                    per_session[sess].append(e.name)
                else:
                    other_root_files += 1
            # 마커(.eojeol_labs_v2 등) 등 기타 루트 파일은 그대로 둠
    nfiles = sum(len(v) for v in per_session.values())
    if nfiles == 0:
        return 0, 0, 0
    if not apply:
        return nfiles, len(per_session), 0
    moved = 0
    t0 = time.time()
    for sess, names in per_session.items():
        sdir = ydir / sess
        sdir.mkdir(exist_ok=True)
        for n in names:
            os.replace(ydir / n, sdir / n)   # 같은 볼륨: rename, 원자적
            moved += 1
            if moved % 100_000 == 0:
                el = time.time() - t0
                print(f"    {moved:,}/{nfiles:,} 이동 ({moved/el:,.0f}개/s)",
                      flush=True)
    # 검증: 루트에 wav/lab 잔여 0이어야 함
    remain = sum(1 for e in os.scandir(ydir)
                 if e.is_file() and e.name.endswith((".wav", ".lab")))
    return moved, len(per_session), remain


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help=r"individual 루트 (예: E:\20_AUDIO\03_wav\individual)")
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    ap.add_argument("--apply", action="store_true", help="실제 이동 (기본 dry-run)")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"루트 없음: {root}")
    years = YEARS if args.year == "all" else [args.year]
    bad = False
    for y in years:
        if y not in YEARS:
            sys.exit(f"알 수 없는 연도: {y}")
        ydir = root / y
        if not ydir.is_dir():
            print(f"[{y}] 폴더 없음 — 건너뜀", flush=True)
            continue
        print(f"[{y}] 스캔 중...", flush=True)
        moved, nsess, remain = restructure_year(ydir, args.apply)
        if moved == 0:
            print(f"[{y}] 루트에 wav/lab 없음 — 이미 세션 구조(또는 빈 연도)",
                  flush=True)
        elif not args.apply:
            print(f"[{y}] dry-run: 세션 {nsess:,}개로 {moved:,}개 이동 예정",
                  flush=True)
        else:
            status = "OK" if remain == 0 else f"!! 루트 잔여 {remain}개"
            print(f"[{y}] 세션 {nsess:,}개로 {moved:,}개 이동 완료 — {status}",
                  flush=True)
            if remain:
                bad = True
    if not args.apply:
        print("dry-run 끝 — 실제 이동은 --apply", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

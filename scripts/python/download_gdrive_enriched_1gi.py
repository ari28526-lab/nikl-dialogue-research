# -*- coding: utf-8 -*-
"""1기 enriched CSV(Google Drive) → SSD 백업 다운로드 (재개 가능)

대상  : 01_nikl_dialogue_enriched.csv (4,957,188,915 bytes, 2020-2024 발화단위
        발음·로마자 포함 — 1기 산출물)
원본  : Drive `DATA_2026/00_raw_data/04_nikl_dialogue/02_csv/` (2026-02-24)
        ※ `NIKL_dialogue/`(2026-05-11)에 동일 크기 사본 있음 — 한 부만 백업
목적지: D:\\90_ARCHIVE\\1기_enriched\\  (기본값)
        - 90_ARCHIVE 선정 이유: 1기 보존물(불변 참고 자료).
          00_RAW은 NIKL 배포 원본 전용, 10_LAYERS는 현행(2기) 레이어이므로 부적합.

준비 (1회):
  1) pip install gdown
  2) Drive 웹에서 파일 우클릭 → 공유 → '링크가 있는 모든 사용자: 뷰어'로 임시 변경
     (개인 파일이라 공유 없이는 gdown이 접근 불가. 다운로드 완료 후 '제한됨'으로 복원)

실행:
  python scripts\\python\\download_gdrive_enriched_1gi.py
  # 중단돼도 같은 명령 재실행 → 이어받기(gdown --continue)

검증: 완료 후 파일 크기가 기대값과 일치하는지 자동 확인.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FILE_ID = "1i38JHkkbir_lY1NzLZY1V9TdKHXexEI0"  # 02_csv 폴더의 원본(2026-02-24)
EXPECTED_BYTES = 4_957_188_915
DEFAULT_DEST = Path(r"D:\90_ARCHIVE\1기_enriched\01_nikl_dialogue_enriched.csv")
MARGIN_BYTES = 1 * 1024**3  # 여유 1GB


def main() -> int:
    ap = argparse.ArgumentParser(description="1기 enriched CSV Drive→SSD 백업")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                    help=f"저장 경로 (기본 {DEFAULT_DEST})")
    args = ap.parse_args()
    dest: Path = args.dest

    # 0) 이미 완료?
    if dest.exists() and dest.stat().st_size == EXPECTED_BYTES:
        print(f"[완료] 이미 존재하고 크기 일치: {dest}")
        return 0

    # 1) 대상 드라이브 여유 공간 확인
    dest.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(dest.parent).free
    need = EXPECTED_BYTES + MARGIN_BYTES
    if free < need:
        print(f"[중단] 여유 공간 부족: 필요 {need/1e9:.1f}GB, 현재 {free/1e9:.1f}GB")
        return 1

    # 2) gdown 확인
    try:
        import gdown  # noqa: F401
    except ImportError:
        print("[중단] gdown 미설치 → 먼저:  pip install gdown")
        return 1

    # 3) 다운로드 (이어받기). gdown은 dest.part 파일로 진행 후 완료 시 개명.
    print(f"[시작] Drive {FILE_ID} → {dest}")
    print("       (중단 시 같은 명령 재실행하면 이어받습니다)")
    cmd = [sys.executable, "-m", "gdown", "--continue", "--id", FILE_ID,
           "-O", str(dest)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print("[실패] gdown 오류. 흔한 원인:")
        print("  - 파일이 '제한됨' 상태 → Drive에서 링크 공유(뷰어) 임시 설정 후 재시도")
        print("  - 네트워크 중단 → 같은 명령으로 이어받기 재시도")
        return proc.returncode

    # 4) 크기 검증
    size = dest.stat().st_size if dest.exists() else 0
    if size == EXPECTED_BYTES:
        print(f"[완료+검증] {dest} ({size:,} bytes = 기대값 일치)")
        print("→ Drive 파일 공유를 다시 '제한됨'으로 되돌리는 것 잊지 마세요.")
        return 0
    print(f"[경고] 크기 불일치: {size:,} / 기대 {EXPECTED_BYTES:,} — 재실행으로 이어받기 시도")
    return 1


if __name__ == "__main__":
    sys.exit(main())

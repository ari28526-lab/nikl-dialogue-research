"""인터넷 단절 중 저장된 오염 파일(빈 tagged 포함) 탐지·삭제.

삭제된 파일은 bareun_dialogue_full.py 재실행 시 자동으로 재분석된다.
사용: python repair_empty_tagged.py          (탐지+삭제)
      python repair_empty_tagged.py --dry    (탐지만, 삭제 안 함)
"""
import argparse
import csv
import sys
from pathlib import Path

RAW_DIR = Path(r"D:\10_LAYERS\01_bareun_raw")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def has_empty_tagged(fp: Path) -> bool:
    with open(fp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("form", "").strip() and not row.get("tagged", "").strip():
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="탐지만 하고 삭제 안 함")
    args = ap.parse_args()

    bad = []
    for ydir in sorted(RAW_DIR.iterdir()):
        if not ydir.is_dir():
            continue
        files = [p for p in ydir.glob("*.csv") if not p.name.startswith("_")]
        n_bad = 0
        for fp in files:
            if has_empty_tagged(fp):
                bad.append(fp)
                n_bad += 1
        print(f"[{ydir.name}] 검사 {len(files)}개, 오염 {n_bad}개", flush=True)

    # 미완성 .tmp 파일도 정리
    tmps = list(RAW_DIR.rglob("*.tmp"))
    print(f"\n오염 CSV {len(bad)}개, 잔여 .tmp {len(tmps)}개")
    for fp in bad[:20]:
        print(f"  {fp.parent.name}\\{fp.name}")
    if len(bad) > 20:
        print(f"  ... 외 {len(bad)-20}개")

    if args.dry:
        print("\n--dry 모드: 삭제하지 않음")
        return 0
    for fp in bad + tmps:
        fp.unlink()
    print(f"\n삭제 완료 → 재실행하면 해당 파일들만 다시 분석됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""D: 폴더 이행 마무리. Claude 앱 완전 종료 후 실행 (잠금 해제 목적):
    python "C:\\Users\\ari30\\Dropbox\\000_2026_summer_research\\scripts\\python\\finish_migration.py"
이미 옮겨진 항목은 건너뜀. 삭제 없음(이동만)."""
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOVES = [
    (r"D:\04_00_NIKL_DIALOGUE_MFA\00_source\modu_corpus_dialogue_audio",
     r"D:\00_RAW\dialogue_audio\modu_corpus_dialogue_audio"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\06_textgrid_merged",
     r"D:\20_AUDIO\06_textgrid_merged"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\02_csv",
     r"D:\90_ARCHIVE\04_00_02_csv_구식형태소"),
    (r"D:\04_00_NIKL_DIALOGUE_MFA\04_mfa_input",
     r"D:\90_ARCHIVE\04_00_04_mfa_input_구식"),
    (r"D:\00_이전시도_NIKL_DIALOGUE_csv",
     r"D:\90_ARCHIVE\00_이전시도_NIKL_DIALOGUE_csv"),
    (r"D:\temp", r"D:\90_ARCHIVE\root_temp"),
    (r"D:\tmp", r"D:\90_ARCHIVE\root_tmp"),
    (r"D:\기타", r"D:\90_ARCHIVE\root_기타"),
    (r"D:\transfer_corpus.py", r"D:\90_ARCHIVE\transfer_corpus.py"),
    (r"D:\transfer_with_zip.py", r"D:\90_ARCHIVE\transfer_with_zip.py"),
]


def main() -> int:
    ok = fail = skip = 0
    for src, dst in MOVES:
        s, d = Path(src), Path(dst)
        if not s.exists():
            print(f"건너뜀({'이미 완료' if d.exists() else '원본 없음'}): {d if d.exists() else s}")
            skip += 1
            continue
        if d.exists():
            print(f"!! 목적지 이미 존재, 수동 확인 필요: {d}")
            fail += 1
            continue
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(d))
            print(f"이동 완료: {s.name} -> {d}")
            ok += 1
        except Exception as e:
            print(f"!! 실패: {s} ({type(e).__name__}: {e})")
            fail += 1
    print(f"\n결과: 이동 {ok} / 건너뜀 {skip} / 실패 {fail}")
    if fail == 0:
        print("이행 완료! Claude를 다시 열고 이어서 작업하면 됩니다.")
    else:
        print("실패가 있으면 Claude 완전 종료 여부 확인 후 재실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

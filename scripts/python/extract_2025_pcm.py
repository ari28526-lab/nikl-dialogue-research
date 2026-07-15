"""2025 PCM 압축 해제 (진행 표시 포함, 중단 시 재실행하면 이어서 해제).

D:/20_AUDIO/00_source/NIKL_DIALOGUE_2025_v1.0_PCM.zip (59.6GB)
 -> 00_source/modu_corpus_dialogue_audio/2025_pcm/
"""
import sys
import zipfile
from pathlib import Path

ZIP = Path(r"D:\00_RAW\dialogue_audio\NIKL_DIALOGUE_2025_v1.0_PCM.zip")
DEST = Path(r"D:\00_RAW\dialogue_audio\modu_corpus_dialogue_audio\2025_pcm")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        total = len(names)
        print(f"항목 {total:,}개 해제 시작 → {DEST}", flush=True)
        done = skip = 0
        for i, name in enumerate(names, 1):
            info = z.getinfo(name)
            target = DEST / name
            # 재개 지원: 크기까지 같으면 건너뜀
            if not info.is_dir() and target.exists() \
                    and target.stat().st_size == info.file_size:
                skip += 1
            else:
                z.extract(name, DEST)
                done += 1
            if i % 200 == 0:
                print(f"  {i:,}/{total:,} (해제 {done:,}, 건너뜀 {skip:,})",
                      flush=True)
        print(f"완료: 해제 {done:,}, 건너뜀 {skip:,} / 총 {total:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

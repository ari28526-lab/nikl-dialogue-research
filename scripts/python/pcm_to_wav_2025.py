"""2025 PCM -> WAV 변환 (구 01_pcm_to_wav.py 로직 재사용, 새 구조 경로).

입력: D:/00_RAW/dialogue_audio/modu_corpus_dialogue_audio/2025_pcm/**.pcm
출력: D:/20_AUDIO/03_wav/individual/2025/{파일명}.wav
16kHz mono 16-bit (국립국어원 기본값). 기존 파일 건너뜀(재개 가능).
실행: python pcm_to_wav_2025.py
"""
import os
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SRC = Path(r"D:\00_RAW\dialogue_audio\modu_corpus_dialogue_audio\2025_pcm")
DST = Path(r"D:\20_AUDIO\03_wav\individual\2025")
SAMPLE_RATE, CHANNELS, BITS = 16000, 1, 16
WORKERS = 4
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def pcm_to_wav(pcm_path: Path, wav_path: Path):
    try:
        data = pcm_path.read_bytes()
        byte_rate = SAMPLE_RATE * CHANNELS * BITS // 8
        header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(data),
                             b"WAVE", b"fmt ", 16, 1, CHANNELS, SAMPLE_RATE,
                             byte_rate, CHANNELS * BITS // 8, BITS,
                             b"data", len(data))
        tmp = wav_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(header)
            f.write(data)
        os.replace(tmp, wav_path)
        return True, str(pcm_path)
    except Exception as e:
        return False, f"{pcm_path}: {e}"


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    print("PCM 파일 검색 중...", flush=True)
    pcm_files = [p for p in SRC.rglob("*.pcm")]
    total = len(pcm_files)
    print(f"PCM {total:,}개 발견", flush=True)

    tasks = []
    skipped = 0
    for p in pcm_files:
        w = DST / (p.stem + ".wav")
        if w.exists() and w.stat().st_size > 44:
            skipped += 1
        else:
            tasks.append((p, w))
    print(f"변환 대상 {len(tasks):,}개 (건너뜀 {skipped:,})", flush=True)

    done = fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(pcm_to_wav, p, w) for p, w in tasks]
        for fut in as_completed(futures):
            ok, msg = fut.result()
            if ok:
                done += 1
            else:
                fail += 1
                print(f"  !! {msg}", flush=True)
            if (done + fail) % 2000 == 0:
                rate = (done + fail) / (time.time() - t0)
                eta = (len(tasks) - done - fail) / rate / 60 if rate else 0
                print(f"  {done+fail:,}/{len(tasks):,} ({rate:.0f}/s, "
                      f"남은 예상 {eta:.0f}분)", flush=True)
    print(f"완료: 변환 {done:,} / 실패 {fail:,} / 건너뜀 {skipped:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

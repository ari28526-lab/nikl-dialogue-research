"""A6: 검색 결과(utt_id 목록) → wav·TextGrid 경로 부여/복사.

입력: utt_id 컬럼이 있는 아무 CSV (검색 결과, 후보 목록 등)
출력: manifest CSV (경로+존재 여부). --copy 시 파일을 대상 폴더로 복사
      (Praat에서 바로 열 수 있게 wav와 TextGrid를 한 폴더에)

사용 예:
  python fetch_audio_for_search.py 후보.csv
  python fetch_audio_for_search.py 후보.csv --copy --out "D:\\30_PHENOMENA\\ㄴ삽입_표본"
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

WAV = Path(r"D:\20_AUDIO\03_wav\individual")
TG = Path(r"D:\20_AUDIO\06_textgrid_merged")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def paths_for(utt_id: str):
    """utt_id -> (wav_path, tg_path). 연도·세션은 ID에서 유도.
    wav는 연도별 구조가 달라 두 경로(평면/세션 폴더)를 모두 확인:
    2020-2022·2025 = {연도}/{utt}.wav / 2023-2024 = {연도}/{세션}/{utt}.wav"""
    session = utt_id.split(".")[0]          # 예: SDRW2400001859
    year = "20" + session[4:6]              # SDRW'24'... -> 2024
    flat = WAV / year / f"{utt_id}.wav"
    nested = WAV / year / session / f"{utt_id}.wav"
    wav = flat if flat.exists() else nested
    return wav, TG / year / session / f"{utt_id}.TextGrid"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_csv", help="utt_id 컬럼이 있는 CSV")
    ap.add_argument("--copy", action="store_true", help="파일을 대상 폴더로 복사")
    ap.add_argument("--out", default="", help="복사/manifest 대상 폴더")
    args = ap.parse_args()

    src = Path(args.input_csv)
    out_dir = Path(args.out) if args.out else src.parent / (src.stem + "_audio")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    n_wav = n_tg = 0
    with open(src, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            uid = (row.get("utt_id") or "").strip()
            if not uid:
                continue
            wav, tg = paths_for(uid)
            hw, ht = wav.exists(), tg.exists()
            n_wav += hw
            n_tg += ht
            if args.copy:
                if hw:
                    shutil.copy2(wav, out_dir / wav.name)
                if ht:
                    shutil.copy2(tg, out_dir / tg.name)
            rows.append([uid, str(wav), int(hw), str(tg), int(ht)])

    mani = out_dir / "_manifest.csv"
    with open(mani, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "wav_path", "has_wav", "textgrid_path", "has_tg"])
        w.writerows(rows)
    print(f"발화 {len(rows):,}개: wav {n_wav:,} / TextGrid {n_tg:,} 확인"
          f"{' (복사 완료)' if args.copy else ''}")
    print(f"manifest: {mani}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

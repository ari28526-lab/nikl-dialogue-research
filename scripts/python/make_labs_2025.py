"""2025 MFA용 .lab 생성 — 바른 형태소 분할 기준 (기존 words tier 방식과 동일).

바른 1차 결과(10_LAYERS/01_bareun_raw/.../2025)의 tagged에서 태그를 벗기고
형태소를 공백으로 이어 .lab 텍스트 생성 (예: '이제 남 들 은').
wav와 같은 폴더(D:/20_AUDIO/03_wav/individual/2025)에 저장
→ 이 폴더가 그대로 MFA corpus 디렉터리가 됨 (별도 복사 없음).
wav가 없는 발화는 .lab을 만들지 않음 (MFA 오류 방지).
실행: python make_labs_2025.py  (WAV 변환 완료 후)
"""
import csv
import sys
from pathlib import Path

RAW_2025 = Path(r"D:\10_LAYERS\01_bareun_raw\NIKL_DIALOGUE_2025_v1.0")
WAV_DIR = Path(r"D:\20_AUDIO\03_wav\individual\2025")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def tagged_to_lab(tagged: str) -> str:
    """태그 제거 + 형태소 공백 연결. 문장부호(S* 태그)는 제외."""
    morphs = []
    for tok in tagged.split(" "):
        for unit in tok.split("+"):
            mo, _, tg = unit.rpartition("/")
            if mo and not tg.startswith("S"):
                morphs.append(mo)
    return " ".join(morphs)


def main() -> int:
    made = no_wav = empty = skipped = 0
    files = sorted(p for p in RAW_2025.glob("*.csv")
                   if not p.name.startswith("_"))
    print(f"CSV {len(files)}개 처리", flush=True)
    for k, fp in enumerate(files, 1):
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                wav = WAV_DIR / (row["utt_id"] + ".wav")
                if not wav.exists():
                    no_wav += 1
                    continue
                lab = WAV_DIR / (row["utt_id"] + ".lab")
                if lab.exists():
                    skipped += 1
                    continue
                lab_text = tagged_to_lab(row["tagged"])
                if not lab_text:
                    empty += 1
                    continue
                (WAV_DIR / (row["utt_id"] + ".lab")).write_text(
                    lab_text, encoding="utf-8")
                made += 1
        if k % 500 == 0:
            print(f"  {k}/{len(files)}", flush=True)
    print(f"완료: .lab {made:,}개 생성 / 건너뜀(기존) {skipped:,} / "
          f"wav 없음 {no_wav:,} / 빈 텍스트 {empty:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

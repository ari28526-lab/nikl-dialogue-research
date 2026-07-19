"""A6: 검색 결과(utt_id 목록) → wav·TextGrid 경로 부여/복사.

입력: utt_id 컬럼이 있는 아무 CSV (검색 결과, 후보 목록 등)
출력: manifest CSV (레이어별 경로+존재 여부). --copy 시 파일을 대상 폴더로 복사
      (Praat에서 바로 열 수 있게 wav와 TextGrid를 한 폴더에)

★ 2026-07-19 재작성: 경로 계산을 locate_utt.locate()로 일원화(좌표계 단일
  진실 원천 — docs/DATA_LAYOUT.md). 세션 재구성 후 6개년 동일 구조 전제이되
  재구성 전 평면도 locate가 폴백 지원. TextGrid는 어절 4-tier(textgrid_eojeol)
  우선, 없으면 구 3-tier(textgrid_merged) — manifest에 어느 쪽인지 기록.
  격리(quarantine)된 발화는 note에 표시.

사용 예:
  python fetch_audio_for_search.py 후보.csv
  python fetch_audio_for_search.py 후보.csv --copy --out "D:\\30_PHENOMENA\\ㄴ삽입_표본"
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_utt import locate  # noqa: E402

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
    n_wav = n_tg = n_quar = n_bad = 0
    with open(src, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            uid = (row.get("utt_id") or "").strip()
            if not uid:
                continue
            try:
                p = locate(uid)
            except ValueError as e:
                n_bad += 1
                rows.append([uid, "", 0, "", "", "", f"ID오류: {e}"])
                continue
            wav = p["wav"]
            has_wav = wav.exists()
            # TextGrid: 어절 4-tier 우선 → 없으면 구 3-tier 폴백
            if p["textgrid_eojeol"].exists():
                tg, tier = p["textgrid_eojeol"], "eojeol_4tier"
            elif p["textgrid_merged"].exists():
                tg, tier = p["textgrid_merged"], "merged_3tier"
            else:
                tg, tier = p["textgrid_eojeol"], ""
            note = ""
            if "quarantine" in p:
                note = "격리됨(0바이트 등) — 음성 사용 불가"
                n_quar += 1
            n_wav += has_wav
            n_tg += bool(tier)
            if args.copy:
                if has_wav:
                    shutil.copy2(wav, out_dir / wav.name)
                if tier:
                    shutil.copy2(tg, out_dir / tg.name)
            rows.append([uid, str(wav), int(has_wav), str(tg) if tier else "",
                         tier, str(p["bareun_csv"]), note])

    mani = out_dir / "_manifest.csv"
    with open(mani, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "wav_path", "has_wav", "textgrid_path",
                    "textgrid_tier", "bareun_csv", "note"])
        w.writerows(rows)
    print(f"발화 {len(rows):,}개: wav {n_wav:,} / TextGrid {n_tg:,} 확인"
          f"{f' / 격리 {n_quar}' if n_quar else ''}"
          f"{f' / ID오류 {n_bad}' if n_bad else ''}"
          f"{' (복사 완료)' if args.copy else ''}")
    print(f"manifest: {mani}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

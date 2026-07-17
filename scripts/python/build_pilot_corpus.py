r"""병목 계측 파일럿용 소표본 MFA 코퍼스 구성 (2026-07-17).

목적: 본 배치(510만 발화, multi-day) 전에 "MFA가 이 PC에서 CPU 병목인가
USB I/O 병목인가"를 확정하기 위한 소표본. wav을 D: 안의 별도 폴더로 복사해
(USB 특성 유지) 어절 lab과 함께 MFA 코퍼스를 만든다.

- 원본: D:\20_AUDIO\03_wav\individual\{year}\{session}\  (읽기 전용, 필수규칙 1)
- 대상: D:\mfa_eojeol\pilot\corpus\{session}\{utt}.wav + .lab
- lab 생성 로직은 realign_eojeol_build_corpus.form_to_lab 재사용 (동일 규칙)
- 재개 가능: .ready 마커 있으면 전체 건너뜀

실행: python build_pilot_corpus.py --year 2020 --sessions 50
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from realign_eojeol_build_corpus import (  # noqa: E402
    RAW, WAV_ROOT, YEAR_DIRS, form_to_lab, load_names)
import csv  # noqa: E402

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PILOT = Path(r"D:\mfa_eojeol\pilot\corpus")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", default="2020")
    ap.add_argument("--sessions", type=int, default=50)
    args = ap.parse_args()

    ready = PILOT / ".ready"
    if ready.exists():
        print(f"파일럿 코퍼스 이미 준비됨({ready}) — 건너뜀", flush=True)
        return 0
    PILOT.mkdir(parents=True, exist_ok=True)

    raw_dir = RAW / YEAR_DIRS[args.year]
    files = sorted(p for p in raw_dir.glob("*.csv")
                   if not p.name.startswith("_"))[: args.sessions]
    print(f"[pilot] {args.year} 세션 {len(files)}개 복사+lab 생성...", flush=True)
    copied = no_wav = empty = 0
    t0 = time.time()
    for k, fp in enumerate(files, 1):
        with open(fp, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        sess = rows[0]["utt_id"].split(".")[0]
        # 실측(2026-07-17): 2020은 세션 하위폴더 없는 '평면' 구조 → 양쪽 지원.
        # 세션 폴더가 있으면 목록 1회, 없으면 연도 루트에서 발화별 존재 확인(파일럿 규모라 허용).
        src_dir = WAV_ROOT / args.year / sess
        names = load_names(src_dir)
        flat_dir = WAV_ROOT / args.year
        dst_dir = PILOT / sess
        dst_dir.mkdir(exist_ok=True)
        for row in rows:
            u = row["utt_id"]
            if f"{u}.wav" in names:
                src = src_dir / f"{u}.wav"
            elif (flat_dir / f"{u}.wav").exists():
                src = flat_dir / f"{u}.wav"
            else:
                no_wav += 1
                continue
            text = form_to_lab(row.get("form", ""))
            if not text.strip():
                empty += 1
                continue
            dst = dst_dir / f"{u}.wav"
            if not dst.exists():
                shutil.copy2(src, dst)
            dst.with_suffix(".lab").write_text(text, encoding="utf-8")
            copied += 1
        el = time.time() - t0
        print(f"  {k}/{len(files)}세션 · 발화 {copied:,} · "
              f"{copied/el if el else 0:.0f}발화/s", flush=True)
    print(f"[pilot] 완료: 발화 {copied:,} / wav없음 {no_wav:,} / "
          f"빈form {empty:,} → {PILOT}", flush=True)
    if copied == 0:
        print("[pilot] !! 발화 0건 — .ready 안 씀, 실패 처리 (wav 경로 확인 필요)",
              flush=True)
        return 1
    ready.write_text(f"utts={copied}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

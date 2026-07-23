# -*- coding: utf-8 -*-
"""measure_spn.py - TextGrid phones tier의 spn(발음 미생성) 비율 측정.

G2P 부재 진단·G2P 적용 전후 비교용. long_textgrid 파싱(의존성 없음).
사용:  python measure_spn.py <TextGrid폴더> [--n 40]
"""
import argparse
import random
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def phones_texts(tg_path):
    """long_textgrid의 phones tier interval text 리스트."""
    texts, in_phones, cur = [], False, None
    for line in tg_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith('name = "'):
            in_phones = (s == 'name = "phones"')
        elif in_phones and s.startswith('text = "'):
            texts.append(s[len('text = "'):-1])
    return texts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()
    files = [p for p in Path(args.folder).rglob("*.TextGrid")]
    if not files:
        sys.exit(f"TextGrid 없음: {args.folder}")
    random.seed(42)
    sample = random.sample(files, min(args.n, len(files)))
    tot, spn, empty = 0, 0, 0
    for p in sample:
        for t in phones_texts(p):
            if t == "":
                empty += 1
                continue
            tot += 1
            if t == "spn":
                spn += 1
    print(f"폴더: {args.folder}")
    print(f"표본 TextGrid: {len(sample)}개 / 전체 {len(files):,}개")
    print(f"phones 구간(빈칸 제외): {tot:,}  · spn: {spn:,} "
          f"({100*spn/tot:.1f}%)  · 실제 음소: {tot-spn:,}")
    print(f"(참고: 빈칸 구간 {empty:,})")


if __name__ == "__main__":
    main()

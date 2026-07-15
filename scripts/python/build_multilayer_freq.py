"""다층위 2025 빈도표 세트 — MP·WSD 레이어에서 2025년판 참조 규준 생성.

출력 (D:/00_RAW/reference/NIKL_Multi-layered_2025_v1.0/freq/):
  ML2025_morpheme_freq.csv  form, label, corpus_type, freq, roman, roman_mfa
  ML2025_word_freq.csv      word_surface, morpheme_analysis, corpus_type, freq
  ML2025_sense_freq.csv     word, sense_id, pos, corpus_type, freq
corpus_type: NXML=문어, SXML=구어. 기존 MP/LS CSV 포맷 호환.
※ LS 2020의 '대체'가 아닌 병렬 규준 (규모 3만 문장 — 저빈도 항목 주의)

실행: python build_multilayer_freq.py --peek   (레이어 구조 확인만)
      python build_multilayer_freq.py          (전체 생성)
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0")
OUT = ROOT / "freq"
LEXICON = Path(r"D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv")
CORPUS_TYPE = {"NXML": "문어", "SXML": "구어"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_roman():
    t = {}
    with open(LEXICON, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w = r.get("word", "")
            if w and w not in t and r.get("word_roman"):
                t[w] = (r["word_roman"], r["word_roman_mfa"])
    return t


def peek(data):
    """레이어 구조 표본 출력 (본 실행 전 확인용)."""
    for doc in data.get("document", []):
        for sent in doc.get("sentence", []):
            if sent.get("MP") and sent.get("WSD"):
                print("form:", sent.get("form", "")[:60])
                print("word[0]:", sent.get("word", [{}])[0])
                print("MP[:3]:", sent["MP"][:3])
                print("WSD[:3]:", sent["WSD"][:3])
                return
    print("MP/WSD가 있는 문장을 찾지 못함")


def process_file(fp: Path, ctype, morph_c, word_c, sense_c):
    data = json.loads(fp.read_text(encoding="utf-8"))
    n_sent = 0
    for doc in data.get("document", []):
        for sent in doc.get("sentence", []):
            n_sent += 1
            words = {w.get("id"): w.get("form", "")
                     for w in sent.get("word", [])}
            by_word = defaultdict(list)
            for m in sent.get("MP", []) or []:
                form = m.get("form", "")
                label = m.get("label", "")
                if form:
                    morph_c[(form, label, ctype)] += 1
                    by_word[m.get("word_id")].append(f"{form}/{label}")
            for wid, surface in words.items():
                if surface:
                    ana = "+".join(by_word.get(wid, []))
                    word_c[(surface, ana, ctype)] += 1
            for s in sent.get("WSD", []) or []:
                w = s.get("form") or s.get("word") or ""
                sid = s.get("sense_id", "")
                pos = s.get("pos", "")
                if w and sid not in ("", None):
                    # "002" -> "2" (LS 2020 표기와 통일; 888/999 특수코드는 유지)
                    sid = str(sid).lstrip("0") or "0"
                    sense_c[(w, sid, pos, ctype)] += 1
    return n_sent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--peek", action="store_true", help="레이어 구조 확인만")
    args = ap.parse_args()

    files = sorted(ROOT.glob("*.json"))
    if args.peek:
        for fp in files:
            print(f"=== {fp.name} ===")
            peek(json.loads(fp.read_text(encoding="utf-8")))
        return 0

    print("로마자 사전 로드...", flush=True)
    roman = load_roman()
    morph_c, word_c, sense_c = Counter(), Counter(), Counter()
    for fp in files:
        ctype = CORPUS_TYPE.get(fp.name[:4], "기타")
        print(f"[{fp.name}] ({ctype}) 처리...", flush=True)
        n = process_file(fp, ctype, morph_c, word_c, sense_c)
        print(f"  문장 {n:,}개", flush=True)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "ML2025_morpheme_freq.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["form", "label", "corpus_type", "freq",
                    "form_roman", "form_roman_mfa"])
        for (fo, la, ct), c in morph_c.most_common():
            ro = roman.get(fo, ("", ""))
            w.writerow([fo, la, ct, c, ro[0], ro[1]])
    with open(OUT / "ML2025_word_freq.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["word_surface", "morpheme_analysis", "corpus_type", "freq"])
        for (su, an, ct), c in word_c.most_common():
            w.writerow([su, an, ct, c])
    with open(OUT / "ML2025_sense_freq.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["word", "sense_id", "pos", "corpus_type", "freq"])
        for (wo, si, po, ct), c in sense_c.most_common():
            w.writerow([wo, si, po, ct, c])

    print(f"완료: 형태소 {len(morph_c):,} / 어절 {len(word_c):,} / "
          f"의미 {len(sense_c):,} 항 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

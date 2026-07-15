"""의미번호 부여 (2차 레이어). 1차 바른 출력은 수정하지 않는다.

입력:  D:/10_LAYERS/01_bareun_raw/{연도}/{ID}.csv
출력:  D:/10_LAYERS/02_sense_annotated/{연도}/{ID}.csv
       (형태소 단위 long format)

부여 규칙 (METHODS 문서 3.3절):
  1) monosemous : 우리말샘 기준 단의어 (lexicon v2에서 (형태소,태그) 의미 1개)
  2) ls_sxls    : LS 구어(SXLS) sense_id 최빈값 + 신뢰도(우세비율)
  3) ls_all     : SXLS 미출현 시 LS 전체 분포
  4) ambiguous  : 사전에 여러 의미가 있으나 LS 미출현 -> 후보 목록만
  5) not_found  : 어떤 자원에도 없음
  조사/어미/기호(J*, E*, S*, X* 중 접사류 제외 판단 없이 J/E/S로 시작하는 태그)는
  대상 외(not_target)로 표기.

실행:
  python assign_sense_layer.py [--year 2025] [--limit-files 5]
"""
import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"D:\10_LAYERS")
RAW_DIR = BASE / "01_bareun_raw"
OUT_DIR = BASE / "02_sense_annotated"
LS_FREQ = Path(r"D:\00_RAW\reference\02_NIKL_LS\08_ALL_morpheme_freq.csv")
LEXICON = Path(r"D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv")

csv.field_size_limit(10_000_000)
NOT_TARGET_PREFIX = ("J", "E", "S")  # 조사/어미/기호


def load_ls_freq():
    """(morph, tag) -> {"SXLS": Counter(sense->freq), "ALL": Counter}"""
    table = defaultdict(lambda: {"SXLS": Counter(), "ALL": Counter()})
    with open(LS_FREQ, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w, s, p = row["word"], row["sense_id"], row["pos"]
            if not w or w == "[]" or not s or s in ("[]", "None", ""):
                continue
            try:
                freq = int(row["freq"])
            except ValueError:
                continue
            key = (w, p)
            table[key]["ALL"][s] += freq
            if row.get("corpus_type") == "SXLS":
                table[key]["SXLS"][s] += freq
    return table


def load_lexicon_senses():
    """(word, pos_tag) -> set(sense_no)  (우리말샘/표준대사전 기준 의미 수)"""
    senses = defaultdict(set)
    with open(LEXICON, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w, p, sn = row.get("word", ""), row.get("pos_tag", ""), row.get("sense_no", "")
            if w and p and sn:
                senses[(w, p)].add(sn.lstrip("0") or "1")
    return senses


def decide(morph, tag, ls_table, lex_senses):
    """반환: (sense_id, confidence, method, candidates)"""
    if tag[:1] in NOT_TARGET_PREFIX:
        return "", "", "not_target", ""
    lex = lex_senses.get((morph, tag), set())
    if len(lex) == 1:
        return next(iter(lex)), "1.00", "monosemous", ""
    ls = ls_table.get((morph, tag))
    if ls:
        for src, method in (("SXLS", "ls_sxls"), ("ALL", "ls_all")):
            dist = ls[src]
            if dist:
                total = sum(dist.values())
                sense, top = dist.most_common(1)[0]
                return sense, f"{top/total:.2f}", method, ""
    if lex:
        return "", "", "ambiguous", "|".join(sorted(lex))
    return "", "", "not_found", ""


def iter_morphs(tagged: str):
    """tagged -> (word_idx, morph_idx, morph, tag)"""
    for wi, token in enumerate(tagged.split(" "), 1):
        if not token:
            continue
        for mi, unit in enumerate(token.split("+"), 1):
            morph, _, tag = unit.rpartition("/")
            if morph:
                yield wi, mi, morph, tag


def process_file(in_csv: Path, out_csv: Path, ls_table, lex_senses, stats: Counter):
    tmp = out_csv.with_suffix(".tmp")
    with open(in_csv, encoding="utf-8") as fi, \
         open(tmp, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["utt_id", "word_idx", "morph_idx", "morph", "tag",
                    "sense_id", "confidence", "method", "candidates"])
        for row in csv.DictReader(fi):
            for wi, mi, morph, tag in iter_morphs(row["tagged"]):
                sense, conf, method, cand = decide(morph, tag, ls_table, lex_senses)
                stats[method] += 1
                w.writerow([row["utt_id"], wi, mi, morph, tag,
                            sense, conf, method, cand])
    os.replace(tmp, out_csv)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year")
    ap.add_argument("--limit-files", type=int, default=0)
    args = ap.parse_args()

    print("자원 로드 중 (LS 빈도, lexicon v2)...", flush=True)
    ls_table = load_ls_freq()
    lex_senses = load_lexicon_senses()
    print(f"LS (형태소,태그) {len(ls_table):,}개 / lexicon {len(lex_senses):,}개", flush=True)

    stats = Counter()
    n_files = 0
    for ydir in sorted(RAW_DIR.iterdir()):
        if not ydir.is_dir():
            continue
        if args.year and args.year not in ydir.name:
            continue
        out_dir = OUT_DIR / ydir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(p for p in ydir.glob("*.csv")
                       if not p.name.startswith("_"))
        if args.limit_files:
            files = files[: args.limit_files]
        for f in files:
            out_csv = out_dir / f.name
            if out_csv.exists():
                continue
            process_file(f, out_csv, ls_table, lex_senses, stats)
            n_files += 1
            if n_files % 100 == 0:
                print(f"  {n_files}파일 처리...", flush=True)

    total = sum(stats.values()) or 1
    print(f"\n완료: {n_files}파일, 형태소 토큰 {total:,}개")
    for method, c in stats.most_common():
        print(f"  {method:12s} {c:>10,} ({c/total*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

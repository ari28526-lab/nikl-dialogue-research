"""A2 보완 패스: 의미번호 레이어의 not_found/ambiguous 행 재판정.

대상과 방법 (원칙: 근거 있는 것만 부여, 나머지는 이유가 보이게 남김):
  1) 접사(XPN/XSN/XSV/XSA)·어근(XR): lexicon v2 직접 조회.
     XSV/XSA는 lexicon 표제어의 '-다' 제거형으로도 색인 (되다->되)
  2) 단의어 -> sense 확정, method="lex_mono"
  3) 다의어 -> 우리말샘 첫 의미번호를 잠정 부여, method="lex_first"
     (confidence 공란, candidates 전체 보존 -> 연구 시 필터 가능)
  4) 그 외 not_found는 그대로 유지

입력/출력: D:/05_.../02_sense_annotated/{연도}/{ID}.csv (제자리 갱신)
실행: python supplement_sense_layer.py [--year 2025] [--limit-files 5]
"""
import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"D:\10_LAYERS")
SENSE_DIR = BASE / "02_sense_annotated"
LEXICON = Path(r"D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_lexicon_senses():
    """(word, pos_tag) -> sorted list of sense_no.
    XSV/XSA는 '-다' 제거형도 함께 색인."""
    senses = defaultdict(set)
    with open(LEXICON, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w = r.get("word", "")
            p = (r.get("pos_tag") or "").strip()
            sn = (r.get("sense_no") or "").strip()
            if not (w and p and sn):
                continue
            sn = sn.lstrip("0") or "1"
            senses[(w, p)].add(sn)
            if p in ("XSV", "XSA") and w.endswith("다") and len(w) > 1:
                senses[(w[:-1], p)].add(sn)
    return {k: sorted(v, key=lambda x: int(x) if x.isdigit() else 999)
            for k, v in senses.items()}


def redecide(morph, tag, lex):
    """반환 (sense, conf, method, candidates) 또는 None(변경 없음)."""
    hits = lex.get((morph, tag))
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0], "1.00", "lex_mono", ""
    return hits[0], "", "lex_first", "|".join(hits)


def process_file(fp: Path, lex, stats: Counter) -> int:
    rows = []
    changed = 0
    with open(fp, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {c: i for i, c in enumerate(header)}
        for row in reader:
            method = row[idx["method"]]
            if method in ("not_found", "ambiguous"):
                r = redecide(row[idx["morph"]], row[idx["tag"]], lex)
                if r:
                    row[idx["sense_id"]], row[idx["confidence"]], \
                        row[idx["method"]], row[idx["candidates"]] = r
                    changed += 1
                    stats[r[2]] += 1
                else:
                    stats["유지_" + method] += 1
            rows.append(row)
    if changed:
        tmp = fp.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        os.replace(tmp, fp)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year")
    ap.add_argument("--limit-files", type=int, default=0)
    args = ap.parse_args()

    print("lexicon 로드 중...", flush=True)
    lex = load_lexicon_senses()
    print(f"(word,pos) 항목 {len(lex):,}개 (XSV/XSA 어간형 색인 포함)", flush=True)

    stats = Counter()
    n_files = n_changed_files = 0
    for ydir in sorted(SENSE_DIR.iterdir()):
        if not ydir.is_dir() or (args.year and args.year not in ydir.name):
            continue
        files = sorted(p for p in ydir.glob("*.csv") if not p.name.startswith("_"))
        if args.limit_files:
            files = files[: args.limit_files]
        print(f"[{ydir.name}] {len(files)}개 파일", flush=True)
        for fp in files:
            if process_file(fp, lex, stats):
                n_changed_files += 1
            n_files += 1
            if n_files % 1000 == 0:
                print(f"  {n_files}파일... (갱신 {n_changed_files})", flush=True)

    print(f"\n완료: 검사 {n_files}파일, 갱신 {n_changed_files}파일")
    for k, c in stats.most_common():
        print(f"  {k:16s} {c:>12,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

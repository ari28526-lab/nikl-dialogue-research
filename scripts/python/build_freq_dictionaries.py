"""빈도사전 생성: 어절 사전 + 형태소 사전 (연도별 + MP/LS 비교 + 로마자/IPA).

입력:  D:/10_LAYERS/01_bareun_raw/{연도}/*.csv
출력:  D:/10_LAYERS/03_freq_dictionaries/
  morpheme_freq_dictionary.csv  형태소+태그 단위
  eojeol_freq_dictionary.csv    어절(표면형) 단위
  _roman_mfa_to_ipa.csv         로마자(MFA식)->IPA 변환표 (직접 수정 가능,
                                수정 후 재실행하면 IPA만 다시 계산됨)
  _summary.txt                  집계 요약

비교 빈도 출처:
  MP  = NIKL 형태 분석 말뭉치 v1.1 (구어/문어)
  LS  = NIKL 어휘의미 분석 말뭉치 2020 (SXLS 구어 / 전체)
로마자: MP -> LS -> lexicon v2 순으로 조회. IPA는 roman_mfa에서 변환.

실행: python build_freq_dictionaries.py [--year 2020] (테스트용 연도 제한)
"""
import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"D:\10_LAYERS")
RAW_DIR = BASE / "01_bareun_raw"
OUT_DIR = BASE / "03_freq_dictionaries"
MP_MORPH = Path(r"D:\00_RAW\reference\01_NIKL_MP_v_1_1\06_ALL_morpheme_freq.csv")
MP_WORD = Path(r"D:\00_RAW\reference\01_NIKL_MP_v_1_1\05_ALL_word_freq.csv")
LS_MORPH = Path(r"D:\00_RAW\reference\02_NIKL_LS\08_ALL_morpheme_freq.csv")
LS_WORD = Path(r"D:\00_RAW\reference\02_NIKL_LS\07_ALL_word_freq.csv")
LEXICON = Path(r"D:\00_RAW\reference\00_DICTIONARY\01_NIKL_lexicon_full_v2.csv")
KOFREN_DIR = Path(r"C:\Users\ari30\research\2026_summer_research\01_frequency_data\final_word_frequency")
ML2025 = Path(r"D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0\freq\ML2025_morpheme_freq.csv")
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):  # Windows cp949 콘솔 대비
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------- IPA 변환 ----------
DEFAULT_IPA = [
    # 초성 (대문자)
    ("G", "k"), ("KK", "k*"), ("N", "n"), ("D", "t"), ("TT", "t*"),
    ("R", "ɾ"), ("M", "m"), ("B", "p"), ("PP", "p*"), ("S", "s"),
    ("SS", "s*"), ("J", "tɕ"), ("JJ", "tɕ*"), ("CH", "tɕʰ"), ("K", "kʰ"),
    ("T", "tʰ"), ("P", "pʰ"), ("H", "h"), ("NG", "ŋ"),
    # 모음
    ("A", "a"), ("AE", "ɛ"), ("YA", "ja"), ("YAE", "jɛ"), ("EO", "ʌ"),
    ("E", "e"), ("YEO", "jʌ"), ("YE", "je"), ("O", "o"), ("WA", "wa"),
    ("WAE", "wɛ"), ("OE", "we"), ("YO", "jo"), ("U", "u"), ("WO", "wʌ"),
    ("WE", "we"), ("WI", "wi"), ("YU", "ju"), ("EU", "ɯ"), ("UI", "ɰi"),
    ("I", "i"),
    # 종성 (소문자)
    ("k", "k̚"), ("n", "n"), ("t", "t̚"), ("l", "l"), ("m", "m"),
    ("p", "p̚"), ("ng", "ŋ"),
    # 종성 대문자 표기 변형 및 문장부호
    ("L", "l"), (".", ""), (",", ""), ("?", ""), ("!", ""), ("~", ""),
]


def load_ipa_map():
    path = OUT_DIR / "_roman_mfa_to_ipa.csv"
    if not path.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["roman_mfa", "ipa", "비고"])
            for r, i in DEFAULT_IPA:
                w.writerow([r, i, ""])
        print(f"IPA 변환표 생성(기본값): {path} — 필요시 직접 수정 후 재실행")
    with open(path, encoding="utf-8-sig") as f:
        return {row["roman_mfa"]: row["ipa"] for row in csv.DictReader(f)}


def to_ipa(roman_mfa: str, ipa_map: dict) -> str:
    """'G EO - S EU' -> 'kʌ.sɯ'. 미정의 기호는 ⟨기호⟩로 표시."""
    if not roman_mfa or roman_mfa.strip() in ("[ - ]", "-"):
        return ""
    syllables = []
    for syl in roman_mfa.split("-"):
        parts = [ipa_map.get(tok, f"⟨{tok}⟩")
                 for tok in syl.split() if tok]
        if parts:
            syllables.append("".join(parts))
    return ".".join(syllables)


# ---------- 비교 자원 로드 ----------
def load_mp_morph():
    """(form, label) -> [구어, 문어, roman, roman_mfa]"""
    t = {}
    with open(MP_MORPH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            key = (r["form"], r["label"])
            e = t.setdefault(key, [0, 0, r["form_roman"], r["form_roman_mfa"]])
            if r["corpus_type"] == "구어":
                e[0] += int(r["freq"])
            else:
                e[1] += int(r["freq"])
    return t


def load_ls_morph():
    """(word, pos) -> [SXLS, ALL, roman, roman_mfa, top_sense, top_share]"""
    acc = defaultdict(lambda: {"SXLS": Counter(), "ALL": Counter(),
                               "roman": "", "mfa": ""})
    with open(LS_MORPH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w, p, s = r["word"], r["pos"], r["sense_id"]
            if not w or w == "[]":
                continue
            try:
                freq = int(r["freq"])
            except ValueError:
                continue
            e = acc[(w, p)]
            e["ALL"][s] += freq
            if r["corpus_type"] == "SXLS":
                e["SXLS"][s] += freq
            if not e["roman"] and r.get("word_roman", "") not in ("", "[ - ]"):
                e["roman"], e["mfa"] = r["word_roman"], r["word_roman_mfa"]
    out = {}
    for key, e in acc.items():
        dist = e["SXLS"] or e["ALL"]
        top, share = "", ""
        if dist:
            s, c = dist.most_common(1)[0]
            top, share = s, f"{c / sum(dist.values()):.2f}"
        out[key] = [sum(e["SXLS"].values()), sum(e["ALL"].values()),
                    e["roman"], e["mfa"], top, share]
    return out


def load_word_table(path, spoken_key):
    """word_surface -> [spoken, other, roman, roman_mfa] (MP/LS 어절 빈도)"""
    t = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w = r["word_surface"]
            if not w:
                continue
            e = t.setdefault(w, [0, 0, r.get("word_roman", ""),
                                 r.get("word_roman_mfa", "")])
            if r["corpus_type"] == spoken_key:
                e[0] += int(r["freq"])
            else:
                e[1] += int(r["freq"])
    return t


def load_lexicon_info():
    """lexicon v2에서 두 가지 추출:
    roman: word -> (roman, roman_mfa)  (로마자 폴백)
    etym : (word, pos_tag) -> (어원분류, 원어)  (우리말샘·표준대사전 기반)
           의미별 어원이 갈리면 '혼합(...)'으로 표시 (과잉 확정 방지)"""
    roman = {}
    etym_sets = defaultdict(lambda: [set(), set()])
    senses = defaultdict(set)
    with open(LEXICON, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            w = r.get("word", "")
            if not w:
                continue
            if w not in roman and r.get("word_roman"):
                roman[w] = (r["word_roman"], r["word_roman_mfa"])
            p = (r.get("pos_tag") or "").strip()
            wt = (r.get("word_type") or "").strip()
            og = (r.get("origin") or "").strip()
            sn = (r.get("sense_no") or "").strip().lstrip("0") or ""
            if p and sn:
                senses[(w, p)].add(sn)
                if p in ("XSV", "XSA") and w.endswith("다") and len(w) > 1:
                    senses[(w[:-1], p)].add(sn)
            if p and wt:
                keys = [(w, p)]
                # XSV/XSA 접미사는 바른 출력(어간형)과 맞추기 위해 '-다' 제거형도 색인
                if p in ("XSV", "XSA") and w.endswith("다") and len(w) > 1:
                    keys.append((w[:-1], p))
                for k in keys:
                    s = etym_sets[k]
                    s[0].add(wt)
                    if og:
                        s[1].add(og)
    etym = {}
    for k, (types, origins) in etym_sets.items():
        t = (types.pop() if len(types) == 1
             else "혼합(" + "|".join(sorted(types)) + ")")
        etym[k] = (t, "|".join(sorted(origins)[:3]))
    lex_senses = {k: sorted(v, key=lambda x: int(x) if x.isdigit() else 999)
                  for k, v in senses.items()}
    return roman, etym, lex_senses


def decide_sense(mo, tg, lex_senses, ls_e):
    """A2/보완 패스와 동일한 우선순위로 (sense_id, conf, method) 결정.
    1) 단의어 확정 2) LS 구어/전체 우세 3) 다의어 첫 의미(잠정) 4) 대상외/없음"""
    lex_s = lex_senses.get((mo, tg))
    if lex_s and len(lex_s) == 1:
        return lex_s[0], "1.00", "monosemous"
    if ls_e[4]:  # LS 우세 의미 존재
        return ls_e[4], ls_e[5], "ls"
    if lex_s:
        return lex_s[0], "", "lex_first(" + "|".join(lex_s) + ")"
    if tg[:1] in ("J", "E", "S"):
        return "", "", "not_target"
    return "", "", "not_found"


def load_ml2025():
    """(form, label) -> [구어, 문어]  (다층위 2025 규준)"""
    t = {}
    if not ML2025.exists():
        print(f"  [경고] ML2025 없음: {ML2025}")
        return t
    with open(ML2025, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            key = (r["form"], r["label"])
            e = t.setdefault(key, [0, 0])
            if r["corpus_type"] == "구어":
                e[0] += int(r["freq"])
            else:
                e[1] += int(r["freq"])
    return t


def load_kofren():
    """(WORD, POS_TAG) -> [all, young, child, elderly, log10_all]
    KoFREN(Kim, Choi & Cho 2024) — 바른 태그셋 기반 자유발화 빈도 규준"""
    files = [("all", "all_speakers_frequency_counts_final.csv"),
             ("young", "adult_frequency_counts_final.csv"),
             ("child", "children_frequency_counts_final.csv"),
             ("elderly", "elderly_frequency_counts_final.csv")]
    order = {name: i for i, (name, _) in enumerate(files)}
    t = {}
    for key, fname in files:
        fp = KOFREN_DIR / fname
        if not fp.exists():
            print(f"  [경고] KoFREN 파일 없음: {fp}")
            continue
        with open(fp, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                w, p = r.get("WORD", ""), r.get("POS_TAG", "")
                if not w:
                    continue
                e = t.setdefault((w, p), [0, 0, 0, 0, ""])
                try:
                    e[order[key]] += int(float(r.get("COUNT", 0)))
                except ValueError:
                    continue
                if key == "all" and r.get("LOG10"):
                    e[4] = f"{float(r['LOG10']):.3f}"
    return t


# ---------- 대화 말뭉치 집계 (연도 분할: count -> merge) ----------
def stage_count(year: str):
    """한 연도만 집계해 중간 파일로 저장 (RAM 절약: 연도별 별도 프로세스)."""
    part = OUT_DIR / "_partials"
    part.mkdir(parents=True, exist_ok=True)
    for ydir in sorted(RAW_DIR.iterdir()):
        if not ydir.is_dir():
            continue
        m = re.search(r"(20\d\d)", ydir.name)
        if not m or m.group(1) != year:
            continue
        morph, eo, n_utt = Counter(), Counter(), 0
        files = sorted(p for p in ydir.glob("*.csv") if not p.name.startswith("_"))
        print(f"[{ydir.name}] {len(files)}파일 집계...", flush=True)
        for k, fp in enumerate(files, 1):
            with open(fp, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    n_utt += 1
                    tagged = row["tagged"]
                    surf = row["form"].split()
                    toks = tagged.split(" ") if tagged else []
                    same = len(surf) == len(toks)
                    for ti, tok in enumerate(toks):
                        if not tok:
                            continue
                        for unit in tok.split("+"):
                            mo, _, tg = unit.rpartition("/")
                            if mo:
                                morph[(mo, tg)] += 1
                        if same:
                            eo[(surf[ti], tok)] += 1
            if k % 500 == 0:
                print(f"  {k}/{len(files)}", flush=True)
        with open(part / f"morph_{year}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for (mo, tg), c in morph.items():
                w.writerow([mo, tg, c])
        with open(part / f"eojeol_{year}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for (s, a), c in eo.items():
                w.writerow([s, a, c])
        (part / f"meta_{year}.txt").write_text(str(n_utt), encoding="utf-8")
        print(f"{year} 완료: 발화 {n_utt:,} / 고유 형태소 {len(morph):,} / "
              f"(어절,분석) {len(eo):,}")


def stage_merge_counts():
    """연도별 중간 파일 병합 -> 전체 구조 복원."""
    part = OUT_DIR / "_partials"
    morph = defaultdict(lambda: [0] * len(YEARS))
    eojeol = defaultdict(lambda: [0] * len(YEARS))
    eo_ana = defaultdict(Counter)
    n_utt = 0
    for yi, y in enumerate(YEARS):
        mf = part / f"morph_{y}.csv"
        if not mf.exists():
            print(f"  [경고] {y} 중간 파일 없음 — 건너뜀 (count 단계 먼저 실행)")
            continue
        with open(mf, encoding="utf-8") as f:
            for mo, tg, c in csv.reader(f):
                morph[(mo, tg)][yi] = int(c)
        with open(part / f"eojeol_{y}.csv", encoding="utf-8") as f:
            for s, a, c in csv.reader(f):
                c = int(c)
                eojeol[s][yi] += c
                eo_ana[s][a] += c
        meta = part / f"meta_{y}.txt"
        if meta.exists():
            n_utt += int(meta.read_text())
        print(f"  {y} 병합", flush=True)
    return morph, eojeol, eo_ana, n_utt


def write_morph_dict(morph, mp, ls, lex_roman, lex_etym, lex_senses, kofren,
                     ml2025, ipa_map):
    path = OUT_DIR / "morpheme_freq_dictionary.csv"
    rows = sorted(morph.items(), key=lambda kv: -sum(kv[1]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["morph", "tag"] + [f"freq_{y}" for y in YEARS]
                   + ["freq_total", "freq_MP_spoken", "freq_MP_written",
                      "freq_LS_spoken", "freq_LS_all",
                      "freq_ML2025_spoken", "freq_ML2025_written",
                      "freq_KoFREN_all", "freq_KoFREN_young",
                      "freq_KoFREN_child", "freq_KoFREN_elderly",
                      "KoFREN_log10", "sense_id", "sense_conf", "sense_method",
                      "etym_type", "etym_origin",
                      "roman", "roman_mfa", "ipa"])
        for (mo, tg), per_year in rows:
            mp_e = mp.get((mo, tg), [0, 0, "", ""])
            ls_e = ls.get((mo, tg), [0, 0, "", "", "", ""])
            kf = kofren.get((mo, tg), [0, 0, 0, 0, ""])
            ml = ml2025.get((mo, tg), [0, 0])
            et = lex_etym.get((mo, tg), ("", ""))
            sense_id, sense_conf, sense_method = decide_sense(mo, tg, lex_senses, ls_e)
            roman = mp_e[2] or ls_e[2]
            mfa = mp_e[3] or ls_e[3]
            if not roman:
                roman, mfa = lex_roman.get(mo, ("", ""))
            w.writerow([mo, tg] + per_year + [sum(per_year),
                        mp_e[0], mp_e[1], ls_e[0], ls_e[1],
                        ml[0], ml[1],
                        kf[0], kf[1], kf[2], kf[3], kf[4],
                        sense_id, sense_conf, sense_method, et[0], et[1],
                        roman, mfa, to_ipa(mfa, ipa_map)])
    return path, len(rows)


def write_eojeol_dict(eojeol, eo_ana, mp_w, ls_w, ipa_map):
    path = OUT_DIR / "eojeol_freq_dictionary.csv"
    rows = sorted(eojeol.items(), key=lambda kv: -sum(kv[1]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["eojeol", "top_analysis"] + [f"freq_{y}" for y in YEARS]
                   + ["freq_total", "freq_MP_spoken", "freq_MP_written",
                      "freq_LS_spoken", "freq_LS_all",
                      "roman", "roman_mfa", "ipa"])
        for surf, per_year in rows:
            ana = eo_ana[surf].most_common(1)
            mp_e = mp_w.get(surf, [0, 0, "", ""])
            ls_e = ls_w.get(surf, [0, 0, "", ""])
            roman = mp_e[2] or ls_e[2]
            mfa = mp_e[3] or ls_e[3]
            w.writerow([surf, ana[0][0] if ana else ""] + per_year
                       + [sum(per_year), mp_e[0], mp_e[1], ls_e[0], ls_e[1],
                          roman, mfa, to_ipa(mfa, ipa_map)])
    return path, len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["count", "merge"], required=True,
                    help="count: 한 연도 집계 (--year 필수) / merge: 병합+사전 생성")
    ap.add_argument("--year", help="count 단계에서 집계할 연도 (예: 2020)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.stage == "count":
        if not args.year:
            sys.exit("--stage count에는 --year가 필요합니다 (예: --year 2020)")
        stage_count(args.year)
        return 0

    # merge 단계: 자원 로드 + 병합 + 사전 생성
    ipa_map = load_ipa_map()
    print("비교 자원 로드 (MP/LS/lexicon/KoFREN)...", flush=True)
    mp = load_mp_morph()
    ls = load_ls_morph()
    mp_w = load_word_table(MP_WORD, "구어")
    ls_w = load_word_table(LS_WORD, "SXLS")
    lex_roman, lex_etym, lex_senses = load_lexicon_info()
    kofren = load_kofren()
    ml2025 = load_ml2025()

    print("연도별 중간 파일 병합...", flush=True)
    morph, eojeol, eo_ana, n_utt = stage_merge_counts()
    p1, n1 = write_morph_dict(morph, mp, ls, lex_roman, lex_etym, lex_senses,
                              kofren, ml2025, ipa_map)
    p2, n2 = write_eojeol_dict(eojeol, eo_ana, mp_w, ls_w, ipa_map)

    total_tok = sum(sum(v) for v in morph.values())
    summary = [
        f"집계 발화: {n_utt:,}",
        f"형태소 토큰: {total_tok:,} / 고유 (형태소,태그): {n1:,}",
        f"고유 어절: {n2:,}",
        f"출력: {p1.name}, {p2.name}",
    ]
    (OUT_DIR / "_summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

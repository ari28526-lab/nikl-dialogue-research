"""온디맨드 TextGrid enrichment — 분석 대상 발화에만 로마자·예측발음·형태소
분석 tier를 얹는다 (전량 4-tier는 가볍게 유지: 2026-07-23 결정 (1)).

배경: 06_textgrid_eojeol의 표준 4-tier(words/phones/morphemes/utterance)는
585만 파일 전량 유지. 철자 로마자·예측발음 등 '파생값'은 검색 마스터
CSV(05_search_master)에 이미 있고 utt_id로 조인 가능하므로 tier에 상시
넣지 않는다. 대신 Praat에서 실제로 열어보는 소수 발화에만, CSV를 읽어
enrichment tier를 얹은 '사본'을 만든다(운율 5번째 tier와 같은 온디맨드 방식).

원칙:
  - 원본(06_textgrid_eojeol)은 절대 수정 안 함 — 사본을 --out 에 새로 씀.
  - 어절 정렬은 words tier 경계를 그대로 미러. 내용 어절 수와 토큰 수가
    다르면 발화 전체 1구간으로 안전 폴백 + [align≠] 표시(조용한 오정렬 금지).
  - 경로는 paths.py(P). utf-8 + stdout reconfigure.

★검증 대기(2026-07-23): 각 컬럼 '어절 구분자' 가정(roman='|', 한글=공백,
  tagged=미분할)은 실제 CSV로 --dry-run 1세션 확인 후 확정할 것. 현재는
  --selftest(합성) 통과 상태. ※MFA 등 D: 배치 도는 동안에는 실행 금지(경합).

사용:
  python enrich_textgrid_ondemand.py --selftest
  python enrich_textgrid_ondemand.py --session SDRW2000000001 --dry-run
  python enrich_textgrid_ondemand.py --session SDRW2000000001
  python enrich_textgrid_ondemand.py --hitlist hits.csv --tiers pron_pred_roman,form_roman
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P                              # noqa: E402
from merge_textgrid_v2 import interval_tier      # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
csv.field_size_limit(10_000_000)

SILENCE = {"", "sil", "sp", "spn", "<eps>", "<unk>"}
ROMAN_COLS = {"form_roman", "tagged_roman", "pron_pred_roman", "pron_pred_ipa"}
SPACE_COLS = {"form", "original_form", "pron_pred_hangul"}
# tagged(한글 형태소분석)의 어절 구분자 미확정 → 기본 미분할(발화 1구간).
# 확정 후 --delims tagged=SPACE 처럼 켤 것.
DEFAULT_TIERS = ["pron_pred_hangul", "pron_pred_roman", "form_roman", "tagged"]
DEFAULT_OUT = Path(r"C:\enriched_textgrid")


def col_delim(col, overrides):
    if col in overrides:
        return overrides[col]
    if col in ROMAN_COLS:
        return "|"
    if col in SPACE_COLS:
        return " "
    return None  # 미분할(발화 전체 1구간)


def split_tokens(value, delim):
    if delim == " ":
        return value.split()
    return [t.strip() for t in value.split(delim)]


def content_indices(words):
    return [i for i, (b, e, t) in enumerate(words) if t.strip() not in SILENCE]


def build_tier(name, value, delim, words, dur):
    """words 경계를 미러한 enrichment tier lines 생성.
    반환: (tier_lines, warn|None). 불일치 시 발화 전체 1구간으로 폴백."""
    value = value or ""
    if delim is None:
        return interval_tier(name, [(0.0, dur, value)], dur), None
    idx = content_indices(words)
    tokens = split_tokens(value, delim)
    if len(tokens) != len(idx):
        warn = f"{name}: 어절 {len(idx)} != 토큰 {len(tokens)} -> 전체 1구간 폴백"
        return interval_tier(name, [(0.0, dur, f"[align≠] {value}")], dur), warn
    idxset = set(idx)
    ptr = 0
    new = []
    for i, (b, e, t) in enumerate(words):
        if i in idxset:
            new.append((b, e, tokens[ptr])); ptr += 1
        else:
            new.append((b, e, ""))
    return interval_tier(name, new, dur), None


def write_tg(path, dur, ordered_tiers):
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {dur:.6f}", "tiers? <exists>",
             f"size = {len(ordered_tiers)}", "item []:"]
    for i, tier in enumerate(ordered_tiers, 1):
        lines.append(f"    item [{i}]:")
        lines.extend(tier)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)


def enrich_utt(master_tg, row, cols, overrides, out_path, dry):
    """반환: (status, warns). 원본 4-tier + phones 아래 enrichment tier 삽입."""
    from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # 지연 import
    dur, tiers = parse_mfa_textgrid(master_tg)
    words = tiers.get("words", [])
    if dur is None or not words:
        return "no_words", []
    ordered = [interval_tier("words", words, dur),
               interval_tier("phones", tiers.get("phones", []), dur)]
    warns = []
    for col in cols:
        t, w = build_tier(col, row.get(col, ""), col_delim(col, overrides),
                          words, dur)
        ordered.append(t)
        if w:
            warns.append(w)
    ordered.append(interval_tier(
        "morphemes", tiers.get("morphemes") or [(0.0, dur, "")], dur))
    ordered.append(interval_tier(
        "utterance", tiers.get("utterance") or [(0.0, dur, row.get("form", ""))],
        dur))
    if not dry:
        write_tg(out_path, dur, ordered)
    return "ok", warns


def derive_year(session):
    """세션 코드에서 연도 유도: SDRW20..->2020 ... SDRW25..->2025."""
    return "20" + session[4:6]


def load_session_rows(year, session):
    fp = P("search_master") / year / f"{session}.csv"
    if not fp.exists():
        return None
    rows = {}
    with open(fp, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["utt_id"]] = r
    return rows


def read_hitlist(fp):
    """CSV(최소 'session_id', 선택 'utt_id'/'year') -> {(year,session): set(utt)}.
    utt_id 없는 세션은 빈 set = 세션 전체."""
    groups = {}
    with open(fp, encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or "session_id" not in rdr.fieldnames:
            sys.exit("hitlist에는 최소 'session_id' 컬럼 필요(+선택 'utt_id','year').")
        for r in rdr:
            s = r["session_id"]
            key = (r.get("year") or derive_year(s), s)
            groups.setdefault(key, set())
            if r.get("utt_id"):
                groups[key].add(r["utt_id"])
    return groups


def parse_overrides(spec):
    out = {}
    for kv in spec.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            v = v.strip()
            out[k.strip()] = " " if v.upper() == "SPACE" else v
    return out


def main():
    ap = argparse.ArgumentParser(description="온디맨드 TextGrid enrichment")
    ap.add_argument("--session")
    ap.add_argument("--year")
    ap.add_argument("--utt", nargs="+")
    ap.add_argument("--hitlist")
    ap.add_argument("--tiers", default=",".join(DEFAULT_TIERS))
    ap.add_argument("--delims", default="", help="예: tagged=SPACE,foo=|")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    cols = [c.strip() for c in a.tiers.split(",") if c.strip()]
    overrides = parse_overrides(a.delims)
    out_root, tg_root = Path(a.out), P("textgrid_eojeol")

    if a.hitlist:
        groups = read_hitlist(Path(a.hitlist))
    elif a.session:
        groups = {(a.year or derive_year(a.session), a.session): set(a.utt or [])}
    else:
        sys.exit("--session 또는 --hitlist (또는 --session과 --utt) 필요.")

    made = missing = skipped = warns = 0
    for (year, session), utts in groups.items():
        rows = load_session_rows(year, session)
        if rows is None:
            print(f"!! CSV 없음: {P('search_master')/year/(session+'.csv')}")
            continue
        targets = sorted(utts) if utts else sorted(rows)
        for uid in targets:
            row = rows.get(uid)
            mtg = tg_root / year / session / f"{uid}.TextGrid"
            if row is None or not mtg.exists():
                missing += 1
                continue
            status, w = enrich_utt(mtg, row, cols, overrides,
                                   out_root / year / session / f"{uid}.TextGrid",
                                   a.dry_run)
            if status == "ok":
                made += 1
                for m in w:
                    warns += 1
                    print(f"  ~ {uid} {m}")
            else:
                skipped += 1
    kind = "검토(dry-run)" if a.dry_run else "생성"
    print(f"{kind} {made} / 누락 {missing} / 스킵 {skipped} / 폴백경고 {warns}")
    if not a.dry_run and made:
        print(f"출력 루트: {out_root}")
    return 0


def selftest():
    """합성 데이터로 정렬·폴백·구분자 로직 검증 (D: 미접근)."""
    dur = 1.0
    words = [(0.0, 0.4, "나는"), (0.4, 0.45, ""), (0.45, 1.0, "밥을")]
    t, w = build_tier("form_roman", "N A n EU n | p A p EU l", "|", words, dur)
    assert w is None
    s = "\n".join(t)
    assert 'text = "N A n EU n"' in s and 'text = "p A p EU l"' in s
    t2, w2 = build_tier("form_roman", "only_one", "|", words, dur)
    assert w2 is not None and "[align≠]" in "\n".join(t2)
    t3, w3 = build_tier("pron_pred_hangul", "나는 바블", " ", words, dur)
    assert w3 is None and 'text = "바블"' in "\n".join(t3)
    t4, w4 = build_tier("tagged", "나/NP + 는/JX 밥/NNG + 을/JKO", None, words, dur)
    assert w4 is None and 'text = "나/NP + 는/JX 밥/NNG + 을/JKO"' in "\n".join(t4)
    print("selftest OK (정렬/폴백/공백/미분할 4케이스)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

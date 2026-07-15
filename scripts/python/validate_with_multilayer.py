"""다층위 2025 구어부(gold) 대비 우리 파이프라인 채점.

전제: SXML 16,439문장 = 우리 2024 발화의 부분집합 (ID 100% 일치 확인).
채점 A) 형태소: 바른(01 레이어) vs 다층위 MP — (형태,태그) 다중집합 P/R/F1
채점 B) 의미번호: 우리 02 레이어 vs 다층위 WSD — 부여방법별 정확도
출력: 10_LAYERS/05_audio_index/validation_multilayer_report.txt + 불일치 표본 CSV
실행: python validate_with_multilayer.py
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SXML = Path(r"D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0\SXML2502512312.json")
RAW24 = Path(r"D:\10_LAYERS\01_bareun_raw\NIKL_DIALOGUE_2024_v1.0")
SENSE24 = Path(r"D:\10_LAYERS\02_sense_annotated\NIKL_DIALOGUE_2024_v1.0")
OUT_DIR = Path(r"D:\10_LAYERS\05_audio_index")
SPECIAL = {"777", "888", "999"}  # 고유명사 등 특수코드
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_gold():
    """utt_id -> {'mp': [(form,label)], 'wsd': [(form,sense,pos)]}"""
    data = json.loads(SXML.read_text(encoding="utf-8"))
    gold = {}
    for doc in data.get("document", []):
        for s in doc.get("sentence", []):
            mp = [(m.get("form", ""), m.get("label", ""))
                  for m in s.get("MP", []) or []]
            gform = s.get("form", "")
            wsd = []
            for w in s.get("WSD", []) or []:
                sid = str(w.get("sense_id", "")).lstrip("0") or "0"
                wsd.append((w.get("form", ""), sid, w.get("pos", "")))
            gold[s["id"]] = {"mp": mp, "wsd": wsd, "form": gform}
    return gold


def load_ours(ids):
    """01 레이어(tagged)와 02 레이어(sense)에서 대상 발화만 수집."""
    ours_mp = {}
    for fp in RAW24.glob("*.csv"):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["utt_id"] in ids:
                    seq = []
                    for tok in row["tagged"].split(" "):
                        for unit in tok.split("+"):
                            mo, _, tg = unit.rpartition("/")
                            if mo:
                                seq.append((mo, tg))
                    ours_mp[row["utt_id"]] = (seq, row["form"])
    ours_sense = defaultdict(list)  # utt -> [(morph, tag, sense, method)]
    for fp in SENSE24.glob("*.csv"):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["utt_id"] in ids and row["sense_id"]:
                    ours_sense[row["utt_id"]].append(
                        (row["morph"], row["tag"], row["sense_id"],
                         row["method"]))
    return ours_mp, ours_sense


def prf(gold_seq, our_seq):
    g, o = Counter(gold_seq), Counter(our_seq)
    tp = sum((g & o).values())
    p = tp / sum(o.values()) if o else 0
    r = tp / sum(g.values()) if g else 0
    return tp, sum(o.values()), sum(g.values()), p, r


def main() -> int:
    print("gold 로드...", flush=True)
    gold = load_gold()
    ids = set(gold)
    print(f"  {len(gold):,}문장", flush=True)
    print("우리 레이어 수집(2024 전체 스캔)...", flush=True)
    ours_mp, ours_sense = load_ours(ids)
    print(f"  01 매칭 {len(ours_mp):,} / 02 매칭 {len(ours_sense):,}", flush=True)

    # A) 형태소 채점 (전체 + 동일문장 부분집합)
    tp_sum = o_sum = g_sum = exact = 0
    stp = so = sg = same_n = 0  # 동일문장(form 일치) 부분집합
    mism = []
    for uid, gd in gold.items():
        ours, oform = ours_mp.get(uid, ([], ""))
        tp, o, g, p, r = prf(gd["mp"], ours)
        tp_sum += tp; o_sum += o; g_sum += g
        if gd["form"].strip() == oform.strip():
            same_n += 1
            stp += tp; so += o; sg += g
        if gd["mp"] == ours:
            exact += 1
        elif len(mism) < 200:
            mism.append((uid, " ".join(f"{a}/{b}" for a, b in gd["mp"][:12]),
                         " ".join(f"{a}/{b}" for a, b in ours[:12])))
    P = tp_sum / o_sum; R = tp_sum / g_sum; F = 2 * P * R / (P + R)
    sP = stp / so if so else 0; sR = stp / sg if sg else 0
    sF = 2 * sP * sR / (sP + sR) if sP + sR else 0

    # B) 의미번호 채점 (형태·태그 일치 항목 기준)
    meth = defaultdict(lambda: [0, 0])   # method -> [일치, 전체]
    special = gold_only = 0
    s_mism = []
    for uid, gd in gold.items():
        pool = defaultdict(list)
        for mo, tg, sid, me in ours_sense.get(uid, []):
            pool[(mo, tg)].append((sid, me))
        for form, gsid, pos in gd["wsd"]:
            if gsid in SPECIAL:
                special += 1
                continue
            cands = pool.get((form, pos))
            if not cands:
                gold_only += 1
                continue
            sid, me = cands[0]
            grp = me.split("(")[0]
            meth[grp][1] += 1
            if sid == gsid:
                meth[grp][0] += 1
            elif len(s_mism) < 200:
                s_mism.append((uid, form, pos, gsid, sid, grp))

    lines = [
        "=== 다층위 2025 구어부 대비 파이프라인 채점 ===",
        f"대상: {len(gold):,}문장 (2024 발화 부분집합, ID 직접 일치)",
        "",
        "[A] 형태소 (바른 vs 공식 MP) — (형태,태그) 다중집합 기준",
        f"  전체: Precision {P:.4f} / Recall {R:.4f} / F1 {F:.4f}",
        f"  동일문장 부분집합({same_n:,}문장 — 다층위 정제로 문장이 바뀌지"
        f" 않은 경우): P {sP:.4f} / R {sR:.4f} / F1 {sF:.4f}",
        f"  문장 완전일치: {exact:,}/{len(gold):,} ({exact/len(gold)*100:.1f}%)",
        "",
        "[B] 의미번호 (우리 레이어 vs 공식 WSD) — 방법별 정확도",
    ]
    tot_ok = tot_all = 0
    for me, (ok, al) in sorted(meth.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"  {me:12s} {ok:,}/{al:,} ({ok/al*100:.1f}%)")
        tot_ok += ok; tot_all += al
    lines += [
        f"  전체         {tot_ok:,}/{tot_all:,} ({tot_ok/tot_all*100:.1f}%)",
        f"  (특수코드 제외 {special:,} / 우리 미부여·형태불일치 {gold_only:,})",
    ]
    report = "\n".join(lines)
    (OUT_DIR / "validation_multilayer_report.txt").write_text(
        report, encoding="utf-8")
    with open(OUT_DIR / "validation_mp_mismatch_sample.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "gold_mp", "ours_mp"])
        w.writerows(mism)
    with open(OUT_DIR / "validation_sense_mismatch_sample.csv", "w",
              newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "form", "pos", "gold_sense", "our_sense", "method"])
        w.writerows(s_mism)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""다층위 2025 구어부 gold 레이어 수입 → 10_LAYERS/06_multilayer_gold/.

대상: SXML 16,439문장 (= 우리 2024 발화 부분집합, ID 직접 조인 가능).
산출물 (전부 utt_id 키):
  gold_index.csv  발화 목록 (프리미엄 표본 필터용)
  gold_mp.csv     공식 형태소 분석 (utt_id, seq, form, label, word_id)
  gold_wsd.csv    공식 의미번호 (utt_id, word_id, form, pos, sense_id)
  gold_dp.csv     구문 의존구조 (utt_id, word_id, word_form, head, label)
  gold_srl.csv    의미역 (utt_id, pred_*, role, arg_form, arg_word_ids)
  gold_za.csv     무형 대용어 복원 (utt_id, pred, restored, antecedent)
실행: python import_multilayer_gold.py
"""
import csv
import json
import sys
from pathlib import Path

SXML = Path(r"D:\00_RAW\reference\NIKL_Multi-layered_2025_v1.0\SXML2502512312.json")
OUT = Path(r"D:\10_LAYERS\06_multilayer_gold")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm_sense(v):
    return str(v).lstrip("0") or "0"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(SXML.read_text(encoding="utf-8"))
    f_idx = open(OUT / "gold_index.csv", "w", newline="", encoding="utf-8-sig")
    f_mp = open(OUT / "gold_mp.csv", "w", newline="", encoding="utf-8-sig")
    f_wsd = open(OUT / "gold_wsd.csv", "w", newline="", encoding="utf-8-sig")
    f_dp = open(OUT / "gold_dp.csv", "w", newline="", encoding="utf-8-sig")
    f_srl = open(OUT / "gold_srl.csv", "w", newline="", encoding="utf-8-sig")
    f_za = open(OUT / "gold_za.csv", "w", newline="", encoding="utf-8-sig")
    w_idx = csv.writer(f_idx); w_idx.writerow(["utt_id", "form", "speaker_id"])
    w_mp = csv.writer(f_mp); w_mp.writerow(["utt_id", "seq", "form", "label", "word_id"])
    w_wsd = csv.writer(f_wsd); w_wsd.writerow(["utt_id", "word_id", "form", "pos", "sense_id"])
    w_dp = csv.writer(f_dp); w_dp.writerow(["utt_id", "word_id", "word_form", "head", "label"])
    w_srl = csv.writer(f_srl); w_srl.writerow(
        ["utt_id", "pred_word_id", "pred_lemma", "pred_sense",
         "role", "arg_form", "arg_word_ids"])
    w_za = csv.writer(f_za); w_za.writerow(
        ["utt_id", "pred_form", "pred_word_id", "restored_form",
         "restored_type", "antecedent_form", "antecedent_sentence_id"])

    counts = {"idx": 0, "mp": 0, "wsd": 0, "dp": 0, "srl": 0, "za": 0}
    for doc in data.get("document", []):
        for s in doc.get("sentence", []):
            uid = s["id"]
            w_idx.writerow([uid, s.get("form", ""), s.get("speaker_id", "")])
            counts["idx"] += 1
            for i, m in enumerate(s.get("MP", []) or [], 1):
                w_mp.writerow([uid, i, m.get("form", ""), m.get("label", ""),
                               m.get("word_id", "")])
                counts["mp"] += 1
            for x in s.get("WSD", []) or []:
                w_wsd.writerow([uid, x.get("word_id", ""), x.get("form", ""),
                                x.get("pos", ""), norm_sense(x.get("sense_id", ""))])
                counts["wsd"] += 1
            for d in s.get("DP", []) or []:
                w_dp.writerow([uid, d.get("word_id", ""), d.get("word_form", ""),
                               d.get("head", ""), d.get("label", "")])
                counts["dp"] += 1

            for sr in s.get("SRL", []) or []:
                pred = sr.get("predicate") or {}
                if isinstance(pred, list):
                    pred = pred[0] if pred else {}
                base = [uid, pred.get("word_id", ""), pred.get("lemma", ""),
                        norm_sense(pred.get("sense_id", ""))]
                for a in (sr.get("argument") or []) + (sr.get("adjunct") or []):
                    wid = a.get("word_id", [])
                    if not isinstance(wid, list):
                        wid = [wid]
                    w_srl.writerow(base + [a.get("label", ""),
                                           a.get("form", ""),
                                           "|".join(map(str, wid))])
                    counts["srl"] += 1
            for z in s.get("ZA", []) or []:
                pred = z.get("predicate") or {}
                for e in z.get("ellipsis") or []:
                    rest = e.get("restored") or {}
                    ants = e.get("antecedent") or []
                    if isinstance(ants, dict):
                        ants = [ants]
                    ant = ants[0] if ants else {}
                    w_za.writerow([uid, pred.get("form", ""),
                                   pred.get("word_id", ""),
                                   rest.get("form", ""), rest.get("type", ""),
                                   ant.get("form", ""),
                                   ant.get("sentence_id", "")])
                    counts["za"] += 1
    for f in (f_idx, f_mp, f_wsd, f_dp, f_srl, f_za):
        f.close()
    print("완료:", ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

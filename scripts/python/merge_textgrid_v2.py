"""표준 TextGrid 직접 생성 (tier 표준 v2) — MFA DB에서 바로 내보내기.

MFA의 불안정한 export를 우회: 정렬 DB(word/phone 구간)를 직접 읽어
표준 3-tier TextGrid(words, phones, utterance)를 생성한다.
(prosody tier는 추후 온디맨드 — STANDARD_textgrid_tiers.md 참조)

출력: D:/20_AUDIO/06_textgrid_merged/2025/{세션}/{utt_id}.TextGrid
재개 가능(기존 파일 건너뜀). 단일 프로세스라 DB 잠금 문제 없음.
실행: python merge_textgrid_v2.py [--limit 50]   (사전에 _build_indexes.py 필요)
"""
import argparse
import csv
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

DB = Path(r"D:\mfa_temp\2025\2025.db")
RAW_2025 = Path(r"D:\10_LAYERS\01_bareun_raw\NIKL_DIALOGUE_2025_v1.0")
OUT_ROOT = Path(r"D:\20_AUDIO\06_textgrid_merged\2025")
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SILENCE_WORDS = {"<eps>", "sil", "<unk>"}
SILENCE_PHONES = {"sil", "sp", ""}


def esc(text: str) -> str:
    return text.replace('"', '""')


def interval_tier(name, intervals, dur):
    """intervals: [(begin, end, text)] -> TextGrid item 텍스트."""
    fixed = []
    for b, e, t in intervals:
        e = min(e, dur)
        if e - b > 1e-6:
            fixed.append((b, e, t))
    if fixed and dur - fixed[-1][1] > 1e-6:
        fixed.append((fixed[-1][1], dur, ""))
    lines = [f'        class = "IntervalTier"',
             f'        name = "{name}"',
             f"        xmin = 0",
             f"        xmax = {dur:.6f}",
             f"        intervals: size = {len(fixed)}"]
    for i, (b, e, t) in enumerate(fixed, 1):
        lines += [f"        intervals [{i}]:",
                  f"            xmin = {b:.6f}",
                  f"            xmax = {e:.6f}",
                  f'            text = "{esc(t)}"']
    return lines


def write_textgrid(path, dur, words, phones, form):
    tiers = [
        interval_tier("words", words, dur),
        interval_tier("phones", phones, dur),
        interval_tier("utterance", [(0.0, dur, form)], dur),
    ]
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {dur:.6f}", "tiers? <exists>",
             f"size = {len(tiers)}", "item []:"]
    for i, tier in enumerate(tiers, 1):
        lines.append(f"    item [{i}]:")
        lines.extend(tier)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_forms():
    forms = {}
    for fp in RAW_2025.glob("*.csv"):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                forms[row["utt_id"]] = row["form"]
    return forms


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="테스트용 발화 수 제한")
    args = ap.parse_args()

    print("form 텍스트 로드...", flush=True)
    forms = load_forms()
    print(f"  {len(forms):,}개", flush=True)

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=120)
    cur = con.cursor()
    print("라벨 사전 로드...", flush=True)
    word_lab = dict(cur.execute("SELECT id, word FROM word"))
    phone_lab = dict(cur.execute("SELECT id, phone FROM phone"))
    print(f"  단어 {len(word_lab):,} / 음소 {len(phone_lab):,}", flush=True)

    utts = cur.execute(
        "SELECT u.id, f.name, u.end FROM utterance u "
        "JOIN file f ON u.file_id = f.id ORDER BY f.name").fetchall()
    if args.limit:
        utts = utts[: args.limit]
    print(f"발화 {len(utts):,}개 내보내기 시작", flush=True)

    # 세션 단위로 묶어 일괄 조회 (속도 최적화)
    sessions = defaultdict(list)
    for uid, name, dur in utts:
        sessions[name.split(".")[0]].append((uid, name, dur))

    made = skipped = no_align = 0
    t0 = time.time()
    for si, (session, su) in enumerate(sorted(sessions.items()), 1):
        out_dir = OUT_ROOT / session
        todo = [(uid, name, dur) for uid, name, dur in su
                if not (out_dir / f"{name}.TextGrid").exists()]
        skipped += len(su) - len(todo)
        if not todo:
            continue
        ids = [u[0] for u in todo]
        ph = ",".join("?" * len(ids))
        wmap = defaultdict(list)
        for uid, b, e, w in cur.execute(
                f"SELECT utterance_id, begin, end, word_id FROM word_interval "
                f"WHERE utterance_id IN ({ph})", ids):
            wmap[uid].append((b, e, w))
        pmap = defaultdict(list)
        for uid, b, e, p in cur.execute(
                f"SELECT utterance_id, begin, end, phone_id FROM phone_interval "
                f"WHERE utterance_id IN ({ph})", ids):
            pmap[uid].append((b, e, p))
        out_dir.mkdir(parents=True, exist_ok=True)
        for uid, name, dur in todo:
            wrows = sorted(wmap.get(uid, []))
            if not wrows:
                no_align += 1
                continue
            prows = sorted(pmap.get(uid, []))
            words = [(b, e, "" if word_lab.get(w, "") in SILENCE_WORDS
                      else word_lab.get(w, "")) for b, e, w in wrows]
            phones = [(b, e, "" if phone_lab.get(p, "") in SILENCE_PHONES
                       else phone_lab.get(p, "")) for b, e, p in prows]
            write_textgrid(out_dir / f"{name}.TextGrid", float(dur),
                           words, phones, forms.get(name, ""))
            made += 1
        if si % 50 == 0:
            rate = made / (time.time() - t0)
            eta = (len(utts) - made - skipped) / rate / 3600 if rate else 0
            print(f"  세션 {si:,}/{len(sessions):,} (생성 {made:,}, "
                  f"{rate:.0f}발화/s, 남은 예상 {eta:.1f}h)", flush=True)
    con.close()
    print(f"완료: 생성 {made:,} / 건너뜀 {skipped:,} / 정렬없음 {no_align:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

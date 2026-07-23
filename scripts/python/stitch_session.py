# -*- coding: utf-8 -*-
"""stitch_session.py - 발화 클립(wav)을 utt_id 순으로 이어붙여
연속 wav + 정렬 TextGrid로 재구성 (원본 연속본이 없어도 '이어 보고 듣기').

NIKL 배포가 발화 단위 클립이라 원본 연속 녹음이 없다는 전제. 클립 연결이므로:
 · 발화 간 원본 침묵은 제거됨(시간은 '연결 기준', 원본 세션 시간 아님).
 · 발화겹침(note '발화겹침')은 직렬화됨.
tier: utterance(form)·speaker + words/phones/morphemes(각 클립 4-tier에서 오프셋).

사용:
  python stitch_session.py --session SDRW2000000001 --out C:\\stitch
  python stitch_session.py --around SDRW2000000001.1.1.175 --window 8 --out C:\\stitch
  옵션: --tg-dir <폴더>(TextGrid를 locate 대신 이 폴더에서 rglob) / --no-align
"""
import argparse, csv, re, sys, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P
from locate_utt import locate, parse_utt
from realign_eojeol_build_corpus import YEAR_DIRS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALIGN_TIERS = ["words", "phones", "morphemes"]


def utt_key(uid):
    return tuple(int(x) for x in uid.split(".")[1:])


def parse_tg_tiers(path):
    """long TextGrid -> {tier: [(xmin,xmax,text)]} (IntervalTier)."""
    tiers, name, xmin = {}, None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        m = re.match(r'name = "(.*)"$', s)
        if m:
            name = m.group(1); tiers.setdefault(name, []); xmin = None; continue
        if name is None:
            continue
        a = re.match(r'xmin = ([\d.]+)$', s)
        b = re.match(r'xmax = ([\d.]+)$', s)
        t = re.match(r'text = "(.*)"$', s)
        if a:
            xmin = float(a.group(1))
        elif b:
            xmax = float(b.group(1))
        elif t is not None and xmin is not None:
            tiers[name].append((xmin, xmax, t.group(1))); xmin = None
    return tiers


def tile(intervals, total):
    """겹침 클램프·빈틈 채워 [0,total] 완전 타일링(Praat 유효)."""
    out, cur = [], 0.0
    for a, b, txt in sorted(intervals):
        a = max(a, cur); b = max(b, a)
        if a > cur + 1e-9:
            out.append((cur, a, ""))
        if b > a:
            out.append((a, b, txt)); cur = b
    if cur < total - 1e-9:
        out.append((cur, total, ""))
    return out


def esc(t):
    return t.replace('"', '""')


def write_textgrid(path, total, tier_data):
    """tier_data: list of (name, [(xmin,xmax,text)]). 모두 [0,total] 타일링 전제."""
    L = ['File type = "ooTextFile"', 'Object class = "TextGrid"', '',
         'xmin = 0', f'xmax = {total}', 'tiers? <exists>',
         f'size = {len(tier_data)}', 'item []:']
    for i, (name, ivs) in enumerate(tier_data, 1):
        L += [f'    item [{i}]:', '        class = "IntervalTier"',
              f'        name = "{name}"', '        xmin = 0',
              f'        xmax = {total}', f'        intervals: size = {len(ivs)}']
        for j, (a, b, txt) in enumerate(ivs, 1):
            L += [f'        intervals [{j}]:', f'            xmin = {a}',
                  f'            xmax = {b}', f'            text = "{esc(txt)}"']
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


def find_tg(uid, loc, tg_dir):
    if tg_dir:
        hits = list(Path(tg_dir).rglob(f"{uid}.TextGrid"))
        return hits[0] if hits else None
    p = loc["textgrid_eojeol"]
    return p if p.exists() else None


def ordered_utts(session, year):
    bareun = P("layers") / "01_bareun_raw" / YEAR_DIRS[year] / f"{session}.csv"
    rows = list(csv.DictReader(open(bareun, encoding="utf-8")))
    rows.sort(key=lambda r: utt_key(r["utt_id"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session")
    ap.add_argument("--around", help="발화 ID 중심으로 --window개 앞뒤")
    ap.add_argument("--window", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tg-dir", default="", help="TextGrid를 이 폴더에서 찾음(rglob)")
    ap.add_argument("--no-align", action="store_true", help="words/phones tier 제외")
    args = ap.parse_args()

    session = args.session or (args.around.split(".")[0] if args.around else None)
    if not session:
        sys.exit("--session 또는 --around 필요")
    year, _ = parse_utt(session), None
    year = parse_utt(session)[0]
    rows = ordered_utts(session, year)
    if args.around:
        ids = [r["utt_id"] for r in rows]
        if args.around not in ids:
            sys.exit(f"{args.around} 세션에 없음")
        c = ids.index(args.around)
        rows = rows[max(0, c - args.window): c + args.window + 1]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    tag = args.around.replace(".", "_") if args.around else session
    wav_out = out / f"{tag}_stitched.wav"
    tg_out = out / f"{tag}_stitched.TextGrid"

    frames, params, t = [], None, 0.0
    utt_iv, spk_iv = [], []
    align = {k: [] for k in ALIGN_TIERS}
    used, skipped = 0, 0
    for r in rows:
        uid, form, spk = r["utt_id"], r.get("form", ""), r.get("speaker_id", "")
        loc = locate(uid)
        w = loc["wav"]
        if not w.exists():
            skipped += 1; continue
        wf = wave.open(str(w)); p = wf.getparams()
        if params is None:
            params = p
        elif (p.nchannels, p.framerate, p.sampwidth) != \
                (params.nchannels, params.framerate, params.sampwidth):
            skipped += 1; wf.close(); continue
        data = wf.readframes(wf.getnframes()); wf.close()
        dur = wf.getnframes() / params.framerate
        frames.append(data)
        utt_iv.append((t, t + dur, form)); spk_iv.append((t, t + dur, spk))
        if not args.no_align:
            tgp = find_tg(uid, loc, args.tg_dir)
            if tgp:
                td = parse_tg_tiers(tgp)
                for k in ALIGN_TIERS:
                    for a, b, txt in td.get(k, []):
                        align[k].append((t + a, t + b, txt))
        t += dur; used += 1

    if used == 0:
        sys.exit("사용 가능한 wav 없음")
    total = t
    with wave.open(str(wav_out), "wb") as wo:
        wo.setparams(params)
        wo.writeframes(b"".join(frames))
    tier_data = [("utterance", tile(utt_iv, total)), ("speaker", tile(spk_iv, total))]
    if not args.no_align:
        for k in ALIGN_TIERS:
            if align[k]:
                tier_data.append((k, tile(align[k], total)))
    write_textgrid(tg_out, total, tier_data)
    print(f"발화 {used}개 연결 (건너뜀 {skipped}) · 길이 {total:.1f}s")
    print(f"wav: {wav_out}")
    print(f"TextGrid: {tg_out}  (tier: {[n for n,_ in tier_data]})")


if __name__ == "__main__":
    raise SystemExit(main())

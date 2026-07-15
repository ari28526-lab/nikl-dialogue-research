# -*- coding: utf-8 -*-
"""운율 파일럿 (Colab 실행용) — 표본 500발화에 운율 정보 부여.

산출 (Drive의 prosody_pilot/results/):
  prosody_utts.csv   발화 단위: IP/AP 경계, 경계성조, F0 통계, 휴지, 말속도,
                     Momel 목표점(가능 시)
  tg/*.TextGrid      prosody tier(AP 구간, IP 경계·성조 라벨) 추가 사본
규칙 v0 (투명·보정 가능):
  IP 경계 = 휴지 >= 0.15s 또는 발화 끝 / 경계성조 = 말미 0.15s F0 기울기
  AP 경계 = IP 내부에서 F0 상승 리셋(>=2st) 또는 미세 휴지(0.05-0.15s)
"""
import csv
import json
import math
import sys
from pathlib import Path

import parselmouth
from textgrid import TextGrid

# ── 표본마다 이 두 줄만 바꾸면 됨 (현상별 재사용) ──
SAMPLE_NAME = "sample500"      # /content/{SAMPLE_NAME} 에 압축 해제돼 있어야 함
RESULT_NAME = "results"        # Drive의 prosody_pilot/{RESULT_NAME}/ 에 저장
# ──────────────────────────────────────────────
SAMPLE = Path(f"/content/{SAMPLE_NAME}")
DRIVE = Path("/content/drive/MyDrive/DATA_2026/prosody_pilot")
OUT = DRIVE / RESULT_NAME
TG_OUT = OUT / "tg"
PAUSE_IP = 0.15
PAUSE_AP = 0.05
RISE_ST = 2.0
TONE_ST = 1.5

HAVE_KOINA = False
try:
    sys.path.insert(0, "/content/KOINA/src")
    import os
    os.chmod("/content/KOINA/src/lib/momel/momel_linux", 0o755)
    from transcribe.momel import generate_momel_labels  # noqa
    HAVE_KOINA = True
    print("KOINA Momel 사용 가능")
except Exception as e:
    print(f"KOINA Momel 불가({type(e).__name__}) → parselmouth만 사용")


def st(hz_from, hz_to):
    """반음 차이."""
    if hz_from and hz_to and hz_from > 0 and hz_to > 0:
        return 12 * math.log2(hz_to / hz_from)
    return 0.0


def f0_at(pitch, t0, t1):
    """구간 내 유성 F0 (처음, 끝, 평균) — 없으면 None."""
    vals = []
    t = t0
    while t <= t1 + 1e-9:
        v = pitch.get_value_at_time(t)
        if v and not math.isnan(v):
            vals.append((t, v))
        t += 0.01
    if not vals:
        return None, None, None
    return vals[0][1], vals[-1][1], sum(v for _, v in vals) / len(vals)


def load_tiers(tg_path):
    tg = TextGrid.fromFile(str(tg_path))
    tiers = {t.name: t for t in tg.tiers}
    words = [(iv.minTime, iv.maxTime, iv.mark.strip())
             for iv in tiers["words"] if iv.mark.strip()]
    sils = [(iv.minTime, iv.maxTime)
            for iv in tiers["words"] if not iv.mark.strip()]
    phones = [(iv.minTime, iv.maxTime, iv.mark.strip())
              for iv in tiers["phones"] if iv.mark.strip()]
    return tg, words, sils, phones


def pause_after(word_end, sils, next_start):
    """단어 끝~다음 단어 시작 사이 무성 길이."""
    return max(0.0, (next_start or word_end) - word_end)


def analyze(utt_id, wav_path, tg_path):
    snd = parselmouth.Sound(str(wav_path))
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=75, pitch_ceiling=500)
    tg, words, sils, phones = load_tiers(tg_path)
    if not words:
        return None
    dur = snd.get_total_duration()

    # 단어 경계 특징 → IP/AP 판정
    boundaries = []  # (word_idx, pause, f0_end, f0_next_start)
    for i, (b, e, w) in enumerate(words):
        nxt = words[i + 1][0] if i + 1 < len(words) else None
        pz = (nxt - e) if nxt is not None else 999.0  # 발화 끝 = IP
        _, f0_end, _ = f0_at(pitch, max(b, e - 0.12), e)
        f0_nx = None
        if nxt is not None:
            ne = words[i + 1][1]
            f0_nx, _, _ = f0_at(pitch, nxt, min(ne, nxt + 0.12))
        boundaries.append((i, pz, f0_end, f0_nx))

    ip_after = set()
    ap_after = set()
    for i, pz, f0e, f0n in boundaries:
        if pz >= PAUSE_IP:
            ip_after.add(i)
        elif pz >= PAUSE_AP:
            ap_after.add(i)
        elif f0e and f0n and st(f0e, f0n) >= RISE_ST:
            ap_after.add(i)  # F0 상승 리셋

    # 경계성조 (IP말 0.15s 기울기)
    tones = []
    for i in sorted(ip_after):
        b, e, w = words[i]
        f0a, f0b, _ = f0_at(pitch, max(b, e - 0.15), e)
        if f0a and f0b:
            d = st(f0a, f0b)
            tones.append("H%" if d >= TONE_ST else "L%" if d <= -TONE_ST else "F%")
        else:
            tones.append("NA")

    # AP 구간 구성 (IP 경계는 AP 경계를 겸함)
    marks = sorted(ip_after | ap_after)
    aps = []
    start_w = 0
    for i in marks:
        aps.append((words[start_w][0], words[i][1],
                    "IP" if i in ip_after else "AP"))
        start_w = i + 1
    if start_w < len(words):
        aps.append((words[start_w][0], words[-1][1], "IP"))

    # F0 통계·말속도·휴지
    f00, f01, f0m = f0_at(pitch, 0, dur)
    vals = [pitch.get_value_at_time(t / 100) for t in range(int(dur * 100))]
    vals = [v for v in vals if v and not math.isnan(v)]
    f0_min = min(vals) if vals else None
    f0_max = max(vals) if vals else None
    slope = st(f00, f01) / dur if (f00 and f01 and dur) else None
    total_pause = sum(e - b for b, e in sils)
    rate = len(phones) / (dur - total_pause) if dur > total_pause else None

    momel = ""
    if HAVE_KOINA:
        try:
            ts, fs = generate_momel_labels(str(wav_path))[:2]
            momel = json.dumps([[round(a, 3), round(b, 1)]
                                for a, b in zip(ts, fs)])
        except Exception:
            momel = ""

    return {"dur": dur, "aps": aps, "tones": tones, "tg": tg,
            "n_words": len(words), "f0_mean": f0m, "f0_min": f0_min,
            "f0_max": f0_max, "f0_slope": slope, "pause": total_pause,
            "rate": rate, "momel": momel}


def add_prosody_tier(tg, aps, tones, dur, out_path):
    from textgrid import IntervalTier
    # wav 길이와 TextGrid xmax의 미세 반올림 차이 방지: TG 기준으로 절단
    dur = float(tg.maxTime) if tg.maxTime else dur
    tier = IntervalTier(name="prosody", minTime=0, maxTime=dur)
    ti = 0
    for b, e, kind in aps:
        e = min(float(e), dur)
        b = min(float(b), dur)
        if e - b <= 1e-6:
            if kind == "IP":
                ti += 1
            continue
        label = kind
        if kind == "IP" and ti < len(tones):
            label = f"IP:{tones[ti]}"
            ti += 1
        try:
            tier.add(b, e, label)
        except ValueError:
            pass
    tg.append(tier)
    tg.write(str(out_path))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TG_OUT.mkdir(exist_ok=True)
    wavs = sorted(SAMPLE.glob("*.wav"))
    print(f"발화 {len(wavs)}개 처리 시작 (KOINA Momel: {HAVE_KOINA})")
    rows = []
    fail = 0
    for k, wav in enumerate(wavs, 1):
        uid = wav.stem
        tgp = SAMPLE / f"{uid}.TextGrid"
        if not tgp.exists():
            continue
        try:
            r = analyze(uid, wav, tgp)
        except Exception as e:
            print(f"  !! {uid}: {type(e).__name__}: {e}")
            fail += 1
            continue
        if not r:
            continue
        add_prosody_tier(r["tg"], r["aps"], r["tones"], r["dur"],
                         TG_OUT / f"{uid}.TextGrid")
        ip_b = "|".join(f"{e:.3f}" for _, e, kk in r["aps"] if kk == "IP")
        ap_b = "|".join(f"{e:.3f}" for _, e, kk in r["aps"] if kk == "AP")
        rows.append([uid, f"{r['dur']:.3f}", r["n_words"],
                     sum(1 for a in r["aps"] if a[2] == "AP") + sum(1 for a in r["aps"] if a[2] == "IP"),
                     sum(1 for a in r["aps"] if a[2] == "IP"),
                     ap_b, ip_b, "|".join(r["tones"]),
                     r["f0_mean"], r["f0_min"], r["f0_max"], r["f0_slope"],
                     f"{r['pause']:.3f}", r["rate"], r["momel"]])
        if k % 50 == 0:
            print(f"  {k}/{len(wavs)}")
    with open(OUT / "prosody_utts.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "dur", "n_words", "n_AP_total", "n_IP",
                    "ap_ends", "ip_ends", "boundary_tones",
                    "f0_mean", "f0_min", "f0_max", "f0_slope_st_per_s",
                    "pause_total", "phones_per_s", "momel_points"])
        w.writerows(rows)
    print(f"완료: {len(rows)}발화 (실패 {fail}) → {OUT}")


main()

# -*- coding: utf-8 -*-
"""build_g2p_pilot_corpus.py - MFA G2P 파일럿용 격리 코퍼스 생성.

한 세션의 wav + form(어절 한글)->lab 을 화자별 하위폴더로 모은다(1화자 함정 회피).
숫자·외국어 어절은 lab에서 제외(기존 make_labs와 동일). 원본·D: 산출 불건드림.
사용: python build_g2p_pilot_corpus.py --session SDRW2000000001 --year 2020 --out C:\\mfa_g2p_pilot\\corpus
"""
import argparse, csv, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P
import predict_pron as pp

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean_lab(form):
    """처리가능(한글) 어절만, 구두점 제거해 공백 결합. 없으면 ''."""
    out = []
    for eoj in form.split():
        if pp._is_processable(eoj):
            out.append("".join(c for c in eoj if pp.is_syllable(c)))
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--year", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = P("layers") / "01_bareun_raw"
    bareun = next((d / f"{args.session}.csv" for d in raw.iterdir()
                   if d.is_dir() and args.year in d.name
                   and (d / f"{args.session}.csv").exists()), None)
    if bareun is None:
        sys.exit(f"bareun CSV 없음: {args.session} ({args.year})")
    wav_dir = P("wav") / "individual"
    out = Path(args.out)

    copied, skip_form, skip_wav = 0, 0, 0
    for r in csv.DictReader(open(bareun, encoding="utf-8")):
        utt, form, spk = r["utt_id"], r.get("form", ""), r.get("speaker_id", "spk")
        lab = clean_lab(form)
        if not lab:
            skip_form += 1
            continue
        w = wav_dir / f"{utt}.wav"
        if not w.exists():
            skip_wav += 1
            continue
        d = out / spk
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(w, d / f"{utt}.wav")
        (d / f"{utt}.lab").write_text(lab, encoding="utf-8")
        copied += 1
    print(f"코퍼스: {out}")
    print(f"복사 발화: {copied}  (form 제외 {skip_form}, wav 없음 {skip_wav})")
    spks = sorted(p.name for p in out.iterdir() if p.is_dir())
    print(f"화자 폴더: {spks}")


if __name__ == "__main__":
    main()

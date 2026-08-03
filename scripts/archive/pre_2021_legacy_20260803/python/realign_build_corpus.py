"""정렬 실패 발화만 모아 재정렬용 MFA 코퍼스 구성 (2020-2025).

배경: 1차 정렬 후 .lab이 정리(삭제)돼 세션 폴더엔 wav만 남음. 재정렬하려면
      lab을 바른 원자료(01_bareun_raw)에서 재생성해야 함. wav은 그대로 있어
      하드링크로 무복사 재사용(같은 볼륨 D:).
대상: coverage_{year}.csv 의 has_wav=1 AND has_textgrid=0 (정렬 실패, 회수 후보).
      has_wav=0(원본 음성 없음)은 재정렬 불가 → 제외.
wav 배치: 2020-2024 = individual/{year}/{session}/{utt}.wav (세션 하위폴더)
          2025      = individual/2025/{utt}.wav (평면)
출력 코퍼스: {CORPUS_ROOT}/{year}/{session}/{utt}.wav(하드링크) + {utt}.lab
            세션 하위폴더 = MFA 화자 단위 (원 파이프라인과 동일 효과).
재개 가능: 코퍼스에 이미 wav 링크+lab 있으면 건너뜀.

실행: python realign_build_corpus.py --year 2023 [--pilot-sessions 5]
      python realign_build_corpus.py --year all
"""
import argparse
import csv
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

WAV_ROOT = Path(r"D:\20_AUDIO\03_wav\individual")
RAW = Path(r"D:\10_LAYERS\01_bareun_raw")
COV = Path(r"D:\10_LAYERS\05_audio_index")
CORPUS_ROOT = Path(r"D:\mfa_realign\corpus")
YEAR_DIRS = {
    "2020": "NIKL_DIALOGUE_2020_v1.4", "2021": "NIKL_DIALOGUE_2021_v1.1",
    "2022": "NIKL_DIALOGUE_2022_v1.0_JSON", "2023": "NIKL_DIALOGUE_2023_v1.1",
    "2024": "NIKL_DIALOGUE_2024_v1.0", "2025": "NIKL_DIALOGUE_2025_v1.0",
}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def tagged_to_lab(tagged: str) -> str:
    """태그 제거 + 형태소 공백 연결. 문장부호(S* 태그)는 제외.
    (make_labs_2025.py 와 동일 로직 — 원 정렬 입력과 일치 보장)"""
    morphs = []
    for tok in tagged.split(" "):
        for unit in tok.split("+"):
            mo, _, tg = unit.rpartition("/")
            if mo and not tg.startswith("S"):
                morphs.append(mo)
    return " ".join(morphs)


def failed_utts(year: str):
    """coverage_{year}.csv 에서 정렬 실패(wav 있고 TG 없음) utt_id 집합."""
    fp = COV / f"coverage_{year}.csv"
    if not fp.exists():
        sys.exit(f"커버리지 없음: {fp}")
    out = set()
    with open(fp, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["has_wav"] == "1" and r["has_textgrid"] == "0":
                out.add(r["utt_id"])
    return out


def wav_path(year: str, utt: str) -> Path | None:
    """실패 발화의 실제 wav 경로 (세션폴더 우선, 없으면 평면)."""
    sess = utt.split(".")[0]
    nested = WAV_ROOT / year / sess / f"{utt}.wav"
    if nested.exists():
        return nested
    flat = WAV_ROOT / year / f"{utt}.wav"
    if flat.exists():
        return flat
    return None


def link_or_copy(src: Path, dst: Path):
    """같은 볼륨이면 하드링크(무복사), 실패 시 복사."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def build_year(year: str, pilot_sessions: int) -> None:
    targets = failed_utts(year)
    print(f"[{year}] 정렬 실패 발화 {len(targets):,}개", flush=True)

    # 세션별로 필요한 lab 텍스트를 원자료에서 한 번에 수집
    by_session = defaultdict(set)
    for u in targets:
        by_session[u.split(".")[0]].add(u)
    sessions = sorted(by_session)
    if pilot_sessions:
        # 실패 발화가 많은 세션 우선(파일럿 대표성)
        sessions = sorted(sessions, key=lambda s: -len(by_session[s]))[:pilot_sessions]
        targets = set().union(*(by_session[s] for s in sessions))
        print(f"  파일럿: 상위 실패세션 {len(sessions)}개 / 발화 {len(targets):,}개",
              flush=True)

    raw_dir = RAW / YEAR_DIRS[year]
    lab_text = {}
    for s in sessions:
        fp = raw_dir / f"{s}.csv"
        if not fp.exists():
            print(f"  !! 원자료 없음: {fp.name}", flush=True)
            continue
        with open(fp, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["utt_id"] in by_session[s] and row["utt_id"] in targets:
                    lab_text[row["utt_id"]] = tagged_to_lab(row["tagged"])

    made = skipped = no_wav = empty = 0
    for s in sessions:
        out_sess = CORPUS_ROOT / year / s
        out_sess.mkdir(parents=True, exist_ok=True)
        for u in sorted(by_session[s] & targets):
            dst_wav = out_sess / f"{u}.wav"
            dst_lab = out_sess / f"{u}.lab"
            if dst_wav.exists() and dst_lab.exists():
                skipped += 1
                continue
            lab = lab_text.get(u, "")
            if not lab.strip():
                empty += 1
                continue
            src = wav_path(year, u)
            if src is None:
                no_wav += 1
                continue
            if not dst_wav.exists():
                link_or_copy(src, dst_wav)
            dst_lab.write_text(lab, encoding="utf-8")
            made += 1
    print(f"[{year}] 완료: 구성 {made:,} / 건너뜀 {skipped:,} / "
          f"wav 없음 {no_wav:,} / 빈 lab {empty:,}", flush=True)
    print(f"  코퍼스 위치: {CORPUS_ROOT / year}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True,
                    help="2020..2025 또는 all")
    ap.add_argument("--pilot-sessions", type=int, default=0,
                    help="지정 시 실패 많은 세션 상위 N개만(파일럿)")
    args = ap.parse_args()
    years = sorted(YEAR_DIRS) if args.year == "all" else [args.year]
    for y in years:
        if y not in YEAR_DIRS:
            sys.exit(f"알 수 없는 연도: {y}")
        build_year(y, args.pilot_sessions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

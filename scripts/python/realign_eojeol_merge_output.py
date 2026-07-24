"""어절 재정렬 MFA 출력 + 기존 형태소 경계 → 4-tier 표준 TextGrid (목적 B).

한 파일에 다 담는다:
  tier1 words     = 어절            (신규 어절 MFA 정렬)
  tier2 phones    = 연결 실제 발음   (신규, 교정된 것: 것을→거슬)
  tier3 morphemes = 형태소 경계      (기존 06_textgrid_merged의 words tier 재사용)
  tier4 utterance = form
입력: D:/mfa_eojeol/out/{year}/{session}/{utt}.TextGrid  (신규 어절 정렬)
      D:/20_AUDIO/06_textgrid_merged/{year}/{session}/{utt}.TextGrid (기존 형태소, 읽기만)
      01_bareun_raw (form)
출력: D:/20_AUDIO/06_textgrid_eojeol/{year}/{session}/{utt}.TextGrid  (4-tier)
  ※ 기존 형태소 폴더(06_textgrid_merged)는 읽기 전용 — 절대 안 건드림.
  ※ 형태소 정렬이 없는 발화는 morphemes tier를 빈 채로 두고 표시(morph_missing 집계).
재개 가능(대상 위치에 이미 있으면 건너뜀).
실행: python realign_eojeol_merge_output.py --year 2020
"""
import argparse
import csv
import os
import re
import sys
import time
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 형제 모듈 import 보장
from merge_textgrid_v2 import interval_tier              # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid, YEAR_DIRS  # noqa: E402
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    archive_copy,
    atomic_write_json,
    new_run_id,
    promote_staged,
    staged_text_writer,
)

MFA_OUT = P("mfa_output_secondary")
MORPH_TG = P("textgrid_merged")   # 기존 형태소 경계 소스(불변)
RAW = P("layers") / "01_bareun_raw"
OUT_ROOT = P("textgrid_eojeol")
STATE_ROOT = P("mfa_state")
YEAR_DIRS = {**YEAR_DIRS, "2025": "NIKL_DIALOGUE_2025_v1.0"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def validate_4tier(path, expected_dur=None):
    """tier 순서·시간 경계·핵심 내용이 유효한지 검사."""
    result = {"valid": False, "reasons": [], "duration": None}
    try:
        text = path.read_text(encoding="utf-8")
        names = re.findall(r'^\s*name = "([^"]+)"\s*$', text, flags=re.MULTILINE)
        expected_names = ["words", "phones", "morphemes", "utterance"]
        if names != expected_names:
            result["reasons"].append(
                f"tier order mismatch: expected={expected_names} actual={names}"
            )
        dur, tiers = parse_mfa_textgrid(path)
        result["duration"] = dur
        if dur is None or dur <= 0:
            result["reasons"].append(f"invalid duration: {dur}")
        if expected_dur is not None and dur is not None \
                and abs(dur - expected_dur) > 0.001:
            result["reasons"].append(
                f"duration mismatch: expected={expected_dur} actual={dur}"
            )
        for tier_name in expected_names:
            if tier_name not in tiers:
                result["reasons"].append(f"missing tier: {tier_name}")
                continue
            for start, end, _label in tiers[tier_name]:
                if start < -1e-6 or end < start or (
                    dur is not None and end > dur + 0.001
                ):
                    result["reasons"].append(
                        f"invalid interval {tier_name}: {start}..{end}/{dur}"
                    )
                    break
        if not tiers.get("words"):
            result["reasons"].append("empty words tier")
        if not tiers.get("phones"):
            result["reasons"].append("empty phones tier")
        if not tiers.get("utterance"):
            result["reasons"].append("empty utterance tier")
        result["valid"] = not result["reasons"]
    except Exception as exc:
        result["reasons"].append(f"{type(exc).__name__}: {exc}")
    return result


def write_4tier(path, dur, words, phones, morphemes, form):
    tiers = [
        interval_tier("words", words, dur),
        interval_tier("phones", phones, dur),
        interval_tier("morphemes", morphemes or [(0.0, dur, "")], dur),
        interval_tier("utterance", [(0.0, dur, form)], dur),
    ]
    lines = ['File type = "ooTextFile"', 'Object class = "TextGrid"', "",
             "xmin = 0", f"xmax = {dur:.6f}", "tiers? <exists>",
             f"size = {len(tiers)}", "item []:"]
    for i, tier in enumerate(tiers, 1):
        lines.append(f"    item [{i}]:")
        lines.extend(tier)
    with staged_text_writer(path, encoding="utf-8", newline="\n") as (stream, tmp):
        stream.write("\n".join(lines) + "\n")
    validation = validate_4tier(tmp, expected_dur=dur)
    if not validation["valid"]:
        raise RuntimeError(
            f"임시 4-tier 검증 실패({tmp}): "
            + "; ".join(validation["reasons"])
        )
    promote_staged(tmp, path)


def load_forms(year, sessions):
    forms = {}
    ydir = RAW / YEAR_DIRS[year]
    for s in sessions:
        fp = ydir / f"{s}.csv"
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"utt_id", "form"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{fp.name} 필수 컬럼 누락: {sorted(missing)}")
            for row in reader:
                if row["utt_id"] in forms:
                    raise ValueError(f"중복 utt_id: {row['utt_id']}")
                forms[row["utt_id"]] = row["form"]
    return forms


def morpheme_tier(year, session, utt):
    """기존 형태소 TextGrid에서 words tier(=형태소 경계) 추출. 없으면 None."""
    fp = MORPH_TG / year / session / f"{utt}.TextGrid"
    if not fp.exists():
        return None
    try:
        _, tiers = parse_mfa_textgrid(fp)
        return tiers.get("words", [])
    except Exception:
        return None


def iter_session_tgs(src_year: Path):
    """(세션명, TextGrid 경로 목록) 생성 — 세션 하위폴더·평면 모두 지원.
    ★ 2026-07-17 실측: wav 코퍼스가 평면인 연도(2020·2021·2025)는 MFA 출력도
    평면(루트에 TextGrid 직접) → 기존 '세션 폴더만' 가정이면 세션 0개로 조용히
    무시됨. 평면이면 파일명에서 세션명 유도(utt.split('.')[0])."""
    dir_names, tg_names = [], []
    for e in os.scandir(src_year):
        if e.is_dir():
            dir_names.append(e.name)
        elif e.name.endswith(".TextGrid"):
            tg_names.append(e.name)
    if dir_names:  # 세션 하위폴더 구조
        nsess = len(dir_names)
        for sname in sorted(dir_names):
            yield nsess, sname, sorted((src_year / sname).glob("*.TextGrid"))
    if tg_names:   # 평면 구조
        tg_names.sort()
        nsess = len({n.split(".")[0] for n in tg_names})
        for sname, grp in groupby(tg_names, key=lambda n: n.split(".")[0]):
            yield nsess, sname, [src_year / n for n in grp]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, choices=sorted(YEAR_DIRS))
    ap.add_argument("--mfa-out", default=str(MFA_OUT),
                    help="MFA 원출력 루트 (기본 D:; 러너는 C: SSD를 넘김)")
    ap.add_argument("--run-id", help="외부 실행 ID")
    args = ap.parse_args()
    run_id = args.run_id or new_run_id(f"merge_{args.year}")

    src_year = Path(args.mfa_out) / args.year
    if not src_year.exists():
        sys.exit(f"어절 재정렬 출력 없음: {src_year}")
    print(f"[{args.year}] form 로드 (전 세션)...", flush=True)
    forms = load_forms(args.year, {p.stem for p in
                                   (RAW / YEAR_DIRS[args.year]).glob("*.csv")
                                   if not p.name.startswith("_")})
    print(f"  form {len(forms):,}개", flush=True)

    made = skipped = failed = morph_missing = form_missing = source_total = 0
    archived_invalid = 0
    failed_files: list = []
    archive_root = STATE_ROOT / "archive_invalid_merge" / run_id / args.year
    t0 = time.time()
    for si, (nsess, sname, tgs) in enumerate(iter_session_tgs(src_year), 1):
        out_dir = OUT_ROOT / args.year / sname
        out_dir.mkdir(parents=True, exist_ok=True)
        for tg in tgs:
            source_total += 1
            out_path = out_dir / tg.name
            if out_path.exists():
                existing = validate_4tier(out_path)
                if existing["valid"]:
                    skipped += 1
                    continue
                archived = archive_copy(
                    out_path, archive_root, Path(sname) / out_path.name
                )
                archived_invalid += 1
                print(f"  !! 손상 기존본 보존 후 재생성: {out_path.name} -> {archived}",
                      flush=True)
            try:
                dur, tiers = parse_mfa_textgrid(tg)
                words = tiers.get("words", [])      # 어절
                phones = tiers.get("phones", [])    # 연결 발음
                if dur is None or not words or not phones:
                    failed += 1
                    failed_files.append({
                        "file": str(tg), "reason": "MFA words/phones/duration 누락",
                    })
                    continue
                if tg.stem not in forms:
                    form_missing += 1
                    failed += 1
                    failed_files.append({
                        "file": str(tg), "reason": "bareun form 누락",
                    })
                    continue
                morphs = morpheme_tier(args.year, sname, tg.stem)
                if morphs is None:
                    morph_missing += 1
                write_4tier(out_path, dur, words, phones, morphs,
                            forms[tg.stem])
                made += 1
            except Exception as e:
                failed += 1
                failed_files.append({
                    "file": str(tg), "reason": f"{type(e).__name__}: {e}",
                })
                print(f"  !! {tg.name}: {type(e).__name__}: {e}", flush=True)
        if si % 50 == 0:
            rate = made / (time.time() - t0) if made else 0
            print(f"  세션 {si:,}/{nsess:,} (생성 {made:,}, "
                  f"형태소없음 {morph_missing:,}, {rate:.0f}/s)", flush=True)
    print(f"완료[{args.year}]: 생성 {made:,} / 건너뜀 {skipped:,} / "
          f"실패 {failed:,} / 형태소tier없음 {morph_missing:,} / "
          f"form없음 {form_missing:,} / 손상구판보존 {archived_invalid:,}")
    report = {
        "run_id": run_id,
        "year": args.year,
        "mfa_output": str(src_year),
        "final_output": str(OUT_ROOT / args.year),
        "source_textgrids": source_total,
        "created": made,
        "validated_existing": skipped,
        "failed": failed,
        "form_missing": form_missing,
        "morpheme_tier_missing": morph_missing,
        "archived_invalid": archived_invalid,
        "elapsed_seconds": round(time.time() - t0, 3),
        "status": "success" if (
            source_total > 0 and failed == 0
            and made + skipped == source_total
        ) else "failed",
    }
    report_path = STATE_ROOT / "logs" / f"merge_report_{args.year}_{run_id}.json"
    atomic_write_json(report_path, report)
    print(f"병합 보고서: {report_path}", flush=True)
    if source_total == 0:
        print(f"!! 처리 0건 — {src_year} 구조 확인 필요", flush=True)
        return 1
    # ★ 부분 실패 묵살 금지 (2026-07-24, 외부 리뷰 P0-2): 종전엔 failed>0이어도 exit 0
    #   → 러너가 MFA 원출력을 삭제하고 merge_done 생성 → 실패분이 재시도 불가능하게
    #   조용히 소실됐음. 이제 실패 목록을 파일로 남기고 exit 1 → 러너가 중단하므로
    #   원출력·재시도 기회가 보존된다(재실행 시 기존 출력은 skip, 실패분만 재시도).
    if failed > 0:
        flog = STATE_ROOT / "logs" / f"merge_failed_{args.year}_{run_id}.json"
        flog.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(flog, {
            "run_id": run_id,
            "year": args.year,
            "failures": failed_files,
        })
        print(f"!! 병합 실패 {failed:,}건 — 목록: {flog}. 원출력 보존 위해 실패 종료", flush=True)
        return 1
    if made + skipped != source_total:
        print("!! 내부 수량 불일치 — 완료로 인정하지 않음", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""어절(語節) 전량 재정렬용 .lab 생성 — 제자리(in-place) 방식 (2020-2025).

★ 원래 파이프라인(make_labs)과 동일하게 lab을 wav '옆에' 직접 쓴다. 하드링크 없음.
   (하드링크 코퍼스 방식은 USB에서 느려 폐기 — 이 스크립트가 그걸 대체.)
교정 요점: lab을 '형태소'가 아니라 '어절'로 만든다. pre-MFA search master의
pron_reference_form을 우선 사용해 JSON 원전사에서 안전하게 복원된 숫자 읽기를
보존하고, 미해결 숫자·기호는 추측하지 않는다. 어절별 한글만 MFA에 넘긴다.

wav 위치(=lab 위치): 연도별 상이(2026-07-17 실측) — 평면(2020·2021·2025 확인)
                     또는 세션 하위폴더(2023 확인). 코드는 양쪽 지원(세션 우선→평면 폴백).
→ MFA 코퍼스 = individual/{year} 폴더 그대로.
기존 lab은 내용이 새 입력과 같은지 읽어 검증하며, 다르면 원자적으로 다시 쓴다.
입력 계약 marker가 같으면 재실행 때 전수 스캔을 건너뛴다.
실행: python realign_eojeol_build_corpus.py --year 2020
      --search-master-root D:/.../pre_mfa_staging/RUN_ID
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    sha256_file,
)

WAV_ROOT = P("wav") / "individual"
RAW = P("layers") / "01_bareun_raw"
SEARCH_MASTER = P("search_master")
STATE_ROOT = P("mfa_state")
YEAR_DIRS = {
    "2020": "NIKL_DIALOGUE_2020_v1.4", "2021": "NIKL_DIALOGUE_2021_v1.1",
    "2022": "NIKL_DIALOGUE_2022_v1.0_JSON", "2023": "NIKL_DIALOGUE_2023_v1.1",
    "2024": "NIKL_DIALOGUE_2024_v1.0", "2025": "NIKL_DIALOGUE_2025_v1.0",
}
HANGUL = re.compile(r"[가-힣]+")
LAB_INPUT_VERSION = "eojeol_v3_pron_reference_form"
MISSING = {"", "미상", "NA", "N/A"}
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def form_to_lab(form: str) -> str:
    """표층 form -> 어절 lab. 어절별 한글만 유지(문장부호/숫자/외국어 제외)."""
    toks = []
    for w in (form or "").split():
        h = "".join(HANGUL.findall(w))
        if h:
            toks.append(h)
    return " ".join(toks)


def load_entries(d: Path) -> dict[str, int]:
    """폴더 내 파일명→크기 (폴더 없으면 빈 dict).
    ★ USB 최적화(2026-07-17): 발화별 exists() 2~3회(각각 USB 왕복)를
    세션당 scandir 1회로 대체 — 510만 발화 기준 메타데이터 왕복 수백만 회 제거."""
    try:
        return {e.name: e.stat().st_size for e in os.scandir(d) if e.is_file()}
    except OSError:
        return {}


def input_contract(search_master_root: Path, year: str) -> dict[str, str]:
    meta_path = search_master_root / "_build_meta.json"
    if not meta_path.is_file():
        raise RuntimeError(f"pre-MFA build meta 없음: {meta_path}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"pre-MFA build meta 손상: {meta_path}: {exc}") from exc
    if meta.get("status") != "success":
        raise RuntimeError(
            f"pre-MFA search master 미통과(status={meta.get('status')}): "
            f"{meta_path}"
        )
    search_year = search_master_root / year
    source_year = RAW / YEAR_DIRS[year]
    actual_sessions = sum(
        1
        for path in search_year.glob("*.csv")
        if not path.name.startswith("_")
    )
    expected_sessions = sum(
        1
        for path in source_year.glob("*.csv")
        if not path.name.startswith("_")
    )
    if expected_sessions <= 0 or actual_sessions != expected_sessions:
        raise RuntimeError(
            f"{year} pre-MFA 세션 coverage 불일치: "
            f"search={actual_sessions}, source={expected_sessions}"
        )
    payload = {
        "lab_input_version": LAB_INPUT_VERSION,
        "year": year,
        "search_master_root": str(search_master_root.resolve()),
        "search_master_meta_sha256": sha256_file(meta_path),
        "source_field": "pron_reference_form",
        "unresolved_policy": "do_not_guess; keep Hangul only",
        "search_sessions": str(actual_sessions),
        "source_sessions": str(expected_sessions),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload["input_contract_id"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return payload


def normalized_lab_text(text: str) -> str:
    return " ".join((text or "").split())


def append_progress(path: Path | None, payload: dict) -> None:
    """Append one durable, machine-readable lab-build progress event."""
    if path is None:
        return
    record = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        **payload,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        handle.flush()


def archive_stale_lab(
    lab_path: Path,
    *,
    year: str,
    session: str,
    input_contract_id: str,
) -> Path:
    source = lab_path.resolve()
    allowed = (WAV_ROOT / year).resolve()
    if allowed not in source.parents:
        raise RuntimeError(f"stale lab 보존 경계 위반: {source}")
    destination = (
        STATE_ROOT
        / "archive_stale_labs"
        / input_contract_id
        / year
        / session
        / lab_path.name
    )
    if destination.exists():
        raise RuntimeError(f"stale lab archive 충돌: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def build_year(
    year: str,
    search_master_root: Path = SEARCH_MASTER,
    *,
    force_verify: bool = False,
    progress_jsonl: Path | None = None,
) -> dict:
    search_master_root = search_master_root.resolve()
    contract = input_contract(search_master_root, year)
    marker = STATE_ROOT / "done" / f"{year}.lab_input_done.json"
    if marker.is_file() and not force_verify:
        try:
            prior = json.loads(marker.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            prior = {}
        if (
            prior.get("status") == "passed"
            and prior.get("input_contract_id")
            == contract["input_contract_id"]
        ):
            print(
                f"[{year}] lab 입력 계약 완료 marker 확인 — 전수 재검사 건너뜀 "
                f"({contract['input_contract_id'][:12]})",
                flush=True,
            )
            atomic_write_json(
                STATE_ROOT / "logs" / f"lab_build_{year}_latest.json",
                prior,
            )
            append_progress(
                progress_jsonl,
                {
                    "event": "lab_reused",
                    "year": year,
                    "input_contract_id": contract["input_contract_id"],
                    "sessions_total": prior.get("sessions"),
                    "created": prior.get("created"),
                    "rewritten_mismatch": prior.get(
                        "rewritten_mismatch"
                    ),
                    "validated_existing": prior.get(
                        "validated_existing"
                    ),
                },
            )
            return prior

    source_dir = search_master_root / year
    files = sorted(
        p for p in source_dir.glob("*.csv") if not p.name.startswith("_")
    )
    nfiles = len(files)
    if nfiles == 0:
        raise RuntimeError(f"{year} pre-MFA 세션 CSV 0개: {source_dir}")
    print(
        f"[{year}] pre-MFA 세션 {nfiles:,}개 — lab 내용 전수 검증·생성...",
        flush=True,
    )
    started_at = datetime.now().astimezone().isoformat()
    append_progress(
        progress_jsonl,
        {
            "event": "lab_started",
            "year": year,
            "input_contract_id": contract["input_contract_id"],
            "sessions_total": nfiles,
            "force_verify": force_verify,
        },
    )
    made = verified = rewritten = no_wav = empty = 0
    reference_changed = unresolved = archived_empty_lab = 0
    rows_seen = 0
    t0 = time.time()
    last_reported_rows = 0
    flat_names = None
    for k, fp in enumerate(files, 1):
        sess_cache = {}  # 세션 → 파일명 집합 (CSV 하나 처리 동안만 유지)
        with open(fp, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            required = {
                "utt_id",
                "form",
                "pron_reference_form",
                "pron_reference_source",
                "pron_reference_status",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"{fp}: pre-MFA 필수 열 누락 {sorted(missing)}"
                )
            for row in reader:
                rows_seen += 1
                u = row["utt_id"]
                sess = u.split(".")[0]
                names = sess_cache.get(sess)
                if names is None:
                    names = load_entries(WAV_ROOT / year / sess)
                    sess_cache[sess] = names
                if f"{u}.wav" in names:
                    wav_dir = WAV_ROOT / year / sess
                else:  # 평면(2025) 폴백
                    if flat_names is None:
                        flat_names = load_entries(WAV_ROOT / year)
                    if f"{u}.wav" in flat_names:
                        wav_dir = WAV_ROOT / year
                        names = flat_names
                    else:
                        no_wav += 1
                        continue
                lab_name = f"{u}.lab"
                form = (row.get("form") or "").strip()
                reference_form = (
                    row.get("pron_reference_form") or ""
                ).strip()
                if reference_form in MISSING:
                    reference_form = form
                if reference_form != form:
                    reference_changed += 1
                if row.get("pron_reference_status") == "unresolved_symbol":
                    unresolved += 1
                text = form_to_lab(reference_form)
                if not text.strip():
                    empty += 1
                    lab_name = f"{u}.lab"
                    if names.get(lab_name, 0) > 0:
                        archive_stale_lab(
                            wav_dir / lab_name,
                            year=year,
                            session=sess,
                            input_contract_id=contract["input_contract_id"],
                        )
                        names.pop(lab_name, None)
                        archived_empty_lab += 1
                    continue
                lab_path = wav_dir / lab_name
                had_existing = names.get(lab_name, 0) > 0
                if had_existing:
                    try:
                        existing = normalized_lab_text(
                            lab_path.read_text(encoding="utf-8-sig")
                        )
                    except (OSError, UnicodeError):
                        existing = ""
                    if existing == normalized_lab_text(text):
                        verified += 1
                        continue
                    rewritten += 1
                with atomic_text_writer(
                    lab_path, encoding="utf-8", newline="\n"
                ) as (stream, _):
                    stream.write(text)
                names[lab_name] = len(text.encode("utf-8"))
                if not had_existing:
                    made += 1
        # 발화 1,000개 훑을 때마다 속도·남은시간 출력 (1분 안에 첫 숫자)
        proc = made + verified + rewritten
        if rows_seen - last_reported_rows >= 1000 or k == nfiles:
            last_reported_rows = rows_seen
            el = time.time() - t0
            rate = rows_seen / el if el > 0 else 0
            eta_min = (nfiles - k) / (k / el) / 60 if el > 0 and k else 0
            print(
                  f"  {year} {k}/{nfiles}세션 · 신규 {made:,} · "
                  f"불일치재작성 {rewritten:,} · 검증 {verified:,} · "
                  f"{rate:.0f}발화/s · 이 연도 남은 ~{eta_min:.0f}분", flush=True)
            append_progress(
                progress_jsonl,
                {
                    "event": "lab_progress",
                    "year": year,
                    "input_contract_id": contract["input_contract_id"],
                    "sessions_current": k,
                    "sessions_total": nfiles,
                    "rows_seen": rows_seen,
                    "usable_labs_seen": proc,
                    "created": made,
                    "rewritten_mismatch": rewritten,
                    "validated_existing": verified,
                    "wav_missing": no_wav,
                    "empty_reference_form": empty,
                    "rows_per_second": round(rate, 1),
                    "eta_minutes": round(eta_min, 1),
                    "elapsed_seconds": round(el, 1),
                },
            )
    print(
        f"[{year}] 완료: 신규 {made:,} / 불일치재작성 {rewritten:,} / "
        f"내용일치 {verified:,} / wav없음 {no_wav:,} / 빈입력 {empty:,} / "
        f"빈입력구lab보존 {archived_empty_lab:,} / "
        f"reference변경 {reference_changed:,} / 미해결기호 {unresolved:,}",
        flush=True,
    )
    print(f"  코퍼스(=wav폴더): {WAV_ROOT / year}", flush=True)
    elapsed_seconds = round(time.time() - t0, 3)
    finished_at = datetime.now().astimezone().isoformat()
    result = {
        **contract,
        "status": "passed",
        "year": year,
        "sessions": nfiles,
        "rows_seen": rows_seen,
        "created": made,
        "rewritten_mismatch": rewritten,
        "validated_existing": verified,
        "wav_missing": no_wav,
        "empty_reference_form": empty,
        "archived_empty_input_lab": archived_empty_lab,
        "reference_form_changed": reference_changed,
        "pron_reference_unresolved": unresolved,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
    }
    if made + verified + rewritten == 0:
        append_progress(
            progress_jsonl,
            {
                "event": "lab_failed",
                "year": year,
                "input_contract_id": contract["input_contract_id"],
                "sessions_total": nfiles,
                "rows_seen": rows_seen,
                "created": made,
                "rewritten_mismatch": rewritten,
                "validated_existing": verified,
                "wav_missing": no_wav,
                "empty_reference_form": empty,
                "elapsed_seconds": elapsed_seconds,
                "status": "failed",
                "reason": "usable_lab_zero",
            },
        )
        raise RuntimeError(f"{year} 유효 lab 0건")
    marker.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(marker, result)
    atomic_write_json(
        STATE_ROOT / "logs" / f"lab_build_{year}_latest.json", result
    )
    append_progress(
        progress_jsonl,
        {
            "event": "lab_completed",
            "year": year,
            "input_contract_id": contract["input_contract_id"],
            "sessions_total": nfiles,
            "rows_seen": rows_seen,
            "created": made,
            "rewritten_mismatch": rewritten,
            "validated_existing": verified,
            "wav_missing": no_wav,
            "empty_reference_form": empty,
            "elapsed_seconds": elapsed_seconds,
            "status": "passed",
        },
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    ap.add_argument(
        "--search-master-root",
        type=Path,
        default=SEARCH_MASTER,
        help="검증 통과한 pre-MFA search master staging",
    )
    ap.add_argument(
        "--force-verify",
        action="store_true",
        help="입력 계약 marker가 같아도 기존 lab을 다시 전수 검증",
    )
    ap.add_argument(
        "--progress-jsonl",
        type=Path,
        help="시작·진행·완료를 append-only JSONL로 기록할 경로",
    )
    args = ap.parse_args()
    years = sorted(YEAR_DIRS) if args.year == "all" else [args.year]
    for y in years:
        if y not in YEAR_DIRS:
            sys.exit(f"알 수 없는 연도: {y}")
        build_year(
            y,
            args.search_master_root,
            force_verify=args.force_verify,
            progress_jsonl=args.progress_jsonl,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

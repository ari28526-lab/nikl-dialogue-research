"""어절(語節) 전량 재정렬용 .lab 생성 — 선택된 MFA corpus 안에 작성.

★ lab은 선택된 MFA corpus의 wav 옆에 직접 쓴다. 기본은 기존 individual root이며,
   복구 계약이 있는 2020은 원본을 보존한 별도 corpus root를 명시한다.
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
    file_fingerprint,
    sha256_file,
)
from mfa_exclusion_contract import load_contract  # noqa: E402

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
LAB_INPUT_VERSION = "eojeol_v4_pron_reference_form_with_token_map"
TOKEN_MAP_VERSION = "source_eojeol_to_mfa_word.v1"
MISSING = {"", "미상", "NA", "N/A"}
UNRESOLVED_INVENTORY_FIELDS = [
    "year",
    "session_id",
    "utt_id",
    "form",
    "pron_reference_form",
    "pron_reference_source",
    "pron_reference_status",
    "lab_text",
]
APPROVED_LAB_EXCLUSION_FIELDS = [
    "year",
    "input_contract_id",
    "approved_contract_sha256",
    "utt_id",
    "session_id",
    "reason_code",
    "exclusion_scope",
    "lab_status",
    "original_lab_path",
    "archive_lab_path",
    "lab_sha256",
]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def form_to_lab_mapping(form: str) -> list[dict[str, object]]:
    """원문 어절과 MFA word 위치의 명시적 대응표를 만든다.

    숫자·기호·외국어만 있는 원문 어절은 삭제 사실을 숨기지 않고
    ``mfa_word_index=None``으로 남긴다. 이후 CSV와 TextGrid를 연결할 때
    원문 어절 번호를 MFA word 번호로 잘못 간주하지 않기 위한 계약이다.
    """

    mapping: list[dict[str, object]] = []
    mfa_word_index = 0
    for source_index, source_token in enumerate((form or "").split()):
        lab_token = "".join(HANGUL.findall(source_token))
        row: dict[str, object] = {
            "source_eojeol_index": source_index,
            "source_token": source_token,
            "lab_token": lab_token,
            "mfa_word_index": None,
            "included_in_mfa": bool(lab_token),
        }
        if lab_token:
            row["mfa_word_index"] = mfa_word_index
            mfa_word_index += 1
        mapping.append(row)
    return mapping


def form_to_lab(form: str) -> str:
    """표층 form -> 어절 lab. 대응관계는 :func:`form_to_lab_mapping`에 보존."""

    return " ".join(
        str(row["lab_token"])
        for row in form_to_lab_mapping(form)
        if row["included_in_mfa"]
    )


def load_entries(d: Path) -> dict[str, int]:
    """폴더 내 파일명→크기 (폴더 없으면 빈 dict).
    ★ USB 최적화(2026-07-17): 발화별 exists() 2~3회(각각 USB 왕복)를
    세션당 scandir 1회로 대체 — 510만 발화 기준 메타데이터 왕복 수백만 회 제거."""
    try:
        return {e.name: e.stat().st_size for e in os.scandir(d) if e.is_file()}
    except OSError:
        return {}


def input_contract(
    search_master_root: Path,
    year: str,
    *,
    wav_root: Path | None = None,
    audio_corpus_contract: Path | None = None,
) -> dict[str, object]:
    wav_root = (wav_root or WAV_ROOT).resolve()
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
        "token_map_version": TOKEN_MAP_VERSION,
        "token_map_policy": (
            "retain every source eojeol; excluded non-Hangul token gets "
            "mfa_word_index=null"
        ),
        "search_sessions": str(actual_sessions),
        "source_sessions": str(expected_sessions),
        "wav_root": str(wav_root.resolve()),
    }
    if audio_corpus_contract is not None:
        contract_path = audio_corpus_contract.resolve()
        try:
            audio = json.loads(contract_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"audio corpus contract 손상: {contract_path}: {exc}"
            ) from exc
        expected_output = (wav_root / year).resolve()
        if (
            audio.get("status") != "passed"
            or str(audio.get("year")) != year
            or not audio.get("source_wav_tree_untouched")
            or Path(str(audio.get("output_year") or "")).resolve()
            != expected_output
            or not str(audio.get("corpus_contract_id") or "")
        ):
            raise RuntimeError(
                f"audio corpus contract identity/status 불일치: {contract_path}"
            )
        payload.update(
            {
                "audio_corpus_contract_id": str(audio["corpus_contract_id"]),
                "audio_corpus_contract_sha256": sha256_file(contract_path),
                "audio_corpus_policy": str(audio.get("schema_version") or ""),
            }
        )
    else:
        payload.update(
            {
                "audio_corpus_contract_id": "source_identity",
                "audio_corpus_contract_sha256": "",
                "audio_corpus_policy": "original_same_id",
            }
        )
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


def write_unresolved_inventory(path: Path, rows: list[dict]) -> None:
    """미해결 숫자·기호 발화를 계약별 CSV로 원자적으로 기록한다."""
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=UNRESOLVED_INVENTORY_FIELDS
        )
        writer.writeheader()
        writer.writerows(rows)


def unresolved_inventory_path(
    *, year: str, input_contract_id: str
) -> Path:
    return (
        STATE_ROOT
        / "logs"
        / (
            f"lab_build_{year}_"
            f"{input_contract_id[:12]}_unresolved_symbols.csv"
        )
    )


def collect_unresolved_rows(
    search_master_root: Path, year: str
) -> list[dict[str, str]]:
    """search CSV만 읽어 미해결 발화와 실제 부분 lab을 다시 만든다."""
    rows: list[dict[str, str]] = []
    required = {
        "utt_id",
        "form",
        "pron_reference_form",
        "pron_reference_source",
        "pron_reference_status",
    }
    for path in sorted((search_master_root / year).glob("*.csv")):
        if path.name.startswith("_"):
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise RuntimeError(
                    f"{path}: pre-MFA 필수 열 누락 {sorted(missing)}"
                )
            for row in reader:
                if row.get("pron_reference_status") != "unresolved_symbol":
                    continue
                utt_id = (row.get("utt_id") or "").strip()
                form = (row.get("form") or "").strip()
                reference_form = (
                    row.get("pron_reference_form") or ""
                ).strip()
                if reference_form in MISSING:
                    reference_form = form
                rows.append(
                    {
                        "year": year,
                        "session_id": utt_id.split(".")[0],
                        "utt_id": utt_id,
                        "form": form,
                        "pron_reference_form": reference_form,
                        "pron_reference_source": row.get(
                            "pron_reference_source", ""
                        ),
                        "pron_reference_status": "unresolved_symbol",
                        "lab_text": form_to_lab(reference_form),
                    }
                )
    return rows


def unresolved_inventory_valid(path: Path, expected_rows: int) -> bool:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if list(reader.fieldnames or ()) != UNRESOLVED_INVENTORY_FIELDS:
                return False
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error):
        return False
    return (
        len(rows) == expected_rows
        and all(
            row.get("utt_id")
            and row.get("pron_reference_status") == "unresolved_symbol"
            for row in rows
        )
    )


def archive_stale_lab(
    lab_path: Path,
    *,
    year: str,
    session: str,
    input_contract_id: str,
    wav_root: Path | None = None,
) -> Path:
    wav_root = (wav_root or WAV_ROOT).resolve()
    source = lab_path.resolve()
    allowed = (wav_root / year).resolve()
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


def approved_lab_exclusion_root(
    *,
    year: str,
    input_contract_id: str,
    approved_contract_sha256: str,
) -> Path:
    """Return the contract-specific, reversible LAB-only archive root."""

    return (
        STATE_ROOT
        / "approved_lab_exclusions"
        / year
        / input_contract_id[:20]
        / approved_contract_sha256[:20]
    )


def archive_approved_lab(
    lab_path: Path,
    *,
    year: str,
    session: str,
    input_contract_id: str,
    approved_contract_sha256: str,
    wav_root: Path,
) -> dict[str, str]:
    """Remove one approved LAB from active MFA input without touching WAV/CSV.

    The move is content-verified and idempotent.  A prior interrupted run is
    represented by a missing source and an existing contract-specific archive.
    If both exist, the state is ambiguous and the run stops instead of choosing
    one copy automatically.
    """

    source = lab_path.resolve()
    allowed = (wav_root / year).resolve()
    if allowed != source.parent and allowed not in source.parents:
        raise RuntimeError(f"승인 제외 LAB 경계 위반: {source}")
    destination = (
        approved_lab_exclusion_root(
            year=year,
            input_contract_id=input_contract_id,
            approved_contract_sha256=approved_contract_sha256,
        )
        / session
        / source.name
    ).resolve()
    source_exists = source.is_file()
    destination_exists = destination.is_file()
    if source_exists and destination_exists:
        raise RuntimeError(
            "승인 제외 LAB가 active/archive 양쪽에 존재함: "
            f"{source} / {destination}"
        )
    if source_exists:
        before = sha256_file(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        after = sha256_file(destination)
        if before != after:
            raise RuntimeError(f"승인 제외 LAB 이동 SHA256 불일치: {source}")
        status = "moved"
        digest = after
    elif destination_exists:
        status = "already_archived"
        digest = sha256_file(destination)
    else:
        status = "no_active_lab"
        digest = ""
    return {
        "lab_status": status,
        "original_lab_path": str(source),
        "archive_lab_path": str(destination),
        "lab_sha256": digest,
    }


def write_approved_lab_exclusion_inventory(
    path: Path, rows: list[dict[str, str]]
) -> None:
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=APPROVED_LAB_EXCLUSION_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_year(
    year: str,
    search_master_root: Path,
    *,
    force_verify: bool = False,
    progress_jsonl: Path | None = None,
    wav_root: Path | None = None,
    audio_corpus_contract: Path | None = None,
    approved_exclusions_contract: Path | None = None,
) -> dict[str, object]:
    search_master_root = search_master_root.resolve()
    wav_root = (wav_root or WAV_ROOT).resolve()
    contract = input_contract(
        search_master_root,
        year,
        wav_root=wav_root,
        audio_corpus_contract=audio_corpus_contract,
    )
    approved_contract_fingerprint = None
    approved_alignment_rows: dict[str, dict[str, str]] = {}
    approved_contract_sha256 = ""
    if approved_exclusions_contract is not None:
        approved_exclusions_contract = approved_exclusions_contract.resolve()
        _, approved_rows = load_contract(
            approved_exclusions_contract,
            year=year,
            input_contract_id=str(contract["input_contract_id"]),
        )
        approved_alignment_rows = {
            utt_id: row
            for utt_id, row in approved_rows.items()
            if row["exclusion_scope"] == "alignment_and_analysis"
        }
        approved_contract_fingerprint = file_fingerprint(
            approved_exclusions_contract, with_sha256=True
        )
        approved_contract_sha256 = str(
            approved_contract_fingerprint["sha256"]
        )
    marker = STATE_ROOT / "done" / f"{year}.lab_input_done.json"
    if (
        marker.is_file()
        and not force_verify
        and approved_exclusions_contract is None
    ):
        try:
            prior = json.loads(marker.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            prior = {}
        if (
            prior.get("status") == "passed"
            and prior.get("input_contract_id")
            == contract["input_contract_id"]
        ):
            inventory = unresolved_inventory_path(
                year=year,
                input_contract_id=contract["input_contract_id"],
            )
            expected_unresolved = int(
                prior.get("pron_reference_unresolved", 0)
            )
            if not unresolved_inventory_valid(
                inventory, expected_unresolved
            ):
                unresolved_rows = collect_unresolved_rows(
                    search_master_root, year
                )
                if len(unresolved_rows) != expected_unresolved:
                    raise RuntimeError(
                        f"{year} marker/inventory 미해결 수 불일치: "
                        f"marker={expected_unresolved}, "
                        f"search={len(unresolved_rows)}"
                    )
                write_unresolved_inventory(inventory, unresolved_rows)
            prior["unresolved_symbol_inventory"] = str(inventory)
            atomic_write_json(marker, prior)
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
    approved_moved = approved_already = approved_no_lab = 0
    approved_seen: set[str] = set()
    approved_inventory_rows: list[dict[str, str]] = []
    unresolved_rows = []
    rows_seen = 0
    t0 = time.time()
    last_reported_rows = 0
    flat_names = None

    def apply_approved_exclusion(
        *,
        utt_id: str,
        session: str,
        lab_name: str,
        preferred_wav_dir: Path,
        approved_row: dict[str, str],
    ) -> None:
        nonlocal approved_moved, approved_already, approved_no_lab
        approved_seen.add(utt_id)
        session_lab = wav_root / year / session / lab_name
        flat_lab = wav_root / year / lab_name
        active_labs = [
            path
            for path in dict.fromkeys((session_lab, flat_lab))
            if path.is_file()
        ]
        if len(active_labs) > 1:
            raise RuntimeError(
                f"{utt_id}: 승인 제외 LAB가 세션/평면 양쪽에 존재함"
            )
        lab_source = (
            active_labs[0]
            if active_labs
            else preferred_wav_dir / lab_name
        )
        archived = archive_approved_lab(
            lab_source,
            year=year,
            session=session,
            input_contract_id=str(contract["input_contract_id"]),
            approved_contract_sha256=approved_contract_sha256,
            wav_root=wav_root,
        )
        status = archived["lab_status"]
        if status == "moved":
            approved_moved += 1
        elif status == "already_archived":
            approved_already += 1
        else:
            approved_no_lab += 1
        approved_inventory_rows.append(
            {
                "year": year,
                "input_contract_id": str(contract["input_contract_id"]),
                "approved_contract_sha256": approved_contract_sha256,
                "utt_id": utt_id,
                "session_id": session,
                "reason_code": approved_row["reason_code"],
                "exclusion_scope": approved_row["exclusion_scope"],
                **archived,
            }
        )

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
                approved_row = approved_alignment_rows.get(u)
                names = sess_cache.get(sess)
                if names is None:
                    names = load_entries(wav_root / year / sess)
                    sess_cache[sess] = names
                session_wav_dir = wav_root / year / sess
                if f"{u}.wav" in names:
                    wav_dir = wav_root / year / sess
                    wav_found = True
                else:  # 평면(2025) 폴백
                    if flat_names is None:
                        flat_names = load_entries(wav_root / year)
                    if f"{u}.wav" in flat_names:
                        wav_dir = wav_root / year
                        names = flat_names
                        wav_found = True
                    else:
                        no_wav += 1
                        wav_dir = session_wav_dir
                        wav_found = False
                lab_name = f"{u}.lab"
                if not wav_found:
                    if approved_row is not None:
                        apply_approved_exclusion(
                            utt_id=u,
                            session=sess,
                            lab_name=lab_name,
                            preferred_wav_dir=wav_dir,
                            approved_row=approved_row,
                        )
                    continue
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
                if row.get("pron_reference_status") == "unresolved_symbol":
                    unresolved_rows.append(
                        {
                            "year": year,
                            "session_id": sess,
                            "utt_id": u,
                            "form": form,
                            "pron_reference_form": reference_form,
                            "pron_reference_source": row.get(
                                "pron_reference_source", ""
                            ),
                            "pron_reference_status": "unresolved_symbol",
                            "lab_text": text,
                        }
                    )
                if approved_row is not None:
                    apply_approved_exclusion(
                        utt_id=u,
                        session=sess,
                        lab_name=lab_name,
                        preferred_wav_dir=wav_dir,
                        approved_row=approved_row,
                    )
                    continue
                if not text.strip():
                    empty += 1
                    lab_name = f"{u}.lab"
                    if names.get(lab_name, 0) > 0:
                        archive_stale_lab(
                            wav_dir / lab_name,
                            year=year,
                            session=sess,
                            input_contract_id=contract["input_contract_id"],
                            wav_root=wav_root,
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
                    "approved_alignment_exclusions": len(
                        approved_alignment_rows
                    ),
                    "approved_labs_moved": approved_moved,
                    "approved_labs_already_archived": approved_already,
                    "approved_labs_without_active_lab": approved_no_lab,
                    "rows_per_second": round(rate, 1),
                    "eta_minutes": round(eta_min, 1),
                    "elapsed_seconds": round(el, 1),
                },
            )
    missing_approved = sorted(set(approved_alignment_rows) - approved_seen)
    if missing_approved:
        raise RuntimeError(
            "승인 제외 계약 ID가 search master에 없음: "
            f"{len(missing_approved):,}건; 예={missing_approved[:20]}"
        )
    approved_apply_manifest = None
    if approved_contract_fingerprint is not None:
        apply_root = approved_lab_exclusion_root(
            year=year,
            input_contract_id=str(contract["input_contract_id"]),
            approved_contract_sha256=approved_contract_sha256,
        )
        inventory_path = apply_root / "approved_lab_exclusion_inventory.csv"
        write_approved_lab_exclusion_inventory(
            inventory_path, approved_inventory_rows
        )
        approved_apply_manifest = apply_root / "apply_manifest.json"
        apply_record = {
            "schema_version": "mfa_approved_lab_exclusion_apply.v1",
            "status": "passed",
            "year": year,
            "input_contract_id": contract["input_contract_id"],
            "approved_exclusions_contract": approved_contract_fingerprint,
            "approved_alignment_exclusion_count": len(
                approved_alignment_rows
            ),
            "inventory": file_fingerprint(
                inventory_path, with_sha256=True
            ),
            "lab_status_counts": {
                "moved": approved_moved,
                "already_archived": approved_already,
                "no_active_lab": approved_no_lab,
            },
            "source_wav_or_csv_changed": False,
            "lab_only_reversible_archive": True,
            "finished_at": datetime.now().astimezone().isoformat(),
        }
        atomic_write_json(approved_apply_manifest, apply_record)
    print(
        f"[{year}] 완료: 신규 {made:,} / 불일치재작성 {rewritten:,} / "
        f"내용일치 {verified:,} / wav없음 {no_wav:,} / 빈입력 {empty:,} / "
        f"빈입력구lab보존 {archived_empty_lab:,} / "
        f"승인LAB이동 {approved_moved:,} / 기존보존 {approved_already:,} / "
        f"활성LAB없음 {approved_no_lab:,} / "
        f"reference변경 {reference_changed:,} / 미해결기호 {unresolved:,}",
        flush=True,
    )
    print(f"  코퍼스(=wav폴더): {wav_root / year}", flush=True)
    elapsed_seconds = round(time.time() - t0, 3)
    finished_at = datetime.now().astimezone().isoformat()
    unresolved_inventory = unresolved_inventory_path(
        year=year,
        input_contract_id=contract["input_contract_id"],
    )
    write_unresolved_inventory(unresolved_inventory, unresolved_rows)
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
        "unresolved_symbol_inventory": str(unresolved_inventory),
        "approved_exclusions_contract": approved_contract_fingerprint,
        "approved_alignment_exclusion_count": len(
            approved_alignment_rows
        ),
        "approved_labs_moved": approved_moved,
        "approved_labs_already_archived": approved_already,
        "approved_labs_without_active_lab": approved_no_lab,
        "approved_lab_exclusion_apply_manifest": (
            str(approved_apply_manifest)
            if approved_apply_manifest is not None
            else None
        ),
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
            "approved_alignment_exclusions": len(
                approved_alignment_rows
            ),
            "approved_labs_moved": approved_moved,
            "approved_labs_already_archived": approved_already,
            "approved_labs_without_active_lab": approved_no_lab,
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
        required=True,
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
    ap.add_argument(
        "--wav-root",
        type=Path,
        default=WAV_ROOT,
        help="MFA corpus의 연도 폴더들을 포함하는 root",
    )
    ap.add_argument(
        "--audio-corpus-contract",
        type=Path,
        help="별도 복구 corpus를 사용할 때의 passed contract",
    )
    ap.add_argument(
        "--approved-exclusions-contract",
        type=Path,
        help=(
            "input_contract_id에 묶인 연구자 승인 제외 계약. "
            "alignment_and_analysis LAB만 가역 보존한다."
        ),
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
            wav_root=args.wav_root,
            audio_corpus_contract=args.audio_corpus_contract,
            approved_exclusions_contract=(
                args.approved_exclusions_contract
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

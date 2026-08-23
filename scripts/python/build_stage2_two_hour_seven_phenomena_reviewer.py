from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_pv_reviewer_v2 import scan_dialogue_text
from build_stage2_gate2_ni_followup_reviewer_v3 import parse_long_textgrid
from pipeline_common import sha256_file

sys.stdout.reconfigure(encoding="utf-8")


class ReviewerBuildError(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CODES = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
EXPECTED_YEARS = list(range(2020, 2026))
EXPECTED_SAMPLES_SHA256 = "8043eb2564e041881051cad4c8f92370b061b363572ad8a4afb21c2e33eaca9f"
DEFAULT_SAMPLES = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/ni_scope_correction_v2/P2H_SAMPLES_FINAL_V2.csv"
)
DEFAULT_CORRECTION_RECEIPT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/ni_scope_correction_v2/"
    "P2H_NI_SCOPE_CORRECTION_RECEIPT.json"
)
DEFAULT_SCOPE_CARDS = Path("config/phenomenon_scope_cards_candidate_v1_20260823.jsonl")
DEFAULT_CLAIMS = Path(
    "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"
)
DEFAULT_OUTPUT = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/researcher_review_package_v1"
)
DEFAULT_REPACKAGE_SOURCE = Path(
    "outputs/pilots/pv_seven_phenomena_20260819/"
    "two_hour_research_pilots_20260823/researcher_review_package_v1"
)
ALLOWED_OUTPUT_ROOT = Path("outputs/pilots/pv_seven_phenomena_20260819")
ROW_CAP = 200000

ASSET_FIELDS = [
    "sample_id",
    "phenomenon_code",
    "year",
    "utt_id",
    "source_wav_path",
    "source_wav_bytes",
    "source_wav_sha256",
    "bundle_wav_path",
    "bundle_wav_sha256",
    "source_textgrid_path",
    "source_textgrid_bytes",
    "source_textgrid_sha256",
    "bundle_source_textgrid_path",
    "bundle_source_textgrid_sha256",
    "praat_work_textgrid_path",
    "praat_work_initial_sha256",
    "copy_status",
]

PRAAT_TASK_FIELDS = [
    "sample_id",
    "phenomenon_code",
    "year",
    "utt_id",
    "target_word_labels_json",
    "bundle_wav_path",
    "praat_work_textgrid_path",
    "source_textgrid_sha256",
    "praat_work_initial_sha256",
    "researcher_need_edit",
    "researcher_edit_reason",
    "researcher_note",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewerBuildError(message)


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
    require(bool(rows), f"empty CSV: {path}")
    return rows


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ReviewerBuildError(f"JSONL parse failure {path}:{line_number}: {exc}") from exc
            require(isinstance(value, dict), f"JSONL row is not object: {path}:{line_number}")
            rows.append(value)
    require(bool(rows), f"empty JSONL: {path}")
    return rows


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON root not object: {path}")
    return value


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    os.replace(partial, path)


def atomic_write_text(path: Path, value: str, *, bom: bool = False) -> None:
    payload = value.encode("utf-8")
    if bom:
        payload = b"\xef\xbb\xbf" + payload
    atomic_write_bytes(path, payload)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def atomic_write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(path)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(partial, path)


def declared_output_sha(receipt: Mapping[str, Any], filename: str) -> str:
    matches = [row for row in receipt.get("outputs", []) if row.get("path") == filename]
    require(len(matches) == 1, f"receipt declaration count for {filename}: {len(matches)}")
    return str(matches[0].get("sha256", ""))


def validate_samples(
    rows: list[dict[str, str]], *, check_source_assets: bool = True
) -> dict[str, Any]:
    require(len(rows) == 84, f"expected 84 sample rows, measured {len(rows)}")
    require(len({row["sample_id"] for row in rows}) == 84, "sample IDs are not unique")
    counts = Counter(row["phenomenon_code"] for row in rows)
    require(set(counts) == set(EXPECTED_CODES), f"phenomenon codes: {sorted(counts)}")
    require(all(counts[code] == 12 for code in EXPECTED_CODES), f"phenomenon counts: {counts}")
    year_counts = Counter((row["phenomenon_code"], row["year"]) for row in rows)
    require(
        all(year_counts[(code, str(year))] == 2 for code in EXPECTED_CODES for year in EXPECTED_YEARS),
        "each phenomenon-year must contain two rows",
    )
    require(
        not any(row["phenomenon_code"] == "NI" and row["query_id"].endswith("VCP_SURFACE_BRANCH_V1") for row in rows),
        "corrected pilot must not select unresolved/overt VCP rows",
    )
    for row in rows:
        if check_source_assets:
            require(Path(row["wav_path"]).is_file(), f"WAV missing: {row['sample_id']}")
            require(Path(row["active_textgrid_path"]).is_file(), f"TextGrid missing: {row['sample_id']}")
        require(str(row["timing_status"]).startswith("linked_"), f"timing not linked: {row['sample_id']}")
        require(row["realization_status"] == "not_judged", f"realization pre-judged: {row['sample_id']}")
    return {
        "rows": len(rows),
        "by_phenomenon": dict(sorted(counts.items())),
        "distinct_utterances": len({row["utt_id"] for row in rows}),
        "distinct_wav_paths": len({row["wav_path"] for row in rows}),
    }


def preflight(
    *, samples_path: Path, correction_receipt_path: Path, cards_path: Path, claims_path: Path
) -> dict[str, Any]:
    rows = read_csv(samples_path)
    stats = validate_samples(rows)
    correction = load_json(correction_receipt_path)
    measured_samples = sha256_file(samples_path)
    require(
        measured_samples == declared_output_sha(correction, samples_path.name),
        "sample SHA differs from NI correction receipt",
    )
    cards = read_jsonl(cards_path)
    claims = read_jsonl(claims_path)
    require([row.get("phenomenon_code") for row in cards] == EXPECTED_CODES, "scope card order/codes")
    claim_ids = [str(row.get("claim_id", "")) for row in claims]
    require(len(claim_ids) == 156 and len(set(claim_ids)) == 156, "claim ledger must be 156 unique rows")
    return {
        "schema_version": "stage2_two_hour_reviewer_preflight.v1",
        "passed": True,
        "status": "ready_no_dialogue_scan_no_asset_copy",
        "samples": {"path": str(samples_path), "sha256": measured_samples, **stats},
        "correction_receipt": {
            "path": str(correction_receipt_path),
            "sha256": sha256_file(correction_receipt_path),
        },
        "scope_cards": {"path": str(cards_path), "rows": len(cards), "sha256": sha256_file(cards_path)},
        "claims": {"path": str(claims_path), "rows": len(claims), "sha256": sha256_file(claims_path)},
        "safety": {
            "row_cap_per_year": ROW_CAP,
            "source_rows_scanned": 0,
            "assets_copied": 0,
            "audio_transformed": False,
            "automatic_realization_judgement": False,
        },
    }


def json_for_html(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def morphology_display(row: Mapping[str, str]) -> dict[str, Any]:
    try:
        evidence = json.loads(row.get("match_evidence_json", "{}"))
    except json.JSONDecodeError:
        evidence = {}
    if evidence.get("left_morph_surface") or evidence.get("right_morph_surface"):
        return {
            "status": "direct_from_match_evidence",
            "kind": "morpheme_boundary",
            "segments": [
                {
                    "surface": evidence.get("left_morph_surface", ""),
                    "pos": evidence.get("left_pos", ""),
                    "focus": evidence.get("left_unit_surface", ""),
                },
                {
                    "surface": evidence.get("right_morph_surface", ""),
                    "pos": evidence.get("right_pos", ""),
                    "focus": evidence.get("right_unit_surface", ""),
                },
            ],
            "boundary": f"{evidence.get('left_unit_surface', '')}│{evidence.get('right_unit_surface', '')}",
        }
    if evidence.get("morph_surface"):
        return {
            "status": "direct_from_match_evidence",
            "kind": "morpheme_internal",
            "segments": [
                {
                    "surface": evidence.get("morph_surface", ""),
                    "pos": evidence.get("pos", ""),
                    "focus": f"{evidence.get('left_unit_surface', '')}│{evidence.get('right_unit_surface', '')}",
                }
            ],
            "boundary": f"{evidence.get('left_unit_surface', '')}│{evidence.get('right_unit_surface', '')}",
        }
    return {
        "status": "orthographic_probe_evidence",
        "kind": "orthographic_probe",
        "segments": [],
        "boundary": evidence.get("orth_eojeol_form", row.get("word_group", "")),
    }


def literature_payload(cards: list[dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    claims_by_id = {str(row["claim_id"]): row for row in claims}
    result: dict[str, Any] = {}
    for card in cards:
        code = str(card["phenomenon_code"])
        claim_rows = []
        missing_refs = []
        for ref in card.get("evidence_refs", []):
            if str(ref).startswith("CLM-"):
                claim = claims_by_id.get(str(ref))
                require(claim is not None, f"card {code} references missing claim {ref}")
                claim_rows.append(
                    {
                        "claim_id": claim["claim_id"],
                        "source_id": claim.get("source_id", ""),
                        "citation": claim.get("citation", ""),
                        "claim_ko": claim.get("claim_ko", ""),
                        "applies_when": claim.get("applies_when", ""),
                        "does_not_establish": claim.get("does_not_establish", ""),
                        "review_question": claim.get("review_question", ""),
                        "printed_page": claim.get("printed_page"),
                        "pdf_page": claim.get("pdf_page"),
                        "confidence": claim.get("confidence", ""),
                        "source_file": claim.get("source_file", ""),
                    }
                )
            else:
                missing_refs.append(str(ref))
        result[code] = {
            "phenomenon_code": code,
            "label_ko": card["label_ko"],
            "definition_summary": card["definition_summary"],
            "literature_synthesis_path": card["literature_synthesis_path"],
            "literature_evidence_level": card["literature_evidence_level"],
            "minimum_contrast": card.get("minimum_contrast", []),
            "population_contract": card.get("population_contract", {}),
            "confounds": card.get("confounds", []),
            "evidence_limits": card.get("evidence_limits", []),
            "open_questions": card.get("open_questions", []),
            "pilot_schedule": card.get("pilot_schedule", []),
            "realization_categories_candidate": card.get("realization_categories_candidate", []),
            "not_judgeable_reasons": card.get("not_judgeable_reasons", []),
            "claims": claim_rows,
            "source_only_refs": missing_refs,
        }
    return result


def compact_dialogue_row(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = [
        "row_status",
        "utt_id",
        "speaker_id",
        "utt_seq",
        "form",
        "original_form",
        "note",
        "start",
        "end",
        "derived_turn_id",
        "speaker_run_unit_count",
        "position_in_speaker_run",
        "speaker_change_before",
        "speaker_change_after",
        "source_note_overlap_flag",
        "timestamp_overlap_raw",
        "is_target",
    ]
    return {field: row.get(field, "") for field in fields}


def compact_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = [
        "utt_id",
        "year",
        "dialogue_id",
        "dialogue_speaker_ids",
        "n_dialogue_speakers",
        "co_speaker_ids",
        "n_co_speakers",
        "category_norm",
        "discourse_mode",
        "topic",
        "speaker_id",
        "sex",
        "age_norm",
        "birthplace_norm",
        "current_residence_norm",
        "form",
        "original_form",
        "note",
        "derived_turn_id",
        "speaker_run_unit_count",
        "target_position_in_speaker_run",
    ]
    return {field: row.get(field, "") for field in fields}


def copy_exact(source: Path, destination: Path) -> tuple[int, str]:
    require(source.is_file(), f"source asset missing: {source}")
    require(not destination.exists(), f"destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_sha = sha256_file(source)
    shutil.copy2(source, destination)
    copied_sha = sha256_file(destination)
    require(source_sha == copied_sha, f"copy SHA mismatch: {source} -> {destination}")
    return source.stat().st_size, source_sha


def materialize_assets(
    samples: list[dict[str, str]], partial_root: Path
) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    assets: list[dict[str, str]] = []
    projections: dict[str, Any] = {}
    sample_payload: dict[str, Any] = {}
    for row in samples:
        sample_id = row["sample_id"]
        source_wav = Path(row["wav_path"])
        source_textgrid = Path(row["active_textgrid_path"])
        asset_dir = partial_root / "assets" / sample_id
        bundle_wav = asset_dir / "target.wav"
        bundle_textgrid = asset_dir / "source.TextGrid"
        work_textgrid = partial_root / "praat_work" / sample_id / f"{sample_id}.TextGrid"
        wav_bytes, wav_sha = copy_exact(source_wav, bundle_wav)
        tg_bytes, tg_sha = copy_exact(source_textgrid, bundle_textgrid)
        _, work_sha = copy_exact(source_textgrid, work_textgrid)
        require(tg_sha == work_sha, f"Praat initial copy differs: {sample_id}")
        projection = parse_long_textgrid(source_textgrid)
        projection["target_xmin"] = float(row["target_xmin"])
        projection["target_xmax"] = float(row["target_xmax"])
        projections[sample_id] = projection
        bundle_wav_rel = bundle_wav.relative_to(partial_root).as_posix()
        bundle_textgrid_rel = bundle_textgrid.relative_to(partial_root).as_posix()
        work_textgrid_rel = work_textgrid.relative_to(partial_root).as_posix()
        assets.append(
            {
                "sample_id": sample_id,
                "phenomenon_code": row["phenomenon_code"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "source_wav_path": str(source_wav),
                "source_wav_bytes": str(wav_bytes),
                "source_wav_sha256": wav_sha,
                "bundle_wav_path": bundle_wav_rel,
                "bundle_wav_sha256": sha256_file(bundle_wav),
                "source_textgrid_path": str(source_textgrid),
                "source_textgrid_bytes": str(tg_bytes),
                "source_textgrid_sha256": tg_sha,
                "bundle_source_textgrid_path": bundle_textgrid_rel,
                "bundle_source_textgrid_sha256": sha256_file(bundle_textgrid),
                "praat_work_textgrid_path": work_textgrid_rel,
                "praat_work_initial_sha256": work_sha,
                "copy_status": "exact_read_only_source_copy_and_separate_praat_work_copy",
            }
        )
        sample_payload[sample_id] = {
            **row,
            "target_word_indices": json.loads(row["target_word_indices_json"]),
            "target_word_labels": json.loads(row["target_word_labels_json"]),
            "morphology_display": morphology_display(row),
            "target_audio": bundle_wav_rel,
            "source_textgrid_copy": bundle_textgrid_rel,
            "praat_work_textgrid": work_textgrid_rel,
            "source_textgrid_sha256": tg_sha,
            "source_wav_sha256": wav_sha,
        }
    return assets, projections, sample_payload


OPEN_PRAAT_PS1 = r'''[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^P2H-(PT|NAN|NAL|NI|LLN|VH|HIA)-20(20|21|22|23|24|25)-0[12]$')]
    [string]$SampleId,
    [string]$PraatExe = 'praat.exe'
)

$ErrorActionPreference = 'Stop'
$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$wavPath = Join-Path $bundleRoot (Join-Path 'assets' (Join-Path $SampleId 'target.wav'))
$textGridPath = Join-Path $bundleRoot (Join-Path 'praat_work' (Join-Path $SampleId ($SampleId + '.TextGrid')))
if (-not (Test-Path -LiteralPath $wavPath -PathType Leaf)) {
    throw ('WAV not found: ' + $wavPath)
}
if (-not (Test-Path -LiteralPath $textGridPath -PathType Leaf)) {
    throw ('TextGrid not found: ' + $textGridPath)
}
$resolvedWav = (Resolve-Path -LiteralPath $wavPath).Path
$resolvedTextGrid = (Resolve-Path -LiteralPath $textGridPath).Path
Start-Process -FilePath $PraatExe -ArgumentList @('--open', $resolvedWav, $resolvedTextGrid)
'''


START_HTML = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>7현상 2시간 파일럿 시작</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.65;color:#17212b}a{display:block;margin:.55rem 0;padding:.85rem 1rem;background:#eaf4fa;border-radius:10px;color:#164f7a;font-weight:700;text-decoration:none}.warn{background:#fff2cb;padding:1rem;border-radius:10px}li{margin:.35rem 0}code{overflow-wrap:anywhere}</style></head><body>
<h1>7현상 · 현상당 2시간 연구 파일럿</h1>
<p class="warn">탐색용입니다. 자동 실현 판정이나 정식 판정 ledger가 아닙니다. 각 현상은 문헌 20분 → 범위 10분 → 사례 60분 → 불확실 사례·Praat 필요 표시 20분 → 요약 10분 순서입니다.</p>
<p>원하는 현상을 하나 골라 시작하세요. 기본 화면은 같은 형태소 조합·단어순이며, 두 번째 확인은 고정 셔플 순서로 바꿀 수 있습니다.</p>
__LINKS__
<p><a href="STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html">전체 84건 화면 열기</a></p>
<h2>선별 재확인</h2>
<p>재확인 대상은 청취 확신도 ≤3 또는 scope unclear 또는 경계 불확실인 사례이며, 확실 사례 2–3건을 대조로 포함합니다. 20분 초과분은 다음 현상 전에 이월 기록합니다.</p>
<h2>Praat 경계 수정</h2>
<p>실현 판정이 경계 위치에 의존하고, 현재 TextGrid 경계가 표적 자음·모음 구간을 청취상 명백히 벗어날 때만 <em>필요</em>로 표시합니다. 판정과 무관한 미세 어긋남은 <em>불필요</em>로 두고 메모에만 적습니다. 첫 현상에서 <em>필요</em> 건수가 12건 중 0–4건 범위인지 점검합니다.</p>
<p>표시 후 PowerShell에서 <code>.\open_praat_sample.ps1 -SampleId P2H-NI-2024-01</code>처럼 실행합니다. Praat가 PATH에 없으면 <code>-PraatExe 'C:\경로\Praat.exe'</code>를 덧붙이세요. WAV는 수정하지 않고, <code>praat_work</code>의 TextGrid만 수정합니다.</p>
<h2>세션 절차 규칙</h2>
<ol>
<li>60분 사례 단계 시작 때 문헌·범위 패널을 접습니다. 먼저 듣고 실현 판정·확신도를 적은 뒤 문헌 연결 메모를 씁니다.</li>
<li>JSONL 불러오기 후 반드시 “n행 불러옴” 메시지를 확인하고, 없으면 진행하지 않습니다.</li>
<li>데이터 문제는 <code>[DATA]</code>, 도구 문제는 <code>[TOOL]</code> 접두어로 불확실성 메모에 적습니다.</li>
<li>세션마다 문헌 메모 끝에 “빌드 8043eb25…, 헤드폰, 조용한 방” 형식의 세션 노트 한 줄을 남깁니다.</li>
<li>export 직후 파일명에 날짜·현상을 붙여 정본 폴더에 1개만 보관하고, 다음 세션에는 그 1개만 불러옵니다.</li>
<li>현상 종료 전 12사례 listened, 불확실 목록 확정, 현상 요약 기록, JSONL export·보관 확인의 4항을 점검합니다. 중단 시 문헌 메모 끝에 “어디까지 완료” 한 줄을 남깁니다.</li>
</ol>
</body></html>'''


REVIEW_HTML = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>7현상 2시간 연구 파일럿</title>
<style>
:root{--ink:#17212b;--muted:#596b78;--line:#ced9e0;--bg:#edf2f5;--paper:#fff;--navy:#173b57;--blue:#eaf4fa;--amber:#fff2cb;--green:#e4f4ea;--red:#ffe8e4;--violet:#efe9f8;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;color:var(--ink)}*{box-sizing:border-box}body{margin:0;background:var(--bg);line-height:1.55}button,input,select,textarea{font:inherit}button{min-height:42px;border:0;border-radius:9px;padding:.55rem .85rem;background:#285f9e;color:#fff;font-weight:700;cursor:pointer}.secondary{background:#596d7b}.ghost{background:#e5edf2;color:#173b57}.danger{background:#8b4037}header{background:var(--navy);color:#fff;padding:1rem max(1rem,env(safe-area-inset-left))}header h1{font-size:1.28rem;margin:0 0 .35rem}.safety{margin:.25rem 0;font-size:.9rem}.layout{display:grid;grid-template-columns:300px minmax(0,1fr);max-width:1350px;margin:auto;min-height:calc(100vh - 110px)}aside{background:#f8fafb;border-right:1px solid var(--line);padding:1rem;position:sticky;top:0;height:100vh;overflow:auto}.control{display:grid;gap:.3rem;margin-bottom:.7rem}.control select,.control input,.form select,.form input,.form textarea{width:100%;min-height:40px;border:1px solid #8da0ad;border-radius:8px;background:#fff;padding:.5rem;color:var(--ink)}#sample-list{display:grid;gap:.4rem}.sample-button{display:block;width:100%;text-align:left;background:#fff;color:var(--ink);border:1px solid var(--line)}.sample-button.active{border:3px solid #2b6c9d;background:var(--blue)}.sample-button small{display:block;color:var(--muted)}main{min-width:0;padding:1rem}.topnav{display:flex;align-items:center;justify-content:space-between;gap:.5rem;position:sticky;top:0;background:var(--bg);padding:.35rem 0;z-index:5}.panel{background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:1rem;margin:.75rem 0;box-shadow:0 2px 8px #173b5710}.tag{display:inline-block;border-radius:999px;padding:.12rem .55rem;font-size:.8rem;font-weight:750}.primary{background:var(--green);color:#176742}.peripheral,.exploratory,.surface_branch_probe,.compoundness_probe{background:var(--amber);color:#765500}.meta{color:var(--muted);overflow-wrap:anywhere}.warning,.recheck{background:var(--amber);padding:.8rem;border-radius:9px}.recheck{border:2px solid #bd7600}.utterance{font-size:1.25rem;background:#f5efe2;padding:1rem;border-radius:10px}.utterance mark{background:#ffd666;color:#17212b;border-radius:4px;padding:.04em .15em;box-shadow:0 0 0 2px #9d6100}.morphs{display:flex;gap:.55rem;flex-wrap:wrap;align-items:center}.morph{border:2px solid #2a729d;border-radius:9px;padding:.55rem .75rem;background:#eef7fc}.boundary{font-weight:800;font-size:1.2rem;color:#8d3d32}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}.form{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}.form label{display:grid;gap:.25rem;font-weight:650}.form .wide{grid-column:1/-1}.form textarea{min-height:72px;resize:vertical}.check{display:flex!important;align-items:center;gap:.5rem}.check input{width:22px;min-height:22px}.actions{display:flex;gap:.5rem;flex-wrap:wrap;align-items:center}.saved{color:#176742;font-weight:750}.claim{border-left:4px solid #6a5a9a;padding:.55rem .75rem;margin:.65rem 0;background:#f8f5fc}.claim p{margin:.25rem 0}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.9rem}th,td{padding:.45rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}details{border-top:1px solid var(--line);padding:.7rem 0}summary{font-weight:750;cursor:pointer}.transcript-tools{display:flex;gap:.5rem;flex-wrap:wrap;margin:.5rem 0}.transcript-tools input{flex:1;min-width:180px}.transcript{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:9px}.transcript-row{display:grid;grid-template-columns:72px 80px 85px 1fr;gap:.4rem;width:100%;text-align:left;background:#fff;color:var(--ink);border:0;border-bottom:1px solid var(--line);border-radius:0;font-weight:400}.transcript-row.target{background:#fff0cc;border-left:5px solid #bd7600}.transcript-row.selected{box-shadow:inset 0 0 0 3px #2b6c9d}.tier{margin:.5rem 0}.tier-label{font-weight:700;font-size:.85rem}.track{position:relative;height:34px;background:#eef2f4;border:1px solid var(--line);overflow:hidden}.interval{position:absolute;top:0;height:100%;border-right:1px solid #9cb0bc;padding:2px;font-size:.7rem;overflow:hidden;white-space:nowrap}.interval.hit{background:#ffd666}.target-span{position:absolute;top:0;height:100%;background:#e95d4b35;border-left:2px solid #b63c2d;border-right:2px solid #b63c2d;pointer-events:none}.empty{color:var(--muted);font-style:italic}.copytext{font-family:Consolas,monospace;background:#eef2f4;padding:.5rem;border-radius:7px;overflow-wrap:anywhere}
@media(max-width:850px){.layout{display:block}.layout aside{position:static;height:auto;border:0;border-bottom:1px solid var(--line)}#sample-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:260px;overflow:auto}.grid2,.form{grid-template-columns:1fr}.form .wide{grid-column:auto}.transcript-row{grid-template-columns:55px 62px 68px 1fr}main{padding:.65rem}.panel{padding:.8rem}}
</style></head><body>
<header><h1>7현상 · 현상당 2시간 연구 파일럿</h1><p class="safety">탐색용 기록입니다. 자동 실현 판정·정식 판정 ledger·MFA/KOINA/wav2vec2 결과가 아닙니다.</p><p class="safety">음성은 발화 WAV의 SHA 동일 복사본이며 자르거나 수정하지 않았습니다. TextGrid 수정은 praat_work 복사본에서만 합니다.</p></header>
<div class="layout"><aside>
<div class="control"><label>현상<select id="phenomenon"></select></label></div>
<div class="control"><label>보기 순서<select id="order-mode"><option value="grouped">같은 형태소 조합·단어순</option><option value="shuffled">고정 셔플(두 번째 확인)</option></select></label></div>
<div class="control"><label>후보 검색<input id="sample-search" placeholder="단어·형태소·연도·ID"></label></div>
<p id="progress" class="meta"></p><div id="sample-list"></div>
</aside><main>
<nav class="topnav"><button id="prev" type="button">← 이전</button><strong id="position"></strong><button id="next" type="button">다음 →</button></nav>
<section class="panel" id="literature-panel"><h2 id="literature-title"></h2><div id="schedule" class="warning"></div><p id="definition"></p><p id="literature-path" class="meta"></p><details open><summary>이 파일럿의 범위·제외·혼란변수</summary><div id="scope-contract"></div></details><details><summary>문헌 주장과 한계 — 20분 읽기</summary><div id="claims"></div></details><label>현상 전체 문헌 메모<textarea id="phenomenon-lit-note" style="width:100%;min-height:80px"></textarea></label><div class="actions"><button type="button" id="phenomenon-summary-save">현상 요약 저장</button><span id="phenomenon-summary-status" class="saved"></span></div><p class="meta">현상 요약은 사례 행과 분리된 탐색 전용 revision으로 저장되며 sample_id 필드는 생략됩니다.</p></section>
<section class="panel"><div><span id="role-tag" class="tag"></span> <span id="sample-title"></span></div><p id="sample-meta" class="meta"></p><p id="active-form" class="utterance"></p><div id="morph-display" class="morphs"></div><p id="morph-limit" class="meta"></p><p id="scope-warning" class="warning"></p></section>
<section class="panel grid2"><div><h3>대상 발화 음성</h3><audio id="target-audio" controls preload="metadata" style="width:100%"></audio><div class="actions"><button type="button" class="ghost" id="target-jump">표적 구간으로 이동</button><span id="target-jump-status" class="meta"></span></div><p class="meta">발화 전체 exact copy입니다. 잘라낸 표적 음성이 아닙니다.</p></div><div><h3>화자·대화 맥락</h3><div id="speaker-meta"></div></div></section>
<section class="panel"><details open><summary>읽기 전용 TextGrid 패널</summary><p id="textgrid-meta" class="meta"></p><div id="tiers"></div><p><a id="source-textgrid-link" href="">원본 보존 복사본</a> · <a id="work-textgrid-link" href="">Praat 수정 작업본</a></p><p id="praat-command" class="copytext"></p><button type="button" class="ghost" id="copy-praat">Praat 명령 복사</button></details></section>
<section class="panel"><details><summary>전체 대화 전사 검색·문맥 행 선택</summary><p class="warning">여기 보이는 derived turn은 같은 화자의 연속 전사 단위를 묶은 탐색 표지입니다. 원자료에 금표준 turn 표지가 있는 것은 아닙니다. 끊겨 보이는 것은 원 전사 단위가 나뉘어 있기 때문일 수 있습니다.</p><div class="transcript-tools"><input id="dialogue-search" placeholder="전체 대화에서 검색"><label class="check"><input id="dialogue-all" type="checkbox"> 전체 행</label></div><p id="selected-context" class="meta"></p><div id="dialogue" class="transcript"></div></details></section>
<section class="panel"><h2>사례별 탐색 기록</h2><p id="recheck-banner" class="recheck" style="display:none">재확인 모드 — 1차 판정(들린 실현·청취 확신도)은 가려집니다. 재확인 대상: 청취 확신도 ≤3 / scope unclear / 경계 불확실 + 대조 2–3건</p><form id="review-form" class="form">
<label class="check"><input name="listened" type="checkbox"> 이 사례를 청취함</label><label>연구자 이름<input name="reviewer"></label>
<label>범위 판정<select name="scope_decision"><option value=""></option><option value="primary_central">일반적·중심 환경</option><option value="peripheral">비전형이지만 관련 가능</option><option value="exploratory">탐색 환경</option><option value="out_of_scope">범위 밖</option><option value="unclear">불확실</option></select></label>
<label>환경 판정 확신도<select name="environment_confidence"><option value=""></option><option value="1">1 · 추측</option><option value="2">2 · 인상 수준</option><option value="3">3 · 단서 있으나 상충</option><option value="4">4 · 단서 우세</option><option value="5">5 · 단서 명확·재청취 불필요</option></select></label>
<label>들린 실현<select name="realization_impression" id="realization-impression"></select></label><label>청취 확신도<select name="realization_confidence"><option value=""></option><option value="1">1 · 추측</option><option value="2">2 · 인상 수준</option><option value="3">3 · 단서 있으나 상충</option><option value="4">4 · 단서 우세</option><option value="5">5 · 단서 명확·재청취 불필요</option></select></label>
<label>문맥 충분성<select name="context_sufficient"><option value=""></option><option value="sufficient">충분</option><option value="need_more">더 필요</option><option value="not_relevant">해당 없음</option><option value="unclear">불확실</option></select></label>
<label>Praat 경계 수정 필요<select name="boundary_edit_need"><option value=""></option><option value="no">불필요</option><option value="yes">필요</option><option value="unclear">불확실</option></select><small class="meta">실현 판정이 경계 위치에 의존하고 경계가 표적 자음·모음 구간을 청취상 명백히 벗어날 때만 ‘필요’입니다.</small></label>
<label id="compoundness-label">PT 합성어성<select name="compoundness_decision"><option value=""></option><option value="confirmed_compound">합성어 확인</option><option value="not_compound">합성어 아님</option><option value="unclear">불확실</option></select></label>
<label>대화 유형 잠정 메모<select name="context_type"><option value=""></option><option value="dialogue">대화</option><option value="monologue_like">혼잣말·독백에 가까움</option><option value="mixed">혼합</option><option value="unclear">불확실</option></select></label>
<label class="wide">형태론·환경 메모<textarea name="morph_environment_note"></textarea></label><label class="wide">음운·음향 인상 메모<textarea name="phonological_note"></textarea></label><label class="wide">문헌과 연결되는 점<textarea name="literature_connection_note"></textarea></label><label class="wide">불확실성·후속 질문<textarea name="uncertainty_and_question"></textarea></label>
<input name="selected_context_utt_ids_json" type="hidden"><div class="wide actions"><button type="submit">수정본 저장</button><span id="saved" class="saved"></span></div></form></section>
<section class="panel"><h2>기록 파일</h2><p>브라우저 저장소는 임시입니다. 작업을 마칠 때마다 JSONL을 내려받으세요. 이전 JSONL을 불러오면 수정 이력이 덧붙습니다.</p><div class="actions"><button id="export" type="button">P2H_EXPLORATORY_REVIEWS.jsonl 저장</button><label class="ghost" style="padding:.55rem .85rem;border-radius:9px;font-weight:700">JSONL 불러오기<input id="import" type="file" accept=".jsonl,application/json" style="display:none"></label></div><p id="import-status" class="meta"></p></section>
</main></div>
<script id="samples-data" type="application/json">__SAMPLES__</script><script id="dialogues-data" type="application/json">__DIALOGUES__</script><script id="metadata-data" type="application/json">__METADATA__</script><script id="literature-data" type="application/json">__LITERATURE__</script><script id="textgrids-data" type="application/json">__TEXTGRIDS__</script><script id="build-data" type="application/json">__BUILD__</script>
<script>
const SAMPLES=JSON.parse(document.getElementById('samples-data').textContent);
const DIALOGUES=JSON.parse(document.getElementById('dialogues-data').textContent);
const METADATA=JSON.parse(document.getElementById('metadata-data').textContent);
const LITERATURE=JSON.parse(document.getElementById('literature-data').textContent);
const TEXTGRIDS=JSON.parse(document.getElementById('textgrids-data').textContent);
const BUILD=JSON.parse(document.getElementById('build-data').textContent);
const SAMPLE_MAP=Object.fromEntries(SAMPLES.map(x=>[x.sample_id,x]));
const STORAGE_KEY='stage2_two_hour_seven_phenomena_reviews_v1_'+BUILD.samples_sha256.slice(0,12);
const SUMMARY_SCHEMA='stage2_two_hour_phenomenon_summary.v1';
const SUMMARY_ROLE='phenomenon_summary_exploratory_only_not_formal_ledger';
let imported=[];
let currentCode=new URLSearchParams(location.search).get('phenomenon');
if(!LITERATURE[currentCode])currentCode='PT';
let currentId='';
let visible=[];
let dirty=false;
let selectedContext=new Set();
const byId=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const parseLocal=()=>{try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]')}catch{return[]}};
const saveLocal=rows=>localStorage.setItem(STORAGE_KEY,JSON.stringify(rows));
const reviewRows=()=>[...imported,...parseLocal()];
const isSummaryRecord=row=>row?.schema_version===SUMMARY_SCHEMA&&row?.record_role===SUMMARY_ROLE;
const isSampleRecord=row=>!isSummaryRecord(row)&&Boolean(SAMPLE_MAP[row?.sample_id]);
function newest(rows){let best=null;rows.forEach((row,index)=>{const time=Date.parse(row.reviewed_at||'');if(!best||time>best.time||(time===best.time&&index>best.index))best={row,time,index}});return best?.row||null}
const latest=()=>{const out={};reviewRows().filter(isSampleRecord).forEach((r,i)=>{const p=out[r.sample_id];const t=Date.parse(r.reviewed_at||'');if(!p||t>p.t||(t===p.t&&i>p.i))out[r.sample_id]={r,t,i}});return Object.fromEntries(Object.entries(out).map(([k,v])=>[k,v.r]));};
const summaryRows=code=>reviewRows().filter(r=>isSummaryRecord(r)&&r.phenomenon_code===code);
const latestImportedSummary=code=>newest(imported.filter(r=>isSummaryRecord(r)&&r.phenomenon_code===code));
const latestSampleNote=code=>newest(reviewRows().filter(r=>isSampleRecord(r)&&r.phenomenon_code===code&&r.phenomenon_literature_note!=null));
function orderedSamples(){const mode=byId('order-mode').value;return SAMPLES.filter(s=>s.phenomenon_code===currentCode).sort((a,b)=>Number(a[mode+'_order'])-Number(b[mode+'_order']));}function applyFilter(){const q=byId('sample-search').value.trim().toLowerCase();visible=orderedSamples().filter(s=>!q||[s.sample_id,s.year,s.active_form,s.morpheme_combination,s.word_group,s.utt_id].join(' ').toLowerCase().includes(q));if(!visible.some(s=>s.sample_id===currentId))currentId=visible[0]?.sample_id||'';renderList();if(currentId)renderCurrent();}
function renderList(){const done=latest();byId('sample-list').innerHTML=visible.map(s=>`<button type="button" class="sample-button ${s.sample_id===currentId?'active':''}" data-id="${esc(s.sample_id)}">${done[s.sample_id]?.listened?'✓ ':''}${esc(s.year)} · ${esc(s.target_word_labels.join(' · '))}<small>${esc(s.sample_id)} · ${esc(s.population_role)}</small></button>`).join('')||'<p class="empty">검색 결과 없음</p>';document.querySelectorAll('.sample-button').forEach(b=>b.onclick=()=>requestOpen(b.dataset.id));const codeRows=SAMPLES.filter(s=>s.phenomenon_code===currentCode);byId('progress').textContent=`${LABEL()} · 저장된 청취 ${codeRows.filter(s=>done[s.sample_id]?.listened).length}/12`;}
function LABEL(){return LITERATURE[currentCode]?.label_ko||currentCode}function requestOpen(id){if(dirty&&!confirm('저장하지 않은 입력이 있습니다. 버리고 이동할까요?'))return;currentId=id;dirty=false;renderCurrent();renderList();}
function highlight(s){const indices=new Set(s.target_word_indices.map(Number));let n=0;return String(s.active_form).split(/(\s+)/).map(p=>/^\s+$/.test(p)?p:(indices.has(++n)?`<mark>${esc(p)}</mark>`:esc(p))).join('');}
function renderLiterature(){const l=LITERATURE[currentCode];byId('literature-title').textContent=`${currentCode} · ${l.label_ko}`;byId('definition').textContent=l.definition_summary;byId('literature-path').textContent=`문헌 종합 초안: ${l.literature_synthesis_path} · 근거 수준 ${l.literature_evidence_level}`;byId('schedule').innerHTML=l.pilot_schedule.map(x=>`<strong>${x.minutes}분</strong> ${esc(x.activity)}`).join(' → ');const populations=Object.entries(l.population_contract).map(([k,rows])=>`<h4>${esc(k)}</h4><ul>${rows.map(x=>`<li><strong>${esc(x.condition_id)}</strong> ${esc(x.description)} · 우선 ${esc(x.priority)} · ${esc((x.evidence_refs||[]).join(', '))}</li>`).join('')}</ul>`).join('');const confounds=`<h4>혼란변수</h4><ul>${l.confounds.map(x=>`<li>${esc(x.name)} · ${esc((x.evidence_refs||[]).join(', '))}</li>`).join('')}</ul><h4>근거 한계</h4><ul>${l.evidence_limits.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>열린 질문</h4><ul>${l.open_questions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;byId('scope-contract').innerHTML=populations+confounds;byId('claims').innerHTML=l.claims.map(c=>`<div class="claim"><strong>${esc(c.claim_id)} · ${esc(c.source_id)}</strong><p>${esc(c.claim_ko)}</p><p><b>적용:</b> ${esc(c.applies_when)}</p><p><b>확립하지 않는 것:</b> ${esc(c.does_not_establish)}</p><p><b>검토 질문:</b> ${esc(c.review_question)}</p><p class="meta">${esc(c.citation)} · 인쇄면 ${esc(c.printed_page??'—')} / PDF면 ${esc(c.pdf_page??'—')}</p></div>`).join('')+`<p class="meta">source-only refs: ${esc(l.source_only_refs.join(', ')||'없음')}</p>`;const key=STORAGE_KEY+'_lit_'+currentCode;const localNote=localStorage.getItem(key);const importedSummary=latestImportedSummary(currentCode);const sampleNote=latestSampleNote(currentCode);byId('phenomenon-lit-note').value=localNote!==null?localNote:(importedSummary?.phenomenon_literature_note??sampleNote?.phenomenon_literature_note??'');const latestSummary=newest(summaryRows(currentCode));byId('phenomenon-summary-status').textContent=latestSummary?.reviewed_at?`최근 현상 요약 ${latestSummary.reviewed_at}`:'';}
function renderMorph(s){const d=s.morphology_display;byId('morph-display').innerHTML=d.segments.map(x=>`<span class="morph"><strong>${esc(x.surface||'미상')}</strong> / ${esc(x.pos||'POS 미상')}<br><small>초점 ${esc(x.focus||'—')}</small></span>`).join('<span class="boundary">│</span>')+`<span class="boundary">${esc(d.boundary||'—')}</span>`;byId('morph-limit').textContent=`${d.status}. 검색 환경 근거이며 실제 실현이나 음향 경계의 자동 판정이 아닙니다.`;}
function renderMetadata(s){const m=METADATA[s.utt_id]||{};byId('speaker-meta').innerHTML=`<table><tr><th>맥락</th><td>${esc(m.discourse_mode||m.category_norm||'미상')} · ${esc(m.topic||'주제 미상')}</td></tr><tr><th>화자</th><td>${esc(m.speaker_id||s.speaker_id||'미상')} · ${esc(m.sex||'성별 미상')} · ${esc(m.age_norm||'연령 미상')}</td></tr><tr><th>지역</th><td>출생 ${esc(m.birthplace_norm||'미상')} · 현재 ${esc(m.current_residence_norm||'미상')}</td></tr><tr><th>대화자</th><td>${esc(m.n_dialogue_speakers||'미상')}명 · ${esc(m.co_speaker_ids||'')}</td></tr><tr><th>derived turn</th><td>${esc(m.derived_turn_id||'미상')} · 같은 화자 연속 전사 단위 ${esc(m.speaker_run_unit_count||'—')}개 중 ${esc(m.target_position_in_speaker_run||'—')}번째</td></tr></table>`;}
function renderTiers(s){const g=TEXTGRIDS[s.sample_id];const span=Math.max(.000001,g.xmax-g.xmin);const left=100*(g.target_xmin-g.xmin)/span;const width=100*(g.target_xmax-g.target_xmin)/span;byId('textgrid-meta').textContent=`전체 ${g.xmin.toFixed(3)}–${g.xmax.toFixed(3)}초 · 표적 ${g.target_xmin.toFixed(3)}–${g.target_xmax.toFixed(3)}초 · ${g.tiers.length} tiers`;byId('tiers').innerHTML=g.tiers.map(t=>`<div class="tier"><div class="tier-label">${esc(t.name)}</div><div class="track">${t.intervals.filter(i=>i.xmax>i.xmin).map(i=>{const l=100*(i.xmin-g.xmin)/span,w=100*(i.xmax-i.xmin)/span,hit=i.xmax>g.target_xmin&&i.xmin<g.target_xmax;return `<span class="interval ${hit?'hit':''}" style="left:${l}%;width:${Math.max(w,.2)}%" title="${esc(i.text)} ${i.xmin.toFixed(3)}–${i.xmax.toFixed(3)}">${esc(i.text)}</span>`}).join('')}<span class="target-span" style="left:${left}%;width:${Math.max(width,.3)}%"></span></div></div>`).join('');}
function dialogueRows(s){return DIALOGUES[s.utt_id]||[]}function rowButton(r){const selected=selectedContext.has(r.utt_id);return `<button type="button" class="transcript-row ${r.is_target?'target':''} ${selected?'selected':''}" data-utt="${esc(r.utt_id)}"><span>${esc(r.utt_seq)}</span><span>${esc(r.speaker_id)}</span><span>${esc(r.derived_turn_id)}</span><span>${esc(r.form||r.original_form||'(없음)')}</span></button>`}function renderDialogue(s){const rows=dialogueRows(s);const q=byId('dialogue-search').value.trim().toLowerCase();const target=rows.findIndex(x=>x.is_target);const shown=q?rows.filter(x=>[x.form,x.original_form,x.note,x.speaker_id,x.utt_id].join(' ').toLowerCase().includes(q)):(byId('dialogue-all').checked?rows:rows.filter((_,i)=>Math.abs(i-target)<=10));byId('dialogue').innerHTML=shown.map(rowButton).join('')||'<p class="empty">대화 행 없음</p>';document.querySelectorAll('.transcript-row').forEach(b=>b.onclick=()=>{selectedContext.has(b.dataset.utt)?selectedContext.delete(b.dataset.utt):selectedContext.add(b.dataset.utt);syncSelected();renderDialogue(s)});syncSelected();}function syncSelected(){byId('selected-context').textContent=`선택한 문맥 행: ${Array.from(selectedContext).join(', ')||'없음'}`;byId('review-form').elements.selected_context_utt_ids_json.value=JSON.stringify(Array.from(selectedContext));}
function blankOptions(values){return '<option value=""></option>'+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('')}
function restoreForm(s){const last=latest()[s.sample_id]||{};const shuffled=byId('order-mode').value==='shuffled';const blindRecheck=shuffled&&last.review_order_mode==='grouped';const form=byId('review-form');form.reset();Array.from(form.elements).forEach(el=>{if(!el.name)return;if(blindRecheck&&(el.name==='realization_impression'||el.name==='realization_confidence'))return;if(el.type==='checkbox')el.checked=Boolean(last[el.name]);else if(last[el.name]!=null)el.value=String(last[el.name])});try{selectedContext=new Set(JSON.parse(last.selected_context_utt_ids_json||'[]'))}catch{selectedContext=new Set()}byId('realization-impression').innerHTML=blankOptions(LITERATURE[currentCode].realization_categories_candidate);if(!blindRecheck&&last.realization_impression)byId('realization-impression').value=last.realization_impression;if(blindRecheck){byId('realization-impression').value='';form.elements.realization_confidence.value=''}byId('recheck-banner').style.display=shuffled?'block':'none';byId('compoundness-label').style.display=currentCode==='PT'?'grid':'none';dirty=false;byId('saved').textContent=blindRecheck?'재확인용 판정 두 필드를 비웠습니다.':(last.reviewed_at?`마지막 저장 ${last.reviewed_at}`:'');}
function renderCurrent(){const s=SAMPLE_MAP[currentId];if(!s)return;renderLiterature();const ordered=orderedSamples();const index=ordered.findIndex(x=>x.sample_id===currentId);byId('position').textContent=`${index+1}/12 · ${currentCode}`;byId('role-tag').textContent=s.population_role;byId('role-tag').className=`tag ${s.population_role}`;byId('sample-title').textContent=`${s.phenomenon_label} · ${s.year}`;byId('sample-meta').textContent=`${s.sample_id} · ${s.utt_id} · ${s.environment_scope} · ${s.query_id}`;byId('active-form').innerHTML=highlight(s);renderMorph(s);byId('scope-warning').textContent=s.interpretation_limit+(s.phenomenon_code==='PT'?' 합성어성을 확인하기 전에는 중심 PT 사례가 아닙니다.':'');byId('target-audio').src=s.target_audio;renderMetadata(s);renderTiers(s);byId('source-textgrid-link').href=s.source_textgrid_copy;byId('work-textgrid-link').href=s.praat_work_textgrid;const cmd=`.\\open_praat_sample.ps1 -SampleId ${s.sample_id}`;byId('praat-command').textContent=cmd;byId('dialogue-search').value='';byId('dialogue-all').checked=false;restoreForm(s);renderDialogue(s);}
function move(delta){if(!visible.length)return;const i=visible.findIndex(s=>s.sample_id===currentId);requestOpen(visible[(i+delta+visible.length)%visible.length].sample_id)}function makeUuid(){return crypto.randomUUID?crypto.randomUUID():'evt-'+Date.now()+'-'+Math.random().toString(16).slice(2)}function formValues(){const out={};new FormData(byId('review-form')).forEach((v,k)=>out[k]=v);out.listened=byId('review-form').elements.listened.checked;return out}
byId('review-form').addEventListener('submit',e=>{e.preventDefault();const s=SAMPLE_MAP[currentId];const prior=reviewRows().filter(x=>isSampleRecord(x)&&x.sample_id===currentId);const row={schema_version:'stage2_two_hour_exploratory_review.v1',event_uuid:makeUuid(),revision_seq:prior.length+1,supersedes_event_uuid:prior.at(-1)?.event_uuid||'',sample_id:s.sample_id,phenomenon_code:s.phenomenon_code,year:s.year,utt_id:s.utt_id,physical_occurrence_ref:s.physical_occurrence_ref,query_id:s.query_id,population_role_at_selection:s.population_role,review_order_mode:byId('order-mode').value,...formValues(),phenomenon_literature_note:byId('phenomenon-lit-note').value,record_role:'exploratory_pilot_only_not_formal_realization_ledger',reviewed_at:new Date().toISOString()};const local=parseLocal();local.push(row);saveLocal(local);localStorage.setItem(STORAGE_KEY+'_lit_'+currentCode,byId('phenomenon-lit-note').value);dirty=false;byId('saved').textContent=`저장됨 ${row.reviewed_at}`;renderList()});
byId('phenomenon-summary-save').onclick=()=>{const prior=summaryRows(currentCode);const previous=newest(prior);const revision=Math.max(0,...prior.map(row=>Number(row.revision_seq)||0))+1;const row={schema_version:SUMMARY_SCHEMA,event_uuid:makeUuid(),revision_seq:revision,supersedes_event_uuid:previous?.event_uuid||'',phenomenon_code:currentCode,phenomenon_literature_note:byId('phenomenon-lit-note').value,record_role:SUMMARY_ROLE,reviewed_at:new Date().toISOString()};const local=parseLocal();local.push(row);saveLocal(local);localStorage.setItem(STORAGE_KEY+'_lit_'+currentCode,row.phenomenon_literature_note);byId('phenomenon-summary-status').textContent=`현상 요약 저장됨 ${row.reviewed_at}`;renderList()};
byId('review-form').addEventListener('input',()=>{dirty=true;byId('saved').textContent='저장하지 않은 변경'});
byId('phenomenon-lit-note').addEventListener('input',()=>{localStorage.setItem(STORAGE_KEY+'_lit_'+currentCode,byId('phenomenon-lit-note').value);byId('phenomenon-summary-status').textContent='문헌 메모 자동 저장됨'});
byId('phenomenon').onchange=()=>{if(dirty&&!confirm('저장하지 않은 입력이 있습니다. 버리고 현상을 바꿀까요?')){byId('phenomenon').value=currentCode;return}currentCode=byId('phenomenon').value;window.history.replaceState(null,'',`?phenomenon=${currentCode}`);currentId='';applyFilter()};
byId('order-mode').onchange=applyFilter;
byId('sample-search').oninput=applyFilter;
byId('prev').onclick=()=>move(-1);
byId('next').onclick=()=>move(1);
byId('target-jump').onclick=()=>{const target=Number(TEXTGRIDS[currentId]?.target_xmin);const audio=byId('target-audio');if(!Number.isFinite(target))return;const seek=()=>{audio.currentTime=target;byId('target-jump-status').textContent=`표적 ${target.toFixed(3)}초로 이동됨`};if(audio.readyState>=3)seek();else{byId('target-jump-status').textContent='오디오 정보를 불러오는 중…';audio.addEventListener('canplay',seek,{once:true});audio.load()}};
byId('dialogue-search').oninput=()=>renderDialogue(SAMPLE_MAP[currentId]);
byId('dialogue-all').onchange=()=>renderDialogue(SAMPLE_MAP[currentId]);
byId('copy-praat').onclick=()=>navigator.clipboard?.writeText(byId('praat-command').textContent).then(()=>byId('copy-praat').textContent='복사됨');
function jsonl(rows){return rows.map(r=>JSON.stringify(r)).join('\n')+(rows.length?'\n':'')}
byId('export').onclick=()=>{const rows=reviewRows();const blob=new Blob([jsonl(rows)],{type:'application/x-ndjson;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='P2H_EXPLORATORY_REVIEWS.jsonl';a.click();URL.revokeObjectURL(a.href)};
byId('import').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;let lineNumber=1;try{const text=await file.text();const rows=[];for(const [i,line] of text.split(/\r?\n/).entries()){lineNumber=i+1;if(!line.trim())continue;let row;try{row=JSON.parse(line)}catch(error){throw new Error(`JSON 구문 오류: ${error.message}`)}if(isSummaryRecord(row)){if(!LITERATURE[row.phenomenon_code])throw new Error(`알 수 없는 phenomenon_code ${row.phenomenon_code}`)}else if(!SAMPLE_MAP[row.sample_id]){throw new Error(`알 수 없는 sample_id ${row.sample_id}`)}rows.push(row)}imported=rows;byId('import-status').textContent=`${rows.length}행 불러옴`;renderLiterature();restoreForm(SAMPLE_MAP[currentId]);renderList()}catch(error){byId('import-status').textContent=`불러오기 실패 — 행 ${lineNumber}: ${error.message||error}`}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
byId('phenomenon').innerHTML=Object.keys(LITERATURE).map(c=>`<option value="${c}">${c} · ${esc(LITERATURE[c].label_ko)}</option>`).join('');byId('phenomenon').value=currentCode;applyFilter();
</script></body></html>'''


def build_html(
    *, samples: list[dict[str, Any]], dialogues: Mapping[str, Any], metadata: Mapping[str, Any],
    literature: Mapping[str, Any], projections: Mapping[str, Any], build_meta: Mapping[str, Any]
) -> str:
    replacements = {
        "__SAMPLES__": json_for_html(samples),
        "__DIALOGUES__": json_for_html(dialogues),
        "__METADATA__": json_for_html(metadata),
        "__LITERATURE__": json_for_html(literature),
        "__TEXTGRIDS__": json_for_html(projections),
        "__BUILD__": json_for_html(build_meta),
    }
    document = REVIEW_HTML
    for marker, value in replacements.items():
        require(document.count(marker) == 1, f"HTML marker count {marker}")
        document = document.replace(marker, value)
    return document


def build_start_html(literature: Mapping[str, Any]) -> str:
    require(list(literature) == EXPECTED_CODES, "START_HERE literature order/codes")
    links = "".join(
        f'<a href="STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html?phenomenon={code}">'
        f'{code} · {html.escape(str(literature[code]["label_ko"]))} 시작</a>'
        for code in EXPECTED_CODES
    )
    return START_HTML.replace("__LINKS__", links)


def build_readme() -> str:
    return (
        "# 7현상 · 현상당 2시간 연구 파일럿\n\n"
        "## 기본 진행\n\n"
        "1. `START_HERE.html`을 엽니다.\n"
        "2. 한 현상을 골라 문헌 20분, 범위 10분, 사례 60분, 선별 재확인·Praat 필요 표시 20분, 요약 10분 순으로 진행합니다.\n"
        "3. 사례 기록은 탐색용이며 정식 realization ledger가 아닙니다. 매 세션 뒤 JSONL을 저장합니다.\n"
        "4. 전체 대화의 derived turn은 같은 화자 연속 전사 단위를 묶은 탐색 표지이며 금표준 turn이 아닙니다.\n\n"
        "## 선별 재확인\n\n"
        "재확인 대상은 청취 확신도 ≤3 또는 scope unclear 또는 boundary_edit_need 불확실인 사례이며, 확실 사례 2–3건을 대조로 포함합니다. 20분 초과분은 다음 현상 전에 이월 기록합니다.\n\n"
        "## Praat '경계 수정 필요' 기준\n\n"
        "실현 판정이 경계 위치에 의존하고, 현재 TextGrid 경계가 표적 자음·모음 구간을 청취상 명백히 벗어날 때만 '필요'로 표시합니다. 판정과 무관한 미세 어긋남은 '불필요'로 두고 메모에만 적습니다. 첫 현상에서 '필요' 건수가 12건 중 0–4건 범위인지 점검합니다.\n\n"
        "필요하면 `open_praat_sample.ps1 -SampleId <ID>`를 실행하고 `praat_work`의 TextGrid만 수정합니다. WAV는 수정하지 않습니다.\n\n"
        "## 절차 규칙\n\n"
        "1. 60분 사례 단계 시작 때 문헌·범위 패널을 접습니다. 먼저 듣고 실현 판정·확신도를 적은 뒤 문헌 연결 메모를 씁니다.\n"
        "2. JSONL 불러오기 후 반드시 `n행 불러옴` 메시지를 확인하고, 없으면 진행하지 않습니다.\n"
        "3. 데이터 문제는 `[DATA]`, 도구 문제는 `[TOOL]` 접두어로 불확실성 메모에 적습니다.\n"
        "4. 세션마다 문헌 메모 끝에 `빌드 8043eb25…, 헤드폰, 조용한 방` 형식의 세션 노트 한 줄을 남깁니다.\n"
        "5. export 직후 파일명에 날짜·현상을 붙여 정본 폴더에 1개만 보관하고, 다음 세션에는 그 1개만 불러옵니다.\n"
        "6. 현상 종료 조건은 12사례 listened, 불확실 목록 확정, 현상 요약 기록, JSONL export·보관 확인의 4항입니다. 중단 시 문헌 메모 끝에 `어디까지 완료` 한 줄을 남깁니다.\n\n"
        "## 현상 요약 행\n\n"
        "`현상 요약 저장`은 `stage2_two_hour_phenomenon_summary.v1` 행을 append합니다. 이 현상 수준 행에는 `sample_id` 필드를 넣지 않으며, 사례 집계에서는 제외합니다.\n"
    )


def extract_json_script(document: str, element_id: str) -> Any:
    match = re.search(
        rf'<script id="{re.escape(element_id)}" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    require(match is not None, f"embedded JSON script missing: {element_id}")
    return json.loads(match.group(1).replace("<\\/", "</"))


def verify_package_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / "SHA256SUMS.txt"
    require(manifest_path.is_file(), f"source manifest missing: {manifest_path}")
    records = 0
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"source manifest syntax line {line_number}")
        expected, relative = match.groups()
        path = package_dir / Path(relative)
        require(path.is_file(), f"source manifest file missing: {relative}")
        require(sha256_file(path) == expected, f"source manifest SHA mismatch: {relative}")
        records += 1
    require(records > 0, "source manifest is empty")
    return {
        "path": str(manifest_path),
        "sha256": sha256_file(manifest_path),
        "records": records,
    }


def repackage_from_verified_package(
    *, source_package_dir: Path, samples_path: Path, correction_receipt_path: Path,
    cards_path: Path, output_dir: Path
) -> dict[str, Any]:
    allowed = (PROJECT_ROOT / ALLOWED_OUTPUT_ROOT).resolve()
    source_package_dir = source_package_dir.resolve()
    output_dir = output_dir.resolve()
    require(allowed in source_package_dir.parents, f"source package outside allowed pilot root: {source_package_dir}")
    require(output_dir == allowed or allowed in output_dir.parents, f"output outside allowed pilot root: {output_dir}")
    require(source_package_dir != output_dir, "source and output package are identical")
    require(source_package_dir.is_dir(), f"source package missing: {source_package_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    require(not output_dir.exists(), f"output already exists: {output_dir}")
    require(not partial.exists(), f"partial output already exists: {partial}")

    source_manifest = verify_package_manifest(source_package_dir)
    sample_rows = read_csv(samples_path)
    sample_stats = validate_samples(sample_rows, check_source_assets=False)
    samples_sha = sha256_file(samples_path)
    require(samples_sha == EXPECTED_SAMPLES_SHA256, f"unexpected samples SHA: {samples_sha}")
    correction = load_json(correction_receipt_path)
    require(
        samples_sha == declared_output_sha(correction, samples_path.name),
        "sample SHA differs from NI correction receipt",
    )
    cards = read_jsonl(cards_path)
    require([row.get("phenomenon_code") for row in cards] == EXPECTED_CODES, "scope card order/codes")
    cards_by_code = {str(row["phenomenon_code"]): row for row in cards}

    source_html_path = source_package_dir / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
    source_document = source_html_path.read_text(encoding="utf-8")
    samples = extract_json_script(source_document, "samples-data")
    dialogues = extract_json_script(source_document, "dialogues-data")
    metadata = extract_json_script(source_document, "metadata-data")
    literature = extract_json_script(source_document, "literature-data")
    projections = extract_json_script(source_document, "textgrids-data")
    source_build_meta = extract_json_script(source_document, "build-data")
    require(source_build_meta.get("samples_sha256") == samples_sha, "source package sample SHA")
    require(len(samples) == 84, f"source embedded sample count: {len(samples)}")
    require(
        [row["sample_id"] for row in samples] == [row["sample_id"] for row in sample_rows],
        "source embedded sample order differs from frozen CSV",
    )
    require(list(literature) == EXPECTED_CODES, "source literature order/codes")
    require(
        all(literature[code]["label_ko"] == cards_by_code[code]["label_ko"] for code in EXPECTED_CODES),
        "source literature labels differ from scope cards",
    )

    source_receipt = load_json(source_package_dir / "BUILD_RECEIPT.json")
    require(source_receipt.get("passed") is True, "source build receipt not passed")
    reusable_directories = ["assets", "praat_work"]
    reusable_files = [
        "ASSET_MANIFEST.csv",
        "PRAAT_TASKS.csv",
        "DIALOGUE_SOURCE_RECEIPTS.json",
        "open_praat_sample.ps1",
    ]
    partial.mkdir(parents=True, exist_ok=False)
    try:
        for name in reusable_directories:
            source = source_package_dir / name
            require(source.is_dir(), f"reusable source directory missing: {name}")
            shutil.copytree(source, partial / name)
        for name in reusable_files:
            source = source_package_dir / name
            require(source.is_file(), f"reusable source file missing: {name}")
            shutil.copy2(source, partial / name)

        build_meta = {
            **source_build_meta,
            "schema_version": "stage2_two_hour_reviewer_build.v2",
            "reviewer_version": "v2",
            "build_mode": "c_only_repackage_from_verified_v1",
            "source_package_manifest_sha256": source_manifest["sha256"],
        }
        atomic_write_text(
            partial / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html",
            build_html(
                samples=samples,
                dialogues=dialogues,
                metadata=metadata,
                literature=literature,
                projections=projections,
                build_meta=build_meta,
            ),
        )
        atomic_write_text(partial / "START_HERE.html", build_start_html(literature))
        atomic_write_text(partial / "README.md", build_readme())

        receipt = {
            **source_receipt,
            "schema_version": "stage2_two_hour_reviewer_build_receipt.v2",
            "status": "researcher_ready_no_listening_started",
            "rebuild": {
                "reviewer_version": "v2",
                "build_mode": "c_only_repackage_from_verified_v1",
                "source_package_dir": str(source_package_dir),
                "source_package_manifest_sha256": source_manifest["sha256"],
                "source_package_manifest_records_verified": source_manifest["records"],
                "samples_path": str(samples_path),
                "samples_sha256": samples_sha,
                "scope_cards_path": str(cards_path),
                "scope_cards_sha256": sha256_file(cards_path),
                "source_assets_reused_without_transformation": True,
                "source_embedded_data_reused_semantically_unchanged": True,
                "user_ui_check_complete": False,
            },
            "safety": {
                **source_receipt.get("safety", {}),
                "source_package_modified": False,
                "c_drive_only_repackage": True,
                "prior_output_overwritten": False,
                "reviewer_listening_started": False,
            },
        }
        atomic_write_json(partial / "BUILD_RECEIPT.json", receipt)
        manifest_rows = []
        for path in sorted(item for item in partial.rglob("*") if item.is_file()):
            if path.name == "SHA256SUMS.txt":
                continue
            manifest_rows.append(f"{sha256_file(path)}  {path.relative_to(partial).as_posix()}")
        atomic_write_text(partial / "SHA256SUMS.txt", "\n".join(manifest_rows) + "\n")
        os.replace(partial, output_dir)
        return {
            **receipt,
            "output_dir": str(output_dir),
            "output_dir_bytes": sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file()),
            "sample_validation": {"sha256": samples_sha, **sample_stats},
            "sha_manifest": {
                "path": str(output_dir / "SHA256SUMS.txt"),
                "sha256": sha256_file(output_dir / "SHA256SUMS.txt"),
                "records": len(manifest_rows),
            },
        }
    except Exception:
        # Preserve the partial tree as failure evidence; never silently delete it.
        raise


def build(
    *, samples_path: Path, correction_receipt_path: Path, cards_path: Path, claims_path: Path,
    morph_root: Path, output_dir: Path
) -> dict[str, Any]:
    allowed = (PROJECT_ROOT / ALLOWED_OUTPUT_ROOT).resolve()
    output_dir = output_dir.resolve()
    require(output_dir == allowed or allowed in output_dir.parents, f"output outside allowed pilot root: {output_dir}")
    partial = output_dir.with_name(output_dir.name + ".partial")
    require(not output_dir.exists(), f"output already exists: {output_dir}")
    require(not partial.exists(), f"partial output already exists: {partial}")
    report = preflight(
        samples_path=samples_path,
        correction_receipt_path=correction_receipt_path,
        cards_path=cards_path,
        claims_path=claims_path,
    )
    samples = read_csv(samples_path)
    cards = read_jsonl(cards_path)
    claims = read_jsonl(claims_path)
    partial.mkdir(parents=True, exist_ok=False)
    try:
        unique_targets: dict[str, dict[str, str]] = {}
        for row in samples:
            unique_targets.setdefault(
                row["utt_id"],
                {
                    "pv_id": row["utt_id"],
                    "year": row["year"],
                    "utt_id": row["utt_id"],
                    "session_id": row["session_id"],
                },
            )
        dialogue_by_utt, metadata_by_utt, context_status, source_receipts = scan_dialogue_text(
            selected=list(unique_targets.values()), morph_root=morph_root, row_cap=ROW_CAP
        )
        require(len(dialogue_by_utt) == len(unique_targets), "zero-drop dialogue target count")
        compact_dialogues = {
            utt_id: [compact_dialogue_row(row) for row in dialogue_by_utt.get(utt_id, [])]
            for utt_id in unique_targets
        }
        compact_meta = {
            utt_id: compact_metadata(metadata_by_utt.get(utt_id, {})) for utt_id in unique_targets
        }
        assets, projections, sample_payload_by_id = materialize_assets(samples, partial)
        sample_payload = [sample_payload_by_id[row["sample_id"]] for row in samples]
        literature = literature_payload(cards, claims)
        build_meta = {
            "schema_version": "stage2_two_hour_reviewer_build.v1",
            "samples_sha256": report["samples"]["sha256"],
            "sample_count": len(sample_payload),
            "phenomenon_count": len(literature),
            "row_cap_per_year": ROW_CAP,
            "automatic_realization_judgement": False,
            "formal_ledger": False,
        }
        review_html = build_html(
            samples=sample_payload,
            dialogues=compact_dialogues,
            metadata=compact_meta,
            literature=literature,
            projections=projections,
            build_meta=build_meta,
        )
        review_path = partial / "STAGE2_TWO_HOUR_SEVEN_PHENOMENA_REVIEW.html"
        atomic_write_text(review_path, review_html)
        atomic_write_text(partial / "START_HERE.html", build_start_html(literature))
        atomic_write_text(partial / "open_praat_sample.ps1", OPEN_PRAAT_PS1, bom=True)
        atomic_write_csv(partial / "ASSET_MANIFEST.csv", ASSET_FIELDS, assets)
        praat_tasks = [
            {
                "sample_id": row["sample_id"],
                "phenomenon_code": row["phenomenon_code"],
                "year": row["year"],
                "utt_id": row["utt_id"],
                "target_word_labels_json": row["target_word_labels_json"],
                "bundle_wav_path": asset["bundle_wav_path"],
                "praat_work_textgrid_path": asset["praat_work_textgrid_path"],
                "source_textgrid_sha256": asset["source_textgrid_sha256"],
                "praat_work_initial_sha256": asset["praat_work_initial_sha256"],
                "researcher_need_edit": "",
                "researcher_edit_reason": "",
                "researcher_note": "",
            }
            for row, asset in zip(samples, assets, strict=True)
        ]
        atomic_write_csv(partial / "PRAAT_TASKS.csv", PRAAT_TASK_FIELDS, praat_tasks)
        atomic_write_json(partial / "DIALOGUE_SOURCE_RECEIPTS.json", {
            "schema_version": "stage2_two_hour_dialogue_source_receipts.v1",
            "row_cap_per_year": ROW_CAP,
            "context_status_by_utt_id": context_status,
            "receipts": source_receipts,
        })
        atomic_write_text(partial / "README.md", build_readme())
        receipt_path = partial / "BUILD_RECEIPT.json"
        receipt = {
            "schema_version": "stage2_two_hour_reviewer_build_receipt.v1",
            "passed": True,
            "status": "researcher_ready_no_listening_started",
            "inputs": report,
            "counts": {
                "samples": len(samples),
                "phenomena": len(EXPECTED_CODES),
                "samples_per_phenomenon": 12,
                "distinct_utterances": len(unique_targets),
                "dialogue_rows": sum(len(rows) for rows in compact_dialogues.values()),
                "asset_rows": len(assets),
                "praat_work_textgrids": len(praat_tasks),
                "literature_claim_rows_embedded": sum(len(value["claims"]) for value in literature.values()),
            },
            "dialogue_source_receipts": source_receipts,
            "asset_totals": {
                "wav_bytes": sum(int(row["source_wav_bytes"]) for row in assets),
                "textgrid_bytes": sum(int(row["source_textgrid_bytes"]) for row in assets),
                "all_copy_sha_equal": all(
                    row["source_wav_sha256"] == row["bundle_wav_sha256"]
                    and row["source_textgrid_sha256"] == row["bundle_source_textgrid_sha256"]
                    and row["source_textgrid_sha256"] == row["praat_work_initial_sha256"]
                    for row in assets
                ),
            },
            "safety": {
                "source_modified": False,
                "wav_cut_or_transformed": False,
                "textgrid_source_modified": False,
                "mfa_koina_wav2vec2_run": False,
                "automatic_realization_judgement": False,
                "formal_ledger_written": False,
                "reviewer_listening_started": False,
                "row_cap_per_year": ROW_CAP,
                "prior_output_overwritten": False,
            },
        }
        atomic_write_json(receipt_path, receipt)
        manifest_rows = []
        for path in sorted(item for item in partial.rglob("*") if item.is_file()):
            if path.name == "SHA256SUMS.txt":
                continue
            manifest_rows.append(f"{sha256_file(path)}  {path.relative_to(partial).as_posix()}")
        atomic_write_text(partial / "SHA256SUMS.txt", "\n".join(manifest_rows) + "\n")
        os.replace(partial, output_dir)
        return {
            **receipt,
            "output_dir": str(output_dir),
            "output_dir_bytes": sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file()),
            "sha_manifest": {
                "path": str(output_dir / "SHA256SUMS.txt"),
                "sha256": sha256_file(output_dir / "SHA256SUMS.txt"),
                "records": len(manifest_rows),
            },
        }
    except Exception:
        # Preserve the partial tree as failure evidence; never silently delete it.
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the seven-phenomena two-hour researcher reviewer")
    parser.add_argument("--samples", type=Path, default=PROJECT_ROOT / DEFAULT_SAMPLES)
    parser.add_argument("--correction-receipt", type=Path, default=PROJECT_ROOT / DEFAULT_CORRECTION_RECEIPT)
    parser.add_argument("--scope-cards", type=Path, default=PROJECT_ROOT / DEFAULT_SCOPE_CARDS)
    parser.add_argument("--claims", type=Path, default=PROJECT_ROOT / DEFAULT_CLAIMS)
    parser.add_argument(
        "--morph-root",
        type=Path,
        default=Path("D:/10_LAYERS/09_morph_search_v3_staging/morph_search_v3_20260801"),
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument(
        "--repackage-from",
        type=Path,
        help="Reuse a verified C:-drive reviewer package without reading raw/source corpus paths",
    )
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.preflight_only:
            result = preflight(
                samples_path=args.samples.resolve(),
                correction_receipt_path=args.correction_receipt.resolve(),
                cards_path=args.scope_cards.resolve(),
                claims_path=args.claims.resolve(),
            )
        elif args.repackage_from is not None:
            result = repackage_from_verified_package(
                source_package_dir=args.repackage_from.resolve(),
                samples_path=args.samples.resolve(),
                correction_receipt_path=args.correction_receipt.resolve(),
                cards_path=args.scope_cards.resolve(),
                output_dir=args.output_dir.resolve(),
            )
        else:
            result = build(
                samples_path=args.samples.resolve(),
                correction_receipt_path=args.correction_receipt.resolve(),
                cards_path=args.scope_cards.resolve(),
                claims_path=args.claims.resolve(),
                morph_root=args.morph_root.resolve(),
                output_dir=args.output_dir.resolve(),
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

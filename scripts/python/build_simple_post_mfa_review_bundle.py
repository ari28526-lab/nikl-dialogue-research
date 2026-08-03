"""Build a flat, numbered post-MFA researcher review bundle.

The builder reads the retained MFA database and frozen search-master CSVs in
read-only mode.  It does not retry alignment, approve exclusions, or modify a
production artifact.  Each review item gets the same numeric prefix so the
researcher can inspect WAV, LAB, CSV context, and (when present) the current
DB-derived six-tier TextGrid without hunting across directories.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from export_mfa_db_research_6tier import (
    _db_inventory,
    _session_intervals,
    load_session_rows,
    open_readonly,
)
from phoneme_roman import classify_phone, load_acoustic_meta, model_group_lookup
from pipeline_common import file_fingerprint, sha256_file
from research_textgrid_v2 import (
    BASE_TIERS,
    build_base_tier_data_from_intervals,
    write_textgrid_exact,
)


REVIEW_FIELDS = [
    "review_order",
    "sample_role",
    "utt_id",
    "expected_text",
    "current_mfa_status",
    "review_question",
    "wav_file",
    "lab_file",
    "search_csv_file",
    "context_file",
    "current_mfa_textgrid",
    "source_wav_duration_seconds",
    "review_wav_duration_seconds",
    "review_edge_padding_seconds",
    "review_time_to_source",
    "decision",
    "notes",
]

CONTEXT_FIELDS = [
    "utt_id",
    "year",
    "session_id",
    "speaker_id",
    "dialogue_id",
    "dialogue_speaker_ids",
    "co_speaker_ids",
    "form",
    "original_form",
    "form_roman",
    "tagged",
    "tagged_roman",
    "pron_pred_hangul",
    "pron_pred_roman",
    "pron_reference_form",
    "pron_reference_hangul",
    "pron_reference_roman",
    "pron_reference_source",
    "pron_reference_status",
    "start",
    "end",
    "dur",
    "note",
    "align_warn",
]


def _read_review_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "review_order",
            "sample_role",
            "year",
            "utt_id",
            "session_id",
            "normalized_text",
            "wav_path",
            "lab_path",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"review CSV 필수 열 누락: {sorted(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise RuntimeError("review CSV가 비어 있음")
    orders = [int(str(row["review_order"]).strip()) for row in rows]
    ids = [str(row["utt_id"]).strip() for row in rows]
    if len(orders) != len(set(orders)) or len(ids) != len(set(ids)):
        raise RuntimeError("review_order 또는 utt_id 중복")
    return sorted(rows, key=lambda row: int(str(row["review_order"])))


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_padded_wav(
    source: Path, destination: Path, edge_padding_seconds: float
) -> dict[str, float | int]:
    if edge_padding_seconds <= 0:
        raise ValueError("review edge padding은 0보다 커야 함")
    with wave.open(str(source), "rb") as input_wav:
        params = input_wav.getparams()
        if params.comptype != "NONE":
            raise ValueError(f"PCM WAV가 아님: {source}")
        frames = input_wav.readframes(params.nframes)
    padding_frames = max(1, round(edge_padding_seconds * params.framerate))
    frame_size = params.nchannels * params.sampwidth
    silence = b"\x00" * (padding_frames * frame_size)
    with wave.open(str(destination), "wb") as output_wav:
        output_wav.setparams(params)
        output_wav.writeframes(silence)
        output_wav.writeframes(frames)
        output_wav.writeframes(silence)
    actual_padding = padding_frames / params.framerate
    return {
        "padding_frames": padding_frames,
        "padding_seconds": actual_padding,
        "source_duration_seconds": params.nframes / params.framerate,
        "review_duration_seconds": (
            params.nframes + 2 * padding_frames
        ) / params.framerate,
    }


def _pad_tier_data(
    tier_data: Sequence[tuple[str, Sequence[tuple[float, float, str]]]],
    *,
    source_duration: float,
    edge_padding_seconds: float,
) -> tuple[float, list[tuple[str, list[tuple[float, float, str]]]]]:
    review_duration = source_duration + 2 * edge_padding_seconds
    padded: list[tuple[str, list[tuple[float, float, str]]]] = []
    for name, intervals in tier_data:
        shifted = [
            (
                float(begin) + edge_padding_seconds,
                float(end) + edge_padding_seconds,
                str(label),
            )
            for begin, end, label in intervals
        ]
        padded.append(
            (
                name,
                [(0.0, edge_padding_seconds, "")]
                + shifted
                + [
                    (
                        edge_padding_seconds + source_duration,
                        review_duration,
                        "",
                    )
                ],
            )
        )
    return review_duration, padded


def _db_rows(
    connection: sqlite3.Connection, utt_ids: Sequence[str]
) -> dict[str, dict[str, object]]:
    marks = ",".join("?" for _ in utt_ids)
    rows = connection.execute(
        """
        SELECT u.id, f.name, f.relative_path, sf.duration,
               u.normalized_text, u.alignment_score,
               EXISTS(SELECT 1 FROM word_interval wi WHERE wi.utterance_id=u.id),
               EXISTS(SELECT 1 FROM phone_interval pi WHERE pi.utterance_id=u.id)
        FROM utterance u
        JOIN file f ON f.id=u.file_id
        JOIN sound_file sf ON sf.file_id=f.id
        WHERE u.ignored=0 AND f.name IN ("""
        + marks
        + ")",
        list(utt_ids),
    ).fetchall()
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        result[str(row[1])] = {
            "utterance_id": int(row[0]),
            "utt_id": str(row[1]),
            "session_id": str(row[2] or str(row[1]).split(".", 1)[0]),
            "duration": float(row[3]),
            "normalized_text": str(row[4] or ""),
            "alignment_score": row[5],
            "word_present": bool(row[6]),
            "phone_present": bool(row[7]),
        }
    missing = set(utt_ids) - set(result)
    if missing:
        raise RuntimeError(f"MFA DB에 검토 utt_id 없음: {sorted(missing)}")
    return result


def _write_context(
    path: Path,
    *,
    review_row: Mapping[str, str],
    search_row: Mapping[str, str],
    db_row: Mapping[str, object],
    edge_padding_seconds: float,
) -> None:
    aligned = bool(db_row["word_present"] and db_row["phone_present"])
    lines = [
        f"검토 번호: {review_row['review_order']}",
        f"표본 역할: {review_row['sample_role']}",
        f"utt_id: {review_row['utt_id']}",
        f"현재 MFA 상태: {'정렬 있음' if aligned else '정렬 없음'}",
        f"DB normalized_text: {db_row['normalized_text']}",
        f"검토표 expected_text: {review_row['normalized_text']}",
        (
            "검토 시간축: 원 WAV/TextGrid 좌우에 "
            f"{edge_padding_seconds:.6f}초 무음을 함께 추가; "
            f"source_time=review_time-{edge_padding_seconds:.6f}"
        ),
        "",
        "[동결 search-master CSV의 해당 1행]",
    ]
    for field in CONTEXT_FIELDS:
        if field in search_row:
            lines.append(f"{field}: {search_row.get(field, '')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_bundle(
    *,
    review_csv: Path,
    db_path: Path,
    search_master_root: Path,
    acoustic_model: Path,
    output_root: Path,
    prefill_match_orders: set[int] | None = None,
    exclude_audio_unusable_orders: set[int] | None = None,
    edge_padding_seconds: float = 0.05,
    researcher_review_evidence: Path | None = None,
    post_mfa_candidates_csv: Path | None = None,
) -> dict[str, object]:
    review_csv = review_csv.resolve()
    db_path = db_path.resolve()
    search_master_root = search_master_root.resolve()
    acoustic_model = acoustic_model.resolve()
    output_root = output_root.resolve()
    prefill_match_orders = set(prefill_match_orders or ())
    exclude_audio_unusable_orders = set(exclude_audio_unusable_orders or ())
    if edge_padding_seconds <= 0:
        raise ValueError("edge_padding_seconds는 0보다 커야 함")
    for source in (review_csv, db_path, acoustic_model):
        if not source.is_file():
            raise FileNotFoundError(source)
    if not search_master_root.is_dir():
        raise FileNotFoundError(search_master_root)
    if output_root.exists():
        raise FileExistsError(f"output already exists: {output_root}")

    rows = _read_review_rows(review_csv)
    known_orders = {int(row["review_order"]) for row in rows}
    if (
        not prefill_match_orders <= known_orders
        or not exclude_audio_unusable_orders <= known_orders
    ):
        raise RuntimeError("prefill order가 review CSV 범위를 벗어남")
    if prefill_match_orders & exclude_audio_unusable_orders:
        raise RuntimeError("match와 audio-unusable exclusion order가 겹침")
    evidence_fingerprint = None
    if researcher_review_evidence is not None:
        researcher_review_evidence = researcher_review_evidence.resolve()
        if not researcher_review_evidence.is_file():
            raise FileNotFoundError(researcher_review_evidence)
        evidence_fingerprint = file_fingerprint(
            researcher_review_evidence, with_sha256=True
        )
    candidate_fields: list[str] = []
    candidate_rows: dict[str, dict[str, str]] = {}
    candidate_fingerprint = None
    if post_mfa_candidates_csv is not None:
        post_mfa_candidates_csv = post_mfa_candidates_csv.resolve()
        if not post_mfa_candidates_csv.is_file():
            raise FileNotFoundError(post_mfa_candidates_csv)
        with post_mfa_candidates_csv.open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            candidate_fields = list(reader.fieldnames or ())
            candidate_rows = {
                str(row.get("utt_id", "")).strip(): dict(row) for row in reader
            }
        candidate_fingerprint = file_fingerprint(
            post_mfa_candidates_csv, with_sha256=True
        )
    years = {str(row["year"]).strip() for row in rows}
    if len(years) != 1:
        raise RuntimeError(f"한 묶음에는 한 연도만 허용: {sorted(years)}")
    year = next(iter(years))

    db_before = file_fingerprint(db_path, with_sha256=False)
    staging = output_root.with_name(
        output_root.name + f".partial-{uuid.uuid4().hex}"
    )
    staging.mkdir(parents=True)
    connection = open_readonly(db_path)
    connection.execute("PRAGMA query_only=ON")
    try:
        ids = [str(row["utt_id"]).strip() for row in rows]
        db_rows = _db_rows(connection, ids)
        word_labels, phone_labels = _db_inventory(connection)
        utterance_ids = [int(db_rows[utt_id]["utterance_id"]) for utt_id in ids]
        words_by_utt, phones_by_utt = _session_intervals(
            connection, utterance_ids, word_labels, phone_labels
        )
        phone_groups = model_group_lookup(load_acoustic_meta(acoustic_model))

        search_cache: dict[tuple[str, str], dict[str, dict[str, str]]] = {}
        review_output: list[dict[str, object]] = []
        manifest_items: list[dict[str, object]] = []
        aligned_count = 0
        missing_count = 0

        for row in rows:
            order = int(row["review_order"])
            prefix = f"{order:02d}"
            utt_id = str(row["utt_id"]).strip()
            session = str(row["session_id"]).strip()
            db_row = db_rows[utt_id]
            key = (year, session)
            if key not in search_cache:
                search_cache[key] = load_session_rows(
                    search_master_root, year, session
                )
            search_row = search_cache[key].get(utt_id)
            if search_row is None:
                raise RuntimeError(f"search-master에 검토 utt_id 없음: {utt_id}")

            source_wav = Path(str(row["wav_path"])).resolve()
            source_lab = Path(str(row["lab_path"])).resolve()
            if not source_wav.is_file() or not source_lab.is_file():
                raise FileNotFoundError(f"WAV/LAB 누락: {utt_id}")
            stem = f"{prefix}__{utt_id}"
            wav_name = stem + ".wav"
            lab_name = stem + ".lab"
            csv_name = stem + "__SEARCH.csv"
            context_name = stem + "__CONTEXT.txt"
            padding = _write_padded_wav(
                source_wav, staging / wav_name, edge_padding_seconds
            )
            shutil.copy2(source_lab, staging / lab_name)
            _write_csv(staging / csv_name, list(search_row), [search_row])
            _write_context(
                staging / context_name,
                review_row=row,
                search_row=search_row,
                db_row=db_row,
                edge_padding_seconds=float(padding["padding_seconds"]),
            )

            uid = int(db_row["utterance_id"])
            aligned = bool(db_row["word_present"] and db_row["phone_present"])
            textgrid_name = ""
            if aligned:
                aligned_count += 1
                words = [
                    (float(begin), float(end), str(label))
                    for _iid, begin, end, label in words_by_utt.get(uid, [])
                ]
                phones = [
                    (float(begin), float(end), str(label))
                    for _iid, begin, end, label, _wid
                    in phones_by_utt.get(uid, [])
                ]
                tier_data, _fallback = build_base_tier_data_from_intervals(
                    duration=float(db_row["duration"]),
                    words=words,
                    phones=phones,
                    row=search_row,
                    phone_mapper=lambda phone: classify_phone(
                        phone, phone_groups
                    ).phone_class_r_auto,
                )
                if [name for name, _intervals in tier_data] != BASE_TIERS:
                    raise RuntimeError(f"6-tier 순서 오류: {utt_id}")
                textgrid_name = stem + "__CURRENT_MFA_6TIER.TextGrid"
                review_duration, padded_tier_data = _pad_tier_data(
                    tier_data,
                    source_duration=float(db_row["duration"]),
                    edge_padding_seconds=float(padding["padding_seconds"]),
                )
                if abs(
                    review_duration - float(padding["review_duration_seconds"])
                ) > 1e-6:
                    raise RuntimeError(f"WAV/DB duration 불일치: {utt_id}")
                write_textgrid_exact(
                    staging / textgrid_name,
                    duration=review_duration,
                    tier_data=padded_tier_data,
                )
                status = "aligned_control"
                question = "WAV·LAB·CSV가 같고 6-tier 정렬이 검토 가능한가?"
            else:
                missing_count += 1
                if db_row["word_present"] or db_row["phone_present"]:
                    detail = (
                        f"word_present={db_row['word_present']}, "
                        f"phone_present={db_row['phone_present']}"
                    )
                else:
                    detail = "word_present=False, phone_present=False"
                notice_name = stem + "__NO_CURRENT_TEXTGRID.txt"
                (staging / notice_name).write_text(
                    "현재 보존 MFA DB에 이 발화의 완전한 word+phone interval이 없어 "
                    "TextGrid를 만들 수 없습니다. 복사 누락이 아니라 이번 검토의 "
                    f"정렬 실패 상태입니다. ({detail})\n",
                    encoding="utf-8-sig",
                )
                status = "missing_word_or_phone_intervals"
                question = "WAV·LAB·CSV가 같은 발화인가? (TextGrid 없음은 현재 실패 상태)"

            if order in exclude_audio_unusable_orders:
                decision = "exclude_audio_unusable"
                notes = "연구자 청취: 소리 안 들림; 정렬·분석 제외"
            elif order in prefill_match_orders:
                decision = "match"
                notes = "사용자 청취 확인 완료"
            else:
                decision = "pending"
                notes = ""
            review_output.append(
                {
                    "review_order": order,
                    "sample_role": row["sample_role"],
                    "utt_id": utt_id,
                    "expected_text": row["normalized_text"],
                    "current_mfa_status": status,
                    "review_question": question,
                    "wav_file": wav_name,
                    "lab_file": lab_name,
                    "search_csv_file": csv_name,
                    "context_file": context_name,
                    "current_mfa_textgrid": textgrid_name,
                    "source_wav_duration_seconds": f"{float(padding['source_duration_seconds']):.6f}",
                    "review_wav_duration_seconds": f"{float(padding['review_duration_seconds']):.6f}",
                    "review_edge_padding_seconds": f"{float(padding['padding_seconds']):.6f}",
                    "review_time_to_source": (
                        "source_time=review_time-"
                        f"{float(padding['padding_seconds']):.6f}"
                    ),
                    "decision": decision,
                    "notes": notes,
                }
            )
            manifest_items.append(
                {
                    "review_order": order,
                    "utt_id": utt_id,
                    "status": status,
                    "source_wav_sha256": sha256_file(source_wav),
                    "review_wav_sha256": sha256_file(staging / wav_name),
                    "source_wav_duration_seconds": padding[
                        "source_duration_seconds"
                    ],
                    "review_wav_duration_seconds": padding[
                        "review_duration_seconds"
                    ],
                    "review_edge_padding_seconds": padding[
                        "padding_seconds"
                    ],
                    "source_lab_sha256": sha256_file(source_lab),
                    "copied_lab_sha256": sha256_file(staging / lab_name),
                    "textgrid": textgrid_name or None,
                }
            )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        connection.close()

    _write_csv(staging / "00_REVIEW.csv", REVIEW_FIELDS, review_output)
    approved_audio_unusable_rows: list[dict[str, str]] = []
    if exclude_audio_unusable_orders:
        if not candidate_rows or not candidate_fields:
            shutil.rmtree(staging, ignore_errors=True)
            raise RuntimeError(
                "audio-unusable exclusion 기록에는 post-MFA candidate CSV가 필요함"
            )
        for row in review_output:
            if int(row["review_order"]) not in exclude_audio_unusable_orders:
                continue
            utt_id = str(row["utt_id"])
            candidate = dict(candidate_rows.get(utt_id) or {})
            if not candidate:
                shutil.rmtree(staging, ignore_errors=True)
                raise RuntimeError(
                    f"post-MFA candidate에 audio-unusable ID 없음: {utt_id}"
                )
            candidate["reason_code"] = "audio_unusable"
            candidate["evidence_path"] = str(
                researcher_review_evidence or review_csv
            )
            candidate["decision"] = "approved"
            candidate["notes"] = (
                "2026-08-03 researcher listening review: audio not audible; "
                "exclude from alignment and analysis"
            )
            approved_audio_unusable_rows.append(candidate)
        _write_csv(
            staging / "01_RESEARCHER_APPROVED_AUDIO_UNUSABLE_EXCLUSIONS.csv",
            candidate_fields,
            approved_audio_unusable_rows,
        )
    (staging / "00_START_HERE.txt").write_text(
        "2020 MFA 단순 검토 묶음\n\n"
        "1. 00_REVIEW.csv에서 번호 하나를 고릅니다.\n"
        "2. 같은 번호 WAV를 재생합니다.\n"
        "3. 같은 번호 CONTEXT.txt 또는 SEARCH.csv에서 전사·형태소 정보를 봅니다.\n"
        "4. 13~16번은 같은 번호 TextGrid를 WAV와 함께 Praat에서 엽니다.\n"
        "5. 1~12번은 현재 정렬 실패 표본이므로 TextGrid가 없습니다. "
        "NO_CURRENT_TEXTGRID.txt가 그 상태를 설명합니다.\n"
        "6. 점검 WAV와 TextGrid에는 모든 tier의 양끝 경계를 보이도록 좌우 "
        "0.05초 무음을 함께 추가했습니다. 원시간은 review_time-0.05초입니다.\n"
        "7. 00_REVIEW.csv의 decision만 match 또는 needs_attention으로 적고, "
        "필요할 때만 notes를 씁니다.\n\n"
        "이 검토는 음운 실현 판정이 아니라 WAV·전사·CSV·정렬 산출물의 "
        "연결 상태를 확인하는 인프라 QC입니다.\n",
        encoding="utf-8-sig",
    )
    db_after = file_fingerprint(db_path, with_sha256=False)
    stable_keys = ("bytes", "mtime_ns")
    db_unchanged = all(db_before.get(key) == db_after.get(key) for key in stable_keys)
    if not db_unchanged:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("검토 묶음 생성 중 MFA DB fingerprint가 바뀜")
    manifest = {
        "schema_version": "simple_post_mfa_review_bundle.v2",
        "status": "success",
        "created_at": datetime.now().astimezone().isoformat(),
        "year": year,
        "review_count": len(rows),
        "missing_alignment_count": missing_count,
        "aligned_control_count": aligned_count,
        "prefilled_match_orders": sorted(prefill_match_orders),
        "excluded_audio_unusable_orders": sorted(
            exclude_audio_unusable_orders
        ),
        "review_edge_padding_seconds_requested": edge_padding_seconds,
        "researcher_review_evidence": evidence_fingerprint,
        "post_mfa_candidates_csv": candidate_fingerprint,
        "approved_audio_unusable_exclusion_count": len(
            approved_audio_unusable_rows
        ),
        "approved_audio_unusable_utt_ids": [
            row["utt_id"] for row in approved_audio_unusable_rows
        ],
        "database_open_mode": "read_only_query_only",
        "database_fingerprint_before": db_before,
        "database_fingerprint_after": db_after,
        "database_size_mtime_unchanged": db_unchanged,
        "review_csv": file_fingerprint(review_csv, with_sha256=True),
        "search_master_root": str(search_master_root),
        "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
        "items": manifest_items,
    }
    (staging / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, output_root)
    return manifest


def _parse_orders(value: str) -> set[int]:
    if not value.strip():
        return set()
    return {int(item.strip()) for item in value.split(",") if item.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--prefill-match-orders", default="")
    parser.add_argument("--exclude-audio-unusable-orders", default="")
    parser.add_argument("--edge-padding-seconds", type=float, default=0.05)
    parser.add_argument("--researcher-review-evidence", type=Path)
    parser.add_argument("--post-mfa-candidates-csv", type=Path)
    args = parser.parse_args()
    result = build_bundle(
        review_csv=args.review_csv,
        db_path=args.db,
        search_master_root=args.search_master_root,
        acoustic_model=args.acoustic_model,
        output_root=args.output_root,
        prefill_match_orders=_parse_orders(args.prefill_match_orders),
        exclude_audio_unusable_orders=_parse_orders(
            args.exclude_audio_unusable_orders
        ),
        edge_padding_seconds=args.edge_padding_seconds,
        researcher_review_evidence=args.researcher_review_evidence,
        post_mfa_candidates_csv=args.post_mfa_candidates_csv,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

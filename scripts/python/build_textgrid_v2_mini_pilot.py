"""확정된 연구용 6-tier와 연결 검토본의 최소 파일럿을 만든다.

기존 Dropbox 12발화 검토본을 읽기 전용 입력으로 사용한다. 새 출력 root만
허용하며, 원 WAV/CSV/TextGrid와 기존 4/5-tier 산출물은 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phoneme_roman import (  # noqa: E402
    ROMAN_SYSTEM_VERSION,
    SCHEMA_VERSION as PHONEME_SCHEMA_VERSION,
    classify_phone,
    load_acoustic_meta,
    model_group_lookup,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    git_commit,
    now_iso,
)
from research_textgrid_v2 import (  # noqa: E402
    BASE_TIERS,
    SCHEMA_VERSION,
    STITCHED_TIERS,
    write_base_textgrid,
    write_stitched_review,
)


PILOT_SCHEMA_VERSION = "research_textgrid_v2_mini_pilot.v1"
SINGLE = ("2020", "SDRW2000000510.1.1.98")
STITCHED = (
    ("2022", "SDRW2200001103.1.1.67"),
    ("2022", "SDRW2200001103.1.1.269"),
)


def read_one_csv(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError(f"발화 CSV 1행 계약 불일치: {path} rows={len(rows)}")
    return rows[0]


def write_csv(
    path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str] | None = None
) -> None:
    if not rows:
        raise ValueError(f"빈 CSV를 쓰지 않음: {path}")
    fieldnames = list(fields or rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with partial.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=fieldnames, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def source_paths(root: Path, year: str, utt_id: str) -> dict[str, Path]:
    prefix = f"{year}__{utt_id}"
    paths = {
        "wav": root / f"{prefix}.wav",
        "textgrid": root / f"{prefix}.TextGrid",
        "csv": root / f"{prefix}.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"파일럿 입력 누락: {missing}")
    return paths


def copy_new(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"기존 출력 보호: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build(
    *,
    project_root: Path,
    source_root: Path,
    acoustic_model: Path,
    output_root: Path,
) -> dict[str, object]:
    if output_root.exists():
        raise FileExistsError(f"새 output root만 허용: {output_root}")
    partial = output_root.with_name(
        f".{output_root.name}.{uuid.uuid4().hex}.partial"
    )
    partial.mkdir(parents=True)
    try:
        meta = load_acoustic_meta(acoustic_model)
        groups = model_group_lookup(meta)

        def phone_mapper(phone: str) -> str:
            # 철자·예측발음은 참조하지 않는다.
            return classify_phone(phone, groups).phone_class_r_auto

        single_year, single_id = SINGLE
        single_source = source_paths(source_root, single_year, single_id)
        single_row = read_one_csv(single_source["csv"])
        if single_row.get("utt_id") != single_id:
            raise ValueError("단일 발화 CSV utt_id 불일치")
        single_stem = f"01_SINGLE_{single_year}__{single_id}"
        single_wav = partial / f"{single_stem}.wav"
        single_tg = partial / f"{single_stem}__6tier.TextGrid"
        single_csv = partial / f"{single_stem}.csv"
        copy_new(single_source["wav"], single_wav)
        copy_new(single_source["csv"], single_csv)
        single_validation = write_base_textgrid(
            single_tg,
            source_textgrid=single_source["textgrid"],
            row=single_row,
            phone_mapper=phone_mapper,
        )

        stitch_sources: list[dict[str, object]] = []
        source_rows: list[dict[str, str]] = []
        input_files: list[Path] = list(single_source.values())
        for year, utt_id in STITCHED:
            paths = source_paths(source_root, year, utt_id)
            row = read_one_csv(paths["csv"])
            if row.get("utt_id") != utt_id:
                raise ValueError(f"연결 발화 CSV utt_id 불일치: {utt_id}")
            stitch_sources.append(
                {"wav": paths["wav"], "textgrid": paths["textgrid"], "row": row}
            )
            source_rows.append(row)
            input_files.extend(paths.values())
        if len({row["session_id"] for row in source_rows}) != 1:
            raise ValueError("연결 파일럿은 같은 session이어야 함")
        if len({row["speaker_id"] for row in source_rows}) != 1:
            raise ValueError("최소 연결 파일럿은 같은 speaker로 고정")
        if [int(row["utt_seq"]) for row in source_rows] != sorted(
            int(row["utt_seq"]) for row in source_rows
        ):
            raise ValueError("연결 source 순서가 utt_seq 오름차순이 아님")

        stitch_stem = "02_STITCHED_2022__SDRW2200001103_67_269__review"
        stitch_wav = partial / f"{stitch_stem}.wav"
        stitch_tg = partial / f"{stitch_stem}__8tier.TextGrid"
        stitch_manifest = partial / f"{stitch_stem}__manifest.csv"
        stitch_source_rows = partial / f"{stitch_stem}__source_rows.csv"
        stitch_validation = write_stitched_review(
            destination_wav=stitch_wav,
            destination_textgrid=stitch_tg,
            destination_manifest=stitch_manifest,
            sources=stitch_sources,
            phone_mapper=phone_mapper,
            gap_seconds=0.05,
            stitched_id=stitch_stem,
            alignment_contract_id="common_pron_mfa_r2_20260728",
            selection_query_id="mini_same_session_same_speaker_nonadjacent.v1",
        )
        source_fields = [
            "utt_id",
            "year",
            "session_id",
            "utt_seq",
            "speaker_id",
            "form",
            "form_roman",
            "tagged",
            "canonical_tagged",
        ]
        write_csv(stitch_source_rows, source_rows, source_fields)

        review_rows = [
            {
                "review_order": 1,
                "item_type": "SINGLE_6TIER",
                "utt_id_or_stitched_id": single_id,
                "wav": single_wav.name,
                "textgrid": single_tg.name,
                "expected_tiers": " | ".join(BASE_TIERS),
                "check_1": "utterance=혹시 요즘",
                "check_2": "utterance_orth_r는 어절을 | 로 구분",
                "check_3": "morph_analysis_utt는 혹시/MAG | 요즘/NNG",
                "check_4": "phoneme_r_auto는 phones_mfa와 같은 경계",
                "decision": "",
                "notes": "",
            },
            {
                "review_order": 2,
                "item_type": "STITCHED_REVIEW_8TIER",
                "utt_id_or_stitched_id": stitch_stem,
                "wav": stitch_wav.name,
                "textgrid": stitch_tg.name,
                "expected_tiers": " | ".join(STITCHED_TIERS),
                "check_1": "source_utt_id가 67→269 순서",
                "check_2": "두 발화 사이 0.05초 구간은 모든 tier에서 빈칸",
                "check_3": "speaker는 두 구간 모두 SD2201567",
                "check_4": "review 연결본이며 seam 횡단 KOINA 해석 금지",
                "decision": "",
                "notes": "",
            },
        ]
        review_path = partial / "REVIEW.csv"
        write_csv(review_path, review_rows)

        readme = partial / "README.md"
        readme.write_text(
            "# TextGrid 6-tier 최소 검토 파일럿\n\n"
            "이 폴더는 확정된 서울 코퍼스 참조 6-tier와 향후 KOINA용 "
            "연결 계약을 최소 파일로 확인하기 위한 사본이다. 원자료와 기존 "
            "4/5-tier는 수정하지 않았다.\n\n"
            "## 1. 단일 발화\n\n"
            f"- `{single_wav.name}`와 `{single_tg.name}`를 함께 연다.\n"
            "- tier 순서는 `words / phones_mfa / phoneme_r_auto / utterance / "
            "utterance_orth_r / morph_analysis_utt`이다.\n"
            "- `phoneme_r_auto`는 `phones_mfa`만 넓게 로마자화하며 철자나 "
            "예측발음으로 기저형을 복원하지 않는다.\n"
            "- 세 발화 수준 tier는 같은 시간경계를 사용한다. 형태소의 `+`는 "
            "문자열 경계이지 음향 시간경계가 아니다.\n\n"
            "## 2. 연결 검토본\n\n"
            f"- `{stitch_wav.name}`와 `{stitch_tg.name}`를 함께 연다.\n"
            "- 기본 6-tier에 연결본 전용 `source_utt_id`, `speaker`만 추가했다.\n"
            "- 같은 세션·같은 화자의 67번과 269번 발화를 순서대로 붙였지만 "
            "서로 인접한 발화는 아니다. 0.05초 무음도 인공적으로 넣었다.\n"
            "- 그러므로 이 파일은 맥락 표시·좌표 계약 검토용이다. seam을 "
            "자연 쉼 또는 AP/IP 경계로 해석하지 않는다.\n"
            f"- 원시간 역매핑은 `{stitch_manifest.name}`가 정본이다.\n\n"
            "## 기록 방법\n\n"
            "`REVIEW.csv`의 두 행에서 `decision`에 `승인` 또는 `수정 필요`, "
            "`notes`에 이유를 적는다. KOINA는 이번 파일럿에서 실행하지 않았고 "
            "빈 KOINA tier도 만들지 않았다.\n",
            encoding="utf-8",
        )

        output_paths = [
            single_wav,
            single_tg,
            single_csv,
            stitch_wav,
            stitch_tg,
            stitch_manifest,
            stitch_source_rows,
            review_path,
            readme,
        ]

        def final_fp(path: Path) -> dict[str, object]:
            result = file_fingerprint(path, with_sha256=True)
            result["path"] = str((output_root / path.relative_to(partial)).resolve())
            return result

        manifest = {
            "schema_version": PILOT_SCHEMA_VERSION,
            "status": "success_researcher_review_pending",
            "created_at": now_iso(),
            "purpose": "minimal acceptance pilot for approved 6-tier and stitched review contract",
            "approved_design": "docs/decisions/PROPOSAL_Seoul_corpus_inspired_TextGrid_tiers_20260801.md",
            "contracts": {
                "base_tiers": BASE_TIERS,
                "stitched_tiers": STITCHED_TIERS,
                "research_textgrid_schema": SCHEMA_VERSION,
                "phoneme_schema": PHONEME_SCHEMA_VERSION,
                "roman_system": ROMAN_SYSTEM_VERSION,
                "phones_mfa_unchanged": True,
                "words_unchanged": True,
                "phoneme_source": "phones_mfa_only",
                "morpheme_time_boundary_claimed": False,
                "koina_run": False,
                "koina_empty_tier_created": False,
                "stitch_mode": "review",
                "koina_cross_seam_allowed": False,
                "prior_four_five_tier_outputs_modified": False,
            },
            "inputs": {
                "source_root": str(source_root.resolve()),
                "acoustic_model": file_fingerprint(
                    acoustic_model, with_sha256=True
                ),
                "files": [
                    file_fingerprint(path, with_sha256=True)
                    for path in sorted(set(input_files))
                ],
            },
            "validation": {
                "single": single_validation,
                "stitched": stitch_validation,
            },
            "outputs": [final_fp(path) for path in output_paths],
            "runtime": {
                "git_commit": git_commit(project_root),
                "python": sys.executable,
            },
        }
        atomic_write_json(partial / "PILOT_MANIFEST.json", manifest)
        os.replace(partial, output_root)
        return manifest
    except BaseException:
        # 실패 원인 추적을 위해 partial은 보존한다.
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(
        project_root=args.project_root.resolve(),
        source_root=args.source_root.resolve(),
        acoustic_model=args.acoustic_model.resolve(),
        output_root=args.output_root.resolve(),
    )
    print(json.dumps(manifest["validation"], ensure_ascii=False, indent=2))
    print(args.output_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

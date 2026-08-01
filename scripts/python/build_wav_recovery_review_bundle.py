"""Build a small, read-only listening bundle for a WAV-ID recovery plan.

The bundle never edits source audio.  It copies, for each sampled target utterance,
the WAV proposed by the duration-sequence plan (A) and the currently same-named WAV
(B).  A JSON manifest and a plain-text guide retain provenance and copy hashes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import wave
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pipeline_common import atomic_text_writer, atomic_write_json, now_iso, sha256_file


SCHEMA_VERSION = "wav_recovery_review_bundle.v1"
REMAP_STATUS = "remap_high_confidence"


@dataclass(frozen=True)
class RemapGroup:
    session: str
    offset: int
    rows: tuple[dict[str, str], ...]

    @property
    def block_length(self) -> int:
        return int(self.rows[0]["block_length"])


def utterance_sequence(utt_id: str) -> int:
    match = re.search(r"(\d+)$", utt_id)
    if not match:
        raise ValueError(f"발화 ID 끝에서 순번을 읽을 수 없음: {utt_id}")
    return int(match.group(1))


def build_contiguous_groups(rows: list[dict[str, str]]) -> list[RemapGroup]:
    candidates = [row for row in rows if row.get("status") == REMAP_STATUS]
    groups: list[RemapGroup] = []
    current: list[dict[str, str]] = []
    current_key: tuple[str, int, int] | None = None
    previous_target: int | None = None
    previous_source: int | None = None

    for row in candidates:
        target_seq = utterance_sequence(row["target_utt_id"])
        source_seq = utterance_sequence(row["source_utt_id"])
        offset = source_seq - target_seq
        key = (row["session"], offset, int(row["block_length"]))
        is_continuation = (
            current
            and key == current_key
            and target_seq == previous_target + 1
            and source_seq == previous_source + 1
        )
        if not is_continuation and current:
            assert current_key is not None
            groups.append(
                RemapGroup(current_key[0], current_key[1], tuple(current))
            )
            current = []
        current.append(row)
        current_key = key
        previous_target = target_seq
        previous_source = source_seq

    if current:
        assert current_key is not None
        groups.append(RemapGroup(current_key[0], current_key[1], tuple(current)))
    return groups


def risk_band(block_length: int) -> str:
    if block_length <= 10:
        return "SHORT_3_10"
    if block_length <= 80:
        return "MEDIUM_11_80"
    return "LONG_81_PLUS"


def select_groups(groups: list[RemapGroup], per_band: int = 2) -> list[RemapGroup]:
    """Select deterministic, length-diverse groups while preferring new sessions."""
    by_band: dict[str, list[RemapGroup]] = defaultdict(list)
    for group in groups:
        by_band[risk_band(group.block_length)].append(group)

    selected: list[RemapGroup] = []
    used_sessions: set[str] = set()
    for band in ("SHORT_3_10", "MEDIUM_11_80", "LONG_81_PLUS"):
        candidates = sorted(
            by_band.get(band, []),
            key=lambda item: (item.block_length, item.session, item.rows[0]["target_utt_id"]),
        )
        if len(candidates) < per_band:
            raise RuntimeError(f"{band} 표본 후보 부족: {len(candidates)} < {per_band}")
        desired_indexes = [0, len(candidates) - 1] if per_band == 2 else [
            round(i * (len(candidates) - 1) / (per_band - 1))
            for i in range(per_band)
        ]
        band_selected: list[RemapGroup] = []
        for desired in desired_indexes:
            ordered = sorted(
                range(len(candidates)),
                key=lambda index: (
                    candidates[index].session in used_sessions,
                    abs(index - desired),
                    candidates[index].session,
                ),
            )
            choice = next(
                candidates[index]
                for index in ordered
                if candidates[index] not in band_selected
            )
            band_selected.append(choice)
            used_sessions.add(choice.session)
        selected.extend(band_selected)
    return selected


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def copy_verified(source: Path, destination: Path) -> dict[str, object]:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copy2(source, destination)
    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)
    if source_hash != destination_hash:
        raise RuntimeError(f"복사 해시 불일치: {source} -> {destination}")
    return {
        "source_path": str(source.resolve()),
        "bundle_path": str(destination.resolve()),
        "bytes": destination.stat().st_size,
        "sha256": destination_hash,
        "duration_seconds": round(wav_seconds(destination), 6),
    }


def write_guide(path: Path, review_rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2020 WAV ID 복구 최소 청취 검토",
        "",
        "목적: 길이 연속열이 제안한 고신뢰 재매핑이 실제 음성과 전사에서도 맞는지 확인합니다.",
        "원본 WAV는 수정하지 않았고, 이 폴더에는 해시 검증한 복사본만 있습니다.",
        "",
        "각 번호에서 다음 순서로 확인합니다.",
        "",
        "1. 아래의 `확인할 전사`를 읽습니다.",
        "2. `A_PROPOSED`를 듣습니다. 이 음성이 확인할 전사와 맞는지 판단합니다.",
        "3. 필요할 때만 `B_CURRENT`를 들어 현재 같은 ID의 음성과 비교합니다.",
        "4. 대화창에 `번호 / A 맞음`, `번호 / 불확실`, 또는 `번호 / A 틀림`으로 알려주세요.",
        "",
        "A가 맞는다는 것은 재매핑 규칙을 지지할 뿐이며, 곧바로 원본을 덮어쓴다는 뜻은 아닙니다.",
        "",
        "## 검토 순서",
        "",
    ]
    for row in review_rows:
        lines.extend(
            [
                f"### {row['review_order']:02d}. {row['risk_band']} / {row['position_in_block']}",
                "",
                f"- 확인할 전사: {row['target_form']}",
                f"- 원문 전사: {row['target_original_form']}",
                f"- 대상 ID: {row['target_utt_id']}",
                f"- 제안: `{row['proposed_audio_file']}`",
                f"- 현재: `{row['current_audio_file']}`",
                f"- 근거: 연속 일치 {row['block_length']}개, ID 오프셋 {row['id_offset']:+d}",
                "",
            ]
        )
    with atomic_text_writer(path, encoding="utf-8", newline="\n") as (stream, _):
        stream.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-csv", type=Path, required=True)
    parser.add_argument("--search-master-root", type=Path, required=True)
    parser.add_argument("--wav-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"출력 폴더가 비어 있지 않음: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = output_dir / "audio"

    plan_rows = read_csv(args.plan_csv.resolve())
    groups = build_contiguous_groups(plan_rows)
    groups = [
        group
        for group in groups
        if all(
            (
                args.wav_root
                / "2020"
                / group.session
                / f"{endpoint['target_utt_id']}.wav"
            ).is_file()
            for endpoint in (group.rows[0], group.rows[-1])
        )
    ]
    selected_groups = select_groups(groups, per_band=2)
    source_to_target = {
        (row["session"], row["source_utt_id"]): row["target_utt_id"]
        for row in plan_rows
        if row.get("source_utt_id") and row.get("target_utt_id")
    }
    session_rows: dict[str, dict[str, dict[str, str]]] = {}
    review_rows: list[dict[str, object]] = []
    file_records: list[dict[str, object]] = []

    for group in selected_groups:
        if group.session not in session_rows:
            search_csv = args.search_master_root / "2020" / f"{group.session}.csv"
            rows = read_csv(search_csv)
            session_rows[group.session] = {row["utt_id"]: row for row in rows}
        row_by_id = session_rows[group.session]
        endpoints = (("START", group.rows[0]), ("END", group.rows[-1]))
        for position, plan_row in endpoints:
            target_id = plan_row["target_utt_id"]
            source_id = plan_row["source_utt_id"]
            target = row_by_id.get(target_id)
            if target is None:
                raise RuntimeError(f"search master 대상 발화 누락: {target_id}")
            current_path = (
                args.wav_root / "2020" / group.session / f"{target_id}.wav"
            ).resolve()
            proposed_path = Path(plan_row["source_wav"]).resolve()
            if not current_path.is_file():
                raise RuntimeError(f"현재 같은 ID WAV 누락: {current_path}")

            order = len(review_rows) + 1
            proposed_name = (
                f"{order:02d}_A_PROPOSED_{target_id}__FROM_{source_id}.wav"
            )
            current_name = f"{order:02d}_B_CURRENT_{target_id}.wav"
            proposed_copy = copy_verified(proposed_path, audio_dir / proposed_name)
            current_copy = copy_verified(current_path, audio_dir / current_name)
            proposed_copy.update({"review_order": order, "role": "A_PROPOSED"})
            current_copy.update({"review_order": order, "role": "B_CURRENT"})
            file_records.extend((proposed_copy, current_copy))

            predicted_current_target = source_to_target.get(
                (group.session, target_id), ""
            )
            predicted_current_row = row_by_id.get(predicted_current_target, {})
            review_rows.append(
                {
                    "review_order": order,
                    "risk_band": risk_band(group.block_length),
                    "position_in_block": position,
                    "session": group.session,
                    "target_utt_id": target_id,
                    "target_form": target.get("form", ""),
                    "target_original_form": target.get("original_form", ""),
                    "target_tagged": target.get("tagged", ""),
                    "source_utt_id": source_id,
                    "id_offset": group.offset,
                    "block_length": group.block_length,
                    "target_duration_seconds": float(
                        plan_row["target_duration_seconds"]
                    ),
                    "proposed_duration_seconds": float(
                        plan_row["source_duration_seconds"]
                    ),
                    "duration_residual_seconds": float(
                        plan_row["duration_residual_seconds"]
                    ),
                    "proposed_audio_file": f"audio/{proposed_name}",
                    "current_audio_file": f"audio/{current_name}",
                    "current_audio_predicted_target_utt_id": predicted_current_target,
                    "current_audio_predicted_form": predicted_current_row.get("form", ""),
                    "decision": "pending",
                    "notes": "",
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "purpose": "human audit of high-confidence 2020 WAV-ID remap before recovery",
        "source_files_untouched": True,
        "plan_csv": str(args.plan_csv.resolve()),
        "plan_csv_sha256": sha256_file(args.plan_csv.resolve()),
        "selection_contract": {
            "bands": ["SHORT_3_10", "MEDIUM_11_80", "LONG_81_PLUS"],
            "groups_per_band": 2,
            "positions_per_group": ["START", "END"],
            "review_rows": len(review_rows),
        },
        "review_rows": review_rows,
        "copied_files": file_records,
    }
    atomic_write_json(output_dir / "REVIEW_MANIFEST.json", manifest)
    write_guide(output_dir / "00_READ_ME_FIRST.md", review_rows)
    print(f"[OK] review rows={len(review_rows)} audio_files={len(file_records)}")
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

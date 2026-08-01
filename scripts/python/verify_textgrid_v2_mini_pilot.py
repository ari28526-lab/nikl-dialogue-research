"""TextGrid v2 최소 파일럿의 실물·SHA·좌표 계약을 독립 재검증한다."""

from __future__ import annotations

import argparse
import csv
import json
import wave
from pathlib import Path

from pipeline_common import atomic_write_json, file_fingerprint, now_iso, sha256_file
from research_textgrid_v2 import BASE_TIERS, STITCHED_TIERS
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def continuous(rows, duration: float, tolerance: float = 1e-6) -> bool:
    if not rows or abs(float(rows[0][0])) > tolerance:
        return False
    cursor = 0.0
    for begin, end, _label in rows:
        if abs(float(begin) - cursor) > tolerance or float(end) < float(begin):
            return False
        cursor = float(end)
    return abs(cursor - duration) <= max(tolerance, 1e-5)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def verify(root: Path) -> dict[str, object]:
    manifest_path = root / "PILOT_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success_researcher_review_pending":
        raise RuntimeError(f"manifest status 오류: {manifest.get('status')}")
    if not manifest.get("contracts", {}).get("prior_four_five_tier_outputs_modified") is False:
        raise RuntimeError("기존 4/5-tier 불변 계약 누락")

    checked_outputs = 0
    for item in manifest["outputs"]:
        path = Path(item["path"])
        if not path.is_file():
            raise FileNotFoundError(f"출력 누락: {path}")
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"출력 SHA/bytes 불일치: {path}")
        checked_outputs += 1
    checked_inputs = 0
    for item in manifest["inputs"]["files"]:
        path = Path(item["path"])
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"입력 변경/누락: {path}")
        checked_inputs += 1

    single_tg = next(root.glob("01_SINGLE*__6tier.TextGrid"))
    single_wav = next(root.glob("01_SINGLE*.wav"))
    single_duration, single_tiers = parse_mfa_textgrid(single_tg)
    if single_duration is None or abs(single_duration - wav_duration(single_wav)) > 0.001:
        raise RuntimeError("단일 WAV/TextGrid duration 불일치")
    if list(single_tiers) != BASE_TIERS:
        raise RuntimeError(f"단일 tier 계약 불일치: {list(single_tiers)}")
    for name in BASE_TIERS:
        if not continuous(single_tiers[name], single_duration):
            raise RuntimeError(f"단일 0-xmax 비연속: {name}")
    phone_rows = single_tiers["phones_mfa"]
    phoneme_rows = single_tiers["phoneme_r_auto"]
    phone_edges = [(begin, end) for begin, end, _ in phone_rows]
    phoneme_edges = [(begin, end) for begin, end, _ in phoneme_rows]
    if phone_edges != phoneme_edges:
        raise RuntimeError("단일 phone/phoneme 경계 불일치")
    if any(label.startswith("?") for _, _, label in phoneme_rows if label):
        raise RuntimeError("구형 lexical review marker가 phoneme tier에 잔존")
    speech_edges = [
        [(begin, end) for begin, end, _ in single_tiers[name]]
        for name in ("utterance", "utterance_orth_r", "morph_analysis_utt")
    ]
    if not all(edges == speech_edges[0] for edges in speech_edges[1:]):
        raise RuntimeError("단일 발화 수준 tier 경계 불일치")

    stitched_tg = next(root.glob("02_STITCHED*__8tier.TextGrid"))
    stitched_wav = next(root.glob("02_STITCHED*.wav"))
    stitched_manifest_path = next(root.glob("02_STITCHED*__manifest.csv"))
    stitched_duration, stitched_tiers = parse_mfa_textgrid(stitched_tg)
    if stitched_duration is None or abs(stitched_duration - wav_duration(stitched_wav)) > 0.001:
        raise RuntimeError("연결 WAV/TextGrid duration 불일치")
    if list(stitched_tiers) != STITCHED_TIERS:
        raise RuntimeError(f"연결 tier 계약 불일치: {list(stitched_tiers)}")
    for name in STITCHED_TIERS:
        if not continuous(stitched_tiers[name], stitched_duration):
            raise RuntimeError(f"연결 0-xmax 비연속: {name}")
    rows = read_csv(stitched_manifest_path)
    ids = [label for _, _, label in stitched_tiers["source_utt_id"] if label]
    if ids != [row["utt_id"] for row in rows]:
        raise RuntimeError("연결 source_utt_id/manifest 순서 불일치")
    if any(row["stitch_mode"] != "review" for row in rows):
        raise RuntimeError("연결 mode가 review가 아님")
    if any(row["koina_cross_seam_allowed"] != "False" for row in rows):
        raise RuntimeError("연결 seam KOINA 차단값 오류")
    for row in rows:
        start = float(row["stitched_start_seconds"])
        source_end = float(row["source_end_seconds"])
        stitched_end = float(row["stitched_end_seconds"])
        if abs(start + source_end - stitched_end) > 1e-6:
            raise RuntimeError(f"원시간 역매핑 불일치: {row['utt_id']}")

    partials = [str(path) for path in root.rglob("*.partial")]
    if partials:
        raise RuntimeError(f"성공 root에 partial 잔존: {partials}")
    return {
        "schema_version": "research_textgrid_v2_mini_verification.v1",
        "status": "success",
        "verified_at": now_iso(),
        "pilot_manifest": file_fingerprint(manifest_path, with_sha256=True),
        "counts": {
            "checked_input_files": checked_inputs,
            "checked_output_files": checked_outputs,
            "single_textgrids": 1,
            "stitched_textgrids": 1,
            "stitched_source_utterances": len(rows),
        },
        "contracts": {
            "single_base_tiers": BASE_TIERS,
            "stitched_tiers": STITCHED_TIERS,
            "all_tiers_continuous_0_xmax": True,
            "phone_phoneme_edges_equal": True,
            "speech_tier_edges_equal": True,
            "output_sha_match": True,
            "input_sha_unchanged": True,
            "source_time_inverse_mapping_valid": True,
            "koina_run": False,
            "koina_cross_seam_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = verify(root)
    destination = root / "PILOT_VERIFICATION.json"
    if destination.exists():
        raise FileExistsError(f"기존 verification 덮어쓰기 금지: {destination}")
    atomic_write_json(destination, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

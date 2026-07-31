"""완성된 로마자 음소 보조층 파일럿의 최종 경로·SHA·tier를 재검증한다."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, file_fingerprint, now_iso  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


FOUR_TIERS = ["words", "phones_mfa", "utterance", "utterance_search"]
FIVE_TIERS = FOUR_TIERS + ["phoneme_r_auto"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def same_intervals(left, right) -> bool:
    return len(left) == len(right) and all(
        abs(a[0] - b[0]) <= 1e-6
        and abs(a[1] - b[1]) <= 1e-6
        and a[2] == b[2]
        for a, b in zip(left, right)
    )


def verify(output_root: Path, review_root: Path) -> dict[str, object]:
    prior_path = output_root / "PILOT_MANIFEST.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    if prior.get("status") != "success_researcher_review_pending":
        raise RuntimeError(f"prior manifest status 오류: {prior.get('status')}")
    expected = {
        "PHONE_ROMAN_INVENTORY.csv": 109,
        "PHONE_ROMAN_INTERVALS.csv": None,
        "PHONEME_ROMAN_CORRESPONDENCE.csv": 1683,
        "UTTERANCE_PHONEME_ROMAN_SUMMARY.csv": 60,
    }
    files: list[dict[str, object]] = []
    rows: dict[str, int] = {}
    for name, expected_rows in expected.items():
        path = output_root / name
        table = read_csv(path)
        if expected_rows is not None and len(table) != expected_rows:
            raise RuntimeError(
                f"{name} 행수 불일치: expected={expected_rows} actual={len(table)}"
            )
        rows[name] = len(table)
        files.append(file_fingerprint(path, with_sha256=True))
    inventory = read_csv(output_root / "PHONE_ROMAN_INVENTORY.csv")
    if len({row["phone_mfa"] for row in inventory}) != 109:
        raise RuntimeError("phone inventory 중복")
    intervals = read_csv(output_root / "PHONE_ROMAN_INTERVALS.csv")
    if any(row["phone_mfa"].strip().lower() == "spn" for row in intervals):
        raise RuntimeError("실제 interval spn 발견")
    summaries = read_csv(output_root / "UTTERANCE_PHONEME_ROMAN_SUMMARY.csv")
    if len({row["utt_id"] for row in summaries}) != 60:
        raise RuntimeError("summary utt_id 중복")

    textgrids = sorted((output_root / "textgrid_5tier_optional").rglob("*.TextGrid"))
    if len(textgrids) != 60:
        raise RuntimeError(f"5-tier 수 불일치: {len(textgrids)}")
    summary_by_utt = {row["utt_id"]: row for row in summaries}
    for path in textgrids:
        utt_id = path.stem
        row = summary_by_utt[utt_id]
        source = Path(row["source_textgrid"])
        duration, tiers = parse_mfa_textgrid(path)
        source_duration, source_tiers = parse_mfa_textgrid(source)
        if duration is None or source_duration is None:
            raise RuntimeError(f"TextGrid duration 없음: {path}")
        if abs(duration - source_duration) > 1e-6:
            raise RuntimeError(f"TextGrid duration 변경: {path}")
        if list(tiers) != FIVE_TIERS or list(source_tiers) != FOUR_TIERS:
            raise RuntimeError(f"TextGrid tier 계약 불일치: {path}")
        for tier_name in FOUR_TIERS:
            if not same_intervals(tiers[tier_name], source_tiers[tier_name]):
                raise RuntimeError(f"기존 tier 변경: {path} {tier_name}")
        phone_edges = [(b, e) for b, e, _ in tiers["phones_mfa"]]
        phoneme_edges = [(b, e) for b, e, _ in tiers["phoneme_r_auto"]]
        if phone_edges != phoneme_edges:
            raise RuntimeError(f"phone/phoneme 경계 불일치: {path}")

    d_workbook = output_root / "review_delivery" / "PHONEME_ROMAN_PILOT.xlsx"
    dropbox_workbook = review_root / "PHONEME_ROMAN_PILOT.xlsx"
    d_fp = file_fingerprint(d_workbook, with_sha256=True)
    dropbox_fp = file_fingerprint(dropbox_workbook, with_sha256=True)
    if d_fp["sha256"] != dropbox_fp["sha256"]:
        raise RuntimeError("D/Dropbox workbook SHA 불일치")
    delivered_tg = sorted(review_root.glob("*__phoneme_r_auto.TextGrid"))
    if len(delivered_tg) != 12:
        raise RuntimeError(f"Dropbox 5-tier 수 불일치: {len(delivered_tg)}")

    stale_paths = [
        item["path"]
        for item in prior.get("outputs", [])
        if ".partial" in str(item.get("path", ""))
    ]
    report = {
        "schema_version": "phoneme_roman_pilot_verification.v2",
        "status": "success",
        "recorded_at": now_iso(),
        "reason": "normalize post-rename manifest paths and independently recheck outputs",
        "prior_manifest": file_fingerprint(prior_path, with_sha256=True),
        "prior_stale_partial_paths_detected": len(stale_paths),
        "prior_stale_paths": stale_paths,
        "counts": {
            "csv_rows": rows,
            "five_tier_textgrids": len(textgrids),
            "dropbox_review_textgrids": len(delivered_tg),
            "source_four_tiers_unchanged": len(textgrids),
            "phone_phoneme_boundaries_equal": len(textgrids),
        },
        "outputs": files,
        "workbooks": {
            "d": d_fp,
            "dropbox": dropbox_fp,
            "sha_equal": True,
        },
        "contracts": {
            "phones_mfa_unchanged": True,
            "default_four_tier_unchanged": True,
            "realization_judgment_performed": False,
            "canonical_paths_are_final_not_partial": True,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--review-root", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.output_root.resolve(), args.review_root.resolve())
    destination = args.output_root.resolve() / "PILOT_VERIFICATION_V2.json"
    if destination.exists():
        raise FileExistsError(f"기존 verification 덮어쓰기 금지: {destination}")
    atomic_write_json(destination, report)
    print(json.dumps(report["counts"], ensure_ascii=False, indent=2))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

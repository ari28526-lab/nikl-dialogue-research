"""Stage one flat, read-mostly production MFA review bundle.

The authoritative review CSV remains in the project.  This script copies that
CSV byte-for-byte together with numbered WAV/LAB/TextGrid payloads so a
researcher can review them from Dropbox without navigating the production tree.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from mfa_production_year_review import FIELDS, IDENTITY_FIELDS
from pipeline_common import file_fingerprint, now_iso, sha256_file

SCHEMA_VERSION = "mfa_production_year_review_bundle.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def read_review(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise RuntimeError(
                f"review columns differ: actual={reader.fieldnames}, expected={FIELDS}"
            )
        return [dict(row) for row in reader]


def copy_verified(source: Path, destination: Path) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(source)
    shutil.copy2(source, destination)
    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)
    if source_hash != destination_hash:
        raise RuntimeError(f"review bundle copy SHA mismatch: {destination}")
    return {
        "source": str(source.resolve()),
        "relative_path": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": destination_hash,
    }


def promote_with_retry(staging: Path, output_root: Path) -> None:
    deadline = time.monotonic() + 60.0
    delay = 0.1
    while True:
        try:
            os.replace(staging, output_root)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 1.0)


def stage_bundle(
    *, review_csv: Path, review_manifest: Path, output_root: Path
) -> dict[str, Any]:
    review_csv = review_csv.resolve()
    review_manifest = review_manifest.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"review bundle output already exists: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = output_root.parent / f".{output_root.name}.partial.{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"review bundle staging already exists: {staging}")

    manifest = read_json(review_manifest)
    rows = read_review(review_csv)
    if (
        manifest.get("schema_version")
        != "mfa_production_year_review_manifest.v1"
        or manifest.get("status") != "pending_researcher_review"
        or manifest.get("automatic_approval_performed") is not False
    ):
        raise RuntimeError("review manifest is not a pending production review")
    expected = manifest.get("row_identities") or []
    actual = [{key: row[key] for key in IDENTITY_FIELDS} for row in rows]
    if actual != expected:
        raise RuntimeError("review CSV identity/path fields differ from manifest")
    if len(rows) < 5 or len({row["session"] for row in rows}) < 5:
        raise RuntimeError("production review bundle requires at least five sessions")

    staging.mkdir()
    copied: list[dict[str, Any]] = []
    try:
        copied.append(copy_verified(review_csv, staging / review_csv.name))
        copied.append(
            copy_verified(review_manifest, staging / review_manifest.name)
        )
        for row in rows:
            order = int(row["review_order"])
            utt_id = row["utt_id"]
            prefix = f"{order:02d}_{utt_id}"
            sources = (
                (Path(row["wav_path"]), f"{prefix}.wav"),
                (Path(row["lab_path"]), f"{prefix}.lab"),
                (Path(row["textgrid_path"]), f"{prefix}.TextGrid"),
            )
            for source, name in sources:
                copied.append(copy_verified(source, staging / name))

        year = str(manifest["year"])
        readme = staging / "00_README.md"
        readme.write_text(
            f"# {year} MFA 최종 인프라 표본 검토\n\n"
            "이 폴더는 실제 음운 실현 여부를 판정하는 단계가 아니라, "
            "전수 산출물의 연결과 사용 가능성을 확인하는 최종 Gate입니다.\n\n"
            "각 번호에서 다음만 확인합니다.\n\n"
            "1. WAV가 재생되고 LAB과 같은 발화인지\n"
            "2. 같은 번호의 TextGrid가 열리고 6개 tier가 보이는지\n"
            "3. words/phones_mfa/phoneme_r_auto/utterance/utterance_orth_r/"
            "morph_analysis가 대체로 맞고 연구 검색에 사용할 수 있는지\n"
            "4. 좌우 빈 구간과 tier 경계가 파일 시간 범위 안에서 정상인지\n\n"
            "문제가 없으면 03_RESEARCHER_REVIEW.csv의 decision을 approved로, "
            "문제가 있으면 needs_attention으로 적고 notes에 이유를 남깁니다. "
            "파일 이름과 식별자·경로 열은 바꾸지 않습니다.\n",
            encoding="utf-8-sig",
        )
        copied.append(
            {
                "source": "generated",
                "relative_path": readme.name,
                "bytes": readme.stat().st_size,
                "sha256": sha256_file(readme),
            }
        )
        bundle: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "success",
            "created_at": now_iso(),
            "year": str(manifest["year"]),
            "input_contract_id": str(manifest["input_contract_id"]),
            "alignment_contract_id": str(manifest["alignment_contract_id"]),
            "authoritative_review_csv": file_fingerprint(
                review_csv, with_sha256=True
            ),
            "authoritative_review_manifest": file_fingerprint(
                review_manifest, with_sha256=True
            ),
            "counts": {
                "review_rows": len(rows),
                "sessions": len({row["session"] for row in rows}),
                "speakers_nonempty": len(
                    {row["speaker_id"] for row in rows if row["speaker_id"]}
                ),
                "payload_files": len(rows) * 3,
            },
            "automatic_approval_performed": False,
            "realization_judgment_requested": False,
            "files": sorted(copied, key=lambda item: item["relative_path"]),
        }
        manifest_path = staging / "BUNDLE_MANIFEST.json"
        manifest_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        promote_with_retry(staging, output_root)
        return bundle
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = stage_bundle(
            review_csv=args.review_csv,
            review_manifest=args.review_manifest,
            output_root=args.output_root,
        )
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "year": result["year"],
                "counts": result["counts"],
                "output_root": str(args.output_root.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

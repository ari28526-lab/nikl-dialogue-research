"""r3 inventory에서 검증된 동일 표면형 phone donor 후보를 찾는다.

donor phone은 최종 선택이 아니다. 규칙 목표 Roman과 정확히 일치하는 기존
provisional 변이만 별도 candidate 열에 기록하며 selected 열은 바꾸지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common_pron_rule_consistency import roman_units  # noqa: E402
from build_common_pron_r3_canonical_inventory import (  # noqa: E402
    OUTPUT_FIELDS as INVENTORY_FIELDS,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_surface_donor_candidates.v1"
CANDIDATE_FIELDS = (
    "candidate_variant_count",
    "candidate_pron_phones_json",
    "candidate_pron_roman_json",
    "candidate_status",
    "candidate_source",
    "candidate_reason",
)
OUTPUT_FIELDS = (
    *INVENTORY_FIELDS[: INVENTORY_FIELDS.index("selected_variant_count")],
    *CANDIDATE_FIELDS,
    *INVENTORY_FIELDS[INVENTORY_FIELDS.index("selected_variant_count") :],
)


def clean(value: object) -> str:
    return str(value or "").strip()


def json_list(value: object, label: str, token: str) -> list[str]:
    try:
        result = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{token} {label} JSON 오류") from exc
    if not isinstance(result, list) or any(not isinstance(item, str) for item in result):
        raise RuntimeError(f"{token} {label}는 문자열 JSON 배열이어야 함")
    return result


@contextmanager
def atomic_gzip_writer(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with gzip.open(
            temp, "xt", encoding="utf-8-sig", newline="", compresslevel=6
        ) as stream:
            yield stream
        os.replace(temp, path)
    except BaseException:
        raise


def matching_donor_variants(
    *, target_roman: str, donor_phones: list[str], donor_romans: list[str]
) -> tuple[list[str], list[str]]:
    if len(donor_phones) != len(donor_romans):
        raise RuntimeError("donor phone/roman variant 수 불일치")
    _, target_keys = roman_units(target_roman)
    phones: list[str] = []
    romans: list[str] = []
    for phone, roman in zip(donor_phones, donor_romans, strict=True):
        _, keys = roman_units(roman)
        if keys and target_keys and keys == target_keys:
            phones.append(phone)
            romans.append(roman)
    return phones, romans


def verify_manifest(input_path: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != "common_pron_r3_canonical_inventory.v1":
        raise RuntimeError("r3 canonical inventory manifest schema 불일치")
    if manifest.get("status") != "success_incomplete_selection":
        raise RuntimeError("r3 canonical inventory 상태 오류")
    expected = clean(manifest["outputs"]["canonical_inventory"].get("sha256"))
    if not expected or sha256_file(input_path).lower() != expected.lower():
        raise RuntimeError("r3 canonical inventory SHA256 불일치")
    return manifest


def load_donors(path: Path) -> dict[str, tuple[list[str], list[str]]]:
    donors: dict[str, tuple[list[str], list[str]]] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != INVENTORY_FIELDS:
            raise RuntimeError("r3 canonical inventory 열 계약 불일치")
        for row in reader:
            if row["selection_status"] != "provisional_retain_exact_rule":
                continue
            token = clean(row["token"])
            phones = json_list(row["selected_pron_phones_json"], "selected phones", token)
            romans = json_list(row["selected_pron_roman_json"], "selected romans", token)
            if not phones or len(phones) != len(romans):
                raise RuntimeError(f"{token} provisional donor 변이 오류")
            donors[token] = (phones, romans)
    return donors


def build_candidates(
    *,
    inventory_path: Path,
    inventory_manifest_path: Path,
    output_path: Path,
    output_manifest_path: Path,
    progress_every: int = 50_000,
) -> dict[str, object]:
    for path in (output_path, output_manifest_path):
        if path.exists():
            raise FileExistsError(f"기존 donor 산출물을 덮어쓰지 않음: {path}")
    source_manifest = verify_manifest(inventory_path, inventory_manifest_path)
    donors = load_donors(inventory_path)
    counts: Counter[str] = Counter()
    occurrence_counts: Counter[str] = Counter()
    previous = ""
    row_count = 0
    candidate_types = 0
    candidate_occurrences = 0
    with gzip.open(
        inventory_path, "rt", encoding="utf-8-sig", newline=""
    ) as source:
        reader = csv.DictReader(source)
        with atomic_gzip_writer(output_path) as target:
            writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row_count, row in enumerate(reader, 1):
                token = clean(row["token"])
                if not token or (previous and token <= previous):
                    raise RuntimeError(f"donor candidate token 정렬/중복 오류: {token!r}")
                previous = token
                candidate_phones: list[str] = []
                candidate_romans: list[str] = []
                candidate_status = "none"
                candidate_source = ""
                candidate_reason = ""
                if row["selected_variant_count"] == "0":
                    donor_token = clean(row["rule_pron_hangul"])
                    donor = donors.get(donor_token)
                    if donor is not None:
                        candidate_phones, candidate_romans = matching_donor_variants(
                            target_roman=row["rule_pron_roman"],
                            donor_phones=donor[0],
                            donor_romans=donor[1],
                        )
                        if candidate_phones:
                            candidate_status = "surface_donor_exact_rule"
                            candidate_source = f"canonical_inventory_token:{donor_token}"
                            candidate_reason = (
                                "donor token has a provisionally retained r2 variant whose "
                                "broad Roman sequence exactly equals this rule target"
                            )
                            candidate_types += 1
                            candidate_occurrences += int(row["total_occurrences"])
                counts[candidate_status] += 1
                occurrence_counts[candidate_status] += int(row["total_occurrences"])
                output = dict(row)
                output.update(
                    {
                        "candidate_variant_count": str(len(candidate_phones)),
                        "candidate_pron_phones_json": json.dumps(
                            candidate_phones, ensure_ascii=False
                        ),
                        "candidate_pron_roman_json": json.dumps(
                            candidate_romans, ensure_ascii=False
                        ),
                        "candidate_status": candidate_status,
                        "candidate_source": candidate_source,
                        "candidate_reason": candidate_reason,
                    }
                )
                writer.writerow(output)
                if progress_every and row_count % progress_every == 0:
                    print(
                        f"[surface-donor] {row_count:,} types; candidates={candidate_types:,}",
                        flush=True,
                    )
    expected = int(source_manifest["coverage"]["total_types"])
    if row_count != expected:
        raise RuntimeError(f"surface donor coverage 불일치: {row_count} != {expected}")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_candidates_not_selected",
        "recorded_at": now_iso(),
        "scope": {
            "row_unit": "one_observed_surface_word_type",
            "candidate_is_final_selection": False,
            "source_files_modified": False,
        },
        "inputs": {
            "canonical_inventory": file_fingerprint(
                inventory_path, with_sha256=True
            ),
            "canonical_inventory_manifest": file_fingerprint(
                inventory_manifest_path, with_sha256=True
            ),
        },
        "coverage": {
            "total_types": row_count,
            "donor_pool_types": len(donors),
            "surface_donor_candidate_types": candidate_types,
            "surface_donor_candidate_occurrences": candidate_occurrences,
        },
        "candidate_status_types": dict(sorted(counts.items())),
        "candidate_status_occurrences": dict(sorted(occurrence_counts.items())),
        "outputs": {
            "candidate_inventory": file_fingerprint(output_path, with_sha256=True)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=50_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_candidates(
        inventory_path=args.inventory.resolve(),
        inventory_manifest_path=args.inventory_manifest.resolve(),
        output_path=args.output.resolve(),
        output_manifest_path=args.manifest.resolve(),
        progress_every=args.progress_every,
    )
    coverage = manifest["coverage"]
    print(
        "[OK] r3 surface donor candidates: "
        f"types={coverage['surface_donor_candidate_types']:,}; "
        f"occurrences={coverage['surface_donor_candidate_occurrences']:,}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

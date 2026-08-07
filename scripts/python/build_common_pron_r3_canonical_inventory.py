"""r2 전수 감사에서 r3 canonical 발음 선택 inventory를 만든다.

이 단계는 최종 MFA 사전을 만들지 않는다. 현재 phone이 프로젝트 표면 규칙형과
정확히 일치하는 경우만 provisional 선택하고, 나머지는 근거별 후보/보류 상태로
분리한다. 사전·규칙이 동의해도 backend phone을 임의 G2P 1-best로 생성하지 않는다.
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

from audit_common_pron_rule_consistency import (  # noqa: E402
    OUTPUT_FIELDS as AUDIT_FIELDS,
    YEARS,
    roman_units,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from predict_pron import predict_pron  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_r3_canonical_inventory.v1"
OUTPUT_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "orth_roman",
    "rule_pron_hangul",
    "rule_pron_roman",
    "surface_rule_names",
    "dictionary_pron_hangul_json",
    "dictionary_pron_roman_json",
    "dictionary_source_refs_json",
    "r2_pron_phones_json",
    "r2_pron_roman_json",
    "r2_pron_source",
    "selected_variant_count",
    "selected_pron_phones_json",
    "selected_pron_roman_json",
    "selection_status",
    "selection_source",
    "selection_reason",
    "morph_context_required",
    "manual_decision_id",
)


def clean(value: object) -> str:
    return str(value or "").strip()


def truth(value: object) -> bool:
    return clean(value).lower() == "true"


@contextmanager
def atomic_gzip_text_writer(path: Path) -> Iterator[TextIO]:
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


def load_json_list(value: object, label: str, token: str) -> list[str]:
    try:
        parsed = json.loads(clean(value) or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{token} {label} JSON 오류") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise RuntimeError(f"{token} {label}는 문자열 JSON 배열이어야 함")
    return parsed


def provisional_exact_rule_variants(
    row: dict[str, str]
) -> tuple[list[str], list[str]]:
    token = row["token"]
    phones = load_json_list(row["current_pron_phones_json"], "r2 phones", token)
    romans = load_json_list(row["current_pron_roman_json"], "r2 roman", token)
    if len(phones) != len(romans):
        raise RuntimeError(f"{token} r2 phone/roman variant 수 불일치")
    _, rule_keys = roman_units(row["rule_pron_roman"])
    selected_phones: list[str] = []
    selected_romans: list[str] = []
    for phone, roman in zip(phones, romans, strict=True):
        _, keys = roman_units(roman)
        if keys and rule_keys and keys == rule_keys:
            selected_phones.append(phone)
            selected_romans.append(roman)
    return selected_phones, selected_romans


def classify_selection(row: dict[str, str]) -> dict[str, object]:
    status = row["comparison_status"]
    if status == "matches_surface_rule":
        phones, romans = provisional_exact_rule_variants(row)
        if not phones:
            raise RuntimeError(
                f"{row['token']} matches_surface_rule인데 선택 가능한 변이가 없음"
            )
        return {
            "phones": phones,
            "romans": romans,
            "status": "provisional_retain_exact_rule",
            "source": "r2_variant_exact_surface_rule",
            "reason": "r2 broad Roman sequence equals the mandatory surface-rule reference",
            "morph": False,
        }
    if status == "phone_inventory_unmapped":
        code = "blocked_phone_inventory_unmapped"
        reason = "r2 phone cannot be mapped inside the frozen acoustic inventory"
    elif status == "unresolved_non_plain_hangul":
        code = "review_non_plain_hangul_or_symbol"
        reason = "surface token requires an explicit symbol/reading policy"
    elif status == "mismatch_rule_sensitive" and truth(row["rule_matches_dictionary"]):
        code = "candidate_replace_rule_dictionary_agree"
        reason = "surface rule and dictionary evidence agree, but r2 phones differ"
    elif status == "mismatch_rule_sensitive" and truth(row["current_matches_dictionary"]):
        code = "review_rule_dictionary_conflict"
        reason = "r2 agrees with a dictionary candidate while the surface-rule target differs"
    elif status == "mismatch_rule_sensitive":
        code = "review_rule_sensitive_no_attested_agreement"
        reason = "surface-rule target differs from r2 without independent dictionary agreement"
    elif status == "mismatch_no_surface_rule_change" and truth(
        row["current_matches_dictionary"]
    ):
        code = "candidate_dictionary_supported_exception"
        reason = "r2 differs from the plain surface target but matches dictionary evidence"
    elif status == "mismatch_no_surface_rule_change":
        code = "review_no_surface_rule_mismatch"
        reason = "r2 differs although the current surface-rule predictor makes no change"
    else:
        code = "review_unclassified"
        reason = f"unhandled audit comparison status: {status}"
    return {
        "phones": [],
        "romans": [],
        "status": code,
        "source": "pending_r3_selection",
        "reason": reason,
        "morph": True,
    }


def verify_audit_manifest(audit_path: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != "common_pron_rule_consistency_audit.v1":
        raise RuntimeError("r2 규칙 감사 manifest schema 불일치")
    if manifest.get("status") != "success":
        raise RuntimeError("r2 규칙 감사가 success가 아님")
    expected = clean(manifest["outputs"]["full_audit"].get("sha256"))
    actual = sha256_file(audit_path)
    if not expected or actual.lower() != expected.lower():
        raise RuntimeError("r2 규칙 감사 CSV SHA256 불일치")
    return manifest


def build_inventory(
    *,
    audit_path: Path,
    audit_manifest_path: Path,
    output_path: Path,
    output_manifest_path: Path,
    progress_every: int = 50_000,
) -> dict[str, object]:
    for path in (output_path, output_manifest_path):
        if path.exists():
            raise FileExistsError(f"기존 r3 inventory를 덮어쓰지 않음: {path}")
    audit_manifest = verify_audit_manifest(audit_path, audit_manifest_path)
    counts: Counter[str] = Counter()
    occurrence_counts: Counter[str] = Counter()
    selected_types = 0
    selected_occurrences = 0
    previous = ""
    row_count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(audit_path, "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != AUDIT_FIELDS:
            raise RuntimeError("r2 규칙 감사 CSV 열 계약 불일치")
        with atomic_gzip_text_writer(output_path) as target:
            writer = csv.DictWriter(target, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
            writer.writeheader()
            for row_count, row in enumerate(reader, 1):
                token = clean(row["token"])
                if not token or (previous and token <= previous):
                    raise RuntimeError(f"r3 inventory token 정렬/중복 오류: {token!r}")
                previous = token
                decision = classify_selection(row)
                total = int(row["total_occurrences"])
                selected_count = len(decision["phones"])
                if selected_count:
                    selected_types += 1
                    selected_occurrences += total
                counts[str(decision["status"])] += 1
                occurrence_counts[str(decision["status"])] += total
                prediction = predict_pron(token)
                output = {
                    "token": token,
                    "total_occurrences": row["total_occurrences"],
                    "n_years_present": row["n_years_present"],
                    **{f"count_{year}": row[f"count_{year}"] for year in YEARS},
                    "orth_roman": prediction["form_roman"],
                    "rule_pron_hangul": row["rule_pron_hangul"],
                    "rule_pron_roman": row["rule_pron_roman"],
                    "surface_rule_names": row["surface_rule_names"],
                    "dictionary_pron_hangul_json": row["dictionary_pron_hangul_json"],
                    "dictionary_pron_roman_json": row["dictionary_pron_roman_json"],
                    "dictionary_source_refs_json": row["dictionary_source_refs_json"],
                    "r2_pron_phones_json": row["current_pron_phones_json"],
                    "r2_pron_roman_json": row["current_pron_roman_json"],
                    "r2_pron_source": row["current_pron_source"],
                    "selected_variant_count": str(selected_count),
                    "selected_pron_phones_json": json.dumps(decision["phones"], ensure_ascii=False),
                    "selected_pron_roman_json": json.dumps(decision["romans"], ensure_ascii=False),
                    "selection_status": decision["status"],
                    "selection_source": decision["source"],
                    "selection_reason": decision["reason"],
                    "morph_context_required": "true" if decision["morph"] else "false",
                    "manual_decision_id": "",
                }
                writer.writerow(output)
                if progress_every and row_count % progress_every == 0:
                    print(
                        f"[r3-inventory] {row_count:,} types; provisional={selected_types:,}",
                        flush=True,
                    )
    expected_rows = int(audit_manifest["counts_by_status_types"].get("source:korean_mfa_dictionary_v3.3.0_preserved", 0))
    expected_rows += sum(
        int(value)
        for key, value in audit_manifest["counts_by_status_types"].items()
        if key.startswith("source:") and key != "source:korean_mfa_dictionary_v3.3.0_preserved"
    )
    if row_count != expected_rows:
        raise RuntimeError(f"r3 inventory coverage 불일치: {row_count} != {expected_rows}")
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success_incomplete_selection",
        "recorded_at": now_iso(),
        "scope": {
            "row_unit": "one_observed_surface_word_type",
            "years": list(YEARS),
            "automatic_final_adoption": False,
            "actual_realization_claimed": False,
            "source_files_modified": False,
        },
        "inputs": {
            "rule_audit": file_fingerprint(audit_path, with_sha256=True),
            "rule_audit_manifest": file_fingerprint(
                audit_manifest_path, with_sha256=True
            ),
        },
        "coverage": {
            "total_types": row_count,
            "provisionally_selected_types": selected_types,
            "unselected_types": row_count - selected_types,
            "provisionally_selected_occurrences": selected_occurrences,
        },
        "selection_status_types": dict(sorted(counts.items())),
        "selection_status_occurrences": dict(sorted(occurrence_counts.items())),
        "outputs": {
            "canonical_inventory": file_fingerprint(output_path, with_sha256=True)
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(output_manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-audit", type=Path, required=True)
    parser.add_argument("--rule-audit-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--progress-every", type=int, default=50_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_inventory(
        audit_path=args.rule_audit.resolve(),
        audit_manifest_path=args.rule_audit_manifest.resolve(),
        output_path=args.output.resolve(),
        output_manifest_path=args.manifest.resolve(),
        progress_every=args.progress_every,
    )
    coverage = manifest["coverage"]
    print(
        "[OK] r3 canonical inventory: "
        f"types={coverage['total_types']:,}; "
        f"provisional={coverage['provisionally_selected_types']:,}; "
        f"unselected={coverage['unselected_types']:,}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

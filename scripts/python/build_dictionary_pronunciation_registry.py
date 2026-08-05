"""Build the reusable dictionary-pronunciation registry.

The registry is a reference layer, not an MFA pronunciation dictionary.  It
preserves attested ``pron_1``/``pron_2`` values and labels legacy ``pron_g2p``
values as machine-generated fallbacks.  Existing MFA outputs are never read or
modified by this script.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


SCHEMA_VERSION = "dictionary_pronunciation_registry.v1"
ROMAN_SYSTEM = "source_preserved_with_roman_mfa.v1"
PLAIN_HANGUL_RE = re.compile(r"^[가-힣]+$")

ENRICHED_REQUIRED = {
    "word",
    "word_stem",
    "pos_full",
    "pos_tag",
    "pos_group",
    "sense_no",
    "urimal_id",
    "stdict_target_code",
    "stdict_sense_code",
    "pron_1",
    "pron_1_roman",
    "pron_1_roman_mfa",
    "pron_2",
    "pron_2_roman",
    "pron_2_roman_mfa",
}
LEGACY_REQUIRED = {
    "urimal_id",
    "pron_g2p",
    "pron_g2p_roman",
}

FIELDS = [
    "dict_pron_candidate_id",
    "headword",
    "word_stem",
    "pos_full",
    "pos_tag",
    "pos_group",
    "sense_no",
    "urimal_id",
    "stdict_target_code",
    "stdict_sense_code",
    "pron_hangul",
    "pron_roman",
    "pron_roman_mfa",
    "roman_system_version",
    "variant_rank",
    "source_name",
    "source_field",
    "source_match_mode",
    "is_dictionary_attested",
    "is_primary",
    "is_alternative",
    "is_legacy_fallback",
    "is_machine_generated",
    "plain_hangul_pron",
    "pron_differs_from_headword",
]

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def _bool(value: bool) -> str:
    return "true" if value else "false"


def candidate_id(row: dict[str, str]) -> str:
    """Return a stable semantic ID independent of source row order."""

    identity_fields = (
        "headword",
        "word_stem",
        "pos_tag",
        "pos_group",
        "sense_no",
        "urimal_id",
        "stdict_target_code",
        "stdict_sense_code",
        "pron_hangul",
        "source_name",
        "source_field",
        "source_match_mode",
    )
    canonical = "\0".join(clean(row.get(field)) for field in identity_fields)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_source_audit(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("status") != "success":
        raise RuntimeError(f"성공한 사전 원천 감사 보고서가 아님: {path}")
    sources = payload.get("sources") or {}
    if not {"enriched", "legacy"}.issubset(sources):
        raise RuntimeError(f"사전 원천 감사 fingerprint 누락: {path}")
    return payload


def _verify_audited_source(
    *, path: Path, expected: dict, source_label: str
) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = file_fingerprint(path, with_sha256=False)
    for field in ("bytes", "mtime_ns"):
        if int(actual[field]) != int(expected[field]):
            raise RuntimeError(
                f"{source_label} 원천이 감사 후 변경됨: {field} "
                f"expected={expected[field]} actual={actual[field]}"
            )
    expected_path = str(Path(expected["path"]).resolve()).casefold()
    actual_path = str(path.resolve()).casefold()
    if actual_path != expected_path:
        raise RuntimeError(
            f"{source_label} 경로가 감사 보고서와 다름: "
            f"expected={expected['path']} actual={path.resolve()}"
        )
    return {
        **actual,
        "sha256": expected.get("sha256", ""),
        "fingerprint_verification": "path_size_mtime_match_prior_sha256_audit",
    }


def validate_inputs(
    *, enriched_path: Path, legacy_path: Path, source_audit_path: Path
) -> tuple[dict, dict, dict]:
    audit = _read_source_audit(source_audit_path)
    enriched_fp = _verify_audited_source(
        path=enriched_path,
        expected=audit["sources"]["enriched"],
        source_label="enriched",
    )
    legacy_fp = _verify_audited_source(
        path=legacy_path,
        expected=audit["sources"]["legacy"],
        source_label="legacy",
    )
    return audit, enriched_fp, legacy_fp


def _check_header(path: Path, required: set[str], label: str) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream), [])
    missing = required - set(header)
    if missing:
        raise RuntimeError(f"{label} 필수 열 누락: {sorted(missing)}")
    return header


@contextmanager
def atomic_gzip_text_writer(path: Path) -> Iterator[TextIO]:
    """Write deterministic gzip text and promote only after a clean close."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    raw = temp.open("xb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8-sig", newline="")
    try:
        yield text
        text.flush()
        gz.flush()
        raw.flush()
        os.fsync(raw.fileno())
        text.close()
        raw.close()
        os.replace(temp, path)
    except BaseException:
        if not text.closed:
            text.close()
        if not raw.closed:
            raw.close()
        raise


def load_legacy_fallbacks(
    path: Path, *, progress_every: int = 250_000
) -> tuple[dict[str, set[tuple[str, str, str]]], Counter]:
    result: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    counts: Counter = Counter()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = LEGACY_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"legacy 필수 열 누락: {sorted(missing)}")
        has_mfa_roman = "pron_g2p_roman_mfa" in (reader.fieldnames or ())
        for row_number, row in enumerate(reader, 1):
            counts["legacy_rows"] += 1
            urimal_id = clean(row.get("urimal_id"))
            pron = clean(row.get("pron_g2p"))
            if urimal_id and pron:
                roman = clean(row.get("pron_g2p_roman"))
                roman_mfa = (
                    clean(row.get("pron_g2p_roman_mfa"))
                    if has_mfa_roman
                    else roman
                )
                result[urimal_id].add((pron, roman, roman_mfa))
                counts["legacy_rows_with_fallback"] += 1
            if progress_every and row_number % progress_every == 0:
                print(f"[registry] legacy {row_number:,}행", flush=True)
    counts["legacy_urimal_ids_with_fallback"] = len(result)
    return dict(result), counts


def _base_row(source: dict[str, str]) -> dict[str, str]:
    return {
        "headword": clean(source.get("word")),
        "word_stem": clean(source.get("word_stem")),
        "pos_full": clean(source.get("pos_full")),
        "pos_tag": clean(source.get("pos_tag")),
        "pos_group": clean(source.get("pos_group")),
        "sense_no": clean(source.get("sense_no")),
        "urimal_id": clean(source.get("urimal_id")),
        "stdict_target_code": clean(source.get("stdict_target_code")),
        "stdict_sense_code": clean(source.get("stdict_sense_code")),
        "roman_system_version": ROMAN_SYSTEM,
    }


def _complete_candidate(
    base: dict[str, str],
    *,
    pron: str,
    roman: str,
    roman_mfa: str,
    rank: str,
    source_name: str,
    source_field: str,
    source_match_mode: str,
    dictionary_attested: bool,
    primary: bool,
    alternative: bool,
    legacy_fallback: bool,
    machine_generated: bool,
) -> dict[str, str]:
    row = {
        **base,
        "pron_hangul": pron,
        "pron_roman": roman,
        "pron_roman_mfa": roman_mfa,
        "variant_rank": rank,
        "source_name": source_name,
        "source_field": source_field,
        "source_match_mode": source_match_mode,
        "is_dictionary_attested": _bool(dictionary_attested),
        "is_primary": _bool(primary),
        "is_alternative": _bool(alternative),
        "is_legacy_fallback": _bool(legacy_fallback),
        "is_machine_generated": _bool(machine_generated),
        "plain_hangul_pron": _bool(bool(PLAIN_HANGUL_RE.fullmatch(pron))),
        "pron_differs_from_headword": _bool(pron != base["headword"]),
    }
    row["dict_pron_candidate_id"] = candidate_id(row)
    return row


def iter_registry_rows(
    *,
    enriched_path: Path,
    legacy_by_urimal: dict[str, set[tuple[str, str, str]]],
    counts: Counter,
    progress_every: int = 250_000,
):
    seen: set[str] = set()
    with enriched_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        missing = ENRICHED_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"enriched 필수 열 누락: {sorted(missing)}")
        for row_number, source in enumerate(reader, 1):
            counts["enriched_rows"] += 1
            base = _base_row(source)
            candidates: list[dict[str, str]] = []
            pron_1 = clean(source.get("pron_1"))
            pron_2 = clean(source.get("pron_2"))
            if pron_1:
                candidates.append(
                    _complete_candidate(
                        base,
                        pron=pron_1,
                        roman=clean(source.get("pron_1_roman")),
                        roman_mfa=clean(source.get("pron_1_roman_mfa")),
                        rank="1",
                        source_name="NIKL_lexicon_full_v2",
                        source_field="pron_1",
                        source_match_mode="direct_enriched_record",
                        dictionary_attested=True,
                        primary=True,
                        alternative=False,
                        legacy_fallback=False,
                        machine_generated=False,
                    )
                )
            if pron_2:
                candidates.append(
                    _complete_candidate(
                        base,
                        pron=pron_2,
                        roman=clean(source.get("pron_2_roman")),
                        roman_mfa=clean(source.get("pron_2_roman_mfa")),
                        rank="2",
                        source_name="NIKL_lexicon_full_v2",
                        source_field="pron_2",
                        source_match_mode="direct_enriched_record",
                        dictionary_attested=True,
                        primary=False,
                        alternative=True,
                        legacy_fallback=False,
                        machine_generated=False,
                    )
                )
            if not pron_1 and not pron_2:
                fallback_values = legacy_by_urimal.get(base["urimal_id"], set())
                if not fallback_values:
                    counts["enriched_rows_without_any_candidate"] += 1
                for pron, roman, roman_mfa in sorted(fallback_values):
                    candidates.append(
                        _complete_candidate(
                            base,
                            pron=pron,
                            roman=roman,
                            roman_mfa=roman_mfa,
                            rank="fallback",
                            source_name="NIKL_lexicon_full_legacy",
                            source_field="pron_g2p",
                            source_match_mode="urimal_id_fallback",
                            dictionary_attested=False,
                            primary=False,
                            alternative=False,
                            legacy_fallback=True,
                            machine_generated=True,
                        )
                    )
            for row in candidates:
                cid = row["dict_pron_candidate_id"]
                if cid in seen:
                    counts["duplicate_candidates_removed"] += 1
                    continue
                seen.add(cid)
                counts["registry_rows"] += 1
                counts[f"source_field_{row['source_field']}"] += 1
                if row["is_dictionary_attested"] == "true":
                    counts["dictionary_attested_rows"] += 1
                if row["is_legacy_fallback"] == "true":
                    counts["legacy_fallback_rows"] += 1
                yield row
            if progress_every and row_number % progress_every == 0:
                print(
                    f"[registry] enriched {row_number:,}행 · "
                    f"후보 {counts['registry_rows']:,}",
                    flush=True,
                )


def build_registry(args: argparse.Namespace) -> dict:
    enriched_path = args.enriched.resolve()
    legacy_path = args.legacy.resolve()
    audit_path = args.source_audit.resolve()
    output_dir = args.output_dir.resolve()
    registry_path = output_dir / "dictionary_pronunciation_registry.csv.gz"
    manifest_path = output_dir / "dictionary_pronunciation_registry_manifest.json"

    audit, enriched_fp, legacy_fp = validate_inputs(
        enriched_path=enriched_path,
        legacy_path=legacy_path,
        source_audit_path=audit_path,
    )
    enriched_header = _check_header(
        enriched_path, ENRICHED_REQUIRED, "enriched"
    )
    legacy_header = _check_header(legacy_path, LEGACY_REQUIRED, "legacy")
    preflight = {
        "schema_version": SCHEMA_VERSION,
        "status": "preflight_passed",
        "inputs": {
            "enriched": enriched_fp,
            "legacy": legacy_fp,
            "source_audit": file_fingerprint(audit_path, with_sha256=True),
        },
        "headers": {
            "enriched_columns": len(enriched_header),
            "legacy_columns": len(legacy_header),
        },
        "outputs": {
            "registry": str(registry_path),
            "manifest": str(manifest_path),
        },
    }
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return preflight
    if registry_path.exists() or manifest_path.exists():
        raise FileExistsError(
            f"기존 registry 산출물 덮어쓰기 금지: {output_dir}"
        )

    started = time.perf_counter()
    legacy_by_urimal, legacy_counts = load_legacy_fallbacks(
        legacy_path, progress_every=args.progress_every
    )
    counts: Counter = Counter(legacy_counts)
    with atomic_gzip_text_writer(registry_path) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=FIELDS,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            iter_registry_rows(
                enriched_path=enriched_path,
                legacy_by_urimal=legacy_by_urimal,
                counts=counts,
                progress_every=args.progress_every,
            )
        )

    if counts["registry_rows"] == 0:
        raise RuntimeError("사전 발음 registry가 비어 있음")
    expected = audit.get("enriched") or {}
    for audit_key, count_key in (
        ("rows_with_pron_1", "source_field_pron_1"),
        ("rows_with_pron_2", "source_field_pron_2"),
    ):
        # Duplicated semantic records may collapse, but the result must never
        # exceed the audited raw-source count.
        if counts[count_key] > int(expected.get(audit_key, counts[count_key])):
            raise RuntimeError(f"원천 감사 count 초과: {count_key}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "dictionary_pronunciation_registry",
        "status": "success",
        "recorded_at": now_iso(),
        "scope": "full_reference_lexicon_type_level_candidates",
        "interpretation": {
            "pron_1": "dictionary_attested_primary_candidate",
            "pron_2": "dictionary_attested_alternative_candidate",
            "pron_g2p": "legacy_machine_fallback_not_attested",
            "mfa_dictionary_activation": False,
            "existing_mfa_outputs_modified": False,
        },
        "inputs": preflight["inputs"],
        "counts": dict(sorted(counts.items())),
        "outputs": {
            "registry": file_fingerprint(registry_path, with_sha256=True),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(Path(__file__).resolve().parents[2]),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] 사전 발음 registry {counts['registry_rows']:,}개: "
        f"{registry_path}",
        flush=True,
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--enriched", type=Path, required=True)
    result.add_argument("--legacy", type=Path, required=True)
    result.add_argument("--source-audit", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--progress-every", type=int, default=250_000)
    result.add_argument("--preflight-only", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.progress_every < 0:
        raise ValueError("--progress-every는 0 이상이어야 함")
    build_registry(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

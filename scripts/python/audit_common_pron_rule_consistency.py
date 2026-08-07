"""공통 MFA 발음열과 표면 음운규칙·사전 후보의 일관성을 전수 감사한다.

이 감사는 실제 발음 실현을 판정하지 않는다. 현재 MFA 입력 발음열이 프로젝트의
표면 규칙 예상형 및 사전 참조 후보와 얼마나 일치하는지 어휘 유형별로 비교한다.
원 사전, MFA DB, TextGrid는 읽기만 하며 새 발음사전을 자동 채택하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from itertools import groupby
from pathlib import Path
from typing import Iterator, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_common_pron_mfa_lexicon import read_mfa_dictionary  # noqa: E402
from phoneme_roman import (  # noqa: E402
    classify_phone,
    expand_roman_eojeol,
    load_acoustic_meta,
    model_group_lookup,
)
from pipeline_common import (  # noqa: E402
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)
from predict_pron import (  # noqa: E402
    DEFAULT_FLAGS,
    RULE_FUNCS,
    RULE_ORDER,
    _is_processable,
    compose,
    decompose,
    predict_pron,
    r_fortis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_rule_consistency_audit.v1"
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
VOCAB_FIELDS = (
    "token",
    "n_syllables",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
)
G2P_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
    "pron_phones_mfa",
    "pron_source",
)
REGISTRY_REQUIRED = {
    "headword",
    "pron_hangul",
    "pron_roman_search",
    "source_name",
    "source_field",
    "is_dictionary_attested",
    "is_machine_generated",
}
OUTPUT_FIELDS = (
    *VOCAB_FIELDS,
    "current_pron_source",
    "current_pron_variant_count",
    "current_pron_phones_json",
    "current_pron_roman_json",
    "rule_pron_hangul",
    "rule_pron_roman",
    "surface_rule_names",
    "surface_rule_sensitive",
    "dictionary_candidate_rows",
    "dictionary_unique_pronunciations",
    "dictionary_pron_hangul_json",
    "dictionary_pron_roman_json",
    "dictionary_source_refs_json",
    "dictionary_reference_status",
    "current_matches_rule",
    "current_matches_dictionary",
    "rule_matches_dictionary",
    "minimum_rule_edit_distance",
    "comparison_status",
    "audit_scope_note",
)

csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: object) -> str:
    return str(value or "").strip()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


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
        # 실패 원인을 조사할 수 있도록 partial은 보존한다.
        raise


def read_and_validate_vocabulary(path: Path) -> Iterator[dict[str, str]]:
    previous = ""
    seen = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != VOCAB_FIELDS:
            raise RuntimeError(
                f"vocabulary 열 불일치: {reader.fieldnames} != {VOCAB_FIELDS}"
            )
        for line_number, row in enumerate(reader, 2):
            token = clean(row.get("token"))
            if not token or (seen and token <= previous):
                raise RuntimeError(
                    f"vocabulary token 정렬/중복 오류: line={line_number} "
                    f"previous={previous!r} token={token!r}"
                )
            counts = [int(row[f"count_{year}"]) for year in YEARS]
            if sum(counts) != int(row["total_occurrences"]):
                raise RuntimeError(f"vocabulary 총빈도 불일치: {token}")
            if sum(value > 0 for value in counts) != int(row["n_years_present"]):
                raise RuntimeError(f"vocabulary 연도수 불일치: {token}")
            previous = token
            seen += 1
            yield {field: clean(row.get(field)) for field in VOCAB_FIELDS}


def iter_g2p(path: Path) -> Iterator[dict[str, str]]:
    previous = ""
    seen = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != G2P_FIELDS:
            raise RuntimeError(f"G2P cache 열 불일치: {reader.fieldnames}")
        for line_number, row in enumerate(reader, 2):
            token = clean(row.get("token"))
            if not token or (seen and token <= previous):
                raise RuntimeError(
                    f"G2P token 정렬/중복 오류: line={line_number} "
                    f"previous={previous!r} token={token!r}"
                )
            previous = token
            seen += 1
            yield {field: clean(row.get(field)) for field in G2P_FIELDS}


def registry_groups(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REGISTRY_REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"사전 registry 필수 열 누락: {sorted(missing)}")
        previous = ""
        seen = 0
        for headword, rows in groupby(reader, key=lambda row: clean(row["headword"])):
            if not headword or (seen and headword <= previous):
                raise RuntimeError(
                    "사전 registry headword 정렬/중복 그룹 오류: "
                    f"previous={previous!r} headword={headword!r}"
                )
            pronunciations: set[str] = set()
            romans: set[str] = set()
            sources: set[str] = set()
            row_count = 0
            attested = False
            machine = False
            for row in rows:
                row_count += 1
                pron = clean(row.get("pron_hangul"))
                roman = clean(row.get("pron_roman_search"))
                if pron:
                    pronunciations.add(pron)
                if roman:
                    romans.add(roman)
                source = ":".join(
                    part
                    for part in (
                        clean(row.get("source_name")),
                        clean(row.get("source_field")),
                    )
                    if part
                )
                if source:
                    sources.add(source)
                attested = attested or clean(row.get("is_dictionary_attested")).lower() == "true"
                machine = machine or clean(row.get("is_machine_generated")).lower() == "true"
            previous = headword
            seen += 1
            yield headword, {
                "row_count": row_count,
                "pronunciations": sorted(pronunciations),
                "romans": sorted(romans),
                "sources": sorted(sources),
                "has_attested": attested,
                "has_machine": machine,
            }


def next_or_none(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None


def applied_surface_rules(token: str) -> tuple[str, ...]:
    if not _is_processable(token):
        return ()
    syllables = [decompose(char) for char in token]
    applied: list[str] = []
    for name in RULE_ORDER:
        if not DEFAULT_FLAGS.get(name, True):
            continue
        before = tuple(tuple(value) for value in syllables)
        if name == "fortis":
            r_fortis(syllables, frozenset())
        else:
            RULE_FUNCS[name](syllables)
        after = tuple(tuple(value) for value in syllables)
        if after != before:
            applied.append(name)
    # compose를 호출해 비정상 자모 상태를 즉시 검출한다.
    for onset, vowel, coda in syllables:
        compose(onset, vowel, coda)
    return tuple(applied)


def roman_units(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    units = expand_roman_eojeol(value)
    return (
        tuple(unit.display for unit in units),
        tuple(unit.comparison_key for unit in units),
    )


def phone_units(
    phones: tuple[str, ...], group_lookup: dict[str, int]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    classified = [classify_phone(phone, group_lookup) for phone in phones]
    return (
        tuple(item.phone_class_r_auto for item in classified),
        tuple(item.comparison_key for item in classified),
    )


def edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for i, lhs in enumerate(left, 1):
        current = [i]
        for j, rhs in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (lhs != rhs),
                )
            )
        previous = current
    return previous[-1]


def dictionary_status(group: dict[str, object] | None) -> str:
    if group is None or not group["pronunciations"]:
        return "no_headword_pronunciation_reference"
    count = len(group["pronunciations"])
    if bool(group["has_attested"]):
        return "attested_unique" if count == 1 else "attested_multiple"
    if bool(group["has_machine"]):
        return "machine_only_unique" if count == 1 else "machine_only_multiple"
    return "other_unique" if count == 1 else "other_multiple"


def build_audit(
    *,
    vocabulary: Path,
    g2p_cache: Path,
    base_dictionary: Path,
    acoustic_model: Path,
    dictionary_registry: Path,
    output_csv_gz: Path,
    top_csv: Path,
    manifest_path: Path,
    top_n: int,
    progress_every: int,
) -> dict[str, object]:
    outputs = (output_csv_gz, top_csv, manifest_path)
    for path in outputs:
        if path.exists():
            raise FileExistsError(f"기존 감사 산출물을 덮어쓰지 않음: {path}")
    for path in (
        vocabulary,
        g2p_cache,
        base_dictionary,
        acoustic_model,
        dictionary_registry,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    _, base_prons = read_mfa_dictionary(base_dictionary)
    group_lookup = model_group_lookup(load_acoustic_meta(acoustic_model))
    g2p_iter = iter(iter_g2p(g2p_cache))
    g2p_row = next_or_none(g2p_iter)
    registry_iter = iter(registry_groups(dictionary_registry))
    registry_row = next_or_none(registry_iter)

    counters: Counter[str] = Counter()
    occurrence_counters: Counter[str] = Counter()
    rule_counters: Counter[str] = Counter()
    rule_occurrence_counters: Counter[str] = Counter()
    top_heap: list[tuple[int, str, dict[str, str]]] = []

    output_csv_gz.parent.mkdir(parents=True, exist_ok=True)
    top_csv.parent.mkdir(parents=True, exist_ok=True)
    with atomic_gzip_text_writer(output_csv_gz) as output_stream:
        writer = csv.DictWriter(
            output_stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for index, vocab in enumerate(read_and_validate_vocabulary(vocabulary), 1):
            token = vocab["token"]
            total = int(vocab["total_occurrences"])

            while g2p_row is not None and g2p_row["token"] < token:
                raise RuntimeError(
                    f"G2P cache token이 vocabulary에 없음: {g2p_row['token']}"
                )
            if g2p_row is not None and g2p_row["token"] == token:
                current_variants = [tuple(g2p_row["pron_phones_mfa"].split())]
                current_source = g2p_row["pron_source"]
                for field in ("total_occurrences", "n_years_present", *(f"count_{year}" for year in YEARS)):
                    if g2p_row[field] != vocab[field]:
                        raise RuntimeError(
                            f"G2P/vocabulary 빈도 불일치: {token} field={field}"
                        )
                g2p_row = next_or_none(g2p_iter)
            else:
                current_variants = sorted(base_prons.get(token, set()))
                current_source = "korean_mfa_dictionary_v3.3.0_preserved"
                if not current_variants:
                    raise RuntimeError(f"현재 발음열을 찾을 수 없음: {token}")

            while registry_row is not None and registry_row[0] < token:
                registry_row = next_or_none(registry_iter)
            dictionary_group = (
                registry_row[1]
                if registry_row is not None and registry_row[0] == token
                else None
            )

            prediction = predict_pron(token)
            rule_hangul = prediction["pron_pred_hangul"]
            rule_roman = prediction["pron_pred_roman"]
            rules = applied_surface_rules(token)
            rule_labels, rule_keys = roman_units(rule_roman)

            current_phone_json: list[str] = []
            current_roman_json: list[str] = []
            current_keys: list[tuple[str, ...]] = []
            phone_error = ""
            for phones in current_variants:
                current_phone_json.append(" ".join(phones))
                try:
                    labels, keys = phone_units(phones, group_lookup)
                except KeyError as exc:
                    phone_error = str(exc)
                    labels, keys = (), ()
                current_roman_json.append(" ".join(labels))
                current_keys.append(keys)

            dictionary_prons = (
                list(dictionary_group["pronunciations"])
                if dictionary_group is not None
                else []
            )
            dictionary_romans = (
                list(dictionary_group["romans"])
                if dictionary_group is not None
                else []
            )
            dictionary_keys: list[tuple[str, ...]] = []
            for value in dictionary_romans:
                _, keys = roman_units(value)
                if keys:
                    dictionary_keys.append(keys)

            current_matches_rule = bool(rule_keys) and any(
                keys == rule_keys for keys in current_keys
            )
            current_matches_dictionary = bool(dictionary_keys) and any(
                current == candidate
                for current in current_keys
                for candidate in dictionary_keys
            )
            rule_matches_dictionary = (
                rule_hangul in dictionary_prons
                or (
                    bool(rule_keys)
                    and any(rule_keys == candidate for candidate in dictionary_keys)
                )
            )
            distances = [
                edit_distance(keys, rule_keys)
                for keys in current_keys
                if keys and rule_keys
            ]
            minimum_distance = min(distances) if distances else None

            if phone_error:
                status = "phone_inventory_unmapped"
            elif not rule_keys:
                status = "unresolved_non_plain_hangul"
            elif current_matches_rule:
                status = "matches_surface_rule"
            elif rules:
                status = "mismatch_rule_sensitive"
            else:
                status = "mismatch_no_surface_rule_change"

            group_status = dictionary_status(dictionary_group)
            row = {
                **vocab,
                "current_pron_source": current_source,
                "current_pron_variant_count": str(len(current_variants)),
                "current_pron_phones_json": json.dumps(
                    current_phone_json, ensure_ascii=False
                ),
                "current_pron_roman_json": json.dumps(
                    current_roman_json, ensure_ascii=False
                ),
                "rule_pron_hangul": rule_hangul,
                "rule_pron_roman": rule_roman,
                "surface_rule_names": "|".join(rules),
                "surface_rule_sensitive": bool_text(bool(rules)),
                "dictionary_candidate_rows": str(
                    dictionary_group["row_count"] if dictionary_group else 0
                ),
                "dictionary_unique_pronunciations": str(len(dictionary_prons)),
                "dictionary_pron_hangul_json": json.dumps(
                    dictionary_prons, ensure_ascii=False
                ),
                "dictionary_pron_roman_json": json.dumps(
                    dictionary_romans, ensure_ascii=False
                ),
                "dictionary_source_refs_json": json.dumps(
                    dictionary_group["sources"] if dictionary_group else [],
                    ensure_ascii=False,
                ),
                "dictionary_reference_status": group_status,
                "current_matches_rule": bool_text(current_matches_rule),
                "current_matches_dictionary": bool_text(
                    current_matches_dictionary
                ),
                "rule_matches_dictionary": bool_text(rule_matches_dictionary),
                "minimum_rule_edit_distance": (
                    str(minimum_distance) if minimum_distance is not None else ""
                ),
                "comparison_status": status,
                "audit_scope_note": (
                    "type-level surface rule audit; no morph context and no "
                    "realized-speech judgment"
                ),
            }
            writer.writerow(row)

            counters[status] += 1
            occurrence_counters[status] += total
            counters[f"source:{current_source}"] += 1
            counters[f"dictionary:{group_status}"] += 1
            if rules:
                signature = "|".join(rules)
                rule_counters[signature] += 1
                rule_occurrence_counters[signature] += total
            if status == "mismatch_rule_sensitive":
                item = (total, token, row)
                if len(top_heap) < top_n:
                    heapq.heappush(top_heap, item)
                elif item[:2] > top_heap[0][:2]:
                    heapq.heapreplace(top_heap, item)
            if progress_every and index % progress_every == 0:
                print(
                    f"[rule-audit] {index:,} 어휘; "
                    f"규칙민감 불일치={counters['mismatch_rule_sensitive']:,}",
                    flush=True,
                )

    if g2p_row is not None or next_or_none(g2p_iter) is not None:
        raise RuntimeError("G2P cache 미소비 행이 남음")

    top_rows = [item[2] for item in sorted(top_heap, reverse=True)]
    with top_csv.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(top_rows)

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "recorded_at": now_iso(),
        "scope": {
            "unit": "observed_surface_word_type",
            "years": list(YEARS),
            "realized_speech_judgment": False,
            "morphological_context_used": False,
            "automatic_lexicon_adoption": False,
            "source_files_modified": False,
        },
        "inputs": {
            "vocabulary": file_fingerprint(vocabulary, with_sha256=True),
            "g2p_cache": file_fingerprint(g2p_cache, with_sha256=True),
            "base_dictionary": file_fingerprint(
                base_dictionary, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(acoustic_model, with_sha256=True),
            "dictionary_registry": file_fingerprint(
                dictionary_registry, with_sha256=True
            ),
        },
        "counts_by_status_types": dict(sorted(counters.items())),
        "counts_by_status_occurrences": dict(
            sorted(occurrence_counters.items())
        ),
        "surface_rule_signatures_types": dict(
            rule_counters.most_common()
        ),
        "surface_rule_signatures_occurrences": dict(
            rule_occurrence_counters.most_common()
        ),
        "outputs": {
            "full_audit": file_fingerprint(output_csv_gz, with_sha256=True),
            "top_rule_sensitive_mismatches": file_fingerprint(
                top_csv, with_sha256=True
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--g2p-cache", type=Path, required=True)
    parser.add_argument("--base-dictionary", type=Path, required=True)
    parser.add_argument("--acoustic-model", type=Path, required=True)
    parser.add_argument("--dictionary-registry", type=Path, required=True)
    parser.add_argument("--output-csv-gz", type=Path, required=True)
    parser.add_argument("--top-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=1000)
    parser.add_argument("--progress-every", type=int, default=50_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_audit(
        vocabulary=args.vocabulary.resolve(),
        g2p_cache=args.g2p_cache.resolve(),
        base_dictionary=args.base_dictionary.resolve(),
        acoustic_model=args.acoustic_model.resolve(),
        dictionary_registry=args.dictionary_registry.resolve(),
        output_csv_gz=args.output_csv_gz.resolve(),
        top_csv=args.top_csv.resolve(),
        manifest_path=args.manifest.resolve(),
        top_n=args.top_n,
        progress_every=args.progress_every,
    )
    counts = manifest["counts_by_status_types"]
    print(
        "[OK] 공통발음 규칙 일관성 감사: "
        f"matches={counts.get('matches_surface_rule', 0):,}; "
        f"rule_sensitive_mismatch={counts.get('mismatch_rule_sensitive', 0):,}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

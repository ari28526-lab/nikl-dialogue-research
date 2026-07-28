"""2020–2025 공통 surface G2P cache와 MFA 파생사전을 만든다.

이 스크립트의 목적은 MFA 효율화다. 기본 ``korean_mfa`` 사전 행은 그대로
보존하고, 실제 코퍼스에 나타났지만 기본사전에 없는 표면 어절만 같은
``korean_mfa`` G2P의 1-best 결과로 한 번 채운다. 우리말샘 발음이나 형태소
조건 발음은 이 생산 사전에 넣지 않는다.

긴 G2P 계산은 PowerShell runner가 shard별로 수행한다. 이 파일은

1. ``prepare``: OOV inventory와 재개 가능한 입력 shard 생성
2. ``finalize``: 모든 shard의 완전성·phone inventory를 검사하고 사전 생성

만 담당한다. 기존 파일은 덮어쓰지 않고, 같은 입력 계약의 완료 산출물만
검증 후 재사용한다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_mfa_lexicon.v2"
MFA_DICTIONARY_PARSE_CONTRACT = "mfa_3_4_optional_probability_columns_v1"
JAMO_LS = "\u11b3"
JAMO_L = "\u11af"
JAMO_S = "\u11ba"
JAMO_LS_REWRITE_RULE = "NFKD U+11B3 -> U+11AF U+11BA -> NFKC"
SPECIAL_REVIEW_FIELDS = (
    "token",
    "model_input",
    "pron_phones_mfa",
    "decision",
    "notes",
)
# MFA 3.4.0 ``utils.parse_dictionary_file``의 실제 판별식과 동일하게
# 선두 숫자 열을 최대 4개까지 확률/보정값으로 해석한다. 세 번째·네 번째
# 보정값은 1보다 클 수 있으므로 0–1 범위로 제한하면 안 된다.
MFA_PROBABILITY_RE = re.compile(r"\b(\d+\.\d+|1)\b")
YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
OOV_FIELDS = (
    "token",
    "total_occurrences",
    "n_years_present",
    *(f"count_{year}" for year in YEARS),
)


def clean(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def parse_mfa_dictionary_line(
    line: str, *, path: Path, line_number: int
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """MFA 3.4의 선택적 확률 4열을 phone과 분리한다."""

    parts = line.strip().split()
    if not parts:
        raise RuntimeError(f"빈 MFA 사전 행 {line_number}: {path}")
    if len(parts) < 2:
        raise RuntimeError(f"잘못된 MFA 사전 행 {line_number}: {path}")
    word = clean(parts.pop(0))
    probability_columns: list[str] = []
    for _ in range(4):
        if not parts or not MFA_PROBABILITY_RE.match(parts[0]):
            break
        probability_columns.append(parts.pop(0))
    if not parts:
        raise RuntimeError(f"phone이 없는 MFA 사전 행 {line_number}: {path}")
    return word, tuple(parts), tuple(probability_columns)


def read_mfa_dictionary(
    path: Path,
) -> tuple[list[str], dict[str, set[tuple[str, ...]]]]:
    lines: list[str] = []
    pronunciations: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            word, phones, _ = parse_mfa_dictionary_line(
                line, path=path, line_number=line_number
            )
            lines.append(line.rstrip("\r\n"))
            pronunciations[word].add(phones)
    if not lines:
        raise RuntimeError(f"MFA 사전이 비어 있음: {path}")
    return lines, dict(pronunciations)


def read_generated_dictionary(path: Path) -> dict[str, tuple[str, ...]]:
    _, pronunciations = read_mfa_dictionary(path)
    duplicates = {
        word: values for word, values in pronunciations.items() if len(values) != 1
    }
    if duplicates:
        raise RuntimeError(
            "G2P shard에 단어당 1개가 아닌 발음이 있음: "
            + ", ".join(sorted(duplicates)[:5])
        )
    return {word: next(iter(values)) for word, values in pronunciations.items()}


def acoustic_phone_inventory(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith("/meta.json")]
        if len(names) != 1:
            raise RuntimeError(f"acoustic meta.json 수가 1이 아님: {names}")
        meta = json.loads(archive.read(names[0]).decode("utf-8"))
    phones = {str(phone) for phone in meta.get("phones", [])}
    if not phones:
        raise RuntimeError("acoustic phone inventory가 비어 있음")
    phones.update({"sil", "spn"})
    return phones


def g2p_grapheme_contract(path: Path) -> tuple[set[str], dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        names = [
            name for name in archive.namelist() if name.endswith("/meta.json")
        ]
        if len(names) != 1:
            raise RuntimeError(f"G2P meta.json 수가 1이 아님: {names}")
        meta = json.loads(archive.read(names[0]).decode("utf-8"))
    graphemes = {str(value) for value in meta.get("graphemes", [])}
    if not graphemes:
        raise RuntimeError("G2P grapheme inventory가 비어 있음")
    phones = {str(value) for value in meta.get("phones", [])}
    if not phones:
        raise RuntimeError("G2P phone inventory가 비어 있음")
    return graphemes, {
        "architecture": str(meta.get("architecture", "unknown")),
        "version": str(meta.get("version", "unknown")),
        "unicode_decomposition": bool(
            meta.get("unicode_decomposition", False)
        ),
        "grapheme_count": len(graphemes),
        "grapheme_sorted_sha256": hashlib.sha256(
            ("\n".join(sorted(graphemes)) + "\n").encode("utf-8")
        ).hexdigest(),
        "phone_count": len(phones),
        "phone_sorted_sha256": hashlib.sha256(
            ("\n".join(sorted(phones)) + "\n").encode("utf-8")
        ).hexdigest(),
    }


def audit_g2p_grapheme_coverage(
    *,
    input_directory: Path,
    g2p_model: Path,
    input_normalization: str = "model",
) -> tuple[dict, list[dict[str, object]]]:
    graphemes, model_contract = g2p_grapheme_contract(g2p_model)
    if input_normalization == "model":
        normalization = (
            "NFKD"
            if bool(model_contract["unicode_decomposition"])
            else "none"
        )
    elif input_normalization in {"none", "NFKC", "NFKD"}:
        normalization = input_normalization
    else:
        raise ValueError(
            f"지원하지 않는 G2P 입력 정규화: {input_normalization}"
        )
    rows: list[dict[str, object]] = []
    missing_character_counts: Counter[str] = Counter()
    total_words = 0
    shard_paths = sorted(input_directory.glob("oov_*.txt"))
    if not shard_paths:
        raise RuntimeError(f"G2P input shard가 없음: {input_directory}")
    for shard_path in shard_paths:
        with shard_path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                token = clean(line)
                if not token:
                    continue
                total_words += 1
                model_input = (
                    unicodedata.normalize(normalization, token)
                    if normalization != "none"
                    else token
                )
                missing = sorted(set(model_input) - graphemes)
                if not missing:
                    continue
                missing_character_counts.update(missing)
                rows.append(
                    {
                        "shard": shard_path.stem,
                        "line_number": line_number,
                        "token": token,
                        "missing_graphemes": "".join(missing),
                        "missing_codepoints": " ".join(
                            f"U+{ord(value):04X}" for value in missing
                        ),
                    }
                )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if not rows else "unsupported_graphemes_found",
        "kind": "g2p_grapheme_coverage_audit",
        "recorded_at": now_iso(),
        "input_directory": str(input_directory.resolve()),
        "g2p_model": file_fingerprint(g2p_model, with_sha256=True),
        "g2p_model_contract": model_contract,
        "input_normalization": normalization,
        "counts": {
            "input_shards": len(shard_paths),
            "input_words": total_words,
            "unsupported_words": len(rows),
            "unsupported_unique_graphemes": len(missing_character_counts),
        },
        "unsupported_grapheme_counts": [
            {"grapheme": value, "words": count}
            for value, count in sorted(
                missing_character_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    return report, rows


def analyze_g2p_word(
    token: str,
    *,
    graphemes: set[str],
    unicode_decomposition: bool,
) -> tuple[str, set[str]]:
    model_sequence = (
        unicodedata.normalize("NFKD", token)
        if unicode_decomposition
        else token
    )
    return model_sequence, set(model_sequence) - graphemes


def rewrite_jamo_ls_for_model(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token)
    if JAMO_LS not in decomposed:
        raise ValueError(f"U+11B3이 없는 어절은 rewrite 대상이 아님: {token}")
    rewritten = decomposed.replace(JAMO_LS, JAMO_L + JAMO_S)
    return unicodedata.normalize("NFKC", rewritten)


def write_grapheme_audit(
    *,
    report: dict,
    rows: list[dict[str, object]],
    output_json: Path,
    output_csv: Path,
) -> None:
    atomic_write_json(output_json, report)
    with atomic_text_writer(
        output_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "shard",
                "line_number",
                "token",
                "missing_graphemes",
                "missing_codepoints",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def phone_inventory_contract(phones: set[str]) -> dict[str, object]:
    canonical = "\n".join(sorted(phones)) + "\n"
    return {
        "count": len(phones),
        "sorted_phone_sha256": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
        "phones": sorted(phones),
    }


def phones_outside_inventory(
    pronunciations: dict[str, set[tuple[str, ...]]],
    inventory: set[str],
) -> set[str]:
    return {
        phone
        for values in pronunciations.values()
        for phones in values
        for phone in phones
        if phone not in inventory
    }


def read_vocabulary(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(OOV_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"vocabulary 필수 열 누락: {sorted(missing)}")
        for row_number, row in enumerate(reader, 2):
            token = clean(row.get("token"))
            if not token or token in seen:
                raise RuntimeError(
                    f"vocabulary token 비어 있음 또는 중복: {row_number} {token!r}"
                )
            seen.add(token)
            normalized = {"token": token}
            for field in OOV_FIELDS[1:]:
                try:
                    value = int(clean(row.get(field)))
                except ValueError as exc:
                    raise RuntimeError(
                        f"vocabulary 정수 열 오류: {row_number} {field}"
                    ) from exc
                if value < 0:
                    raise RuntimeError(
                        f"vocabulary 음수 값: {row_number} {field}={value}"
                    )
                normalized[field] = str(value)
            year_counts = sum(
                int(normalized[f"count_{year}"]) > 0 for year in YEARS
            )
            if year_counts != int(normalized["n_years_present"]):
                raise RuntimeError(
                    f"n_years_present 불일치: {token} "
                    f"{normalized['n_years_present']} != {year_counts}"
                )
            if sum(
                int(normalized[f"count_{year}"]) for year in YEARS
            ) != int(normalized["total_occurrences"]):
                raise RuntimeError(f"total_occurrences 불일치: {token}")
            rows.append(normalized)
    if not rows:
        raise RuntimeError("vocabulary가 비어 있음")
    return rows


def validate_vocabulary_manifest(
    vocabulary: Path, manifest_path: Path, row_count: int
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("status") != "success":
        raise RuntimeError("vocabulary manifest가 success가 아님")
    expected = manifest.get("output", {})
    if int(expected.get("bytes", -1)) != vocabulary.stat().st_size:
        raise RuntimeError("vocabulary bytes가 manifest와 다름")
    if str(expected.get("sha256", "")).lower() != sha256_file(vocabulary):
        raise RuntimeError("vocabulary SHA256이 manifest와 다름")
    if int(manifest.get("counts", {}).get("unique_tokens", -1)) != row_count:
        raise RuntimeError("vocabulary unique token 수가 manifest와 다름")
    source = manifest.get("source", {})
    search_master_root = Path(source.get("search_master_root", ""))
    build_meta = source.get("build_meta", {})
    if not search_master_root.is_dir():
        raise RuntimeError("vocabulary search_master_root 원천 없음")
    if not build_meta:
        raise RuntimeError("vocabulary build_meta fingerprint 누락")
    verify_fingerprint(build_meta)
    return manifest


def write_csv(path: Path, fields: tuple[str, ...], rows) -> int:
    count = 0
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def canonical_identity(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalized_source_contract(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8-sig")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return {
        "path": str(path.resolve()),
        "normalization": "UTF-8 text with LF newlines",
        "lines": normalized.count("\n")
        + (0 if normalized.endswith("\n") else 1),
        "normalized_utf8_sha256": hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest(),
    }


def verify_fingerprint(record: dict) -> None:
    path = Path(record["path"])
    if not path.is_file():
        raise RuntimeError(f"manifest 파일 없음: {path}")
    actual = file_fingerprint(path, with_sha256=True)
    for key in ("bytes", "sha256"):
        if str(actual[key]).lower() != str(record[key]).lower():
            raise RuntimeError(f"manifest fingerprint 불일치: {path} {key}")


def prepare_paths(release_root: Path) -> dict[str, Path]:
    return {
        "manifest": release_root / "00_contract" / "prepare_manifest.json",
        "oov_inventory": release_root / "01_g2p" / "oov_inventory.csv",
        "input_shards": release_root / "01_g2p" / "input_shards",
        "output_shards": release_root / "01_g2p" / "output_shards",
        "logs": release_root / "logs",
        "state": release_root / "_state",
        "work": release_root / "work",
        "grapheme_audit": release_root
        / "00_contract"
        / "grapheme_coverage.csv",
        "special_mapping": release_root
        / "01_g2p"
        / "jamo_ls_mapping.csv",
        "special_original_input": release_root
        / "01_g2p"
        / "jamo_ls_original.txt",
        "special_model_input": release_root
        / "01_g2p"
        / "jamo_ls_model_input.txt",
        "special_raw_output": release_root
        / "01_g2p"
        / "output_shards"
        / "jamo_ls_raw.dict",
        "special_restored_output": release_root
        / "01_g2p"
        / "output_shards"
        / "jamo_ls_restored.dict",
        "special_candidate_report": release_root
        / "_state"
        / "jamo_ls_candidate_report.json",
        "special_review": release_root
        / "03_review"
        / "jamo_ls_researcher_review.csv",
        "final_dictionary": release_root
        / "02_mfa_lexicon"
        / "common_pron_mfa_r2.dict",
        "g2p_cache": release_root / "02_mfa_lexicon" / "g2p_cache.csv",
        "final_manifest": release_root
        / "00_contract"
        / "release_manifest.json",
    }


def verify_prepared(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "prepared"
    ):
        raise RuntimeError(f"prepare manifest 계약 불일치: {manifest_path}")
    required_inputs = {
        "vocabulary",
        "vocabulary_manifest",
        "base_dictionary",
        "g2p_model",
        "acoustic_model",
    }
    if set(manifest.get("inputs", {})) != required_inputs:
        raise RuntimeError(
            "prepare manifest 코드 포함 입력계약 불일치: "
            f"{sorted(manifest.get('inputs', {}))}"
        )
    for record in manifest["inputs"].values():
        verify_fingerprint(record)
    expected_code = manifest.get("code_contract", {}).get(
        "lexicon_builder", {}
    )
    actual_code = normalized_source_contract(Path(__file__).resolve())
    if (
        expected_code.get("normalized_utf8_sha256")
        != actual_code["normalized_utf8_sha256"]
    ):
        raise RuntimeError("prepare manifest 생성기 코드 계약 불일치")
    verify_fingerprint(manifest["outputs"]["oov_inventory"])
    verify_fingerprint(manifest["outputs"]["grapheme_audit"])
    for key in (
        "jamo_ls_mapping",
        "jamo_ls_original_input",
        "jamo_ls_model_input",
    ):
        verify_fingerprint(manifest["outputs"][key])
    for record in manifest["outputs"]["input_shards"]:
        verify_fingerprint(record)
    return manifest


def prepare(
    *,
    vocabulary: Path,
    vocabulary_manifest: Path,
    base_dictionary: Path,
    g2p_model: Path,
    acoustic_model: Path,
    release_root: Path,
    shard_size: int,
) -> dict:
    if shard_size < 100:
        raise ValueError("shard_size는 100 이상이어야 함")
    paths = prepare_paths(release_root)
    if paths["manifest"].exists():
        return verify_prepared(paths["manifest"])
    if paths["final_manifest"].exists():
        raise FileExistsError(
            f"완료 release를 prepare로 변경할 수 없음: {paths['final_manifest']}"
        )
    for key in ("oov_inventory", "final_dictionary", "g2p_cache"):
        if paths[key].exists():
            raise FileExistsError(f"manifest 없는 기존 산출물: {paths[key]}")
    if paths["input_shards"].exists() and any(paths["input_shards"].iterdir()):
        raise FileExistsError(
            f"manifest 없는 기존 input shards: {paths['input_shards']}"
        )

    rows = read_vocabulary(vocabulary)
    source_manifest = validate_vocabulary_manifest(
        vocabulary, vocabulary_manifest, len(rows)
    )
    base_lines, base_prons = read_mfa_dictionary(base_dictionary)
    phone_inventory = acoustic_phone_inventory(acoustic_model)
    base_unknown = phones_outside_inventory(base_prons, phone_inventory)
    if base_unknown:
        raise RuntimeError(
            "기본 사전에 acoustic inventory 밖 phone이 있음: "
            f"{sorted(base_unknown)}"
        )
    for required in (g2p_model, acoustic_model):
        if not required.is_file():
            raise RuntimeError(f"모델 파일 없음: {required}")

    oov_rows = [row for row in rows if row["token"] not in base_prons]
    # 긴 계산이 중단돼도 연구에서 재사용성이 큰 항목부터 안전하게 남는다.
    oov_rows.sort(
        key=lambda row: (
            -int(row["n_years_present"]),
            -int(row["total_occurrences"]),
            row["token"],
        )
    )
    for key in (
        "input_shards",
        "output_shards",
        "logs",
        "state",
        "work",
    ):
        paths[key].mkdir(parents=True, exist_ok=True)
    paths["manifest"].parent.mkdir(parents=True, exist_ok=True)

    write_csv(paths["oov_inventory"], OOV_FIELDS, oov_rows)
    graphemes, g2p_model_contract = g2p_grapheme_contract(g2p_model)
    standard_rows: list[dict[str, str]] = []
    special_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    model_inputs_seen: set[str] = set()
    for row in oov_rows:
        token = row["token"]
        _, missing = analyze_g2p_word(
            token,
            graphemes=graphemes,
            unicode_decomposition=bool(
                g2p_model_contract["unicode_decomposition"]
            ),
        )
        if not missing:
            standard_rows.append(row)
            continue
        audit_row = {
            "token": token,
            "missing_graphemes": "".join(sorted(missing)),
            "missing_codepoints": " ".join(
                f"U+{ord(value):04X}" for value in sorted(missing)
            ),
            "disposition": "blocked",
            "model_input": "",
            "rewrite_rule": "",
        }
        if missing == {JAMO_LS}:
            model_input = rewrite_jamo_ls_for_model(token)
            _, rewritten_missing = analyze_g2p_word(
                model_input,
                graphemes=graphemes,
                unicode_decomposition=bool(
                    g2p_model_contract["unicode_decomposition"]
                ),
            )
            if rewritten_missing:
                raise RuntimeError(
                    f"U+11B3 rewrite 뒤에도 미지원 grapheme: "
                    f"{token} {sorted(rewritten_missing)}"
                )
            if model_input in model_inputs_seen:
                raise RuntimeError(
                    f"U+11B3 model input 충돌: {token} -> {model_input}"
                )
            model_inputs_seen.add(model_input)
            special_rows.append(
                {
                    "token": token,
                    "model_input": model_input,
                    "rewrite_rule": JAMO_LS_REWRITE_RULE,
                }
            )
            audit_row.update(
                {
                    "disposition": "same_model_u11b3_full_decomposition",
                    "model_input": model_input,
                    "rewrite_rule": JAMO_LS_REWRITE_RULE,
                }
            )
        audit_rows.append(audit_row)
    unexpected = [
        row
        for row in audit_rows
        if row["disposition"] == "blocked"
    ]
    write_csv(
        paths["grapheme_audit"],
        (
            "token",
            "missing_graphemes",
            "missing_codepoints",
            "disposition",
            "model_input",
            "rewrite_rule",
        ),
        audit_rows,
    )
    if unexpected:
        raise RuntimeError(
            "U+11B3 외 미지원 G2P grapheme 발견: "
            + ", ".join(row["token"] for row in unexpected[:5])
        )
    write_csv(
        paths["special_mapping"],
        ("token", "model_input", "rewrite_rule"),
        special_rows,
    )
    with atomic_text_writer(
        paths["special_original_input"], encoding="utf-8", newline="\n"
    ) as (stream, _):
        for row in special_rows:
            stream.write(f"{row['token']}\n")
    with atomic_text_writer(
        paths["special_model_input"], encoding="utf-8", newline="\n"
    ) as (stream, _):
        for row in special_rows:
            stream.write(f"{row['model_input']}\n")
    shard_records: list[dict] = []
    shard_count = math.ceil(len(standard_rows) / shard_size)
    for index in range(shard_count):
        shard_rows = standard_rows[
            index * shard_size : (index + 1) * shard_size
        ]
        shard_path = paths["input_shards"] / f"oov_{index + 1:05d}.txt"
        with atomic_text_writer(
            shard_path, encoding="utf-8", newline="\n"
        ) as (stream, _):
            for row in shard_rows:
                stream.write(f"{row['token']}\n")
        record = file_fingerprint(shard_path, with_sha256=True)
        record.update(
            {
                "shard_index": index + 1,
                "row_count": len(shard_rows),
                "expected_output_name": f"oov_{index + 1:05d}.dict",
            }
        )
        shard_records.append(record)

    input_records = {
        "vocabulary": file_fingerprint(vocabulary, with_sha256=True),
        "vocabulary_manifest": file_fingerprint(
            vocabulary_manifest, with_sha256=True
        ),
        "base_dictionary": file_fingerprint(
            base_dictionary, with_sha256=True
        ),
        "g2p_model": file_fingerprint(g2p_model, with_sha256=True),
        "acoustic_model": file_fingerprint(
            acoustic_model, with_sha256=True
        ),
    }
    code_contract = {
        "lexicon_builder": normalized_source_contract(
            Path(__file__).resolve()
        )
    }
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "policy": "base_dictionary_plus_same_g2p_1best_no_attested_variants",
        "inputs": {
            name: {
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            }
            for name, record in input_records.items()
        },
        "shard_size": shard_size,
        "jamo_ls_rewrite_rule": JAMO_LS_REWRITE_RULE,
        "builder_code_sha256": code_contract[
            "lexicon_builder"
        ]["normalized_utf8_sha256"],
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "recorded_at": now_iso(),
        "release_id": release_root.name,
        "release_contract_id": canonical_identity(identity_payload),
        "purpose": "MFA efficiency through one reusable surface-word G2P cache",
        "phone_policy": (
            "preserve base dictionary rows; add only same korean_mfa G2P "
            "1-best strict-grapheme OOV; no Urimalsaem variants"
        ),
        "g2p_contract": {
            "num_pronunciations": 1,
            "strict_graphemes": True,
            "input_unit": "unique_surface_eojeol",
            "model_contract": g2p_model_contract,
            "unsupported_grapheme_policy": (
                "only U+11B3 is rewritten to U+11AF+U+11BA for the same "
                "frozen Jamo rewriter; every other unsupported grapheme "
                "blocks prepare"
            ),
            "surface_key_restoration_required": True,
        },
        "phone_inventory_contract": phone_inventory_contract(
            phone_inventory
        ),
        "inputs": input_records,
        "code_contract": code_contract,
        "source_vocabulary_manifest_status": source_manifest["status"],
        "source_vocabulary_contract": {
            "search_master_root": source_manifest.get("source", {}).get(
                "search_master_root", "unknown"
            ),
            "build_meta_sha256": source_manifest.get("source", {})
            .get("build_meta", {})
            .get("sha256", "unknown"),
            "vocabulary_sha256": input_records["vocabulary"]["sha256"],
        },
        "counts": {
            "vocabulary_words": len(rows),
            "base_dictionary_words": len(base_prons),
            "base_dictionary_rows": len(base_lines),
            "observed_words_in_base_dictionary": len(rows) - len(oov_rows),
            "observed_oov_words": len(oov_rows),
            "g2p_standard_words": len(standard_rows),
            "g2p_jamo_ls_rewrite_words": len(special_rows),
            "g2p_unsupported_other_words": 0,
            "shards": shard_count,
            "shard_size": shard_size,
        },
        "outputs": {
            "oov_inventory": file_fingerprint(
                paths["oov_inventory"], with_sha256=True
            ),
            "grapheme_audit": file_fingerprint(
                paths["grapheme_audit"], with_sha256=True
            ),
            "jamo_ls_mapping": file_fingerprint(
                paths["special_mapping"], with_sha256=True
            ),
            "jamo_ls_original_input": file_fingerprint(
                paths["special_original_input"], with_sha256=True
            ),
            "jamo_ls_model_input": file_fingerprint(
                paths["special_model_input"], with_sha256=True
            ),
            "input_shards": shard_records,
            "output_shards_directory": str(paths["output_shards"].resolve()),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(paths["manifest"], manifest)
    return manifest


def read_oov_inventory(path: Path) -> tuple[list[dict[str, str]], dict[str, dict]]:
    rows = read_vocabulary(path)
    return rows, {row["token"]: row for row in rows}


def verify_final(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "success"
    ):
        raise RuntimeError(f"release manifest 계약 불일치: {manifest_path}")
    verify_fingerprint(manifest["outputs"]["dictionary"])
    verify_fingerprint(manifest["outputs"]["g2p_cache"])
    return manifest


def verify_g2p_shard(
    *,
    input_shard: Path,
    output_shard: Path,
    acoustic_model: Path,
) -> dict:
    input_words = [
        clean(line)
        for line in input_shard.read_text(encoding="utf-8-sig").splitlines()
        if clean(line)
    ]
    if not input_words or len(input_words) != len(set(input_words)):
        raise RuntimeError(
            f"G2P input shard가 비었거나 중복됨: {input_shard}"
        )
    generated = read_generated_dictionary(output_shard)
    missing = set(input_words) - set(generated)
    extras = set(generated) - set(input_words)
    if missing or extras:
        raise RuntimeError(
            f"G2P shard coverage 불일치: missing={len(missing)} "
            f"extras={len(extras)}"
        )
    inventory = acoustic_phone_inventory(acoustic_model)
    unknown = {
        phone
        for phones in generated.values()
        for phone in phones
        if phone not in inventory
    }
    spn_words = {
        word for word, phones in generated.items() if "spn" in phones
    }
    if unknown:
        raise RuntimeError(
            f"G2P shard acoustic inventory 밖 phone: {sorted(unknown)}"
        )
    if spn_words:
        raise RuntimeError(
            f"G2P shard spn 포함: {len(spn_words)}"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "kind": "common_pron_g2p_shard_verification",
        "recorded_at": now_iso(),
        "counts": {
            "input_words": len(input_words),
            "output_words": len(generated),
            "missing": 0,
            "extras": 0,
            "spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
        },
        "inputs": {
            "input_shard": file_fingerprint(
                input_shard, with_sha256=True
            ),
            "output_shard": file_fingerprint(
                output_shard, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }


def read_special_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"token", "model_input", "rewrite_rule"}
    if rows and not required.issubset(rows[0]):
        raise RuntimeError("Jamo ㄽ mapping 필수 열 누락")
    tokens = [clean(row.get("token")) for row in rows]
    model_inputs = [clean(row.get("model_input")) for row in rows]
    if (
        len(tokens) != len(set(tokens))
        or len(model_inputs) != len(set(model_inputs))
        or any(not value for value in (*tokens, *model_inputs))
    ):
        raise RuntimeError("Jamo ㄽ mapping 키가 비었거나 중복됨")
    for row in rows:
        if clean(row.get("rewrite_rule")) != JAMO_LS_REWRITE_RULE:
            raise RuntimeError("Jamo ㄽ mapping rewrite rule 불일치")
        if rewrite_jamo_ls_for_model(clean(row["token"])) != clean(
            row["model_input"]
        ):
            raise RuntimeError("Jamo ㄽ mapping 재계산 불일치")
    return [
        {
            "token": clean(row["token"]),
            "model_input": clean(row["model_input"]),
            "rewrite_rule": clean(row["rewrite_rule"]),
        }
        for row in rows
    ]


def read_special_review(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(SPECIAL_REVIEW_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"Jamo ㄽ 연구자 검토표 필수 열 누락: {sorted(missing)}"
            )
        rows = []
        for row in reader:
            # IPA modifier letters such as ʰ and ʲ are meaningful phone
            # symbols. NFKC would silently collapse them to ASCII h/j, so
            # normalization is limited to orthographic key columns.
            rows.append(
                {
                    "token": clean(row.get("token")),
                    "model_input": clean(row.get("model_input")),
                    "pron_phones_mfa": str(
                        row.get("pron_phones_mfa") or ""
                    ).strip(),
                    "decision": str(
                        row.get("decision") or ""
                    ).strip(),
                    "notes": str(row.get("notes") or "").strip(),
                }
            )
        return rows


def restore_jamo_ls_candidates(
    *,
    release_root: Path,
    acoustic_model: Path,
) -> dict:
    paths = prepare_paths(release_root)
    prepared = verify_prepared(paths["manifest"])
    mapping = read_special_mapping(paths["special_mapping"])
    raw = (
        read_generated_dictionary(paths["special_raw_output"])
        if mapping
        else {}
    )
    expected_model_inputs = {row["model_input"] for row in mapping}
    missing = expected_model_inputs - set(raw)
    extras = set(raw) - expected_model_inputs
    if missing or extras:
        raise RuntimeError(
            f"Jamo ㄽ raw G2P coverage 불일치: missing={len(missing)} "
            f"extras={len(extras)}"
        )
    inventory = acoustic_phone_inventory(acoustic_model)
    unknown = {
        phone
        for phones in raw.values()
        for phone in phones
        if phone not in inventory
    }
    spn_words = {
        word for word, phones in raw.items() if "spn" in phones
    }
    if unknown or spn_words:
        raise RuntimeError(
            f"Jamo ㄽ 후보 phone gate 실패: unknown={sorted(unknown)}, "
            f"spn={sorted(spn_words)}"
        )
    candidates = [
        {
            "token": row["token"],
            "model_input": row["model_input"],
            "pron_phones_mfa": " ".join(raw[row["model_input"]]),
            "decision": "pending",
            "notes": "",
        }
        for row in mapping
    ]
    if paths["special_restored_output"].exists():
        existing = read_generated_dictionary(
            paths["special_restored_output"]
        )
        expected = {
            row["token"]: tuple(row["pron_phones_mfa"].split())
            for row in candidates
        }
        if existing != expected:
            raise RuntimeError("기존 Jamo ㄽ 표층키 복원 출력 불일치")
    else:
        with atomic_text_writer(
            paths["special_restored_output"],
            encoding="utf-8",
            newline="\n",
        ) as (stream, _):
            for row in candidates:
                stream.write(
                    f"{row['token']}\t{row['pron_phones_mfa']}\n"
                )
    paths["special_review"].parent.mkdir(parents=True, exist_ok=True)
    if paths["special_review"].exists():
        existing_review = read_special_review(paths["special_review"])
        candidate_contract = [
            (
                row["token"],
                row["model_input"],
                row["pron_phones_mfa"],
            )
            for row in candidates
        ]
        existing_contract = [
            (
                row["token"],
                row["model_input"],
                row["pron_phones_mfa"],
            )
            for row in existing_review
        ]
        if existing_contract != candidate_contract:
            raise RuntimeError("기존 Jamo ㄽ 연구자 검토표 후보가 달라짐")
    else:
        write_csv(
            paths["special_review"],
            SPECIAL_REVIEW_FIELDS,
            candidates,
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "candidate_ready_researcher_review_required",
        "kind": "jamo_ls_same_model_candidate",
        "recorded_at": now_iso(),
        "release_id": release_root.name,
        "rewrite_rule": JAMO_LS_REWRITE_RULE,
        "counts": {
            "mapping_words": len(mapping),
            "raw_output_words": len(raw),
            "surface_keys_restored": len(candidates),
            "missing": 0,
            "extras": 0,
            "spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
        },
        "inputs": {
            "prepare_manifest": file_fingerprint(
                paths["manifest"], with_sha256=True
            ),
            "mapping": file_fingerprint(
                paths["special_mapping"], with_sha256=True
            ),
            "raw_output": file_fingerprint(
                paths["special_raw_output"], with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "outputs": {
            "restored_output": file_fingerprint(
                paths["special_restored_output"], with_sha256=True
            ),
            "researcher_review": file_fingerprint(
                paths["special_review"], with_sha256=True
            ),
        },
        "prepared_release_contract_id": prepared["release_contract_id"],
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(paths["special_candidate_report"], report)
    return report


def finalize(*, release_root: Path) -> dict:
    paths = prepare_paths(release_root)
    if paths["final_manifest"].exists():
        return verify_final(paths["final_manifest"])
    prepared = verify_prepared(paths["manifest"])
    for path in (paths["final_dictionary"], paths["g2p_cache"]):
        if path.exists():
            raise FileExistsError(f"manifest 없는 기존 final 산출물: {path}")

    oov_rows, oov_by_token = read_oov_inventory(paths["oov_inventory"])
    expected_words = set(oov_by_token)
    generated: dict[str, tuple[str, ...]] = {}
    output_records: list[dict] = []
    for shard in prepared["outputs"]["input_shards"]:
        output_path = (
            paths["output_shards"] / shard["expected_output_name"]
        )
        if not output_path.is_file():
            raise RuntimeError(f"G2P output shard 누락: {output_path}")
        mapping = read_generated_dictionary(output_path)
        duplicates = set(generated) & set(mapping)
        if duplicates:
            raise RuntimeError(
                "G2P shard 사이 중복: " + ", ".join(sorted(duplicates)[:5])
            )
        generated.update(mapping)
        record = file_fingerprint(output_path, with_sha256=True)
        record.update(
            {
                "shard_index": shard["shard_index"],
                "row_count": len(mapping),
            }
        )
        output_records.append(record)
    special_mapping = read_special_mapping(paths["special_mapping"])
    special_generated = (
        read_generated_dictionary(paths["special_restored_output"])
        if special_mapping
        else {}
    )
    expected_special = {row["token"] for row in special_mapping}
    if set(special_generated) != expected_special:
        raise RuntimeError("Jamo ㄽ 표층키 복원 coverage 불일치")
    special_review = (
        read_special_review(paths["special_review"])
        if special_mapping
        else []
    )
    review_by_token = {row["token"]: row for row in special_review}
    if (
        len(review_by_token) != len(special_review)
        or set(review_by_token) != expected_special
    ):
        raise RuntimeError("Jamo ㄽ 연구자 검토표 token 집합 불일치")
    for row in special_mapping:
        token = row["token"]
        review = review_by_token[token]
        phones = " ".join(special_generated[token])
        if (
            review["decision"] != "approved"
            or review["model_input"] != row["model_input"]
            or review["pron_phones_mfa"] != phones
        ):
            raise RuntimeError(
                f"Jamo ㄽ 연구자 승인 미완료 또는 후보 불일치: {token}"
            )
    duplicates = set(generated) & set(special_generated)
    if duplicates:
        raise RuntimeError(
            "표준 shard와 Jamo ㄽ shard 중복: "
            + ", ".join(sorted(duplicates))
        )
    generated.update(special_generated)
    if special_mapping:
        output_records.append(
            {
                **file_fingerprint(
                    paths["special_restored_output"], with_sha256=True
                ),
                "kind": "jamo_ls_surface_key_restored",
                "row_count": len(special_generated),
            }
        )
    special_review_record = (
        file_fingerprint(paths["special_review"], with_sha256=True)
        if special_mapping
        else {"status": "not_applicable", "rows": 0}
    )
    missing = expected_words - set(generated)
    extras = set(generated) - expected_words
    if missing or extras:
        raise RuntimeError(
            f"G2P coverage 불일치: missing={len(missing)} "
            f"extras={len(extras)}; 예={sorted(missing)[:3]} "
            f"{sorted(extras)[:3]}"
        )

    base_dictionary = Path(prepared["inputs"]["base_dictionary"]["path"])
    acoustic_model = Path(prepared["inputs"]["acoustic_model"]["path"])
    base_lines, base_prons = read_mfa_dictionary(base_dictionary)
    phone_inventory = acoustic_phone_inventory(acoustic_model)
    base_unknown = phones_outside_inventory(base_prons, phone_inventory)
    if base_unknown:
        raise RuntimeError(
            "기본 사전에 acoustic inventory 밖 phone이 있음: "
            f"{sorted(base_unknown)}"
        )
    unknown = {
        phone
        for phones in generated.values()
        for phone in phones
        if phone not in phone_inventory
    }
    spn_words = {
        word for word, phones in generated.items() if "spn" in phones
    }
    if unknown:
        raise RuntimeError(
            f"acoustic phone inventory 밖 기호: {sorted(unknown)}"
        )
    if spn_words:
        raise RuntimeError(
            f"G2P 결과에 spn 포함: {len(spn_words)} "
            + ", ".join(sorted(spn_words)[:5])
        )

    paths["final_dictionary"].parent.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(
        paths["final_dictionary"], encoding="utf-8", newline="\n"
    ) as (stream, _):
        for line in base_lines:
            stream.write(f"{line}\n")
        for word in sorted(generated):
            stream.write(f"{word}\t{' '.join(generated[word])}\n")

    cache_fields = (*OOV_FIELDS, "pron_phones_mfa", "pron_source")
    cache_rows = (
        {
            **oov_by_token[word],
            "pron_phones_mfa": " ".join(generated[word]),
            "pron_source": (
                "korean_mfa_jamo_g2p_v3.2.0_1best_u11b3_decomposed"
                if word in expected_special
                else "korean_mfa_jamo_g2p_v3.2.0_1best_strict"
            ),
        }
        for word in sorted(generated)
    )
    cache_count = write_csv(paths["g2p_cache"], cache_fields, cache_rows)
    if cache_count != len(expected_words):
        raise RuntimeError("G2P cache 행 수 불일치")

    all_words = set(base_prons) | set(generated)
    observed_coverage_missing = expected_words - all_words
    if observed_coverage_missing:
        raise RuntimeError(
            f"최종 사전 coverage 누락: {sorted(observed_coverage_missing)[:5]}"
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "recorded_at": now_iso(),
        "release_id": release_root.name,
        "release_contract_id": prepared["release_contract_id"],
        "purpose": prepared["purpose"],
        "phone_policy": prepared["phone_policy"],
        "g2p_contract": prepared["g2p_contract"],
        "phone_inventory_contract": prepared[
            "phone_inventory_contract"
        ],
        "source_vocabulary_contract": prepared[
            "source_vocabulary_contract"
        ],
        "dictionary_contract": {
            "parser": MFA_DICTIONARY_PARSE_CONTRACT,
            "base_rows": "text preserved in original order",
            "added_rows": "one unweighted G2P pronunciation per observed OOV",
            "attested_dictionary_variants_added": 0,
            "changes_phone_standard": False,
            "jamo_ls_surface_key_restoration": True,
            "jamo_ls_rewrite_rule": JAMO_LS_REWRITE_RULE,
            "jamo_ls_researcher_review": special_review_record,
        },
        "inputs": prepared["inputs"],
        "counts": {
            **prepared["counts"],
            "g2p_output_words": len(generated),
            "g2p_jamo_ls_rewrite_words": len(expected_special),
            "g2p_missing": 0,
            "g2p_extras": 0,
            "g2p_spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
            "final_dictionary_words": len(all_words),
            "final_dictionary_rows": len(base_lines) + len(generated),
            "observed_oov_coverage_missing": 0,
        },
        "g2p_output_shards": output_records,
        "outputs": {
            "dictionary": file_fingerprint(
                paths["final_dictionary"], with_sha256=True
            ),
            "g2p_cache": file_fingerprint(
                paths["g2p_cache"], with_sha256=True
            ),
        },
        "required_before_mfa": {
            "frozen_latest_jamo_model_pin": (
                "must_be_reverified_by_adoption_contract"
            ),
            "baseline_2020_2021_difference_inventory": "pending",
            "jamo_ls_four_word_researcher_approval": "passed",
            "yearly_mfa_adoption_contract": "pending",
            "legacy_mismatch_zero_is_not_an_adoption_gate": True,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(paths["final_manifest"], manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--vocabulary", type=Path, required=True)
    prepare_parser.add_argument(
        "--vocabulary-manifest", type=Path, required=True
    )
    prepare_parser.add_argument(
        "--base-dictionary", type=Path, required=True
    )
    prepare_parser.add_argument("--g2p-model", type=Path, required=True)
    prepare_parser.add_argument(
        "--acoustic-model", type=Path, required=True
    )
    prepare_parser.add_argument("--release-root", type=Path, required=True)
    prepare_parser.add_argument("--shard-size", type=int, default=25000)

    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("--release-root", type=Path, required=True)

    restore_parser = sub.add_parser("restore-jamo-ls")
    restore_parser.add_argument("--release-root", type=Path, required=True)
    restore_parser.add_argument(
        "--acoustic-model", type=Path, required=True
    )

    verify_parser = sub.add_parser("verify-shard")
    verify_parser.add_argument("--input-shard", type=Path, required=True)
    verify_parser.add_argument("--output-shard", type=Path, required=True)
    verify_parser.add_argument(
        "--acoustic-model", type=Path, required=True
    )
    verify_parser.add_argument("--report", type=Path, required=True)

    audit_parser = sub.add_parser("audit-graphemes")
    audit_parser.add_argument(
        "--input-directory", type=Path, required=True
    )
    audit_parser.add_argument("--g2p-model", type=Path, required=True)
    audit_parser.add_argument(
        "--input-normalization",
        choices=("model", "none", "NFKC", "NFKD"),
        default="model",
    )
    audit_parser.add_argument("--output-json", type=Path, required=True)
    audit_parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "prepare":
        manifest = prepare(
            vocabulary=args.vocabulary.resolve(),
            vocabulary_manifest=args.vocabulary_manifest.resolve(),
            base_dictionary=args.base_dictionary.resolve(),
            g2p_model=args.g2p_model.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
            release_root=args.release_root.resolve(),
            shard_size=args.shard_size,
        )
        print(
            "[OK] common G2P 준비: "
            f"OOV={manifest['counts']['observed_oov_words']:,}, "
            f"shards={manifest['counts']['shards']:,}",
            flush=True,
        )
    elif args.command == "finalize":
        manifest = finalize(release_root=args.release_root.resolve())
        print(
            "[OK] common MFA 사전: "
            f"{manifest['counts']['final_dictionary_words']:,} words; "
            "2020/2021 동등성은 아직 pending",
            flush=True,
        )
    elif args.command == "restore-jamo-ls":
        manifest = restore_jamo_ls_candidates(
            release_root=args.release_root.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
        )
        print(
            "[PENDING] Jamo ㄽ 후보 생성: "
            f"{manifest['counts']['surface_keys_restored']:,} words; "
            "researcher review required",
            flush=True,
        )
    elif args.command == "verify-shard":
        manifest = verify_g2p_shard(
            input_shard=args.input_shard.resolve(),
            output_shard=args.output_shard.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
        )
        atomic_write_json(args.report.resolve(), manifest)
        print(
            "[OK] G2P shard: "
            f"{manifest['counts']['output_words']:,} words",
            flush=True,
        )
    else:
        report, rows = audit_g2p_grapheme_coverage(
            input_directory=args.input_directory.resolve(),
            g2p_model=args.g2p_model.resolve(),
            input_normalization=args.input_normalization,
        )
        write_grapheme_audit(
            report=report,
            rows=rows,
            output_json=args.output_json.resolve(),
            output_csv=args.output_csv.resolve(),
        )
        print(
            "[OK] G2P grapheme audit: "
            f"{report['counts']['unsupported_words']:,}/"
            f"{report['counts']['input_words']:,} unsupported words",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

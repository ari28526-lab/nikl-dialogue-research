"""2020–2025 공통 발음사전 A/B 파일럿을 준비·비교한다.

이 모듈은 네 개의 명시적 단계를 제공한다.

``registry``
    6개년 전체 vocabulary와 사전 원천을 exact word 기준으로 결합한다.
``sample``
    사전 발음이 철자와 다른 발화를 연도별·화자별로 층화하고 같은 화자의
    대조 발화를 붙여 정책 A/B에 byte-identical corpus를 만든다.
``lexicons``
    MFA G2P의 별도 출력으로 표본 한정 정책 A/B 사전을 만든다.
``compare``
    두 정책의 4-tier 결과를 발화별로 비교하되 자동 승자를 정하지 않는다.

원 JSON·WAV·동결 CSV·기존 MFA 결과는 읽기만 한다. 모든 쓰기는 지정된
공통 발음 release 아래에서만 수행하고 기존 산출물을 덮어쓰지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import wave
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)
from build_stratified_mfa_pilot import (  # noqa: E402
    audit_session_durations,
    inspect_wav,
    locate_wav,
    stable_key,
)
from realign_eojeol_build_corpus import form_to_lab  # noqa: E402
from realign_eojeol_merge_output import parse_mfa_textgrid  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE = (
    P("common_pron_home")
    / "releases"
    / "common_pron_pilot_full6y_20260728"
)
DEFAULT_VOCABULARY = (
    DEFAULT_RELEASE
    / "01_vocabulary"
    / "common_vocabulary_2020_2025.csv"
)
DEFAULT_ENRICHED = (
    P("reference_dictionary") / "01_NIKL_lexicon_full_v2.csv"
)
DEFAULT_LEGACY = P("lexicon_full")
DEFAULT_BASE_DICTIONARY = (
    Path.home()
    / "Documents"
    / "MFA"
    / "pretrained_models"
    / "dictionary"
    / "korean_mfa.dict"
)
DEFAULT_ACOUSTIC_MODEL = (
    Path.home()
    / "Documents"
    / "MFA"
    / "pretrained_models"
    / "acoustic"
    / "korean_mfa.zip"
)
DEFAULT_YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")
PLAIN_HANGUL_RE = re.compile(r"^[가-힣]+$")
SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MFA_PROBABILITY_RE = re.compile(r"\b(\d+\.\d+|1)\b")
REGISTRY_SCHEMA_VERSION = 2
MFA_DICTIONARY_PARSE_CONTRACT = (
    "mfa_3_4_optional_probability_columns_v1"
)
REGISTRY_FIELDS = [
    "candidate_id",
    "token",
    "pron_hangul",
    "pron_phones_mfa",
    "pron_source_type",
    "pron_source_field",
    "source_release",
    "urimal_id",
    "stdict_target_code",
    "pos_tag",
    "sense_no",
    "is_dictionary_attested",
    "is_machine_generated",
    "plain_hangul_pron",
    "pron_differs_from_token",
    "selection_status",
    "exclusion_reason",
    "total_occurrences",
    "n_years_present",
]
SELECTION_FIELDS = [
    "year",
    "sample_index",
    "sample_role",
    "pair_id",
    "speaker_id",
    "session_id",
    "utt_id",
    "form",
    "lab_text",
    "stress_tokens",
    "attested_pronunciations",
    "wav_duration_seconds",
    "csv_duration_seconds",
    "session_padding_seconds",
    "wav_csv_duration_residual_seconds",
    "source_wav",
    "source_search_master_csv",
    "source_morpheme_textgrid",
    "corpus_wav_relpath",
    "corpus_lab_relpath",
]
COMPARISON_FIELDS = [
    "year",
    "sample_role",
    "speaker_id",
    "session_id",
    "utt_id",
    "stress_tokens",
    "policy_b_changed_token",
    "comparison_group",
    "a_phone_count",
    "b_phone_count",
    "phone_edit_distance",
    "phone_sequence_identical",
    "word_labels_identical",
    "max_same_index_boundary_delta_seconds",
    "wav_a",
    "textgrid_a",
    "wav_b",
    "textgrid_b",
]
csv.field_size_limit(10_000_000)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean(value: str | None) -> str:
    return (value or "").strip()


def ensure_release_child(path: Path, release_root: Path) -> Path:
    resolved = path.resolve()
    root = release_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            f"공통 발음 release 경계 밖 쓰기 차단: {resolved} (root={root})"
        ) from exc
    return resolved


def candidate_id(parts: list[str]) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8"))
    return digest.hexdigest()


def write_csv_atomic(
    path: Path,
    fields: list[str],
    rows,
) -> int:
    count = 0
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def parse_mfa_dictionary_line(
    line: str, *, path: Path, line_number: int
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """MFA 3.4의 선택적 확률 4열을 phone과 분리한다."""

    parts = line.strip().split()
    if not parts:
        raise RuntimeError(f"빈 MFA 사전 행 {line_number}: {path}")
    if len(parts) < 2:
        raise RuntimeError(
            f"잘못된 MFA 사전 행 {line_number}: {path}"
        )
    word = unicodedata.normalize("NFKC", parts.pop(0))
    probability_columns: list[str] = []
    for _ in range(4):
        if not parts or not MFA_PROBABILITY_RE.match(parts[0]):
            break
        probability_columns.append(parts.pop(0))
    if not parts:
        raise RuntimeError(
            f"phone이 없는 MFA 사전 행 {line_number}: {path}"
        )
    return word, tuple(parts), tuple(probability_columns)


def read_dict(path: Path) -> dict[str, set[tuple[str, ...]]]:
    result: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            word, phones, _ = parse_mfa_dictionary_line(
                line, path=path, line_number=line_number
            )
            result[word].add(phones)
    return dict(result)


def acoustic_phone_inventory(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        meta_names = [
            name for name in archive.namelist() if name.endswith("/meta.json")
        ]
        if len(meta_names) != 1:
            raise RuntimeError(
                f"acoustic meta.json 수가 1이 아님: {meta_names}"
            )
        meta = json.loads(archive.read(meta_names[0]).decode("utf-8"))
    phones = {str(phone) for phone in meta.get("phones", [])}
    if not phones:
        raise RuntimeError("acoustic phone inventory가 비어 있음")
    phones.update({"spn", "sil"})
    return phones


def vocabulary_info(path: Path) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"token", "total_occurrences", "n_years_present"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"vocabulary 필수 열 누락: {sorted(missing)}")
        for row in reader:
            token = clean(row.get("token"))
            if not token or token in result:
                raise RuntimeError(f"비어 있거나 중복된 vocabulary token: {token!r}")
            result[token] = (
                int(row["total_occurrences"]),
                int(row["n_years_present"]),
            )
    if not result:
        raise RuntimeError("공통 vocabulary가 비어 있음")
    return result


def registry_rows(
    *,
    vocab: dict[str, tuple[int, int]],
    base: dict[str, set[tuple[str, ...]]],
    enriched_path: Path,
    legacy_path: Path,
    counters: Counter,
):
    seen: set[str] = set()
    for token in sorted(base):
        if token not in vocab:
            continue
        for phones in sorted(base[token]):
            cid = candidate_id(
                ["base_mfa_dictionary", token, " ".join(phones)]
            )
            if cid in seen:
                continue
            seen.add(cid)
            counters["base_candidates"] += 1
            yield {
                "candidate_id": cid,
                "token": token,
                "pron_hangul": "",
                "pron_phones_mfa": " ".join(phones),
                "pron_source_type": "base_mfa_dictionary",
                "pron_source_field": "korean_mfa.dict",
                "source_release": "korean_mfa",
                "is_dictionary_attested": "False",
                "is_machine_generated": "False",
                "plain_hangul_pron": "",
                "pron_differs_from_token": "",
                "selection_status": "policy_a_base",
                "exclusion_reason": "",
                "total_occurrences": vocab[token][0],
                "n_years_present": vocab[token][1],
            }

    with enriched_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        required = {
            "word",
            "pron_1",
            "pron_2",
            "urimal_id",
            "pos_tag",
            "sense_no",
            "stdict_target_code",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"enriched 필수 열 누락: {sorted(missing)}"
            )
        for source_row, row in enumerate(reader, 2):
            token = clean(row.get("word"))
            if token not in vocab:
                continue
            for field in ("pron_1", "pron_2"):
                pron = clean(row.get(field))
                if not pron:
                    continue
                plain = bool(PLAIN_HANGUL_RE.fullmatch(pron))
                differs = pron != token
                selection = (
                    "eligible_policy_b_pilot"
                    if plain and differs
                    else "registry_only"
                )
                exclusion = ""
                if not plain:
                    exclusion = "pron_not_plain_modern_hangul"
                elif not differs:
                    exclusion = "same_hangul_as_token"
                parts = [
                    "dictionary_attested",
                    token,
                    pron,
                    field,
                    clean(row.get("urimal_id")),
                    clean(row.get("pos_tag")),
                    clean(row.get("sense_no")),
                    str(source_row),
                ]
                cid = candidate_id(parts)
                if cid in seen:
                    counters["duplicate_candidate_ids"] += 1
                    continue
                seen.add(cid)
                counters["attested_candidates"] += 1
                counters[f"attested_{field}"] += 1
                counters[
                    "attested_plain_hangul"
                    if plain
                    else "attested_non_plain_hangul"
                ] += 1
                counters[
                    "attested_differs"
                    if differs
                    else "attested_same_as_token"
                ] += 1
                if selection == "eligible_policy_b_pilot":
                    counters["attested_eligible_policy_b_pilot"] += 1
                yield {
                    "candidate_id": cid,
                    "token": token,
                    "pron_hangul": pron,
                    "pron_phones_mfa": "",
                    "pron_source_type": "dictionary_attested",
                    "pron_source_field": field,
                    "source_release": "01_NIKL_lexicon_full_v2",
                    "urimal_id": clean(row.get("urimal_id")),
                    "stdict_target_code": clean(
                        row.get("stdict_target_code")
                    ),
                    "pos_tag": clean(row.get("pos_tag")),
                    "sense_no": clean(row.get("sense_no")),
                    "is_dictionary_attested": "True",
                    "is_machine_generated": "False",
                    "plain_hangul_pron": str(plain),
                    "pron_differs_from_token": str(differs),
                    "selection_status": selection,
                    "exclusion_reason": exclusion,
                    "total_occurrences": vocab[token][0],
                    "n_years_present": vocab[token][1],
                }

    with legacy_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        required = {
            "word",
            "pron_g2p",
            "urimal_id",
            "pos_tag",
            "sense_no",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(f"legacy 필수 열 누락: {sorted(missing)}")
        for source_row, row in enumerate(reader, 2):
            token = clean(row.get("word"))
            pron = clean(row.get("pron_g2p"))
            if token not in vocab or not pron:
                continue
            cid = candidate_id(
                [
                    "legacy_machine_g2p",
                    token,
                    pron,
                    clean(row.get("urimal_id")),
                    clean(row.get("pos_tag")),
                    clean(row.get("sense_no")),
                    str(source_row),
                ]
            )
            if cid in seen:
                counters["duplicate_candidate_ids"] += 1
                continue
            seen.add(cid)
            counters["legacy_g2p_candidates"] += 1
            yield {
                "candidate_id": cid,
                "token": token,
                "pron_hangul": pron,
                "pron_phones_mfa": "",
                "pron_source_type": "legacy_machine_g2p",
                "pron_source_field": "pron_g2p",
                "source_release": "01_NIKL_lexicon_full_legacy",
                "urimal_id": clean(row.get("urimal_id")),
                "stdict_target_code": "",
                "pos_tag": clean(row.get("pos_tag")),
                "sense_no": clean(row.get("sense_no")),
                "is_dictionary_attested": "False",
                "is_machine_generated": "True",
                "plain_hangul_pron": str(
                    bool(PLAIN_HANGUL_RE.fullmatch(pron))
                ),
                "pron_differs_from_token": str(pron != token),
                "selection_status": "audit_only",
                "exclusion_reason": "legacy_g2p_not_attested",
                "total_occurrences": vocab[token][0],
                "n_years_present": vocab[token][1],
            }


def build_registry(args: argparse.Namespace) -> int:
    release_root = args.release_root.resolve()
    output_dir = ensure_release_child(
        args.output_dir.resolve(), release_root
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = output_dir / "pronunciation_registry_seed.csv"
    oov_path = output_dir / "full_vocabulary_oov_words.txt"
    manifest_path = output_dir / "registry_seed_manifest.json"
    for path in (registry_path, oov_path, manifest_path):
        if path.exists():
            raise FileExistsError(f"기존 registry 산출물 덮어쓰기 금지: {path}")

    for path in (
        args.vocabulary,
        args.enriched,
        args.legacy,
        args.base_dictionary,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    started = time.perf_counter()
    vocab = vocabulary_info(args.vocabulary)
    base = read_dict(args.base_dictionary)
    counters: Counter = Counter()
    rows = registry_rows(
        vocab=vocab,
        base=base,
        enriched_path=args.enriched,
        legacy_path=args.legacy,
        counters=counters,
    )
    row_count = write_csv_atomic(registry_path, REGISTRY_FIELDS, rows)
    oov_words = sorted(set(vocab) - set(base))
    with atomic_text_writer(
        oov_path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write("\n".join(oov_words))
        stream.write("\n")
    manifest = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "kind": "common_pronunciation_registry_seed",
        "status": "success",
        "recorded_at": now_iso(),
        "scope": "full_frozen_vocabulary_exact_word_linkage",
        "policy": {
            "dictionary_match": "exact token == enriched/legacy word",
            "inflected_form_lemma_join": False,
            "legacy_pron_g2p": "audit_only_not_attested",
            "attested_pilot_eligibility": (
                "pron_1/2; plain modern Hangul; differs from token"
            ),
            "base_dictionary_parse_contract": (
                MFA_DICTIONARY_PARSE_CONTRACT
            ),
        },
        "inputs": {
            "vocabulary": file_fingerprint(
                args.vocabulary, with_sha256=True
            ),
            "enriched": file_fingerprint(args.enriched, with_sha256=True),
            "legacy": file_fingerprint(args.legacy, with_sha256=True),
            "base_dictionary": file_fingerprint(
                args.base_dictionary, with_sha256=True
            ),
        },
        "counts": {
            "vocabulary_tokens": len(vocab),
            "base_dictionary_words": len(base),
            "vocabulary_oov_words": len(oov_words),
            "registry_rows": row_count,
            **dict(counters),
        },
        "outputs": {
            "registry": file_fingerprint(registry_path, with_sha256=True),
            "oov_words": file_fingerprint(oov_path, with_sha256=True),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    print(
        f"[OK] registry seed={row_count:,}행, "
        f"eligible={counters['attested_eligible_policy_b_pilot']:,}, "
        f"full OOV={len(oov_words):,}",
        flush=True,
    )
    return 0


def load_stress_candidates(
    registry_path: Path,
) -> dict[str, set[str]]:
    by_token: dict[str, set[str]] = defaultdict(set)
    with registry_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            if row.get("selection_status") != "eligible_policy_b_pilot":
                continue
            token = clean(row.get("token"))
            pron = clean(row.get("pron_hangul"))
            if not token or not pron:
                continue
            by_token[token].add(pron)
    if not by_token:
        raise RuntimeError("A/B stress 후보 token 0개")
    return dict(by_token)


def read_session(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    required = {
        "utt_id",
        "year",
        "session_id",
        "speaker_id",
        "form",
        "pron_reference_form",
        "pron_reference_status",
        "dur",
    }
    missing = required - set(fields)
    if missing:
        raise RuntimeError(f"search CSV 필수 열 누락 {sorted(missing)}: {path}")
    return fields, rows


def row_asset(
    *,
    row: dict[str, str],
    year: str,
    session_id: str,
    search_path: Path,
    wav_year: Path,
    morph_year: Path,
    duration_audit: dict,
) -> dict[str, object] | None:
    utt_id = clean(row.get("utt_id"))
    speaker_id = clean(row.get("speaker_id"))
    if not utt_id or not speaker_id:
        return None
    lab_text = form_to_lab(row.get("pron_reference_form") or "")
    if not lab_text:
        return None
    if clean(row.get("pron_reference_status")) == "unresolved_symbol":
        return None
    wav_path = locate_wav(wav_year, session_id, utt_id)
    morph_path = morph_year / session_id / f"{utt_id}.TextGrid"
    if wav_path is None or not morph_path.is_file():
        return None
    duration_info = duration_audit.get("by_utt", {}).get(utt_id)
    if duration_info is None:
        return None
    residual = float(duration_info["residual"])
    if abs(residual) > 0.025:
        return None
    try:
        wav_info = inspect_wav(wav_path)
    except (OSError, EOFError, wave.Error, ValueError):
        return None
    return {
        **row,
        "year": year,
        "session_id": session_id,
        "speaker_id": speaker_id,
        "lab_text": lab_text,
        "source_wav": str(wav_path.resolve()),
        "source_search_master_csv": str(search_path.resolve()),
        "source_morpheme_textgrid": str(morph_path.resolve()),
        "wav_duration_seconds": round(float(wav_info["duration"]), 6),
        "csv_duration_seconds": round(
            float(duration_info["csv_duration"]), 6
        ),
        "session_padding_seconds": round(
            float(duration_audit["padding"]), 6
        ),
        "wav_csv_duration_residual_seconds": round(residual, 6),
    }


def select_year_pairs(
    *,
    year: str,
    search_year: Path,
    wav_year: Path,
    morph_year: Path,
    candidates: dict[str, set[str]],
    speakers: int,
    seed: str,
) -> list[dict[str, object]]:
    files = sorted(
        (
            path
            for path in search_year.glob("*.csv")
            if not path.name.startswith("_")
        ),
        key=lambda path: stable_key(f"{seed}:{year}:session", path.stem),
    )
    selected: list[dict[str, object]] = []
    used_speakers: set[str] = set()
    used_sessions: set[str] = set()
    for search_path in files:
        session_id = search_path.stem
        _, rows = read_session(search_path)
        stress_by_speaker: dict[str, list[tuple[dict[str, str], list[str]]]] = (
            defaultdict(list)
        )
        controls_by_speaker: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            speaker = clean(row.get("speaker_id"))
            lab_text = form_to_lab(row.get("pron_reference_form") or "")
            if not speaker or not lab_text:
                continue
            matched = sorted(
                {token for token in lab_text.split() if token in candidates}
            )
            if matched:
                stress_by_speaker[speaker].append((row, matched))
            else:
                controls_by_speaker[speaker].append(row)
        possible = [
            speaker
            for speaker in stress_by_speaker
            if speaker not in used_speakers and controls_by_speaker[speaker]
        ]
        possible.sort(
            key=lambda value: stable_key(
                f"{seed}:{year}:{session_id}:speaker", value
            )
        )
        if not possible:
            continue
        duration_audit = audit_session_durations(
            session_id=session_id,
            rows=rows,
            search_rows=rows,
            wav_year=wav_year,
        )
        if not duration_audit["valid"]:
            continue
        chosen_pair = None
        for speaker in possible:
            stress_options = sorted(
                stress_by_speaker[speaker],
                key=lambda item: stable_key(
                    f"{seed}:{year}:{speaker}:stress",
                    clean(item[0].get("utt_id")),
                ),
            )
            control_options = sorted(
                controls_by_speaker[speaker],
                key=lambda row: stable_key(
                    f"{seed}:{year}:{speaker}:control",
                    clean(row.get("utt_id")),
                ),
            )
            stress_asset = None
            stress_tokens: list[str] = []
            for row, matched in stress_options:
                asset = row_asset(
                    row=row,
                    year=year,
                    session_id=session_id,
                    search_path=search_path,
                    wav_year=wav_year,
                    morph_year=morph_year,
                    duration_audit=duration_audit,
                )
                if asset is not None:
                    stress_asset = asset
                    stress_tokens = matched
                    break
            if stress_asset is None:
                continue
            control_asset = None
            for row in control_options:
                asset = row_asset(
                    row=row,
                    year=year,
                    session_id=session_id,
                    search_path=search_path,
                    wav_year=wav_year,
                    morph_year=morph_year,
                    duration_audit=duration_audit,
                )
                if asset is not None:
                    control_asset = asset
                    break
            if control_asset is not None:
                chosen_pair = (
                    speaker,
                    stress_asset,
                    stress_tokens,
                    control_asset,
                )
                break
        if chosen_pair is None:
            continue
        speaker, stress_asset, stress_tokens, control_asset = chosen_pair
        pair_id = f"{year}_{len(used_speakers) + 1:02d}_{speaker}"
        stress_asset.update(
            {
                "sample_role": "stress",
                "pair_id": pair_id,
                "stress_tokens": " | ".join(stress_tokens),
                "attested_pronunciations": " | ".join(
                    f"{token}=>{','.join(sorted(candidates[token]))}"
                    for token in stress_tokens
                ),
            }
        )
        control_asset.update(
            {
                "sample_role": "control",
                "pair_id": pair_id,
                "stress_tokens": "",
                "attested_pronunciations": "",
            }
        )
        selected.extend([stress_asset, control_asset])
        used_speakers.add(speaker)
        used_sessions.add(session_id)
        if len(used_speakers) == speakers:
            break
    if len(used_speakers) != speakers:
        raise RuntimeError(
            f"{year} stress/control 표본 부족: "
            f"speakers={len(used_speakers)}/{speakers}, "
            f"sessions={len(used_sessions)}/{speakers}"
        )
    selected.sort(
        key=lambda row: (
            str(row["speaker_id"]),
            0 if row["sample_role"] == "stress" else 1,
        )
    )
    for index, row in enumerate(selected, 1):
        row["sample_index"] = index
    return selected


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.{os.getpid()}.partial")
    if temp.exists() or destination.exists():
        raise FileExistsError(
            f"기존 또는 partial 복사 대상 덮어쓰기 금지: {destination}"
        )
    shutil.copy2(source, temp)
    if temp.stat().st_size != source.stat().st_size:
        raise RuntimeError(f"복사 크기 불일치: {source} -> {temp}")
    os.replace(temp, destination)


def write_lab(path: Path, text: str) -> None:
    with atomic_text_writer(
        path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write(text.strip() + "\n")


def validate_existing_sample(
    shared_root: Path, policy_roots: list[Path], run_id: str
) -> bool:
    manifest = shared_root / "sample_manifest.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("status") != "success" or data.get("run_id") != run_id:
        return False
    for root in policy_roots:
        if not (root / "selection_manifest.csv").is_file():
            return False
        for row in data.get("paired_files", []):
            rel = Path(row["relative_path"])
            path = root / rel
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                return False
    return True


def build_sample(args: argparse.Namespace) -> int:
    release_root = args.release_root.resolve()
    if not SAFE_RUN_ID_RE.fullmatch(args.run_id):
        raise ValueError(f"안전하지 않은 run ID: {args.run_id}")
    shared_root = ensure_release_child(
        release_root / "05_ab_corpus" / args.run_id, release_root
    )
    result_root = ensure_release_child(
        release_root / "06_ab_results" / args.run_id, release_root
    )
    policy_roots = [result_root / "A", result_root / "B"]
    if validate_existing_sample(shared_root, policy_roots, args.run_id):
        print(f"[OK] 검증된 기존 A/B 표본 재사용: {shared_root}")
        return 0
    if shared_root.exists() or any(path.exists() for path in policy_roots):
        raise RuntimeError(
            "완료 manifest 없는 기존 A/B 표본 폴더를 덮어쓰지 않음: "
            f"{shared_root} / {result_root}"
        )
    candidates = load_stress_candidates(args.registry)
    started = time.perf_counter()
    all_rows: list[dict[str, object]] = []
    for year in args.years:
        selected = select_year_pairs(
            year=year,
            search_year=args.search_root / year,
            wav_year=args.wav_root / year,
            morph_year=args.morph_root / year,
            candidates=candidates,
            speakers=args.speakers_per_year,
            seed=args.seed,
        )
        all_rows.extend(selected)
        print(
            f"[sample] {year}: {len(selected)}발화, "
            f"{args.speakers_per_year}화자 stress/control",
            flush=True,
        )

    shared_root.mkdir(parents=True)
    for root in policy_roots:
        root.mkdir(parents=True)
    paired_files: list[dict[str, str | int]] = []
    sample_words: set[str] = set()
    stress_tokens: set[str] = set()
    selected_by_year: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in all_rows:
        year = str(row["year"])
        speaker = str(row["speaker_id"])
        utt_id = str(row["utt_id"])
        wav_rel = Path("corpus") / year / speaker / f"{utt_id}.wav"
        lab_rel = Path("corpus") / year / speaker / f"{utt_id}.lab"
        row["corpus_wav_relpath"] = wav_rel.as_posix()
        row["corpus_lab_relpath"] = lab_rel.as_posix()
        source_wav = Path(str(row["source_wav"]))
        for root in policy_roots:
            atomic_copy(source_wav, root / wav_rel)
            write_lab(root / lab_rel, str(row["lab_text"]))
        for rel in (wav_rel, lab_rel):
            a_path = policy_roots[0] / rel
            b_path = policy_roots[1] / rel
            a_sha = sha256_file(a_path)
            b_sha = sha256_file(b_path)
            if a_sha != b_sha:
                raise RuntimeError(f"A/B 입력 byte 불일치: {rel}")
            paired_files.append(
                {
                    "relative_path": rel.as_posix(),
                    "bytes": a_path.stat().st_size,
                    "sha256": a_sha,
                }
            )
        sample_words.update(str(row["lab_text"]).split())
        stress_tokens.update(
            part.strip()
            for part in str(row.get("stress_tokens") or "").split("|")
            if part.strip()
        )
        selected_by_year[year].append(row)

    manifest_rows = [
        {field: row.get(field, "") for field in SELECTION_FIELDS}
        for row in all_rows
    ]
    for root in [shared_root, *policy_roots]:
        write_csv_atomic(
            root / "selection_manifest.csv",
            SELECTION_FIELDS,
            manifest_rows,
        )
        for year, rows in selected_by_year.items():
            csv_path = root / "csv" / year / "search_master_selected.csv"
            fields = list(rows[0].keys())
            write_csv_atomic(csv_path, fields, rows)

    words_path = shared_root / "sample_words.txt"
    with atomic_text_writer(
        words_path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write("\n".join(sorted(sample_words)) + "\n")
    subset_rows: list[dict[str, str]] = []
    with args.registry.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        for row in csv.DictReader(stream):
            if (
                row.get("selection_status") == "eligible_policy_b_pilot"
                and clean(row.get("token")) in stress_tokens
            ):
                subset_rows.append(row)
    subset_path = shared_root / "stress_registry_subset.csv"
    write_csv_atomic(subset_path, REGISTRY_FIELDS, subset_rows)
    pron_forms = sorted(
        {
            row["pron_hangul"]
            for row in subset_rows
            if PLAIN_HANGUL_RE.fullmatch(row["pron_hangul"])
        }
    )
    pron_path = shared_root / "sample_attested_pron_forms.txt"
    with atomic_text_writer(
        pron_path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write("\n".join(pron_forms) + "\n")

    manifest = {
        "schema_version": 1,
        "kind": "common_pronunciation_ab_sample",
        "status": "success",
        "run_id": args.run_id,
        "recorded_at": now_iso(),
        "years": list(args.years),
        "speakers_per_year": args.speakers_per_year,
        "utterances_per_year": args.speakers_per_year * 2,
        "roles": {"stress_per_speaker": 1, "control_per_speaker": 1},
        "selection_seed": args.seed,
        "counts": {
            "utterances": len(all_rows),
            "speakers": len(
                {(str(row["year"]), str(row["speaker_id"])) for row in all_rows}
            ),
            "stress_utterances": sum(
                row["sample_role"] == "stress" for row in all_rows
            ),
            "control_utterances": sum(
                row["sample_role"] == "control" for row in all_rows
            ),
            "sample_words": len(sample_words),
            "stress_tokens": len(stress_tokens),
            "attested_pron_forms": len(pron_forms),
        },
        "inputs": {
            "registry": file_fingerprint(args.registry, with_sha256=True),
            "search_root": str(args.search_root.resolve()),
            "wav_root": str(args.wav_root.resolve()),
            "morph_root": str(args.morph_root.resolve()),
        },
        "outputs": {
            "selection_manifest": file_fingerprint(
                shared_root / "selection_manifest.csv", with_sha256=True
            ),
            "sample_words": file_fingerprint(
                words_path, with_sha256=True
            ),
            "stress_registry_subset": file_fingerprint(
                subset_path, with_sha256=True
            ),
            "attested_pron_forms": file_fingerprint(
                pron_path, with_sha256=True
            ),
            "policy_a_root": str(policy_roots[0]),
            "policy_b_root": str(policy_roots[1]),
        },
        "paired_files": paired_files,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(shared_root / "sample_manifest.json", manifest)
    for root in policy_roots:
        atomic_write_json(root / "selection_manifest.json", manifest)
    print(
        f"[OK] A/B byte-identical 표본 {len(all_rows)}발화: {shared_root}",
        flush=True,
    )
    return 0


def parse_generated_dict(path: Path) -> dict[str, tuple[str, ...]]:
    raw = read_dict(path)
    duplicates = {word: prons for word, prons in raw.items() if len(prons) > 1}
    if duplicates:
        sample = ", ".join(sorted(duplicates)[:5])
        raise RuntimeError(
            "G2P 출력에 단어당 복수 발음이 있음. "
            f"--num_pronunciations 1 계약 위반: {sample}"
        )
    return {word: next(iter(prons)) for word, prons in raw.items()}


def write_policy_mfa_dict(
    path: Path,
    base_dictionary: Path,
    additions: dict[str, set[tuple[str, ...]]],
) -> tuple[int, int]:
    """기본 사전 행·확률열을 보존하고 새 발음만 무확률 행으로 추가한다."""

    base_lines: list[str] = []
    with base_dictionary.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            parse_mfa_dictionary_line(
                line, path=base_dictionary, line_number=line_number
            )
            base_lines.append(line.rstrip("\r\n"))
    addition_rows = [
        (word, phones)
        for word in sorted(additions)
        for phones in sorted(additions[word])
    ]
    with atomic_text_writer(
        path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        for line in base_lines:
            stream.write(f"{line}\n")
        for word, phones in addition_rows:
            stream.write(f"{word}\t{' '.join(phones)}\n")
    return len(base_lines) + len(addition_rows), len(base_lines)


def build_lexicons(args: argparse.Namespace) -> int:
    release_root = args.release_root.resolve()
    output_dir = ensure_release_child(args.output_dir.resolve(), release_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "policy_a": output_dir / "policy_A_baseline_cache.dict",
        "policy_b": output_dir / "policy_B_attested_variants.dict",
        "diff": output_dir / "policy_B_added_variants.csv",
        "encoded": output_dir / "pilot_registry_encoded.csv",
        "manifest": output_dir / "pilot_lexicon_manifest.json",
    }
    for path in paths.values():
        if path.exists():
            raise FileExistsError(f"기존 A/B 사전 덮어쓰기 금지: {path}")
    base = read_dict(args.base_dictionary)
    word_g2p = parse_generated_dict(args.word_g2p)
    pron_g2p = parse_generated_dict(args.pron_g2p)
    phone_inventory = acoustic_phone_inventory(args.acoustic_model)
    sample_words = {
        line.strip()
        for line in args.sample_words.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }
    if not sample_words:
        raise RuntimeError("표본 어절 목록이 비어 있음")
    policy_a = {word: set(prons) for word, prons in base.items()}
    policy_a_additions: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    g2p_missing: list[str] = []
    for word in sorted(sample_words):
        if word in policy_a:
            continue
        pron = word_g2p.get(word)
        if pron is None:
            pron = ("spn",)
            g2p_missing.append(word)
        policy_a[word] = {pron}
        policy_a_additions[word].add(pron)
    policy_b = {word: set(prons) for word, prons in policy_a.items()}
    policy_b_additions = {
        word: set(prons) for word, prons in policy_a_additions.items()
    }

    subset_rows: list[dict[str, str]] = []
    with args.registry_subset.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        subset_rows = list(csv.DictReader(stream))
    diff_rows: list[dict[str, object]] = []
    encoded_rows: list[dict[str, object]] = []
    missing_pron_forms: set[str] = set()
    for row in subset_rows:
        token = clean(row.get("token"))
        pron_hangul = clean(row.get("pron_hangul"))
        phones = pron_g2p.get(pron_hangul)
        disposition = "excluded"
        reason = ""
        added = False
        if token not in sample_words:
            reason = "token_not_in_sample"
        elif phones is None:
            reason = "attested_pron_g2p_missing"
            missing_pron_forms.add(pron_hangul)
        elif any(phone not in phone_inventory for phone in phones):
            reason = "phone_outside_acoustic_inventory"
        else:
            if phones not in policy_b[token]:
                policy_b[token].add(phones)
                policy_b_additions.setdefault(token, set()).add(phones)
                added = True
                disposition = "policy_b_added"
                diff_rows.append(
                    {
                        "token": token,
                        "pron_hangul": pron_hangul,
                        "pron_phones_mfa": " ".join(phones),
                        "pron_source_field": row.get("pron_source_field", ""),
                        "urimal_id": row.get("urimal_id", ""),
                        "pos_tag": row.get("pos_tag", ""),
                        "sense_no": row.get("sense_no", ""),
                        "candidate_id": row.get("candidate_id", ""),
                    }
                )
            else:
                disposition = "already_in_policy_a"
                reason = "encoded_phones_duplicate_policy_a"
        encoded_rows.append(
            {
                **row,
                "pron_phones_mfa": " ".join(phones or ()),
                "selection_status": disposition,
                "exclusion_reason": reason,
                "policy_b_added": str(added),
            }
        )
    if not diff_rows:
        raise RuntimeError(
            "정책 B가 정책 A에 추가하는 발음이 0개라 A/B 파일럿 중단"
        )
    all_unknown = {
        phone
        for mapping in (policy_a, policy_b)
        for prons in mapping.values()
        for phones in prons
        for phone in phones
        if phone not in phone_inventory
    }
    if all_unknown:
        raise RuntimeError(
            f"acoustic phone inventory 밖 기호: {sorted(all_unknown)}"
        )
    a_rows, base_rows = write_policy_mfa_dict(
        paths["policy_a"], args.base_dictionary, policy_a_additions
    )
    b_rows, policy_b_base_rows = write_policy_mfa_dict(
        paths["policy_b"], args.base_dictionary, policy_b_additions
    )
    if policy_b_base_rows != base_rows:
        raise RuntimeError(
            "A/B 기본 사전 행 수 불일치: "
            f"A={base_rows}, B={policy_b_base_rows}"
        )
    diff_fields = [
        "token",
        "pron_hangul",
        "pron_phones_mfa",
        "pron_source_field",
        "urimal_id",
        "pos_tag",
        "sense_no",
        "candidate_id",
    ]
    write_csv_atomic(paths["diff"], diff_fields, diff_rows)
    encoded_fields = REGISTRY_FIELDS + ["policy_b_added"]
    write_csv_atomic(paths["encoded"], encoded_fields, encoded_rows)
    a_coverage_missing = sorted(sample_words - set(policy_a))
    b_coverage_missing = sorted(sample_words - set(policy_b))
    if a_coverage_missing or b_coverage_missing:
        raise RuntimeError(
            f"표본 lexicon coverage 실패: A={a_coverage_missing[:5]}, "
            f"B={b_coverage_missing[:5]}"
        )
    manifest = {
        "schema_version": 2,
        "kind": "common_pronunciation_ab_pilot_lexicons",
        "status": "needs_manual_review",
        "recorded_at": now_iso(),
        "scope": "base_dictionary_plus_sample_oov_only",
        "policy_a": (
            "base korean_mfa.dict; sample OOV uses current korean_mfa G2P "
            "num_pronunciations=1 strict_graphemes; missing becomes spn"
        ),
        "policy_b": (
            "policy A union exact-word pron_1/2 encoded with current "
            "korean_mfa G2P; no automatic replacement"
        ),
        "counts": {
            "sample_words": len(sample_words),
            "base_dictionary_words": len(base),
            "base_dictionary_rows_preserved": base_rows,
            "policy_a_words": len(policy_a),
            "policy_a_rows": a_rows,
            "policy_a_added_rows": sum(
                len(prons) for prons in policy_a_additions.values()
            ),
            "policy_b_words": len(policy_b),
            "policy_b_rows": b_rows,
            "policy_b_added_rows_total": sum(
                len(prons) for prons in policy_b_additions.values()
            ),
            "policy_b_added_variants": len(diff_rows),
            "policy_b_changed_tokens": len(
                {row["token"] for row in diff_rows}
            ),
            "sample_g2p_failures_encoded_as_spn": len(g2p_missing),
            "attested_pron_forms_missing_g2p": len(missing_pron_forms),
            "phone_inventory": len(phone_inventory),
            "phone_outside_inventory": 0,
            "policy_a_sample_coverage_missing": len(a_coverage_missing),
            "policy_b_sample_coverage_missing": len(b_coverage_missing),
        },
        "g2p_contract": {
            "num_pronunciations": 1,
            "strict_graphemes": True,
            "reason": "MFA 3.4 inline normalize_text uses the same settings",
        },
        "dictionary_contract": {
            "parser": MFA_DICTIONARY_PARSE_CONTRACT,
            "base_rows": (
                "copied semantically with optional pronunciation and "
                "silence probability columns preserved"
            ),
            "added_rows": (
                "word plus phones without probability columns; MFA 3.4 "
                "uses its default pronunciation weight 1.0"
            ),
            "interpretation": (
                "policy B is an availability pilot, not calibrated "
                "pronunciation-probability estimation"
            ),
        },
        "inputs": {
            "base_dictionary": file_fingerprint(
                args.base_dictionary, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                args.acoustic_model, with_sha256=True
            ),
            "sample_words": file_fingerprint(
                args.sample_words, with_sha256=True
            ),
            "registry_subset": file_fingerprint(
                args.registry_subset, with_sha256=True
            ),
            "word_g2p": file_fingerprint(args.word_g2p, with_sha256=True),
            "pron_g2p": file_fingerprint(args.pron_g2p, with_sha256=True),
        },
        "outputs": {
            key: file_fingerprint(path, with_sha256=True)
            for key, path in paths.items()
            if key != "manifest"
        },
        "warnings": {
            "sample_g2p_failures": g2p_missing,
            "attested_pron_forms_missing_g2p": sorted(missing_pron_forms),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(paths["manifest"], manifest)
    print(
        f"[OK] A={a_rows:,}행, B={b_rows:,}행, "
        f"B 추가={len(diff_rows):,}; 자동 채택 안 함",
        flush=True,
    )
    return 0


def labels(intervals: list[tuple[float, float, str]]) -> list[str]:
    return [label.strip() for _, _, label in intervals if label.strip()]


def edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for index_a, item_a in enumerate(a, 1):
        current = [index_a]
        for index_b, item_b in enumerate(b, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index_b] + 1,
                    previous[index_b - 1] + (item_a != item_b),
                )
            )
        previous = current
    return previous[-1]


def find_final(root: Path, row: dict[str, str]) -> Path:
    expected = (
        root
        / "textgrid_4tier"
        / row["year"]
        / row["speaker_id"]
        / f"{row['utt_id']}.TextGrid"
    )
    if expected.is_file():
        return expected
    matches = list(
        (root / "textgrid_4tier" / row["year"]).rglob(
            f"{row['utt_id']}.TextGrid"
        )
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"최종 TextGrid 누락/중복: {row['utt_id']} at {root}"
        )
    return matches[0]


def classify_comparison_rows(
    rows: list[dict[str, object]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, int],
]:
    stress_rows = [
        row for row in rows if row["sample_role"] == "stress"
    ]
    controls = [
        row for row in rows if row["sample_role"] == "control"
    ]
    effective_stress = [
        row
        for row in stress_rows
        if row["policy_b_changed_token"] == "True"
    ]
    screened_no_effect = [
        row
        for row in stress_rows
        if row["policy_b_changed_token"] != "True"
    ]
    controls_with_change = [
        row
        for row in controls
        if row["policy_b_changed_token"] == "True"
    ]
    if not stress_rows or not controls:
        raise RuntimeError(
            f"stress/control 표본이 비어 있음: "
            f"stress={len(stress_rows)}, control={len(controls)}"
        )
    if controls_with_change:
        examples = [
            str(row["utt_id"]) for row in controls_with_change[:5]
        ]
        raise RuntimeError(
            "control 발화에 policy B 변경 token 포함: "
            f"{examples}"
        )
    effective_by_year = Counter(
        str(row["year"]) for row in effective_stress
    )
    selected_years = sorted(
        {str(row["year"]) for row in stress_rows}
    )
    missing_years = [
        year for year in selected_years if not effective_by_year[year]
    ]
    if missing_years:
        raise RuntimeError(
            "실제 policy B 변경 stress가 없는 연도: "
            f"{missing_years}"
        )
    return (
        stress_rows,
        controls,
        screened_no_effect,
        dict(sorted(effective_by_year.items())),
    )


def boundary_delta_summary(
    rows: list[dict[str, object]],
) -> dict[str, int | float]:
    values = [
        float(row["max_same_index_boundary_delta_seconds"])
        for row in rows
        if row.get("max_same_index_boundary_delta_seconds") not in ("", None)
    ]
    return {
        "comparable_utterances": len(values),
        "nonzero_utterances": sum(value > 0 for value in values),
        "over_20ms_utterances": sum(value > 0.02 for value in values),
        "max_seconds": max(values, default=0.0),
    }


def compare_results(args: argparse.Namespace) -> int:
    release_root = args.release_root.resolve()
    output_dir = ensure_release_child(args.output_dir.resolve(), release_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "ab_utterance_comparison.csv"
    json_path = output_dir / "ab_comparison_summary.json"
    md_path = output_dir / "RESULTS.md"
    for path in (csv_path, json_path, md_path):
        if path.exists():
            raise FileExistsError(f"기존 A/B 비교 결과 덮어쓰기 금지: {path}")
    with args.selection_manifest.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        selected = list(csv.DictReader(stream))
    changed_tokens: set[str] = set()
    with args.diff_csv.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        for row in csv.DictReader(stream):
            changed_tokens.add(clean(row.get("token")))
    rows: list[dict[str, object]] = []
    for row in selected:
        a_tg = find_final(args.policy_a_root, row)
        b_tg = find_final(args.policy_b_root, row)
        _, a_tiers = parse_mfa_textgrid(a_tg)
        _, b_tiers = parse_mfa_textgrid(b_tg)
        a_phones = [
            item for item in a_tiers.get("phones", []) if item[2].strip()
        ]
        b_phones = [
            item for item in b_tiers.get("phones", []) if item[2].strip()
        ]
        a_labels = labels(a_phones)
        b_labels = labels(b_phones)
        boundary_delta = ""
        if len(a_phones) == len(b_phones):
            boundary_delta = round(
                max(
                    [
                        abs(a_item[0] - b_item[0])
                        for a_item, b_item in zip(a_phones, b_phones)
                    ]
                    + [
                        abs(a_item[1] - b_item[1])
                        for a_item, b_item in zip(a_phones, b_phones)
                    ]
                    + [0.0]
                ),
                6,
            )
        lab_tokens = set(clean(row.get("lab_text")).split())
        has_policy_b_change = bool(lab_tokens & changed_tokens)
        if row.get("sample_role") == "control":
            comparison_group = "control"
        elif has_policy_b_change:
            comparison_group = "stress_effective"
        else:
            comparison_group = "stress_screened_no_effect"
        wav_rel = Path(row["corpus_wav_relpath"])
        rows.append(
            {
                **{key: row.get(key, "") for key in COMPARISON_FIELDS},
                "policy_b_changed_token": str(has_policy_b_change),
                "comparison_group": comparison_group,
                "a_phone_count": len(a_labels),
                "b_phone_count": len(b_labels),
                "phone_edit_distance": edit_distance(a_labels, b_labels),
                "phone_sequence_identical": str(a_labels == b_labels),
                "word_labels_identical": str(
                    labels(a_tiers.get("words", []))
                    == labels(b_tiers.get("words", []))
                ),
                "max_same_index_boundary_delta_seconds": boundary_delta,
                "wav_a": str(args.policy_a_root / wav_rel),
                "textgrid_a": str(a_tg),
                "wav_b": str(args.policy_b_root / wav_rel),
                "textgrid_b": str(b_tg),
            }
        )
    write_csv_atomic(csv_path, COMPARISON_FIELDS, rows)
    (
        stress_rows,
        controls,
        screened_no_effect,
        effective_stress_by_year,
    ) = classify_comparison_rows(rows)
    effective_stress = [
        row
        for row in stress_rows
        if row["policy_b_changed_token"] == "True"
    ]
    summary = {
        "schema_version": 2,
        "kind": "common_pronunciation_ab_pilot_comparison",
        "status": "needs_manual_review",
        "recorded_at": now_iso(),
        "counts": {
            "utterances": len(rows),
            "stress": len(stress_rows),
            "controls": len(controls),
            "effective_stress": len(effective_stress),
            "screened_no_effect_stress": len(screened_no_effect),
            "controls_with_policy_b_changed_token": 0,
            "effective_stress_by_year": effective_stress_by_year,
            "phone_sequence_changed": sum(
                row["phone_sequence_identical"] == "False" for row in rows
            ),
            "stress_phone_sequence_changed": sum(
                row["phone_sequence_identical"] == "False"
                for row in stress_rows
            ),
            "effective_stress_phone_sequence_changed": sum(
                row["phone_sequence_identical"] == "False"
                for row in effective_stress
            ),
            "screened_no_effect_phone_sequence_changed": sum(
                row["phone_sequence_identical"] == "False"
                for row in screened_no_effect
            ),
            "control_phone_sequence_changed": sum(
                row["phone_sequence_identical"] == "False"
                for row in controls
            ),
            "word_labels_changed": sum(
                row["word_labels_identical"] == "False" for row in rows
            ),
        },
        "same_index_boundary_delta": {
            "effective_stress": boundary_delta_summary(
                effective_stress
            ),
            "screened_no_effect_stress": boundary_delta_summary(
                screened_no_effect
            ),
            "control": boundary_delta_summary(controls),
            "warning": (
                "A/B are separate MFA runs; nonzero control deltas are "
                "the empirical run-to-run noise reference"
            ),
        },
        "interpretation": (
            "stress는 사전 원천 기준으로 먼저 뽑았으며, current phone "
            "encoding 뒤 실제 B 변이가 남은 stress_effective와 A와 "
            "동일해진 stress_screened_no_effect를 분리한다. 자동 우승 "
            "정책은 없고 연구자가 WAV/TextGrid를 검토해야 한다."
        ),
        "inputs": {
            "selection_manifest": file_fingerprint(
                args.selection_manifest, with_sha256=True
            ),
            "policy_b_diff": file_fingerprint(
                args.diff_csv, with_sha256=True
            ),
        },
        "output": file_fingerprint(csv_path, with_sha256=True),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(json_path, summary)
    control_boundary = summary["same_index_boundary_delta"]["control"]
    screened_boundary = summary["same_index_boundary_delta"][
        "screened_no_effect_stress"
    ]
    lines = [
        "# 공통 발음사전 A/B MFA 파일럿",
        "",
        f"- 상태: **{summary['status']}**",
        f"- 전체 발화: {len(rows)}",
        f"- stress/control: {len(stress_rows)}/{len(controls)}",
        f"- 실제 B 변이 stress: {len(effective_stress)}",
        f"- phone 변환 뒤 무효과 stress: {len(screened_no_effect)}",
        (
            "- 연도별 실제 B 변이 stress: "
            + ", ".join(
                f"{year}={count}"
                for year, count in effective_stress_by_year.items()
            )
        ),
        "- A: 기존 `korean_mfa.dict` + 표본 OOV의 현재 G2P 1-best",
        "- B: A + exact-word 우리말샘 연계 `pron_1/2` 변이",
        "- A와 B의 WAV·lab은 SHA256이 같은 복사본",
        "",
        "## 자동 비교",
        "",
        f"- phone열 변화: {summary['counts']['phone_sequence_changed']}발화",
        (
            "- stress phone열 변화: "
            f"{summary['counts']['stress_phone_sequence_changed']}발화"
        ),
        (
            "- control phone열 변화: "
            f"{summary['counts']['control_phone_sequence_changed']}발화"
        ),
        (
            "- 실제 B 변이 stress 중 phone열 변화: "
            f"{summary['counts']['effective_stress_phone_sequence_changed']}발화"
        ),
        (
            "- control 동일-index 경계 변화: "
            f"{control_boundary['nonzero_utterances']}"
            f"/{control_boundary['comparable_utterances']}"
            "발화, 최대 "
            f"{control_boundary['max_seconds']:.3f}초"
        ),
        (
            "- 무효과 stress 동일-index 경계 변화: "
            f"{screened_boundary['nonzero_utterances']}"
            f"/{screened_boundary['comparable_utterances']}"
            "발화, 최대 "
            f"{screened_boundary['max_seconds']:.3f}초"
        ),
        (
            "- control의 비영 경계 차이는 별도 MFA 실행 사이의 "
            "경험적 잡음 기준이다."
        ),
        "",
        "## 연구자 확인",
        "",
        "1. `comparison_group=stress_effective` 발화를 먼저 고른다.",
        "2. 같은 발화의 A/B TextGrid와 WAV를 나란히 연다.",
        "3. 사전 예외 발음이 기대 구간의 경계를 개선했는지 확인한다.",
        "4. `stress_screened_no_effect`와 control의 경계 이동을 잡음 기준으로 본다.",
        "5. 이 결과만으로 실제 음운 실현을 자동 판정하지 않는다.",
        "",
        "wav2vec2 phone 후보는 후속 보조 파일럿에서 별도 열/tier로만 추가하며 "
        "여기의 MFA phone tier를 바꾸지 않는다.",
        "",
    ]
    with atomic_text_writer(
        md_path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        stream.write("\n".join(lines))
    print(f"[OK] A/B 비교 완료, 수동 검토 필요: {md_path}", flush=True)
    return 0


def add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--release-root", type=Path, default=DEFAULT_RELEASE
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    registry = commands.add_parser("registry")
    add_common_paths(registry)
    registry.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY)
    registry.add_argument("--enriched", type=Path, default=DEFAULT_ENRICHED)
    registry.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    registry.add_argument(
        "--base-dictionary", type=Path, default=DEFAULT_BASE_DICTIONARY
    )
    registry.add_argument("--output-dir", type=Path, required=True)

    sample = commands.add_parser("sample")
    add_common_paths(sample)
    sample.add_argument("--run-id", required=True)
    sample.add_argument("--registry", type=Path, required=True)
    sample.add_argument(
        "--search-root", type=Path, default=P("pre_mfa_search_master")
    )
    sample.add_argument(
        "--wav-root", type=Path, default=P("wav") / "individual"
    )
    sample.add_argument(
        "--morph-root", type=Path, default=P("textgrid_merged")
    )
    sample.add_argument(
        "--years", nargs="+", default=list(DEFAULT_YEARS)
    )
    sample.add_argument("--speakers-per-year", type=int, default=5)
    sample.add_argument("--seed", default="common_pron_ab_stress_control_v1")

    lexicons = commands.add_parser("lexicons")
    add_common_paths(lexicons)
    lexicons.add_argument(
        "--base-dictionary", type=Path, default=DEFAULT_BASE_DICTIONARY
    )
    lexicons.add_argument(
        "--acoustic-model", type=Path, default=DEFAULT_ACOUSTIC_MODEL
    )
    lexicons.add_argument("--sample-words", type=Path, required=True)
    lexicons.add_argument("--registry-subset", type=Path, required=True)
    lexicons.add_argument("--word-g2p", type=Path, required=True)
    lexicons.add_argument("--pron-g2p", type=Path, required=True)
    lexicons.add_argument("--output-dir", type=Path, required=True)

    compare = commands.add_parser("compare")
    add_common_paths(compare)
    compare.add_argument("--selection-manifest", type=Path, required=True)
    compare.add_argument("--diff-csv", type=Path, required=True)
    compare.add_argument("--policy-a-root", type=Path, required=True)
    compare.add_argument("--policy-b-root", type=Path, required=True)
    compare.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "registry":
            return build_registry(args)
        if args.command == "sample":
            if (
                args.speakers_per_year < 1
                or args.speakers_per_year > 20
            ):
                raise ValueError("speakers-per-year는 1–20")
            if set(args.years) - set(DEFAULT_YEARS):
                raise ValueError(f"지원 연도는 {DEFAULT_YEARS}")
            return build_sample(args)
        if args.command == "lexicons":
            return build_lexicons(args)
        if args.command == "compare":
            return compare_results(args)
        raise RuntimeError(f"알 수 없는 command: {args.command}")
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

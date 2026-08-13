"""형태소·음절·철자 구성 성분 검색 스키마의 단일 출처.

이 모듈은 음성 실현이나 MFA phone을 판정하지 않는다. Bareun ``tagged``의
분석 표면형을 형태소, 표면 unit(완성형 음절·독립 자모·literal run), 형태소
경계로 정규화하고 철자 기반 로마자 표시를 결정적으로 만든다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Iterator, Mapping, Sequence

import predict_pron as pp

ROMAN_SYSTEM_VERSION = "roman_mfa.v1"
SERIALIZATION_VERSION = "tagged_roman.v2"
POSITION_SCHEMA_VERSION = "morph_position.v1"
MORPH_SCHEMA_VERSION = "morph_search.v3"
SYMBOL_SCHEMA_VERSION = "symbol_reading.v1"

EOJEOL_SEPARATOR = " | "
MORPH_SEPARATOR = " + "
UNIT_SEPARATOR = " _ "

POS_RE = re.compile(r"^[A-Z][A-Z0-9_-]*$")
POS_TERMINATOR_RE = re.compile(r"/(?P<pos>[A-Z][A-Z0-9_-]*)(?=\+|$)")

# 단일 아라비아 숫자의 읽기 *후보*다. 실제 읽기 선택값이 아니며, 원 JSON의
# 전사나 연구자 판정이 없을 때 후보를 실제 발음처럼 확정하지 않는다.
# `2`는 문맥에 따라 `이/둘/두`가 될 수 있으므로 세 값을 함께 둔다.
DIGIT_READING_CANDIDATES: dict[str, tuple[str, ...]] = {
    "0": ("영", "공"),
    "1": ("일", "하나", "한"),
    "2": ("이", "둘", "두"),
    "3": ("삼", "셋", "세"),
    "4": ("사", "넷", "네"),
    "5": ("오", "다섯"),
    "6": ("육", "륙", "여섯"),
    "7": ("칠", "일곱"),
    "8": ("팔", "여덟"),
    "9": ("구", "아홉"),
}

SYMBOL_READING_FIELDS = [
    "utt_id",
    "year",
    "symbol_idx_in_utterance",
    "symbol_count_in_utterance",
    "orth_eojeol_idx",
    "orth_eojeol_count",
    "symbol_surface",
    "symbol_type",
    "source_eojeol",
    "char_start_in_eojeol",
    "char_end_in_eojeol",
    "char_start_in_compact_utterance",
    "char_end_in_compact_utterance",
    "left_context",
    "right_context",
    "reference_form",
    "reference_reading",
    "reference_reading_orth_roman",
    "reading_candidates_json",
    "reading_candidate_source",
    "reading_source",
    "reading_status",
    "resolution_method",
    "affects_reference_form",
    "pron_reference_source",
    "pron_reference_status",
    "symbol_schema_version",
]

# 호환 자모 한 글자 안에 결합되어 있는 철자 구성 성분이다. 이 목록을
# MFA phone이나 실제 음성 분절 목록으로 해석하지 않는다.
NUCLEUS_COMPONENTS: dict[str, tuple[str, ...]] = {
    "ㅘ": ("ㅗ", "ㅏ"),
    "ㅙ": ("ㅗ", "ㅐ"),
    "ㅚ": ("ㅗ", "ㅣ"),
    "ㅝ": ("ㅜ", "ㅓ"),
    "ㅞ": ("ㅜ", "ㅔ"),
    "ㅟ": ("ㅜ", "ㅣ"),
    "ㅢ": ("ㅡ", "ㅣ"),
}
CODA_COMPONENTS: dict[str, tuple[str, ...]] = {
    "ㄳ": ("ㄱ", "ㅅ"),
    "ㄵ": ("ㄴ", "ㅈ"),
    "ㄶ": ("ㄴ", "ㅎ"),
    "ㄺ": ("ㄹ", "ㄱ"),
    "ㄻ": ("ㄹ", "ㅁ"),
    "ㄼ": ("ㄹ", "ㅂ"),
    "ㄽ": ("ㄹ", "ㅅ"),
    "ㄾ": ("ㄹ", "ㅌ"),
    "ㄿ": ("ㄹ", "ㅍ"),
    "ㅀ": ("ㄹ", "ㅎ"),
    "ㅄ": ("ㅂ", "ㅅ"),
}

CHOSEONG_TO_COMPAT = {
    chr(0x1100 + index): value for index, value in enumerate(pp.CHO)
}
JUNGSEONG_TO_COMPAT = {
    chr(0x1161 + index): value for index, value in enumerate(pp.JUNG)
}
JONGSEONG_TO_COMPAT = {
    chr(0x11A8 + index): value
    for index, value in enumerate(pp.JONG[1:])
}


class MorphSchemaError(ValueError):
    """입력 ``tagged``가 동결 문법으로 무손실 해석되지 않을 때 발생한다."""


@dataclass(frozen=True)
class Morph:
    eojeol_idx: int
    morph_idx_in_eojeol: int
    surface: str
    pos: str


@dataclass(frozen=True)
class SurfaceUnit:
    surface: str
    unit_type: str
    char_start: int
    char_end: int
    jamo_compat: str = ""


def nfc(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or ""))


def _json_list(values: Sequence[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _compat_jamo(char: str) -> str:
    if char in pp.CHO or char in pp.JUNG or char in pp.JONG:
        return char
    return (
        CHOSEONG_TO_COMPAT.get(char)
        or JUNGSEONG_TO_COMPAT.get(char)
        or JONGSEONG_TO_COMPAT.get(char)
        or ""
    )


def _is_standalone_jamo(char: str) -> bool:
    return bool(_compat_jamo(char))


def parse_tagged(tagged: str) -> list[list[Morph]]:
    """Bareun ``tagged``를 어절·형태소 구조로 엄격하게 해석한다.

    POS 종결점 뒤의 ``+``만 형태소 경계로 삼는다. 1차 Bareun serializer는
    표면형 자체의 ``+``를 escape하지 않았으므로 ``.+/SW`` 같은 기호 표면형을
    단순 ``split('+')``하면 손실된다. POS 종결점을 기준으로 읽되, 설명되지 않는
    빈 형태소나 한글 형태소 안의 모호한 ``+``는 계속 실패시킨다.
    """

    value = nfc(tagged).strip()
    if not value:
        raise MorphSchemaError("빈 tagged")
    eojeol_texts = value.split()
    parsed: list[list[Morph]] = []
    for eojeol_idx, eojeol_text in enumerate(eojeol_texts, 1):
        matches = list(POS_TERMINATOR_RE.finditer(eojeol_text))
        if not matches:
            raise MorphSchemaError(
                "POS 종결점 없는 형태소: "
                f"eojeol_idx={eojeol_idx} value={eojeol_text!r}"
            )
        morphs: list[Morph] = []
        cursor = 0
        for morph_idx, match in enumerate(matches, 1):
            surface = eojeol_text[cursor : match.start()]
            pos = match.group("pos")
            unit = eojeol_text[cursor : match.end()]
            if not surface:
                raise MorphSchemaError(
                    "형태소는 비어 있지 않은 surface/POS여야 함: "
                    f"eojeol_idx={eojeol_idx} morph_idx={morph_idx} "
                    f"value={unit!r}"
                )
            if not POS_RE.fullmatch(pos):
                raise MorphSchemaError(
                    f"동결 POS 문법 밖의 값: {unit!r}"
                )
            if any(char.isspace() for char in surface):
                raise MorphSchemaError(
                    f"surface에 어절 구분자 존재: {unit!r}"
                )
            if "+" in surface and any(
                "가" <= char <= "힣" or _is_standalone_jamo(char)
                for char in surface
            ):
                raise MorphSchemaError(
                    "한글 형태소 surface의 모호한 literal '+': "
                    f"{unit!r}"
                )
            morphs.append(
                Morph(
                    eojeol_idx=eojeol_idx,
                    morph_idx_in_eojeol=morph_idx,
                    surface=surface,
                    pos=pos,
                )
            )
            if match.end() < len(eojeol_text):
                if eojeol_text[match.end()] != "+":
                    raise MorphSchemaError(
                        "형태소 사이 '+' 구분자 누락: "
                        f"eojeol_idx={eojeol_idx} value={eojeol_text!r}"
                    )
                cursor = match.end() + 1
            else:
                cursor = match.end()
        if cursor != len(eojeol_text):
            raise MorphSchemaError(
                "POS 뒤 해석되지 않은 tagged 잔여값: "
                f"eojeol_idx={eojeol_idx} value={eojeol_text!r}"
            )
        parsed.append(morphs)
    if recompose_raw_tagged(parsed) != value:
        raise MorphSchemaError(
            "tagged 무손실 재조립 실패: "
            f"expected={value!r} actual={recompose_raw_tagged(parsed)!r}"
        )
    return parsed


def recompose_raw_tagged(eojeols: Sequence[Sequence[Morph]]) -> str:
    return " ".join(
        "+".join(f"{morph.surface}/{morph.pos}" for morph in morphs)
        for morphs in eojeols
    )


def canonicalize_tagged(tagged_or_parsed: str | Sequence[Sequence[Morph]]) -> str:
    parsed = (
        parse_tagged(tagged_or_parsed)
        if isinstance(tagged_or_parsed, str)
        else tagged_or_parsed
    )
    return EOJEOL_SEPARATOR.join(
        MORPH_SEPARATOR.join(
            f"{morph.surface}/{morph.pos}" for morph in morphs
        )
        for morphs in parsed
    )


def iter_surface_units(surface: str) -> Iterator[SurfaceUnit]:
    """표면형을 완성형 음절, 독립 자모, 나머지 literal run으로 나눈다."""

    value = nfc(surface)
    index = 0
    while index < len(value):
        char = value[index]
        if pp.is_syllable(char):
            yield SurfaceUnit(char, "hangul", index, index + 1)
            index += 1
            continue
        compat = _compat_jamo(char)
        if compat:
            yield SurfaceUnit(
                char, "jamo", index, index + 1, jamo_compat=compat
            )
            index += 1
            continue
        end = index + 1
        while end < len(value):
            if pp.is_syllable(value[end]) or _is_standalone_jamo(value[end]):
                break
            end += 1
        yield SurfaceUnit(value[index:end], "literal", index, end)
        index = end


def _literal_display(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("⟨", "\\⟨")
        .replace("⟩", "\\⟩")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f"⟨{escaped}⟩"


def _standalone_jamo_roman(jamo: str) -> str:
    if jamo in pp.VOWEL_ROMAN:
        return pp.VOWEL_ROMAN[jamo]
    if jamo in pp.SPELL_CODA_ROMAN:
        return pp.SPELL_CODA_ROMAN[jamo]
    # ㄸ·ㅃ·ㅉ처럼 종성에 올 수 없는 독립 자음은 종성 철자표에 없다.
    # 독립 ㄴ·ㄹ 등의 기존 소문자 표기는 유지하고, 필요한 경우에만
    # onset 표기로 fallback해 표면 자모가 검색에서 사라지지 않게 한다.
    if jamo in pp.ONSET_ROMAN and pp.ONSET_ROMAN[jamo]:
        return pp.ONSET_ROMAN[jamo]
    raise MorphSchemaError(f"지원하지 않는 독립 자모: {jamo!r}")


def unit_roman(unit: SurfaceUnit) -> str:
    if unit.unit_type == "hangul":
        return pp.romanize(
            [pp.decompose(unit.surface)], pp.SPELL_CODA_ROMAN
        )
    if unit.unit_type == "jamo":
        return _standalone_jamo_roman(unit.jamo_compat)
    return _literal_display(unit.surface)


def tagged_roman_v2(
    tagged_or_parsed: str | Sequence[Sequence[Morph]],
) -> str:
    parsed = (
        parse_tagged(tagged_or_parsed)
        if isinstance(tagged_or_parsed, str)
        else tagged_or_parsed
    )
    eojeol_values: list[str] = []
    for morphs in parsed:
        morph_values: list[str] = []
        for morph in morphs:
            units = list(iter_surface_units(morph.surface))
            if not units:
                raise MorphSchemaError(
                    f"빈 형태소 unit: {morph.surface}/{morph.pos}"
                )
            roman = UNIT_SEPARATOR.join(unit_roman(unit) for unit in units)
            morph_values.append(f"{roman}/{morph.pos}")
        eojeol_values.append(MORPH_SEPARATOR.join(morph_values))
    return EOJEOL_SEPARATOR.join(eojeol_values)


def orth_roman_v2(form: str) -> str:
    """Romanize surface orthography without dropping mixed-script eojeols.

    Hangul syllables use the frozen orthographic Roman mapping. Non-Hangul
    runs remain escaped ``⟨literal⟩`` tokens instead of turning the entire
    eojeol into ``∅``. No pronunciation rule or morphology is used.
    """

    eojeols = str(form or "").split()
    if not eojeols:
        raise MorphSchemaError("빈 form은 orth_roman_v2로 변환할 수 없음")
    values: list[str] = []
    for eojeol in eojeols:
        units = [
            unit for unit in iter_surface_units(eojeol)
            if unit.unit_type != "literal"
            or not all(char in pp.PUNCT for char in unit.surface)
        ]
        if not units:
            # A punctuation-only eojeol must retain its position, but attached
            # punctuation is omitted to stay compatible with legacy Hangul
            # orthographic Roman labels.
            units = list(iter_surface_units(eojeol))
        values.append(UNIT_SEPARATOR.join(unit_roman(unit) for unit in units))
    return EOJEOL_SEPARATOR.join(values)


def _symbol_type(value: str) -> str:
    """Classify one literal run without interpreting its pronunciation."""

    if value and all(char.isdigit() for char in value):
        return "digit"
    if value and all(
        char.isalpha() and "LATIN" in unicodedata.name(char, "")
        for char in value
    ):
        return "latin"
    if value and all(unicodedata.category(char).startswith("P") for char in value):
        return "punctuation"
    if value and all(unicodedata.category(char).startswith("S") for char in value):
        return "symbol"
    return "mixed_literal"


def _is_korean_reading(value: str) -> bool:
    return bool(value) and all(
        pp.is_syllable(char) or _is_standalone_jamo(char) for char in value
    )


def _symbol_reading_candidates(value: str) -> tuple[str, ...]:
    # 여러 자리 수는 자리값·단위·문맥에 따라 읽기가 달라지므로 각 자릿값을
    # 기계적으로 이어 붙이지 않는다.
    return DIGIT_READING_CANDIDATES.get(value, ())


def build_symbol_readings(
    *,
    utt_id: str,
    year: str,
    form_eojeols: Sequence[str],
    reference_form: str,
    pron_reference_source: str,
    pron_reference_status: str,
) -> list[dict[str, object]]:
    """Build source-preserving literal/symbol rows and evidence-backed readings.

    The table never treats a numeral candidate as the selected pronunciation.
    A selected ``reference_reading`` is emitted only when a SequenceMatcher
    replacement aligns exactly to the literal run in ``form``.  Thus
    ``2사람이`` -> ``두 사람이`` can yield ``2`` -> ``두`` when the corpus
    reference supplies that form, while an unexpanded ``2`` remains unresolved
    with ``이/둘/두`` only in ``reading_candidates_json``.
    """

    source_compact = "".join(form_eojeols)
    reference_value = nfc(reference_form).strip()
    reference_compact = "".join(reference_value.split())
    opcodes = (
        SequenceMatcher(
            None, source_compact, reference_compact, autojunk=False
        ).get_opcodes()
        if reference_compact
        else []
    )

    specs: list[dict[str, object]] = []
    compact_offset = 0
    for eojeol_idx, eojeol in enumerate(form_eojeols, 1):
        for unit in iter_surface_units(eojeol):
            if unit.unit_type != "literal":
                continue
            specs.append(
                {
                    "eojeol_idx": eojeol_idx,
                    "source_eojeol": eojeol,
                    "surface": unit.surface,
                    "start_eojeol": unit.char_start,
                    "end_eojeol": unit.char_end,
                    "start_compact": compact_offset + unit.char_start,
                    "end_compact": compact_offset + unit.char_end,
                }
            )
        compact_offset += len(eojeol)

    rows: list[dict[str, object]] = []
    symbol_count = len(specs)
    for symbol_idx, spec in enumerate(specs, 1):
        start = int(spec["start_compact"])
        end = int(spec["end_compact"])
        surface = str(spec["surface"])
        symbol_type = _symbol_type(surface)
        reading = ""
        reading_source = ""
        status = "unresolved_no_reference"
        method = "no_reference"
        affects_reference = False

        covering = [
            opcode
            for opcode in opcodes
            if opcode[1] <= start and end <= opcode[2]
        ]
        if covering:
            tag, i1, i2, j1, j2 = covering[0]
            exact = i1 == start and i2 == end
            reading_source = pron_reference_source
            if tag == "equal":
                method = "literal_preserved_in_reference"
                status = (
                    "not_applicable_punctuation_preserved"
                    if symbol_type == "punctuation"
                    else "unresolved_same_literal"
                )
            elif exact and tag == "replace":
                reading = reference_compact[j1:j2]
                affects_reference = True
                method = "exact_sequence_replace"
                status = (
                    "resolved_reference_transcription"
                    if _is_korean_reading(reading)
                    else "unresolved_non_korean_replacement"
                )
            elif exact and tag == "delete":
                affects_reference = True
                method = "exact_sequence_delete"
                status = (
                    "not_applicable_punctuation_omitted"
                    if symbol_type == "punctuation"
                    else "unresolved_reference_omitted"
                )
            else:
                affects_reference = tag != "equal"
                method = "sequence_change_not_isolated_to_symbol"
                status = "unresolved_alignment_ambiguous"

        candidates = _symbol_reading_candidates(surface)
        rows.append(
            {
                "utt_id": utt_id,
                "year": year,
                "symbol_idx_in_utterance": symbol_idx,
                "symbol_count_in_utterance": symbol_count,
                "eojeol_idx": spec["eojeol_idx"],
                "eojeol_count": len(form_eojeols),
                "symbol_surface": surface,
                "symbol_type": symbol_type,
                "source_eojeol": spec["source_eojeol"],
                "char_start_in_eojeol": spec["start_eojeol"],
                "char_end_in_eojeol": spec["end_eojeol"],
                "char_start_in_compact_utterance": start,
                "char_end_in_compact_utterance": end,
                "left_context": source_compact[max(0, start - 12):start],
                "right_context": source_compact[end:end + 12],
                "reference_form": reference_value,
                "reference_reading": reading,
                "reference_reading_orth_roman": (
                    orth_roman_v2(reading) if reading else ""
                ),
                "reading_candidates_json": _json_list(candidates),
                "reading_candidate_source": (
                    "korean_digit_candidates.v1" if candidates else ""
                ),
                "reading_source": reading_source,
                "reading_status": status,
                "resolution_method": method,
                "affects_reference_form": affects_reference,
                "pron_reference_source": pron_reference_source,
                "pron_reference_status": pron_reference_status,
                "symbol_schema_version": SYMBOL_SCHEMA_VERSION,
            }
        )
    return rows


def _slot_components(slot: str, jamo: str) -> tuple[str, ...]:
    if not jamo:
        return ()
    if slot == "nucleus":
        return NUCLEUS_COMPONENTS.get(jamo, (jamo,))
    if slot == "coda":
        return CODA_COMPONENTS.get(jamo, (jamo,))
    return (jamo,)


def _component_roman(slot: str, jamo: str) -> str:
    if slot == "onset":
        return pp.ONSET_ROMAN[jamo]
    if slot == "nucleus":
        return pp.VOWEL_ROMAN[jamo]
    if slot == "coda":
        return pp.SPELL_CODA_ROMAN[jamo]
    return _standalone_jamo_roman(jamo)


def _unit_slot_payload(unit: SurfaceUnit) -> dict[str, object]:
    payload: dict[str, object] = {
        "syllable_surface": "",
        "standalone_jamo": "",
        "onset_jamo": "",
        "nucleus_jamo": "",
        "coda_jamo": "",
        "onset_roman": "",
        "nucleus_roman": "",
        "coda_roman": "",
        "onset_zero": False,
        "nucleus_components_json": "[]",
        "coda_components_json": "[]",
        "orth_component_count": 0,
    }
    if unit.unit_type == "hangul":
        onset, nucleus, coda = pp.decompose(unit.surface)
        nucleus_components = _slot_components("nucleus", nucleus)
        coda_components = _slot_components("coda", coda)
        payload.update(
            syllable_surface=unit.surface,
            onset_jamo=onset,
            nucleus_jamo=nucleus,
            coda_jamo=coda,
            onset_roman=pp.ONSET_ROMAN[onset],
            nucleus_roman=pp.VOWEL_ROMAN[nucleus],
            coda_roman=pp.SPELL_CODA_ROMAN[coda],
            onset_zero=onset == "ㅇ",
            nucleus_components_json=_json_list(nucleus_components),
            coda_components_json=_json_list(coda_components),
            orth_component_count=(
                1 + len(nucleus_components) + len(coda_components)
            ),
        )
    elif unit.unit_type == "jamo":
        payload.update(
            standalone_jamo=unit.jamo_compat,
            orth_component_count=1,
        )
    return payload


def _orth_component_rows(
    unit_row: Mapping[str, object],
    *,
    unit: SurfaceUnit,
) -> list[dict[str, object]]:
    common = {
        key: unit_row[key]
        for key in (
            "utt_id",
            "year",
            "eojeol_idx",
            "morph_idx_in_eojeol",
            "morph_idx_in_utterance",
            "unit_idx_in_morph",
            "unit_idx_in_eojeol",
            "unit_idx_in_utterance",
        )
    }
    rows: list[dict[str, object]] = []
    if unit.unit_type == "hangul":
        onset, nucleus, coda = pp.decompose(unit.surface)
        slots = (
            ("onset", onset, _slot_components("onset", onset)),
            ("nucleus", nucleus, _slot_components("nucleus", nucleus)),
            ("coda", coda, _slot_components("coda", coda)),
        )
        component_idx_in_unit = 0
        for slot_idx, (slot, slot_jamo, components) in enumerate(slots, 1):
            if not slot_jamo:
                continue
            slot_roman = (
                pp.ONSET_ROMAN[slot_jamo]
                if slot == "onset"
                else (
                    pp.VOWEL_ROMAN[slot_jamo]
                    if slot == "nucleus"
                    else pp.SPELL_CODA_ROMAN[slot_jamo]
                )
            )
            for component_idx_in_slot, component in enumerate(components, 1):
                component_idx_in_unit += 1
                rows.append(
                    {
                        **common,
                        "unit_type": unit.unit_type,
                        "slot": slot,
                        "slot_idx_in_syllable": slot_idx,
                        "slot_jamo": slot_jamo,
                        "slot_roman": slot_roman,
                        "component_idx_in_slot": component_idx_in_slot,
                        "component_count_in_slot": len(components),
                        "component_idx_in_unit": component_idx_in_unit,
                        "component_jamo": component,
                        "component_roman": _component_roman(
                            slot, component
                        ),
                        "component_is_onset_zero": (
                            slot == "onset" and component == "ㅇ"
                        ),
                        "component_schema_version": POSITION_SCHEMA_VERSION,
                    }
                )
    elif unit.unit_type == "jamo":
        rows.append(
            {
                **common,
                "unit_type": unit.unit_type,
                "slot": "standalone",
                "slot_idx_in_syllable": "",
                "slot_jamo": unit.jamo_compat,
                "slot_roman": _standalone_jamo_roman(unit.jamo_compat),
                "component_idx_in_slot": 1,
                "component_count_in_slot": 1,
                "component_idx_in_unit": 1,
                "component_jamo": unit.jamo_compat,
                "component_roman": _standalone_jamo_roman(
                    unit.jamo_compat
                ),
                "component_is_onset_zero": False,
                "component_schema_version": POSITION_SCHEMA_VERSION,
            }
        )
    return rows


def _edge_payload(unit_row: Mapping[str, object], prefix: str) -> dict[str, object]:
    return {
        f"{prefix}_unit_surface": unit_row["unit_surface"],
        f"{prefix}_unit_type": unit_row["unit_type"],
        f"{prefix}_onset_jamo": unit_row["onset_jamo"],
        f"{prefix}_nucleus_jamo": unit_row["nucleus_jamo"],
        f"{prefix}_coda_jamo": unit_row["coda_jamo"],
        f"{prefix}_onset_zero": unit_row["onset_zero"],
        f"{prefix}_standalone_jamo": unit_row["standalone_jamo"],
        f"{prefix}_nucleus_components_json": unit_row[
            "nucleus_components_json"
        ],
        f"{prefix}_coda_components_json": unit_row[
            "coda_components_json"
        ],
    }


def build_utterance_tables(row: Mapping[str, object]) -> dict[str, object]:
    """발화 1행에서 정규화 검색표와 master 파생값을 만든다."""

    utt_id = nfc(row.get("utt_id", "")).strip()
    year = nfc(row.get("year", "")).strip()
    tagged = nfc(row.get("tagged", "")).strip()
    if not utt_id:
        raise MorphSchemaError("빈 utt_id")
    parsed = parse_tagged(tagged)
    flat_morphs = [morph for eojeol in parsed for morph in eojeol]
    morph_count = len(flat_morphs)

    # 어절 철자·로마자 검색은 형태소 표와 분리한 1행/어절 표를 정본으로
    # 사용한다. form이 없는 단위시험·구자료는 tagged 표면형으로 결정적으로
    # 재생성하지만, 그 출처를 숨기지 않는다.
    tagged_eojeol_forms = [
        "".join(morph.surface for morph in morphs) for morphs in parsed
    ]
    form_value = nfc(row.get("form", "")).strip()
    if form_value:
        form_eojeols = form_value.split()
        eojeol_form_source = "form"
    else:
        form_eojeols = tagged_eojeol_forms
        eojeol_form_source = "tagged_surface_fallback"
    form_tagged_count_equal = len(form_eojeols) == len(parsed)

    form_roman_value = str(row.get("form_roman", "") or "").strip()
    if form_roman_value:
        form_roman_eojeols = form_roman_value.split(EOJEOL_SEPARATOR)
        eojeol_roman_source = "form_roman"
    else:
        predicted = pp.predict_pron(" ".join(form_eojeols), tagged=tagged)
        form_roman_eojeols = str(predicted["form_roman"]).split(
            EOJEOL_SEPARATOR
        )
        eojeol_roman_source = "deterministic_form_fallback"
    form_roman_count_equal = len(form_roman_eojeols) == len(form_eojeols)

    orth_eojeol_rows: list[dict[str, object]] = []
    for orth_idx, orth_form in enumerate(form_eojeols, 1):
        orth_eojeol_rows.append(
            {
                "utt_id": utt_id,
                "year": year,
                "orth_eojeol_idx": orth_idx,
                "orth_eojeol_count": len(form_eojeols),
                "orth_eojeol_form": orth_form,
                "orth_eojeol_roman": (
                    form_roman_eojeols[orth_idx - 1]
                    if form_roman_count_equal
                    else ""
                ),
                "orth_eojeol_roman_v2": orth_roman_v2(orth_form),
                "linked_morph_eojeol_idx": (
                    orth_idx if form_tagged_count_equal else ""
                ),
                "morph_link_status": (
                    "count_aligned"
                    if form_tagged_count_equal
                    else "form_tagged_count_mismatch"
                ),
                "orth_eojeol_form_source": eojeol_form_source,
                "orth_eojeol_roman_source": (
                    eojeol_roman_source
                    if form_roman_count_equal
                    else "legacy_form_roman_count_mismatch"
                ),
                "roman_system_version": ROMAN_SYSTEM_VERSION,
                "position_schema_version": POSITION_SCHEMA_VERSION,
            }
        )

    eojeol_rows: list[dict[str, object]] = []
    for eojeol_idx, morphs in enumerate(parsed, 1):
        morph_surface = tagged_eojeol_forms[eojeol_idx - 1]
        linked_form = (
            form_eojeols[eojeol_idx - 1]
            if form_tagged_count_equal
            else ""
        )
        use_legacy_roman = form_tagged_count_equal and form_roman_count_equal
        eojeol_form = linked_form or morph_surface
        eojeol_roman = (
            form_roman_eojeols[eojeol_idx - 1]
            if use_legacy_roman
            else orth_roman_v2(morph_surface)
        )
        eojeol_rows.append(
            {
                "utt_id": utt_id,
                "year": year,
                "eojeol_idx": eojeol_idx,
                "eojeol_count": len(parsed),
                "eojeol_form": eojeol_form,
                "eojeol_roman": eojeol_roman,
                "eojeol_roman_v2": (
                    orth_roman_v2(linked_form)
                    if linked_form
                    else orth_roman_v2(morph_surface)
                ),
                "morph_eojeol_surface": morph_surface,
                "orth_eojeol_form": linked_form,
                "morph_count_in_eojeol": len(morphs),
                "morph_surface_concat": tagged_eojeol_forms[eojeol_idx - 1],
                "morph_tagged": canonicalize_tagged([morphs]),
                "morph_roman": tagged_roman_v2([morphs]),
                "form_matches_morph_surface": (
                    bool(linked_form) and linked_form == morph_surface
                ),
                "morph_to_form_status": (
                    "form_tagged_count_mismatch"
                    if not form_tagged_count_equal
                    else (
                        "exact_concat"
                        if linked_form == morph_surface
                        else "surface_mismatch"
                    )
                ),
                "eojeol_form_source": (
                    eojeol_form_source
                    if linked_form
                    else "tagged_analysis_space"
                ),
                "eojeol_roman_source": (
                    eojeol_roman_source
                    if use_legacy_roman
                    else "tagged_roman_v2_analysis_space"
                ),
                "eojeol_roman_v2_source": (
                    "orth_roman_v2"
                    if linked_form
                    else "tagged_roman_v2_analysis_space"
                ),
                "roman_system_version": ROMAN_SYSTEM_VERSION,
                "position_schema_version": POSITION_SCHEMA_VERSION,
            }
        )

    reference_form = nfc(row.get("pron_reference_form", "")).strip()
    if not reference_form:
        reference_form = " ".join(form_eojeols)
    pron_reference_source = nfc(
        row.get("pron_reference_source", "")
    ).strip() or "form_fallback"
    pron_reference_status = nfc(
        row.get("pron_reference_status", "")
    ).strip() or "reference_not_supplied"
    symbol_rows = build_symbol_readings(
        utt_id=utt_id,
        year=year,
        form_eojeols=form_eojeols,
        reference_form=reference_form,
        pron_reference_source=pron_reference_source,
        pron_reference_status=pron_reference_status,
    )

    units_by_morph: dict[tuple[int, int], list[SurfaceUnit]] = {
        (morph.eojeol_idx, morph.morph_idx_in_eojeol): list(
            iter_surface_units(morph.surface)
        )
        for morph in flat_morphs
    }
    if any(not units for units in units_by_morph.values()):
        raise MorphSchemaError(f"{utt_id}: unit 0개 형태소")

    units_per_eojeol = {
        eojeol_idx: sum(
            len(units_by_morph[(morph.eojeol_idx, morph.morph_idx_in_eojeol)])
            for morph in morphs
        )
        for eojeol_idx, morphs in enumerate(parsed, 1)
    }
    total_units = sum(units_per_eojeol.values())

    morph_rows: list[dict[str, object]] = []
    unit_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    morph_idx_in_utterance = 0
    unit_idx_in_utterance = 0
    syllable_idx_in_utterance = 0

    for eojeol_idx, morphs in enumerate(parsed, 1):
        unit_idx_in_eojeol = 0
        syllable_idx_in_eojeol = 0
        eojeol_syllable_count = sum(
            sum(
                unit.unit_type == "hangul"
                for unit in units_by_morph[
                    (morph.eojeol_idx, morph.morph_idx_in_eojeol)
                ]
            )
            for morph in morphs
        )
        for morph in morphs:
            morph_idx_in_utterance += 1
            units = units_by_morph[
                (morph.eojeol_idx, morph.morph_idx_in_eojeol)
            ]
            syllable_count = sum(unit.unit_type == "hangul" for unit in units)
            morph_roman = UNIT_SEPARATOR.join(
                unit_roman(unit) for unit in units
            )
            morph_rows.append(
                {
                    "utt_id": utt_id,
                    "year": year,
                    "eojeol_idx": eojeol_idx,
                    "eojeol_count": len(parsed),
                    "morph_idx_in_eojeol": morph.morph_idx_in_eojeol,
                    "morph_count_in_eojeol": len(morphs),
                    "morph_idx_in_utterance": morph_idx_in_utterance,
                    "morph_count_in_utterance": morph_count,
                    "morph_surface": morph.surface,
                    "pos": morph.pos,
                    "morph_roman": morph_roman,
                    "unit_count": len(units),
                    "syllable_count": syllable_count,
                    "has_literal": any(
                        unit.unit_type == "literal" for unit in units
                    ),
                    "has_standalone_jamo": any(
                        unit.unit_type == "jamo" for unit in units
                    ),
                    "position_schema_version": POSITION_SCHEMA_VERSION,
                }
            )
            syllable_idx_in_morph = 0
            for unit_idx_in_morph, unit in enumerate(units, 1):
                unit_idx_in_eojeol += 1
                unit_idx_in_utterance += 1
                if unit.unit_type == "hangul":
                    syllable_idx_in_morph += 1
                    syllable_idx_in_eojeol += 1
                    syllable_idx_in_utterance += 1
                    syllable_idx_value: int | str = syllable_idx_in_morph
                else:
                    syllable_idx_value = ""
                unit_row = {
                    "utt_id": utt_id,
                    "year": year,
                    "eojeol_idx": eojeol_idx,
                    "eojeol_count": len(parsed),
                    "morph_idx_in_eojeol": morph.morph_idx_in_eojeol,
                    "morph_count_in_eojeol": len(morphs),
                    "morph_idx_in_utterance": morph_idx_in_utterance,
                    "morph_count_in_utterance": morph_count,
                    "morph_surface": morph.surface,
                    "pos": morph.pos,
                    "unit_idx_in_morph": unit_idx_in_morph,
                    "unit_count_in_morph": len(units),
                    "unit_idx_in_eojeol": unit_idx_in_eojeol,
                    "unit_count_in_eojeol": units_per_eojeol[eojeol_idx],
                    "unit_idx_in_utterance": unit_idx_in_utterance,
                    "unit_count_in_utterance": total_units,
                    "syllable_idx_in_morph": syllable_idx_value,
                    "syllable_count_in_morph": syllable_count,
                    "syllable_idx_in_eojeol": (
                        syllable_idx_in_eojeol
                        if unit.unit_type == "hangul"
                        else ""
                    ),
                    "syllable_count_in_eojeol": eojeol_syllable_count,
                    "syllable_idx_in_utterance": (
                        syllable_idx_in_utterance
                        if unit.unit_type == "hangul"
                        else ""
                    ),
                    "unit_surface": unit.surface,
                    "unit_type": unit.unit_type,
                    "char_start": unit.char_start,
                    "char_end": unit.char_end,
                    "unit_roman": unit_roman(unit),
                    **_unit_slot_payload(unit),
                    "position_schema_version": POSITION_SCHEMA_VERSION,
                }
                if unit.unit_type == "hangul":
                    onset = str(unit_row["onset_jamo"])
                    nucleus = str(unit_row["nucleus_jamo"])
                    coda = str(unit_row["coda_jamo"])
                    if pp.compose(onset, nucleus, coda) != unit.surface:
                        raise MorphSchemaError(
                            f"{utt_id}: 음절 재조립 실패 {unit.surface!r}"
                        )
                unit_rows.append(unit_row)
                component_rows.extend(
                    _orth_component_rows(unit_row, unit=unit)
                )

    unit_rows_by_morph: dict[tuple[int, int], list[dict[str, object]]] = {}
    for unit_row in unit_rows:
        key = (
            int(unit_row["eojeol_idx"]),
            int(unit_row["morph_idx_in_eojeol"]),
        )
        unit_rows_by_morph.setdefault(key, []).append(unit_row)

    boundary_rows: list[dict[str, object]] = []
    boundary_count = max(0, morph_count - 1)
    for boundary_idx, (left, right) in enumerate(
        zip(flat_morphs, flat_morphs[1:]), 1
    ):
        left_units = unit_rows_by_morph[
            (left.eojeol_idx, left.morph_idx_in_eojeol)
        ]
        right_units = unit_rows_by_morph[
            (right.eojeol_idx, right.morph_idx_in_eojeol)
        ]
        boundary_rows.append(
            {
                "utt_id": utt_id,
                "year": year,
                "boundary_idx_in_utterance": boundary_idx,
                "boundary_count_in_utterance": boundary_count,
                "boundary_scope": (
                    "intra_eojeol"
                    if left.eojeol_idx == right.eojeol_idx
                    else "inter_eojeol"
                ),
                "left_eojeol_idx": left.eojeol_idx,
                "left_morph_idx_in_eojeol": left.morph_idx_in_eojeol,
                "left_morph_idx_in_utterance": boundary_idx,
                "left_morph_surface": left.surface,
                "left_pos": left.pos,
                "right_eojeol_idx": right.eojeol_idx,
                "right_morph_idx_in_eojeol": right.morph_idx_in_eojeol,
                "right_morph_idx_in_utterance": boundary_idx + 1,
                "right_morph_surface": right.surface,
                "right_pos": right.pos,
                **_edge_payload(left_units[-1], "left"),
                **_edge_payload(right_units[0], "right"),
                "has_literal_context": (
                    left_units[-1]["unit_type"] == "literal"
                    or right_units[0]["unit_type"] == "literal"
                ),
                "position_schema_version": POSITION_SCHEMA_VERSION,
            }
        )

    expected_n_morphs = str(row.get("n_morphs", "") or "").strip()
    legacy_plus_count = sum(
        eojeol.count("+") + 1 for eojeol in tagged.split() if eojeol
    )
    literal_plus_count = sum(
        morph.surface.count("+") for morph in flat_morphs
    )
    n_morphs_equal = (
        not expected_n_morphs
        or not expected_n_morphs.isdigit()
        or int(expected_n_morphs) == morph_count
    )
    legacy_plus_overcount_explained = (
        bool(expected_n_morphs)
        and expected_n_morphs.isdigit()
        and literal_plus_count > 0
        and int(expected_n_morphs) == legacy_plus_count
        and legacy_plus_count == morph_count + literal_plus_count
    )
    if not n_morphs_equal and not legacy_plus_overcount_explained:
        raise MorphSchemaError(
            f"{utt_id}: n_morphs 불일치 "
            f"csv={expected_n_morphs} parsed={morph_count}"
        )
    roman = tagged_roman_v2(parsed)
    master = dict(row)
    master.update(
        {
            "canonical_tagged": canonicalize_tagged(parsed),
            "tagged_roman_v2": roman,
            "form_roman_v2": orth_roman_v2(" ".join(form_eojeols)),
            "roman_system_version": ROMAN_SYSTEM_VERSION,
            "serialization_version": SERIALIZATION_VERSION,
            "position_schema_version": POSITION_SCHEMA_VERSION,
            "morph_schema_version": MORPH_SCHEMA_VERSION,
            "morph_parse_status": (
                "ok_legacy_literal_plus_n_morphs_overcount"
                if legacy_plus_overcount_explained
                else "ok"
            ),
            "morph_count_structured": morph_count,
            "morph_unit_count": total_units,
            "morph_boundary_count": boundary_count,
            "orth_eojeol_count_structured": len(form_eojeols),
            "morph_eojeol_count_structured": len(parsed),
            "form_tagged_eojeol_count_equal": form_tagged_count_equal,
            "symbol_schema_version": SYMBOL_SCHEMA_VERSION,
            "symbol_count": len(symbol_rows),
            "symbol_reading_resolved_count": sum(
                str(item["reading_status"]).startswith("resolved_")
                for item in symbol_rows
            ),
            "symbol_reading_unresolved_count": sum(
                str(item["reading_status"]).startswith("unresolved_")
                for item in symbol_rows
            ),
            "symbol_not_applicable_count": sum(
                str(item["reading_status"]).startswith("not_applicable_")
                for item in symbol_rows
            ),
            "tagged_regeneration_equal": (
                recompose_raw_tagged(parsed) == tagged
            ),
            "legacy_tagged_roman_equal_v2": (
                str(row.get("tagged_roman", "")) == roman
            ),
        }
    )
    if not master["tagged_regeneration_equal"]:
        raise MorphSchemaError(f"{utt_id}: tagged regeneration 불일치")
    return {
        "master": master,
        "orth_eojeol_tokens": orth_eojeol_rows,
        "eojeol_tokens": eojeol_rows,
        "morph_tokens": morph_rows,
        "morph_units": unit_rows,
        "morph_boundaries": boundary_rows,
        "symbol_readings": symbol_rows,
        "orth_components": component_rows,
    }


def table_fieldnames(rows: Iterable[Mapping[str, object]]) -> list[str]:
    for row in rows:
        return list(row)
    return []

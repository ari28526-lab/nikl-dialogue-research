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
from typing import Iterable, Iterator, Mapping, Sequence

import predict_pron as pp

ROMAN_SYSTEM_VERSION = "roman_mfa.v1"
SERIALIZATION_VERSION = "tagged_roman.v2"
POSITION_SCHEMA_VERSION = "morph_position.v1"
MORPH_SCHEMA_VERSION = "morph_search.v1"

EOJEOL_SEPARATOR = " | "
MORPH_SEPARATOR = " + "
UNIT_SEPARATOR = " _ "

POS_RE = re.compile(r"^[A-Z][A-Z0-9_-]*$")

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

    ``/``는 마지막 것을 POS 경계로 삼는다. POS와 표면형이 비거나 예약 구분자
    때문에 무손실 재조립할 수 없는 입력은 조용히 보정하지 않고 실패시킨다.
    """

    value = nfc(tagged).strip()
    if not value:
        raise MorphSchemaError("빈 tagged")
    eojeol_texts = value.split()
    parsed: list[list[Morph]] = []
    for eojeol_idx, eojeol_text in enumerate(eojeol_texts, 1):
        units = eojeol_text.split("+")
        if any(not unit for unit in units):
            raise MorphSchemaError(
                f"빈 형태소: eojeol_idx={eojeol_idx} value={eojeol_text!r}"
            )
        morphs: list[Morph] = []
        for morph_idx, unit in enumerate(units, 1):
            surface, separator, pos = unit.rpartition("/")
            if not separator or not surface or not pos:
                raise MorphSchemaError(
                    "형태소는 비어 있지 않은 surface/POS여야 함: "
                    f"eojeol_idx={eojeol_idx} morph_idx={morph_idx} "
                    f"value={unit!r}"
                )
            if not POS_RE.fullmatch(pos):
                raise MorphSchemaError(
                    f"동결 POS 문법 밖의 값: {unit!r}"
                )
            if "+" in surface or any(char.isspace() for char in surface):
                raise MorphSchemaError(
                    f"surface에 예약 형태소/어절 구분자 존재: {unit!r}"
                )
            morphs.append(
                Morph(
                    eojeol_idx=eojeol_idx,
                    morph_idx_in_eojeol=morph_idx,
                    surface=surface,
                    pos=pos,
                )
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
    """발화 1행에서 정규화 표 네 종류와 master 파생값을 만든다."""

    utt_id = nfc(row.get("utt_id", "")).strip()
    year = nfc(row.get("year", "")).strip()
    tagged = nfc(row.get("tagged", "")).strip()
    if not utt_id:
        raise MorphSchemaError("빈 utt_id")
    parsed = parse_tagged(tagged)
    flat_morphs = [morph for eojeol in parsed for morph in eojeol]
    morph_count = len(flat_morphs)

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
    n_morphs_equal = (
        not expected_n_morphs
        or not expected_n_morphs.isdigit()
        or int(expected_n_morphs) == morph_count
    )
    if not n_morphs_equal:
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
            "roman_system_version": ROMAN_SYSTEM_VERSION,
            "serialization_version": SERIALIZATION_VERSION,
            "position_schema_version": POSITION_SCHEMA_VERSION,
            "morph_schema_version": MORPH_SCHEMA_VERSION,
            "morph_parse_status": "ok",
            "morph_count_structured": morph_count,
            "morph_unit_count": total_units,
            "morph_boundary_count": boundary_count,
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
        "morph_tokens": morph_rows,
        "morph_units": unit_rows,
        "morph_boundaries": boundary_rows,
        "orth_components": component_rows,
    }


def table_fieldnames(rows: Iterable[Mapping[str, object]]) -> list[str]:
    for row in rows:
        return list(row)
    return []

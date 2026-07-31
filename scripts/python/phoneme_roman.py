"""MFA phone을 검색용 프로젝트 로마자에 연결하는 보조 모듈.

이 모듈은 음성 실현을 판정하지 않는다. ``phones_mfa``의 IPA 원값과 시간을
그대로 보존하면서 다음 두 파생값만 만든다.

``phone_class_r_auto``
    동결 acoustic model의 phone inventory와 phone groups를 근거로 한
    기계적 로마자 범주. 한국어의 평음/격음/경음 대립은 보존한다.

``phoneme_lexical_r_auto``
    철자 로마자와 규칙 예측발음 로마자를 함께 표시하고, 예측발음 토큰을
    MFA phone 시간에 자동 투영한 어휘적 음소 후보. 실제 발음 전사가 아니다.
"""

from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA_VERSION = "phoneme_roman_aux.v1"
ROMAN_SYSTEM_VERSION = "roman_mfa.v1"

# acoustic meta.json의 phone_groups 0--21을 사람이 검색하기 쉬운 ASCII
# 로마자로 이름 붙인다. 이 값은 음소 판정이 아니라 model group의 표시명이다.
MODEL_GROUP_R = {
    0: "K_GROUP",
    1: "M_GROUP",
    2: "N_GROUP",
    3: "NG_GROUP",
    4: "NY_GROUP",
    5: "P_GROUP",
    6: "S_GROUP",
    7: "T_GROUP",
    8: "C_GROUP",
    9: "Y_GROUP",
    10: "W_GROUP",
    11: "H_GROUP",
    12: "EU_GLIDE_GROUP",
    13: "L_GROUP",
    14: "E_GROUP",
    15: "I_GROUP",
    16: "O_GROUP",
    17: "U_GROUP",
    18: "A_GROUP",
    19: "AE_GROUP",
    20: "EU_GROUP",
    21: "EO_GROUP",
}

H_ALLOPHONES = {"h", "x", "ç", "ɣ", "ɦ", "ɸʷ", "ʝ", "β", "βʷ"}

# 예측발음의 복합 중성 한 토큰을 MFA가 쓰는 glide+vowel 단위로 펼친다.
# 원 토큰과 component index는 별도 열에 남기므로 정보가 사라지지 않는다.
PRON_TOKEN_EXPANSIONS = {
    "YA": ("Y", "A"),
    "YAE": ("Y", "AE"),
    "YEO": ("Y", "EO"),
    "YE": ("Y", "E"),
    "WA": ("W", "A"),
    "WAE": ("W", "AE"),
    "OE": ("W", "E"),
    "YO": ("Y", "O"),
    "WO": ("W", "EO"),
    "WE": ("W", "E"),
    "WI": ("W", "I"),
    "YU": ("Y", "U"),
    "UI": ("EU_G", "I"),
}


@dataclass(frozen=True)
class PhoneClass:
    phone_mfa: str
    phone_class_r_auto: str
    comparison_key: str
    model_group_id: int
    model_group_r: str
    has_length: bool
    secondary_articulation: str
    unreleased: bool


@dataclass(frozen=True)
class RomanUnit:
    display: str
    comparison_key: str
    source_token: str
    syllable_index: int
    token_index_in_syllable: int
    component_index: int
    component_count: int


@dataclass(frozen=True)
class AlignmentOp:
    operation: str
    status: str
    phone_index: int | None
    reference_index: int | None
    cost: float


def load_acoustic_meta(acoustic_model: Path) -> dict[str, object]:
    """동결 acoustic zip의 meta.json을 추출 없이 읽는다."""

    with zipfile.ZipFile(acoustic_model) as archive:
        candidates = [
            name for name in archive.namelist() if name.endswith("/meta.json")
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"acoustic meta.json 수가 1이 아님: {candidates}"
            )
        return json.loads(archive.read(candidates[0]).decode("utf-8"))


def model_group_lookup(meta: dict[str, object]) -> dict[str, int]:
    groups = meta.get("phone_groups")
    if not isinstance(groups, dict):
        raise RuntimeError("acoustic meta에 phone_groups가 없음")
    lookup: dict[str, int] = {}
    for raw_group, raw_phones in groups.items():
        group = int(raw_group)
        if group not in MODEL_GROUP_R:
            raise RuntimeError(f"알 수 없는 model phone group: {group}")
        if not isinstance(raw_phones, list):
            raise RuntimeError(f"phone group 형식 오류: {group}")
        for raw_phone in raw_phones:
            phone = str(raw_phone)
            if phone in lookup:
                raise RuntimeError(f"phone이 두 group에 존재: {phone}")
            lookup[phone] = group
    phones = {str(phone) for phone in meta.get("phones", [])}
    if phones != set(lookup):
        raise RuntimeError(
            "acoustic phones와 phone_groups coverage 불일치: "
            f"missing={sorted(phones-set(lookup))} "
            f"extras={sorted(set(lookup)-phones)}"
        )
    return lookup


def _strip_features(phone: str) -> str:
    return phone.replace("ː", "").replace("ʲ", "").replace("ʷ", "")


def _class_label(phone: str, group: int) -> str:
    base = _strip_features(phone)
    if phone in H_ALLOPHONES:
        return "H"
    if group == 0:
        if "ʰ" in base:
            return "K"
        if "͈" in base:
            return "KK"
        if "̚" in base:
            return "k"
        return "G"
    if group == 1:
        return "M"
    if group in {2, 4}:
        return "N"
    if group == 3:
        return "NG"
    if group == 5:
        if "ʰ" in base:
            return "P"
        if "͈" in base:
            return "PP"
        if "̚" in base:
            return "p"
        return "B"
    if group == 6:
        return "SS" if "͈" in base else "S"
    if group == 7:
        if "ʰ" in base:
            return "T"
        if "͈" in base:
            return "TT"
        if "̚" in base:
            return "t"
        return "D"
    if group == 8:
        if "ʰ" in base:
            return "CH"
        if "͈" in base:
            return "JJ"
        return "J"
    if group == 9:
        return "Y"
    if group == 10:
        return "W"
    if group == 11:
        return "H"
    if group == 12:
        return "EU_G"
    if group == 13:
        return "R" if base == "ɾ" else "l"
    vowel_labels = {
        14: "E",
        15: "I",
        16: "O",
        17: "U",
        18: "A",
        19: "AE",
        20: "EU",
        21: "EO",
    }
    if group in vowel_labels:
        return vowel_labels[group]
    raise RuntimeError(f"phone class 규칙 없음: phone={phone} group={group}")


def comparison_key(label: str) -> str:
    """초성/종성 위치 표기만 다른 같은 계열을 비교용으로 합친다."""

    return {
        "G": "G",
        "k": "G",
        "B": "B",
        "p": "B",
        "D": "D",
        "t": "D",
        "R": "L",
        "l": "L",
        "M": "M",
        "m": "M",
        "N": "N",
        "n": "N",
        "NG": "NG",
        "ng": "NG",
    }.get(label, label)


def classify_phone(phone: str, group_lookup: dict[str, int]) -> PhoneClass:
    if phone not in group_lookup:
        raise KeyError(f"acoustic inventory 밖 phone: {phone}")
    group = group_lookup[phone]
    label = _class_label(phone, group)
    secondary = ""
    if "ʲ" in phone:
        secondary += "palatalized"
    if "ʷ" in phone:
        secondary += ("+" if secondary else "") + "labialized"
    return PhoneClass(
        phone_mfa=phone,
        phone_class_r_auto=label,
        comparison_key=comparison_key(label),
        model_group_id=group,
        model_group_r=MODEL_GROUP_R[group],
        has_length="ː" in phone,
        secondary_articulation=secondary,
        unreleased="̚" in phone,
    )


def build_phone_inventory(meta: dict[str, object]) -> list[PhoneClass]:
    lookup = model_group_lookup(meta)
    result = [classify_phone(phone, lookup) for phone in sorted(lookup)]
    if len(result) != len(lookup):
        raise RuntimeError("phone inventory 중복")
    return result


def expand_roman_eojeol(value: str) -> list[RomanUnit]:
    """roman_mfa 어절을 phone 호환 단위로 펼친다."""

    value = str(value or "").strip()
    if not value or value == "∅":
        return []
    units: list[RomanUnit] = []
    for syllable_index, syllable in enumerate(value.split(" _ "), 1):
        tokens = [token for token in syllable.split() if token]
        for token_index, token in enumerate(tokens, 1):
            components = PRON_TOKEN_EXPANSIONS.get(token, (token,))
            for component_index, display in enumerate(components, 1):
                units.append(
                    RomanUnit(
                        display=display,
                        comparison_key=comparison_key(display),
                        source_token=token,
                        syllable_index=syllable_index,
                        token_index_in_syllable=token_index,
                        component_index=component_index,
                        component_count=len(components),
                    )
                )
    return units


def _substitution_cost(phone: PhoneClass, reference: RomanUnit) -> float:
    if phone.phone_class_r_auto == reference.display:
        return 0.0
    if phone.comparison_key == reference.comparison_key:
        return 0.2
    # 같은 acoustic decision-tree group 안의 차이는 경음/격음 등 중요한
    # 대립일 수 있으므로 자동 일치로 승인하지 않고 review 비용을 준다.
    broad = {
        "G": "K_GROUP",
        "k": "K_GROUP",
        "K": "K_GROUP",
        "KK": "K_GROUP",
        "B": "P_GROUP",
        "p": "P_GROUP",
        "P": "P_GROUP",
        "PP": "P_GROUP",
        "D": "T_GROUP",
        "t": "T_GROUP",
        "T": "T_GROUP",
        "TT": "T_GROUP",
        "J": "C_GROUP",
        "CH": "C_GROUP",
        "JJ": "C_GROUP",
        "S": "S_GROUP",
        "SS": "S_GROUP",
        "R": "L_GROUP",
        "l": "L_GROUP",
    }
    if broad.get(reference.display) == phone.model_group_r:
        return 1.2
    return 2.4


def align_phone_to_reference(
    phones: Sequence[PhoneClass], references: Sequence[RomanUnit]
) -> list[AlignmentOp]:
    """결정적 DP로 MFA phone과 예측발음 로마자 component를 대응한다."""

    n, m = len(phones), len(references)
    gap_cost = 1.5
    dp = [[math.inf] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str, float] | None]] = [
        [None] * (m + 1) for _ in range(n + 1)
    ]
    dp[0][0] = 0.0
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap_cost
        back[i][0] = (i - 1, 0, "phone_only", gap_cost)
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap_cost
        back[0][j] = (0, j - 1, "reference_only", gap_cost)
    # 동점이면 paired > phone_only > reference_only 순으로 고정한다.
    priority = {"paired": 0, "phone_only": 1, "reference_only": 2}
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = _substitution_cost(phones[i - 1], references[j - 1])
            candidates = [
                (dp[i - 1][j - 1] + sub, "paired", i - 1, j - 1, sub),
                (dp[i - 1][j] + gap_cost, "phone_only", i - 1, j, gap_cost),
                (dp[i][j - 1] + gap_cost, "reference_only", i, j - 1, gap_cost),
            ]
            best = min(candidates, key=lambda row: (row[0], priority[row[1]]))
            dp[i][j] = best[0]
            back[i][j] = (best[2], best[3], best[1], best[4])
    ops: list[AlignmentOp] = []
    i, j = n, m
    while i or j:
        prior = back[i][j]
        if prior is None:
            raise RuntimeError(f"alignment backtrace 없음: i={i} j={j}")
        pi, pj, operation, step_cost = prior
        phone_index = i - 1 if operation in {"paired", "phone_only"} else None
        reference_index = (
            j - 1 if operation in {"paired", "reference_only"} else None
        )
        if operation == "paired":
            phone = phones[phone_index]  # type: ignore[index]
            reference = references[reference_index]  # type: ignore[index]
            if phone.phone_class_r_auto == reference.display:
                status = "exact"
            elif phone.comparison_key == reference.comparison_key:
                status = "position_compatible"
            elif step_cost <= 1.2:
                status = "model_group_only"
            else:
                status = "substitution"
        else:
            status = operation
        ops.append(
            AlignmentOp(
                operation=operation,
                status=status,
                phone_index=phone_index,
                reference_index=reference_index,
                cost=step_cost,
            )
        )
        i, j = pi, pj
    ops.reverse()
    return ops


def split_roman_eojeols(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(" | ")]


def sequence_edit_count(left: Iterable[RomanUnit], right: Iterable[RomanUnit]) -> int:
    """철자/예측열 변화의 단순 Levenshtein 거리(설명용)."""

    a = [unit.comparison_key for unit in left]
    b = [unit.comparison_key for unit in right]
    prior = list(range(len(b) + 1))
    for i, left_value in enumerate(a, 1):
        current = [i]
        for j, right_value in enumerate(b, 1):
            current.append(
                min(
                    current[-1] + 1,
                    prior[j] + 1,
                    prior[j - 1] + (left_value != right_value),
                )
            )
        prior = current
    return prior[-1]

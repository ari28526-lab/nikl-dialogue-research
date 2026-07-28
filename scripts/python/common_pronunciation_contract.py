"""공통 발음 자원의 형태소 조건·정렬 backend 계약.

사전 발음 후보를 보존하는 일과 MFA 등 정렬 사전에 활성화하는 일을 분리한다.
특히 MFA의 일반 사전은 표층 word만 키로 사용하므로, 동형 어절의 형태소 구성이
다르면 표기 일치만으로 사전 발음을 전역 활성화하지 않는다.
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


CONTRACT_VERSION = "common_pron_resource_v2_20260728"
MORPH_MATCH_POLICY_VERSION = "strict_morph_match_v1"

PREDICATE_POS = frozenset({"VV", "VA", "VX", "VCP", "VCN"})
PUNCTUATION_POS = frozenset(
    {"SF", "SP", "SS", "SSO", "SSC", "SE", "SO", "SW", "SY"}
)
ELIGIBLE_OCCURRENCE_MATCHES = frozenset(
    {
        "exact_single_morph_pos",
        "predicate_dictionary_form_pos",
    }
)


@dataclass(frozen=True)
class Morph:
    surface: str
    pos: str


@dataclass(frozen=True)
class CandidateMatch:
    match_status: str
    occurrence_mfa_status: str
    reason: str
    morph_signature: str
    reconstructed_surface: str


def normalize_text(value: str | None) -> str:
    return unicodedata.normalize("NFKC", (value or "").strip())


def parse_tagged_group(tagged_group: str) -> tuple[Morph, ...]:
    """Bareun의 한 어절 ``형태/품사+형태/품사``를 보수적으로 읽는다."""

    value = normalize_text(tagged_group)
    if not value:
        raise ValueError("빈 tagged 어절")
    result: list[Morph] = []
    for part in value.split("+"):
        if "/" not in part:
            raise ValueError(f"형태/품사 구분자가 없는 tagged 조각: {part!r}")
        surface, pos = part.rsplit("/", 1)
        surface = surface.strip()
        pos = pos.strip()
        if not surface or not pos:
            raise ValueError(f"비어 있는 형태 또는 품사: {part!r}")
        result.append(Morph(surface=surface, pos=pos))
    return tuple(result)


def morph_signature(morphs: Iterable[Morph]) -> str:
    return "+".join(f"{m.surface}/{m.pos}" for m in morphs)


def content_morphs(morphs: Iterable[Morph]) -> tuple[Morph, ...]:
    return tuple(m for m in morphs if m.pos not in PUNCTUATION_POS)


def reconstructed_surface(morphs: Iterable[Morph]) -> str:
    return "".join(m.surface for m in content_morphs(morphs))


def classify_dictionary_candidate(
    *,
    token: str,
    lexicon_pos: str,
    tagged_group: str,
) -> CandidateMatch:
    """사전 후보가 한 occurrence의 형태소 분석과 양립하는지 판정한다.

    이 판정은 사전 후보를 삭제하지 않는다. 부적합 후보도 registry와 검색용
    CSV에는 남고, plain-word MFA 사전의 자동 활성화만 차단한다.
    """

    token = normalize_text(token)
    lexicon_pos = normalize_text(lexicon_pos)
    try:
        parsed = parse_tagged_group(tagged_group)
    except ValueError as exc:
        return CandidateMatch(
            match_status="tagged_parse_error",
            occurrence_mfa_status="reference_only",
            reason=str(exc),
            morph_signature=normalize_text(tagged_group),
            reconstructed_surface="",
        )

    signature = morph_signature(parsed)
    morphs = content_morphs(parsed)
    surface = reconstructed_surface(morphs)
    if not token:
        return CandidateMatch(
            match_status="empty_token",
            occurrence_mfa_status="reference_only",
            reason="사전 token이 비어 있음",
            morph_signature=signature,
            reconstructed_surface=surface,
        )
    if surface != token:
        return CandidateMatch(
            match_status="token_group_surface_mismatch",
            occurrence_mfa_status="reference_only",
            reason="MFA token과 tagged 어절의 형태 결합이 일치하지 않음",
            morph_signature=signature,
            reconstructed_surface=surface,
        )
    if not lexicon_pos:
        return CandidateMatch(
            match_status="lexicon_pos_missing",
            occurrence_mfa_status="reference_only",
            reason="사전 품사가 없어 형태소 조건을 확인할 수 없음",
            morph_signature=signature,
            reconstructed_surface=surface,
        )

    if len(morphs) == 1:
        morph = morphs[0]
        if morph.surface == token and morph.pos == lexicon_pos:
            return CandidateMatch(
                match_status="exact_single_morph_pos",
                occurrence_mfa_status="eligible_occurrence_candidate",
                reason="단일 형태소 표면형과 품사가 사전 표제어와 정확히 일치",
                morph_signature=signature,
                reconstructed_surface=surface,
            )
        return CandidateMatch(
            match_status="surface_only_pos_mismatch",
            occurrence_mfa_status="reference_only",
            reason=(
                f"표면형은 같지만 Bareun 품사 {morph.pos}와 "
                f"사전 품사 {lexicon_pos}가 다름"
            ),
            morph_signature=signature,
            reconstructed_surface=surface,
        )

    if (
        len(morphs) == 2
        and morphs[0].pos in PREDICATE_POS
        and morphs[1].surface == "다"
        and morphs[1].pos == "EF"
        and morphs[0].pos == lexicon_pos
    ):
        return CandidateMatch(
            match_status="predicate_dictionary_form_pos",
            occurrence_mfa_status="eligible_occurrence_candidate",
            reason="용언 어간+다/EF가 사전 -다 표제어와 품사까지 일치",
            morph_signature=signature,
            reconstructed_surface=surface,
        )

    return CandidateMatch(
        match_status="surface_only_morphologically_composed",
        occurrence_mfa_status="reference_only",
        reason=(
            "표면 철자는 같지만 여러 형태소로 구성되어 단일 사전 표제어의 "
            "발음을 이 occurrence에 적용할 근거가 없음"
        ),
        morph_signature=signature,
        reconstructed_surface=surface,
    )


def decide_global_plain_word_activation(
    match_statuses: Iterable[str],
    *,
    full_occurrence_audit_complete: bool,
) -> tuple[str, str]:
    """MFA plain-word 키에 후보를 전역 활성화할 수 있는지 판정한다."""

    counts = Counter(match_statuses)
    if not full_occurrence_audit_complete:
        return (
            "pending_full_occurrence_audit",
            "일부 표본만으로 같은 철자의 전 occurrence에 적용할 수 없음",
        )
    if not counts:
        return (
            "reference_only_no_occurrences",
            "동결 코퍼스에서 해당 표층 token의 occurrence가 없음",
        )
    incompatible = {
        status: count
        for status, count in counts.items()
        if status not in ELIGIBLE_OCCURRENCE_MATCHES
    }
    if incompatible:
        detail = ",".join(
            f"{status}:{count}" for status, count in sorted(incompatible.items())
        )
        return (
            "reference_only_mixed_or_unresolved_morphology",
            f"plain-word 전역 적용과 양립하지 않는 occurrence가 있음({detail})",
        )
    return (
        "eligible_global_plain_word_candidate",
        "동결 코퍼스의 모든 occurrence가 엄격 형태소 조건을 통과",
    )

#!/usr/bin/env python3
"""Extend the Stage2 claim ledger and derive systematic seven-phenomena cards.

The script is append-only for the canonical claim ledger and replace-by-verified-
derivation for the candidate v2 scope-card file.  It never edits source PDFs,
frozen v1 cards, corpus assets, or researcher review JSONL files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from extend_stage2_nan_prosody_literature import extend_claims as extend_nan_claims


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLAIMS = PROJECT_ROOT / "work/literature_evidence_seven_phenomena_20260822/02_claims/CLAIM_EVIDENCE.jsonl"
DEFAULT_CARDS_INPUT = PROJECT_ROOT / "config/phenomenon_scope_cards_candidate_v1_20260823.jsonl"
DEFAULT_CARDS_OUTPUT = PROJECT_ROOT / "config/phenomenon_scope_cards_candidate_v2_20260824.jsonl"
DEFAULT_FACTORS = PROJECT_ROOT / "config/phenomenon_factor_maps_candidate_v1_20260824.json"


def claim(
    claim_id: str,
    ref_id: str,
    source_id: str,
    source_file: str,
    source_sha256: str,
    citation: str,
    claim_kind: str,
    phenomenon_codes: list[str],
    link_scope: str,
    relation: str,
    claim_ko: str,
    printed_page: int | str,
    pdf_page: int,
    applies_when: str,
    does_not_establish: str,
    review_question: str,
    future_layer: str,
    confidence: str,
    needs_human_check: bool,
    extraction_note: str,
) -> dict[str, Any]:
    return {
        "schema_version": "reference_evidence.v2",
        "claim_id": claim_id,
        "ref_id": ref_id,
        "source_id": source_id,
        "source_file": source_file,
        "source_sha256": source_sha256,
        "citation": citation,
        "evidence_owner": "paper_author",
        "claim_kind": claim_kind,
        "phenomenon_codes": phenomenon_codes,
        "link_scope": link_scope,
        "relation": relation,
        "claim_ko": claim_ko,
        "printed_page": printed_page,
        "pdf_page": pdf_page,
        "page_locator_status": "verified",
        "applies_when": applies_when,
        "does_not_establish": does_not_establish,
        "review_question": review_question,
        "future_layer": future_layer,
        "confidence": confidence,
        "needs_human_check": needs_human_check,
        "extraction_note": extraction_note,
    }


PT_FILE = "00_참고문헌/사잇소리/Kim_Kang_2017_The Prosodic Effect of Compound Tensification in Korean.pdf"
PT_SHA = "4d7656419ca825267b8c243185014d4a8a47e7b9eee6122393f4661efbce48f5"
NI15_FILE = "00_참고문헌/ㄴ삽입/Jun_2015_Korean n-insertion a mismatch between data and learning.pdf"
NI15_SHA = "1003b242401411dfd1d117bc399271803439897f97abfb47f384a22232258e52"
NI21_FILE = "00_참고문헌/ㄴ삽입/Jun_2021_Gradient patterns of Korean n-insertion.pdf"
NI21_SHA = "cbf65f79ae350d15ba8a27b9772bda3b5264133866f2d484d70f37dd7c35892d"
AMP_FILE = "00_참고문헌/0000_형태론세미나_리딩/W11_유음의_비음화_유음화_비음화복합형/Jun-Yee-Yim_2024_AMP.pdf"
AMP_SHA = "640c2652cd2aaa3a7d218de696a33a4296f8ac38987853caaafd4b0e05fe106d"
PMCK_FILE = "00_참고문헌/0000_형태론세미나_리딩/W11_유음의_비음화_유음화_비음화복합형/Jun_2025_ho_PMCK.pdf"
PMCK_SHA = "b0c538a4c2f1cb27a4d000b0f5220c4b289182f7b3da4634bb19c93315103b73"


ADDITIONAL_CLAIMS = [
    claim(
        "CLM-0163", "kim_kang2017_pt_design", "SRC-313", PT_FILE, PT_SHA,
        "Kim, Yeonju & Hijo Kang (2017). The Prosodic Effect of Compound Tensification in Korean. Studies in Linguistics 45, 1–27.",
        "methodology", ["PT"], "direct_evidence", "direct",
        "서울·광주 화자 12명의 산출에서 합성어 파생 경음, 단일어 기저 경음, 단일어 평음을 비교하고 선행 모음·종성·폐쇄·후행 모음 길이와 선행 구간 F0를 측정했다.",
        1, 1,
        "합성어 경음화를 평음·기저 경음과 음향적으로 비교할 판정 항목을 설계할 때",
        "자연대화의 모든 합성어 유형, 필수 저해음 뒤 경음화, 또는 개별 토큰의 경음 실현을 자동 판정하는 기준",
        "PT 사례에서 폐쇄·VOT·F0뿐 아니라 선행 음절과 전체 표현 길이를 별도 관찰했는가?",
        "PT_measurement", "high", False,
        "PDF 1면 초록과 8–9면 방법을 시각 대조함.",
    ),
    claim(
        "CLM-0164", "kim_kang2017_pt_duration", "SRC-313", PT_FILE, PT_SHA,
        "Kim, Yeonju & Hijo Kang (2017). The Prosodic Effect of Compound Tensification in Korean. Studies in Linguistics 45, 1–27.",
        "acoustic_result", ["PT"], "direct_evidence", "direct",
        "평음보다 기저·파생 경음의 폐쇄가 길었고, 합성어 파생 경음과 단일어 기저 경음의 차이는 주로 파생 경음 앞 음절(모음 또는 종성)이 더 길다는 데서 나타났다.",
        16, 16,
        "합성어 파생 경음과 단일어 기저 경음을 구분해 길이 단서를 해석할 때",
        "선행 음절 장음화 하나가 합성어 경음화를 필요충분하게 판정한다는 것 또는 자연대화에서 동일 효과 크기",
        "후행 자음의 경음성 단서와 합성어 경계 단서를 같은 값으로 합치지 않았는가?",
        "PT_measurement", "high", False,
        "PDF/인쇄 16면의 결과와 그림 14를 시각 대조함.",
    ),
    claim(
        "CLM-0165", "kim_kang2017_pt_pitch_limit", "SRC-313", PT_FILE, PT_SHA,
        "Kim, Yeonju & Hijo Kang (2017). The Prosodic Effect of Compound Tensification in Korean. Studies in Linguistics 45, 1–27.",
        "limitation", ["PT"], "direct_evidence", "direct",
        "이 연구의 짧은 목표어에서는 합성어와 단일어를 구분하는 데 길이가 F0보다 더 일관된 단서였으며, 저자들은 더 많은 화자·더 긴 단어·쌍비음 합성어·더 나이 든 화자의 추가 연구가 필요하다고 밝혔다.",
        21, 21,
        "PT 음향 단서의 우선순위와 연구 설계 한계를 정할 때",
        "F0가 한국어 경음성이나 합성어 경계에서 일반적으로 무의미하다는 것",
        "자연대화에서 F0 비효과를 미리 가정하지 않고 길이·F0를 모두 보존했는가?",
        "PT_limitations", "high", False,
        "PDF/인쇄 21면을 시각 대조함.",
    ),
    claim(
        "CLM-0166", "jun2015_ni_gradient_factors", "SRC-257", NI15_FILE, NI15_SHA,
        "Jun, Jongho (2015). Korean n-insertion: a mismatch between data and learning. Phonology 32(3), 417–458.",
        "environment_condition", ["NI"], "direct_evidence", "direct",
        "서울말 ㄴ삽입은 자음말 형태소와 후행 /i, j/ 사이에서 수의적으로 나타나며, 기존 단어에서는 /j/가 /i/보다, /j/ 뒤 고모음이 비고모음보다 삽입을 더 촉진하고, 저해음과 /ŋ/은 다른 공명음보다 억제하며, 선행 형태소 길이 효과도 관찰된다.",
        418, 2,
        "NI 표본을 음운 환경과 형태소 길이로 층화할 때",
        "각 요인이 절대 조건이라는 것 또는 모든 기존 단어 경향이 화자의 생산 문법으로 일반화된다는 것",
        "/i/·/j/, /j/ 뒤 모음 높이, M1 말음, M1 길이를 서로 다른 열로 기록했는가?",
        "NI_factor_map", "high", False,
        "인쇄 418쪽(PDF 2면)을 시각 대조함.",
    ),
    claim(
        "CLM-0167", "jun2015_ni_learning_mismatch", "SRC-257", NI15_FILE, NI15_SHA,
        "Jun, Jongho (2015). Korean n-insertion: a mismatch between data and learning. Phonology 32(3), 417–458.",
        "limitation", ["NI"], "direct_evidence", "direct",
        "새 단어 실험은 기존 단어의 여러 음운 경향을 재현했지만 선행 형태소 길이 효과는 재현하지 않아, 어휘 통계와 화자가 일반화한 경향을 구분해야 한다.",
        453, 37,
        "기존 어휘 분포를 생산성 또는 자연대화의 인과 요인으로 해석할 때",
        "길이가 기존 단어 분포에도 영향이 없다는 것 또는 다른 형태론·어휘 요인이 학습되지 않는다는 것",
        "코퍼스 상관, 기존 단어 판단, 새 단어 일반화를 같은 근거 수준으로 합치지 않았는가?",
        "NI_evidence_level", "high", False,
        "인쇄 453쪽(PDF 37면)을 시각 대조함.",
    ),
    claim(
        "CLM-0168", "jun2021_ni_morphophonological_gradience", "SRC-258", NI21_FILE, NI21_SHA,
        "Jun, Jongho (2021). Morphophonological gradience in Korean n-insertion. Glossa 6(1): 40, 1–40.",
        "environment_condition", ["NI"], "direct_evidence", "direct",
        "서울·경상 방언의 기존·새 단어 조사는 구성 형태소의 형태론적 범주·어원·길이, 선행 자음의 공명성·조음 위치, 후행 형태소 첫 모음 높이, 방언과 그 상호작용이 ㄴ삽입 확률에 점진적으로 기여하며 어느 하나도 절대 조건이 아니라고 보고한다.",
        1, 1,
        "NI를 형태음운론적 확률 현상으로 설계하고 표본 요인을 정할 때",
        "모든 요인의 독립 효과가 모든 방언·과제·어휘에서 동일하거나 인과적으로 확정됐다는 것",
        "M1·M2 형태론 범주와 어원, 길이, C1, V2, 방언을 표집과 분석에서 분리했는가?",
        "NI_factor_map", "high", False,
        "PDF 1면 초록을 시각 대조함.",
    ),
    claim(
        "CLM-0169", "jun2021_ni_task_dialect_limit", "SRC-258", NI21_FILE, NI21_SHA,
        "Jun, Jongho (2021). Morphophonological gradience in Korean n-insertion. Glossa 6(1): 40, 1–40.",
        "limitation", ["NI"], "direct_evidence", "direct",
        "저자는 젊은 경상 방언 화자의 서울말 친숙도, 문자·판단 과제의 양식, 서울말 표준 단어만을 사용한 자극 때문에 방언 차이가 축소되거나 서울말 지식이 개입했을 수 있다고 지적한다.",
        37, 37,
        "NI의 방언·세대·과제 효과를 자연대화에 외삽할 때",
        "경상·서울 차이가 없다는 것 또는 자연대화에서도 문자 과제와 동일한 효과가 난다는 것",
        "화자 지역·연령과 과제·장르를 기록하고 표준어 어휘 편향을 표시했는가?",
        "NI_limitations", "high", False,
        "PDF/인쇄 37면의 방법론적 한계를 시각 대조함.",
    ),
    claim(
        "CLM-0170", "jun_yee_yim2024_nal_aerodynamic", "SRC-055", AMP_FILE, AMP_SHA,
        "Jun, Jongho, Jieun Yee & Sua Yim (2024). Unnatural sonorant assimilation in Korean: an aerodynamic study. AMP poster.",
        "acoustic_result", ["NAL"], "direct_evidence", "direct",
        "서울말 화자 17명의 비강·구강 기류 실험은 장애음+/ㄹ/에서 후행 유음의 비음화는 수의적이지만, 후행 [l]이 유지된 경우에도 선행 장애음의 비음화가 나타날 수 있음을 보고한다.",
        1, 1,
        "NAL에서 C2 유음 비음화와 C1 장애음 비음화를 독립 판정할 때",
        "자연대화·전 연령·모든 어휘에서 같은 비율, 또는 청취만으로 공기역학적 비음화를 확정할 수 있다는 것",
        "후행 /l/의 [n]/[l] 판정과 선행 장애음의 비음화 판정을 두 칸으로 분리했는가?",
        "NAL_realization", "medium", True,
        "1면 학회 포스터 원문을 시각·텍스트 대조함. 학회 포스터이므로 동료심사 논문과 구분함.",
    ),
    claim(
        "CLM-0171", "jun_yee_yim2024_nal_design", "SRC-055", AMP_FILE, AMP_SHA,
        "Jun, Jongho, Jieun Yee & Sua Yim (2024). Unnatural sonorant assimilation in Korean: an aerodynamic study. AMP poster.",
        "methodology", ["NAL"], "direct_evidence", "direct",
        "실험은 KL·KN·NN·NL·LK·LL 여섯 연쇄 유형의 실제 단어를 유형당 10개씩 읽게 하고 정규화 비강기류 궤적을 비교하여 청취 전사만으로는 놓칠 수 있는 부분 비음화를 측정했다.",
        1, 1,
        "NAL 음향·공기역학 검증의 비교 조건과 한계를 설계할 때",
        "현재 reviewer의 WAV·TextGrid만으로 비강기류를 직접 측정할 수 있다는 것",
        "현재 파일럿에서 청취 판정과 장비가 필요한 후속 공기역학 판정을 구분했는가?",
        "NAL_method", "medium", True,
        "1면 학회 포스터 방법 섹션을 대조함.",
    ),
    claim(
        "CLM-0172", "jun2025_nal_segment_boundary_limit", "SRC-056", PMCK_FILE, PMCK_SHA,
        "Jun, Jongho (2025). Preliquid nasalization revisited. Phonology-Morphology Circle of Korea presentation, 15 March 2025.",
        "limitation", ["NAL"], "direct_evidence", "direct",
        "발표 자료는 C1과 C2의 음향·청각 경계가 흔히 불명확하여 기류 궤적을 초기 2/3과 후기 1/3로 나눈 것이 분석상 불가피한 근사였다고 명시한다.",
        77, 77,
        "NAL의 C1·C2 구간을 TextGrid에서 나누거나 부분 비음화를 판정할 때",
        "2/3–1/3 분할이 자연적 분절 경계이거나 현재 자료에 그대로 적용해야 한다는 것",
        "분절 경계가 불명확하면 수치 경계를 억지로 확정하지 않고 불확실성을 보존했는가?",
        "NAL_measurement_limit", "medium", True,
        "발표 슬라이드 77면을 텍스트·시각 대조 대상으로 지정. 미출판 발표 자료임.",
    ),
    claim(
        "CLM-0173", "jun2025_nal_aerodynamic_replication", "SRC-056", PMCK_FILE, PMCK_SHA,
        "Jun, Jongho (2025). Preliquid nasalization revisited. Phonology-Morphology Circle of Korea presentation, 15 March 2025.",
        "acoustic_result", ["NAL"], "direct_evidence", "direct",
        "발표 자료의 공기역학 분석은 KL 연쇄 후기의 비강기류가 KN보다 낮아 /l/ 비음화가 수의적임을 보이면서도, KL 초기부는 KN과 차이가 없어 표면 비비음 유음 앞에서도 선행 장애음 비음화가 나타난다는 해석을 제시한다.",
        124, 124,
        "NAL의 두 종속 판정과 Jun·Seo 결과의 반복 확인을 문헌 지도에 표시할 때",
        "동료심사 완료, 자연대화 일반화, 또는 모든 KL 토큰의 범주적 동일 실현",
        "이 결과를 학회 발표 수준의 직접 근거로 표시하고 후속 출판본을 찾도록 남겼는가?",
        "NAL_evidence_level", "medium", True,
        "슬라이드 82·85·87·124면의 결과와 결론을 대조함. 대표 locator는 결론 124면.",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def atomic_write(path: Path, text: str) -> None:
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


def append_additional_claims(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_id = {row["claim_id"]: row for row in rows}
    ids = [row["claim_id"] for row in ADDITIONAL_CLAIMS]
    present = [claim_id for claim_id in ids if claim_id in by_id]
    if present != ids[: len(present)]:
        raise ValueError(f"non-prefix all-phenomena extension: {present}")
    for expected in ADDITIONAL_CLAIMS[: len(present)]:
        if by_id[expected["claim_id"]] != expected:
            raise ValueError(f"existing claim differs: {expected['claim_id']}")
    if len(present) == len(ids):
        return {"status": "already_applied", "rows": len(rows), "sha256": sha256(path)}
    expected_last = 162 + len(present)
    if len(rows) != expected_last or rows[-1]["claim_id"] != f"CLM-{expected_last:04d}":
        raise ValueError("unexpected claim ledger before all-phenomena append")
    rows.extend(ADDITIONAL_CLAIMS[len(present):])
    atomic_write(path, jsonl_text(rows))
    return {"status": "appended", "rows": len(rows), "sha256": sha256(path)}


def update_cards(input_path: Path, output_path: Path, factors_path: Path) -> dict[str, Any]:
    cards = read_jsonl(input_path)
    factor_doc = json.loads(factors_path.read_text(encoding="utf-8"))
    factors = {item["phenomenon_code"]: item for item in factor_doc["phenomena"]}
    expected = ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]
    if [row["phenomenon_code"] for row in cards] != expected or list(factors) != expected:
        raise ValueError("seven-phenomena order mismatch")
    updated = []
    claim_refs = {
        "PT": ["CLM-0163", "CLM-0164", "CLM-0165"],
        "NAN": ["CLM-0061", "CLM-0157", "CLM-0158", "CLM-0159", "CLM-0160", "CLM-0161", "CLM-0162"],
        "NAL": ["CLM-0170", "CLM-0171", "CLM-0172", "CLM-0173"],
        "NI": ["CLM-0166", "CLM-0167", "CLM-0168", "CLM-0169"],
        "LLN": [], "VH": [], "HIA": [],
    }
    for card in cards:
        value = json.loads(json.dumps(card, ensure_ascii=False))
        code = value["phenomenon_code"]
        fmap = factors[code]
        value["schema_version"] = "stage2_two_hour_phenomenon_pilot_card.v2"
        value["card_id"] = f"P2H-{code}-V2"
        value["label_ko"] = fmap["label_ko"]
        value["evidence_refs"] = list(dict.fromkeys([*value.get("evidence_refs", []), *claim_refs[code]]))
        value["research_question_map"] = {
            "questions": fmap["research_questions"],
            "scope_families": fmap["scope_families"],
            "factor_dimensions": fmap["factor_dimensions"],
            "sampling_requirements": fmap["sampling_requirements"],
            "seminar_seed_sources": fmap["seminar_seed_sources"],
            "additional_direct_sources": fmap["additional_direct_sources"],
            "status": "candidate_pending_researcher_adoption",
        }
        value["sidecar_candidates"] = list(dict.fromkeys([
            *value.get("sidecar_candidates", []),
            *[field for fields in fmap["factor_dimensions"].values() for field in fields],
        ]))
        if code == "PT":
            value["definition_summary"] = "저해음 뒤 경음화의 필수적 기준층과 합성어·사이시옷 관련 변이층을 분리하고, 합성어이면서 저해음 뒤인 사례는 중첩층으로 복수 태깅한다."
            value["population_contract"] = {
                "primary": [
                    {"condition_id": "PT_PRI_POST_OBSTRUENT_BASELINE", "description": "저해음 종성 뒤 기저 평장애음의 기준층: 단일어 내부·어간+어미·체언+조사·파생을 형태소 유형별로 분리", "priority": 1, "evidence_refs": ["CLM-0163", "CLM-0164"], "status": "new_required_candidate"},
                    {"condition_id": "PT_PRI_COMPOUND_VARIABLE", "description": "모음·공명음말 합성어 경계의 평음~경음 변이", "priority": 1, "evidence_refs": ["CLM-0023", "CLM-0029", "CLM-0035", "CLM-0164"], "status": "literature_seeded_candidate"},
                ],
                "peripheral": [
                    {"condition_id": "PT_PER_COMPOUND_POST_OBSTRUENT_OVERLAP", "description": "합성어이면서 저해음 뒤여서 자동 경음화·합성어 경음화·사이시옷 해석이 중첩되는 사례", "priority": 2, "evidence_refs": ["CLM-0041", "CLM-0059"], "status": "multiple_membership_required"},
                    {"condition_id": "PT_PER_LEXICALIZED", "description": "어휘화·합성어성 판단이 흔들리는 직접 보고 어휘", "priority": 2, "evidence_refs": ["CLM-0037", "CLM-0040", "CLM-0052"], "status": "literature_seeded_candidate"},
                ],
                "exploratory": [
                    {"condition_id": "PT_EXP_INTER_EOJEOL", "description": "어절 간 저해음#평장애음과 운율 경계", "priority": 3, "evidence_refs": ["CLM-0160"], "status": "pending_probe"}
                ],
                "out_of_scope": [
                    {"condition_id": "PT_OUT_UNDERLYING_TENSE", "description": "후행 자음이 기저 경음인 어휘", "priority": 4, "evidence_refs": ["CLM-0163"], "status": "pending_probe"},
                    {"condition_id": "PT_OUT_H_ASPIRATION", "description": "ㅎ·ㄶ·ㅀ 관련 격음화가 핵심인 사례", "priority": 4, "evidence_refs": ["CLM-0059"], "status": "pending_probe"},
                ],
                "unclear": [
                    {"condition_id": "PT_UNC_COMPOUNDNESS_OR_OVERLAP", "description": "합성어성·형태소 경계·사이시옷·저해음 뒤 기준층의 소속을 현재 자료로 확정할 수 없는 사례", "priority": 4, "evidence_refs": ["CLM-0041"], "status": "pending_probe"}
                ],
            }
            value["evidence_limits"] = [
                "기존 v2 PT 12건은 단일 NNG 내부 음절쌍 compoundness probe가 대부분이며 저해음 뒤 기준층과 형태소·품사별 균형 표본이 아니다.",
                "합성어 저해음말 사례는 자동 저해음 뒤 경음화와 합성어·사이시옷 해석이 중첩되므로 배타적으로 분류하지 않는다.",
                "Kim·Kang(2017)의 읽기 실험 음향 결과를 자연대화 모든 토큰의 자동 판정 기준으로 쓰지 않는다.",
            ]
        elif code == "NAN":
            value["definition_summary"] = "저해음 종성과 후행 /ㄴ·ㅁ/의 필수적 기준층을 형태소·품사 조건별로 구성하고, 어절 간 연쇄는 운율경계 민감 탐색층으로 분리한다."
            value["evidence_refs"] = claim_refs[code]
            value["boundary_scopes"] = [
                {"name": "단일어·형태소 내부 및 어절 내부 저해음+/ㄴ/", "status": "primary_required", "evidence_refs": ["CLM-0061"]},
                {"name": "어절 내부 저해음+/ㅁ/", "status": "primary_required_extension", "evidence_refs": ["CLM-0061"]},
                {"name": "어절 간 저해음#/ㄴ·ㅁ/", "status": "separate_prosody_population", "evidence_refs": ["CLM-0157", "CLM-0158", "CLM-0159", "CLM-0161"]},
            ]
            value["population_contract"] = {
                "primary": [
                    {"condition_id": "NAN_PRI_OBS_N_INTRA", "description": "저해음+/ㄴ/ 어절 내부 기준층: 단일어·어간+어미·체언+접사/조사·합성을 분리", "priority": 1, "evidence_refs": ["CLM-0061"], "status": "required_candidate"},
                    {"condition_id": "NAN_PRI_OBS_M_INTRA", "description": "저해음+/ㅁ/ 어절 내부 필수 비교층", "priority": 1, "evidence_refs": ["CLM-0061"], "status": "new_required_candidate"},
                ],
                "peripheral": [
                    {"condition_id": "NAN_PER_INTER_EOJEOL_PROSODY", "description": "어절 간 저해음#/ㄴ·ㅁ/을 AP/IP 단서와 함께 보는 별도 모집단", "priority": 2, "evidence_refs": ["CLM-0157", "CLM-0158", "CLM-0159", "CLM-0161"], "status": "literature_seeded_candidate"}
                ],
                "exploratory": [
                    {"condition_id": "NAN_EXP_AFTER_N_INSERTION", "description": "NI 적용 뒤 생긴 비음 연쇄를 복수 membership으로 기록", "priority": 3, "evidence_refs": ["CLM-0166"], "status": "pending_probe"}
                ],
                "out_of_scope": [
                    {"condition_id": "NAN_OUT_UNDERLYING_NASAL_C1", "description": "선행 종성이 기저 비음이라 저해음 비음화가 성립하지 않는 연쇄", "priority": 4, "evidence_refs": [], "status": "pending_probe"}
                ],
                "unclear": [
                    {"condition_id": "NAN_UNC_PARTIAL_OR_BOUNDARY", "description": "부분 비음화·기저/삽입 ㄴ·운율 경계를 확정할 수 없는 사례", "priority": 4, "evidence_refs": ["CLM-0159", "CLM-0161"], "status": "pending_probe"}
                ],
            }
            value["evidence_limits"] = [
                "기존 NAN 장부에는 NAL·LLN 인접 주장이 섞여 있었으므로 CLM-0064·0069·0071·0072·0074·0075·0077을 NAN 직접 근거로 사용하지 않는다.",
                "신지영(2011)의 어절 간 예시는 운율경계 대비를 직접 제시하지만 자연대화 전수 확률과 부분 비음화 음향 기준은 확립하지 않는다.",
                "Jun(1998)은 직접 장애음 비음화 실험이 아니라 방법론·선행 연구 지시이므로 Jun(1992/1993) 원전 확보가 남아 있다.",
                "현재 v2 12건은 /ㄴ/ 중심이므로 후행 /ㅁ/과 형태소·품사별 필수 기준층을 추가 표집해야 한다.",
            ]
        elif code == "NI":
            value["evidence_limits"] = list(dict.fromkeys([*value["evidence_limits"], "Jun(2015/2021)은 요인들이 점진적으로 기여하며 어느 하나도 절대 조건이 아니라고 보고하므로 범주적 자동 분류에 쓰지 않는다.", "기존 단어의 길이·빈도 경향이 새 단어에서 재현되지 않을 수 있어 어휘 분포와 생산성 근거를 분리한다."]))
        elif code == "NAL":
            value["evidence_limits"] = list(dict.fromkeys([*value["evidence_limits"], "Jun·Yee·Yim(2024) 포스터와 Jun(2025) 발표는 직접 공기역학 근거이지만 미출판·비동료심사 자료로 별도 표시한다.", "후행 유음의 비음화와 선행 장애음의 비음화는 독립 판정이어야 하며 C1/C2 경계 자체가 불명확할 수 있다."]))
        updated.append(value)
    atomic_write(output_path, jsonl_text(updated))
    return {"status": "derived", "rows": len(updated), "sha256": sha256(output_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--cards-input", type=Path, default=DEFAULT_CARDS_INPUT)
    parser.add_argument("--cards-output", type=Path, default=DEFAULT_CARDS_OUTPUT)
    parser.add_argument("--factors", type=Path, default=DEFAULT_FACTORS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nan = extend_nan_claims(args.claims.resolve())
    additional = append_additional_claims(args.claims.resolve())
    cards = update_cards(args.cards_input.resolve(), args.cards_output.resolve(), args.factors.resolve())
    print(json.dumps({"nan_claims": nan, "additional_claims": additional, "cards": cards}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

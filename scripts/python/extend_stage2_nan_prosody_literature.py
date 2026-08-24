from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLAIMS = PROJECT_ROOT / (
    "work/literature_evidence_seven_phenomena_20260822/02_claims/"
    "CLAIM_EVIDENCE.jsonl"
)
DEFAULT_CARDS_INPUT = PROJECT_ROOT / "config/phenomenon_scope_cards_candidate_v1_20260823.jsonl"
DEFAULT_CARDS_OUTPUT = PROJECT_ROOT / "config/phenomenon_scope_cards_candidate_v2_20260824.jsonl"

JUN_FILE = (
    "00_참고문헌/03_운율_초점_음성변이/"
    "Jun_1998_The Accentual Phrase in the Korean prosodic hierarchy.pdf"
)
SHIN_FILE = "00_참고문헌/03_운율_초점_음성변이/신지영_2011_한국어의운율.pdf"
JUN_SHA = "25827f7985605e356eef50736ce0089e3ad0747ce80d57bd9225ee5977c28335"
SHIN_SHA = "cb9463b3e251ecba50f8408035ededceb7fc7b57a9f4a0724cefc1422edd1b5d"


NEW_CLAIMS: list[dict[str, Any]] = [
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0157",
        "ref_id": "shin2011_nan_prosodic_domain",
        "source_id": "SRC-362",
        "source_file": SHIN_FILE,
        "source_sha256": SHIN_SHA,
        "citation": "신지영(2011). 「한국어의 운율」, 『한국어의 말소리』 제8장, 221–264쪽.",
        "evidence_owner": "paper_author",
        "claim_kind": "environment_condition",
        "phenomenon_codes": ["NAN"],
        "link_scope": "direct_evidence",
        "relation": "direct",
        "claim_ko": (
            "어절 간 '미역국 누가'의 /ㄱ#ㄴ/ 연쇄는 두 음운단어 사이에 억양구 경계가 "
            "놓이면 선행 /ㄱ/이 유지되고, 음운구 경계에서는 [ㅇ]으로 비음화된다. 저자는 "
            "이를 장애음 비음화가 억양구 경계보다 작은, 곧 음운구 이하 경계에서 적용되는 "
            "운율 단위 민감 현상으로 정리한다."
        ),
        "printed_page": 257,
        "pdf_page": 35,
        "page_locator_status": "verified",
        "applies_when": "서로 다른 음운단어에 속한 장애음 종성과 후행 비음이 연쇄되는 어절 간 환경",
        "does_not_establish": (
            "자연대화의 모든 어절 간 토큰에서 경계와 비음화가 범주적으로 일대일 대응한다는 것, "
            "부분 비음화의 음향 기준, 또는 ㄴ 앞 환경만의 확률"
        ),
        "review_question": (
            "각 어절 간 NAN 사례에서 두 표적 어절이 같은 억양구 안인지, 억양구 경계로 갈리는지 "
            "독립적으로 기록했을 때 비음화 실현과 대응하는가?"
        ),
        "future_layer": "L2_environment_map",
        "confidence": "high",
        "needs_human_check": False,
        "extraction_note": "인쇄 256–257쪽의 예 (16)–(17)과 바로 뒤 일반화. PDF 34–35면을 시각 대조함.",
    },
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0158",
        "ref_id": "shin2011_ip_boundary_cues",
        "source_id": "SRC-362",
        "source_file": SHIN_FILE,
        "source_sha256": SHIN_SHA,
        "citation": "신지영(2011). 「한국어의 운율」, 『한국어의 말소리』 제8장, 221–264쪽.",
        "evidence_owner": "paper_author",
        "claim_kind": "methodology",
        "phenomenon_codes": ["NAN", "GENERAL"],
        "link_scope": "design",
        "relation": "direct",
        "claim_ko": (
            "억양구 경계는 마지막 음절의 특징적인 음높이 패턴, 어말 장음화, 그리고 뒤따르는 "
            "물리적 휴지로 확인할 수 있으며, 장음화와 휴지는 음운구 경계보다 큰 쉼을 느끼게 한다."
        ),
        "printed_page": 257,
        "pdf_page": 35,
        "page_locator_status": "verified",
        "applies_when": "신지영(2011)의 한국어 억양구 기술에 따라 경계 후보를 수동 점검할 때",
        "does_not_establish": (
            "휴지 하나만으로 억양구 경계를 자동 확정할 수 있다는 것, 또는 현재 TextGrid에 억양구 "
            "주석이 이미 있다는 것"
        ),
        "review_question": (
            "청각적 끊김·휴지·경계 전 장음화·음높이 재설정을 각각 관찰값으로 분리하고, 종합 경계 "
            "판정에는 불확실 범주를 허용했는가?"
        ),
        "future_layer": "prosody_annotation",
        "confidence": "high",
        "needs_human_check": False,
        "extraction_note": "인쇄 257쪽 하단. PDF 35면을 시각 대조함.",
    },
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0159",
        "ref_id": "jun1998_nasalisation_domain_disagreement",
        "source_id": "SRC-360",
        "source_file": JUN_FILE,
        "source_sha256": JUN_SHA,
        "citation": (
            "Jun, Sun-Ah (1998). The Accentual Phrase in the Korean prosodic hierarchy. "
            "Phonology 15(2), 189–226."
        ),
        "evidence_owner": "paper_author",
        "claim_kind": "methodology",
        "phenomenon_codes": ["NAN", "GENERAL"],
        "link_scope": "design",
        "relation": "direct",
        "claim_ko": (
            "장애음 비음화의 적용 영역은 선행 연구에서 음운구(PhP)와 억양구(IP)로 엇갈렸는데, "
            "Jun은 후어휘적 이음 변이에 대한 비전문 청자의 직관이 기저음과 표면음을 혼동할 수 "
            "있으므로 실제 화자의 음성 자료를 조사해야 한다고 지적한다."
        ),
        "printed_page": 221,
        "pdf_page": 33,
        "page_locator_status": "verified",
        "applies_when": "운율 영역을 이음 분포나 청취 직관만으로 정하려 할 때의 방법론적 경고",
        "does_not_establish": (
            "Jun(1998) 자체가 장애음 비음화의 정확한 적용 영역을 새 실험으로 확정했다는 것"
        ),
        "review_question": (
            "비음화 판정과 운율 경계 판정을 한 번의 인상으로 합치지 않고, 음성 단서와 운율 단서를 "
            "서로 다른 칸에 독립적으로 기록하는가?"
        ),
        "future_layer": "review_protocol",
        "confidence": "high",
        "needs_human_check": False,
        "extraction_note": "인쇄 221쪽. PDF 33면을 시각 대조함.",
    },
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0160",
        "ref_id": "jun1998_phrasing_not_syntax_only",
        "source_id": "SRC-360",
        "source_file": JUN_FILE,
        "source_sha256": JUN_SHA,
        "citation": (
            "Jun, Sun-Ah (1998). The Accentual Phrase in the Korean prosodic hierarchy. "
            "Phonology 15(2), 189–226."
        ),
        "evidence_owner": "paper_author",
        "claim_kind": "environment_condition",
        "phenomenon_codes": ["NAN", "PT", "GENERAL"],
        "link_scope": "context",
        "relation": "direct",
        "claim_ko": (
            "실제 운율구 형성은 통사 구조에서 곧바로 예측되지 않으며, 구의 길이와 구성요소의 의미·"
            "사용 관계 같은 여러 요인에 따라 같은 문장에서도 달라질 수 있다."
        ),
        "printed_page": 211,
        "pdf_page": 23,
        "page_locator_status": "verified",
        "applies_when": "어절·통사 경계를 실제 AP/IP 경계의 대리값으로 사용하려 할 때",
        "does_not_establish": "각 요인의 독립 효과 크기나 자연대화에서의 확률, 또는 NAN의 직접 실현율",
        "review_question": (
            "띄어쓰기나 통사 경계만으로 IP 경계를 자동 부여하지 않고 실제 발화의 운율 단서를 "
            "확인했는가?"
        ),
        "future_layer": "prosody_annotation",
        "confidence": "high",
        "needs_human_check": False,
        "extraction_note": "인쇄 211쪽의 가변적 phrasing 논의. PDF 23면을 대조함.",
    },
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0161",
        "ref_id": "jun1998_pause_tone_mismatch",
        "source_id": "SRC-360",
        "source_file": JUN_FILE,
        "source_sha256": JUN_SHA,
        "citation": (
            "Jun, Sun-Ah (1998). The Accentual Phrase in the Korean prosodic hierarchy. "
            "Phonology 15(2), 189–226."
        ),
        "evidence_owner": "paper_author",
        "claim_kind": "limitation",
        "phenomenon_codes": ["NAN", "GENERAL"],
        "link_scope": "design",
        "relation": "direct",
        "claim_ko": (
            "비실험 발화에서는 지각된 끊김·휴지와 성조로 표시된 운율 경계가 어긋날 수 있으며, "
            "Jun(1998)의 완전한 일치는 실험실의 가장대화식 발화에 근거하므로 장르와 담화 구조가 "
            "달라지면 대응 정도를 다시 확인해야 한다."
        ),
        "printed_page": 223,
        "pdf_page": 35,
        "page_locator_status": "verified",
        "applies_when": "NIKL 자연대화에서 휴지 또는 청각적 끊김을 운율 경계 단서로 사용할 때",
        "does_not_establish": "휴지와 성조 경계가 언제나 일치하거나, 하나의 단서만으로 경계가 확정된다는 것",
        "review_question": (
            "자연대화의 IP 경계 후보를 기록할 때 휴지, 음높이, 장음화, 지각적 끊김을 따로 남기고 "
            "장르·말차례 맥락을 함께 보존했는가?"
        ),
        "future_layer": "prosody_annotation",
        "confidence": "high",
        "needs_human_check": False,
        "extraction_note": "인쇄 223쪽. PDF 35면을 시각 대조함.",
    },
    {
        "schema_version": "reference_evidence.v2",
        "claim_id": "CLM-0162",
        "ref_id": "jun1998_points_to_primary_nasalisation_studies",
        "source_id": "SRC-360",
        "source_file": JUN_FILE,
        "source_sha256": JUN_SHA,
        "citation": (
            "Jun, Sun-Ah (1998). The Accentual Phrase in the Korean prosodic hierarchy. "
            "Phonology 15(2), 189–226."
        ),
        "evidence_owner": "paper_author",
        "claim_kind": "prior_work_summary",
        "phenomenon_codes": ["NAN"],
        "link_scope": "context",
        "relation": "summarized",
        "claim_ko": (
            "Jun(1998)은 한국어의 성조로 정의된 억양구가 비성조 음운 규칙의 영역이기도 하다는 "
            "근거로 Jun(1992)와 Jun(1993: ch. 4)을 지시한다. 장애음 비음화의 직접 실험 근거는 "
            "따라서 1998 논문 자체보다 이 선행 연구를 확인해야 한다."
        ),
        "printed_page": 222,
        "pdf_page": 34,
        "page_locator_status": "verified",
        "applies_when": "Jun 계열의 NAN 운율영역 근거를 직접 인용하려 할 때",
        "does_not_establish": (
            "현재 로컬 문헌 장부가 Jun(1992) 원문 또는 Jun(1993/1996)의 장애음 비음화 실험 장을 "
            "이미 직접 추출했다는 것"
        ),
        "review_question": (
            "Jun(1992) 또는 Jun(1993/1996)의 장애음 비음화 실험 원문을 확보·추출하기 전까지 "
            "Jun의 정확한 영역 주장을 2차 인용으로 표시했는가?"
        ),
        "future_layer": "literature_gap",
        "confidence": "high",
        "needs_human_check": True,
        "extraction_note": (
            "인쇄 222쪽의 Jun(1992, 1993: ch. 4) 지시와 참고문헌의 Jun(1992) 서지를 확인. "
            "원전 미추출을 사람확인 항목으로 둠."
        ),
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"non-object row at {path}:{line_number}")
            rows.append(value)
    return rows


def jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def atomic_replace(path: Path, text: str) -> None:
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise FileExistsError(partial)
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


def extend_claims(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_id = {str(row.get("claim_id", "")): row for row in rows}
    new_ids = [row["claim_id"] for row in NEW_CLAIMS]
    present = [claim_id for claim_id in new_ids if claim_id in by_id]
    if present:
        expected_prefix = new_ids[: len(present)]
        if present != expected_prefix:
            raise ValueError(f"non-prefix NAN prosody claim extension: {present}")
        for expected in NEW_CLAIMS[: len(present)]:
            if by_id[expected["claim_id"]] != expected:
                raise ValueError(f"existing claim differs: {expected['claim_id']}")
        if len(present) == len(new_ids):
            return {"status": "already_applied", "rows": len(rows), "sha256": sha256(path)}
    expected_last = 156 + len(present)
    if len(rows) != expected_last or rows[-1].get("claim_id") != f"CLM-{expected_last:04d}":
        raise ValueError("unexpected base/prefix claim ledger; refuse append")
    extended = [*rows, *NEW_CLAIMS[len(present):]]
    atomic_replace(path, jsonl_text(extended))
    return {"status": "appended", "rows": len(extended), "sha256": sha256(path)}


def build_cards(input_path: Path, output_path: Path) -> dict[str, Any]:
    cards = read_jsonl(input_path)
    if [row.get("phenomenon_code") for row in cards] != ["PT", "NAN", "NAL", "NI", "LLN", "VH", "HIA"]:
        raise ValueError("unexpected scope card order")
    updated: list[dict[str, Any]] = []
    new_refs = ["CLM-0157", "CLM-0158", "CLM-0159", "CLM-0160", "CLM-0161", "CLM-0162"]
    for row in cards:
        value = json.loads(json.dumps(row, ensure_ascii=False))
        if value["phenomenon_code"] == "NAN":
            value["schema_version"] = "stage2_two_hour_phenomenon_pilot_card.v2"
            value["card_id"] = "P2H-NAN-V2"
            value["literature_evidence_level"] = "core_paper_plus_prosody_sources_extracted"
            value["evidence_refs"] = list(dict.fromkeys([*value["evidence_refs"], *new_refs]))
            for item in value["boundary_scopes"]:
                if item["name"] == "어절 간 장애음#ㄴ":
                    item["evidence_refs"] = list(
                        dict.fromkeys([*item["evidence_refs"], "CLM-0157", "CLM-0158", "CLM-0159"])
                    )
            for item in value["population_contract"]["peripheral"]:
                if item["condition_id"] == "NAN_PER_INTER_EOJEOL":
                    item["evidence_refs"] = list(
                        dict.fromkeys([*item["evidence_refs"], "CLM-0157", "CLM-0158", "CLM-0161"])
                    )
            for item in value["confounds"]:
                if item["name"] == "어절 간 운율 경계":
                    item["evidence_refs"] = list(
                        dict.fromkeys([*item["evidence_refs"], "CLM-0157", "CLM-0158", "CLM-0159", "CLM-0161"])
                    )
            value["evidence_limits"] = [
                "장애음 비음화의 변이·발화 요인 직접 정독은 서윤정(2022) 한 편에 크게 의존한다.",
                "신지영(2011)은 미역국#누가의 운율경계 대비를 직접 제시하지만 자연대화 전수 확률이나 부분 비음화 기준을 제시하지 않는다.",
                "Jun(1998)은 영역 판정의 방법론과 선행 연구 불일치를 설명할 뿐 장애음 비음화 영역의 직접 실험은 Jun(1992/1993)에 있으므로 원전 추가 확보가 필요하다.",
                "현재 84사례 패키지에는 AP/IP 정식 주석이 없으므로 경계 판정은 수동 잠정값이며 실현 판정과 분리해야 한다.",
            ]
            value["open_questions"] = [
                "후행 ㅁ을 NAN 본모집단에 넣을 것인가 별도 현상으로 둘 것인가?",
                "어절 간 ㄱ#ㄴ 사례에서 같은 억양구 내부와 억양구 경계 후보의 비음화 실현이 실제로 다른가?",
                "휴지·음높이·경계 전 장음화·지각적 끊김을 어떤 조합으로 잠정 IP 경계라 할 것인가?",
                "부분 비음화를 3단계로 기록할 수 있는가?",
                "Jun(1992) 또는 Jun(1993/1996)의 장애음 비음화 직접 실험을 확보하면 현재 경계 가설을 어떻게 수정해야 하는가?",
            ]
            value["research_question_map"] = {
                "primary_question": "어절 간 장애음#ㄴ에서 운율 경계가 비음화의 실현 여부와 어떻게 대응하는가?",
                "questions": [
                    {
                        "question_id": "NAN-RQ1",
                        "question": "두 표적 어절은 같은 억양구 안에 있는가, 억양구 경계로 갈리는가?",
                        "evidence_refs": ["CLM-0157", "CLM-0158", "CLM-0159", "CLM-0161"],
                    },
                    {
                        "question_id": "NAN-RQ2",
                        "question": "선행 장애음은 구강 장애음·완전 비음·부분 비음 중 무엇으로 실현되는가?",
                        "evidence_refs": ["CLM-0061", "CLM-0157"],
                    },
                    {
                        "question_id": "NAN-RQ3",
                        "question": "경계 판정과 실현 판정을 분리했을 때 같은 IP 내부에서 비음화, IP 경계에서 유지라는 대응이 보이는가?",
                        "evidence_refs": ["CLM-0157", "CLM-0159"],
                    },
                    {
                        "question_id": "NAN-RQ4",
                        "question": "예외가 있다면 속도·말차례·초점·형태소 분석·음질 중 무엇이 대안 설명인가?",
                        "evidence_refs": ["CLM-0065", "CLM-0160", "CLM-0161"],
                    },
                ],
                "prosodic_boundary_labels_candidate": [
                    "same_ip_likely",
                    "ip_boundary_likely",
                    "unclear",
                    "not_assessed",
                ],
                "prosodic_cues_to_record_separately": [
                    "boundary_tone_or_pitch_reset",
                    "preboundary_lengthening",
                    "physical_pause",
                    "perceived_disjuncture",
                    "turn_or_discourse_context",
                ],
                "candidate_logic": [
                    "같은 억양구 안이면 후어휘 규칙의 단일 적용 영역에 두 분절이 함께 들어 비음화가 허용된다는 가설",
                    "억양구 경계가 사이에 놓이면 적용 영역이 끊겨 어절 간 비음화가 차단된다는 가설",
                    "휴지 하나만으로 경계를 확정하지 않고 복수 단서와 불확실성을 보존",
                ],
                "status": "candidate_pending_researcher_adoption",
            }
        updated.append(value)
    text = jsonl_text(updated)
    if output_path.exists():
        if output_path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"scope card output differs: {output_path}")
        status = "already_present"
    else:
        output_path.write_text(text, encoding="utf-8")
        status = "created"
    return {"status": status, "rows": len(updated), "sha256": sha256(output_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extend NAN prosody literature evidence and derive v2 scope cards")
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--cards-input", type=Path, default=DEFAULT_CARDS_INPUT)
    parser.add_argument("--cards-output", type=Path, default=DEFAULT_CARDS_OUTPUT)
    args = parser.parse_args()
    result = {
        "claims": extend_claims(args.claims.resolve()),
        "cards": build_cards(args.cards_input.resolve(), args.cards_output.resolve()),
        "source_pdfs_read_only": True,
        "automatic_research_judgement": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

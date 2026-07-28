# 공통 발음 자원 v2 결정 — 어절 occurrence·MFA·선택적 보조기술

작성일: 2026-07-28
상태: **방향 확정, 소표본 계약 구현·검증 완료, 전량 type inventory 전**

## 1. 연구 흐름에서의 역할

이 프로젝트의 목적은 정렬기가 실제 음운현상 실현을 자동 판정하게 하는 것이
아니다.

```text
형태소·표기·음운환경 CSV 검색
  → 해당 WAV·TextGrid 수집
  → KOINA 운율 분석 결합
  → 연구자가 WAV·TextGrid를 직접 보고 실현 판정
```

공통 발음 자원은 이 과정의 검색 기준과 MFA 입력을 2020–2025에 일관되게
제공한다. 사전 발음, 규칙 예상 발음, G2P, MFA phones, 음향모델 후보, 연구자
판정은 서로 다른 층으로 유지한다.

## 2. 핵심 결정

1. MFA 3.4와 `korean_mfa`를 주 정렬기로 유지한다.
2. 우리말샘 연계 `pron_1/2`를 출처 보존 발음 registry에 수록한다.
3. 사전 발음을 표기만 같은 모든 발화에 곧바로 활성화하지 않는다.
4. 검색층은 `표기+형태소 구성`의 어절 type과 발화별 occurrence를 분리한다.
5. MFA용 `.dict`는 registry의 정본이 아니라 명시적 정책으로 만든 파생물이다.
6. wav2vec2 phone은 검색 후 선택한 발화에만 붙이는 post-alignment 보조표다.
7. KFaligner/HTK는 비교 가능성을 검토한 참고사항으로만 남기며, 현재
   구축·설치·테스트 계획에는 넣지 않는다.

기계 판독 계약은
`config/common_pronunciation_resource_contract.json`에 고정한다.

## 3. 하나의 “발음사전 파일”이 아니라 재사용 가능한 층

```text
pronunciation_registry
  ├── eojeol_pronunciation_types
  │     └── eojeol_occurrences
  ├── alignment_backend_lexicons
  │     ├── mfa
  │     └── other_backends_reference_only
  ├── post_alignment_index
  ├── acoustic_phone_candidates
  └── human_annotations
```

### 3.1 `pronunciation_registry`

행 단위는 출처가 하나인 발음 후보 하나다. 같은 한글 발음이라도 사전 ID,
품사, 의미, `pron_1/2`, 자료 판본이 다르면 원천행을 보존한다.

최소 표현은 다음과 같다.

```text
표기: normalized_form, headword, word_stem
형태: pos_lexicon, sense_id, urimal_id, stdict_target_code
발음: pron_hangul, pron_roman_search, pron_ipa_reference
출처: pron_source_type, pron_source_field, source_release
변환: phone_mapping_version, source_row_fingerprint
상태: match_status, selection_status, exclusion_reason
```

MFA 또는 장래 다른 정렬기의 phone열은 정본 한 칸에 섞지 않고 backend
adapter 표에 둔다.

### 3.2 `eojeol_pronunciation_types`

2020–2025 동결 CSV에는 5,103,356발화와 27,847,068어절이 있다. 모든
occurrence에 긴 사전 발음·G2P 문자열을 반복하면 파일과 갱신 비용이 과도하다.

따라서 다음 키의 고유 type을 먼저 만든다.

```text
eojeol_type_id
normalized_surface
morph_signature
orth_roman_search
dictionary_candidate_ids
g2p_candidate_id
dictionary_match_summary
```

`수가/NNG`와 `수/NNB+가/JKS`는 표면 철자가 같아도 서로 다른 type이다.

### 3.3 `eojeol_occurrences`

```text
utt_id, eojeol_idx, eojeol_type_id
left_context_type_id, right_context_type_id
rule_pron_context_id, boundary_ids
eojeol_map_status
```

사전·G2P처럼 문맥과 독립적인 정보는 type에 두고, 앞뒤 환경에 따라 달라지는
규칙 예상 발음과 음운경계는 occurrence 또는 boundary 표에 둔다. 연구자가
받는 후보 CSV에는 필요한 열만 펼쳐 쓴다.

## 4. 표기 일치와 형태소 일치를 분리하는 정책

소표본 구현은 다음 두 경우만 occurrence 수준 MFA 후보로 인정한다.

```text
exact_single_morph_pos
predicate_dictionary_form_pos
```

- `그것/NP` ↔ 사전 `그것/NP`
- `있/VX+다/EF` ↔ 사전 `있다/VX`

다음은 registry와 검색 CSV에는 남지만 MFA 자동 활성화 대상이 아니다.

```text
surface_only_pos_mismatch
surface_only_morphologically_composed
token_group_surface_mismatch
eojeol_alignment_unresolved
lexicon_pos_missing
tagged_parse_error
```

`lab`과 `tagged`의 어절 수가 다르면 위치로 억지 조인하지 않는다. target
표면형으로 복원되는 tagged 그룹이 정확히 하나일 때만
`unique_surface_recovery`로 회수한다. 0개 또는 2개 이상이면 미해결로 남긴다.

## 5. 첫 세 발화의 수동 검토와 해석

사용자 판정은
`outputs/reports/MANUAL_REVIEW_common_pron_AB_first3_20260728.csv`에 보존했다.

| 발화 | 사전 후보 | 형태소 감사 | 사용자 판정 | 결정 |
|---|---|---|---|---|
| `SDRW2000001214.1.1.95` `있다` | `읻따`, `iː t͈ ɐ` | `있/VX+다/EF`; `VX` 후보 2개만 엄격 일치 | B가 더 나음 | `t͈`는 경음 /ㄸ/ phone. 같은 발음의 호환 품사·의미 후보를 합쳐 MFA 후보 검토 |
| `SDRW2300000171.1.1.108` `그것` | `그걷` | `그것/NP`; NP 후보 일치, NNG 후보 제외 | 둘 다 무난; A가 유성음 반영 | 사전 후보 보존. phone 라벨 차이만으로 B 우세 판정 금지 |
| `SDRW2400002901.1.1.111` `수가` | `수까`, 사전 `수가/NNG` 의미 005 | 실제 `수/NNB+가/JKS`; 유일 표면형 회수 | A가 더 나음 | 사전 후보는 CSV 참고열에 보존, 이 occurrence와 plain-word MFA 전역 활성화에서는 제외 |

`t͈`는 IPA의 tense alveolar stop으로 한국어 경음 `ㄸ`을 가리킨다.
`있다`의 표준 독립형 `읻따`를 backend phone으로 변환한 결과이지, 그 기호
자체가 연구자의 실제 실현 판정은 아니다.

## 6. 30 stress 발화 형태소 결합 파일럿

산출물:

- `outputs/reports/PILOT_common_pron_occurrence_match_20260728.csv`
- `outputs/reports/PILOT_common_pron_occurrence_match_20260728.manifest.json`

입력은 완료된 A/B의 60발화 중 stress 30발화와 사전 후보 110행이다.

| 항목 | 결과 |
|---|---:|
| 감사 결과행 | 128 |
| 위치 exact 조인 | 83 |
| 어절 수 불일치 뒤 유일 표면형 회수 | 45 |
| 엄격 occurrence 후보 | 73 |
| reference-only | 55 |
| 단일 형태소+품사 일치 | 57 |
| 용언 `-다` 표제어+품사 일치 | 16 |
| 다형태소 표면 일치만 있음 | 33 |
| 품사 불일치 | 22 |

7발화에서 `lab/tagged` 어절 수가 달랐다. 대상 후보행 45개는 모두 유일
표면형으로 회수됐지만, 이는 전량에서도 모두 회수된다는 뜻이 아니다. plain
word MFA 전역 활성화 여부는 같은 철자의 **전 occurrence 감사** 전까지
`pending_full_occurrence_audit`다.

최초 위치-only 감사표는 다음에 archive했다.

```text
archive/common_pron_occurrence_match_pre_surface_recovery_20260728
```

## 7. MFA에서 사전 발음을 사용하는 범위

MFA 공식 3.X 사전은 같은 word의 복수 발음과 발음확률을 지원한다.

- 사전 형식:
  <https://montreal-forced-aligner.readthedocs.io/en/stable/user_guide/dictionary.html>
- 발음확률 산정:
  <https://montreal-forced-aligner.readthedocs.io/en/latest/reference/dictionary/generated/montreal_forced_aligner.alignment.pretrained.DictionaryTrainer.html>

그러나 일반 MFA 사전의 key는 형태소 occurrence가 아니라 plain word다. 따라서
다음 정책을 적용한다.

1. 기본 `korean_mfa.dict` 발음은 보존하고 자동 대체하지 않는다.
2. registry 후보의 기본 상태는 `reference_only`다.
3. 같은 표층 token의 전 occurrence가 엄격 형태소 조건을 통과한 경우에만
   global plain-word 후보가 될 수 있다.
4. `수가`처럼 서로 다른 형태소 type이 공존하면 문맥 특정 발음을 전역
   활성화하지 않는다.
5. 동형·다의 후보의 출처행은 보존하되 backend phone이 같으면 정렬용 행은
   중복 제거하고 source IDs를 별도 연결한다.
6. 확률 없는 새 발음은 MFA에서 기본 1.0으로 처리되므로, 현재 A/B처럼
   availability 파일럿에서만 무가중 추가를 허용한다.
7. 생산 사전의 복수 발음은 두 후보를 넣은 뒤 `mfa train_dictionary`로
   사용빈도를 추정하고 수동 극단치 검토를 거쳐 확률을 고정한다.

필요하면 문맥별 lab token decoration으로 occurrence별 사전을 강제할 수 있지만,
전사와 word 라벨을 바꾸므로 전량 기본정책으로 사용하지 않는다. 특정 연구
후보의 재정렬 실험에서만 별도 run으로 검토한다.

### 7.1 G2P는 선택사항이 아니라 MFA coverage baseline

MFA 기본사전에 없는 관측 어절은 고정한 G2P 모델의 1-best 발음을 반드시
갖게 한다. 그렇지 않으면 OOV가 `spn`으로 정렬되어 phone 검색과 경계 검토가
무너진다.

생산 파생사전의 우선순위는 다음과 같다.

1. MFA 기본사전의 기존 발음·확률열을 그대로 보존한다.
2. 2020–2025에서 실제 관측됐지만 기본사전에 없는 고유 표면 어절은 고정
   G2P 1-best를 한 번만 생성해 추가한다.
3. 형태소·품사가 안전하게 일치한 우리말샘 발음은 기본/G2P를 대체하지 않고
   검증된 복수 후보로만 추가한다.
4. G2P 변환 실패는 성공으로 넘기지 않고 별도 실패표에 기록한다.
5. MFA 시작 전 관측 lab token의 사전 OOV는 0이어야 하며, 정렬 뒤 `spn`은
   연도·화자·어절별로 다시 감사한다.

G2P 결과에는 모델명·모델 fingerprint·MFA 버전·생성 옵션·입력 vocabulary
SHA256을 기록한다. 형태소 type이 달라도 표면형이 같으면 G2P 계산은
공유하지만, 사전 발음의 적합성은 각 형태소 type에서 별도로 판정한다.

## 8. KFaligner 검토

저장소:
<https://github.com/exphon/kfaligner>

KFaligner는 HTK 3.4.1 기반 한국어 정렬기로, 설치 뒤 오프라인 실행은 가능하다.
한국어 철자 lab, 자체 발음사전 생성기, phone/syllable/word/utterance TextGrid를
제공한다. 알고리즘과 phone 체계가 MFA와 달라 선택 발화의 교차검증 도구로는
가치가 있다.

현재 상태에서 MFA 전량 backend를 대체하지 않는 이유는 다음과 같다.

- Linux가 권장되고 HTK를 별도로 내려받아 컴파일해야 한다. 현재 Windows
  환경에서는 WSL/Ubuntu 또는 별도 Linux 기기가 필요하다.
- HTK는 별도 라이선스가 적용된다. 저장소 README는 MIT를 표기하지만
  2026-07-28 확인 시 repository root의 `LICENSE` 파일은 없었다.
- 음향모델의 학습자료·평가치·재현 manifest가 README에 충분히 기록돼 있지 않다.
- 기본 사전은 README 기준 약 5,589단어로, 881,237 고유 어절에는 사전 생성
  경로가 핵심이 된다.
- 현재 `align.py`는 공용 `./tmp`를 매번 삭제하고, 한글 입력 때
  `bin/kdict1.txt`와 `bin/dict`를 공유 갱신하므로 병렬·재개에 안전하지 않다.
- `os.system` 반환코드를 확인하지 않고 OOV 단어를 `SKIPPING WORD`로
  건너뛴다. 부분 전사가 정렬돼도 성공처럼 보일 수 있다.
- TextGrid domain은 WAV의 0–xmax가 아니라 첫 phone–마지막 phone에서 시작한다.
  현재 연구의 전 tier 경계·coverage 계약과 맞지 않는다.
- 저장소는 12 commits, 자동시험·release가 확인되지 않아 대량 파이프라인
  안전장치는 별도 구현해야 한다.

현재는 HTK/KFaligner가 MFA보다 낫다는 비교 근거가 없고, 별도 설치·보완·수동
판정 비용을 투입할 여력도 없다. 따라서 상태를
`reference_only_not_planned`로 고정하고 설치·코드 보완·A/B 테스트를 하지
않는다. 향후 독립된 평가자료에서 MFA보다 낫다는 근거가 생기거나 MFA로
반복해서 회수하지 못하는 특정 오류군이 연구상 핵심이 될 때만 재검토한다.

## 9. 다른 현재 기술의 현실적 위치

### wav2vec2 한국어 phone 모델

`slplab/wav2vec2-xls-r-300m_phone-mfa_korean`은 독립 음향 후보로만 쓴다.
<https://huggingface.co/slplab/wav2vec2-xls-r-300m_phone-mfa_korean>

2020–2025 동결 CSV의 `dur` 합계는 3,808.128시간이다. 현재 기기는 Intel N200
4코어, RAM 8GB, CUDA GPU가 없다. 전량 추론은 현실적 기본계획에서 제외하고,
CSV 검색 뒤 선택 발화에만 실행한다. 모델은 낭독체 학습이므로 대화체의 실제
오류율은 모델 카드 수치와 같다고 가정하지 않는다.

### WhisperX

WhisperX는 ASR와 word timestamp가 주 역할이고 이 프로젝트에는 이미 신뢰할
전사가 있다. 한국어 phone 연구의 정본을 제공하지 않으며, 2025–2026에도
forced-alignment timestamp 회귀와 수정이 이어졌다.
<https://github.com/m-bain/whisperX/releases>

따라서 전사 생성·word 정렬을 다시 하기 위해 추가하지 않는다.

### TorchAudio multilingual forced alignment

공식 multilingual forced-alignment 예제가 있지만 해당 API는 deprecated되어
2.9 제거가 예고됐다.
<https://docs.pytorch.org/audio/main/tutorials/forced_alignment_for_multilingual_data_tutorial.html>

장기 인프라의 기반으로 채택하지 않는다.

## 10. 공통 발음 자원 구축과 MFA 시작 순서

### 단계 A — 입력과 type/occurrence 고정

1. 현재 30 stress occurrence 감사표를 방법론 소표본으로 고정한다.
2. 60발화 전체에서 `surface+morph_signature` type 생성과 원 어절 왕복 조인을
   시험한다.
3. 한 연도에서 type 빈도와 occurrence 표 예상 용량을 실측한다.
4. 통과하면 2020–2025 전량에서 다음 두 표를 원자적으로 생성한다.
   - `eojeol_pronunciation_types`: 표면형, 형태소 signature, 철자·형태소
     검색 로마자, 사전/G2P candidate IDs
   - `eojeol_occurrences`: `utt_id`, `eojeol_idx`, `type_id`, 좌우 문맥,
     음운경계, 왕복 조인 상태

### 단계 B — 발음 registry와 MFA 파생사전

5. MFA 기본사전, 고정 G2P, 우리말샘 `pron_1/2`를 출처별 long registry로
   합친다. 어느 후보도 연구자의 실제 실현 판정 열에 쓰지 않는다.
6. 기본사전에 없는 관측 고유 표면 어절에 G2P 1-best를 checkpoint 방식으로
   한 번만 생성한다. 동일 입력·모델은 cache로 재사용한다.
7. 형태소 조건을 통과한 우리말샘 후보만 별도 `eligible`로 표시한다.
   전 occurrence 감사 전에는 plain-word 전역 변이로 활성화하지 않는다.
8. 기본사전+OOV G2P를 필수 baseline으로 하고, 안전한 사전 변이만 선택적으로
   더한 `common_pron_mfa_r1` 파생사전과 manifest를 만든다.

### 단계 C — MFA 시작 gate

9. 실행 전 자동 gate는 다음을 모두 통과해야 한다.
   - 모든 관측 lab token의 사전 coverage 100%, OOV 0
   - G2P 실패 0 또는 명시적으로 차단된 실패 inventory
   - acoustic model phone inventory 밖 기호 0
   - 기본사전 행·확률열 무손상
   - 중복·빈 발음·숫자 phone·잘못된 탭 구조 0
   - 입력 CSV/WAV/lab과 사전의 SHA256 manifest 완성
10. 기존 6개년×10발화·5화자 표본과 형태소 충돌 사례에서 자동 정렬·4-tier
    경계·`spn`·부분 성공 gate를 다시 통과시킨다. 새 사전 변이가 실제 phone을
    바꾸는 소수 사례만 사람이 확인한다.
11. 통과한 release ID를 고정한 뒤 2022부터 연도별 MFA를 시작한다. 각 연도는
    preflight→align→direct DB export→4-tier QC→완료 marker 순서로 실행하고,
    다음 연도는 앞 연도 보고서가 완성된 뒤 시작한다.
12. 2020·2021은 즉시 전량 재실행하지 않는다. 기존 실행에서 사용한 G2P와
    `common_pron_mfa_r1`의 관측 token별 phone을 비교한다.
    - phone과 coverage가 동등하면 동등성 manifest를 남기고 기존 결과를 보존한다.
    - 실제 차이가 있으면 영향 발화 inventory를 먼저 만들고, 방법론적 일관성에
      필요한 범위만 재정렬한다.

전량 작업 전까지 기존 A/B policy B를 production 정본으로 채택하지 않는다.
이번 A/B는 exact-word 무가중 availability 실험이며, 형태소 조건 필요성을
발견한 성공적인 방법론 파일럿으로 보존한다.

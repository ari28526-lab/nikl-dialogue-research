# 프로젝트 현재 상태 정본

> **2026-08-18 현재 진입점 — 자료구축 1단계 공식 종료·2단계 설계 채택:**
> 6개년 인프라 closeout과 외부 HTML 보고서
> (`qmd/six_year_infrastructure_report_20260818.qmd` →
> `outputs/reports/six_year_infrastructure_report_20260818.html`, 수량 20항목
> 재검증 통과)를 본선에 반영하고, 자료구축 단계를
> `docs/decisions/DECISION_stage1_data_infrastructure_closure_20260818.md`로
> 공식 종료했다. 잔여 recovery 817,255건·RC1 enrichment·의미번호 join·대형
> `work/` 정리·main 동기화는 소속 Gate를 확정해 라우팅했다. 다음 단계 전체
> 구조는 `docs/decisions/PLAN_stage2_target_query_and_realization_design_20260818.md`
> (G0–G8: query 동결 → 의미번호 join → 2020 생산 감사 → 6개년 후보 생성 →
> 문맥 연결 → 검토 bundle → 연구자 실현 ledger → 표적 후속)가 정본이다.
> production query 실행은 여전히 미승인이며, G1 착수·A3 `etym_type` 정본
> 위치·검토 표본 전략 3건이 사용자 결정 대기다.

> **2026-08-18 현재 진입점 — 6개년 인프라 closeout:** 2020–2025년 원천
> 5,103,356발화의 형태소·표기 검색층과 exact-ID 상태 회계, 동일 r3 계약의
> 4,286,046발화 6-tier, 기술·발음 후속 817,310건의 보존 장부, RC1 append-only
> 수동 보정과 후보→TextGrid 연결 파일럿을 한 단계의 인프라 release candidate로
> 정리했다. 전체 510만 발화는 검색 가능하지만 전체가 정렬된 것은 아니다.
> closeout 해설·재사용·시행착오·외부 HTML source map은
> `docs/releases/20260818_six_year_infrastructure_closeout/`에 있다. 2020–2025
> r3 MFA와 전수 6-tier를 다시 실행하지 않는다. 다음은 이 정본을 바탕으로 외부
> HTML을 만들거나, 별도 연구 Gate에서 실제 target query와 연구자 실현 판정을
> 시작하는 단계다.

> **2026-08-18 ㄴ 삽입 B1 개정안 승인·생산 query 미실행:** 7월 정의 초안의
> “MFA phone을 핵심 실현 판정으로 사용”하는 잘못된 문구를 역사 archive로
> 분리하고, 수동 청취·TextGrid 판정만 최종 실현값으로 쓰는 현행 개정안을
> 연구자 `ari30`이 승인했다. 생산 후보는 어절 내부/어절 간을 분리하고
> J*/E*·숫자·기호 인접을 제외하며 의미번호의 불확실성을 별도 열로 보존한다.
> 후보·시간 연결 인프라는 통과했으며 새 청취 파일럿은 필요 없다. 다만 의미번호
> join과 6개년 생산 query는 이 closeout에 포함하지 않았고 아직 실행하지 않았다.

> **2026-08-18 현재 진입점 — 후보→TextGrid 문맥 시간 연결 통과:** 파일럿
> 22행 중 실제 환경 후보 20개를 대상으로, TextGrid가 있는 19개 occurrence를
> 형태소 어절 index와 `words` tier로 연결했다. 단일 어절 12, 인접 두 어절 7,
> 자산 부재 대기 1이며 인프라 검사 2건에는 시간을 붙이지 않았다. 이 시간은
> 연구자 검토용 어절 문맥이지 실제 음운 분절 경계나 실현 판정이 아니다. 독립
> 감사가 원행·TextGrid SHA·index·시간을 재계산해 통과했다. 다음은 파일럿을 더
> 늘리는 것이 아니라 실제 연구의 형태소·의미번호·표기 환경 query set을
> 확정하는 단계다.

> **2026-08-18 현재 진입점 — overlay-aware 표적 manifest 파일럿 통과:**
> RC0 기본값과 RC1 curated exact-ID 우선순위를 실제 후보 검색에 연결했다.
> 인프라 확인 2건과 ㄴ 삽입 유사 철자·형태소 환경 20건, 총 22 occurrence를
> 생성했고 독립 감사가 통과했다. 21건은 WAV·TextGrid 검토 가능, 1건은 자산
> 부재를 숨기지 않은 metadata-only 후보다. 실제 음성 실현 판정, target 시간
> 확정, MFA, 원자료·RC0·RC1·TextGrid 수정은 0건이다. 이 단계의 다음 작업인
> occurrence→TextGrid word interval 파일럿은 위와 같이 통과했다. RC1 16건
> enrichment는 실제 표적에 포함될 때만 한다.

> **2026-08-18 RC1 방향 재점검·active view 계약 완료:** 전체 510만 발화에 비해
> curated 16건 enrichment를 즉시 완성하는 것은 우선순위가 낮다고 판단했다.
> RC0 기본값 위에 RC1 exact-ID 예외만 적용하는
> `nikl_dialogue_research_db_v1_active_view_contract_v1_20260818`을 생성했고 감사가
> 통과했다. exception 55, curated pointer 16, base 보존 39, full base copy 0이다.
> diagnostic evidence는 active가 아니며 D9 phone·형태소 pending은 유지한다.
> 이 단계의 다음 작업이었던 target manifest 소표본은 위와 같이 통과했다.

> **2026-08-18 DB v1 RC1 recovery sidecar 채택 완료:** 승인 exact-ID 55건의
> recovery 후속 상태와 D10 수동 word·전사 16건의 curated snapshot·active
> pointer를 `nikl_dialogue_research_db_v1_0_0_rc1_20260818`로 채택했다. RC0
> ledger를 덮어쓰지 않는 sidecar이며 독립 감사가 통과했다. RC0 5,103,356발화,
> 본체 정렬 성공 4,286,046, 잔여 recovery 817,255다. D9 phone은 참고 전용,
> 수정 전사의 형태소·phoneme은 pending이다. RC0·r3·6-tier·TextGrid 변경과
> MFA는 0건이다. 이 기록의 다음 단계는 위 방향 재점검으로 대체됐다.

> **2026-08-18 D10 연구자 반환 16건 동결 완료·채택 전:** Dropbox 수동
> TextGrid 16/16을 `D10_RESEARCHER_RETURN_0001`에 raw 16·normalized 16으로
> 분리 보존했다. 1–4번은 연구자가 만든 interval의 tier 위치만 옮겼고 다른 수동
> 경계는 바꾸지 않았다. 제안 전사와 다른 연구자 판정 5건 및 문자 동일·분절 차이
> 1건을 provenance에 함께 기록했다. 길이·전구간 연속성·D9 reference 불변 감사가
> 통과했으며 상태는 `frozen_researcher_return_pending_adoption_gate`다. 원본·r3·
> 6-tier·DB v1 변경과 MFA 실행은 0건이다. 다음은 전체연도 재실행이 아니라 이
> exact ID들의 수동 word overlay를 DB 파생층에 연결하는 별도 adoption Gate다.

> **2026-08-18 D10 격리 수동 작업본 생성 완료·채택 전:** D9 부분 보존 16건을
> D:의 `D10_MANUAL_OVERLAY_0001`에 16세트×5파일로 materialize했고 전수 SHA·
> 길이·tier 감사를 통과했다. 수동 TextGrid는 D9 word/phone 참고, 제안 전사,
> `words_manual_working` 네 tier다. 국소 수정 9건은 D9 word 경계를 초안으로
> 가져왔고 전체 재정렬 6건·단일어 1건은 빈 작업 tier로 시작한다. 원본·r3·
> 최종 6-tier·DB v1 변경과 MFA 실행은 0건이다. 현재 상태는
> `materialized_pending_researcher_manual_overlay`이며 수동 경계 수정과 별도
> adoption Gate 전에는 alignment/analysis 범위로 복귀하지 않는다.

> **2026-08-18 D10 manual overlay Gate 준비 완료:** D9 연구자 판정에서 수동
> 복구할 16건을 국소 수정 9·전체 재정렬 6·단일어 1로 고정하고, 실제 들린 문장과
> 수정 지시를 exact-ID queue로 만들었다. 기술 제외 2·직접 승인 1은 섞지 않았다.
> 자동 감사가 D9 판정과 완전 일치함을 확인했으며 현재는
> `passed_gate_closed_before_overlay_materialization`이다. 원본·D9·r3·6-tier·
> DB v1 변경과 MFA 실행은 0건이다. 다음은 16건의 격리 작업 사본 생성이다.

> **2026-08-18 D9 연구자 검토 완료·D10 직전:** D9 19건을 직접 청취·경계
> 검토해 승인 1, 수동 overlay 16, 기술 제외 2, 미결정 0으로 확정했다. 16건은
> 실제 음성은 살릴 수 있으나 LAB 과잉·중복·치환·끝 잘림 때문에 수정 전사와
> 수동 경계가 필요하다. 기술 제외 2건도 증거를 보존한다. 자동 overlap 네 건 중
> 실제 겹침은 한 건뿐이었다. 원본·r3 본체·6-tier·DB v1 수정은 0건이다. 다음은
> 전체 재정렬이 아니라 16 exact ID의 격리 D10 manual overlay package다.

> **2026-08-17 D9 통제 재정렬 완료·채택 Gate 닫힘:** D8에서 identity가
> 확인된 미정렬 19건만 동일 모델·공통발음 r3·LAB으로 `beam=100`,
> `retry_beam=400` 한 차례 실행해 TextGrid 19/19, 누락 0으로 끝났다. 실행시간은
> 707.031초다. 번호가 같은 WAV·LAB·2-tier TextGrid 검토 묶음은 독립 SHA·tier·
> 길이 감사가 통과했고 원음원 겹침 4건을 표시했다. 이 결과는 탐색 폭 민감성을
> 보여주지만 경계·단일 화자 적합성의 자동 승인은 아니다. r3 본체·6-tier·DB v1·
> 원자료 변경은 0건이다. 개인 Dropbox 검토 폴더 복사 61/61와 SHA 검증이
> 통과했고 공유 설정은 바꾸지 않았다. 다음은 19건 연구자 검토와 별도 채택
> Gate다.

> **2026-08-17 D9 통제 재시도 승인·preflight 완료:** D8에서 원자료 identity가
> 확인된 계속 미정렬 19건만 별도 namespace에서 `beam=100`,
> `retry_beam=400`으로 한 차례 재시도하도록 run shard·설정·execution contract를
> SHA-256으로 동결했다. 0.1초 미만 25건과 전체연도는 입력에서 제외했다.
> 연구자 `ari30`의 scope-bound 승인을 세 해시에 결속했고 PowerShell 5.1
> safety/runtime와 승인 포함 `-PreflightOnly`가 `passed_ready_to_execute`로
> 통과했다. 현재 D: materialize, MFA 실행, r3·6-tier·DB v1 수정은 0건이다.
> 다음은 단일 D9 runner 실행이며 결과 채택은 별도 Gate다.

> **2026-08-17 D8 읽기 전용 회수 가능성 감사 완료:** 계속 미정렬 19건은 원
> JSON·동결 CSV·LAB·canonical/r3/H WAV identity가 모두 확인되어 D9의 한 차례
> 통제 parameter-retry 후보가 됐다. 0.1초 미만 25건은 H 백업 WAV도 r3와 같은
> payload이며 최대 0.099875초라 동일 exact ID의 기술 제외로 확정할 근거를
> 확보했다. 숫자 읽기 3건은 동결 normalized LAB와 일치해 오류가 아니다. 독립
> 감사 상태는 `passed_read_only_feasibility_gate_closed`다. MFA·새 음원 생성·
> 본체/6-tier/DB v1 수정·삭제는 0건이다. 다음은 19건만 새 namespace에서 한
> 차례 실행하는 D9 scope-bound 승인·실행 계약이며 25건과 전체연도는 재실행하지
> 않는다.

> **2026-08-17 D7 연구자 검토 반영 완료:** D5 진단 TextGrid가 생성된 11건을
> 본체 성공에서는 모두 제외하고 진단 자료를 그대로 보존했다. 사용자 메모에 따라
> 부분 정렬 가능 6, 잡음 보존 3, 전사 누락 1, 전사 수정 후보 1로 exact-ID
> 분류했으며 별도 recovery SQLite에서 검색 가능하다. r3 본체·6-tier·DB v1
> 변경과 파일 삭제는 0건이다. 다음은 19개 미정렬과 25개 짧은/없는 PCM의 원자료
> 회수 가능성만 읽기 전용으로 감사하고, 회수 후보에 한해서만 별도 통제 재정렬
> Gate를 만드는 것이다.

> **2026-08-15 D6 사후 분기 Gate 완료:** D5 TextGrid 성공 11건을 번호가 같은
> WAV·LAB·2-tier TextGrid와 CSV로 한 폴더에 구성했다. 계속 미정렬 19건은 D5
> 보존 DB에서 모두 `ignored=false`, `num_frames>0`, word/phone interval 0으로
> 확인되어 새 exact-ID 기술 진단 대상으로 남았다. 0.1초 미만 25건은 원 PCM
> 점검표에서 24건 짧음·1건 없음으로 연결했고 원 CSV 시간정보와 회수 경로를
> 보존했다. 독립 감사가 통과했으며 본체·6-tier·DB v1 자동 병합은 0건이다.
> 다음은 성공 11건 연구자 검토와 별도 채택 승인이다. 전체연도나 D5 전체를
> 다시 실행하지 않는다.

> **2026-08-15 D5 격리 진단 완료:** alignment-missing 30건만 byte-copy로
> 격리해 공통발음 r3 기준 MFA를 실행했다. TextGrid 11건이 생성되고 19건은 계속
> 미정렬이며, 두 집합은 겹침·누락 없이 frozen 30 ID를 완전 회계한다. 0.1초 미만
> feature-failure 25건은 동일 입력으로 실행하지 않고 원 음원 길이 회수 장부에
> 보존했다. 상태는 `completed_diagnostic_no_merge`다. r3 본체·연구용 6-tier·
> DB v1 자동 병합은 0건이며, 다음은 11건 채택 및 19건 추가 회수의 별도
> exact-ID Gate다.

최종 갱신: 2026-08-18 KST

> **2026-08-15 recovery D0–D4 완료·pre-MFA 정지:** A–C 정본 밖 후속
> 817,310건을 pre-MFA 기술 95,860, post-MFA 기술 3,086, 발음 후속
> 718,364로 exact-ID 완전 회계하고 43개 reason routing unit을 만들었다. 기술
> 98,946건은 frozen CSV와 WAV/LAB를 읽기 전용 감사했고, 발음 후속은 85,433
> token-role 유형으로 축약해 사전·규칙·G2P 근거만 연결했다. 자동 실현 판정은
> 0건이다. 첫 진단 shard는 feature 실패 25건 전수와 연도별 서로 다른 세션의
> alignment 미정렬 5건씩, 합계 55건이다. 독립 감사와 Windows PowerShell 5.1
> preflight가 통과했으며 상태는 `passed_gate_closed`다. **D: recovery root 생성,
> WAV/LAB 복사, MFA, r3 DB·TextGrid 수정은 모두 0건이다. 다음은 55건 exact
> shard에 대한 별도 scope-bound 연구자 승인 Gate이며, 전 연도 MFA를 반복하지
> 않는다.**

> **2026-08-15 2020–2025 r3 안전 본체 완료:** 여섯 연도를 동일
> `common_pron_mfa_r3_20260809` 발음 release, Korean MFA v3.3.0 음향모델,
> phone inventory와 6-tier schema로 신규 정렬했다. 2025 입력 458,413건은 정렬
> 성공 457,611건과 연구자 승인 기술 미정렬 802건으로 exact-ID 완전 회계됐다.
> 보존 DB SHA-256은
> `5d7eab5a986dd39af2fc163d94bd0d8a378a891d242f984a2e536a24fcd5c0e6`다.
> 457,611개 6-tier와 동반표 4종을 수출했고 독립 QC는 coverage 100%, 25개
> hard-failure 범주 전부 0, DB 재수출 semantic·byte 24/24로 `passed`다.
> `QC_STATE.json` SHA-256은
> `4f32d0b4993967ebef245a4672ea73e3738696f60981d58b0808484332cfb3b3`다.
> **현재 장시간 실행은 없으며, 2020–2025 MFA·전수 수출·QC를 다시 실행하지
> 않는다. 다음은 여섯 연도 완료 state의 읽기 전용 교차 감사와 별도 follow-up
> shard다.**

> **2026-08-15 연구 DB v1 준비 A–C 완료:** 기존 r3 DB·TextGrid를 변경하지
> 않고 6개년 same-contract 교차 감사, 저장공간 읽기 전용 계획, 원천
> 5,103,356발화 exact-ID 상태 장부를 완료했다. 회계는 정렬 성공 4,286,046,
> pre-MFA 기술 제외 95,860, post-MFA 기술 제외 3,086, 발음 후속 718,364,
> 인프라 단계 방법론 제외 0이며 누락·중복·미분류는 모두 0이다. 보존 DB와 동반표
> 실제 SHA를 재확인했고 별도 감사기가 510만 행을 다시 검사해 `passed`다.
> 내부 package는
> `outputs/releases/nikl_dialogue_research_db_v1_0_0_rc0_20260815`다.
> **다음은 D 이유별 recovery shard이며, r3 본체 재실행·삭제·이동·외부 배포는
> 아직 하지 않는다.**

> **2026-08-15 D단계 용량 Gate 완료:** `ari30`의 명시 승인 범위인 2024–2025
> r3 QC 완료 MFA temp의 재생성 가능 exact allowlist 126개·38,640,655,415
> bytes(35.987 GiB)만 삭제했다. 삭제 후보 잔존 0, 보호 파일 누락 0이며 2024·
> 2025 DB의 사후 SHA-256이 A–C 정본과 일치한다. 최종 6-tier·원자료·공통발음
> 계약도 보존됐고 D: 여유는 64.184 GiB다. 다음은 D0 입력 계약과 D1 이유별
> exact-ID routing 장부이며, 아직 recovery MFA를 시작하지 않는다.

## 최근 완료 이력

아래 블록은 각 날짜 당시의 정지점 기록이며 현재 실행 지시가 아니다. 실제 다음
단계는 위 2026-08-15 블록만 따른다.

> **2026-08-13 2024 r3 장시간 MFA 시작 준비 완료:** 2024 조합검색 33/33 shard와
> 연간 7표, source contract, 발음 연구 DB(728,257발화·5,141,540 occurrence),
> 입력·정렬 계약과 독립 감사를 완료했다. 최종 MFA 입력은 594,404개이며 WAV 누락은
> 0이다. PowerShell 5.1 69개·Python 564 tests와 보수적 용량 preflight가 GO이고,
> 2023 완성본 SHA와 결속한 2023→2024 Gate도 8/8 통과했다. **이 기록 시점에는
> 2024 MFA가 아직 시작되지 않았으며**, 다음 한 단계는 사용자가 단일 PowerShell에서 2024 runner를
> 실행하는 것이다. 2020–2023 DB·6-tier·QC는 변경하지 않는다.

> **2026-08-13 2023 r3 정렬·수출·독립 QC 완료:** 2023 exact-ID 입력
> 494,580건을 2020–2022와 같은 `common_pron_mfa_r3_20260809` 계약으로 새로
> 정렬했다. 보존 DB SHA-256은
> `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`이며,
> 성공 494,228건과 기술 미정렬 352건을 exact-ID로 완전 회계했다. 연구자
> `ari30`이 candidate `e6716a369412...eb878b3b`를 명시 승인했고, 6-tier
> 494,228개와 gzip 동반표 4종을 수출했다. 독립 전수 QC는 coverage 100%·hard
> failure 0, 보존 DB 재수출 semantic·byte 24/24로 `passed`다. 2020–2023은
> 재실행하지 않는다. 이어 독립 QC 뒤 재생성 가능한 temp 252파일만 exact
> allowlist로 삭제해 68.201 GiB를 회수했고, D: 여유는 116.806 GiB가 됐다.
> DB·최종 6-tier·로그·모델·계약은 보존했다. 다음 한 단계는 2024 exact-ID·
> capacity preflight와 2023→2024 전환 Gate다.
>
> **2026-08-12 2022 r3 정렬·수출·독립 QC 완료:** 2020·2021 완료 SHA를
> 변경하지 않고 2022 exact-ID 751,721건을 동일 r3 계약으로 새로 정렬했다.
> `ALIGN_DONE_2022.json`은 2026-08-11 21:41 KST에 `passed`로 생성됐고,
> DB 7,146,942,464 bytes의 SHA-256은
> `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`다.
> 정렬 성공 751,383건과 기술 미정렬 338건을 exact-ID로 완전 회계했으며,
> 연구자 `ari30`이 candidate `272bcc134776...3b2357b7a`를 명시 승인했다.
> 2026-08-11 23:36–2026-08-12 01:12 KST에 6-tier 751,383개와 gzip 동반표
> 4종을 수출했다. 독립 QC는 TextGrid coverage 100%·hard failure 0,
> 동반표 계약 오류 0, DB 재수출 semantic·byte 24/24로 완료됐다. 최종
> `QC_STATE.json`은 `passed`다. 2022 r3 MFA·전수 수출·QC는 다시 실행하지
> 않는다. 이 완료 SHA는 통과한 2022→2023 전환 Gate에 결속됐다.

> **2026-08-11 2021 r3 정렬·수출·독립 QC 완료:** 2020 최종 QC state와 정렬
> marker의 SHA를 동결한 채 2020 MFA·전수 수출을 반복하지 않았다. 2021 r3 입력
> 1,207,299건은 4,139세션의 WAV/LAB로 materialize됐고, 같은 exact-ID 수의 보존
> DB가 2026-08-11 00:19 KST에 완료됐다. DB SHA-256은
> `faaef1c2f7c8dd013f7e90dc1694d6514e9b5bdf8fdbe0e60b07d179925a7731`이다.
> word·phone 정렬 성공은 1,206,862건, post-MFA 후보는 437건
> (`mfa_alignment_missing` 413, feature 생성 실패 24)이다. 후보 identity
> `5a4c3de672f...be6a7be35`는 자동 승인하지 않았으며, 연구자가 08:16 KST에 명시
> 승인했다. feature 실패 24와 DB 내 미정렬 413을 분리한 exact-ID preflight가
> 미승인 차이 0으로 통과했다. 08:30–11:00 KST에 6-tier 1,206,862개와 gzip
> 동반표 4개를 수출했다. 동반표는 발화 1,206,862·word 8,926,793·phone
> 32,776,584·제외 437행이며 `spn`은 0이다. 이어 11:05–11:58 KST에 독립 QC를
> 완료했다. 전수 coverage 100%·hard failure 0, 보존 DB 재수출은 semantic·byte
> 24/24이고 최종 `QC_STATE.json`은 `passed`다. 원자료 변경·MFA 재계산·전수
> 수출 반복은 모두 없었다. 이 state의 SHA는 2021→2022 전환 Gate에 고정됐고,
> 이후 2022 완료 결과는 바로 위 최신 state가 대체한다.

> **2026-08-09 r3 2020 정렬 DB 완료·export 직전 상태:** 2020 exact-ID 입력은
> 782,715발화이며 alignment contract ID는
> `3eff5ae34eb1015c05532140162636609099f1fd1203f561cc06d837039d8e8a`다.
> production Gate 승인 뒤, r3 발음 유형표가 연도별 발화·참조 어절 CSV에 직접
> 연결되지 않은 마지막 DB 공백을 MFA 전에 발견했다. 원 형태소 CSV를 덮어쓰지
> 않고 type catalog–utterance scope–reference-eojeol occurrence의 정규화 DB와
> 독립 감사를 추가했다. 보강된 runner는 이 감사가 없으면 NO-GO한다.
> 2020 정규화 DB는 발화 870,437개·참조 어절 3,056,807개를 전수 회계해 독립
> 감사 `passed`를 받았다. r3 MFA DB도 완료되어 782,432건은 word+phone 정렬,
> 283건은 기술적 `mfa_alignment_missing` exact-ID 후속 대상으로 동결됐다.
> 연구자가 2026-08-10에 이 범주를 명시 승인했고, 실제 수출 preflight도 모든
> exact-ID 차이 0·`spn` 0·phone inventory 밖 0으로 통과했다. 이어 보존 DB에서
> 6-tier 782,432개와 gzip 동반표 4개를 수출했다. 완료 감사에서 coverage 100%,
> 실패·누락·partial 0, 동반표 SHA 4/4 일치를 확인했다. MFA DB는 재계산하지
> 않았다. 독립 연도 내용·계약 QC도 2026-08-10에 완료됐다. 782,432개 전수 감사는
> coverage 100%·hard failure 25범주 전부 0이며, 보존 DB 24세션 재수출은
> semantic·byte 24/24 동일하다. 표본 검사 첫 호출의 r3 input-ID 호환 오류는
> source 변경 없이 수정했고, 통과한 25분 전수 감사 checkpoint를 재사용해 표본만
> 55.524초에 재개했다. MFA·전수 수출은 반복하지 않았다. 다음 단계는 2020을
> 동결하고 2021 한 연도만 같은 r3 계약으로 준비하는 것이다.

> **2026-08-07 발음 입력 Gate 보정:** 2022 공식 표본에서 `있지·있는·없는·
> 어쨌든` 등의 MFA 입력 phone이 기존 규칙 예상형과 불일치함을 확인했다. 전수
> 감사 결과 이 문제는 특정 연도나 표본 파일만의 문제가 아니므로 r2 신규 실행을
> 차단했다. 아래 2020–2022의 “완료”는 r2 계산·자료구조·감사 증거의 완료를
> 뜻하며 최종 공통발음 정본 승인을 뜻하지 않는다. 연구자는 2026-08-09에
> 2020–2025 pronunciation-safe pool의 정렬 가능 발화 전체를 동일 r3 계약으로
> 새로 정렬하고, 기술적 제외는 exact-ID로 별도 회계하며 기존 r2 interval은
> 최종 r3에 재사용하지 않는 방안을 승인했다. 718,364 follow-up 발화는 별도
> exact-ID shard로 보존한다.

> 2026-08-07 18:02 보정: 2022 MFA 계산과 보존 DB direct export, 연구용 6-tier
> 864,690개, gzip 동반표 4종, 독립 전수 감사와 DB 재수출 24/24 동등성 검사가
> 완료됐다. 남은 core 단계는 공식 연구자 인프라 표본 24개의 한 번의 Gate뿐이다.
> 연구자가 표본에서 발견한 겹침·잘림 의심·소음 문제는 2020–2025 공통 품질
> 감사로 확장했다. 정렬 가능한 발화는 데이터 구축을 위해 보존하고 승인된 연구
> 주 분석 제외만 `analysis_only`로 붙인다. 이 품질 결정 자체는 유지하되,
> 발음 입력 r3가 채택되면 2020–2025 pronunciation-safe 중 정렬 가능 집합 전체를
> 다시 정렬하고 같은 품질
> Gate를 정렬 전·후에 적용한다. 근거는
> `docs/decisions/DECISION_dialogue_audio_quality_gate_2020_2025_20260807.md`와
> `outputs/reviews/dialogue_audio_quality_2020_2025_20260807/`에 있다.

이 문서는 지금 유효한 완료·미완료·다음 단계만 기록한다. 2026-08-06 이전의
상세 누적본은
`docs/archive/pre_2022_refresh_20260806/PROJECT_CURRENT_STATE_pre_2022_20260806.md`에
보존한다.

## 연구 목적

```text
형태소·표기상 음운 환경을 CSV/Parquet에서 검색
  → utt_id로 WAV·TextGrid·메타데이터 수집
  → 선별 후보에 KOINA·이어붙이기·wav2vec2 보조 분석
  → 연구자가 음성·TextGrid를 보고 실제 실현 여부 판정
```

MFA/G2P phone은 강제정렬용 분절 보조값이다. 규칙 예상 발음, 사전 발음,
음성에서 실현된 발음과 동일시하지 않는다.

## 현재 연도별 상태

| 연도 | 검색표 | r2 계산·6-tier 보존 | 연구자 검토 | r3 최종 정렬 |
|---:|---|---|---|---|
| 2020 | 완료 | 읽기 전용 증거로 완료 | Gate B 검토를 회귀 근거로 보존 | r3 DB·283 승인·6-tier 782,432·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2021 | 완료 | 읽기 전용 증거로 완료 | 24/24 검토를 회귀 근거로 보존 | r3 DB·437 승인·6-tier 1,206,862·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2022 | 완료 | 읽기 전용 증거로 완료 | 기존 24개 검토를 회귀 근거로 보존 | r3 DB·338 승인·6-tier 751,383·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2023 | 완료 | r2 생산 없음 | 기술 후보 352건 명시 승인 | r3 DB·352 승인·6-tier 494,228·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2024 | 완료 | r2 생산 없음 | 기술 후보 874건 명시 승인 | r3 DB·874 승인·6-tier 593,530·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |
| 2025 | 완료 | r2 생산 없음 | 기술 후보 802건 명시 승인 | r3 DB·802 승인·6-tier 457,611·동반표 4개·독립 전수 QC·DB 표본 24/24 완료; SHA 동결 |

## 2020 — r2 계산·검토 완료, 읽기 전용 보존

- 공통 Jamo r2 신규 MFA, 6-tier 868,187개, 동반표 4개, 독립 전수 감사,
  DB 표본 24/24, 연구자 표본 24/24를 완료했다.
- Gate B는 16/16 core check, 실패 0, `allow_remaining_years=true`다.
- 보존 DB는 `D:\mfa_tmp\2020\2020.db`다.
- r2 MFA·export·광범위 Gate·검토를 같은 조건으로 반복하지 않는다. r3 채택 뒤에는
  같은 사람 검토를 재사용하고 정렬 계산만 새 6개년 계약으로 수행한다.
- 7번째 `pron_reference_utt` 전수 복사는 core 완료 조건이 아니다. 현재
  2세션 914개로 구현 계약이 검증됐으며, 전수 backfill은 다른 MFA와 D: I/O가
  겹치지 않을 때 수행한다.

## 2021 — r2 생산·연구자 Gate 완료, 읽기 전용 보존

- `morph_search.v3` 7표와 frozen source contract가 완료됐다.
- MFA 정렬은 2026-08-04 20:53:45 KST에 exit 0으로 끝났다.
- 보존 DB는 `D:\mfa_tmp\2021\2021.db`, checkpoint marker는
  `D:\mfa_eojeol\done\2021.direct_db_ready`다.
- 정렬 당시 pre-MFA 승인 제외는 1,502건이다. post-MFA exact-ID 기술 제외
  535건을 더한 export/QC 회계는 2,037건이다. 삭제가 아니라 후속 회수 대상으로
  보존한다.
- 6-tier·동반표는 1,371,883발화다. 독립 감사 coverage 100%, hard failure 0,
  `spn` 0이며 DB 재수출 표본은 semantic·byte 24/24 일치했다.
- 19개 후행 무음 word 표지는 시간·phone을 유지하고 빈 word label로 국소
  정규화했다. MFA DB·WAV·LAB·원 CSV는 변경하지 않았다.

- 연구자는 1–20번과 21–24번, 총 24개 표본의 WAV·LAB·TextGrid 연결,
  6-tier, 정렬, 검색 정보가 대체로 적절하다고 확인했다. 원 pending CSV를
  바이트 동일 보존한 뒤 명시 승인 문장을 24/24에 기록했다.
- 승인 보고서는 `automatic_approval_performed=false`,
  `materialized_from_explicit_researcher_statement=true`,
  `allow_next_year_mfa=true`다.
- checkpoint-resume mode와 별도 `direct_db_ready` marker를 같은 6-tier 생산
  계약으로 검증한 `2021 → 2022` Gate는 2026-08-06에 실패 검사 0으로 통과했다.
- 우리말샘 occurrence 12,015,453행, 원 표기 어절 비교표 6,610,698행,
  발화 index 1,373,920행을 독립 검증했다.
- 7-tier 파생본은 4,139세션·1,371,883개다. 기존 6개 tier 변경 0,
  `pron_reference_utt` 경계·label 오류 0으로 2026-08-05 21:20 KST에
  독립 전수 검증을 통과했다.
- r2 산출을 같은 조건으로 반복하지 않는다. r3 채택 뒤 정렬·6-tier·동반표는 새
  release root에 만들고, 기존 7-tier와 검토 결과는 회귀·비교 근거로 보존한다.

## 2021 — r3 신규 정렬·6-tier·독립 QC 완료

- r3 exact-ID 입력 1,207,299건과 DB 발화 1,207,299건이 일치한다.
- 1,206,862건은 word·phone interval이 모두 있고, 437건은 기술적 후속 후보로
  동결됐다. 후보는 정렬 없음 413건과 feature 생성 실패 24건이다.
- `ALIGN_DONE_2021.json`은 `status=passed`이며 DB 경로·bytes·SHA를 고정한다.
- 연구자는 437건을 명시 승인했고, feature 실패 24·DB 내 미정렬 413을 분리한
  preflight가 통과했다. 보존 DB에서 6-tier 1,206,862개와 동반표 4개를 수출했다.
  독립 전수 감사 coverage는 100%, hard failure는 0이고, DB 재수출은
  semantic·byte 24/24다. 최종 `QC_STATE.json`은 `passed`다.
- 2021 r3 MFA·전수 수출·QC는 다시 실행하지 않는다. 2020 변경도 금지한다.
  2021 완료 SHA를 이용한 2021→2022 r3 전환 Gate는 통과했다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2021_20260811.md`

## 2022 — r3 신규 정렬·6-tier·독립 QC 완료, SHA 동결

- r3 source snapshot·입력 계약·발음 연구 DB·alignment contract와 독립 감사를
  완료했다. source 866,359 = safe 752,591 + follow-up 113,768이며, safe 집합의
  pre-MFA 기술 제외 870을 뺀 exact-ID 751,721건이 새 r3 정렬 대상이다.
- source WAV 누락은 0이다. source 밖 WAV 11,798개는 snapshot에만 기록하고 입력으로
  암묵 선택하지 않는다. 과거 r2 실패 438건 중 조건을 충족한 337건은 새 r3
  정렬에 재진입한다.
- 발음 연구 DB는 866,359발화·4,504,375 occurrence이며 미회계 발화·unknown
  nonempty LAB token은 0이다. alignment contract ID는
  `f53b6c2be25fc4e694796ae123c005258ee9913a4b6bf4cf6625220dec4113cb`다.
- 실제 runner `-PreflightOnly`는 실패 검사 0, 필요 공간 52.193 GiB 대비 D: 여유
  114.028 GiB로 GO였고, 2026-08-11 15:05 KST에 시작해 21:41 KST에 보존 DB와
  `ALIGN_DONE_2022.json`을 완료했다. DB SHA-256은
  `610054531403f0ca13292194b13f6e63e509434435864aec9f7118d888bfe5b2`다.
- DB exact-ID는 입력 751,721 = 정렬 751,383 + 승인 기술 미정렬 338로 닫혔다.
  후보 identity `272bcc134776...3b2357b7a`는 자동 승인하지 않았고 연구자가
  명시 승인했다. r2 미정렬 438과 비교하면 공통 318, r3 회수 120, r3 신규
  미정렬 20이다.
- 6-tier 751,383개와 gzip 동반표 4종을 수출했다. 동반표는 utterance
  751,383, word 5,882,284, phone 21,857,009, excluded 338행이다.
- 독립 QC는 coverage 100%·hard failure 0, 동반표 오류 0, 보존 DB 재수출
  semantic·byte 24/24로 `passed`다. MFA·전수 수출·QC를 다시 실행하지 않는다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_2022_preflight_20260811.md`,
  `docs/decisions/RESULT_mfa_r3_alignment_database_2022_20260812.md`

## 2023 — r3 신규 정렬·6-tier·독립 QC 완료, SHA 동결

- source 677,262 = pronunciation-safe 582,389 + follow-up 94,873이며, safe 집합의
  pre-MFA 기술 제외 87,809를 뺀 exact-ID 494,580건을 새 r3 DB에 정렬했다.
- 입력 494,580 = 정렬 성공 494,228 + 승인 기술 미정렬 352로 완전 회계했다.
  후보는 `mfa_alignment_missing` 351건과 feature 생성 실패 1건이다.
- `ALIGN_DONE_2023.json`은 `status=passed`다. 보존 DB SHA-256은
  `3c6695ac2033612d514e6ca57711d006d2505c6ddb25124b666865df8c315108`이다.
- 연구자 명시 승인 뒤 보존 DB에서 6-tier 494,228개와 동반표 utterance
  494,228·word 3,832,921·phone 14,781,191·excluded 352행을 수출했다.
- 독립 QC는 coverage 100%·hard failure 0, 동반표·contract 오류 0, 보존 DB
  재수출 semantic·byte 24/24로 `passed`다. `QC_STATE.json` SHA-256은
  `115b81f539d87eb30892df2ffb0052e5d569884569aa4ff9f30c0b39db91d958`이다.
- 2023 MFA·전수 수출·QC를 다시 실행하지 않는다. 다음은 이 완료 SHA를 사용하는
  2023→2024 전환 Gate다.
- 상세 근거:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2023_20260813.md`

### 2022 r2 역사적 비교 증거 — 현행 생산 입력 아님

아래 항목은 r3 채택 이전의 r2 결과와 문제 발견 경위를 보존한 기록이다. 현재
TextGrid·동반표·분석 범위에는 바로 위 r3 완료본만 사용하며, 아래 r2 DB·수출물은
재실행하거나 r3와 섞지 않는다.

- search master와 source/input/alignment 계약은 완료됐다.
- 활성 LAB 865,128개 중 864,690개가 정렬됐고 438개는 최종 interval이 없는
  `mfa_alignment_missing` exact-ID 집합이다.
- 보존 DB는 `D:\mfa_tmp\2022\2022.db`이며 r2 증거로 변경하지 않는다. r3 채택
  뒤 별도 DB·release root에서 다시 정렬한다.
- 연구자는 20개 연결 표본의 WAV·LAB를 확인했다. 그 과정에서 겹침·잘림 의심·
  심한 소음을 발견해 2020–2025 공통 품질 감사로 확장했다.
- 연구자는 2026-08-07 15:04 KST에 438건을
  `mfa_alignment_missing / alignment_and_analysis`로 명시 승인했다. 원 pending
  작업본은 SHA-256 동일 archive로 보존했고, candidate identity는
  `36912d5d3802...`로 유지됐다.
- 결합 승인 preflight는 기존 1,231건 + post-MFA 438건 = 1,669건 exact-ID
  일치, DB 무변경, 출력 생성 0으로 통과했다.
- 보존 DB direct export는 2026-08-07 17:28 KST에 완료됐다. 연구용 6-tier
  864,690개, coverage 100%, `spn` 0, 정확 ID 대사 `passed`이며 1,669개 제외는
  별도 동반표에 보존했다. gzip 동반표는 발화 864,690행, 어절 7,039,920행,
  phone 26,372,701행, 제외 1,669행이다.
- 독립 전수 감사는 hard failure 20범주가 모두 0으로 통과했다. 보존 DB에서 다시
  내보낸 24세션·24발화 표본은 최종 TextGrid와 semantic·byte 모두 24/24
  일치했다. 실행 queue는
  `mfa_r2_prod_safe_body_2022_20260806_postmfa`이며 DB는 계속 보존한다.
- 공식 연구자 표본 24개를
  `outputs/reviews/mfa_production_2022_mfa_r2_prod_safe_body_2022_20260806_postmfa`
  에 준비했고 연구자가 24개 모두의 연결·정렬·6-tier·검색 정보를 확인했다.
  이 검토에서 발견한 공통발음 입력 불일치를 r3 Gate의 회귀 표본으로 재사용한다.
  실제 음운 실현 판정은 이 인프라 Gate의 대상이 아니다.

## 2023–2025 r3 완료 상태

승인 제외 계약과 LAB marker input ID를 각 연도에서 exact-ID로 결속했고, 세 연도
모두 정렬·6-tier·동반표·독립 QC까지 완료했다. 음원 품질 및 기술 제외는 성공한
안전 본체와 섞지 않고 별도 exact-ID 후속 범위로 보존한다.

| 연도 | r3 입력 | 정렬 성공 | 승인 기술 후속 | 6-tier·QC |
|---:|---:|---:|---:|---|
| 2023 | 494,580 | 494,228 | 352 | 494,228·passed |
| 2024 | 594,404 | 593,530 | 874 | 593,530·passed |
| 2025 | 458,413 | 457,611 | 802 | 457,611·passed |

## 발음 참조 레이어의 위치

- 참조 정본:
  `D:\10_LAYERS\10_pronunciation_reference\dictionary_pron_registry_v2_20260805`
- 구 진단 계약: `config/pronunciation_reference_layer_v1.json`
- 사전 후보는 검색·참조용이며 MFA 입력사전을 자동 교체하지 않는다.
- 이 분리가 r2 입력 배선 공백을 만들었으므로 v1 occurrence·비교/index·7-tier를
  더 생성하지 않는다. 이미 만든 2020–2021 자료는 r3 근거로 재사용한다.
- r3 정본은 `config/common_pronunciation_resource_contract_v3_draft.json`을
  채택 계약으로 승격한 뒤 canonical 선택표와 MFA 사전을 같은 projection으로 낸다.

## 현재 안전 정지점

- 실행 중인 장시간 작업 없음
- 2020–2025 r3 MFA·6-tier·동반표·독립 QC 완료 SHA 동결
- 2025 exact-ID 458,413 = 정렬 457,611 + 승인 기술 후속 802
- 2025 독립 QC coverage 100%·hard failure 0·DB 재수출 24/24
- 2020–2023 r3 temp exact cleanup 완료: 252파일·68.201 GiB, blocker 0
- 2024–2025 r3 temp exact cleanup 완료: 126파일·35.987 GiB, blocker 0
- D: 2026-08-15 정리 후 여유 64.184 GiB; DB·최종 6-tier·원자료·로그·모델·계약 보존 확인
- 다음 단계는 D0 입력 계약과 817,310건 이유별 recovery routing 장부
- 2022 post-MFA 438건과 결합 제외 1,669건의 승인·회계 완료
- 2022 공식 연구자 인프라 표본 24개 검토 완료·발음 입력 불일치 발견
- r2 프로젝트 발음 release Gate 차단 완료
- r3 canonical inventory 881,237형 생성 완료
- exact Roman 표면 donor 후보 346형 생성 완료(아직 최종 선택 아님)
- 규칙 목표형 Jamo G2P 310,605개·13 shard 후보 생성 및 읽기 전용 독립 감사 완료
- no-path·`spn`·중복·입력 밖 key·acoustic inventory 밖 phone 모두 0
- G2P 후보–독립 규칙 Roman 전수 exact Gate와 별도 읽기 전용 감사 완료
- 대상형 exact 96,284개(30.999%), mismatch 214,321개(69.001%)
- source 출현 exact 1,676,283회(37.476%), mismatch 2,796,609회(62.524%)
- 사전 근거 일치 exact 3,078형은 후속 선택 후보, 사전 충돌 14형과 독립 근거 없는
  exact 94,134형은 각각 보류, mismatch 215,184형은 자동 선택 불가
- mismatch 214,321 target·215,184 source형 전수 편집 진단과 독립 감사 완료
- mismatch 출현 중 표상 동등성 후보 1,686,625회(60.310%), 실질 차이 후보
  1,075,211회(38.447%), model 내부 대조 34,667회(1.240%), 표상 추가 검토
  106회(0.004%)
- 전체 2,625개 패턴 중 56행이 2,590,212회(92.620%)를 포괄하는 결정표 생성;
  자동 동등성 승인과 연구자 즉시 검토 요구는 모두 없음
- 후보 비교는 최종 선택이 아니며 canonical selection·adoption·TextGrid 변경 없음
- 좁은 model 단위화 관계와 exact 문맥 donor projection 계약·전수 생성·독립
  감사 완료: target 후보 가능 264,906개(85.287%)·3,744,243회(83.710%)
- 자동 보류 45,699개·728,649회; 잔여 1,799패턴은 95.136% 출현과 각 범주
  대표를 포괄하는 56행 handoff로 축약
- source 중 projection과 독립 사전 근거가 함께 일치한 것은 5,948형·349,689회;
  이 또한 canonical 최종 선택 전 후보
- canonical exact donor 382,891형 전역 projection·독립 감사 완료: 기존과 동일
  286,556 target, 후보 획득 13,172, 후보 상실 10,799, phone 변경 78
- 전역 결과를 반영한 09 readiness·독립 감사 완료: candidate 준비 752,270형
  (26,197,593회), 복수 변이 정책 35형·163회, zero-fallback 보류
  128,932형·1,649,312회
- 잔여 보류: target projection 미해결 43,428형, 아직 target이 아닌 no-rule
  실질 불일치 85,504형. 후자의 83,922형은 이미 동일 Jamo G2P 1-best 출처다.

no-rule 85,504형·1,140,107회의 전수 특성화와 독립 감사가 완료됐다. 모두
완성형 한글 음절이며, 숫자·기호·라틴 문자·낱자 자모는 없다. 주요 비배타적
진단 표지는 비음 조음 위치·경계 54,073형, 분절 수·탈락 35,703형,
활음·모음 단위화 22,168형, 후두 대립·phone 매핑 13,550형이다. 이는 규칙
정답이 아니라 현재 규칙 엔진·phone 매핑의 coverage를 점검할 우선순위다.

후속 읽기 전용 coverage 감사에서 모든 변이가 수의적 위치동화로만 다른
36,568형·525,747회, 위치동화와 겹치지 않으면서 모든 변이가 frozen 기본사전에
정확히 있는 811형·229,177회를 분리했다. 일부 변이만 위치동화인 82형·16,271회와
나머지 48,043형·368,912회는 보류한다. 107 acoustic phone 중 33개는 frozen
사전의 동일 길이 위치 대조에서 둘 이상의 규칙키와 반복 공존하므로, phone만으로
기저·표면 음소를 일대일 복원하지 않는다. 특히 `pʲ`는 B/P 양쪽에 쓰인다.

stage 12 readiness v2는 검증된 37,379형을 **정렬용 candidate-only**로 추가했고
독립 전수 감사를 통과했다. 이어 Stage 13에서 frozen 기본사전의 단어·음절·
국소 분절·이차조음 문맥 inventory를 만들고 zero-fallback 91,553형을 기존
canonical donor와 전수 대조했다. 단일 근거 10,594형, 복수 근거 22,171형,
출처 충돌 48,780형, 근거 없음 10,008형이며 독립 감사가 통과했다.

Stage 14 readiness v3는 단일 근거 중 기존 r2 phone·Roman을 바이트 그대로
유지하고 모든 issue가 frozen 사전의 onset+glide 이차조음 문맥으로 지지되는
6,141형·90,544회만 정렬용 candidate-only로 추가했다. candidate 준비는
795,790형·27,043,061회, zero-fallback hold는 85,412형·803,844회다. 881,237행
전수 v2 대조에서 비대상 필드 변화 0, phone·Roman 변화 0을 확인했다.

Stage 15는 남은 단일 근거 4,453형·72,030회의 4,900 issue를 ㅢ 규칙, 활음·
`ng`·종성 삽입, 후두 대립·비음/종성·모음·이차조음 치환, 혼합 편집으로 전수
분류하고 독립 감사를 통과했다. 자동 후보는 0형이고 4,453형 모두 기존 hold를
유지한다. `중에서`처럼 donor `ŋ`가 하나여도 기존 phone열에 분절을 새로 넣는
경우는 자동 승격하지 않는다.

Stage 16은 이 4,453형을 6개년 동결 검색 master 5,103,356발화와 연결했다.
exact 표면 어절은 68,285회, Bareun group과 표면 어절이 1:1일 때의 안전한
형태소·품사 문맥은 60,292회 연결됐다. 비1:1 분석은 억지로 맞추지 않았다.
자동 후보는 0형이며 4,453형 hold, MFA·TextGrid 미변경을 유지했고 독립 감사가
통과했다.

Stage 17은 사전·규칙 Roman exact 141형을 실제 등재 `pron_1/2` 65형과 legacy
기계 `pron_g2p` 76형으로 분리했다. 등재 65형의 전체 phone열을 동결 문맥 donor로
재구성해 14형·200회만 candidate-only로 준비하고 51형·2,851회는 복수·충돌로
hold했다. Stage 18 readiness v4는 이 14형만 병합했다. candidate 준비는
795,804형·27,043,261회, zero-fallback hold는 85,398형·803,644회다. v3/v4
881,237행 전수 감사에서 비대상 변화 0을 확인했다.

Stage 19는 동결 pre-MFA `pron_reference_form`과 실제 LAB tokenizer로
5,103,356발화를 전수 다시 읽었다. candidate만 포함한 safe body는
4,384,992발화(85.923694%), hold·policy·빈 LAB가 하나라도 있는 follow-up은
718,364발화다. unknown 어절은 0이며, 여섯 연도에 같은 발화 단위 라우팅 규칙을
적용했다. 부분 어절 삭제·대체는 하지 않았다. 독립 전수 감사가 통과했다.

Stage 20은 795,804형·796,061변이의 safe-body MFA 후보 사전을 물질화하고
107-phone 동결 acoustic inventory와 전수 byte projection을 독립 감사했다.
inventory 밖 phone, lexical `spn`/`sil`, non-candidate 누출은 모두 0이다. 파일명과
manifest의 `NOT_ADOPTED`는 당시 Stage 20 후보 상태를 보존한다. 이 후보를
byte-exact selected projection으로 물질화한 별도
`common_pron_mfa_r3_20260809` release는 2026-08-09 production Gate에서
채택됐다. Stage 폴더 자체를 production release로 사용하지 않는다.

Stage 21은 기존 연구자 지적 표본 `있지·놨던·슬프겠지만·없는` 네 발화만 새
후보 사전으로 표적 정렬했다. 입력 phone exact 4/4, interval 연속 4/4,
word–phone 바깥 경계 4/4, `spn` 0으로 자동 검사를 통과했다. 연구자는 네 경계를
모두 승인했다. 승인 계약은
`outputs/reviews/common_pron_r3_targeted_regression_20260808/RESEARCHER_APPROVAL.json`
이다.

연구자는 같은 승인에서 2020–2025 pronunciation-safe 4,384,992발화를 r3 대상
pool로 삼고, 독립 정렬 가능성 Gate를 통과한 발화를 모두 동일 r3 계약으로 새로
정렬하며 follow-up 718,364발화를 별도 shard로 보존하도록 결정했다.
따라서 더 이상 full-coverage/단계 채택이나 r2 interval 재사용을 다시 선택하지
않는다. 외부 workflow 리뷰, r3 전용 release/adoption, 연도별 checkpoint runner,
정책 감사와 2020 preflight는 완료됐다. 현재는 2020 장시간 runner를 사용자가
시작하기 직전이며, DB 완료 전 TextGrid materialization은 시작하지 않는다.

## 정본 문서

- 생산 순서: `docs/RUNBOOK_production_2020_2025.md`
- 발음 참조 파생층: `docs/RUNBOOK_pronunciation_reference_layer_2020_2025.md`
- 자산 위치: `docs/ASSETS_LEDGER.md`
- 상세 시행착오: `docs/WORK_HISTORY_2026-08.md`
- r3 후보 선택 결정:
  `docs/decisions/DECISION_common_pron_r3_candidate_resolution_20260807.md`
- r3 G2P 후보 실행 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_candidate_phase_20260808.md`
- r3 G2P–규칙 Roman 전수 Gate 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_agreement_gate_20260808.md`
- r3 G2P mismatch 전수 진단 결과:
  `docs/decisions/RESULT_common_pron_r3_g2p_mismatch_diagnostics_20260808.md`
- r3 model 표상·문맥 projection 후보 결과:
  `docs/decisions/RESULT_common_pron_r3_model_projection_candidates_20260808.md`
- r3 881,237형 selection-readiness 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_20260808.md`
- r3 전역 donor projection·09 readiness 결과:
  `docs/decisions/RESULT_common_pron_r3_global_projection_v2_20260808.md`
- r3 no-rule 보류형 전수 특성화 결과:
  `docs/decisions/RESULT_common_pron_r3_no_rule_hold_characterization_20260808.md`
- r3 규칙·MFA phone coverage 감사 결과:
  `docs/decisions/RESULT_common_pron_r3_rule_phone_coverage_audit_20260808.md`
- r3 selection-readiness v2 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_v2_20260808.md`
- r3 readiness v2 잔여 hold 우선순위:
  `docs/decisions/RESULT_common_pron_r3_readiness_v2_residual_priorities_20260808.md`
- r3 문맥 보존 frozen 사전 donor 감사:
  `docs/decisions/RESULT_common_pron_r3_contextual_dictionary_donor_audit_20260808.md`
- r3 selection-readiness v3 결과:
  `docs/decisions/RESULT_common_pron_r3_selection_readiness_v3_20260808.md`
- r3 단일 문맥 근거·phone 변경 필요형 감사:
  `docs/decisions/RESULT_common_pron_r3_unanimous_phone_change_audit_20260808.md`
- r3 pre-adoption 발화 라우팅:
  `docs/decisions/RESULT_common_pron_r3_pre_adoption_routing_20260808.md`
- r3 safe-body 후보 사전:
  `docs/decisions/RESULT_common_pron_r3_safe_body_candidate_20260808.md`
- r3 2022 표적 회귀 정렬:
  `docs/decisions/RESULT_common_pron_r3_targeted_regression_20260808.md`
- r3 adoption 선택 Gate:
  `docs/decisions/DECISION_common_pron_r3_full_realign_2020_2025_20260809.md`
- r3 전수 재정렬 workflow:
  `docs/WORKFLOW_mfa_r3_full_realign_2020_2025.md`
- 리밋·새 대화 재개: `docs/environment/CONTINUITY_AFTER_LIMIT_OR_NEW_THREAD.md`

## 2026-08-09 21:30 현재: 2020 r3 정렬 DB 완료·export 전 정지

- 2020 r3 코퍼스는 2,231세션·782,715 WAV/LAB 쌍으로 완료됐고, 같은 계약의
  재개 실행이 17:28–21:20에 정상 종료됐다.
- `ALIGN_DONE_2020.json`은 `status=passed`다. 보존 DB는 5,534,134,272 bytes이며
  marker와 실제 SHA-256이 일치하고 SQLite `quick_check=ok`다.
- 782,715발화 중 782,432발화에 word·phone interval이 모두 있고 post-MFA
  미정렬은 283건이다. `spn` interval은 0이며 coverage는 99.9638%다.
- 최초 `fstcompile` PATH 실패는 runner의 conda runtime 상속과
  `check_third_party()` preflight hard Gate로 보정했다. 실패 당시 코퍼스·DB를
  삭제하지 않고 같은 계약에서 재개했다.
- 2021 corpus·temp·marker는 생성되지 않았다. 현재 허용 작업은 283건 exact-ID
  회계와 보존 DB 기반 6-tier/export preflight이며, TextGrid·CSV·tier 수정 때문에
  2020 MFA 전체를 다시 계산하지 않는다.
- 완료 기록:
  `docs/decisions/RESULT_mfa_r3_alignment_database_2020_20260809.md`

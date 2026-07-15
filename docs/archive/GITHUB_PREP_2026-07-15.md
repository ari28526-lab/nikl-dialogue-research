# GitHub 셋업 준비 브리핑 (2026-07-15 14:00 전문가 세션용)

## 1. 프로젝트 한 줄 소개
한국어 일상대화 말뭉치(510만 발화)의 형태음운 변이·빈도 효과 연구.
파이프라인: 형태소 분석(바른) → 의미번호 → 빈도사전 → MFA 강제정렬 →
TextGrid → (예정) 운율 주석 → R 통계 분석.

## 2. 리포지토리로 만들고 싶은 것 (범위)
**이 폴더(`C:\Users\ari30\Dropbox\000_2026_summer_research`)가 리포 후보.**
- 포함: `scripts/`(python·R·powershell), `config/`(paths.json),
  `docs/`(방법론·결정 기록), `qmd/`, 루트 md 문서들(WORKFLOW·TODO·HANDOFF)
- 제외(대용량·저작권·비밀): 말뭉치 데이터 일체(외장하드 D:),
  `00_참고문헌/`(논문 PDF — 저작권), `01_frequency_data/`(KoFREN 외부 배포자료),
  `work/` 파일럿 산출물, API 키(원래 폴더 밖 보관 중)
- **private 리포 희망** (말뭉치 인용 예문·연구 미공개 내용 포함)

## 2.5 전문가에게 먼저 전달할 맥락 (읽어주기)
- 연구 개요는 `PROJECT_SUMMARY_2026-07.md` 참조 (1페이지)
- 작업이 세 곳에 흩어져 있음: **외장하드 D:**(데이터 수백 GB — git 불가),
  **Dropbox**(코드·연구노트 — 리포 후보), **Google Drive**(Colab 작업용)
- 원하는 것: "파일 저장소"가 아니라 **코드·문서에 시간축(이력)을 다는 것**
  + 여러 기계에서 같은 상태로 작업 + 논문 시점 코드 박제(태그)
- 데이터는 경로 중앙관리(config/paths.json)로 코드와 이미 분리돼 있음

## 3. 전문가에게 물어볼 것 (질문 목록)
0. **핵심 질문**: 제 3-저장소 구조(D: 데이터 / Dropbox 코드·문서 / G: Colab)
   에서 GitHub가 정확히 어느 조각을 맡는 게 맞나요? 흩어짐 자체를 더
   줄이는 권장 역할 분담이 있다면?
0-1. 데이터 버전 관리는 어떻게? (수백 GB — DVC 같은 도구까지 필요한가,
   아니면 인벤토리 문서·해시 기록으로 충분한가)
0-2. 논문 시점의 코드 상태 고정(release/tag) 실제 절차
1. Dropbox 폴더를 그대로 git 리포로 써도 되는가? (Dropbox 동기화와 git 충돌
   이슈 — .git을 Dropbox 밖에 두는 방법? worktree? 아니면 폴더 이전?)
2. 데이터 없이 코드·문서만 버전관리할 때 권장 구조 (경로 config 분리는
   이미 paths.json으로 해둠)
3. 큰 md 문서(방법론 기록)의 버전관리 관례 — 커밋 단위를 어떻게?
4. Colab 노트북과 GitHub 연동 워크플로 (노트북을 리포에? Colab에서 pull?)
5. 향후 논문 공개 시: private → 일부 public(코드만) 분리 전략
6. 백업 관점: GitHub + Dropbox + 외장하드 3중이면 충분한지
7. 커밋 메시지·브랜치 관례 최소 세트 (1인 연구자 기준)

## 4. 현재 자산 지도 (전문가 참고용)
```
Dropbox/000_2026_summer_research/   ← 리포 후보 (코드·문서)
  scripts/python/    파이프라인 스크립트 15개 (SCRIPTS_INDEX.md 참조)
  config/paths.json  경로 중앙 관리 (기계 간 이동 대비)
  docs/decisions/    방법론(METHODS)·표준(STANDARD)·계획(PLAN) 문서
  000_WORKFLOW_v2.md / 000_TODO_A단계.md / 000_HANDOFF*.md  길잡이 3종

D:\ (외장, 리포 제외)   00_RAW(원본) / 10_LAYERS(분석 레이어) /
                        20_AUDIO(음성·TextGrid) / 90_ARCHIVE
G:\ (Google Drive)      Colab 작업용
```

## 5. 민감정보 체크리스트 (세션 전 확인 완료 목표)
- [x] API 키: 폴더 밖(`Documents\Codex\_secrets`) + .gitignore에 패턴 차단
- [x] 대용량: wav/zip 등 .gitignore 차단
- [ ] 논문 PDF(`00_참고문헌/`) → .gitignore 추가 (2026-07-14 처리)
- [ ] KoFREN(`01_frequency_data/`) → .gitignore 추가 (재배포권 불확실)
- [ ] 문서 내 말뭉치 발화 인용 — private 리포면 문제 없음, public 전환 시 점검
- [ ] `.claude/`, `archive/` 제외

## 6. 세션에서 함께 하고 싶은 실작업 (우선순위)
1. 리포 초기화 + 첫 커밋 (Dropbox-git 이슈 해결 방식 포함)
2. .gitignore 최종 확정 + 히스토리에 비밀·대용량 안 들어갔는지 확인
3. 커밋·푸시 루틴 몸에 익히기 (제일 중요)
4. (시간 되면) GitHub에서 문서 보기 좋게 — README 정리

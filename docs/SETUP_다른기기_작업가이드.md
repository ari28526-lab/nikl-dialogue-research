# 다른 기기에서 연구 리포 작업하기 (1회 설정 + 일상 루틴)

> 어느 컴퓨터에서든 이 순서대로. 이 문서는 GitHub에서 바로 볼 수 있음:
> https://github.com/ari28526-lab/nikl-dialogue-research → `docs/SETUP_다른기기_작업가이드.md`

## 원칙: "진실은 GitHub 하나"
- 코드·문서의 정본은 GitHub 리포 (`ari28526-lab/nikl-dialogue-research`)
- 각 기기에는 복사본(clone)을 두고 **git으로만** 동기화
- ❌ 리포 폴더를 Dropbox/Google Drive 동기화 폴더 안에 두지 말 것 (git과 충돌)
- 데이터(D: 외장하드)는 본 PC 전용 — 다른 기기에서는 **문서·논의 작업만**

## A. 새 기기 1회 설정 (약 10분)

1. **Git 설치**: https://git-scm.com/download/win
   → 설치 옵션은 전부 기본값(다음다음)으로 OK
2. **리포 받기**: PowerShell 열고
   ```powershell
   cd ~\Documents
   git clone https://github.com/ari28526-lab/nikl-dialogue-research.git
   ```
3. **GitHub 로그인 창**이 뜨면 → `ari28526-lab` 계정으로 로그인 → Authorize
   (한 번만 하면 그 기기에 저장됨)
4. **커밋용 이름 설정** (1회):
   ```powershell
   git config --global user.name "ari28526-lab"
   git config --global user.email "ari28526@gmail.com"
   ```
5. **폴더 위치 확인**: `문서(Documents)\nikl-dialogue-research`에 생김.
   확인: 같은 창에서 `explorer nikl-dialogue-research` (탐색기로 열림)
   또는 `(Resolve-Path nikl-dialogue-research).Path` (전체 경로 출력)
6. **Claude 앱**에서 프로젝트 폴더로 그 경로 지정

## B. 일상 루틴 (매번, Claude에게 말로 시키면 됨)

| 시점 | Claude에게 |
|---|---|
| 작업 **시작** | "git pull 받아줘" |
| 작업 **끝** | "오늘 작업 커밋하고 푸시해줘" |

- 이 두 마디면 기기 간 동기화 끝. 명령어 외울 필요 없음.
- 직접 치고 싶으면: 시작 `git pull` / 끝 `git add -A && git commit -m "메모"` → `git push`

## C. 다른 기기 세션에서 지킬 규칙

세션 첫머리에 Claude에게 알려줄 것:
> "데이터(D:)는 이 컴퓨터에 없다. 문서 논의·outline 작업만.
> 결과물은 docs/ 아래에 쓰고, 끝나면 커밋+푸시."

- 연구 outline 등 새 문서: `docs/` 아래에 (예: `docs/OUTLINE_논문구상.md`)
- ㄴ삽입 환경 정의 논의: `phenomena/34_n_insertion/definition.md` 직접 수정
- 본 PC에서 D: 배치(MFA 등)가 도는 동안은 본 PC 쪽에서 D: 읽는 작업 금지
  (다른 기기는 D:가 없으므로 자동으로 안전)

## D. 본 PC로 돌아왔을 때
- Claude에게 "git pull 받아줘" 한 뒤 작업 시작 (다른 기기에서 푸시한 것 반영)

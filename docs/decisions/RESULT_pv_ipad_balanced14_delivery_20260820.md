# RESULT — PV-A iPad 균형 14개 원격 검토본 전달

- 기록일: 2026-08-20 KST
- 상태: `delivered_pending_ipad_smoke_test`
- 성격: 7현상 PV 탐색 기록용 보조 검토본
- 정식 실현 판정 ledger: 변경 없음

## 1. 결론

원격 iPad 환경에서 첫 표본을 바로 확인할 수 있도록, 통과한 PV 최종 산출물에서
각 현상의 2020년 1개와 2025년 1개를 선택한 단일 self-contained HTML을 만들고
Dropbox에 전달했다. 물리 표본과 primary review event는 각각 14개이며, 대상
음성 14개와 앞뒤 문맥 음성 14개를 원 WAV 바이트 그대로 HTML에 포함했다.

기존 PV 최종 산출물과 감사 파일은 읽기 전용으로 유지했다. 음성 재인코딩,
자동 실현 판정, 정식 ledger 기록, 기존 출력 덮어쓰기는 모두 수행하지 않았다.

## 2. 선택 범위

현상 순서는 `PT, NAN, NAL, NI, LLN, VH, HIA`이며, 각 현상에서 2020년과
2025년 primary event를 각각 하나씩 선택했다.

- 물리 package: 14
- primary review event: 14
- HTML `<audio>` 요소: 28
- HTML에 포함한 원 WAV payload: 8,657,296 bytes
- 외부 URL 또는 네트워크 음원: 0

각 행의 `pv_id`, `review_event_id`, `utt_id`, package 경로, 대상·문맥 WAV의
크기와 SHA-256은 아래 receipt에 전부 기록했다.

## 3. 산출물과 전달 위치

저장소 작업본:

- `work/pv_ipad_balanced14_20260820/PV_IPAD_BALANCED14_20260820.html`
  - 11,599,474 bytes
  - SHA-256: `c59bf73a012709524d03060e5155819d122690453463d635acd26a18a883e6e0`
- `work/pv_ipad_balanced14_20260820/PV_IPAD_BALANCED14_20260820_RECEIPT.json`
  - 9,251 bytes
  - SHA-256: `18f5bd24f6ffc30e81624f60bcfe7eecadfa22022a70b939a94ae633310ff435`
- `work/PV_IPAD_README_20260820.txt`

Dropbox 전달본:

- `C:\Users\ari30\Dropbox\pv_seven_phenomena_20260819\PV_IPAD_BALANCED14_20260820.html`
- `C:\Users\ari30\Dropbox\pv_seven_phenomena_20260819\PV_IPAD_BALANCED14_20260820_RECEIPT.json`
- `C:\Users\ari30\Dropbox\pv_seven_phenomena_20260819\PV_IPAD_README_20260820.txt`

Dropbox에는 각 목적지가 없음을 먼저 확인하고 `.partial` 파일에 복사한 뒤,
원본과 SHA-256이 같을 때만 최종 이름으로 원자 승격했다. 덮어쓰기는 없었다.

결속한 기존 PV 근거:

- source run manifest SHA-256:
  `acb8772e1f4ab8860ebc0631517f616eeb2b2e0f5eeb8e1d890abf462248ad51`
- source audit SHA-256:
  `628cb01692c28e14b9cfe00271fc3aa6e9c33267aafe34895c95c6f7d6896db2`
- source audit `passed`: `true`

## 4. iPad 사용 절차

Dropbox가 공식 모바일 미리보기 대상으로 HTML을 열거하지 않으므로 Dropbox
화면에서 직접 실행된다고 가정하지 않는다. Dropbox에서 HTML을 iPad의 파일
앱에 저장한 다음, 파일을 길게 눌러 `다음으로 열기(Open With)`로 HTML을 실행할
수 있는 앱을 선택한다.

1. 먼저 `PV_IPAD_README_20260820.txt`를 연다.
2. HTML을 `파일에 저장`한다.
3. 파일 앱에서 `다음으로 열기(Open With)`를 선택한다.
4. 각 표본 메모 뒤 `새 revision 저장`을 누른다.
5. 종료할 때 `JSONL 파일 저장`을 누른다.
6. 다운로드가 작동하지 않으면 `복사용 JSONL 펼치기`로 내용을 복사해 텍스트
   파일 또는 메모에 붙여 넣고 Dropbox에 별도 이름으로 저장한다.

브라우저·뷰어의 local storage만 최종 보존 수단으로 믿지 않는다. 이 HTML의
기록은 탐색용이고 정식 실현 판정 ledger와 분리된다.

공식 참고:

- Dropbox 지원 파일 형식: <https://help.dropbox.com/view-edit/viewable-file-types>
- iPad 파일 앱의 `Open With`: <https://support.apple.com/guide/ipad/files-basics-ipad4aaf0d7f/26/ipados/26>

## 5. 구현과 독립 검증

신규 재현 코드:

- `scripts/python/build_pv_ipad_balanced14.py`
- `scripts/python/audit_pv_ipad_balanced14.py`
- `tests/test_pv_ipad_html_runtime.js`

성공 검증:

| 로그 | 확인 내용 | SHA-256 |
|---|---|---|
| `logs/pv_preview_pilot_validation_20260819/26_ipad_rebuild_after_js_fix.log` | 두 Python 스크립트 `py_compile`, 최종 build | `e2263522a9b8ac6976ab6dc815f8b2e9caa3b204a2b0ed9b62fb9590d4ab88fa` |
| `logs/pv_preview_pilot_validation_20260819/27_ipad_independent_audit.log` | 14 form, 28 WAV SHA 일치, 외부 source 0, `passed=true` | `79ed062eeb527dcf9830a42073abe51de73fd3cf62d490a4a61c4c5599dda0ca` |
| `logs/pv_preview_pilot_validation_20260819/28_ipad_javascript_parse.log` | JavaScript parse 성공 | `21bcbe787ef303f86fbfc23b7a4eb0332d3404eee9657c21ad57324d9f8db344` |
| `logs/pv_preview_pilot_validation_20260819/29_ipad_save_copy_export_runtime.log` | revision 저장, 진행률 1/14, JSONL 복사 fallback·download trigger | `11539a3816fbe2995bf8c335a9115e9419cd97fd89b5ddd6cd2ac49397db2da4` |
| `logs/pv_preview_pilot_validation_20260819/30_ipad_dropbox_delivery_verification.log` | Dropbox 3파일의 byte·SHA 일치, `.partial` 0 | `d42ef920a2bbc22caa20d8005695bb4dbf4818387de48a72d9942bf253c7b99e` |

기존 출력이 있을 때 builder가 exit 1로 중단하고 HTML SHA가 바뀌지 않는 것도
확인했다.

## 6. 실패 보존과 한계

첫 build의 HTML은 Python 템플릿이 JavaScript 문자열 안의 `\n`을 실제 줄바꿈으로
방출해 parse 오류가 났다. 해당 실패본과 로그를 삭제하지 않고 다음 경로에
보존했다.

- `work/pv_ipad_balanced14_20260820_failed_20260820T152238`
- `logs/pv_preview_pilot_validation_20260819/25_ipad_javascript_parse.log`

템플릿에서 JavaScript용 역슬래시를 명시적으로 보존하도록 수정한 뒤 재생성했고,
위 26–29번 검증이 모두 통과했다.

Codex 앱 내장 브라우저로 실제 화면을 열어 보려 했으나 browser service의
trusted-path 설정 오류로 연결되지 않았다. 대신 독립 HTML 구조·WAV SHA 감사,
JavaScript parse, stub runtime의 저장·복사·export 동작까지 검증했다. 따라서
남은 확인은 연구자의 실제 iPad에서 HTML이 열리고 음성 재생 버튼이 작동하는지
1개 표본으로 확인하는 smoke test뿐이다.

## 7. 전달 선호 기록

`docs/environment/PROJECT_START_HERE.md`에 다음 원칙을 기록했다. 이후 Dropbox
전달 요청마다 현재 환경이 데스크톱인지 원격 iPad인지 먼저 확인하고, iPad일 때만
작은 self-contained 검토본과 JSONL 복사 fallback을 우선 검토한다. 연구자가
항상 iPad를 사용한다고 가정하지 않는다.

# 공통발음사전 r2 휴대용 검토 패키지

## 검토 파일

`01_MFA_R2_REVIEW_FILL_ME.xlsx`를 열어 `발음검토` 시트의 노란색
R·S·U열만 입력하고 같은 파일에 저장한다.

- R: 연구자 결정
- S: `approve_custom`일 때만 MFA phone 입력
- U: 대안·직접 입력·보류·거부의 판단 근거

확신할 수 없는 항목은 억지로 승인하지 않고 `hold`로 둔다.

## 음성 확인

다른 컴퓨터에서는 workbook에 기록된 D: 절대경로 링크가 열리지 않을
수 있다. 이때 `발화근거` 시트의 `year`, `session_id`, `utt_id`를 보고
패키지 내부에서 다음 파일을 연다.

```text
wav\<year>\<session_id>\<utt_id>.wav
```

`review_occurrences.csv`에도 검토 순서, 대상 어휘, 연도, 발화·세션·화자
ID, 발화문, 참고 발음과 WAV SHA-256이 기록되어 있다. 연결표는 31행,
고유 WAV는 29개이며, 같은 발화가 둘 이상의 대상 근거이면 WAV를 한
번만 보존한다.

## 완료 후

1. Excel을 완전히 종료해 Dropbox 동기화가 끝나게 한다.
2. `01_MFA_R2_REVIEW_FILL_ME.xlsx`의 Dropbox 경로를 Codex에 알린다.
3. `review_occurrences.csv`, `manifest.json`, `wav` 폴더는 수정하지
   않는다.

작성한 Excel만으로 D:의 원장·G2P shard·최종 사전이 바뀌지는 않는다.
Codex가 clean template과 비교 검증하고 연구자 결정이 유효한 경우에만
별도의 archive·transaction 절차로 적용한다.

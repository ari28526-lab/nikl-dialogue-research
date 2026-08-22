# PV-B 보조층 환경 점검 노트

작성일: 2026-08-19
상태: **문서·로컬 실물 위치 점검 완료 / KOINA·wav2vec2·음향 처리 미실행**

## 1. 점검 범위

`PLAN_stage2_seven_phenomena_PV_pilot_20260819.md` §3의 선행 조건만
확인했다. KOINA, Momel, wav2vec2, Praat/Parselmouth 음향 측정, 모델 다운로드,
대량 음성 처리는 실행하지 않았다.

## 2. 2026-07-15 KOINA 파일럿 실물 위치

프로젝트 내부 파일 목록에서 `prosody_utts.csv`와 결과 TextGrid 500개는
발견되지 않았다. 문서가 지시하는 다음 G: 후보 경로도 2026-08-19 현재 세션에서
`Test-Path=False`였고, `Get-PSDrive -Name G`도 값을 반환하지 않았다.

```text
G:\내 드라이브\DATA_2026\prosody_pilot\results\prosody_utts.csv
G:\내 드라이브\DATA_2026\prosody_pilot\results\tg
G:\My Drive\DATA_2026\prosody_pilot\results\prosody_utts.csv
G:\My Drive\DATA_2026\prosody_pilot\results\tg
G:\DATA_2026\prosody_pilot\results\prosody_utts.csv
G:\DATA_2026\prosody_pilot\results\tg
```

따라서 “500건 실행을 기록한 문서와 재사용 스크립트는 있음”과 “현재 접근 가능한
결과 실물이 검증됨”을 구분한다. 후자는 아직 충족되지 않았다. PV-B 실행 승인
전에 사용자가 Google Drive를 연결한 상태에서 CSV 행 수, TextGrid 파일 수,
각 산출물 SHA manifest를 새로 실측해야 한다.

## 3. 로컬에서 확인한 재현 자료

| 파일 | bytes | SHA-256 | 확인 내용 |
|---|---:|---|---|
| `scripts/colab/prosody_pilot_colab.py` | 8,371 | `48CDAE29749A3A608B2E227010BF08D96DB0002237CB749BF857549508CC3EF2` | 500발화, `PAUSE_IP=0.15`, `PAUSE_AP=0.05`, `RISE_ST=2.0`, `TONE_ST=1.5`; Momel 실패 시 Parselmouth-only fallback |
| `scripts/colab/COLAB_실행안내.md` | 1,468 | `C5520903AAFAC02CD7BC41C2D13ADFB72C10E44863CE13806F4972D21EB17E23` | Drive 입력·결과 예정 경로와 3-cell 실행 절차 |
| `docs/decisions/PLAN_KOINA_intonation_IP_AP.md` | 4,514 | `ACEB49EC4F965B37FE9D2D7CE91BE223FC9342E573507611E87A651FBA6F546F` | 2026-07-15 파일럿 완료 기록과 규칙 v0 |
| `docs/decisions/NOTE_wav2vec2_phone_candidate_layer_20260727.md` | 8,153 | `FFE85541FD92E2FE0721150B05F90165D0903472B28E001039CF8AE3053C1DA0` | 후보 모델·라이선스·별도 보조층 원칙 |

`prosody_pilot_colab.py`는 Linux의
`/content/KOINA/src/lib/momel/momel_linux`를 호출한다. 이 점은 Momel이 현재
Windows wrapper의 실행 대상이 아니며 Colab/Linux 환경이 필요하다는 기존
결정과 일치한다.

## 4. 재현성 위험

현재 `COLAB_실행안내.md`의 설치 셀은 다음처럼 KOINA 저장소의 revision/tag를
고정하지 않은 clone을 사용한다.

```text
git clone https://github.com/YugwonWon/KOINA.git
```

그래서 문서에 적힌 “KOINA v1.1.0”과 2026-07-15 실제 실행 checkout이 같았는지
로컬 자료만으로 증명할 수 없다. 또한 스크립트는 KOINA import가 실패해도
Parselmouth-only 결과를 만들도록 되어 있어, `prosody_utts.csv` 파일명만으로
Momel 열이 실제 생성됐다고 판정할 수 없다.

PV-B를 실행하는 별도 승인 단계에서는 다음을 먼저 고정해야 한다.

1. KOINA tag/commit과 소스 SHA manifest
2. Python·Parselmouth·textgrid·MFA 버전
3. `HAVE_KOINA`, Momel 성공/실패, 임계값 version을 결과 행 또는 run manifest에 기록
4. 원 PV-A `pv_id`, `utt_id`, 원 WAV/TextGrid SHA, 원 좌표와 파생 좌표 연결
5. 실패·값 없음·낮은 신뢰도와 실제 숫자 0의 구분

이 항목은 현재 §5 구현 범위를 넓히지 않으며, PV-B 실행 승인 전 계약 보완 목록이다.

## 5. wav2vec2 점검 결론

기존 노트가 지정한 후보는
`slplab/wav2vec2-xls-r-300m_phone-mfa_korean`, Apache-2.0, 약 1.26GB이며,
낭독체 학습·CTC 시간 후보·MFA 계열 phone inventory라는 한계가 이미 기록돼
있다. 로컬 모델 존재 여부, inference 환경, 실제 처리율은 이번에 확인하거나
실행하지 않았다.

PV-B에서도 출력은 `w2v_phone_candidates_json`, 모델 ID/revision/SHA,
confidence·실패 상태를 가진 **후보 보조층**이어야 한다. MFA phone, canonical
TextGrid, 사람의 실현 판정을 수정할 수 없다.

## 6. PV-B 시작 가능 여부

현재 판정은 **보류**다. 이유는 2026-07-15 결과 실물과 실행 revision을 확인하지
못했기 때문이다. 이는 PV-A wrapper 실행이나 청취 준비를 막지는 않는다.
PV-B는 결과 실물 확인과 별도 사용자 승인 뒤, 현상별 5–10건의 작은 부분집합에서만
시작한다.

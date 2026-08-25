# Stage2 PV-B KOINA·wav2vec2 보조층 최소 골격

작성일: 2026-08-25 KST
상태: 코드 골격 구현, 실제 모델·음성 실행 전

## 목적

문헌 검토가 오래 걸리는 동안에도 나중에 버리지 않을 기술 골격을 준비한다.
현상별 query·표본·실현 범주를 지금 확정하지 않고, 연구자가 승인한 작은 PV-B
manifest를 입력으로 받는 보조 runner만 만든다.

## 공통 경계

- 입력은 `stage2_pv_b_input.v1` JSONL이며 `pv_id`, `phenomenon_code`,
  `occurrence_id`, `utt_id`, WAV 경로·SHA, KOINA용 text·sex를 가진다.
- 현상당 최대 10건, 전체 최대 70건이다. 기본 실행이 아니라 preflight다.
- 기존 출력과 `.partial`이 있으면 거부한다.
- 성공 때만 `.partial`을 최종 이름으로 승격한다. 실패 산출물은 진단 근거로
  보존한다.
- WAV·canonical TextGrid·MFA·정식 realization ledger를 수정하지 않는다.
- 모든 출력은 `machine_candidate_not_realization`이다.

## KOINA

공식 저장소의 v1.1.0 선언과 Linux·Python 3.10·MFA 3.2.1 실행 안내를 기준으로
wrapper를 만들었다. 실제 실행에는 로컬 KOINA checkout과 full Git commit을
명시해야 하며 checkout HEAD와 `v1.1.0` tag가 그 commit과 다르면 중단한다. 기존 파일럿의 조용한
Parselmouth-only fallback은 이 wrapper에서 허용하지 않는다.

`scripts/python/run_pv_b_koina.py`는 입력 WAV를 복사하지 않고 새 `.partial`
namespace에 symlink로 연결한 뒤 upstream `transcriber.py`를 `n_jobs=1`로
호출한다. Windows에서는 manifest preflight만 가능하고 실제 실행은 Linux에서만
허용한다.

## wav2vec2

모델은 `slplab/wav2vec2-xls-r-300m_phone-mfa_korean`, revision
`e26ff9dfb62169acf445d0060ef56863c018b20e`, Apache-2.0으로 고정했다.
`trust_remote_code=False`이며 다운로드와 pickle 기반 `pytorch_model.bin` 로드는
각각 명시적 flag가 있어야 한다.

`scripts/python/run_pv_b_wav2vec2.py`는 CTC frame argmax를 반복·blank 규칙으로
축약해 phone 후보와 근사 시간·frame probability를 별도 JSONL로 쓴다. sample
rate가 모델과 다르면 조용히 resample하지 않고 중단한다.

## 현재 가능한 안전 실행

두 runner 모두 `--execute`가 없으면 manifest·WAV SHA·표본 수·기존 출력 여부만
검사하고 모델이나 KOINA를 실행하지 않는다.

```powershell
$pipelinePython = (Get-Content ".\config\paths.json" -Raw | ConvertFrom-Json).pipeline_python

& $pipelinePython `
  ".\scripts\python\run_pv_b_koina.py" `
  --input-manifest "승인된_PV-B_manifest.jsonl" `
  --output-dir ".\work\pv_b_koina_smoke"

& $pipelinePython `
  ".\scripts\python\run_pv_b_wav2vec2.py" `
  --input-manifest "승인된_PV-B_manifest.jsonl" `
  --output-dir ".\work\pv_b_wav2vec2_smoke"
```

실제 실행 명령은 승인된 manifest와 새 output namespace가 준비된 뒤 만든다.
KOINA에는 검증된 full commit이, wav2vec2에는 pickle weight 승인과 필요시 다운로드
승인이 별도로 필요하다.

## 아직 하지 않은 것

- 실제 PV-B 표본 manifest 선정·승인
- KOINA checkout/tag commit 실측과 라이선스 원문 재확인
- 모델 다운로드 또는 추론
- KOINA TextGrid에서 stage2 prosody sidecar를 추출하는 parser
- wav2vec2 후보와 MFA·사람 판정의 정확도 비교
- 정본 schema·query·realization ledger 반영

## 다음 Gate

1. 문헌 작업과 독립적으로 1건짜리 승인 없는 synthetic WAV preflight를 유지한다.
2. 연구자가 PV-A에서 현상별 1건 smoke manifest를 승인한다.
3. KOINA full commit과 실행 환경, wav2vec2 전용 환경·모델 cache를 검증한다.
4. 실제 음성 1건 실행 결과를 독립 감사하고 멈춘다.
5. 연구자가 결과와 비용을 본 뒤 5–10건 확대 여부를 결정한다.

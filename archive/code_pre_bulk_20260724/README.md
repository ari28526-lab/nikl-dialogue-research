# 대량 MFA·CSV 작업 전 코드 아카이브

생성일: 2026-07-24  
기준 브랜치: `main`  
기준 커밋: `e1075ee`  
목적: 대량 MFA G2P 재정렬 및 검색 마스터 CSV 생성 코드를 개선하기 전의
정확한 바이트 상태를 보존한다.

## 범위

이 폴더에는 이번 안전성 개선에서 직접 수정할 가능성이 있는 설정·실행기·핵심
Python 코드만 복사했다. 연구 데이터, 비밀정보, 실행 산출물은 포함하지 않았다.

```text
config/paths.json
scripts/preflight_eojeol_realign.ps1
scripts/run_eojeol_realign.ps1
scripts/python/paths.py
scripts/python/realign_eojeol_build_corpus.py
scripts/python/realign_eojeol_merge_output.py
scripts/python/preflight_search_master.py
scripts/python/build_search_master.py
scripts/python/predict_pron.py
```

`MANIFEST.sha256`은 각 파일의 SHA256과 크기를 기록한다. 복원할 때는 현재
파일을 먼저 별도 보존한 뒤 이 폴더의 상대경로를 프로젝트 루트에 대응시킨다.
PowerShell 파일은 원본의 UTF-8 BOM을 포함한 바이트를 그대로 복사했다.

## 연구적 의미

대량 처리 전 코드를 보존하는 이유는 결과 차이가 자료의 변화인지 코드 변경의
효과인지 구분하기 위해서다. 이후 파일럿과 본 실행은 Git 커밋과 run manifest를
함께 기록하여 이 기준선과 직접 비교한다.

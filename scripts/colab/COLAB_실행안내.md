# 운율 파일럿 Colab 실행 안내 (3개 셀 복사-붙여넣기)

준비물 (이미 G:에 올라가 있음, 드라이브 동기화 완료 확인):
- `내 드라이브/DATA_2026/prosody_pilot/sample500.zip`
- `내 드라이브/DATA_2026/prosody_pilot/prosody_pilot_colab.py`

colab.research.google.com → 새 노트북 → 아래 셀을 순서대로.

## 셀 1 — 설치 + 드라이브 연결 (2~3분)
```python
!git clone -q https://github.com/YugwonWon/KOINA.git
!pip -q install praat-parselmouth textgrid
from google.colab import drive
drive.mount('/content/drive')
```

## 셀 2 — 표본 압축 해제
```python
!unzip -q "/content/drive/MyDrive/DATA_2026/prosody_pilot/sample500.zip" -d /content/sample500
!ls /content/sample500 | head -5
```

## 셀 3 — 실행 (500발화, 약 10~20분)
```python
%run "/content/drive/MyDrive/DATA_2026/prosody_pilot/prosody_pilot_colab.py"
```

## 결과 확인
- `내 드라이브/DATA_2026/prosody_pilot/results/prosody_utts.csv`
  (발화별 IP/AP 경계·경계성조·F0 통계·휴지·말속도·Momel 목표점)
- `results/tg/*.TextGrid` — prosody tier가 추가된 TextGrid
  (다운로드해서 Praat에서 소리와 함께 열어 검토)

## 주의
- 셀 1에서 KOINA clone이 실패해도 셀 3은 돌아감 (Momel 열만 비게 됨)
- 완료 후 결과는 드라이브 동기화로 로컬 G:에 자동 내려옴
- 규칙 v0 임계값(휴지 0.15s, F0 리셋 2st 등)은 청취 검증 후 보정 예정

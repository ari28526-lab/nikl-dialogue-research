"""발화 ID → 전 레이어 경로 조회 (B단계 현상별 검색·청취 검증용, 2026-07-19).

좌표계(데이터 배치 규약, docs/DATA_LAYOUT.md):
  발화 ID = {세션ID}.{n}.{n}.{발화번호}  (예: SDRW2000000521.1.1.175)
  세션ID  = 발화 ID의 첫 '.' 앞         (예: SDRW2000000521)
  연도    = 세션ID 5-6번째 글자(2자리)  (예: SDRW'20'.. → 2020, SARW'25'.. → 2025)
  파일 위치 = {레이어 루트}\\{연도}\\{세션}\\{발화ID}.{확장자}   ← 6개년 동일 depth

용법:
  코드에서:  from locate_utt import locate ; locate("SDRW2000000521.1.1.175")
  콘솔에서:  python locate_utt.py SDRW2000000521.1.1.175 [발화ID ...]
             → 레이어별 경로와 존재 여부([O]/[X]) 출력. 폴더 열 필요 없음.
비고: 세션 재구성(7/20) 전의 평면 연도도 지원(세션 경로 없으면 평면 폴백).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P                                        # noqa: E402
from realign_eojeol_build_corpus import YEAR_DIRS          # noqa: E402  (바른 CSV 연도폴더명)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_utt(utt_id: str) -> tuple:
    """발화 ID → (연도, 세션). 형식이 어긋나면 ValueError."""
    session = utt_id.split(".")[0]
    if len(session) < 6 or not session[4:6].isdigit():
        raise ValueError(f"세션 ID에서 연도를 못 읽음: {utt_id}")
    year = f"20{session[4:6]}"
    if year not in YEAR_DIRS:
        raise ValueError(f"연도 범위 밖({year}): {utt_id}")
    return year, session


def _with_flat_fallback(year_root: Path, session: str, fname: str) -> Path:
    """세션 경로 우선, 없으면 평면(재구성 전) 경로. 둘 다 없으면 세션 경로 반환."""
    p = year_root / session / fname
    if p.exists():
        return p
    flat = year_root / fname
    return flat if flat.exists() else p


def locate(utt_id: str) -> dict:
    """발화 ID → 레이어별 Path. 반환 키:
    wav / lab / textgrid_eojeol(4-tier 주 레이어) / textgrid_merged(형태소) /
    bareun_csv(세션 전사·형태소 CSV) / quarantine(격리됐다면 그 위치)"""
    year, session = parse_utt(utt_id)
    wav_root = P("wav") / "individual" / year
    out = {
        "wav": _with_flat_fallback(wav_root, session, f"{utt_id}.wav"),
        "lab": _with_flat_fallback(wav_root, session, f"{utt_id}.lab"),
        "textgrid_eojeol": P("textgrid_eojeol") / year / session / f"{utt_id}.TextGrid",
        "textgrid_merged": P("textgrid_merged") / year / session / f"{utt_id}.TextGrid",
        "bareun_csv": P("layers") / "01_bareun_raw" / YEAR_DIRS[year] / f"{session}.csv",
    }
    q = Path(r"D:\mfa_eojeol\quarantine") / year / f"{utt_id}.wav"
    if q.exists():
        out["quarantine"] = q
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for utt in sys.argv[1:]:
        print(f"\n■ {utt}")
        try:
            paths = locate(utt)
        except ValueError as e:
            print(f"  !! {e}")
            continue
        for layer, p in paths.items():
            mark = "O" if p.exists() else "X"
            print(f"  [{mark}] {layer:16s} {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

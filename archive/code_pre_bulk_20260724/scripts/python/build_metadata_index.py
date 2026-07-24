"""A4: 파일 메타데이터 인덱스 — 원본 JSON에서 사용역·주제·화자 추출.

출력: D:/10_LAYERS/04_metadata_index/file_meta.csv
  문서(document) 단위 1행: file_id, doc_id, year, category(사용역),
  topic, date, relation, n_speakers, speaker_ids
  ※ utt_id가 doc_id로 시작하므로 발화와 바로 조인 가능.
층화 빈도(A5)와 B단계 검색에서 사용역·주제 변수로 사용.

실행: python build_metadata_index.py   (읽기 전용, 약 5-10분)
"""
import csv
import json
import re
import sys
from pathlib import Path

SRC = Path(r"D:\00_RAW\dialogue_json")
OUT_DIR = Path(r"D:\10_LAYERS\04_metadata_index")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


GOLD_INDEX = Path(r"D:\10_LAYERS\06_multilayer_gold\gold_index.csv")


def norm_category(cat: str) -> str:
    """사용역 표기 변이(마디 내부 공백) 정규화. 원본은 category에 보존.
    '구어 > 사적 대화 > 일상 대화' -> '구어 > 사적대화 > 일상대화'"""
    cat = (cat or "").strip()
    if not cat:
        return ""
    parts = [p.strip().replace(" ", "") for p in cat.split(">")]
    return " > ".join(p for p in parts if p)


def discourse_mode(cat_norm: str) -> str:
    """정규화 사용역 leaf가 '독백'이면 독백, 아니면 대화(빈값→미상).
    독백/대화는 순서교대 유무 = 형태음운 변이에 중요한 담화 유형 구분."""
    if not cat_norm:
        return "미상"
    return "독백" if cat_norm.split(">")[-1].strip() == "독백" else "대화"


def load_gold_fids() -> set:
    """다층위 2025 gold에 포함된 file_id 집합 (없으면 빈 집합).
    in_ml2025_gold = 우리 코퍼스 중 공식 gold로 검증된 부분 표시."""
    if not GOLD_INDEX.exists():
        print("  [참고] gold_index 없음 → in_ml2025_gold 전부 False")
        return set()
    fids = set()
    with open(GOLD_INDEX, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            fids.add(r["utt_id"].split(".")[0])
    return fids


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "file_meta.csv"
    gold_fids = load_gold_fids()
    n_files = n_docs = 0
    with open(out, "w", newline="", encoding="utf-8-sig") as fo:
        w = csv.writer(fo)
        w.writerow(["file_id", "doc_id", "year", "category", "category_norm",
                    "discourse_mode", "topic", "date", "relation",
                    "n_speakers", "speaker_ids", "in_ml2025_gold"])
        for ydir in sorted(SRC.iterdir()):
            if not ydir.is_dir():
                continue
            m = re.search(r"(20\d\d)", ydir.name)
            year = m.group(1) if m else ""
            files = sorted(ydir.rglob("*.json"))
            print(f"[{ydir.name}] {len(files)}개...", flush=True)
            for jf in files:
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"  !! {jf.name}: {e}")
                    continue
                n_files += 1
                file_id = data.get("id", jf.stem)
                top_meta = data.get("metadata", {}) or {}
                category = (top_meta.get("category") or "").strip()
                cat_norm = norm_category(category)
                for doc in data.get("document", []):
                    dm = doc.get("metadata", {}) or {}
                    spk = dm.get("speaker") or []
                    setting = dm.get("setting", {}) or {}
                    w.writerow([
                        file_id, doc.get("id", ""), year,
                        category, cat_norm, discourse_mode(cat_norm),
                        (dm.get("topic") or "").strip(),
                        (dm.get("date") or "").strip(),
                        (setting.get("relation") or "").strip(),
                        len(spk),
                        "|".join(s.get("id", "") for s in spk),
                        "True" if file_id in gold_fids else "False",
                    ])
                    n_docs += 1
    print(f"완료: 파일 {n_files:,}개 → 문서 {n_docs:,}행")
    print(f"출력: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

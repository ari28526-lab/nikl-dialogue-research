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


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "file_meta.csv"
    n_files = n_docs = 0
    with open(out, "w", newline="", encoding="utf-8-sig") as fo:
        w = csv.writer(fo)
        w.writerow(["file_id", "doc_id", "year", "category", "topic",
                    "date", "relation", "n_speakers", "speaker_ids"])
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
                top_meta = data.get("metadata", {}) or {}
                category = (top_meta.get("category") or "").strip()
                for doc in data.get("document", []):
                    dm = doc.get("metadata", {}) or {}
                    spk = dm.get("speaker") or []
                    setting = dm.get("setting", {}) or {}
                    w.writerow([
                        data.get("id", jf.stem), doc.get("id", ""), year,
                        category, (dm.get("topic") or "").strip(),
                        (dm.get("date") or "").strip(),
                        (setting.get("relation") or "").strip(),
                        len(spk),
                        "|".join(s.get("id", "") for s in spk),
                    ])
                    n_docs += 1
    print(f"완료: 파일 {n_files:,}개 → 문서 {n_docs:,}행")
    print(f"출력: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

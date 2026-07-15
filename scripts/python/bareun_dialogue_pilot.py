"""NIKL 일상대화 2025 파일럿: 바른 클라우드 API 형태소 분석.

사용 (bareun-smoke venv의 python으로 실행):
  python bareun_dialogue_pilot.py [--files 2] [--max-utt 120]

출력: work/bareun/pilot/
  pilot_utterances.csv  발화 단위 (utt_id, speaker_id, form, tagged)
  pilot_morphs_long.csv 형태소 단위 long format
  pilot_summary.txt     요약 + 전체 코퍼스 소요시간 추정
API 키는 코드/출력에 절대 노출하지 않는다.
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

YEAR_DIR = Path(r"D:\00_RAW\dialogue_json\NIKL_DIALOGUE_2025_v1.0")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "work" / "bareun" / "pilot"
SECRET_DIR = Path.home() / "Documents" / "Codex" / "_secrets" / "bareun"
SECRET_FILES = [SECRET_DIR / "bareun.env", SECRET_DIR / "bareun_api.txt"]


def load_api_key() -> str:
    key = os.environ.get("BAREUN_API_KEY", "").strip()
    if key:
        return key
    for path in SECRET_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == "BAREUN_API_KEY" and v.strip():
                    return v.strip().strip('"').strip("'")
            elif line.lower().startswith("koba-"):
                return line
    sys.exit("API 키를 찾지 못했습니다. bareun.env 또는 bareun_api.txt 확인 필요.")


def iter_utterances(json_path: Path):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    for doc in data.get("document", []):
        for utt in doc.get("utterance", []):
            form = (utt.get("form") or "").strip()
            if form:
                yield utt["id"], utt.get("speaker_id", ""), form


def tag_name(morph) -> str:
    """protobuf enum -> 'NNG' 같은 문자열 태그."""
    tag = morph.tag
    if isinstance(tag, str):
        return tag
    try:
        return type(morph).Tag.Name(tag)
    except Exception:
        return str(tag)


def parse_msg_sentences(res):
    """tags()/tag() 결과 msg에서 문장별 (morph, tag) 목록 추출."""
    out = []
    for sent in res.msg().sentences:
        morphs = []
        for token in sent.tokens:
            for m in token.morphemes:
                morphs.append((m.text.content, tag_name(m)))
        out.append(morphs)
    return out


def tag_batch(tagger, sentences):
    """배치 호출. 실패하면 단건 호출로 폴백."""
    try:
        res = tagger.tags(sentences)
        parsed = parse_msg_sentences(res)
        if len(parsed) == len(sentences):
            return parsed, "batch"
    except Exception as e:
        print(f"  [batch 실패 -> 단건 폴백] {type(e).__name__}: {e}", file=sys.stderr)
    out = []
    for s in sentences:
        if not s:
            out.append([])
            continue
        # 발화 하나가 여러 문장으로 나뉘어도 형태소를 하나로 합침
        sents = parse_msg_sentences(tagger.tag(s))
        out.append([m for sent in sents for m in sent])
    return out, "single"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=2)
    ap.add_argument("--max-utt", type=int, default=120)
    ap.add_argument("--chunk", type=int, default=10)
    args = ap.parse_args()

    from bareunpy import Tagger
    tagger = Tagger(load_api_key(), "api.bareun.ai", 443)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(YEAR_DIR.glob("*.json"))[: args.files]
    utts = []
    for jf in json_files:
        for uid, spk, form in iter_utterances(jf):
            utts.append((jf.stem, uid, spk, form))
    utts = utts[: args.max_utt]
    print(f"파일 {len(json_files)}개, 발화 {len(utts)}건 분석 시작")

    results = []  # (file_id, utt_id, spk, form, [(morph, tag)...])
    modes = Counter()
    t0 = time.time()
    for i in range(0, len(utts), args.chunk):
        chunk = utts[i : i + args.chunk]
        parsed, mode = tag_batch(tagger, [u[3] for u in chunk])
        modes[mode] += 1
        for u, morphs in zip(chunk, parsed):
            results.append((*u, morphs))
        print(f"  {min(i+args.chunk, len(utts))}/{len(utts)} ({mode})")
    elapsed = time.time() - t0

    with open(OUT_DIR / "pilot_utterances.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file_id", "utt_id", "speaker_id", "form", "tagged", "n_morphs"])
        for fid, uid, spk, form, morphs in results:
            tagged = " ".join(f"{m}/{t}" for m, t in morphs)
            w.writerow([fid, uid, spk, form, tagged, len(morphs)])

    freq = Counter()
    with open(OUT_DIR / "pilot_morphs_long.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "idx", "morph", "tag"])
        for fid, uid, spk, form, morphs in results:
            for idx, (m, t) in enumerate(morphs, 1):
                w.writerow([uid, idx, m, t])
                freq[(m, t)] += 1

    per_utt = elapsed / max(len(utts), 1)
    lines = [
        f"발화 수: {len(utts)}",
        f"총 소요: {elapsed:.1f}초, 발화당 {per_utt:.3f}초",
        f"호출 모드: {dict(modes)}",
        f"형태소 토큰 수: {sum(freq.values())}, 고유 (형태소,태그): {len(freq)}",
        f"457만 발화 예상(현재 속도): {457e4 * per_utt / 3600:.1f}시간",
        "", "상위 30 (형태소/태그):",
    ]
    for (m, t), c in freq.most_common(30):
        lines.append(f"  {m}/{t}\t{c}")
    (OUT_DIR / "pilot_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:5]))
    print(f"완료 → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

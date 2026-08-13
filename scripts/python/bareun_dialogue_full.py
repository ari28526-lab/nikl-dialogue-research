"""NIKL 일상대화 2020-2025 전체: 바른 클라우드 API 형태소 재분석 (1차 레이어).

- 출력은 순수 바른 분석만 담는다 (의미번호 없음). 의미번호는 별도 스크립트
  (assign_sense_layer.py)가 2차 레이어로 생성한다.
- 파일 단위 체크포인트: 완료된 JSON은 재실행 시 자동 건너뜀 (중단 후 재개 가능).
- 실행 예 (bareun-smoke venv python 사용):
    python bareun_dialogue_full.py                # 전체
    python bareun_dialogue_full.py --year 2025    # 특정 연도만
    python bareun_dialogue_full.py --limit-files 5  # 테스트

출력 구조:
  D:/10_LAYERS/
    01_bareun_raw/{연도폴더}/{파일ID}.csv   발화별: utt_id, speaker_id, form, tagged, n_morphs
    01_bareun_raw/{연도폴더}/_speakers.csv  화자 메타데이터 (성별/연령 등)
    logs/run_log.txt, failed.csv

tagged 형식: 어절(token) 사이는 공백, 어절 내 형태소는 '+' 구분.
  예: 요즘/NNG+처럼/JKB 추운/... -> "요즘/NNG+처럼/JKB 춥/VA+ㄴ/ETM ..."
"""
import argparse
import csv
import json
import os
import platform
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\00_RAW\dialogue_json")
OUT_ROOT = Path(r"D:\10_LAYERS")
RAW_DIR = OUT_ROOT / "01_bareun_raw"
LOG_DIR = OUT_ROOT / "logs"
SECRET_DIR = Path.home() / "Documents" / "Codex" / "_secrets" / "bareun"
SECRET_FILES = [SECRET_DIR / "bareun.env", SECRET_DIR / "bareun_api.txt"]
SPEAKER_FIELDS = ["id", "age", "sex", "occupation", "birthplace",
                  "principal_residence", "current_residence", "education"]
POS_TERMINATOR_RE = re.compile(r"/[A-Z][A-Z0-9_-]*(?=\+| |$)")


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
    sys.exit("API 키를 찾지 못했습니다.")


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "run_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def tag_name(morph) -> str:
    tag = morph.tag
    if isinstance(tag, str):
        return tag
    try:
        return type(morph).Tag.Name(tag)
    except Exception:
        return str(tag)


def parse_sentences_tokenwise(res):
    """msg().sentences -> 문장별 tagged 문자열 (어절은 공백, 형태소는 + 구분)."""
    out = []
    for sent in res.msg().sentences:
        tokens = []
        for token in sent.tokens:
            tokens.append("+".join(f"{m.text.content}/{tag_name(m)}"
                                   for m in token.morphemes))
        out.append(" ".join(tokens))
    return out


def count_morphs(tagged: str) -> int:
    """직렬화 구분자가 아니라 POS 종결점으로 형태소 수를 센다.

    Bareun surface 자체에 ``+``가 포함될 수 있다(예: ``.+/SW``). 모든 plus를
    경계로 세면 그 발화의 ``n_morphs``가 과대계상된다.
    """
    if not tagged:
        return 0
    return len(POS_TERMINATOR_RE.findall(tagged))


def tag_chunk(tagger, texts, max_retry=3):
    """배치 분석. 1:1 대응 실패/오류 시 단건 폴백. 반환: tagged 문자열 리스트."""
    for attempt in range(max_retry):
        try:
            parsed = parse_sentences_tokenwise(tagger.tags(texts))
            if len(parsed) == len(texts):
                return parsed
            break  # 문장 수 불일치 -> 단건 폴백
        except Exception as e:
            wait = 2 * (attempt + 1)
            log(f"  batch 오류({type(e).__name__}), {wait}s 후 재시도 {attempt+1}/{max_retry}")
            time.sleep(wait)
    out = []
    for t in texts:
        tagged = ""
        for attempt in range(max_retry):
            try:
                tagged = " ".join(parse_sentences_tokenwise(tagger.tag(t)))
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
        out.append(tagged)  # 실패 시 빈 문자열 (failed.csv에 기록됨)
    return out


def wait_for_network(tagger):
    """API 연결이 살아날 때까지 60초 간격으로 대기 (인터넷 단절 대비)."""
    while True:
        try:
            tagger.tag("연결 확인")
            log("  연결 회복 확인 — 재개")
            return
        except Exception:
            log("  네트워크/서버 연결 안 됨 — 60초 후 재확인 (Ctrl+C로 중단 가능)")
            time.sleep(60)


def iter_utterances(data):
    for doc in data.get("document", []):
        for utt in doc.get("utterance", []):
            form = (utt.get("form") or "").strip()
            if form:
                yield utt.get("id", ""), utt.get("speaker_id", ""), form


def collect_speakers(data, store: dict):
    for doc in data.get("document", []):
        for spk in (doc.get("metadata", {}) or {}).get("speaker", []) or []:
            sid = spk.get("id", "")
            if sid and sid not in store:
                store[sid] = {k: spk.get(k, "") for k in SPEAKER_FIELDS}


def process_file(tagger, json_path: Path, out_csv: Path, chunk: int, failed_w):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    utts = list(iter_utterances(data))
    tmp = out_csv.with_suffix(".tmp")
    n_fail = 0
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["utt_id", "speaker_id", "form", "tagged", "n_morphs"])
        for i in range(0, len(utts), chunk):
            part = utts[i:i + chunk]
            tags = tag_chunk(tagger, [u[2] for u in part])
            # 청크 전체 실패 = 네트워크 단절로 간주 → 빈 값 저장 대신 대기 후 재시도
            guard = 0
            while part and all(not t for t in tags) and guard < 10:
                log("  청크 전체 실패 → 네트워크 대기 모드")
                wait_for_network(tagger)
                tags = tag_chunk(tagger, [u[2] for u in part])
                guard += 1
            for (uid, spk, form), tagged in zip(part, tags):
                if not tagged:
                    n_fail += 1
                    failed_w.writerow([json_path.stem, uid, form])
                w.writerow([uid, spk, form, tagged, count_morphs(tagged)])
    os.replace(tmp, out_csv)
    return data, len(utts), n_fail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", help="예: 2025 (해당 연도 폴더만)")
    ap.add_argument("--chunk", type=int, default=40, help="배치당 발화 수")
    ap.add_argument("--limit-files", type=int, default=0, help="테스트용 파일 수 제한")
    args = ap.parse_args()

    from bareunpy import Tagger
    import bareunpy
    tagger = Tagger(load_api_key(), "api.bareun.ai", 443)

    log(f"=== 실행 시작: python {platform.python_version()}, "
        f"bareunpy {getattr(bareunpy, '__version__', '?')}, chunk={args.chunk}, "
        f"year={args.year or 'ALL'} ===")

    year_dirs = sorted(d for d in ROOT.iterdir() if d.is_dir())
    if args.year:
        year_dirs = [d for d in year_dirs if args.year in d.name]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    failed_f = open(LOG_DIR / "failed.csv", "a", newline="", encoding="utf-8")
    failed_w = csv.writer(failed_f)
    grand_utts = grand_files = grand_skip = 0
    t0 = time.time()

    for ydir in year_dirs:
        out_dir = RAW_DIR / ydir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        speakers: dict = {}
        spk_csv = out_dir / "_speakers.csv"
        if spk_csv.exists():  # 재개 시 기존 화자 정보 로드
            with open(spk_csv, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    speakers[row["id"]] = row
        json_files = sorted(ydir.rglob("*.json"))
        if args.limit_files:
            json_files = json_files[: args.limit_files]
        log(f"[{ydir.name}] JSON {len(json_files)}개")
        done = 0
        for jf in json_files:
            out_csv = out_dir / f"{jf.stem}.csv"
            if out_csv.exists():
                grand_skip += 1
                continue
            t1 = time.time()
            try:
                data, n_utt, n_fail = process_file(tagger, jf, out_csv,
                                                   args.chunk, failed_w)
            except Exception as e:
                log(f"  !! {jf.name} 파일 단위 실패: {type(e).__name__}: {e}")
                failed_w.writerow([jf.stem, "<FILE>", str(e)])
                continue
            collect_speakers(data, speakers)
            done += 1
            grand_files += 1
            grand_utts += n_utt

            if n_fail:
                log(f"  {jf.stem}: 발화 {n_utt}, 실패 {n_fail}, {time.time()-t1:.1f}s")
            if done % 20 == 0:
                elapsed = time.time() - t0
                rate = grand_utts / elapsed if elapsed else 0
                log(f"  진행: 이번 세션 {grand_files}파일/{grand_utts}발화, "
                    f"{rate:.0f}발화/초, 건너뜀 {grand_skip}")
                _write_speakers(spk_csv, speakers)
                failed_f.flush()
        _write_speakers(spk_csv, speakers)
        log(f"[{ydir.name}] 완료 (이번 세션 처리 {done}, 건너뜀 포함 전체 확인)")

    failed_f.close()
    log(f"=== 종료: {grand_files}파일/{grand_utts}발화 처리, "
        f"건너뜀 {grand_skip}, 총 {(time.time()-t0)/3600:.2f}시간 ===")
    return 0


def _write_speakers(spk_csv: Path, speakers: dict) -> None:
    if not speakers:
        return
    with open(spk_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SPEAKER_FIELDS)
        w.writeheader()
        for row in speakers.values():
            w.writerow({k: row.get(k, "") for k in SPEAKER_FIELDS})


if __name__ == "__main__":
    raise SystemExit(main())

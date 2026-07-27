# -*- coding: utf-8 -*-
"""사전점검(preflight): 검색 마스터 파일럿 전에 깨질 곳을 전부 미리 찾는다.

무엇을 하나
  1) config/paths.json의 모든 경로가 실재하는지 (SSD 이전 누락 탐지)
  2) 파일럿에 필요한 입력이 갖춰졌는지 (bareun CSV·메타·원본 JSON·어휘목록 v1)
  3) 각 파일의 컬럼/필드가 기대와 맞는지 (헤더 수준 검증)
  4) 쓰기 대상 폴더·디스크 여유 확인
결과는 콘솔과 함께 **logs/preflight_report.txt**에 저장된다.
(이 보고서 파일은 Claude가 원격에서 직접 읽는다 — 복사/붙여넣기 불필요)

실행 (리포 루트 아무 데서나):
  python scripts\\python\\preflight_search_master.py

절대 원본을 수정하지 않는다 — 읽기 + 빈 폴더 생성 시험만.
"""
import csv
import json
import shutil
import subprocess
import sys
from itertools import islice
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P, path_values  # noqa: E402
from pipeline_common import atomic_text_writer  # noqa: E402

REPORT = ROOT / "logs" / "preflight_report.txt"
LINES = []


def log(msg=""):
    print(msg, flush=True)
    LINES.append(msg)


def section(title):
    log()
    log("=" * 60)
    log(title)
    log("=" * 60)


def load_paths():
    p = ROOT / "config" / "paths.json"
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(p.read_text(encoding=enc))
        except Exception:
            continue
    log(f"[치명] paths.json을 읽지 못함: {p}")
    return None


def check_csv_header(path: Path, required: set, label: str):
    """CSV 헤더만 읽어 필수 컬럼 유무 확인. (대용량이어도 헤더 1줄만)"""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f))
        missing = sorted(required - set(header))
        if missing:
            log(f"  [경고] {label}: 필수 컬럼 누락 {missing}")
            log(f"         실제 헤더: {header}")
            return False
        log(f"  [OK] {label}: 필수 컬럼 {len(required)}종 확인 (전체 {len(header)}컬럼)")
        return True
    except FileNotFoundError:
        log(f"  [누락] {label}: 파일 없음 — {path}")
        return False
    except Exception as e:
        log(f"  [오류] {label}: 읽기 실패 ({e})")
        return False


def check_session_id_coverage(raw_root: Path, metadata_csv: Path) -> bool:
    """형태 분석 세션과 문서 메타의 ID 집합이 정확히 같은지 확인한다."""
    raw_ids = {
        path.stem
        for year_dir in raw_root.iterdir()
        if year_dir.is_dir()
        for path in year_dir.glob("*.csv")
        if not path.name.startswith("_")
    }
    with open(metadata_csv, encoding="utf-8-sig", newline="") as stream:
        metadata_ids = [row.get("file_id", "") for row in csv.DictReader(stream)]
    metadata_set = set(metadata_ids)
    duplicates = len(metadata_ids) - len(metadata_set)
    missing = sorted(raw_ids - metadata_set)
    extra = sorted(metadata_set - raw_ids)
    if duplicates or missing or extra or "" in metadata_set:
        log(
            "  [오류] 세션-메타 ID 불일치: "
            f"형태분석={len(raw_ids):,}, 메타행={len(metadata_ids):,}, "
            f"중복={duplicates:,}, 메타누락={len(missing):,}, 메타초과={len(extra):,}"
        )
        if missing:
            log(f"         메타누락 예: {missing[:10]}")
        if extra:
            log(f"         메타초과 예: {extra[:10]}")
        return False
    log(f"  [OK] 세션-메타 ID 집합 일치: {len(raw_ids):,}개")
    return True


def main() -> int:
    ok_all = True
    fixes = []  # (무엇, 어떻게)

    section("0. 환경")
    log(f"  리포 루트: {ROOT}")
    log(f"  Python: {sys.version.split()[0]}")

    # ---------- 1. paths.json 전수 ----------
    section("1. paths.json 경로 실재 여부")
    cfg = load_paths()
    if cfg is None:
        return 1
    missing_keys = []
    resolved = path_values()
    for k, path in resolved.items():
        exists = path.exists()
        mark = "OK  " if exists else "없음"
        log(f"  [{mark}] {k:22s} {path}")
        if not exists:
            missing_keys.append(k)
    # 없어도 파일럿에 지장 없는 키 (지금 단계 기준)
    later_ok = {"gdrive", "textgrid_eojeol", "textgrid_eojeol_staging",
                "actual_pron", "enriched_1gi",
                "search_master", "reference_dictionary", "reference_mp",
                "reference_ls", "reference_multilayer", "bareun_venv_python",
                "mfa_temp_primary", "mfa_temp_secondary",
                "mfa_output_primary", "mfa_output_secondary"}
    blockers = [k for k in missing_keys if k not in later_ok]
    if missing_keys:
        log()
        log("  ── 해석 ──")
        for k in missing_keys:
            if k in ("search_master", "actual_pron"):
                log(f"  · {k}: 신규 출력 폴더 — 스크립트가 만들므로 정상")
            elif k in ("textgrid_eojeol", "textgrid_eojeol_staging"):
                log(f"  · {k}: MFA 재정렬 산출 폴더 — CSV 생성에는 무관")
            elif k in ("enriched_1gi",):
                log(f"  · {k}: 1기 백업 (다운로드 예정) — 파일럿 무관")
            elif k == "gdrive":
                log(f"  · {k}: G: 미연결 — 방침상 미사용, 무관")
            elif k == "bareun_venv_python":
                log(f"  · {k}: 기존 바른 API venv — 검색 마스터 생성에는 미사용. "
                    "A1 재분석 전 별도 복구 필요")
            elif k.startswith(("mfa_temp_", "mfa_output_")):
                log(f"  · {k}: MFA 실행 때 생성되는 작업 경로 — CSV 파일럿 무관")
            elif k.startswith("reference_"):
                log(f"  · {k}: ★구 HDD 미이전 추정 — 파일럿엔 무관하나 A단계 재실행에 필요")
                fixes.append((k, f"HDD 연결 후: robocopy \"E:{Path(cfg[k]).as_posix()[2:]}\" \"{cfg[k]}\" /E  (E:는 HDD 문자)"))
            else:
                log(f"  · {k}: ★파일럿 차단 요소")
    if blockers:
        ok_all = False

    # 검색 마스터 실행기는 시스템 PATH의 모호한 python이 아니라 설정된 실행기를 쓴다.
    pipeline_python = P("pipeline_python")
    if pipeline_python.exists():
        try:
            proc = subprocess.run(
                [str(pipeline_python), "--version"],
                check=True, capture_output=True, text=True, encoding="utf-8",
            )
            version = (proc.stdout or proc.stderr).strip()
            log(f"  [OK] pipeline_python 실행 가능: {pipeline_python} ({version})")
        except Exception as exc:
            ok_all = False
            log(f"  [오류] pipeline_python 실행 실패: {pipeline_python} ({exc})")
    else:
        ok_all = False
        log(f"  [누락] pipeline_python 없음: {pipeline_python}")

    # ---------- 2. 파일럿 입력 ----------
    section("2. 파일럿 입력 자료")
    layers = Path(cfg.get("layers", "D:/10_LAYERS"))

    # 2a. bareun raw
    raw = layers / "01_bareun_raw"
    if raw.exists():
        ydirs = [d for d in raw.iterdir() if d.is_dir()]
        log(f"  [OK] 01_bareun_raw: 연도 폴더 {len(ydirs)}개 — {sorted(d.name for d in ydirs)}")
        y2020 = [d for d in ydirs if "2020" in d.name]
        if y2020:
            n = sum(1 for p in y2020[0].glob("*.csv") if not p.name.startswith("_"))
            log(f"       2020 세션 CSV {n:,}개 (고정 참조값 대신 현재 파일 수 사용)")
            sample = next((p for p in sorted(y2020[0].glob("*.csv"))
                           if not p.name.startswith("_")), None)
            if sample:
                check_csv_header(sample, {"utt_id", "speaker_id", "form",
                                          "tagged", "n_morphs"}, f"bareun 표본({sample.name})")
        else:
            ok_all = False
            log("  [누락] 2020 연도 폴더 없음")
    else:
        ok_all = False
        log(f"  [누락] 01_bareun_raw 없음: {raw}")
        fixes.append(("01_bareun_raw", "HDD에서 10_LAYERS 복사 필요"))

    # 2b. 메타데이터
    meta = layers / "04_metadata_index"
    ok_all &= check_csv_header(meta / "file_meta.csv",
                               {"file_id", "year", "category", "topic"},
                               "file_meta.csv")
    ok_all &= check_csv_header(
        meta / "file_meta.csv",
        {"category_norm", "discourse_mode"},
        "file_meta.csv (정규화 컬럼)",
    )
    if raw.exists() and (meta / "file_meta.csv").exists():
        ok_all &= check_session_id_coverage(raw, meta / "file_meta.csv")
    ok_all &= check_csv_header(meta / "speakers_normalized.csv",
                               {"year", "id", "sex_norm", "age_norm",
                                "occupation_norm", "education_ord"},
                               "speakers_normalized.csv")

    # 2c. 원본 JSON (original_form·start·end·note의 출처)
    dj = Path(cfg.get("dialogue_json", "D:/00_RAW/dialogue_json"))
    if dj.exists():
        sample_json = next(islice(dj.rglob("*.json"), 0, 1), None)
        if sample_json:
            try:
                data = json.loads(sample_json.read_text(encoding="utf-8"))
                # 첫 발화 dict 탐색
                utt = None
                stack = [data]
                while stack and utt is None:
                    x = stack.pop()
                    if isinstance(x, dict):
                        if "form" in x and ("original_form" in x or "start" in x):
                            utt = x
                        else:
                            stack.extend(x.values())
                    elif isinstance(x, list):
                        stack.extend(x)
                if utt:
                    have = [k for k in ("original_form", "start", "end", "note") if k in utt]
                    miss = [k for k in ("original_form", "start", "end", "note") if k not in utt]
                    log(f"  [OK] dialogue_json 표본({sample_json.name}): 발화 필드 확인 {have}")
                    if miss:
                        log(f"  [경고] 표본 발화에 없는 필드: {miss} (연도별 스키마 차이 가능 — 파일럿에서 연도별 재확인)")
                else:
                    log(f"  [경고] {sample_json.name}: 발화 구조 미발견 — 파일럿에서 파서 점검 필요")
            except Exception as e:
                log(f"  [경고] JSON 표본 파싱 실패: {e}")
        else:
            ok_all = False
            log(f"  [누락] dialogue_json 아래 .json 없음: {dj}")
    else:
        ok_all = False
        log(f"  [누락] dialogue_json 없음: {dj}")
        fixes.append(("dialogue_json", "HDD에서 00_RAW/dialogue_json 복사 필요"))

    # 2d. 어휘목록 v1 (발음 조회부)
    lex = Path(cfg.get("lexicon_full", ""))
    got = check_csv_header(lex, {"word", "pos_tag", "sense_no", "pron_1",
                                 "pron_2", "pron_g2p", "morph_dict"},
                           "lexicon v1 (발음)")
    if not got:
        ok_all = False
        fixes.append(("lexicon_full",
                      "robocopy \"C:\\Users\\ari30\\Dropbox\\000_NIKL_2026\\00_01_1차_archive\\02_DICTIONARY\" "
                      f"\"{Path(cfg.get('lexicon_full','D:/00_RAW/reference/03_lexicon_1기/x')).parent}\" 01_NIKL_lexicon_full.csv"))

    # 2e. IPA 변환표 (있으면 재사용, 없으면 파일럿이 기본값 생성)
    ipa = layers / "03_freq_dictionaries" / "_roman_mfa_to_ipa.csv"
    if ipa.exists():
        log(f"  [OK] IPA 변환표 존재 (빈도사전과 공유): {ipa}")
    else:
        log(f"  [정보] IPA 변환표 없음 — 파일럿이 기본값으로 생성 (빈도사전 폴더 미이전이면 추후 HDD 것과 대조)")

    # ---------- 3. 출력·용량 ----------
    section("3. 출력 대상·디스크")
    sm = Path(cfg.get("search_master", "D:/10_LAYERS/05_search_master"))
    try:
        probe = sm / "_write_test"
        probe.mkdir(parents=True, exist_ok=True)
        probe.rmdir()
        log(f"  [OK] 출력 폴더 쓰기 가능: {sm}")
    except Exception as e:
        ok_all = False
        log(f"  [오류] 출력 폴더 생성 불가: {sm} ({e})")
    try:
        drive = Path(str(layers)[:3])
        free = shutil.disk_usage(drive).free
        log(f"  [{'OK' if free > 20 * 1024**3 else '경고'}] {drive} 여유 {free/1024**3:.1f}GB (전량 생성 시 ~수 GB + Parquet)")
    except Exception as e:
        log(f"  [경고] 디스크 확인 실패: {e}")

    # ---------- 판정 ----------
    section("판정")
    if ok_all:
        log("  ✅ 파일럿 진행 가능 — 차단 요소 없음")
    else:
        log("  ❌ 차단 요소 있음 — 아래 조치 후 재실행")
    if fixes:
        log()
        log("  ── 조치 목록 ──")
        for what, how in fixes:
            log(f"  · {what}:")
            log(f"      {how}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(REPORT, encoding="utf-8", newline="\n") as (stream, _):
        stream.write("\n".join(LINES) + "\n")
    log()
    log(f"보고서 저장: {REPORT}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())

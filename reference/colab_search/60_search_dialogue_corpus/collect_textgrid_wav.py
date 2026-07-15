"""
collect_textgrid_wav.py
=======================
CSV에서 include=Y로 체크한 행의 TextGrid + WAV 파일을 출력 폴더로 복사

사전 준비:
    python build_file_index.py   (최초 1회, 인덱스 생성)

사용법:
    python collect_textgrid_wav.py <input_csv> [--output_dir <dir>] [--dry-run]

CSV 요구사항:
    - utterance_id 컬럼 필수 (예: SDRW2000000004.1.1.226)
    - include 컬럼에 Y/1 표시된 행만 수집
    - realized 컬럼 (Y/1=실현됨, N/0=미실현) — 하위 폴더로 분리 저장
    - file_id 컬럼 (선택, 없으면 utterance_id에서 추출)

출력 구조:
    output_dir/
      realized/textgrid/    (realized=Y인 파일)
      realized/wav/
      unrealized/textgrid/  (realized=N인 파일)
      unrealized/wav/

예시:
    python collect_textgrid_wav.py search_results/dialogue_phrase_n_insertion_full.csv
    python collect_textgrid_wav.py my_results.csv --output_dir D:/collected_files --dry-run
"""

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

# === 기본 경로 ===
DEFAULT_OUTPUT = Path(r"D:\04_00_NIKL_DIALOGUE_MFA\07_output\collected")
INDEX_PATH = Path(r"G:\내 드라이브\DATA_2026\60_search_dialogue_corpus\file_index.csv")


def load_file_index(index_path=INDEX_PATH):
    """인덱스 CSV를 딕셔너리로 로드 (filename -> full_path)"""
    if not index_path.exists():
        print(f"[ERROR] 파일 인덱스가 없습니다: {index_path}")
        print(f"  먼저 실행: python build_file_index.py")
        sys.exit(1)

    df_idx = pd.read_csv(index_path, encoding="utf-8-sig")
    index = {}
    for _, row in df_idx.iterrows():
        index[row["filename"]] = row["full_path"]
    print(f"  파일 인덱스 로드: {len(index):,}개")
    return index


def find_file(index, utterance_id, ext):
    """인덱스에서 파일 찾기"""
    filename = f"{utterance_id}{ext}"
    path_str = index.get(filename)
    if path_str:
        return Path(path_str)
    return None


def main():
    parser = argparse.ArgumentParser(description="CSV에서 체크한 행의 TextGrid+WAV 수집")
    parser.add_argument("input_csv", help="입력 CSV 파일 경로")
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT),
                        help=f"출력 폴더 (기본: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 복사 없이 파일 존재 여부만 확인")
    parser.add_argument("--include-col", default="include",
                        help="체크 컬럼명 (기본: include)")
    args = parser.parse_args()

    # 인덱스 로드
    file_index = load_file_index()

    # CSV 로드
    df = pd.read_csv(args.input_csv, encoding="utf-8-sig")
    print(f"CSV 로드: {len(df):,}행, 컬럼: {list(df.columns)}")

    # utterance_id 확인
    if "utterance_id" not in df.columns:
        print("[ERROR] utterance_id 컬럼이 없습니다.")
        print("  61번 노트북을 다시 실행하여 utterance_id를 포함시켜주세요.")
        sys.exit(1)

    # include 컬럼 필터
    inc_col = args.include_col
    if inc_col in df.columns:
        df_sel = df[df[inc_col].astype(str).str.strip().isin(["1", "True", "true", "yes", "Y", "o", "O"])].copy()
        print(f"  {inc_col}=1 체크된 행: {len(df_sel):,}개")
    else:
        print(f"  [INFO] '{inc_col}' 컬럼 없음 -> 전체 {len(df):,}행 대상")
        df_sel = df.copy()

    if len(df_sel) == 0:
        print("수집할 행이 없습니다.")
        sys.exit(0)

    # realized 컬럼으로 그룹 분리
    has_realized_col = "realized" in df_sel.columns
    if has_realized_col:
        realized_mask = df_sel["realized"].astype(str).str.strip().isin(["1", "True", "true", "yes", "Y"])
        unrealized_mask = df_sel["realized"].astype(str).str.strip().isin(["0", "False", "false", "no", "N"])
        groups = {}
        if realized_mask.any():
            groups["realized"] = df_sel[realized_mask]
        if unrealized_mask.any():
            groups["unrealized"] = df_sel[unrealized_mask]
        # realized가 빈칸인 행 (체크 안 한 것) — 미분류로 수집
        neither = ~realized_mask & ~unrealized_mask
        if neither.any():
            groups["unclassified"] = df_sel[neither]
        print(f"  realized 분류: { {k: len(v) for k, v in groups.items()} }")
    else:
        groups = {"all": df_sel}
        print("  realized 컬럼 없음 -> 전체를 하나의 폴더에 수집")

    # 출력 폴더
    out_dir = Path(args.output_dir)

    # 수집
    total_tg = 0
    total_wav = 0
    all_missing_tg = []
    all_missing_wav = []
    all_log_data = []

    for group_name, df_group in groups.items():
        utt_ids = df_group["utterance_id"].dropna().unique()
        print(f"\n--- {group_name}: {len(utt_ids):,}개 utterance ---")

        # 그룹별 하위 폴더
        tg_dir = out_dir / group_name / "textgrid"
        wav_dir = out_dir / group_name / "wav"
        if not args.dry_run:
            tg_dir.mkdir(parents=True, exist_ok=True)
            wav_dir.mkdir(parents=True, exist_ok=True)

        found_tg = 0
        found_wav = 0

        for i, uid in enumerate(utt_ids):
            uid = str(uid).strip()
            if not uid:
                continue

            # TextGrid
            tg = find_file(file_index, uid, ".TextGrid")
            if tg:
                found_tg += 1
                if not args.dry_run:
                    shutil.copy2(tg, tg_dir / tg.name)
            else:
                all_missing_tg.append(uid)

            # WAV
            wav = find_file(file_index, uid, ".wav")
            if wav:
                found_wav += 1
                if not args.dry_run:
                    shutil.copy2(wav, wav_dir / wav.name)
            else:
                all_missing_wav.append(uid)

            # 진행률
            if (i + 1) % 100 == 0 or (i + 1) == len(utt_ids):
                print(f"  [{i+1}/{len(utt_ids)}] TG: {found_tg}, WAV: {found_wav}")

            all_log_data.append({
                "utterance_id": uid,
                "group": group_name,
                "textgrid_found": bool(tg),
                "textgrid_path": str(tg) if tg else "",
                "wav_found": bool(wav),
                "wav_path": str(wav) if wav else "",
            })

        total_tg += found_tg
        total_wav += found_wav
        print(f"  -> TG: {found_tg}, WAV: {found_wav}")

    # 결과 요약
    total_utt = sum(len(g["utterance_id"].dropna().unique()) for g in groups.values())
    print(f"\n=== 수집 결과 ===")
    print(f"TextGrid: {total_tg}/{total_utt} 발견 ({len(all_missing_tg)} 누락)")
    print(f"WAV:      {total_wav}/{total_utt} 발견 ({len(all_missing_wav)} 누락)")

    if not args.dry_run:
        print(f"\n출력: {out_dir}")
        for group_name in groups:
            print(f"  {group_name}/textgrid/, {group_name}/wav/")

    if all_missing_tg:
        print(f"\n누락 TextGrid (상위 10): {all_missing_tg[:10]}")
    if all_missing_wav:
        print(f"누락 WAV (상위 10): {all_missing_wav[:10]}")

    # 매핑 로그 저장
    if not args.dry_run and all_log_data:
        log_path = out_dir / "collection_log.csv"
        pd.DataFrame(all_log_data).to_csv(log_path, index=False, encoding="utf-8-sig")
        print(f"\n로그: {log_path}")


if __name__ == "__main__":
    main()

"""
build_file_index.py
====================
D드라이브의 WAV/TextGrid 파일 경로를 인덱스 CSV로 생성.
한 번 실행하면 이후 collect_textgrid_wav.py에서 즉시 lookup 가능.

사용법:
    python build_file_index.py
    python build_file_index.py --force

중단되어도 자동으로 이어서 스캔 (폴더 단위 체크포인트)
"""

import argparse
import csv
import json
import os
import time

DEFAULT_ROOT = r"D:\04_00_NIKL_DIALOGUE_MFA"
DEFAULT_OUTPUT = r"G:\내 드라이브\DATA_2026\60_search_dialogue_corpus\file_index.csv"
CHECKPOINT_PATH = r"G:\내 드라이브\DATA_2026\60_search_dialogue_corpus\file_index_checkpoint.json"
SCAN_FOLDERS = ["03_wav", "06_textgrid_merged"]


def load_checkpoint(checkpoint_path):
    """체크포인트 로드: 완료된 폴더 목록 + 누적 행"""
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_folders": [], "rows": []}


def save_checkpoint(checkpoint_path, data):
    """체크포인트 저장"""
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def build_index(root, output, force=False):
    if os.path.exists(output) and not force:
        print(f"인덱스가 이미 존재합니다: {output}")
        print(f"  강제 재생성: --force")
        return output

    os.makedirs(os.path.dirname(output), exist_ok=True)

    # 체크포인트 로드
    if force:
        ckpt = {"done_folders": [], "rows": []}
    else:
        ckpt = load_checkpoint(CHECKPOINT_PATH)

    if ckpt["done_folders"]:
        print(f"이전 체크포인트 발견: {len(ckpt['done_folders'])}개 폴더 완료, {len(ckpt['rows']):,}개 파일")

    rows = ckpt["rows"]
    done_folders = set(ckpt["done_folders"])
    total_start = time.time()

    for folder in SCAN_FOLDERS:
        base = os.path.join(root, folder)
        if not os.path.exists(base):
            print(f"[SKIP] {base} 없음")
            continue

        # 연도별로 스캔 (체크포인트 단위)
        for year_or_sub in sorted(os.listdir(base)):
            sub_path = os.path.join(base, year_or_sub)
            if not os.path.isdir(sub_path):
                continue

            folder_key = f"{folder}/{year_or_sub}"
            if folder_key in done_folders:
                print(f"  [SKIP] {folder_key} (이미 완료)")
                continue

            print(f"  Scanning {folder_key}...")
            t = time.time()
            count_before = len(rows)

            for dirpath, dirs, files in os.walk(sub_path):
                for f in files:
                    if f.endswith(".wav") or f.endswith(".TextGrid"):
                        rows.append([f, os.path.join(dirpath, f)])

            elapsed = time.time() - t
            added = len(rows) - count_before
            print(f"    {added:,}개 ({elapsed:.0f}s), 누적: {len(rows):,}개")

            # 폴더 완료 -> 체크포인트 저장
            done_folders.add(folder_key)
            save_checkpoint(CHECKPOINT_PATH, {
                "done_folders": list(done_folders),
                "rows": rows,
            })

    # 최종 CSV 저장
    with open(output, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["filename", "full_path"])
        w.writerows(rows)

    total_elapsed = time.time() - total_start
    print(f"\nTotal: {len(rows):,} files -> {output} ({total_elapsed:.0f}s)")

    # 체크포인트 정리
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
        print("체크포인트 삭제 완료")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="D드라이브 WAV/TextGrid 파일 인덱스 생성")
    parser.add_argument("--root", default=DEFAULT_ROOT, help=f"스캔 루트 (기본: {DEFAULT_ROOT})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"출력 경로 (기본: {DEFAULT_OUTPUT})")
    parser.add_argument("--force", action="store_true", help="기존 인덱스/체크포인트 무시하고 처음부터")
    args = parser.parse_args()

    build_index(args.root, args.output, args.force)

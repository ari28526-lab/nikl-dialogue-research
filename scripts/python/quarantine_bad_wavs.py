"""깨진(0바이트/헤더 미만) wav 격리 — MFA 로딩 전체 실패 방지 (2026-07-18).

배경: MFA 3.4는 코퍼스 로딩 워커가 soundfile로 못 여는 wav(예: 0바이트)를
만나면 그 파일만 건너뛰지 않고 **로딩 말미에 전체를 실패**시킨다
(acoustic_corpus.py error_dict → raise). 7/17·7/18 두 차례 본실행이
`SDRW2000000521.1.1.175.wav`(0바이트, 2026-01 변환 산물)로 죽었음.

동작: 연도 wav 폴더(평면/세션 하위폴더 모두)를 훑어 크기 < min-bytes(기본
44=WAV 헤더 최소)인 .wav를 D:\\mfa_eojeol\\quarantine\\{year}\\로 이동(짝 .lab
동반). 기본은 dry-run(목록만), --apply 시 실제 이동. CSV 기록 남김.
스캔은 디렉토리 열거만으로 크기를 얻으므로(Windows scandir) 추가 I/O 없음.

실행: python quarantine_bad_wavs.py --year 2020 [--apply]
      (all = 6개년 전부. 격리 복원은 CSV의 원경로로 되돌리면 됨.)
"""
import argparse
import csv
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import P  # noqa: E402
from pipeline_common import atomic_text_writer, atomic_write_json  # noqa: E402

QUARANTINE_ROOT = P("mfa_state") / "quarantine"
YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def scan_year(
    year: str,
    min_bytes: int,
    apply: bool,
    *,
    wav_root: Path | None = None,
    quarantine_root: Path | None = None,
    inventory_csv: Path | None = None,
) -> int:
    base_wav = wav_root or (P("wav") / "individual")
    qroot = quarantine_root or QUARANTINE_ROOT
    root = base_wav / year
    if not root.is_dir():
        raise FileNotFoundError(f"[{year}] wav 폴더 없음: {root}")
    qdir = qroot / year
    bad = []          # (wav Path, size)
    seen = 0
    t0 = time.time()
    for dirpath, _dirnames, _filenames in os.walk(root):
        # os.walk가 내부적으로 scandir을 쓰지만 크기는 다시 stat이 필요하므로
        # 폴더별 scandir 1회로 크기까지 한 번에 얻는다 (USB 왕복 최소화).
        with os.scandir(dirpath) as it:
            for e in it:
                if not e.is_file() or not e.name.endswith(".wav"):
                    continue
                seen += 1
                size = e.stat().st_size
                if size < min_bytes:
                    bad.append((Path(e.path), size))
                if seen % 200_000 == 0:
                    el = time.time() - t0
                    print(f"  [{year}] {seen:,}개 확인 ({seen/el:,.0f}개/s) · "
                          f"불량 {len(bad)}건", flush=True)
    print(f"[{year}] 스캔 완료: wav {seen:,}개 중 불량(<{min_bytes}B) "
          f"{len(bad)}건 ({time.time()-t0:,.0f}초)", flush=True)
    for p, size in bad:
        print(f"  - {p.relative_to(root)} ({size}B)", flush=True)
    if inventory_csv is not None:
        with atomic_text_writer(
            inventory_csv.resolve(), encoding="utf-8-sig", newline=""
        ) as (stream, _temp):
            fields = [
                "year", "name", "size_bytes", "orig_path",
                "quarantine_path", "lab_present", "apply",
            ]
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for path, size in bad:
                relative = path.relative_to(root)
                writer.writerow(
                    {
                        "year": year,
                        "name": path.name,
                        "size_bytes": size,
                        "orig_path": str(path),
                        "quarantine_path": str(qdir / relative),
                        "lab_present": str(path.with_suffix(".lab").is_file()).lower(),
                        "apply": str(apply).lower(),
                    }
                )
    if not bad:
        return 0
    if not apply:
        print(f"[{year}] dry-run — 이동하려면 --apply", flush=True)
        return len(bad)
    qdir.mkdir(parents=True, exist_ok=True)
    log_path = qdir / "quarantine_log.csv"
    new_log = not log_path.exists()
    with open(log_path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_log:
            w.writerow([
                "transaction_id", "moved_at", "name", "size_bytes",
                "orig_path", "quarantine_path", "lab_moved",
            ])
        for p, size in bad:
            transaction_id = uuid.uuid4().hex
            relative = p.relative_to(root)
            dest = qdir / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            lab = p.with_suffix(".lab")
            lab_moved = lab.exists()
            lab_dest = dest.with_suffix(".lab")
            if dest.exists() or (lab_moved and lab_dest.exists()):
                raise FileExistsError(
                    f"격리 대상 충돌 — 자동 덮어쓰기 금지: {dest}"
                )
            txn = qdir / "_transactions" / f"{transaction_id}.json"
            record = {
                "transaction_id": transaction_id,
                "status": "planned",
                "year": year,
                "size_bytes": size,
                "wav_source": str(p),
                "wav_destination": str(dest),
                "lab_source": str(lab) if lab_moved else None,
                "lab_destination": str(lab_dest) if lab_moved else None,
            }
            atomic_write_json(txn, record)
            try:
                os.replace(p, dest)
                if lab_moved:
                    os.replace(lab, lab_dest)
            except Exception as exc:
                record.update({
                    "status": "partial_failure",
                    "error": f"{type(exc).__name__}: {exc}",
                    "wav_source_exists": p.exists(),
                    "wav_destination_exists": dest.exists(),
                    "lab_source_exists": lab.exists() if lab_moved else None,
                    "lab_destination_exists": (
                        lab_dest.exists() if lab_moved else None
                    ),
                })
                atomic_write_json(txn, record)
                raise
            record.update({"status": "complete", "completed_at": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )})
            atomic_write_json(txn, record)
            w.writerow([
                transaction_id, record["completed_at"], p.name, size,
                str(p), str(dest), lab_moved,
            ])
            f.flush()
            os.fsync(f.fileno())
    print(f"[{year}] {len(bad)}건 격리 완료 → {qdir} (기록: {log_path})",
          flush=True)
    return len(bad)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True, help="2020..2025 또는 all")
    ap.add_argument("--min-bytes", type=int, default=44,
                    help="이 크기 미만이면 불량 (기본 44=WAV 헤더 최소)")
    ap.add_argument("--apply", action="store_true", help="실제 이동 (기본 dry-run)")
    ap.add_argument("--root", type=Path, help="wav individual 루트(테스트용)")
    ap.add_argument("--quarantine-root", type=Path,
                    help="격리 루트(테스트용)")
    ap.add_argument(
        "--inventory-csv",
        type=Path,
        help="dry-run/apply와 무관하게 불량 후보 전수 목록을 원자적으로 기록",
    )
    args = ap.parse_args()
    if args.min_bytes < 44:
        ap.error("--min-bytes는 WAV 최소 헤더 44보다 작게 설정할 수 없습니다.")
    years = YEARS if args.year == "all" else [args.year]
    if args.inventory_csv is not None and len(years) != 1:
        ap.error("--inventory-csv는 연도 1개 실행에서만 사용")
    total = 0
    for y in years:
        if y not in YEARS:
            sys.exit(f"알 수 없는 연도: {y}")
        total += scan_year(
            y, args.min_bytes, args.apply,
            wav_root=args.root, quarantine_root=args.quarantine_root,
            inventory_csv=args.inventory_csv,
        )
    print(f"총 불량 {total}건" + ("" if args.apply else " (dry-run)"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

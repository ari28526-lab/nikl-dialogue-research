# -*- coding: utf-8 -*-
"""발화 클립을 이어 붙여 맥락 검토용 WAV·TextGrid·좌표 manifest를 만든다.

NIKL 배포본은 발화 단위 클립이므로 연결 시간은 원 세션 시간이 아니다.
겹침발화도 직렬화된다. 이 산출물은 후보 주변 청취·KOINA·수동 검토용이며
전량 MFA 입력이나 검색 정본으로 사용하지 않는다.

기본적으로 발화 사이에 0.05초 0진폭 무음을 넣는다. manifest의
stitched_start_seconds를 빼면 각 원 clip의 시간으로 돌아갈 수 있다.

사용:
  python stitch_session.py --session SDRW2000000001 --out C:\\stitch
  python stitch_session.py --around SDRW2000000001.1.1.175 --window 8 \
      --tg-dir D:\\20_AUDIO\\07_textgrid_eojeol_g2p_staging\\2020 \
      --out C:\\stitch
"""

import argparse
import csv
import os
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_utt import locate, parse_utt  # noqa: E402
from paths import P  # noqa: E402
from pipeline_common import promote_staged, staged_text_writer  # noqa: E402
from realign_eojeol_build_corpus import YEAR_DIRS  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ALIGN_TIER_SOURCES = [
    ("words", ("words",)),
    ("phones_mfa", ("phones_mfa", "phones")),
    ("morphemes_legacy", ("morphemes_legacy", "morphemes")),
]
MANIFEST_FIELDS = [
    "order",
    "utt_id",
    "speaker_id",
    "form",
    "source_wav",
    "source_textgrid",
    "stitched_start_seconds",
    "stitched_end_seconds",
    "source_clip_start_seconds",
    "source_clip_end_seconds",
    "source_time_rule",
    "gap_after_seconds",
]


def utt_key(uid):
    return tuple(int(x) for x in uid.split(".")[1:])


def parse_tg_tiers(path):
    """long TextGrid -> {tier: [(xmin,xmax,text)]}."""
    tiers, name, xmin = {}, None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = re.match(r'name = "(.*)"$', stripped)
        if match:
            name = match.group(1)
            tiers.setdefault(name, [])
            xmin = None
            continue
        if name is None:
            continue
        left = re.match(r"xmin = ([\d.]+)$", stripped)
        right = re.match(r"xmax = ([\d.]+)$", stripped)
        label = re.match(r'text = "(.*)"$', stripped)
        if left:
            xmin = float(left.group(1))
        elif right:
            xmax = float(right.group(1))
        elif label is not None and xmin is not None:
            tiers[name].append((xmin, xmax, label.group(1)))
            xmin = None
    return tiers


def tile(intervals, total):
    """겹침을 자르고 빈틈을 채워 [0,total]을 완전히 덮는다."""
    result, current = [], 0.0
    for begin, end, label in sorted(intervals):
        begin = max(begin, current)
        end = max(end, begin)
        if begin > current + 1e-9:
            result.append((current, begin, ""))
        if end > begin:
            result.append((begin, end, label))
            current = end
    if current < total - 1e-9:
        result.append((current, total, ""))
    return result


def esc(text):
    return str(text).replace('"', '""')


def write_textgrid(path, total, tier_data):
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {total:.6f}",
        "tiers? <exists>",
        f"size = {len(tier_data)}",
        "item []:",
    ]
    for tier_index, (name, intervals) in enumerate(tier_data, 1):
        lines += [
            f"    item [{tier_index}]:",
            '        class = "IntervalTier"',
            f'        name = "{name}"',
            "        xmin = 0",
            f"        xmax = {total:.6f}",
            f"        intervals: size = {len(intervals)}",
        ]
        for interval_index, (begin, end, label) in enumerate(intervals, 1):
            lines += [
                f"        intervals [{interval_index}]:",
                f"            xmin = {begin:.6f}",
                f"            xmax = {end:.6f}",
                f'            text = "{esc(label)}"',
            ]
    path = Path(path)
    with staged_text_writer(
        path, encoding="utf-8", newline="\n"
    ) as (stream, staged):
        stream.write("\n".join(lines) + "\n")
    promote_staged(staged, path)


def find_tg(uid, location, tg_dir):
    if tg_dir:
        hits = list(Path(tg_dir).rglob(f"{uid}.TextGrid"))
        if len(hits) > 1:
            raise RuntimeError(f"{uid} TextGrid 중복 {len(hits)}건: {hits[:3]}")
        return hits[0] if hits else None
    path = location["textgrid_eojeol"]
    return path if path.exists() else None


def ordered_utts(session, year):
    bareun = (
        P("layers")
        / "01_bareun_raw"
        / YEAR_DIRS[year]
        / f"{session}.csv"
    )
    with bareun.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: utt_key(row["utt_id"]))
    return rows


def source_intervals(tiers, source_names):
    for name in source_names:
        if tiers.get(name):
            return tiers[name]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session")
    parser.add_argument("--around", help="발화 ID 중심으로 --window개 앞뒤")
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--tg-dir",
        default="",
        help="TextGrid를 이 폴더에서 찾음(rglob); 새 staging 연도 폴더 권장",
    )
    parser.add_argument(
        "--no-align",
        action="store_true",
        help="words/phones/morphemes tier 제외",
    )
    parser.add_argument(
        "--gap-seconds",
        type=float,
        default=0.05,
        help="발화 사이 검토용 0진폭 무음(기본 0.05초)",
    )
    args = parser.parse_args()

    if args.gap_seconds < 0:
        parser.error("--gap-seconds는 0 이상이어야 함")
    session = args.session or (
        args.around.split(".")[0] if args.around else None
    )
    if not session:
        parser.error("--session 또는 --around 필요")
    year = parse_utt(session)[0]
    rows = ordered_utts(session, year)
    if args.around:
        identifiers = [row["utt_id"] for row in rows]
        if args.around not in identifiers:
            sys.exit(f"{args.around} 세션에 없음")
        center = identifiers.index(args.around)
        rows = rows[
            max(0, center - args.window) : center + args.window + 1
        ]

    output_root = Path(args.out)
    output_root.mkdir(parents=True, exist_ok=True)
    tag = args.around.replace(".", "_") if args.around else session
    wav_output = output_root / f"{tag}_stitched.wav"
    tg_output = output_root / f"{tag}_stitched.TextGrid"
    manifest_output = output_root / f"{tag}_stitched_manifest.csv"
    for target in (wav_output, tg_output, manifest_output):
        if target.exists():
            sys.exit(f"기존 출력 보호(새 --out 사용): {target}")

    clips = []
    params = None
    utterance_intervals = []
    speaker_intervals = []
    aligned = {name: [] for name, _ in ALIGN_TIER_SOURCES}
    manifest = []
    skipped = 0

    for row in rows:
        uid = row["utt_id"]
        form = row.get("form", "")
        speaker = row.get("speaker_id", "")
        location = locate(uid)
        wav_path = location["wav"]
        if not wav_path.exists():
            skipped += 1
            continue
        with wave.open(str(wav_path)) as wav_file:
            wav_params = wav_file.getparams()
            if params is None:
                params = wav_params
            elif (
                wav_params.nchannels,
                wav_params.framerate,
                wav_params.sampwidth,
            ) != (params.nchannels, params.framerate, params.sampwidth):
                skipped += 1
                continue
            frame_count = wav_file.getnframes()
            data = wav_file.readframes(frame_count)
        duration = frame_count / params.framerate

        tg_path = None
        tiers = {}
        if not args.no_align:
            tg_path = find_tg(uid, location, args.tg_dir)
            if tg_path:
                tiers = parse_tg_tiers(tg_path)
                tg_end = max(
                    (
                        end
                        for intervals in tiers.values()
                        for _, end, _ in intervals
                    ),
                    default=0.0,
                )
                if abs(tg_end - duration) > 0.02:
                    raise RuntimeError(
                        f"{uid} WAV/TextGrid 길이 불일치 "
                        f"{duration:.6f}/{tg_end:.6f}; padding된 review "
                        "TextGrid는 이어붙이기 입력으로 사용하지 말 것"
                    )

        start = sum(item["duration"] for item in clips)
        start += len(clips) * args.gap_seconds
        end = start + duration
        clips.append({"data": data, "duration": duration})
        utterance_intervals.append((start, end, form))
        speaker_intervals.append((start, end, speaker))
        for output_name, source_names in ALIGN_TIER_SOURCES:
            for begin, finish, label in source_intervals(
                tiers, source_names
            ):
                aligned[output_name].append(
                    (start + begin, start + finish, label)
                )
        manifest.append(
            {
                "order": len(manifest) + 1,
                "utt_id": uid,
                "speaker_id": speaker,
                "form": form,
                "source_wav": str(wav_path),
                "source_textgrid": str(tg_path) if tg_path else "",
                "stitched_start_seconds": f"{start:.6f}",
                "stitched_end_seconds": f"{end:.6f}",
                "source_clip_start_seconds": "0.000000",
                "source_clip_end_seconds": f"{duration:.6f}",
                "source_time_rule": (
                    f"source_clip_time = stitched_time - {start:.6f}"
                ),
                "gap_after_seconds": "",
            }
        )

    if not clips:
        sys.exit("사용 가능한 wav 없음")
    for index, row in enumerate(manifest):
        row["gap_after_seconds"] = (
            f"{args.gap_seconds:.6f}"
            if index < len(manifest) - 1
            else "0.000000"
        )
    total = sum(item["duration"] for item in clips)
    total += (len(clips) - 1) * args.gap_seconds

    wav_partial = wav_output.with_name(
        f".{wav_output.name}.{os.getpid()}.partial"
    )
    try:
        with wave.open(str(wav_partial), "wb") as output_wav:
            output_wav.setparams(params)
            gap_frames = round(args.gap_seconds * params.framerate)
            silence = b"\x00" * (
                gap_frames * params.nchannels * params.sampwidth
            )
            for index, clip in enumerate(clips):
                output_wav.writeframes(clip["data"])
                if index < len(clips) - 1 and silence:
                    output_wav.writeframes(silence)
        os.replace(wav_partial, wav_output)
    finally:
        if wav_partial.exists():
            wav_partial.unlink()

    tier_data = [
        ("utterance", tile(utterance_intervals, total)),
        ("speaker", tile(speaker_intervals, total)),
    ]
    if not args.no_align:
        for name, _ in ALIGN_TIER_SOURCES:
            if aligned[name]:
                tier_data.append((name, tile(aligned[name], total)))
    write_textgrid(tg_output, total, tier_data)
    with manifest_output.open(
        "x", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(manifest)

    print(
        f"발화 {len(clips)}개 연결 (건너뜀 {skipped}) · "
        f"길이 {total:.1f}s · 발화간 gap {args.gap_seconds:.3f}s"
    )
    print(f"wav: {wav_output}")
    print(
        f"TextGrid: {tg_output} "
        f"(tier: {[name for name, _ in tier_data]})"
    )
    print(f"manifest: {manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create an immutable, read-only WAV tree snapshot for one r3 year.

The snapshot does not copy, rename, repair, stat, or open source audio.  It binds the
physical WAV name inventory (relative paths) to a stable
contract so that an exact-ID year-input contract can safely select only the
approved alignment body even when the source tree also contains non-search
WAV files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_common import atomic_write_json, now_iso, runtime_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "mfa_wav_source_snapshot.v1"
STATUS = "passed"


def scan_inventory(root: Path) -> dict[str, object]:
    if not root.is_dir():
        raise RuntimeError(f"WAV year root is not a directory: {root}")
    digest = hashlib.sha256()
    seen: set[str] = set()
    files = 0
    for directory, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if not name.lower().endswith(".wav"):
                continue
            path = Path(directory) / name
            utt_id = path.stem
            if not utt_id or utt_id in seen:
                raise RuntimeError(f"blank or duplicate WAV utt_id: {utt_id!r}")
            seen.add(utt_id)
            relative = path.relative_to(root).as_posix()
            digest.update(f"{relative}\n".encode("utf-8"))
            files += 1
            if files % 100_000 == 0:
                print(f"WAV snapshot: {files:,} files", flush=True)
    if files == 0:
        raise RuntimeError(f"WAV year root contains no .wav files: {root}")
    return {
        "wav_files": files,
        "relative_path_sha256": digest.hexdigest(),
    }


def contract_id(payload: dict[str, object]) -> str:
    identity = {
        "schema_version": payload["schema_version"],
        "year": payload["year"],
        "output_year": payload["output_year"],
        "wav_files": payload["wav_files"],
        "relative_path_sha256": payload["relative_path_sha256"],
    }
    canonical = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build(*, year: str, wav_root: Path, output: Path) -> dict[str, object]:
    inventory = scan_inventory(wav_root)
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "recorded_at": now_iso(),
        "year": year,
        "source_wav_tree_untouched": True,
        "output_year": str(wav_root.resolve()),
        **inventory,
        "corpus_contract_id": "",
        "scope": {
            "audio_content_read": False,
            "file_metadata_stat_performed": False,
            "source_wav_modified": False,
            "wav_copied_or_renamed": False,
            "non_search_wav_allowed_but_never_selected_implicitly": True,
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    payload["corpus_contract_id"] = contract_id(payload)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8-sig"))
        if (
            existing.get("schema_version") == SCHEMA_VERSION
            and existing.get("status") == STATUS
            and existing.get("corpus_contract_id") == payload["corpus_contract_id"]
            and contract_id(existing) == payload["corpus_contract_id"]
        ):
            return existing
        raise RuntimeError("existing WAV source snapshot differs; overwrite refused")
    atomic_write_json(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True)
    parser.add_argument("--wav-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(
        year=args.year,
        wav_root=args.wav_root.resolve(),
        output=args.output.resolve(),
    )
    print(
        f"[OK] {args.year} WAV source snapshot: "
        f"{int(result['wav_files']):,} files; "
        f"contract={result['corpus_contract_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

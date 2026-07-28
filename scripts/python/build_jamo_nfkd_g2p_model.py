"""Build a reproducible MFA Jamo G2P model with NFKD input enabled.

The official ``korean_jamo_mfa`` v3 archive contains a Jamo grapheme
inventory, but its ``unicode_decomposition`` metadata value is null. MFA
3.4.0 therefore validates and rewrites ordinary precomposed Hangul without
first decomposing it, which makes the Jamo FST unusable through the standard
``mfa g2p`` command.

This helper never modifies the official archive. It copies every archive
member byte-for-byte except the single ``meta.json`` member, where it changes
only ``unicode_decomposition`` to ``true``. A manifest fingerprints both
archives and proves that every other member is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path

from pipeline_common import (
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_jamo_g2p_derivation.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_members(path: Path) -> tuple[list[str], dict[str, bytes], bytes]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        payloads = {name: archive.read(name) for name in names}
        comment = archive.comment
    if len(names) != len(set(names)):
        raise RuntimeError(f"중복 ZIP member가 있음: {path}")
    return names, payloads, comment


def validate_derivation(
    *,
    source_model: Path,
    derived_model: Path,
) -> dict:
    source_names, source_payloads, _ = archive_members(source_model)
    derived_names, derived_payloads, _ = archive_members(derived_model)
    if source_names != derived_names:
        raise RuntimeError("파생 모델 ZIP member 순서·집합이 원본과 다름")
    meta_names = [name for name in source_names if name.endswith("/meta.json")]
    if len(meta_names) != 1:
        raise RuntimeError(f"G2P meta.json 수가 1이 아님: {meta_names}")
    meta_name = meta_names[0]
    changed = [
        name
        for name in source_names
        if source_payloads[name] != derived_payloads[name]
    ]
    if changed != [meta_name]:
        raise RuntimeError(f"meta.json 외 ZIP member가 바뀜: {changed}")

    source_meta = json.loads(source_payloads[meta_name].decode("utf-8"))
    derived_meta = json.loads(derived_payloads[meta_name].decode("utf-8"))
    source_value = source_meta.get("unicode_decomposition")
    if source_value not in (None, False):
        raise RuntimeError(
            "원본 unicode_decomposition이 null/false가 아님: "
            f"{source_value!r}"
        )
    if derived_meta.get("unicode_decomposition") is not True:
        raise RuntimeError("파생 모델 unicode_decomposition이 true가 아님")
    source_without_flag = dict(source_meta)
    derived_without_flag = dict(derived_meta)
    source_without_flag.pop("unicode_decomposition", None)
    derived_without_flag.pop("unicode_decomposition", None)
    if source_without_flag != derived_without_flag:
        raise RuntimeError("unicode_decomposition 외 meta 필드가 바뀜")

    unchanged = [
        {
            "name": name,
            "bytes": len(source_payloads[name]),
            "sha256": sha256_bytes(source_payloads[name]),
        }
        for name in source_names
        if name != meta_name
    ]
    canonical = "".join(
        f"{item['name']}\0{item['bytes']}\0{item['sha256']}\n"
        for item in unchanged
    )
    return {
        "meta_member": meta_name,
        "source_unicode_decomposition": source_value,
        "derived_unicode_decomposition": True,
        "unchanged_member_count": len(unchanged),
        "unchanged_members_contract_sha256": sha256_bytes(
            canonical.encode("utf-8")
        ),
        "phones": list(derived_meta.get("phones", [])),
        "graphemes": list(derived_meta.get("graphemes", [])),
    }


def build_derived_model(
    *,
    source_model: Path,
    derived_model: Path,
    manifest_path: Path,
) -> dict:
    source_model = source_model.resolve()
    derived_model = derived_model.resolve()
    manifest_path = manifest_path.resolve()
    if source_model == derived_model:
        raise ValueError("원본 모델과 파생 모델 경로가 같음")
    if not source_model.is_file():
        raise FileNotFoundError(source_model)
    if derived_model.exists() and manifest_path.exists():
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8-sig")
        )
        if (
            manifest.get("schema_version") != SCHEMA_VERSION
            or manifest.get("status") != "success"
        ):
            raise RuntimeError(f"기존 manifest가 유효하지 않음: {manifest_path}")
        if (
            manifest["source_model"]["sha256"]
            != file_fingerprint(source_model, with_sha256=True)["sha256"]
            or manifest["derived_model"]["sha256"]
            != file_fingerprint(derived_model, with_sha256=True)["sha256"]
        ):
            raise RuntimeError("기존 Jamo 파생 모델 fingerprint 불일치")
        validate_derivation(
            source_model=source_model,
            derived_model=derived_model,
        )
        return manifest
    if derived_model.exists() or manifest_path.exists():
        raise FileExistsError(
            "파생 모델과 manifest가 부분 존재함: "
            f"{derived_model}, {manifest_path}"
        )

    derived_model.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    partial = derived_model.with_name(derived_model.name + ".partial")
    if partial.exists():
        raise FileExistsError(f"기존 partial이 있음: {partial}")

    try:
        with zipfile.ZipFile(source_model) as source, zipfile.ZipFile(
            partial, "w"
        ) as destination:
            destination.comment = source.comment
            meta_names = [
                info.filename
                for info in source.infolist()
                if info.filename.endswith("/meta.json")
            ]
            if len(meta_names) != 1:
                raise RuntimeError(
                    f"G2P meta.json 수가 1이 아님: {meta_names}"
                )
            meta_name = meta_names[0]
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == meta_name:
                    meta = json.loads(payload.decode("utf-8"))
                    if meta.get("unicode_decomposition") not in (None, False):
                        raise RuntimeError(
                            "원본 unicode_decomposition이 null/false가 아님"
                        )
                    meta["unicode_decomposition"] = True
                    payload = json.dumps(
                        meta,
                        ensure_ascii=False,
                        indent=4,
                    ).encode("utf-8")
                destination.writestr(info, payload)
        os.replace(partial, derived_model)
    finally:
        if partial.exists():
            partial.unlink()

    contract = validate_derivation(
        source_model=source_model,
        derived_model=derived_model,
    )
    phones = sorted(str(value) for value in contract.pop("phones"))
    graphemes = sorted(str(value) for value in contract.pop("graphemes"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "recorded_at": now_iso(),
        "purpose": (
            "enable lossless NFKD input for the official Korean Jamo MFA "
            "G2P FST without changing its FST, symbols, phones, or graphemes"
        ),
        "source_model": file_fingerprint(
            source_model, with_sha256=True
        ),
        "derived_model": file_fingerprint(
            derived_model, with_sha256=True
        ),
        "change_contract": contract,
        "phone_inventory": {
            "count": len(phones),
            "sorted_sha256": sha256_bytes(
                ("\n".join(phones) + "\n").encode("utf-8")
            ),
        },
        "grapheme_inventory": {
            "count": len(graphemes),
            "sorted_sha256": sha256_bytes(
                ("\n".join(graphemes) + "\n").encode("utf-8")
            ),
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-model", type=Path, required=True)
    parser.add_argument("--derived-model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_derived_model(
        source_model=args.source_model,
        derived_model=args.derived_model,
        manifest_path=args.manifest,
    )
    print(
        "[OK] Jamo NFKD G2P derived model: "
        f"{manifest['derived_model']['sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

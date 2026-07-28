"""공식 Hugging Face Korean MFA 저장소를 재현 가능한 생산 묶음으로 고정한다.

MFA 내장 ``model download``가 최신 Hugging Face release보다 뒤처질 수
있으므로, 이미 clone한 공식 저장소의 commit과 파일 해시를 검증한 뒤
acoustic/G2P archive와 dictionary를 만든다. 원본 저장소는 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path

from build_common_pron_mfa_lexicon import parse_mfa_dictionary_line
from pipeline_common import atomic_write_json, now_iso, sha256_file


SCHEMA_VERSION = "hf_korean_mfa_frozen_bundle.v1"
ACOUSTIC_REQUIRED = (
    "final.alimdl",
    "final.mdl",
    "lda.mat",
    "meta.json",
    "phones.txt",
    "tree",
)
G2P_REQUIRED = (
    "graphemes.sym",
    "meta.json",
    "model.fst",
    "phones.sym",
)


def sorted_set_sha256(values: set[str]) -> str:
    return hashlib.sha256(
        ("\n".join(sorted(values)) + "\n").encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_commit(root: Path) -> str:
    head_path = root / ".git" / "HEAD"
    if not head_path.is_file():
        raise RuntimeError(f"공식 저장소 .git/HEAD가 없음: {root}")
    head = head_path.read_text(encoding="ascii").strip()
    if not head.startswith("ref: "):
        commit = head
    else:
        ref_path = root / ".git" / Path(head[5:])
        if not ref_path.is_file():
            raise RuntimeError(f"공식 저장소 HEAD ref가 없음: {ref_path}")
        commit = ref_path.read_text(encoding="ascii").strip()
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise RuntimeError(f"잘못된 공식 저장소 commit: {commit!r}")
    return commit


def require_files(root: Path, names: tuple[str, ...]) -> list[Path]:
    paths = [root / name for name in names]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError("필수 공식 모델 파일 없음: " + ", ".join(missing))
    return paths


def dictionary_contract(
    path: Path, acoustic_phones: set[str]
) -> dict[str, object]:
    rows = 0
    words: set[str] = set()
    phones: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            word, row_phones, _ = parse_mfa_dictionary_line(
                line, path=path, line_number=line_number
            )
            rows += 1
            words.add(word)
            phones.update(row_phones)
    if not rows:
        raise RuntimeError("공식 dictionary가 비어 있음")
    unsupported = phones - acoustic_phones - {"sil", "spn"}
    if unsupported:
        raise RuntimeError(
            "dictionary phone이 acoustic inventory 밖임: "
            + ", ".join(sorted(unsupported))
        )
    return {
        "rows": rows,
        "words": len(words),
        "phones": len(phones),
        "phone_sorted_sha256": sorted_set_sha256(phones),
        "unsupported_phone_count": len(unsupported),
    }


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_archive(
    destination: Path, members: list[tuple[Path, str]]
) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.partial"
    )
    try:
        with zipfile.ZipFile(
            temp,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for source, member_name in sorted(
                members, key=lambda item: item[1]
            ):
                archive.writestr(zip_info(member_name), source.read_bytes())
        candidate_sha = sha256_file(temp)
        if destination.exists():
            if sha256_file(destination) != candidate_sha:
                raise FileExistsError(
                    f"다른 내용의 동결 archive가 이미 있음: {destination}"
                )
            temp.unlink()
            status = "verified_existing"
        else:
            os.replace(temp, destination)
            status = "created"
    finally:
        if temp.exists():
            temp.unlink()
    return {
        "path": str(destination.resolve()),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "status": status,
        "members": len(members),
    }


def copy_dictionary(source: Path, destination: Path) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_sha = sha256_file(source)
    if destination.exists():
        if sha256_file(destination) != source_sha:
            raise FileExistsError(
                f"다른 내용의 동결 dictionary가 이미 있음: {destination}"
            )
        status = "verified_existing"
    else:
        temp = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.partial"
        )
        shutil.copy2(source, temp)
        os.replace(temp, destination)
        status = "created"
    return {
        "path": str(destination.resolve()),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "status": status,
    }


def source_fingerprints(
    root: Path, paths: list[Path]
) -> list[dict[str, object]]:
    return [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths)
    ]


def build_bundle(
    *,
    hf_root: Path,
    output_directory: Path,
    manifest_path: Path,
) -> dict:
    hf_root = hf_root.resolve()
    output_directory = output_directory.resolve()
    acoustic_root = hf_root / "acoustic"
    dictionary_root = hf_root / "dictionary"
    g2p_root = hf_root / "g2p" / "korean_mfa"
    acoustic_paths = require_files(acoustic_root, ACOUSTIC_REQUIRED)
    dictionary_paths = require_files(
        dictionary_root, ("korean_mfa.dict", "rules.yaml")
    )
    g2p_paths = require_files(g2p_root, G2P_REQUIRED)

    acoustic_meta = read_json(acoustic_root / "meta.json")
    g2p_meta = read_json(g2p_root / "meta.json")
    acoustic_phones = {str(value) for value in acoustic_meta.get("phones", [])}
    g2p_phones = {str(value) for value in g2p_meta.get("phones", [])}
    if not acoustic_phones or not g2p_phones:
        raise RuntimeError("공식 acoustic/G2P phone inventory가 비어 있음")
    if acoustic_phones != g2p_phones:
        raise RuntimeError(
            "공식 acoustic/G2P phone inventory가 동일하지 않음"
        )
    if g2p_meta.get("unicode_decomposition") is not True:
        raise RuntimeError(
            "최신 생산 G2P가 Jamo unicode_decomposition=True가 아님"
        )
    for sym_name in ("phones.sym", "graphemes.sym"):
        if b"\r" in (g2p_root / sym_name).read_bytes():
            raise RuntimeError(
                f"OpenFST symbol 파일에 CR/CRLF가 있음: {sym_name}"
            )

    dictionary = dictionary_contract(
        dictionary_root / "korean_mfa.dict", acoustic_phones
    )
    acoustic_members = [
        (path, f"korean_mfa/{path.name}") for path in acoustic_paths
    ]
    acoustic_members.append(
        (dictionary_root / "rules.yaml", "korean_mfa/rules.yaml")
    )
    g2p_members = [
        (path, f"korean_mfa/{path.name}") for path in g2p_paths
    ]
    acoustic_version = str(acoustic_meta.get("version", "unknown"))
    g2p_version = str(g2p_meta.get("version", "unknown"))
    acoustic_archive = output_directory / (
        f"korean_mfa_acoustic_v{acoustic_version}.zip"
    )
    g2p_archive = output_directory / (
        f"korean_mfa_jamo_g2p_v{g2p_version}.zip"
    )
    dictionary_output = output_directory / (
        f"korean_mfa_dictionary_v{acoustic_version}.dict"
    )

    archive_acoustic = build_archive(acoustic_archive, acoustic_members)
    archive_g2p = build_archive(g2p_archive, g2p_members)
    frozen_dictionary = copy_dictionary(
        dictionary_root / "korean_mfa.dict", dictionary_output
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "recorded_at": now_iso(),
        "source": {
            "hf_root": str(hf_root),
            "repository": "MontrealCorpusTools/korean_mfa",
            "commit": read_commit(hf_root),
            "files": source_fingerprints(
                hf_root,
                acoustic_paths + dictionary_paths + g2p_paths,
            ),
        },
        "contract": {
            "acoustic_version": acoustic_version,
            "g2p_version": g2p_version,
            "unicode_decomposition": True,
            "phone_count": len(acoustic_phones),
            "phone_sorted_sha256": sorted_set_sha256(acoustic_phones),
            "acoustic_g2p_phone_inventory_equal": True,
            "symbol_files_cr_count": 0,
            "dictionary": dictionary,
        },
        "outputs": {
            "acoustic_model": archive_acoustic,
            "g2p_model": archive_g2p,
            "dictionary": frozen_dictionary,
        },
    }
    atomic_write_json(manifest_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-root", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    report = build_bundle(
        hf_root=args.hf_root,
        output_directory=args.output_directory,
        manifest_path=args.manifest,
    )
    print(
        "[OK] frozen Korean MFA bundle: "
        f"acoustic={report['contract']['acoustic_version']}, "
        f"g2p={report['contract']['g2p_version']}, "
        f"phones={report['contract']['phone_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

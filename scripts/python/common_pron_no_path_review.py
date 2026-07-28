"""Review and repair deterministic MFA G2P no-path words.

The frozen Jamo G2P can return exit code 0 while omitting a word for which its
FST has no path.  This helper never guesses a phone sequence and never
overwrites a pronunciation that the frozen model already generated.

Known surface words are mapped to an explicitly documented standard-
pronunciation respelling.  The same frozen Jamo G2P generates phones for that
respelling, a researcher approves the candidate, and only then may the missing
surface key be added to a shard.  The partial shard is backed up before an
atomic replacement, and a separate repair manifest preserves the exception
provenance.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

from build_common_pron_mfa_lexicon import (
    acoustic_phone_inventory,
    clean,
    read_generated_dictionary,
    verify_g2p_shard,
)
from pipeline_common import (
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
    sha256_file,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "common_pron_g2p_no_path.v1"
PENDING_EXIT = 76
UNKNOWN_EXIT = 77
MAPPING_FIELDS = (
    "surface",
    "respelled",
    "rule_id",
    "evidence_source",
    "evidence_detail",
)
REVIEW_FIELDS = (
    *MAPPING_FIELDS,
    "pron_phones_mfa",
    "decision",
    "notes",
)
DECISIONS = {"pending", "approved", "rejected"}


def _strip(value: object) -> str:
    return str(value or "").strip()


def _ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved_root = root.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise RuntimeError(f"경로 경계 위반: {resolved} (root={resolved_root})")
    return resolved


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(
        path, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream, fieldnames=fieldnames, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def load_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != MAPPING_FIELDS:
            raise RuntimeError(
                f"no-path mapping 열 계약 불일치: {reader.fieldnames}"
            )
        rows = []
        for raw in reader:
            row = {
                "surface": clean(raw["surface"]),
                "respelled": clean(raw["respelled"]),
                "rule_id": _strip(raw["rule_id"]),
                "evidence_source": _strip(raw["evidence_source"]),
                "evidence_detail": _strip(raw["evidence_detail"]),
            }
            if not all(row.values()):
                raise RuntimeError(f"no-path mapping 빈 필드: {row}")
            rows.append(row)
    surfaces = [row["surface"] for row in rows]
    respelled = [row["respelled"] for row in rows]
    if not rows or len(surfaces) != len(set(surfaces)):
        raise RuntimeError("no-path mapping surface가 비었거나 중복됨")
    if len(respelled) != len(set(respelled)):
        raise RuntimeError("no-path mapping respelled가 중복됨")
    return rows


def prepare_input(mapping_path: Path, output_path: Path) -> dict:
    rows = load_mapping(mapping_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(
        output_path, encoding="utf-8", newline="\n"
    ) as (stream, _):
        for row in rows:
            stream.write(row["respelled"] + "\n")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "kind": "no_path_respelled_input",
        "counts": {"candidates": len(rows)},
        "inputs": {
            "mapping": file_fingerprint(mapping_path, with_sha256=True)
        },
        "output": file_fingerprint(output_path, with_sha256=True),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }


def _review_candidate(row: dict[str, str], phones: tuple[str, ...]) -> dict:
    return {
        **row,
        "pron_phones_mfa": " ".join(phones),
        "decision": "pending",
        "notes": "",
    }


def _candidate_signature(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(_strip(row[field]) for field in REVIEW_FIELDS[:-2])


def read_review(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != REVIEW_FIELDS:
            raise RuntimeError(
                f"no-path review 열 계약 불일치: {reader.fieldnames}"
            )
        rows = []
        for raw in reader:
            row = {field: _strip(raw[field]) for field in REVIEW_FIELDS}
            row["surface"] = clean(row["surface"])
            row["respelled"] = clean(row["respelled"])
            if row["decision"] not in DECISIONS:
                raise RuntimeError(
                    f"no-path review decision 불일치: {row['decision']}"
                )
            rows.append(row)
    surfaces = [row["surface"] for row in rows]
    if not rows or len(surfaces) != len(set(surfaces)):
        raise RuntimeError("no-path review surface가 비었거나 중복됨")
    return rows


def build_review(
    *,
    mapping_path: Path,
    raw_dictionary: Path,
    acoustic_model: Path,
    g2p_model: Path,
    frozen_model_pin: Path,
    review_path: Path,
    manifest_path: Path,
) -> dict:
    for label, path in (
        ("G2P model", g2p_model),
        ("frozen model pin", frozen_model_pin),
    ):
        if not path.is_file():
            raise RuntimeError(f"no-path {label} 없음: {path}")
    mappings = load_mapping(mapping_path)
    generated = read_generated_dictionary(raw_dictionary)
    expected = {row["respelled"] for row in mappings}
    missing = expected - set(generated)
    extras = set(generated) - expected
    if missing or extras:
        raise RuntimeError(
            "no-path respelled G2P coverage 불일치: "
            f"missing={len(missing)} extras={len(extras)}"
        )
    inventory = acoustic_phone_inventory(acoustic_model)
    unknown = {
        phone
        for phones in generated.values()
        for phone in phones
        if phone not in inventory
    }
    if unknown:
        raise RuntimeError(
            f"no-path respelled phone inventory 이탈: {sorted(unknown)}"
        )
    spn = [
        row["respelled"]
        for row in mappings
        if "spn" in generated[row["respelled"]]
    ]
    if spn:
        raise RuntimeError(f"no-path respelled spn 후보: {spn}")

    candidates = [
        _review_candidate(row, generated[row["respelled"]])
        for row in mappings
    ]
    if review_path.exists():
        existing = {
            row["surface"]: row for row in read_review(review_path)
        }
        if set(existing) != {row["surface"] for row in candidates}:
            raise RuntimeError("기존 no-path 연구자 검토표 후보 집합이 달라짐")
        for candidate in candidates:
            old = existing[candidate["surface"]]
            if _candidate_signature(candidate) != _candidate_signature(old):
                raise RuntimeError(
                    "기존 no-path 연구자 검토표 후보가 달라짐: "
                    f"{candidate['surface']}"
                )
            candidate["decision"] = old["decision"]
            candidate["notes"] = old["notes"]

    _write_csv(review_path, REVIEW_FIELDS, candidates)
    approved = sum(row["decision"] == "approved" for row in candidates)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "approved" if approved == len(candidates) else "review_pending"
        ),
        "kind": "reviewed_standard_pronunciation_no_path_candidates",
        "policy": (
            "only fill a frozen-Jamo-G2P missing surface after researcher "
            "approval; never replace an existing model pronunciation"
        ),
        "recorded_at": now_iso(),
        "counts": {
            "candidates": len(candidates),
            "approved": approved,
            "pending_or_rejected": len(candidates) - approved,
            "spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
        },
        "inputs": {
            "helper_code": file_fingerprint(
                Path(__file__), with_sha256=True
            ),
            "mapping": file_fingerprint(mapping_path, with_sha256=True),
            "respelled_g2p": file_fingerprint(
                raw_dictionary, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
            "g2p_model": file_fingerprint(
                g2p_model, with_sha256=True
            ),
            "frozen_model_pin": file_fingerprint(
                frozen_model_pin, with_sha256=True
            ),
        },
        "output": {
            "researcher_review": file_fingerprint(
                review_path, with_sha256=True
            )
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def record_decision(
    *,
    review_path: Path,
    surface: str,
    decision: str,
    notes: str,
    decision_record: Path,
    release_root: Path,
) -> dict:
    release_root = release_root.resolve()
    review_path = _ensure_within(review_path, release_root)
    decision_record = _ensure_within(decision_record, release_root)
    surface = clean(surface)
    decision = _strip(decision)
    notes = _strip(notes)
    if decision not in {"approved", "rejected"}:
        raise RuntimeError("연구자 결정은 approved/rejected만 기록 가능")
    if not surface or not notes:
        raise RuntimeError("연구자 결정 surface/notes는 비울 수 없음")

    rows = read_review(review_path)
    matches = [row for row in rows if row["surface"] == surface]
    if len(matches) != 1:
        raise RuntimeError(
            f"연구자 결정 대상이 정확히 1행이 아님: {surface}"
        )
    row = matches[0]
    previous = row["decision"]
    if previous not in {"pending", decision}:
        raise RuntimeError(
            f"기존 연구자 결정을 자동 반전할 수 없음: "
            f"{surface} {previous}->{decision}"
        )
    if previous == decision and row["notes"] != notes:
        raise RuntimeError(
            f"기존 연구자 결정의 notes를 자동 변경할 수 없음: {surface}"
        )
    if previous == decision and decision_record.exists():
        existing = json.loads(
            decision_record.read_text(encoding="utf-8-sig")
        )
        expected = {
            "surface": surface,
            "respelled": row["respelled"],
            "pron_phones_mfa": row["pron_phones_mfa"],
            "decision": decision,
            "notes": notes,
        }
        if any(existing.get(key) != value for key, value in expected.items()):
            raise RuntimeError(
                f"기존 연구자 결정 기록과 충돌: {decision_record}"
            )
        return existing

    row["decision"] = decision
    row["notes"] = notes
    _write_csv(review_path, REVIEW_FIELDS, rows)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "recorded",
        "kind": "researcher_no_path_pronunciation_decision",
        "recorded_at": now_iso(),
        "surface": surface,
        "respelled": row["respelled"],
        "pron_phones_mfa": row["pron_phones_mfa"],
        "previous_decision": previous,
        "decision": decision,
        "notes": notes,
        "approval_scope": (
            "this exact surface-respelling-phone candidate only"
        ),
        "review": file_fingerprint(review_path, with_sha256=True),
        "helper_code": file_fingerprint(Path(__file__), with_sha256=True),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(decision_record, payload)
    return payload


def _input_words(path: Path) -> list[str]:
    words = [
        clean(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if clean(line)
    ]
    if not words or len(words) != len(set(words)):
        raise RuntimeError(f"shard input이 비었거나 중복됨: {path}")
    return words


def repair_shard(
    *,
    input_shard: Path,
    output_shard: Path,
    acoustic_model: Path,
    review_path: Path,
    release_root: Path,
    attempt_report: Path | None = None,
) -> tuple[int, dict]:
    release_root = release_root.resolve()
    input_shard = _ensure_within(input_shard, release_root)
    output_shard = _ensure_within(output_shard, release_root)
    review_path = _ensure_within(review_path, release_root)
    if attempt_report is not None:
        attempt_report = _ensure_within(attempt_report, release_root)
    if not output_shard.exists():
        raise RuntimeError(f"보수할 partial shard가 없음: {output_shard}")

    def finish(code: int, payload: dict) -> tuple[int, dict]:
        payload.setdefault("recorded_at", now_iso())
        payload.setdefault("input_shard", str(input_shard))
        payload.setdefault("output_shard", str(output_shard))
        if attempt_report is not None:
            atomic_write_json(attempt_report, payload)
        return code, payload

    words = _input_words(input_shard)
    generated = read_generated_dictionary(output_shard)
    missing = [word for word in words if word not in generated]
    extras = sorted(set(generated) - set(words))
    if extras:
        raise RuntimeError(f"partial shard extras가 있음: {extras[:5]}")
    if not missing:
        return finish(0, {
            "schema_version": SCHEMA_VERSION,
            "status": "no_repair_needed",
            "counts": {"missing": 0},
        })

    reviews = {row["surface"]: row for row in read_review(review_path)}
    unknown = [word for word in missing if word not in reviews]
    if unknown:
        return finish(UNKNOWN_EXIT, {
            "schema_version": SCHEMA_VERSION,
            "status": "unknown_missing_words",
            "counts": {"missing": len(missing), "unknown": len(unknown)},
            "missing_words": missing,
            "unknown_words": unknown,
        })
    not_approved = [
        word for word in missing if reviews[word]["decision"] != "approved"
    ]
    if not_approved:
        return finish(PENDING_EXIT, {
            "schema_version": SCHEMA_VERSION,
            "status": "researcher_approval_required",
            "counts": {
                "missing": len(missing),
                "not_approved": len(not_approved),
            },
            "missing_words": missing,
            "not_approved_words": not_approved,
            "review_path": str(review_path),
        })

    inventory = acoustic_phone_inventory(acoustic_model)
    used = []
    repaired = dict(generated)
    for word in missing:
        row = reviews[word]
        phones = tuple(row["pron_phones_mfa"].split())
        if not phones or "spn" in phones:
            raise RuntimeError(f"승인 no-path phone이 비었거나 spn임: {word}")
        outside = sorted(set(phones) - inventory)
        if outside:
            raise RuntimeError(
                f"승인 no-path phone inventory 이탈: {word} {outside}"
            )
        repaired[word] = phones
        used.append(
            {
                "surface": word,
                "respelled": row["respelled"],
                "pron_phones_mfa": row["pron_phones_mfa"],
                "rule_id": row["rule_id"],
                "evidence_source": row["evidence_source"],
                "evidence_detail": row["evidence_detail"],
                "decision": row["decision"],
                "notes": row["notes"],
            }
        )

    repair_dir = _ensure_within(
        release_root
        / "_state"
        / "no_path_repairs"
        / output_shard.stem,
        release_root,
    )
    repair_dir.mkdir(parents=True, exist_ok=True)
    original = file_fingerprint(output_shard, with_sha256=True)
    backup_path = repair_dir / (
        f"partial_{original['sha256'][:16]}.dict"
    )
    if backup_path.exists():
        if sha256_file(backup_path) != original["sha256"]:
            raise RuntimeError(f"기존 no-path backup SHA 불일치: {backup_path}")
    else:
        shutil.copy2(output_shard, backup_path)
    backup = file_fingerprint(backup_path, with_sha256=True)

    review_snapshot_path = repair_dir / "approved_review_snapshot.csv"
    snapshot_rows = [reviews[word] for word in missing]
    if review_snapshot_path.exists():
        if read_review(review_snapshot_path) != snapshot_rows:
            raise RuntimeError(
                f"기존 승인 검토 snapshot 불일치: {review_snapshot_path}"
            )
    else:
        _write_csv(review_snapshot_path, REVIEW_FIELDS, snapshot_rows)

    staged = repair_dir / f"{output_shard.stem}.repaired.staged.dict"
    with atomic_text_writer(
        staged, encoding="utf-8", newline="\n"
    ) as (stream, _):
        for word in words:
            stream.write(f"{word}\t{' '.join(repaired[word])}\n")
    # Verify the full candidate before replacing the production shard.
    verify_g2p_shard(
        input_shard=input_shard,
        output_shard=staged,
        acoustic_model=acoustic_model,
    )
    os.replace(staged, output_shard)
    verification = verify_g2p_shard(
        input_shard=input_shard,
        output_shard=output_shard,
        acoustic_model=acoustic_model,
    )

    manifest_path = repair_dir / "repair_manifest.json"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "kind": "reviewed_no_path_shard_repair",
        "recorded_at": now_iso(),
        "policy": (
            "append only approved missing surfaces using phones generated by "
            "the same frozen Jamo G2P from documented standard respellings"
        ),
        "counts": {
            "input_words": len(words),
            "model_generated_words": len(generated),
            "reviewed_fallback_words": len(used),
            "final_words": len(repaired),
            "spn_words": 0,
            "phone_outside_acoustic_inventory": 0,
        },
        "used_candidates": used,
        "inputs": {
            "helper_code": file_fingerprint(
                Path(__file__), with_sha256=True
            ),
            "input_shard": file_fingerprint(
                input_shard, with_sha256=True
            ),
            "partial_output": original,
            "partial_output_backup": backup,
            "researcher_review": file_fingerprint(
                review_path, with_sha256=True
            ),
            "approved_review_snapshot": file_fingerprint(
                review_snapshot_path, with_sha256=True
            ),
            "acoustic_model": file_fingerprint(
                acoustic_model, with_sha256=True
            ),
        },
        "output": {
            "repaired_shard": file_fingerprint(
                output_shard, with_sha256=True
            ),
            "verification_counts": verification["counts"],
        },
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return finish(0, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare-input")
    prepare.add_argument("--mapping", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    review = sub.add_parser("build-review")
    review.add_argument("--mapping", type=Path, required=True)
    review.add_argument("--raw-dictionary", type=Path, required=True)
    review.add_argument("--acoustic-model", type=Path, required=True)
    review.add_argument("--g2p-model", type=Path, required=True)
    review.add_argument("--frozen-model-pin", type=Path, required=True)
    review.add_argument("--review", type=Path, required=True)
    review.add_argument("--manifest", type=Path, required=True)

    decide = sub.add_parser("record-decision")
    decide.add_argument("--review", type=Path, required=True)
    decide.add_argument("--surface", required=True)
    decide.add_argument(
        "--decision", choices=("approved", "rejected"), required=True
    )
    decide.add_argument("--notes", required=True)
    decide.add_argument("--decision-record", type=Path, required=True)
    decide.add_argument("--release-root", type=Path, required=True)

    repair = sub.add_parser("repair-shard")
    repair.add_argument("--input-shard", type=Path, required=True)
    repair.add_argument("--output-shard", type=Path, required=True)
    repair.add_argument("--acoustic-model", type=Path, required=True)
    repair.add_argument("--review", type=Path, required=True)
    repair.add_argument("--release-root", type=Path, required=True)
    repair.add_argument("--attempt-report", type=Path)
    return parser.parse_args()


def main() -> int:
    # Windows PowerShell 5.1 commonly exposes a CP949 console even though MFA
    # phone labels contain IPA characters.  A successful disk mutation must
    # not be reported as a failed command only because stdout cannot encode ɨ.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    if args.command == "prepare-input":
        payload = prepare_input(args.mapping.resolve(), args.output.resolve())
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "build-review":
        payload = build_review(
            mapping_path=args.mapping.resolve(),
            raw_dictionary=args.raw_dictionary.resolve(),
            acoustic_model=args.acoustic_model.resolve(),
            g2p_model=args.g2p_model.resolve(),
            frozen_model_pin=args.frozen_model_pin.resolve(),
            review_path=args.review.resolve(),
            manifest_path=args.manifest.resolve(),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command == "record-decision":
        payload = record_decision(
            review_path=args.review.resolve(),
            surface=args.surface,
            decision=args.decision,
            notes=args.notes,
            decision_record=args.decision_record.resolve(),
            release_root=args.release_root.resolve(),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    code, payload = repair_shard(
        input_shard=args.input_shard.resolve(),
        output_shard=args.output_shard.resolve(),
        acoustic_model=args.acoustic_model.resolve(),
        review_path=args.review.resolve(),
        release_root=args.release_root.resolve(),
        attempt_report=(
            args.attempt_report.resolve()
            if args.attempt_report is not None
            else None
        ),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

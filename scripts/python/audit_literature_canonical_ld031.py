#!/usr/bin/env python3
"""Regenerate and verify the literature canonical audit for LD-031."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = PROJECT_ROOT / "work/literature_evidence_seven_phenomena_20260822"
AUDIT_DIR = CANONICAL / "audit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(relative: str) -> list[dict]:
    path = CANONICAL / relative
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def add_check(checks: list[dict], name: str, passed: bool, detail: object) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT / "work/pdf_tools"))
    from pypdf import PdfReader  # type: ignore

    sources = load_jsonl("01_inventory/SOURCE_INVENTORY.jsonl")
    instances = load_jsonl("01_inventory/SOURCE_INSTANCES.jsonl")
    events = load_jsonl("01_inventory/SOURCE_VERIFICATION_EVENTS.jsonl")
    relations = load_jsonl("01_inventory/SOURCE_RELATIONS.jsonl")
    seminar = load_jsonl("01_inventory/SEMINAR_SOURCE_LINKS.jsonl")
    wanted = load_jsonl("01_inventory/MISSING_ORIGINALS_WANTED.jsonl")
    claims = load_jsonl("02_claims/CLAIM_EVIDENCE.jsonl")
    decisions = load_jsonl("00_admin/DECISION_LOG.jsonl")

    checks: list[dict] = []
    required = {
        "current_state": "00_admin/CURRENT_STATE.md",
        "decision_log": "00_admin/DECISION_LOG.jsonl",
        "readme": "00_admin/README.md",
        "schema": "00_admin/SCHEMA.md",
        "sources": "01_inventory/SOURCE_INVENTORY.jsonl",
        "instances": "01_inventory/SOURCE_INSTANCES.jsonl",
        "events": "01_inventory/SOURCE_VERIFICATION_EVENTS.jsonl",
        "relations": "01_inventory/SOURCE_RELATIONS.jsonl",
        "claims": "02_claims/CLAIM_EVIDENCE.jsonl",
    }
    for name, relative in required.items():
        add_check(checks, f"required_file:{name}", (CANONICAL / relative).is_file(), relative)

    expected_counts = {
        "sources": 372,
        "instances": 71,
        "events": 15,
        "relations": 50,
        "seminar": 193,
        "wanted": 81,
        "claims": 173,
        "decisions": 31,
    }
    actual_counts = {
        "sources": len(sources),
        "instances": len(instances),
        "events": len(events),
        "relations": len(relations),
        "seminar": len(seminar),
        "wanted": len(wanted),
        "claims": len(claims),
        "decisions": len(decisions),
    }
    add_check(checks, "canonical_counts", actual_counts == expected_counts, actual_counts)

    id_specs = [
        ("source", sources, "source_id", "SRC-", 3, 372),
        ("instance", instances, "instance_id", "INST-", 4, 71),
        ("verification", events, "verification_id", "VER-", 4, 15),
        ("relation", relations, "relation_id", "REL-", 3, 50),
        ("claim", claims, "claim_id", "CLM-", 4, 173),
        ("decision", decisions, "decision_id", "LD-", 3, 31),
    ]
    for name, rows, field, prefix, width, maximum in id_specs:
        observed = [row[field] for row in rows]
        expected = [f"{prefix}{number:0{width}d}" for number in range(1, maximum + 1)]
        add_check(
            checks,
            f"ids_contiguous_unique:{name}",
            observed == expected and len(set(observed)) == len(observed),
            {"first": observed[0], "last": observed[-1], "count": len(observed)},
        )

    source_by_id = {row["source_id"]: row for row in sources}
    physical_mismatches: list[dict] = []
    physical_paths: set[str] = set()
    for row in sources:
        path = PROJECT_ROOT / row["relative_path"]
        physical_paths.add(str(path.resolve()) if path.exists() else str(path))
        observed_size = path.stat().st_size if path.is_file() else None
        observed_sha = sha256(path) if path.is_file() else None
        if observed_size != row["file_size"] or observed_sha != row["sha256"]:
            physical_mismatches.append(
                {
                    "record": row["source_id"],
                    "relative_path": row["relative_path"],
                    "expected_size": row["file_size"],
                    "observed_size": observed_size,
                    "expected_sha256": row["sha256"],
                    "observed_sha256": observed_sha,
                }
            )
    for row in instances:
        path = PROJECT_ROOT / row["relative_path"]
        physical_paths.add(str(path.resolve()) if path.exists() else str(path))
        observed_size = path.stat().st_size if path.is_file() else None
        observed_sha = sha256(path) if path.is_file() else None
        if observed_size != row["file_size"] or observed_sha != row["sha256"]:
            physical_mismatches.append(
                {
                    "record": row["instance_id"],
                    "relative_path": row["relative_path"],
                    "expected_size": row["file_size"],
                    "observed_size": observed_size,
                    "expected_sha256": row["sha256"],
                    "observed_sha256": observed_sha,
                }
            )
    add_check(
        checks,
        "physical_size_and_sha256",
        not physical_mismatches,
        {"checked": len(sources) + len(instances), "mismatches": physical_mismatches},
    )

    broken_relations = []
    for row in relations:
        for field in ("from_source_id", "to_source_id"):
            source_id = row.get(field)
            if source_id is not None and source_id not in source_by_id:
                broken_relations.append({"relation_id": row["relation_id"], field: source_id})
    add_check(checks, "relation_source_references", not broken_relations, broken_relations)

    broken_events = []
    for row in events:
        source = source_by_id.get(row["source_id"])
        if source is None or source["sha256"] != row["source_sha256"]:
            broken_events.append(row["verification_id"])
    add_check(checks, "verification_source_and_sha_references", not broken_events, broken_events)

    intake_expected = {
        "SRC-363": ("e8483021b43803244a2a98117bc1361022880e9bddf2fc1c80a58ea94610ea5e", 369299, 12),
        "SRC-364": ("2d5b2c432bad5dce29cb067efddcc3e6e5984e2781be49f51fd45677eceb15f2", 240675, 29),
        "SRC-365": ("fd4409c89ee3ca3f62e37b3344c70d1b6135f19e607f51b603fbffde7a293138", 7199658, 58),
        "SRC-366": ("179381df613680360f39dca7e67995eed612d237c31b8624c362ca0cdf1834c3", 4542856, 28),
        "SRC-367": ("083efcf107609cb8fa66f67ae3e1df9bd1aeb64421acf931751c3bcd2ca62fc6", 2732147, 279),
        "SRC-368": ("6e17886a7a6e561b4988e535f28d75be7de5e86ac237fae72b3b0c7d16784c47", 5228535, 19),
        "SRC-369": ("6d91a22f9d8156a4cf1874605378db677eff6978dcaa32fa8f9c6182a2b5130c", 843389, 10),
        "SRC-370": ("b7ff1bdf2487920cbbedfe6dfb58ae4d18ade0c7dab84fa6bc9e1f1ced5fcd80", 7886069, 12),
        "SRC-371": ("698868505299e092b696cff94807fa9eaaf3cebd331274d51f6ca59584040fa4", 10817402, 279),
        "SRC-372": ("36180032331b7b04062381ac4db555def4b3c8551be6abdc8337b46b185048ba", 8322006, 10),
    }
    intake_mismatches = []
    for source_id, (expected_sha, expected_size, expected_pages) in intake_expected.items():
        row = source_by_id[source_id]
        path = PROJECT_ROOT / row["relative_path"]
        pages = len(PdfReader(str(path)).pages)
        if (
            row["sha256"] != expected_sha
            or row["file_size"] != expected_size
            or row["page_count"] != expected_pages
            or pages != expected_pages
        ):
            intake_mismatches.append(
                {"source_id": source_id, "observed_pages": pages, "row": row}
            )
    add_check(checks, "ld031_intake_sha_size_pages", not intake_mismatches, intake_mismatches)

    intake_folder = PROJECT_ROOT / "00_참고문헌/06_원문반입_20260825"
    intake_files = sorted(path.name for path in intake_folder.glob("*.pdf"))
    add_check(
        checks,
        "ld031_folder_contract",
        intake_folder.is_dir()
        and len(intake_files) == 10
        and not (PROJECT_ROOT / "00_참고문헌/_반입대기_20260825").exists(),
        intake_files,
    )
    add_check(
        checks,
        "ld031_no_nan_topic_folder",
        not (PROJECT_ROOT / "00_참고문헌/06_비음화_NAN_저해음뒤비음화").exists(),
        "NAN classification is stored in phenomenon_codes",
    )

    p02 = source_by_id["SRC-364"]
    kyobo = [
        record
        for record in p02.get("alternate_bibliographic_records", [])
        if record.get("system") == "kyobo_scholar"
    ]
    add_check(
        checks,
        "ld031_p02_page_and_alternate_record",
        p02.get("page_count") == 29
        and len(kyobo) == 1
        and kyobo[0].get("record_pages") == "75–101",
        {"page_count": p02.get("page_count"), "kyobo": kyobo},
    )

    relation_kinds = Counter(row["kind"] for row in relations[41:])
    add_check(
        checks,
        "ld031_relation_append",
        relation_kinds == Counter({"same_work_variant": 6, "ocr_variant": 3}),
        dict(relation_kinds),
    )
    add_check(
        checks,
        "ld031_verification_append",
        [row["verification_id"] for row in events[5:]]
        == [f"VER-{number:04d}" for number in range(6, 16)],
        [row["verification_id"] for row in events[5:]],
    )
    add_check(
        checks,
        "ld031_p08_not_registered",
        not any(
            row.get("year") == "1992"
            and row.get("title") == "The Domain of Nasalization and the Prosodic Structure in Korean"
            for row in sources
        ),
        "P-08 remains unobtainable_for_now outside SOURCE_INVENTORY",
    )

    unchanged_hashes = {
        "01_inventory/MISSING_ORIGINALS_WANTED.jsonl": "38279b8f2fc3d515776ea5f23632aaab82b7035b9e79d21c2ac2646f3f6866fa",
        "01_inventory/SOURCE_INSTANCES.jsonl": "ce6f454220bf654961408c187b9fa40356ec10ec0a67f4a96df1f53a0db197a7",
        "02_claims/CLAIM_EVIDENCE.jsonl": "0bd9175a55bf845b812318112d69304f1b89db16b713ebdb7a6aaaf147eb2e68",
    }
    observed_unchanged = {
        relative: sha256(CANONICAL / relative) for relative in unchanged_hashes
    }
    add_check(
        checks,
        "ld031_prohibited_ledgers_unchanged",
        observed_unchanged == unchanged_hashes,
        observed_unchanged,
    )

    manifest_files = sorted(
        path
        for path in CANONICAL.rglob("*")
        if path.is_file() and path.parent != AUDIT_DIR and AUDIT_DIR not in path.parents
    )
    file_records = []
    manifest_lines = []
    for path in manifest_files:
        relative_project = path.relative_to(PROJECT_ROOT).as_posix()
        digest = sha256(path)
        record = {
            "path": relative_project,
            "bytes": path.stat().st_size,
            "sha256": digest,
        }
        if path.suffix == ".jsonl":
            record["rows"] = sum(
                1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()
            )
        file_records.append(record)
        manifest_lines.append(f"{digest}  {relative_project}")

    passed = all(check["passed"] for check in checks)
    audit = {
        "schema_version": "literature_canonical_audit.v2",
        "audit_id": "AUDIT_LD031_20260825",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision_id": "LD-031",
        "input_scope": "user-approved P-01 through P-07 source intake, three OCR variants, proposed variant relations, and verification events",
        "passed": passed,
        "counts": actual_counts,
        "canonical_effects": {
            "original_sources_appended": 7,
            "ocr_sources_appended": 3,
            "ocr_relations_appended": 3,
            "same_work_variant_relations_appended": 6,
            "verification_events_appended": 10,
            "decisions_appended": 1,
            "claims_appended": 0,
            "p08_status": "unobtainable_for_now_not_registered",
        },
        "physical_verification": {
            "canonical_source_files_checked": len(sources),
            "registered_instance_files_checked": len(instances),
            "unique_physical_paths_hashed": len(physical_paths),
            "size_and_sha256_mismatches": len(physical_mismatches),
        },
        "source_type_counts": dict(sorted(Counter(row["source_type"] for row in sources).items())),
        "claim_kind_counts": dict(sorted(Counter(row["claim_kind"] for row in claims).items())),
        "checks": checks,
        "files": file_records,
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "SHA256SUMS_L0.txt").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8"
    )
    (AUDIT_DIR / "AUDIT_L0.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": passed, "counts": actual_counts, "checks": checks}, ensure_ascii=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

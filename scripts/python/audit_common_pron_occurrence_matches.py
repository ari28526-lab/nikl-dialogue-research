"""공통 발음 사전 후보와 발화별 형태소 occurrence의 결합을 감사한다.

완료된 A/B 파일럿의 exact-word 후보를 다시 읽어, 같은 철자라도 실제 Bareun
형태소 구성이 사전 표제어와 다른 경우를 표시한다. 출력은 다음 공통 발음
release의 활성화 정책을 설계하기 위한 소표본이며 기존 release를 수정하지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_pronunciation_contract import (  # noqa: E402
    CandidateMatch,
    CONTRACT_VERSION,
    MORPH_MATCH_POLICY_VERSION,
    classify_dictionary_candidate,
    parse_tagged_group,
    reconstructed_surface,
)
from pipeline_common import (  # noqa: E402
    atomic_text_writer,
    atomic_write_json,
    file_fingerprint,
    now_iso,
    runtime_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FIELDS = [
    "year",
    "speaker_id",
    "utt_id",
    "target_token",
    "eojeol_idx",
    "form",
    "lab_text",
    "eojeol_map_status",
    "tagged_group",
    "morph_signature",
    "candidate_id",
    "pron_hangul",
    "pron_source_field",
    "urimal_id",
    "lexicon_pos",
    "sense_no",
    "match_status",
    "occurrence_mfa_status",
    "match_reason",
    "global_plain_word_status",
    "manual_decision",
    "manual_notes",
    "source_search_master_csv",
]


def clean(value: str | None) -> str:
    return (value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def stress_tokens(value: str) -> list[str]:
    return [token.strip() for token in value.split("|") if token.strip()]


def find_utterance(path: Path, utt_id: str) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"utt_id", "form", "tagged"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RuntimeError(
                f"search-master 필수 열 누락 {sorted(missing)}: {path}"
            )
        matches = [row for row in reader if clean(row.get("utt_id")) == utt_id]
    if len(matches) != 1:
        raise RuntimeError(
            f"search-master 발화 역조회 수가 1이 아님: "
            f"utt_id={utt_id} matches={len(matches)} path={path}"
        )
    return matches[0]


def recover_unique_tagged_group(
    token: str,
    tagged_groups: list[str],
) -> str | None:
    matches: list[str] = []
    for group in tagged_groups:
        try:
            surface = reconstructed_surface(parse_tagged_group(group))
        except ValueError:
            continue
        if surface == token:
            matches.append(group)
    if len(matches) == 1:
        return matches[0]
    return None


def build_audit(
    *,
    selection_manifest: Path,
    registry_subset: Path,
    output_csv: Path,
    manual_review: Path | None = None,
) -> dict:
    for path in (selection_manifest, registry_subset):
        if not path.is_file():
            raise FileNotFoundError(path)
    if manual_review is not None and not manual_review.is_file():
        raise FileNotFoundError(manual_review)

    manifest_path = output_csv.with_suffix(".manifest.json")
    for path in (output_csv, manifest_path):
        if path.exists():
            raise FileExistsError(f"기존 감사 산출물 덮어쓰기 금지: {path}")

    selections = read_csv(selection_manifest)
    candidates = read_csv(registry_subset)
    by_token: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        token = clean(candidate.get("token"))
        if token:
            by_token[token].append(candidate)

    manual_by_utt: dict[str, dict[str, str]] = {}
    if manual_review is not None:
        for row in read_csv(manual_review):
            utt_id = clean(row.get("utt_id"))
            if not utt_id or utt_id in manual_by_utt:
                raise RuntimeError(f"수동 검토 utt_id 비어 있음 또는 중복: {utt_id!r}")
            manual_by_utt[utt_id] = row

    rows: list[dict[str, str]] = []
    counters: Counter = Counter()
    cache: dict[tuple[Path, str], dict[str, str]] = {}
    for selection in selections:
        if clean(selection.get("sample_role")) != "stress":
            continue
        utt_id = clean(selection.get("utt_id"))
        source_path = Path(clean(selection.get("source_search_master_csv")))
        key = (source_path, utt_id)
        if key not in cache:
            cache[key] = find_utterance(source_path, utt_id)
        master = cache[key]
        lab_words = clean(selection.get("lab_text")).split()
        tagged_groups = clean(master.get("tagged")).split()
        eojeol_alignment_resolved = len(lab_words) == len(tagged_groups)
        if not eojeol_alignment_resolved:
            counters["utterance:lab_tagged_count_mismatch"] += 1

        for token in stress_tokens(clean(selection.get("stress_tokens"))):
            indices = [
                index
                for index, word in enumerate(lab_words, 1)
                if word == token
            ]
            if not indices:
                raise RuntimeError(
                    f"stress token이 lab에 없음: utt_id={utt_id} token={token}"
                )
            token_candidates = by_token.get(token, [])
            if not token_candidates:
                raise RuntimeError(f"registry 후보가 없음: token={token}")

            for eojeol_idx in indices:
                if eojeol_alignment_resolved:
                    tagged_group = tagged_groups[eojeol_idx - 1]
                    eojeol_map_status = "position_exact"
                elif len(indices) == 1:
                    tagged_group = (
                        recover_unique_tagged_group(token, tagged_groups) or ""
                    )
                    eojeol_map_status = (
                        "unique_surface_recovery"
                        if tagged_group
                        else "unresolved_count_mismatch"
                    )
                else:
                    tagged_group = ""
                    eojeol_map_status = "unresolved_count_mismatch"
                for candidate in token_candidates:
                    if tagged_group:
                        match = classify_dictionary_candidate(
                            token=token,
                            lexicon_pos=clean(candidate.get("pos_tag")),
                            tagged_group=tagged_group,
                        )
                    else:
                        match = CandidateMatch(
                            match_status="eojeol_alignment_unresolved",
                            occurrence_mfa_status="reference_only",
                            reason=(
                                "lab과 tagged 어절 수가 달라 target occurrence의 "
                                "형태소 그룹을 안전하게 연결할 수 없음"
                            ),
                            morph_signature="",
                            reconstructed_surface="",
                        )
                    manual = manual_by_utt.get(utt_id, {})
                    row = {
                        "year": clean(selection.get("year")),
                        "speaker_id": clean(selection.get("speaker_id")),
                        "utt_id": utt_id,
                        "target_token": token,
                        "eojeol_idx": str(eojeol_idx),
                        "form": clean(selection.get("form")),
                        "lab_text": clean(selection.get("lab_text")),
                        "eojeol_map_status": eojeol_map_status,
                        "tagged_group": tagged_group,
                        "morph_signature": match.morph_signature,
                        "candidate_id": clean(candidate.get("candidate_id")),
                        "pron_hangul": clean(candidate.get("pron_hangul")),
                        "pron_source_field": clean(
                            candidate.get("pron_source_field")
                        ),
                        "urimal_id": clean(candidate.get("urimal_id")),
                        "lexicon_pos": clean(candidate.get("pos_tag")),
                        "sense_no": clean(candidate.get("sense_no")),
                        "match_status": match.match_status,
                        "occurrence_mfa_status": match.occurrence_mfa_status,
                        "match_reason": match.reason,
                        "global_plain_word_status": (
                            "pending_full_occurrence_audit"
                        ),
                        "manual_decision": clean(manual.get("decision")),
                        "manual_notes": clean(manual.get("notes")),
                        "source_search_master_csv": str(source_path),
                    }
                    rows.append(row)
                    counters[f"match_status:{match.match_status}"] += 1
                    counters[f"eojeol_map_status:{eojeol_map_status}"] += 1
                    counters[
                        f"occurrence_mfa_status:{match.occurrence_mfa_status}"
                    ] += 1

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with atomic_text_writer(
        output_csv, encoding="utf-8-sig", newline=""
    ) as (stream, _):
        writer = csv.DictWriter(
            stream,
            fieldnames=OUTPUT_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "kind": "common_pronunciation_occurrence_match_audit",
        "status": "success",
        "recorded_at": now_iso(),
        "contract_version": CONTRACT_VERSION,
        "morph_match_policy_version": MORPH_MATCH_POLICY_VERSION,
        "scope": "stress_sample_only_not_global_activation_evidence",
        "inputs": {
            "selection_manifest": file_fingerprint(
                selection_manifest, with_sha256=True
            ),
            "registry_subset": file_fingerprint(
                registry_subset, with_sha256=True
            ),
            "manual_review": (
                file_fingerprint(manual_review, with_sha256=True)
                if manual_review is not None
                else None
            ),
        },
        "counts": {
            "selection_rows": len(selections),
            "stress_selection_rows": sum(
                clean(row.get("sample_role")) == "stress"
                for row in selections
            ),
            "registry_candidate_rows": len(candidates),
            "output_rows": len(rows),
            **dict(sorted(counters.items())),
        },
        "output": file_fingerprint(output_csv, with_sha256=True),
        "runtime": runtime_snapshot(PROJECT_ROOT),
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--registry-subset", type=Path, required=True)
    parser.add_argument("--manual-review", type=Path)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_audit(
        selection_manifest=args.selection_manifest,
        registry_subset=args.registry_subset,
        output_csv=args.output_csv,
        manual_review=args.manual_review,
    )
    print(
        "[OK] occurrence match audit="
        f"{manifest['counts']['output_rows']:,}행; 전역 MFA 자동 채택 안 함",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

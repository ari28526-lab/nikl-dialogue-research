from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "python"))

import audit_common_pron_occurrence_matches as audit  # noqa: E402


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class AuditCommonPronOccurrenceMatchesTests(unittest.TestCase):
    def test_build_audit_separates_surface_only_suga(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            master = root / "master.csv"
            write_csv(
                master,
                ["utt_id", "form", "tagged"],
                [
                    {
                        "utt_id": "u1",
                        "form": "있다",
                        "tagged": "있/VV+다/EF",
                    },
                    {
                        "utt_id": "u2",
                        "form": "그것",
                        "tagged": "그것/NP",
                    },
                    {
                        "utt_id": "u3",
                        "form": "수가 없다",
                        "tagged": "수/NNB+가/JKS 없/VA+다/EF",
                    },
                ],
            )
            selection = root / "selection.csv"
            selection_rows = []
            for utt_id, token, form in (
                ("u1", "있다", "있다"),
                ("u2", "그것", "그것"),
                ("u3", "수가", "수가 없다"),
            ):
                selection_rows.append(
                    {
                        "year": "2024",
                        "sample_role": "stress",
                        "speaker_id": "s1",
                        "utt_id": utt_id,
                        "form": form,
                        "lab_text": form,
                        "stress_tokens": token,
                        "source_search_master_csv": str(master),
                    }
                )
            write_csv(
                selection,
                [
                    "year",
                    "sample_role",
                    "speaker_id",
                    "utt_id",
                    "form",
                    "lab_text",
                    "stress_tokens",
                    "source_search_master_csv",
                ],
                selection_rows,
            )
            registry = root / "registry.csv"
            write_csv(
                registry,
                [
                    "candidate_id",
                    "token",
                    "pron_hangul",
                    "pron_source_field",
                    "urimal_id",
                    "pos_tag",
                    "sense_no",
                ],
                [
                    {
                        "candidate_id": "c1",
                        "token": "있다",
                        "pron_hangul": "읻따",
                        "pron_source_field": "pron_1",
                        "urimal_id": "1",
                        "pos_tag": "VV",
                        "sense_no": "001",
                    },
                    {
                        "candidate_id": "c2",
                        "token": "그것",
                        "pron_hangul": "그걷",
                        "pron_source_field": "pron_1",
                        "urimal_id": "2",
                        "pos_tag": "NP",
                        "sense_no": "001",
                    },
                    {
                        "candidate_id": "c3",
                        "token": "수가",
                        "pron_hangul": "수까",
                        "pron_source_field": "pron_1",
                        "urimal_id": "3",
                        "pos_tag": "NNG",
                        "sense_no": "005",
                    },
                ],
            )
            manual = root / "manual.csv"
            write_csv(
                manual,
                ["utt_id", "decision", "notes"],
                [
                    {
                        "utt_id": "u3",
                        "decision": "A가 더 나음",
                        "notes": "B는 수까",
                    }
                ],
            )
            output = root / "audit.csv"
            manifest = audit.build_audit(
                selection_manifest=selection,
                registry_subset=registry,
                output_csv=output,
                manual_review=manual,
            )

            rows = audit.read_csv(output)
            by_token = {row["target_token"]: row for row in rows}
            self.assertEqual(
                by_token["있다"]["match_status"],
                "predicate_dictionary_form_pos",
            )
            self.assertEqual(
                by_token["그것"]["match_status"],
                "exact_single_morph_pos",
            )
            self.assertEqual(
                by_token["수가"]["match_status"],
                "surface_only_morphologically_composed",
            )
            self.assertEqual(
                by_token["수가"]["occurrence_mfa_status"],
                "reference_only",
            )
            self.assertEqual(by_token["수가"]["manual_decision"], "A가 더 나음")
            self.assertEqual(manifest["counts"]["output_rows"], 3)
            self.assertTrue(output.with_suffix(".manifest.json").is_file())

    def test_build_audit_recovers_unique_group_when_counts_differ(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            master = root / "master.csv"
            write_csv(
                master,
                ["utt_id", "form", "tagged"],
                [
                    {
                        "utt_id": "u1",
                        "form": "수가 정말 없다",
                        "tagged": "수/NNB+가/JKS 없/VA+다/EF",
                    }
                ],
            )
            selection = root / "selection.csv"
            write_csv(
                selection,
                [
                    "year",
                    "sample_role",
                    "speaker_id",
                    "utt_id",
                    "form",
                    "lab_text",
                    "stress_tokens",
                    "source_search_master_csv",
                ],
                [
                    {
                        "year": "2024",
                        "sample_role": "stress",
                        "speaker_id": "s1",
                        "utt_id": "u1",
                        "form": "수가 정말 없다",
                        "lab_text": "수가 정말 없다",
                        "stress_tokens": "수가",
                        "source_search_master_csv": str(master),
                    }
                ],
            )
            registry = root / "registry.csv"
            write_csv(
                registry,
                [
                    "candidate_id",
                    "token",
                    "pron_hangul",
                    "pron_source_field",
                    "urimal_id",
                    "pos_tag",
                    "sense_no",
                ],
                [
                    {
                        "candidate_id": "c1",
                        "token": "수가",
                        "pron_hangul": "수까",
                        "pron_source_field": "pron_1",
                        "urimal_id": "1",
                        "pos_tag": "NNG",
                        "sense_no": "005",
                    }
                ],
            )
            output = root / "audit.csv"
            manifest = audit.build_audit(
                selection_manifest=selection,
                registry_subset=registry,
                output_csv=output,
            )
            row = audit.read_csv(output)[0]
            self.assertEqual(
                row["match_status"],
                "surface_only_morphologically_composed",
            )
            self.assertEqual(row["occurrence_mfa_status"], "reference_only")
            self.assertEqual(
                row["eojeol_map_status"],
                "unique_surface_recovery",
            )
            self.assertEqual(
                manifest["counts"][
                    "utterance:lab_tagged_count_mismatch"
                ],
                1,
            )

    def test_build_audit_keeps_nonunique_recovery_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            master = root / "master.csv"
            write_csv(
                master,
                ["utt_id", "form", "tagged"],
                [
                    {
                        "utt_id": "u1",
                        "form": "수가 정말 없다",
                        "tagged": "수/NNB+가/JKS 수/NNB+가/JKS",
                    }
                ],
            )
            selection = root / "selection.csv"
            write_csv(
                selection,
                [
                    "year",
                    "sample_role",
                    "speaker_id",
                    "utt_id",
                    "form",
                    "lab_text",
                    "stress_tokens",
                    "source_search_master_csv",
                ],
                [
                    {
                        "year": "2024",
                        "sample_role": "stress",
                        "speaker_id": "s1",
                        "utt_id": "u1",
                        "form": "수가 정말 없다",
                        "lab_text": "수가 정말 없다",
                        "stress_tokens": "수가",
                        "source_search_master_csv": str(master),
                    }
                ],
            )
            registry = root / "registry.csv"
            write_csv(
                registry,
                [
                    "candidate_id",
                    "token",
                    "pron_hangul",
                    "pron_source_field",
                    "urimal_id",
                    "pos_tag",
                    "sense_no",
                ],
                [
                    {
                        "candidate_id": "c1",
                        "token": "수가",
                        "pron_hangul": "수까",
                        "pron_source_field": "pron_1",
                        "urimal_id": "1",
                        "pos_tag": "NNG",
                        "sense_no": "005",
                    }
                ],
            )
            output = root / "audit.csv"
            audit.build_audit(
                selection_manifest=selection,
                registry_subset=registry,
                output_csv=output,
            )
            row = audit.read_csv(output)[0]
            self.assertEqual(
                row["match_status"],
                "eojeol_alignment_unresolved",
            )
            self.assertEqual(row["occurrence_mfa_status"], "reference_only")
            self.assertEqual(
                row["eojeol_map_status"],
                "unresolved_count_mismatch",
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import build_eojeol_pronunciation_compare as compare  # noqa: E402
import build_pron_reference_utterance_index as utterance_index  # noqa: E402
import verify_eojeol_pronunciation_compare as verify_compare  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


def write_csv(path: Path, fields: set[str], rows: list[dict]) -> None:
    ordered = sorted(fields)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ordered, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class EojeolCompareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.master = self.root / "master.csv.gz"
        self.eojeol = self.root / "eojeol.csv.gz"
        self.occurrence = self.root / "occurrence.csv.gz"
        self.words = self.root / "words.csv.gz"
        self.summaries = self.root / "summaries.csv.gz"
        self.year_manifest = self.root / "year.json"
        self.occurrence_manifest = self.root / "occurrence.json"
        self.tables_manifest = self.root / "tables.json"
        self.summary_manifest = self.root / "summary.json"
        self.output = self.root / "output"

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def base(fields: set[str], **values: str) -> dict[str, str]:
        result = {field: "" for field in fields}
        result.update(values)
        return result

    def fixture(self) -> None:
        write_csv(
            self.master,
            compare.MASTER_REQUIRED,
            [
                self.base(
                    compare.MASTER_REQUIRED,
                    utt_id="u1",
                    year="2020",
                    session_id="s1",
                    form="읽",
                    canonical_tagged="읽/VV",
                    n_eojeol="1",
                    morph_eojeol_count_structured="1",
                    form_tagged_eojeol_count_equal="True",
                    pron_reference_form="읽",
                    pron_reference_hangul="익따",
                    pron_reference_roman="I k _ TT A",
                    pron_reference_source="form_rule_prediction",
                    pron_reference_status="resolved_form",
                    pron_reference_n_eojeol="1",
                )
            ],
        )
        write_csv(
            self.eojeol,
            compare.ORTH_EOJEOL_REQUIRED,
            [
                self.base(
                    compare.ORTH_EOJEOL_REQUIRED,
                    utt_id="u1",
                    year="2020",
                    orth_eojeol_idx="1",
                    orth_eojeol_count="1",
                    orth_eojeol_form="읽",
                    orth_eojeol_roman_v2="I l k",
                    linked_morph_eojeol_idx="1",
                    morph_link_status="count_aligned",
                )
            ],
        )
        write_csv(
            self.occurrence,
            compare.OCCURRENCE_REQUIRED,
            [
                self.base(
                    compare.OCCURRENCE_REQUIRED,
                    utt_id="u1",
                    year="2020",
                    eojeol_idx="1",
                    morph_idx_in_eojeol="1",
                    morph_surface="읽",
                    pos="VV",
                    candidate_group_id="g1",
                    dict_match_status="matched_exact_surface_pos",
                    preferred_source_tier="dictionary_attested",
                    pronunciation_resolution_status="unique_candidate_unique_pronunciation",
                )
            ],
        )
        write_csv(
            self.words,
            compare.WORD_REQUIRED,
            [
                self.base(
                    compare.WORD_REQUIRED,
                    utt_id="u1",
                    year="2020",
                    session_id="s1",
                    reference_eojeol_idx="1",
                    reference_eojeol="읽",
                    begin_seconds="0.1",
                    end_seconds="0.5",
                    word_mfa="읽",
                    is_silence="false",
                    pron_mfa_ipa="ik͈t͈a",
                    pron_mfa_r_auto="I k TT A",
                    mapping_status="mapped",
                )
            ],
        )
        write_csv(
            self.summaries,
            compare.SUMMARY_REQUIRED,
            [
                self.base(
                    compare.SUMMARY_REQUIRED,
                    candidate_group_id="g1",
                    preferred_source_tier="dictionary_attested",
                    pronunciation_resolution_status="unique_candidate_unique_pronunciation",
                    preferred_pron_hangul_json='["익따"]',
                    preferred_pron_roman_search_json='["I k _ TT A"]',
                )
            ],
        )
        self.year_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "year": "2020",
                    "tables": {
                        "master": {**file_fingerprint(self.master, with_sha256=True), "rows": 1},
                        "orth_eojeol_tokens": {**file_fingerprint(self.eojeol, with_sha256=True), "rows": 1},
                    },
                }
            ),
            encoding="utf-8",
        )
        self.occurrence_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "year": "2020",
                    "outputs": {"occurrences": file_fingerprint(self.occurrence, with_sha256=True)},
                }
            ),
            encoding="utf-8",
        )
        self.tables_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "year": "2020",
                    "tables": {"words": file_fingerprint(self.words, with_sha256=True)},
                }
            ),
            encoding="utf-8",
        )
        self.summary_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "outputs": {"summaries": file_fingerprint(self.summaries, with_sha256=True)},
                }
            ),
            encoding="utf-8",
        )

    def args(self, preflight: bool = False) -> Namespace:
        return Namespace(
            year="2020",
            utterance_master=self.master,
            orth_eojeol_tokens=self.eojeol,
            year_manifest=self.year_manifest,
            morph_occurrences=self.occurrence,
            occurrence_manifest=self.occurrence_manifest,
            word_intervals=self.words,
            tables_manifest=self.tables_manifest,
            group_summaries=self.summaries,
            group_summary_manifest=self.summary_manifest,
            output_dir=self.output,
            max_utterances=None,
            progress_every=0,
            preflight_only=preflight,
        )

    def test_builds_complete_side_by_side_comparison(self) -> None:
        self.fixture()
        manifest = compare.build(self.args())
        with gzip.open(
            self.output / "eojeol_pronunciation_compare.csv.gz",
            "rt",
            encoding="utf-8",
            newline="",
        ) as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["pron_rule_hangul"], "익따")
        self.assertEqual(row["pron_mfa_r_auto"], "I k TT A")
        self.assertEqual(
            row["rule_mfa_roman_compare_status"],
            "same_roman_token_sequence",
        )
        self.assertEqual(
            row["single_morph_dict_rule_compare_status"],
            "same_roman_token_sequence",
        )
        self.assertEqual(row["pron_audit_status"], "complete_no_flagged_difference")
        self.assertEqual(manifest["counts"]["eojeol_rows"], 1)
        verification = verify_compare.verify(
            Namespace(
                year="2020",
                orth_eojeol_tokens=self.eojeol,
                compare=self.output / "eojeol_pronunciation_compare.csv.gz",
                compare_manifest=self.output
                / "eojeol_pronunciation_compare_manifest.json",
                output_report=self.output / "VERIFY.json",
                progress_every=0,
            )
        )
        self.assertEqual(verification["status"], "passed")

    def test_preflight_does_not_write(self) -> None:
        self.fixture()
        result = compare.build(self.args(preflight=True))
        self.assertEqual(result["status"], "preflight_passed")
        self.assertFalse(self.output.exists())

    def test_builds_utterance_level_seventh_tier_label(self) -> None:
        self.fixture()
        compare.build(self.args())
        index_output = self.root / "utterance_index"
        manifest = utterance_index.build(
            Namespace(
                year="2020",
                utterance_master=self.master,
                year_manifest=self.year_manifest,
                compare=self.output / "eojeol_pronunciation_compare.csv.gz",
                compare_manifest=self.output
                / "eojeol_pronunciation_compare_manifest.json",
                output_dir=index_output,
                max_utterances=None,
                progress_every=0,
                preflight_only=False,
            )
        )
        with gzip.open(
            index_output / "pron_reference_utterance.csv.gz",
            "rt",
            encoding="utf-8",
            newline="",
        ) as stream:
            row = next(csv.DictReader(stream))
        self.assertIn("[RULE_H] 익따", row["pron_reference_utt_label"])
        self.assertIn("[MFA_COMPARE] same=1", row["pron_reference_utt_label"])
        self.assertEqual(
            manifest["textgrid_label_schema_version"],
            "pron_reference_utt.v1",
        )

    def test_roman_comparison_ignores_display_separators_not_tokens(self) -> None:
        self.assertEqual(
            compare.compare_roman("I k _ TT A", "I k TT A"),
            "same_roman_token_sequence",
        )
        self.assertEqual(
            compare.compare_roman("I t _ JJ A", "I s JJ A"),
            "different_roman_token_sequence",
        )


if __name__ == "__main__":
    unittest.main()

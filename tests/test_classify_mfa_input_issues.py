import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from classify_mfa_input_issues import classify  # noqa: E402


class ClassifyMfaInputIssuesTests(unittest.TestCase):
    def test_separates_source_exclusions_and_recovery_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            pcm = root / "pcm.csv"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2021",
                                "morph_source_issues": [
                                    {
                                        "session": "S1",
                                        "utt_id": "S1.1",
                                        "issue": "morph_source_missing",
                                        "path": "missing1.TextGrid",
                                    },
                                    {
                                        "session": "S2",
                                        "utt_id": "S2.1",
                                        "issue": "morph_source_missing",
                                        "path": "missing2.TextGrid",
                                    },
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with open(pcm, "w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["year", "utt_id", "pcm_sec", "category"])
                writer.writerow(["2021", "S1.1", "0.1", "원본짧음"])
                writer.writerow(["2021", "S2.1", "2.5", "원본정상"])

            rows, summary = classify(
                audit_report=audit,
                source_pcm_check=pcm,
                year="2021",
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                summary["counts"]["source_audio_unusable_exclusions"], 1
            )
            self.assertEqual(
                summary["counts"][
                    "morpheme_alignment_recovery_candidates"
                ],
                1,
            )
            self.assertTrue(summary["all_issues_classified"])

    def test_unmatched_issue_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            pcm = root / "pcm.csv"
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2021",
                                "morph_source_issues": [
                                    {
                                        "session": "S1",
                                        "utt_id": "S1.1",
                                        "issue": "morph_source_missing",
                                        "path": "missing.TextGrid",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            pcm.write_text(
                "year,utt_id,pcm_sec,category\n",
                encoding="utf-8",
            )
            rows, summary = classify(
                audit_report=audit,
                source_pcm_check=pcm,
                year="2021",
            )
            self.assertEqual(
                rows[0]["recommended_action"],
                "manual_review_unclassified",
            )
            self.assertFalse(summary["all_issues_classified"])

    def test_physically_impossible_text_duration_is_source_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.json"
            pcm = root / "pcm.csv"
            search = root / "search"
            (search / "2021").mkdir(parents=True)
            audit.write_text(
                json.dumps(
                    {
                        "years": [
                            {
                                "year": "2021",
                                "morph_source_issues": [
                                    {
                                        "session": "S1",
                                        "utt_id": "S1.1",
                                        "issue": "morph_source_missing",
                                        "path": "missing.TextGrid",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            pcm.write_text(
                "year,utt_id,pcm_sec,category\n"
                "2021,S1.1,0.5,원본정상\n",
                encoding="utf-8",
            )
            with (search / "2021" / "S1.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "utt_id",
                        "form",
                        "pron_reference_form",
                        "dur",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "utt_id": "S1.1",
                        "form": "가" * 25,
                        "pron_reference_form": "가" * 25,
                        "dur": "0.5",
                    }
                )

            rows, summary = classify(
                audit_report=audit,
                source_pcm_check=pcm,
                year="2021",
                search_master_root=search,
            )

            self.assertEqual(
                rows[0]["recommended_action"],
                "exclude_source_audio_unusable",
            )
            self.assertEqual(
                rows[0]["exclusion_reason"],
                "source_segment_text_duration_impossible",
            )
            self.assertEqual(
                summary["by_exclusion_reason"][
                    "source_segment_text_duration_impossible"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()

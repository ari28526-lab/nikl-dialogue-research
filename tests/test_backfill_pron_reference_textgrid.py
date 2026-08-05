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

import backfill_pron_reference_textgrid as backfill  # noqa: E402
import verify_pron_reference_textgrid_backfill as verify_backfill  # noqa: E402
import research_textgrid_v2 as textgrid_v2  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402
from retrofit_textgrid_2020_2024 import parse_mfa_textgrid  # noqa: E402


class PronReferenceTextGridBackfillTests(unittest.TestCase):
    def write_gzip_csv(self, path: Path, fields: list[str], rows: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_json(self, path: Path, payload: dict):
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_session_checkpoint_and_first_six_tier_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            year = "2020"
            session = "S1"
            utt_id = "U1"
            second_utt_id = "U10"
            source_root = root / "source"
            source = source_root / year / session / f"{utt_id}.TextGrid"
            source.parent.mkdir(parents=True)
            duration = 1.0
            utterance = [(0.0, 0.1, ""), (0.1, 0.9, "가"), (0.9, 1.0, "")]
            words = [(0.0, 0.1, ""), (0.1, 0.9, "가"), (0.9, 1.0, "")]
            phones = [(0.0, 0.1, ""), (0.1, 0.9, "k"), (0.9, 1.0, "")]
            phoneme = [(0.0, 0.1, ""), (0.1, 0.9, "G"), (0.9, 1.0, "")]
            textgrid_v2.write_textgrid_exact(
                source,
                duration=duration,
                tier_data=[
                    ("words", words),
                    ("phones_mfa", phones),
                    ("phoneme_r_auto", phoneme),
                    ("utterance", utterance),
                    ("utterance_orth_r", [(0.0, 0.1, ""), (0.1, 0.9, "G A"), (0.9, 1.0, "")]),
                    ("morph_analysis_utt", [(0.0, 0.1, ""), (0.1, 0.9, "가/VV"), (0.9, 1.0, "")]),
                ],
            )
            second_source = source_root / year / session / f"{second_utt_id}.TextGrid"
            textgrid_v2.write_textgrid_exact(
                second_source,
                duration=duration,
                tier_data=[
                    ("words", words),
                    ("phones_mfa", phones),
                    ("phoneme_r_auto", phoneme),
                    ("utterance", utterance),
                    ("utterance_orth_r", [(0.0, 0.1, ""), (0.1, 0.9, "G A"), (0.9, 1.0, "")]),
                    ("morph_analysis_utt", [(0.0, 0.1, ""), (0.1, 0.9, "가/VV"), (0.9, 1.0, "")]),
                ],
            )
            alignment = root / "utterance_alignment.csv.gz"
            self.write_gzip_csv(
                alignment,
                ["utt_id", "year", "session_id", "textgrid_relative_path"],
                [
                    {
                        "utt_id": utt_id,
                        "year": year,
                        "session_id": session,
                        "textgrid_relative_path": f"{year}/{session}/{utt_id}.TextGrid",
                    },
                    {
                        "utt_id": second_utt_id,
                        "year": year,
                        "session_id": session,
                        "textgrid_relative_path": f"{year}/{session}/{second_utt_id}.TextGrid",
                    },
                ],
            )
            tables_manifest = root / "TABLES_MANIFEST.json"
            self.write_json(
                tables_manifest,
                {
                    "status": "success",
                    "year": year,
                    "textgrid_schema_version": "research_textgrid.v2",
                    "tables": {
                        "utterances": file_fingerprint(alignment, with_sha256=True)
                    },
                    "counts": {"utterances": 2},
                },
            )
            label = "[RULE_H] 가 || [DICT] linked=1"
            index = root / "pron_reference_utterance.csv.gz"
            self.write_gzip_csv(
                index,
                [
                    "utt_id",
                    "year",
                    "session_id",
                    "pron_reference_utt_label",
                    "textgrid_label_schema_version",
                ],
                [
                    {
                        "utt_id": utt_id,
                        "year": year,
                        "session_id": session,
                        "pron_reference_utt_label": label,
                        "textgrid_label_schema_version": "pron_reference_utt.v1",
                    },
                    # U2 models an utterance present in the pronunciation index
                    # but excluded from the MFA alignment output.
                    {
                        "utt_id": "U2",
                        "year": year,
                        "session_id": session,
                        "pron_reference_utt_label": "excluded",
                        "textgrid_label_schema_version": "pron_reference_utt.v1",
                    },
                    {
                        "utt_id": second_utt_id,
                        "year": year,
                        "session_id": session,
                        "pron_reference_utt_label": label,
                        "textgrid_label_schema_version": "pron_reference_utt.v1",
                    },
                ],
            )
            index_manifest = root / "PRON_REFERENCE_UTTERANCE_MANIFEST.json"
            self.write_json(
                index_manifest,
                {
                    "status": "success",
                    "year": year,
                    "textgrid_label_schema_version": "pron_reference_utt.v1",
                    "outputs": {
                        "index": file_fingerprint(index, with_sha256=True)
                    },
                },
            )
            output_root = root / "output"
            args = Namespace(
                year=year,
                source_textgrid_root=source_root,
                utterance_alignment=alignment,
                tables_manifest=tables_manifest,
                utterance_index=index,
                utterance_index_manifest=index_manifest,
                output_root=output_root,
                max_sessions=1,
                preflight_only=False,
            )
            first = backfill.build(args)
            self.assertEqual(first["status"], "bounded_pilot_success")
            destination = output_root / year / session / f"{utt_id}.TextGrid"
            _source_duration, source_tiers = parse_mfa_textgrid(source)
            _output_duration, output_tiers = parse_mfa_textgrid(destination)
            self.assertEqual(
                list(output_tiers), textgrid_v2.BASE_TIERS + [backfill.TIER_NAME]
            )
            for name in textgrid_v2.BASE_TIERS:
                self.assertTrue(
                    textgrid_v2._same_intervals(source_tiers[name], output_tiers[name])
                )
            self.assertTrue(
                textgrid_v2._same_edges(
                    output_tiers["utterance"], output_tiers[backfill.TIER_NAME]
                )
            )
            self.assertEqual(
                [row[2] for row in output_tiers[backfill.TIER_NAME] if row[2]],
                [label],
            )
            self.assertTrue(
                (output_root / year / session / f"{second_utt_id}.TextGrid").is_file()
            )
            self.assertEqual(first["counts"]["index_rows_not_in_alignment"], 1)
            audit = verify_backfill.verify(
                Namespace(
                    year=year,
                    source_textgrid_root=source_root,
                    output_root=output_root,
                    report=None,
                )
            )
            self.assertEqual(audit["status"], "passed")
            self.assertEqual(audit["counts"]["textgrids_semantically_verified"], 2)
            second = backfill.build(args)
            self.assertEqual(second["counts"]["sessions_skipped_checkpoint"], 1)
            self.assertEqual(second["counts"].get("sessions_created", 0), 0)


if __name__ == "__main__":
    unittest.main()

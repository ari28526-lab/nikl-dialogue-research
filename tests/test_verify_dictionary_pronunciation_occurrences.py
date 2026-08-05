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

from pipeline_common import file_fingerprint  # noqa: E402
from verify_dictionary_pronunciation_occurrences import verify  # noqa: E402


FIELDS = [
    "utt_id",
    "year",
    "eojeol_idx",
    "morph_idx_in_eojeol",
    "morph_idx_in_utterance",
    "morph_surface",
    "pos",
]


def write_gzip_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class VerifyOccurrenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.morph = self.root / "morph.csv.gz"
        self.occurrence = self.root / "occurrence.csv.gz"
        self.manifest = self.root / "manifest.json"
        self.report = self.root / "report.json"
        base = {
            "utt_id": "u1",
            "year": "2021",
            "eojeol_idx": "1",
            "morph_idx_in_eojeol": "1",
            "morph_idx_in_utterance": "1",
            "morph_surface": "있",
            "pos": "VA",
        }
        write_gzip_csv(self.morph, FIELDS, [base])
        occurrence = {
            **base,
            "candidate_group_id": "g1",
            "dict_match_status": "matched_exact_surface_pos",
            "sense_match_status": "corpus_sense_unavailable",
        }
        write_gzip_csv(
            self.occurrence,
            FIELDS
            + [
                "candidate_group_id",
                "dict_match_status",
                "sense_match_status",
            ],
            [occurrence],
        )
        payload = {
            "status": "success",
            "year": "2021",
            "coverage_complete": True,
            "counts": {
                "rows": 1,
                "status_matched_exact_surface_pos": 1,
            },
            "outputs": {
                "occurrences": file_fingerprint(
                    self.occurrence, with_sha256=True
                )
            },
        }
        self.manifest.write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def args(self) -> Namespace:
        return Namespace(
            year="2021",
            morph_tokens=self.morph,
            occurrences=self.occurrence,
            occurrence_manifest=self.manifest,
            output_report=self.report,
            progress_every=0,
        )

    def test_passes_exact_link_contract(self) -> None:
        report = verify(self.args())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["rows_verified"], 1)
        self.assertEqual(report["error_counts"], {})

    def test_fails_identity_mismatch(self) -> None:
        with gzip.open(
            self.occurrence, "rt", encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
            fields = list(rows[0])
        rows[0]["morph_surface"] = "없"
        write_gzip_csv(self.occurrence, fields, rows)
        payload = json.loads(self.manifest.read_text(encoding="utf-8"))
        payload["outputs"]["occurrences"] = file_fingerprint(
            self.occurrence, with_sha256=True
        )
        self.manifest.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            verify(self.args())
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["error_counts"]["identity_mismatch_morph_surface"], 1)


if __name__ == "__main__":
    unittest.main()

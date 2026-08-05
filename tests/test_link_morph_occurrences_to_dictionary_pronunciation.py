from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = PROJECT_ROOT / "scripts" / "python"
sys.path.insert(0, str(PYTHON_ROOT))

import link_morph_occurrences_to_dictionary_pronunciation as linker  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


MORPH_FIELDS = sorted(linker.MORPH_REQUIRED)
GROUP_FIELDS = sorted(linker.GROUP_REQUIRED)


def write_gzip(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class MorphOccurrenceLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.morph = self.root / "morph_tokens.csv.gz"
        self.year_manifest = self.root / "YEAR_MANIFEST.json"
        self.groups = self.root / "groups.csv.gz"
        self.match_manifest = self.root / "MATCH_MANIFEST.json"
        self.output = self.root / "output"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_fixture(self) -> None:
        morph_rows = []
        for index, (surface, pos, literal) in enumerate(
            [
                ("여행", "NNG", "False"),
                ("저", "MM", "False"),
                (".", "SF", "True"),
                ("name1", "NNG", "True"),
                ("미등재", "NNG", "False"),
            ],
            1,
        ):
            row = {field: "" for field in MORPH_FIELDS}
            row.update(
                {
                    "utt_id": "U1",
                    "year": "2020",
                    "eojeol_idx": str(index),
                    "morph_idx_in_eojeol": "1",
                    "morph_idx_in_utterance": str(index),
                    "morph_surface": surface,
                    "pos": pos,
                    "has_literal": literal,
                    "has_standalone_jamo": "False",
                }
            )
            morph_rows.append(row)
        write_gzip(self.morph, MORPH_FIELDS, morph_rows)

        group_rows = []
        for group_id, surface, pos in (
            ("g-travel", "여행", "NNG"),
            ("g-jeo", "저", "NNG"),
        ):
            row = {field: "" for field in GROUP_FIELDS}
            row.update(
                {
                    "candidate_group_id": group_id,
                    "morph_surface": surface,
                    "corpus_pos": pos,
                    "match_type": "headword_exact_pos",
                    "candidate_count": "2",
                    "preferred_source_tier": "dictionary_attested",
                    "preferred_candidate_count": "1",
                    "preferred_pronunciation_count": "1",
                    "pronunciation_resolution_status": (
                        "unique_candidate_unique_pronunciation"
                    ),
                }
            )
            group_rows.append(row)
        write_gzip(self.groups, GROUP_FIELDS, group_rows)

        self.year_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "year": "2020",
                    "tables": {
                        "morph_tokens": {
                            **file_fingerprint(self.morph, with_sha256=True),
                            "rows": len(morph_rows),
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.match_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "outputs": {
                        "groups": file_fingerprint(
                            self.groups, with_sha256=True
                        )
                    },
                }
            ),
            encoding="utf-8",
        )

    def args(self, *, preflight_only: bool = False):
        return linker.argparse.Namespace(
            year="2020",
            morph_tokens=self.morph,
            year_manifest=self.year_manifest,
            match_groups=self.groups,
            match_manifest=self.match_manifest,
            output_dir=self.output,
            max_rows=None,
            progress_every=0,
            preflight_only=preflight_only,
        )

    def test_linker_preserves_one_row_per_occurrence(self) -> None:
        self.write_fixture()
        manifest = linker.build(self.args())
        path = self.output / "morph_dictionary_pron_occurrences.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 5)
        by_surface = {row["morph_surface"]: row for row in rows}
        self.assertEqual(
            by_surface["여행"]["dict_match_status"],
            "matched_exact_surface_pos",
        )
        self.assertEqual(by_surface["여행"]["candidate_group_id"], "g-travel")
        self.assertEqual(
            by_surface["여행"]["sense_match_status"],
            "corpus_sense_unavailable",
        )
        self.assertEqual(
            by_surface["저"]["dict_match_status"],
            "surface_found_pos_mismatch",
        )
        self.assertEqual(
            by_surface["."]["dict_match_status"],
            "not_applicable_punctuation",
        )
        self.assertEqual(
            by_surface["name1"]["dict_match_status"],
            "not_applicable_nonstandard_surface",
        )
        self.assertEqual(
            by_surface["미등재"]["dict_match_status"],
            "dictionary_surface_not_found",
        )
        self.assertTrue(manifest["coverage_complete"])

    def test_preflight_does_not_load_or_write_full_output(self) -> None:
        self.write_fixture()
        report = linker.build(self.args(preflight_only=True))
        self.assertEqual(report["status"], "preflight_passed")
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

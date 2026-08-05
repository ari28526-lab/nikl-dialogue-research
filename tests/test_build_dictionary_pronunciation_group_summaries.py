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

import build_dictionary_pronunciation_group_summaries as summaries  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class GroupSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.csv.gz"
        self.groups = self.root / "groups.csv.gz"
        self.members = self.root / "members.csv.gz"
        self.registry_manifest = self.root / "registry_manifest.json"
        self.match_manifest = self.root / "match_manifest.json"
        self.output = self.root / "output"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fixture(self) -> None:
        registry_fields = sorted(summaries.REGISTRY_FIELDS)
        base = {field: "" for field in registry_fields}
        rows = [
            {
                **base,
                "dict_pron_candidate_id": "c1",
                "headword": "읽다",
                "word_stem": "읽",
                "pos_tag": "VV",
                "sense_no": "001",
                "urimal_id": "u1",
                "pron_hangul": "익따",
                "pron_roman_search": "I k _ TT A",
                "source_name": "urimal",
                "source_field": "pron_1",
            },
            {
                **base,
                "dict_pron_candidate_id": "c2",
                "headword": "읽다",
                "word_stem": "읽",
                "pos_tag": "VV",
                "sense_no": "002",
                "urimal_id": "u2",
                "pron_hangul": "익따",
                "pron_roman_search": "I k _ TT A",
                "source_name": "legacy",
                "source_field": "pron_g2p",
            },
        ]
        write_csv(self.registry, registry_fields, rows)
        group_fields = sorted(summaries.GROUP_FIELDS)
        write_csv(
            self.groups,
            group_fields,
            [
                {
                    "candidate_group_id": "g1",
                    "morph_surface": "읽",
                    "corpus_pos": "VV",
                    "match_type": "predicate_stem_exact_pos",
                    "preferred_source_tier": "dictionary_attested",
                    "preferred_candidate_count": "1",
                    "preferred_pronunciation_count": "1",
                    "pronunciation_resolution_status": "unique_candidate_unique_pronunciation",
                }
            ],
        )
        member_fields = sorted(summaries.MEMBER_FIELDS)
        write_csv(
            self.members,
            member_fields,
            [
                {
                    "candidate_group_id": "g1",
                    "dict_pron_candidate_id": "c1",
                    "member_priority": "preferred",
                },
                {
                    "candidate_group_id": "g1",
                    "dict_pron_candidate_id": "c2",
                    "member_priority": "retained_fallback",
                },
            ],
        )
        self.registry_manifest.write_text(
            json.dumps(
                {
                    "status": "success",
                    "outputs": {
                        "registry": file_fingerprint(
                            self.registry, with_sha256=True
                        )
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
                        ),
                        "members": file_fingerprint(
                            self.members, with_sha256=True
                        ),
                    },
                }
            ),
            encoding="utf-8",
        )

    def args(self, preflight: bool = False) -> Namespace:
        return Namespace(
            registry=self.registry,
            registry_manifest=self.registry_manifest,
            match_groups=self.groups,
            match_members=self.members,
            match_manifest=self.match_manifest,
            output_dir=self.output,
            progress_every=0,
            preflight_only=preflight,
        )

    def test_builds_non_selecting_preferred_and_fallback_summary(self) -> None:
        self.fixture()
        manifest = summaries.build(self.args())
        with gzip.open(
            self.output / "dictionary_pronunciation_group_summaries.csv.gz",
            "rt",
            encoding="utf-8",
            newline="",
        ) as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(json.loads(row["preferred_candidate_ids_json"]), ["c1"])
        self.assertEqual(
            json.loads(row["retained_fallback_candidate_ids_json"]), ["c2"]
        )
        self.assertEqual(json.loads(row["preferred_pron_hangul_json"]), ["익따"])
        self.assertIn("sense=001", row["preferred_sense_refs_json"])
        self.assertEqual(manifest["counts"]["summary_groups"], 1)

    def test_preflight_does_not_write(self) -> None:
        self.fixture()
        report = summaries.build(self.args(preflight=True))
        self.assertEqual(report["status"], "preflight_passed")
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()

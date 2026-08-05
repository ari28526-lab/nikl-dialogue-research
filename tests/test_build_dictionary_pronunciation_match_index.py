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

import build_dictionary_pronunciation_match_index as match  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


REGISTRY_FIELDS = sorted(match.REGISTRY_REQUIRED)


def row(**values: str) -> dict[str, str]:
    result = {field: "" for field in REGISTRY_FIELDS}
    result.update(values)
    return result


class DictionaryPronunciationMatchIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.csv.gz"
        self.registry_manifest = self.root / "registry_manifest.json"
        self.output = self.root / "index"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_fixture(self) -> None:
        rows = [
            row(
                dict_pron_candidate_id="travel-attested",
                headword="여행",
                word_stem="여행",
                pos_tag="NNG",
                pron_hangul="여행",
                is_dictionary_attested="true",
                is_legacy_fallback="false",
            ),
            row(
                dict_pron_candidate_id="travel-fallback",
                headword="여행",
                word_stem="여행",
                pos_tag="NNG",
                pron_hangul="여행",
                is_dictionary_attested="false",
                is_legacy_fallback="true",
            ),
            row(
                dict_pron_candidate_id="read",
                headword="읽다",
                word_stem="읽",
                pos_tag="VV",
                pron_hangul="익따",
                is_dictionary_attested="true",
                is_legacy_fallback="false",
            ),
            row(
                dict_pron_candidate_id="jeo-noun",
                headword="저",
                word_stem="저",
                pos_tag="NNG",
                pron_hangul="저",
                is_dictionary_attested="true",
                is_legacy_fallback="false",
            ),
            row(
                dict_pron_candidate_id="jeo-pronoun",
                headword="저",
                word_stem="저",
                pos_tag="NP",
                pron_hangul="저",
                is_dictionary_attested="true",
                is_legacy_fallback="false",
            ),
            row(
                dict_pron_candidate_id="no-pos",
                headword="있잖아",
                word_stem="있잖아",
                pos_tag="",
                pron_hangul="읻짜나",
                is_dictionary_attested="false",
                is_legacy_fallback="true",
            ),
        ]
        with gzip.open(
            self.registry, "wt", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream, fieldnames=REGISTRY_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        payload = {
            "status": "success",
            "outputs": {
                "registry": file_fingerprint(self.registry, with_sha256=True)
            },
        }
        self.registry_manifest.write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def args(self, *, preflight_only: bool = False):
        return match.argparse.Namespace(
            registry=self.registry,
            registry_manifest=self.registry_manifest,
            output_dir=self.output,
            progress_every=0,
            preflight_only=preflight_only,
        )

    @staticmethod
    def read_gzip(path: Path) -> list[dict[str, str]]:
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_build_groups_by_surface_and_exact_pos(self) -> None:
        self.write_fixture()
        manifest = match.build(self.args())
        groups = self.read_gzip(
            self.output / "dictionary_pronunciation_match_groups.csv.gz"
        )
        members = self.read_gzip(
            self.output / "dictionary_pronunciation_match_group_members.csv.gz"
        )

        self.assertEqual(len(groups), 4)
        self.assertEqual(len(members), 5)
        by_key = {(r["morph_surface"], r["corpus_pos"]): r for r in groups}
        travel = by_key[("여행", "NNG")]
        self.assertEqual(travel["preferred_source_tier"], "dictionary_attested")
        self.assertEqual(travel["candidate_count"], "2")
        self.assertEqual(travel["preferred_candidate_count"], "1")
        self.assertEqual(
            travel["pronunciation_resolution_status"],
            "unique_candidate_unique_pronunciation",
        )
        self.assertIn(("읽", "VV"), by_key)
        self.assertEqual(
            by_key[("읽", "VV")]["match_type"], "predicate_stem_exact_pos"
        )
        self.assertNotEqual(
            by_key[("저", "NNG")]["candidate_group_id"],
            by_key[("저", "NP")]["candidate_group_id"],
        )
        priority = {
            r["dict_pron_candidate_id"]: r["member_priority"] for r in members
        }
        self.assertEqual(priority["travel-attested"], "preferred")
        self.assertEqual(priority["travel-fallback"], "retained_fallback")
        self.assertEqual(
            manifest["counts"]["unindexed_missing_surface_or_pos"], 1
        )

    def test_preflight_does_not_create_outputs(self) -> None:
        self.write_fixture()
        report = match.build(self.args(preflight_only=True))
        self.assertEqual(report["status"], "preflight_passed")
        self.assertFalse(self.output.exists())

    def test_resolution_keeps_multiple_pronunciations_unresolved(self) -> None:
        self.assertEqual(
            match.resolution_status(
                preferred_candidate_count=3,
                preferred_pronunciation_count=2,
            ),
            "multiple_pronunciations_unresolved",
        )


if __name__ == "__main__":
    unittest.main()

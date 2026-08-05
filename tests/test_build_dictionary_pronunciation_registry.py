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

import build_dictionary_pronunciation_registry as registry  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


ENRICHED_FIELDS = sorted(registry.ENRICHED_REQUIRED)
LEGACY_FIELDS = sorted(registry.LEGACY_REQUIRED)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def enriched_row(**values: str) -> dict[str, str]:
    row = {field: "" for field in ENRICHED_FIELDS}
    row.update(values)
    return row


class DictionaryPronunciationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.enriched = self.root / "enriched.csv"
        self.legacy = self.root / "legacy.csv"
        self.audit = self.root / "audit.json"
        self.output = self.root / "output"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_fixture(self) -> None:
        direct = enriched_row(
            word="읽다",
            word_stem="읽다",
            pos_full="동사",
            pos_tag="VV",
            pos_group="V",
            sense_no="001",
            urimal_id="100",
            stdict_target_code="T100",
            stdict_sense_code="S100",
            pron_1="익따",
            pron_1_roman="iktta",
            pron_1_roman_mfa="I k _ TT A",
            pron_2="일따",
            pron_2_roman="iltta",
            pron_2_roman_mfa="I l _ TT A",
        )
        fallback = enriched_row(
            word="가상어",
            word_stem="가상어",
            pos_full="명사",
            pos_tag="NNG",
            pos_group="NNG",
            sense_no="001",
            urimal_id="200",
        )
        # Exact duplicate source records collapse by semantic candidate ID.
        write_csv(self.enriched, ENRICHED_FIELDS, [direct, direct, fallback])
        write_csv(
            self.legacy,
            LEGACY_FIELDS,
            [
                {
                    "urimal_id": "200",
                    "pron_g2p": "가상어",
                    "pron_g2p_roman": "gasangeo",
                }
            ],
        )
        payload = {
            "status": "success",
            "sources": {
                "enriched": file_fingerprint(self.enriched, with_sha256=True),
                "legacy": file_fingerprint(self.legacy, with_sha256=True),
            },
            "enriched": {
                "rows_with_pron_1": 2,
                "rows_with_pron_2": 2,
            },
        }
        self.audit.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def args(self, *, preflight_only: bool = False):
        return registry.argparse.Namespace(
            enriched=self.enriched,
            legacy=self.legacy,
            source_audit=self.audit,
            output_dir=self.output,
            progress_every=0,
            preflight_only=preflight_only,
        )

    def test_build_preserves_attested_variants_and_labels_fallback(self) -> None:
        self.write_fixture()
        manifest = registry.build_registry(self.args())
        path = self.output / "dictionary_pronunciation_registry.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))

        self.assertEqual(len(rows), 3)
        by_field = {row["source_field"]: row for row in rows}
        self.assertEqual(by_field["pron_1"]["pron_hangul"], "익따")
        self.assertEqual(by_field["pron_1"]["is_primary"], "true")
        self.assertEqual(by_field["pron_2"]["is_alternative"], "true")
        self.assertEqual(by_field["pron_2"]["pron_roman_mfa"], "I l _ TT A")
        self.assertEqual(by_field["pron_g2p"]["is_dictionary_attested"], "false")
        self.assertEqual(by_field["pron_g2p"]["is_machine_generated"], "true")
        self.assertEqual(by_field["pron_g2p"]["source_match_mode"], "urimal_id_fallback")
        self.assertEqual(manifest["counts"]["duplicate_candidates_removed"], 2)
        self.assertFalse(manifest["interpretation"]["mfa_dictionary_activation"])

    def test_preflight_does_not_create_output(self) -> None:
        self.write_fixture()
        report = registry.build_registry(self.args(preflight_only=True))
        self.assertEqual(report["status"], "preflight_passed")
        self.assertFalse(self.output.exists())

    def test_changed_source_is_rejected(self) -> None:
        self.write_fixture()
        with self.enriched.open("a", encoding="utf-8") as stream:
            stream.write("changed\n")
        with self.assertRaisesRegex(RuntimeError, "감사 후 변경"):
            registry.build_registry(self.args(preflight_only=True))


if __name__ == "__main__":
    unittest.main()

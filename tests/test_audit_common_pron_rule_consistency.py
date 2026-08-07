from __future__ import annotations

import csv
import gzip
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import audit_common_pron_rule_consistency as audit  # noqa: E402


class CommonPronRuleConsistencyAuditTest(unittest.TestCase):
    def test_rule_sensitive_mismatch_and_match_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vocabulary = root / "vocabulary.csv"
            with vocabulary.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(audit.VOCAB_FIELDS)
                writer.writerow(["가", "1", "10", "1", "10", "0", "0", "0", "0", "0"])
                writer.writerow(["없음", "2", "5", "1", "0", "0", "5", "0", "0", "0"])
                writer.writerow(["있는", "2", "20", "1", "0", "0", "20", "0", "0", "0"])

            g2p = root / "g2p.csv"
            with g2p.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(audit.G2P_FIELDS)
                writer.writerow(["없음", "5", "1", "0", "0", "5", "0", "0", "0", "ʌ p̚ s͈ ɨ m", "g2p"])
                writer.writerow(["있는", "20", "1", "0", "0", "20", "0", "0", "0", "i s͈ n ɨ n", "g2p"])

            base = root / "base.dict"
            base.write_text("가\t0.99\t0.2\t1.0\t1.0\tk ɐ\n", encoding="utf-8")

            acoustic = root / "acoustic.zip"
            groups = {
                "0": ["k"], "1": ["m"], "2": ["n"], "5": ["p̚"],
                "6": ["s͈"], "7": ["t̚"], "8": ["tɕ͈"],
                "15": ["i"], "18": ["ɐ"], "20": ["ɨ"], "21": ["ʌ"],
            }
            phones = [phone for values in groups.values() for phone in values]
            with zipfile.ZipFile(acoustic, "w") as archive:
                archive.writestr(
                    "model/meta.json",
                    json.dumps({"phones": phones, "phone_groups": groups}),
                )

            registry = root / "registry.csv.gz"
            fields = sorted(audit.REGISTRY_REQUIRED)
            with gzip.open(registry, "wt", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                for headword, pron, roman in (
                    ("가", "가", "G A"),
                    ("없음", "업씀", "EO p _ SS EU m"),
                    ("있는", "인는", "I n _ N EU n"),
                ):
                    writer.writerow(
                        {
                            "headword": headword,
                            "pron_hangul": pron,
                            "pron_roman_search": roman,
                            "source_name": "dictionary",
                            "source_field": "pron_1",
                            "is_dictionary_attested": "true",
                            "is_machine_generated": "false",
                        }
                    )

            output = root / "audit.csv.gz"
            top = root / "top.csv"
            manifest = root / "manifest.json"
            result = audit.build_audit(
                vocabulary=vocabulary,
                g2p_cache=g2p,
                base_dictionary=base,
                acoustic_model=acoustic,
                dictionary_registry=registry,
                output_csv_gz=output,
                top_csv=top,
                manifest_path=manifest,
                top_n=10,
                progress_every=0,
            )

            with gzip.open(output, "rt", encoding="utf-8-sig", newline="") as stream:
                rows = {row["token"]: row for row in csv.DictReader(stream)}
            self.assertEqual(rows["가"]["comparison_status"], "matches_surface_rule")
            self.assertEqual(rows["없음"]["comparison_status"], "matches_surface_rule")
            self.assertEqual(rows["있는"]["comparison_status"], "mismatch_rule_sensitive")
            self.assertEqual(rows["있는"]["surface_rule_names"], "neutralize|nasal_assim")
            self.assertEqual(rows["있는"]["rule_pron_hangul"], "인는")
            self.assertEqual(rows["있는"]["rule_matches_dictionary"], "true")
            self.assertEqual(
                result["counts_by_status_types"]["mismatch_rule_sensitive"], 1
            )
            with top.open("r", encoding="utf-8-sig", newline="") as stream:
                top_rows = list(csv.DictReader(stream))
            self.assertEqual([row["token"] for row in top_rows], ["있는"])


if __name__ == "__main__":
    unittest.main()

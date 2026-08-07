from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from prepare_common_pron_r3_g2p_targets import build_targets  # noqa: E402
from resolve_common_pron_r3_surface_donors import (  # noqa: E402
    OUTPUT_FIELDS,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class R3G2pTargetPrepareTests(unittest.TestCase):
    def test_aggregates_shared_rule_target_and_skips_donor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "candidates.csv.gz"
            rows = []
            for token, target, status, candidate, occurrences in (
                ("갔다", "갇따", "candidate_replace_rule_dictionary_agree", "none", "10"),
                ("같다", "갇따", "review_rule_sensitive_no_attested_agreement", "none", "20"),
                ("갖다", "갇따", "review_rule_sensitive_no_attested_agreement", "surface_donor_exact_rule", "30"),
            ):
                row = {field: "" for field in OUTPUT_FIELDS}
                row.update(
                    {
                        "token": token,
                        "total_occurrences": occurrences,
                        "rule_pron_hangul": target,
                        "rule_pron_roman": "G A t _ TT A",
                        "selected_variant_count": "0",
                        "candidate_status": candidate,
                        "selection_status": status,
                    }
                )
                rows.append(row)
            with gzip.open(
                source, "wt", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            source_manifest = root / "source_manifest.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "common_pron_r3_surface_donor_candidates.v1",
                        "status": "success_candidates_not_selected",
                        "outputs": {
                            "candidate_inventory": {
                                "path": str(source),
                                "sha256": sha(source),
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            model = root / "g2p.zip"
            graphemes = sorted(set("갇따"))
            with zipfile.ZipFile(model, "w") as archive:
                archive.writestr(
                    "model/meta.json",
                    json.dumps(
                        {
                            "architecture": "test",
                            "version": "test",
                            "unicode_decomposition": False,
                            "graphemes": graphemes,
                            "phones": ["k", "a", "t"],
                        }
                    ),
                )
            output = root / "out"
            manifest = build_targets(
                candidate_inventory=source,
                candidate_manifest=source_manifest,
                g2p_model=model,
                output_root=output,
                shard_size=100,
            )
            self.assertEqual(manifest["counts"]["unique_targets"], 1)
            self.assertEqual(manifest["counts"]["source_candidate_types"], 2)
            self.assertEqual(manifest["counts"]["total_occurrences"], 30)
            shard = output / "input_shards" / "g2p_target_00001.txt"
            self.assertEqual(shard.read_text(encoding="utf-8").strip(), "갇따")
            with gzip.open(
                output / "g2p_rule_targets.csv.gz",
                "rt",
                encoding="utf-8-sig",
                newline="",
            ) as stream:
                result = list(csv.DictReader(stream))
            self.assertEqual(result[0]["source_type_count"], "2")
            self.assertEqual(result[0]["total_occurrences"], "30")


if __name__ == "__main__":
    unittest.main()

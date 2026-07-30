import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_mfa_year_phone_inventory as inventory  # noqa: E402
from pipeline_common import file_fingerprint  # noqa: E402


class YearPhoneInventoryTests(unittest.TestCase):
    def fixture(self, root: Path) -> dict[str, Path]:
        db = root / "2020.db"
        connection = sqlite3.connect(db)
        connection.executescript(
            "CREATE TABLE phone(id INTEGER, phone TEXT);"
            "CREATE TABLE phone_interval("
            "id INTEGER, utterance_id INTEGER, begin REAL, end REAL, "
            "phone_id INTEGER);"
        )
        connection.executemany(
            "INSERT INTO phone VALUES(?, ?)",
            [(1, "k"), (2, "a"), (3, "spn")],
        )
        connection.executemany(
            "INSERT INTO phone_interval VALUES(?, 1, ?, ?, ?)",
            [(1, 0.0, 0.5, 1), (2, 0.5, 1.0, 2)],
        )
        connection.commit()
        connection.close()

        allowed = inventory.phone_contract({"k", "a", "spn"})
        common = root / "common.json"
        common.write_text(
            json.dumps(
                {
                    "schema_version": inventory.COMMON_SCHEMA_VERSION,
                    "status": "success",
                    "phone_inventory_contract": allowed,
                }
            ),
            encoding="utf-8",
        )
        common_record = file_fingerprint(common, with_sha256=True)
        contract = root / "contract.json"
        contract.write_text(
            json.dumps(
                {
                    "schema_version": inventory.ALIGNMENT_SCHEMA_VERSION,
                    "status": "passed",
                    "year": "2020",
                    "alignment_contract_id": "align-2020",
                    "pronunciation_mode": "common_pronunciation",
                    "common_pron_manifest": common_record,
                }
            ),
            encoding="utf-8",
        )
        return {"db": db, "common": common, "contract": contract}

    def test_observed_subset_of_allowed_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            report = inventory.build_year_phone_inventory(
                db_path=paths["db"],
                year="2020",
                common_manifest_path=paths["common"],
                alignment_contract_path=paths["contract"],
            )
            self.assertEqual(report["status"], "success")
            self.assertEqual(
                report["observed_phone_inventory"]["phones"],
                ["a", "k"],
            )
            self.assertEqual(report["outside_allowed_inventory"], [])

    def test_spn_interval_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp))
            connection = sqlite3.connect(paths["db"])
            connection.execute(
                "INSERT INTO phone_interval VALUES(3, 1, 1, 1.2, 3)"
            )
            connection.commit()
            connection.close()
            report = inventory.build_year_phone_inventory(
                db_path=paths["db"],
                year="2020",
                common_manifest_path=paths["common"],
                alignment_contract_path=paths["contract"],
            )
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["spn_intervals"], 1)


if __name__ == "__main__":
    unittest.main()

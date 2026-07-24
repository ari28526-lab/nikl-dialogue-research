import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

import preflight_search_master as preflight  # noqa: E402


def write_metadata(path: Path, ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file_id"])
        writer.writeheader()
        writer.writerows({"file_id": item} for item in ids)


class SearchPreflightTests(unittest.TestCase):
    def test_session_metadata_coverage_requires_exact_unique_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            year = root / "raw" / "2023"
            year.mkdir(parents=True)
            (year / "A.csv").write_text("utt_id\n", encoding="utf-8")
            (year / "B.csv").write_text("utt_id\n", encoding="utf-8")
            (year / "_speakers.csv").write_text("id\n", encoding="utf-8")
            metadata = root / "file_meta.csv"

            write_metadata(metadata, ["A", "B"])
            self.assertTrue(
                preflight.check_session_id_coverage(root / "raw", metadata)
            )

            write_metadata(metadata, ["A", "A"])
            self.assertFalse(
                preflight.check_session_id_coverage(root / "raw", metadata)
            )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "scripts" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import build_research_companion_parquet as module


class _FakeArrow:
    @staticmethod
    def string():
        return "string"

    @staticmethod
    def int64():
        return "int64"

    @staticmethod
    def float64():
        return "float64"

    @staticmethod
    def bool_():
        return "bool"


class ParquetContractTests(unittest.TestCase):
    def test_all_frozen_dtypes_have_arrow_mapping(self) -> None:
        for name in ("string", "int64", "float64", "bool"):
            self.assertEqual(module._arrow_type(_FakeArrow, name), name)

    def test_unknown_dtype_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unsupported companion dtype"):
            module._arrow_type(_FakeArrow, "decimal")


if __name__ == "__main__":
    unittest.main()

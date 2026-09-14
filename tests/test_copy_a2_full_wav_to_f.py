from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "python"
    / "copy_a2_full_wav_to_f.py"
)


def load_module():
    script_dir = str(SCRIPT.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("copy_a2_full_wav_to_f", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class A2FullWavTests(unittest.TestCase):
    def test_groups_cover_canonical_years_and_recovered_2020(self):
        module = load_module()
        rows = module.groups()
        self.assertEqual(
            [row["year"] for row in rows[:6]],
            ["2020", "2021", "2022", "2023", "2024", "2025"],
        )
        self.assertEqual(rows[-1]["name"], "analysis_resolved_2020")
        self.assertEqual(len({row["name"] for row in rows}), 7)

    def test_select_evenly_has_stable_endpoints(self):
        module = load_module()
        items = [Path(str(index)) for index in range(10)]
        selected = module.select_evenly(items, 4)
        self.assertEqual(selected[0], items[0])
        self.assertEqual(selected[-1], items[-1])
        self.assertEqual(len(selected), 4)


if __name__ == "__main__":
    unittest.main()

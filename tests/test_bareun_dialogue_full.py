import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPT_DIR))

from bareun_dialogue_full import count_morphs  # noqa: E402


class BareunDialogueFullTests(unittest.TestCase):
    def test_count_morphs_does_not_count_literal_plus_surface(self):
        self.assertEqual(count_morphs("같/VA+아요/EF+.+/SW"), 3)
        self.assertEqual(count_morphs("가/VV+아/EC 나/NP+는/JX"), 4)


if __name__ == "__main__":
    unittest.main()

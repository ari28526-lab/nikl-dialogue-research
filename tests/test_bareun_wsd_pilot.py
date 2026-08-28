from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "python" / "run_bareun_wsd_pilot.py"
SPEC = importlib.util.spec_from_file_location("bareun_wsd_pilot", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BareunWsdPilotTest(unittest.TestCase):
    def test_deterministic_positions_cover_edges(self) -> None:
        self.assertEqual(MODULE.deterministic_positions(10), [0, 3, 6, 9])
        self.assertEqual(MODULE.deterministic_positions(4), [0, 1, 2, 3])

    def test_year_from_name(self) -> None:
        self.assertEqual(MODULE.year_from_name("NIKL_DIALOGUE_2024_v1.0"), "2024")
        with self.assertRaises(ValueError):
            MODULE.year_from_name("unknown")

    def test_safe_output_must_be_new_child_of_configured_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            configured = base / "external" / "run"
            config = {
                "output": {"root": str(configured)},
                "protected_roots": [str(base / "protected")],
            }
            MODULE.ensure_safe_output(config, configured / "pilot")
            with self.assertRaises(RuntimeError):
                MODULE.ensure_safe_output(config, base / "elsewhere")
            with self.assertRaises(RuntimeError):
                MODULE.ensure_safe_output(
                    {
                        "output": {"root": str(base)},
                        "protected_roots": [str(base / "protected")],
                    },
                    base / "protected" / "pilot",
                )

    def test_legacy_batch_path_is_used_when_cardinality_matches(self) -> None:
        class Result:
            def __init__(self, sentences):
                self.sentences = sentences

            def msg(self):
                return self

        class Tagger:
            def __init__(self):
                self.tags_calls = 0
                self.tag_calls = 0

            def tags(self, texts, **kwargs):
                self.tags_calls += 1
                self.kwargs = kwargs
                return Result([object() for _ in texts])

            def tag(self, text, **kwargs):
                self.tag_calls += 1
                return Result([object()])

        tagger = Tagger()
        sentences, stats = MODULE.analyze_batch(tagger, ["가", "나"])
        self.assertEqual(len(sentences), 2)
        self.assertEqual(tagger.tags_calls, 1)
        self.assertEqual(tagger.tag_calls, 0)
        self.assertTrue(tagger.kwargs["with_sense"])
        self.assertFalse(tagger.kwargs["auto_split"])
        self.assertEqual(stats["single_fallbacks"], 0)

    def test_cardinality_mismatch_falls_back_to_ordered_singles(self) -> None:
        class Result:
            def __init__(self, sentences):
                self.sentences = sentences

            def msg(self):
                return self

        class Tagger:
            def __init__(self):
                self.tags_calls = 0
                self.tag_calls = 0

            def tags(self, texts, **kwargs):
                self.tags_calls += 1
                return Result([object()])

            def tag(self, text, **kwargs):
                self.tag_calls += 1
                return Result([text])

        tagger = Tagger()
        sentences, stats = MODULE.analyze_batch(
            tagger, ["가", "나"], max_retries=1
        )
        self.assertEqual(sentences, ["가", "나"])
        self.assertEqual(tagger.tags_calls, 1)
        self.assertEqual(tagger.tag_calls, 2)
        self.assertEqual(stats["single_fallbacks"], 2)


if __name__ == "__main__":
    unittest.main()

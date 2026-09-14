from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "python" / "run_wsd_scope_inventory.py"
SPEC = importlib.util.spec_from_file_location("wsd_scope_inventory", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def morph(pos="NNG", surface="말", token="말은", token_index=0, morph_index=0):
    return {
        "utt_id": "U1",
        "token_index": str(token_index),
        "morph_index": str(morph_index),
        "token_surface": token,
        "morph_surface": surface,
        "pos": pos,
    }


class WsdScopeInventoryTest(unittest.TestCase):
    def classify(self, row, rows=None, mono=None, direct=None, mismatch=None, donors=None):
        return MODULE.classify_occurrence(
            row,
            rows or [row],
            mono or {},
            direct or {},
            mismatch or set(),
            donors or {},
            ("J", "E", "S"),
            2,
        )

    def test_not_target_is_pos_based(self):
        row = morph(pos="JKS")
        self.assertEqual(self.classify(row)["scope_status"], "not_target")

    def test_monosemous_requires_unique_trusted_sense(self):
        row = morph()
        result = self.classify(row, mono={("말", "NNG"): {"1"}})
        self.assertEqual(result["scope_status"], "monosemous_candidate")
        self.assertEqual(result["sense_id"], "1")

    def test_direct_gold_is_exact_coordinate(self):
        row = morph()
        direct = {("U1", 0, 0): {"2"}}
        result = self.classify(row, direct=direct)
        self.assertEqual(result["scope_status"], "local_gold_candidate")
        self.assertEqual(result["sense_id"], "2")

    def test_unanimous_context_donor(self):
        row = morph()
        key = MODULE.context_key([row], row, 2)
        donors = {key: {"3": {"D1", "D2"}}}
        result = self.classify(row, donors=donors)
        self.assertEqual(result["scope_status"], "exact_context_donor_candidate")
        self.assertEqual(result["donor_count"], 2)

    def test_conflicting_evidence_is_not_guessed(self):
        row = morph()
        direct = {("U1", 0, 0): {"2"}}
        result = self.classify(row, mono={("말", "NNG"): {"1"}}, direct=direct)
        self.assertEqual(result["scope_status"], "conflict")
        self.assertEqual(result["sense_id"], "")
        self.assertEqual(set(result["candidates"].split("|")), {"1", "2"})

    def test_missing_evidence_stays_unresolved(self):
        row = morph()
        self.assertEqual(self.classify(row)["scope_status"], "unresolved_api_candidate")

    def test_context_key_marks_sentence_boundaries(self):
        row = morph()
        key = MODULE.context_key([row], row, 2)
        self.assertEqual(key[-5:], ("<BOS>", "<BOS>", "말은", "<EOS>", "<EOS>"))

    def test_b5_terminal_null_pid_is_not_a_crash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state.json"
            lock = root / "lock.json"
            state.write_text(
                json.dumps({"status": "failed_safe_to_review", "pid": None,
                            "errors": [{"message": "access denied"}]}),
                encoding="utf-8",
            )
            config = {"b5_gate": {"state": str(state), "lock": str(lock)}}
            ready, errors, detail = MODULE.b5_gate(config)
            self.assertTrue(ready)
            self.assertEqual(errors, [])
            self.assertEqual(detail["pid"], -1)


if __name__ == "__main__":
    unittest.main()

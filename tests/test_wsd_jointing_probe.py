from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from probe_wsd_conversation_jointing import budget,PROBE_OPTIONS
from run_wsd_conversation_pilot import atomic


class ProbeTests(unittest.TestCase):
    def test_only_jointing_option_changes(self):
        from run_wsd_conversation_pilot import OPTIONS
        self.assertEqual([k for k in OPTIONS if OPTIONS[k]!=PROBE_OPTIONS[k]],['auto_jointing'])
        self.assertTrue(PROBE_OPTIONS['with_sense'])

    def test_combined_budget_counts_baseline_and_probe(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            probe=base/'probe'
            (base/'whole').mkdir()
            (probe/'job').mkdir(parents=True)
            atomic(base/'whole/attempt_1.intent.json',dict(chars=100))
            atomic(probe/'job/INTENT.json',dict(binding=dict(request_chars=200)))
            self.assertEqual(budget(base,probe,1),(2,300))
            with patch('probe_wsd_conversation_jointing.MAX_CALLS',2):
                with self.assertRaises(ValueError): budget(base,probe,1)


if __name__=='__main__': unittest.main()

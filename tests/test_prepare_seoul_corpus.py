import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]/'scripts/python/prepare_seoul_corpus.py'
spec = importlib.util.spec_from_file_location('seoul', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class SeoulParserTests(unittest.TestCase):
    def sample(self, declared=1):
        return '\n'.join(f'''item [{i}]:
class = "IntervalTier"
name = "{name}"
intervals: size = {declared}
intervals [1]:
xmin = 0
xmax = 1.5e+0
text = "그는 ""네""라고 했다"
''' for i,name in enumerate(m.NAMES,1))

    def test_unicode_duplicate_names_quotes_and_exponent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.TextGrid'
            p.write_text(self.sample(),encoding='utf-16')
            tiers,_=m.parse(p)
            self.assertEqual(tiers[4]['intervals'][0]['text'],'그는 "네"라고 했다')
            self.assertEqual(tiers[1]['name'],tiers[2]['name'])
            self.assertEqual(tiers[1]['tier_index'],2)
            self.assertEqual(tiers[2]['tier_index'],3)
            self.assertEqual(tiers[6]['intervals'][0]['end'],1.5)

    def test_missing_interval_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.TextGrid';p.write_text(self.sample(2),encoding='utf-8')
            with self.assertRaises(AssertionError):m.parse(p)

    def test_labels_are_not_silently_dropped(self):
        self.assertEqual(m.input_status('<IVER>'),'non_speech_marker')
        self.assertEqual(m.input_status('말 <NOISE> 말'),'mixed_marker_hold')
        self.assertEqual(m.input_status(''),'empty')
        self.assertEqual(m.input_status('네'),'ready')
        self.assertEqual(m.input_status('\ufffd'),'encoding_hold')

if __name__=='__main__':unittest.main()

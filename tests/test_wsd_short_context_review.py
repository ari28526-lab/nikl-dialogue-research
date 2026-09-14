from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/python'))
from review_wsd_short_context import compare_exact


def row(begin=0, end=1, form='가', pos='VV', number=1, probability=0.9):
    return dict(begin_in_utterance=begin, end_in_utterance=end, surface=form, pos=pos,
                sense=dict(sense_no=number, urimal_target_id=123, probability=probability))


class ReviewTests(unittest.TestCase):
    def test_probability_is_not_identity_change(self):
        out = compare_exact([row()], [row(probability=0.8)])
        self.assertEqual(out['sense_identity_changes'], 0)
        self.assertEqual(out['sense_metadata_only_changes'], 1)

    def test_true_identity_change(self):
        self.assertEqual(compare_exact([row()], [row(number=2)])['sense_identity_changes'], 1)

    def test_split_and_pos_change_not_forced(self):
        out = compare_exact([row(end=2)], [row(), row(begin=1, end=2)])
        self.assertEqual(out['unique_exact_matches'], 0)
        self.assertEqual(compare_exact([row()], [row(pos='NNG')])['unique_exact_matches'], 0)

    def test_duplicate_anchor_held(self):
        out = compare_exact([row(), row()], [row()])
        self.assertEqual(out['unique_exact_matches'], 0)
        self.assertEqual(out['left_unmatched'], 2)


if __name__ == '__main__':
    unittest.main()

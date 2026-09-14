"""Behavioral tests for all-utterance context packing and mapping."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
from prepare_wsd_conversation_plan import pack, mapping_rows, audit_windows, ordered_rows


def rows(texts):
    return [dict(utt_id=f'CONV.1.{i}', source_row_index=str(i), speaker_id=str(i % 2), form=t)
            for i, t in enumerate(texts, 1)]


class ConversationPlanTests(unittest.TestCase):
    def test_all_rows_have_one_core_with_overlap(self):
        data = rows(['abc', 'def', 'ghi', 'jkl', 'mno'])
        windows = pack(data, 7, 15)
        audit_windows(data, windows)
        self.assertEqual(len(windows), 3)
        self.assertTrue(any(m['role'] == 'context' for w in windows for m in mapping_rows(data, w)))

    def test_utf32_korean_emoji_and_newlines(self):
        data = rows(['한😀\n글', ' 둘 ', '\r\n셋'])
        win = pack(data, 100, 100)[0]
        audit_windows(data, [win])
        maps = mapping_rows(data, win)
        self.assertEqual(maps[0]['end_utf32'], 4)
        self.assertEqual(maps[1]['begin_utf32'], 5)
        self.assertEqual(maps[2]['line_separator_replacements'], 2)

    def test_oversize_preserved_and_held(self):
        data = rows(['a' * 20, 'ok'])
        windows = pack(data, 5, 10)
        self.assertEqual(windows[0]['status'], 'hold_oversize_utterance')
        audit_windows(data, windows)

    def test_empty_rows_preserved(self):
        data = rows(['', ' ', ''])
        windows = pack(data, 10, 10)
        self.assertEqual(windows[0]['status'], 'hold_empty_text')
        audit_windows(data, windows)

    def test_duplicate_id_rejected(self):
        data = rows(['a', 'b'])
        data[1]['utt_id'] = data[0]['utt_id']
        with self.assertRaises(ValueError):
            ordered_rows(data, 'CONV')

    def test_foreign_conversation_rejected(self):
        with self.assertRaises(ValueError):
            ordered_rows(rows(['x']), 'OTHER')

    def test_numeric_source_order_not_lexical_id(self):
        data = rows(['a', 'b', 'c'])
        data[1]['utt_id'] = 'CONV.1.10'
        self.assertEqual(ordered_rows(data, 'CONV'), data)
        with self.assertRaises(ValueError):
            ordered_rows(list(reversed(data)), 'CONV')

    def test_auditor_rejects_missing_or_duplicate_core(self):
        data = rows(['abc', 'def', 'ghi'])
        windows = pack(data, 3, 7)
        for changed in (windows[:-1], windows + windows[:1]):
            with self.assertRaises(ValueError):
                audit_windows(data, changed)

    def test_auditor_rejects_hash_tampering(self):
        data = rows(['abc'])
        windows = copy.deepcopy(pack(data))
        windows[0]['request_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            audit_windows(data, windows)

    def test_context_not_silently_truncated(self):
        data = rows(['a' * 10, 'b' * 10])
        windows = pack(data, 10, 10)
        self.assertTrue(windows[0]['right_context_omitted'])
        self.assertTrue(windows[1]['left_context_omitted'])


if __name__ == '__main__':
    unittest.main()

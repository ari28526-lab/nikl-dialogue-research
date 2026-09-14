from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from prepare_wsd_short_production import make_record,source_year
from audit_wsd_short_production import check_record


class ShortPlanTests(unittest.TestCase):
    def record(self,forms):
        rows=[dict(utt_id=f'C.{i}',source_row_index=str(i+1),speaker_id=str(i%2),form=s)
              for i,s in enumerate(forms)]
        result=make_record(rows,'C',dict(relative='files/NIKL_DIALOGUE_2020_v1.4/C/RECEIPT.json'))
        check_record(result,rows)
        return result

    def test_real_collection_year_labels(self):
        for y in range(2020,2026):
            self.assertEqual(source_year(f'files/NIKL_DIALOGUE_{y}_v1.0_JSON/C/RECEIPT.json'),str(y))
        with self.assertRaises(ValueError):source_year('files/unknown/C/RECEIPT.json')

    def test_short_and_long_zero_drop(self):
        r=self.record(['abc','x'*401,'def','x'*220,'abc'])
        self.assertEqual(r['counts']['utterances'],5)
        self.assertEqual(r['counts']['hold_oversize_utterance_utterances'],1)
        self.assertEqual(r['counts']['planned_utterances'],4)
        self.assertEqual(r['max_utterance_chars'],401)
        self.assertEqual(sum(w['core_end']-w['core_start'] for w in r['windows']),5)

    def test_empty_text_is_preserved(self):
        r=self.record(['',' '])
        self.assertEqual(r['counts']['hold_empty_text_utterances'],2)
        self.assertEqual(r['counts']['utterance_chars_0'],1)

    def test_source_identity_and_context(self):
        r=self.record(['a'*100]*6)
        self.assertEqual(r['year'],'2020')
        self.assertTrue(all(w['request_chars']<=400 for w in r['windows']))
        self.assertEqual(r['windows'][0]['context_end'],3)
        self.assertTrue(all(len(w['mapping_sha256'])==64 for w in r['windows']))

    def test_exact_400_limit_and_normalization(self):
        r=self.record(['x'*400,'a\nb'])
        self.assertEqual(r['counts']['planned_utterances'],2)
        self.assertEqual(r['counts']['input_chars'],403)


if __name__=='__main__':unittest.main()

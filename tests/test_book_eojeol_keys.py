import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from book_eojeol_keys import keys

class KeysTest(unittest.TestCase):
    def test_comma_variants_merge(self):
        self.assertEqual(keys('사람은','사람/NNG + 은/JX')['key'],keys('사람은,','사람/NNG + 은/JX + ,/SP')['key'])
    def test_sentence_functions_distinct(self):
        self.assertEqual(len({keys('사람'+s,'사람/NNG'+(' + '+s+'/SF' if s else ''))['key'] for s in ['', '.', '?', '!']}),4)
    def test_repeated_question_same_function(self):
        self.assertEqual(keys('사람?','사람/NNG + ?/SF')['key'],keys('사람??','사람/NNG + ??/SF')['key'])
    def test_ellipsis_not_declarative(self):
        self.assertNotEqual(keys('사람.','사람/NNG + ./SF')['key'],keys('사람...','사람/NNG + .../SE')['key'])
    def test_native_competition_same_lookup_not_same_decision(self):
        a,b=keys('배','배__01/NNG'),keys('배,','배__02/NNG + ,/SP')
        self.assertEqual(a['key'],b['key']);self.assertNotEqual(a['body'],b['body'])
    def test_numbers_only_template(self):
        a,b=keys('1차','1/SN + 차__01/NNG'),keys('2차','2/SN + 차__01/NNG')
        self.assertNotEqual(a['key'],b['key']);self.assertEqual(a['numeric_key'],b['numeric_key'])
    def test_number_unit_and_decimal_distinct(self):
        a=keys('1차','1/SN + 차/NNG')['numeric_key']
        self.assertNotEqual(a,keys('1년','1/SN + 년/NNB')['numeric_key'])
        self.assertNotEqual(a,keys('1.5차','1.5/SN + 차/NNG')['numeric_key'])
    def test_internal_symbol_and_particle_preserved(self):
        self.assertNotEqual(keys('사람','사람/NNG')['key'],keys('사람은','사람/NNG + 은/JX')['key'])
        self.assertNotEqual(keys('남녀','남/NNG + 녀/NNG')['key'],keys('남/녀','남/NNG + //SP + 녀/NNG')['key'])
    def test_quote_preserved_and_styles_match(self):
        a=keys('“사람”','“/SS + 사람/NNG + ”/SS')['key']
        self.assertEqual(a,keys('"사람"','"/SS + 사람/NNG + "/SS')['key'])
        self.assertNotEqual(a,keys('사람','사람/NNG')['key'])
    def test_alignment_hold(self):
        self.assertEqual(keys('사람','사람/NNG + ,/SP')['state'],'edge_alignment_hold')
    def test_lexical_digits_not_erased(self):
        self.assertNotEqual(keys('제1차','제1차/NNG')['key'],keys('제2차','제2차/NNG')['key'])
        self.assertIsNone(keys('제1차','제1차/NNG')['numeric_key'])
    def test_unknown_symbol_retained(self):
        self.assertNotEqual(keys('사람+','사람/NNG + +/SW')['key'],keys('사람','사람/NNG')['key'])

if __name__=='__main__': unittest.main()

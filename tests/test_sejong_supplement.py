import hashlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_sejong_supplement as s
from sejong_supplement import Supplement
from build_sejong_context_patterns import context_keys
from build_sejong_definition_bridge import identifier

class SejongTests(unittest.TestCase):
    def test_number_and_special_preserved(self):
        x=s.morphology('세계__02/NNG + 간__x16/NNG + 을/JKO')
        self.assertEqual(x,[('세계','NNG','02'),('간','NNG','x16'),('을','JKO','')])
        self.assertEqual(s.kind('x16'),'special_native_code')
        self.assertEqual(s.kind('88'),'special_native_code')
        self.assertEqual(s.kind('^03'),'special_native_code')
    def test_no_frequency_completion(self):
        self.assertEqual(s.kind(''),'unannotated')
        self.assertEqual(s.kind('02'),'native_number')
    def test_jamo_compatibility(self):
        self.assertEqual(s.shape(s.morphology('가/VV + ᆫ/ETM')),s.shape(s.morphology('가/VV + ㄴ/ETM')))
    def test_shape_keeps_particles_and_position(self):
        self.assertNotEqual(s.shape(s.morphology('배__01/NNG + 를/JKO')),s.shape(s.morphology('배__02/NNG + 에/JKB')))
        self.assertEqual(s.shape(s.morphology('배__01/NNG')),s.shape(s.morphology('배__02/NNG')))
    def test_literal_slash(self):self.assertEqual(s.morphology('//SP'),[('/','SP','')])
    def test_identifier_is_lossless_not_float_rounding(self):
        self.assertEqual(identifier('449431.0'),'449431')
        self.assertEqual(identifier('0002.000'),'2')
        self.assertEqual(identifier('9007199254740993.0'),'9007199254740993')
        self.assertIsNone(identifier('2.5'));self.assertIsNone(identifier('nan'))
    def test_context_includes_neighbor_and_particle(self):
        words=[s.morphology('큰/VA'),s.morphology('배__01/NNG + 를/JKO'),s.morphology('타/VV')]
        keys=context_keys(words,1,0)
        self.assertEqual(len(keys),3)
        other=[*words[:2],s.morphology('먹/VV')]
        self.assertNotEqual(keys[1][0],context_keys(other,1,0)[1][0])
        self.assertEqual(keys[0][0],context_keys(other,1,0)[0][0])
    def test_context_cannot_cross_missing_word(self):
        words=[[],s.morphology('배__01/NNG')]
        self.assertEqual(context_keys(words,1,0),[])
    def test_invalid_analysis(self):
        with self.assertRaises(ValueError):s.morphology('bad')
    def test_blocks_do_not_cross_markup(self):
        x=list(s.blocks('<p>\nBSAA0001-00001\ta\ta/NNG\n</p>\n<p>\nBSAA0001-00002\tb\tb/NNG\n</p>'))
        self.assertEqual(len(x),2)
    def fixture(self,td,total='3'):
        p=Path(td)/'05.txt';p.write_text('형태소 어절\t타입: [1]\t토큰: [3]\n\n1\t배 : '+total+'\n\t배__01/NNG\t2\t66.67\n\t배__02/NNG\t1\t33.33\n',encoding='cp949')
        p.with_suffix('.txt.receipt.json').write_text(json.dumps({'status':'verified','bytes':p.stat().st_size,'sha256':s.sha(p)}),encoding='utf-8')
        return p
    def test_competing_variants_retained_and_resume(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.fixture(td);c=sqlite3.connect(':memory:');c.executescript(s.SCHEMA)
            s.book_eojeols(c,p);s.book_eojeols(c,p)
            self.assertEqual(c.execute('SELECT COUNT(*),SUM(frequency) FROM variants').fetchone(),(2,3))
    def test_failed_unit_rolls_back(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.fixture(td,total='invalid');c=sqlite3.connect(':memory:');c.executescript(s.SCHEMA)
            with self.assertRaises(ValueError):s.book_eojeols(c,p)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM variants').fetchone()[0],0)
    def test_original_source_discrepancy_retained(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.fixture(td,total='4');c=sqlite3.connect(':memory:');c.executescript(s.SCHEMA);s.book_eojeols(c,p)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM issues').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT SUM(frequency) FROM variants').fetchone()[0],3)
    def test_tampered_input(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.fixture(td);p.write_bytes(p.read_bytes()+b'X')
            with self.assertRaises(ValueError):s.verified(p)
    def test_lookup_never_uses_majority_as_completion(self):
        with tempfile.TemporaryDirectory() as td:
            p=self.fixture(td);c=sqlite3.connect(':memory:');c.executescript(s.SCHEMA);s.book_eojeols(c,p)
            x=Supplement.__new__(Supplement);x.c=c
            r=x.word('배','배','NNG')
            self.assertEqual(r['native_codes'],['01','02']);self.assertIsNone(r['selected_group'])
            self.assertFalse(r['single_observed_regular_native_code'])
    def test_mapping_keeps_definitions_without_certifying_number(self):
        c=sqlite3.connect(':memory:');c.executescript(s.SCHEMA)
        c.execute('INSERT INTO crosswalk VALUES(?,?,?,?,?,?,?,?,?,?,?)',('배','명사','03','1','2','9','definition_high',1.0,'설명','설명','historical_number_unverified_candidate'))
        x=Supplement.__new__(Supplement);x.c=c;r=x.mapping('배','NNG','01')
        self.assertEqual(len(r),1);self.assertFalse(r[0]['historical_number_matches']);self.assertFalse(r[0]['historical_mapping_verified'])
        self.assertEqual(r[0]['urimal_definition'],'설명')

if __name__=='__main__':unittest.main()

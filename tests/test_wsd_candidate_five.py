import argparse,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'python'))
import build_wsd_candidate_five as b

class CandidateTests(unittest.TestCase):
    def test_book_numbers_never_rank_modern_groups(self):
        x=b.rank_groups(['100','200'],{'donors':[],'book':[{'native_frequency':{'100':999999}}]})
        self.assertTrue(all(c['rank_status']=='unranked_display_only' for c in x['candidates']))
        self.assertIsNone(x['selected_group']);self.assertFalse(x['wsd_completed'])

    def test_tied_groups_preserved_beyond_five(self):
        x=b.rank_groups([str(i) for i in range(9)],{'donors':[]})
        self.assertEqual(len(x['candidates']),5);self.assertEqual(len(x['all_candidate_groups']),9)
        self.assertTrue(x['boundary_tie']);self.assertEqual(x['omitted_group_count'],4)

    def test_source_frequencies_are_not_pooled(self):
        ds=[{'source':s,'group_id':'a','frequency':n} for s,n in [('LS',3),('ML',999)]]
        x=b.rank_groups(['a','b'],{'donors':ds})['candidates'][0]
        self.assertEqual(x['source_rank_score'],2);self.assertEqual(x['source_frequencies']['LS']['frequency'],3)
        self.assertNotIn('frequency',x)

    def test_repeated_lemma_target_is_held(self):
        k=b.keys('가가',[('가','NNG',''),('가','NNG','')]);self.assertIsNone(b.position(k,'가','NNG'))

    def test_donor_restart_and_duplicate_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=sqlite3.connect(root/'sample.sqlite')
            src.executescript('CREATE TABLE occurrences(id INTEGER,sentence_id INTEGER,lemma TEXT,pos TEXT,native_code TEXT,word_id_json TEXT,alignment TEXT,word_pattern TEXT);CREATE TABLE sentences(id INTEGER,raw BLOB);')
            src.execute('INSERT INTO sentences VALUES(?,?)',(1,b.pack({'word':[{'id':1,'form':'사람,'}]})))
            pattern=json.dumps([['사람','NNG'],[',','SP']],ensure_ascii=False)
            src.executemany('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?)',[(1,1,'사람','NNG','001','1','unique_native_form_pos_match',pattern),(2,1,'사람','NNG','888','1','unique_native_form_pos_match',pattern),(3,1,'사람','NNG','001','1','multiple_native_matches',pattern)])
            src.commit();src.close();dic=sqlite3.connect(root/'sample.dictionary.sqlite')
            dic.execute('CREATE TABLE bindings(lemma TEXT,pos TEXT,native_code TEXT,state TEXT,groups_json TEXT)')
            dic.execute('INSERT INTO bindings VALUES(?,?,?,?,?)',('사람','NNG','001','snapshot_code_match_candidate','["100"]'));dic.commit();dic.close()
            c=sqlite3.connect(root/'output.sqlite');b.schema(c)
            args=argparse.Namespace(output=root,max_batches=1)
            with patch.object(b,'BASE',root),patch.object(b,'SOURCES',['sample']),patch.object(b.shutil,'disk_usage',return_value=type('D',(),{'free':100*2**30})()):
                self.assertFalse(b.build_donors(c,args));args.max_batches=0
                self.assertTrue(b.build_donors(c,args));self.assertTrue(b.build_donors(c,args))
            self.assertEqual(c.execute('SELECT SUM(n) FROM donors').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT group_id FROM donors WHERE native="888"').fetchone()[0],'')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM donor_issues').fetchone()[0],1)
            c.close()

    def test_transaction_rollback_preserves_source_boundary(self):
        c=sqlite3.connect(':memory:');b.schema(c)
        row=('1:0:0',1,None,'no_same_eojeol_evidence',b.pack({'target_id':'1:0:0'}))
        with self.assertRaises(RuntimeError):
            with c:b.commit_source(c,1,[row],0,.1);raise RuntimeError('power_loss')
        self.assertEqual(c.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],0)
        with c:b.commit_source(c,1,[row],0,.1)
        self.assertEqual(c.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],1)
        self.assertEqual(c.execute('SELECT targets FROM done').fetchone()[0],1)

if __name__=='__main__':unittest.main()

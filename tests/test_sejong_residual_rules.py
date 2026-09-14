import sys,unittest,tempfile,sqlite3,json,hashlib,contextlib,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from apply_sejong_residual import classify,words_for,pack
from sejong_context_rules import RULES,guard,decide
import apply_sejong_residual as application

class Rules(unittest.TestCase):
    def test_no_frequency_completion(self):
        self.assertEqual(classify([]),'no_adjacent_context_match')
    def test_rival_and_special_preserved(self):
        p={'native_distribution':{'01':999,'02':1},'source_files':20,'observations':1000}
        self.assertEqual(classify([p]),'context_native_conflict')
        p['native_distribution']={'01':999,'':1}
        self.assertEqual(classify([p]),'unannotated_or_special_evidence')
    def ability(self,left,right):
        return {'condition':['v','both',1,0,[left,[['수','NNB']],right]],'hash':'test','native_distribution':{'02':50},'source_files':10,'observations':50}
    def test_ability_requires_two_sides(self):
        rule=next(r for r in RULES if r[0]=='ability')
        self.assertTrue(guard(rule,self.ability([['하','VV'],['ㄹ','ETM']],[['없','VA']])) )
        self.assertFalse(guard(rule,self.ability([['한','MM']],[['없','VA']])) )
        self.assertFalse(guard(rule,self.ability([['하','VV'],['ㄹ','ETM']],[['두','VV']])) )
    def test_decision_guards(self):
        p=self.ability([['하','VV'],['ㄹ','ETM']],[['없','VA']])
        x={'lemma':'수','pos':'NNB','candidate_groups':['540667','other'],'category':'context_supported_definition_pending','prior_status':'context_hold','form':'할 수 없다','patterns':[p]}
        self.assertIsNotNone(decide(x,lambda p:[1,2]))
        self.assertIsNone(decide(x,lambda p:[1]))
        x['prior_status']='context_conflict';self.assertIsNone(decide(x,lambda p:[1,2]))
        x['prior_status']='context_hold';x['candidate_groups']=['other'];self.assertIsNone(decide(x,lambda p:[1,2]))
    def test_mapping_anchor_duplicate(self):
        r={'raw_bareun':{'token_index':'0','morph_index':'0','morph_surface':'수','pos':'NNB'}}
        self.assertRaises(ValueError,words_for,[(0,pack(r)),(1,pack(r))])

class DurableApplication(unittest.TestCase):
    def test_real_transactions_stop_resume_and_target_tamper(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ready=root/'ready';sup=root/'sup';app=root/'src';out=root/'out'
            for p in [ready,sup,app,out]:p.mkdir()
            p=sqlite3.connect(sup/'CONTEXT_PATTERNS.sqlite');p.execute('CREATE TABLE observations(hash BLOB,native_code TEXT,occurrences INT,source_id INT,first_segment INT,last_segment INT)');p.commit();p.close()
            p=sqlite3.connect(sup/'SUPPLEMENT.sqlite');p.execute('CREATE TABLE dummy(x)');p.commit();p.close()
            for fn,rp in [('SUPPLEMENT.sqlite','FINAL_MANIFEST.json'),('CONTEXT_PATTERNS.sqlite','CONTEXT_PATTERNS.receipt.json')]:
                (sup/rp).write_text(json.dumps({'database_sha256':application.sha(sup/fn)}))
            (sup/'RELEASE.json').write_text('{}')
            r=sqlite3.connect(ready/'WSD_READY.sqlite');r.executescript('CREATE TABLE sources(source_index INT,receipt_relative TEXT,database_sha256 TEXT,receipt_sha256 TEXT); CREATE TABLE contexts(source_index INT,analysis_ordinal INT,json_ordinal INT,document_id TEXT,utt_id TEXT,form TEXT,raw_bareun BLOB); CREATE TABLE targets(source_index INT,utterance_ordinal INT,row_ordinal INT,lemma TEXT,pos TEXT,candidate_groups TEXT,payload BLOB);')
            for sid in [0,1]:
                raw={'token_index':'0','morph_index':'0','morph_surface':'수','pos':'NNB','token_surface':'수','token_begin_utf32':'0','token_length_utf32':'1','utt_id':str(sid)}
                blob=pack({'raw_bareun':raw,'dictionary_decision':{'status':'context_hold'}})
                d=app/str(sid);d.mkdir();s=sqlite3.connect(d/'APPLICATION.sqlite');s.execute('CREATE TABLE morphemes(utterance_ordinal INT,row_ordinal INT,payload BLOB)');s.execute('INSERT INTO morphemes VALUES(0,0,?)',(blob,));s.commit();s.close();(d/'RECEIPT.json').write_text('{}')
                r.execute('INSERT INTO sources VALUES(?,?,?,?)',(sid,str(sid)+'/RECEIPT.json',application.sha(d/'APPLICATION.sqlite'),application.sha(d/'RECEIPT.json')))
                r.execute('INSERT INTO contexts VALUES(?,0,0,?,?,?,?)',(sid,'d'+str(sid),str(sid),'수',pack({'response_text':'수'})))
                r.execute('INSERT INTO targets VALUES(?,0,0,?,?,?,?)',(sid,'수','NNB','["a","b"]',blob))
            r.commit();r.close();(ready/'FINAL_MANIFEST.json').write_text(json.dumps({'database_bytes':(ready/'WSD_READY.sqlite').stat().st_size,'database_sha256':application.sha(ready/'WSD_READY.sqlite')}))
            a=SimpleNamespace(output=out,max_sources=1,preflight=False)
            with patch.multiple(application,READY=ready,SUP=sup,APP=app),contextlib.redirect_stdout(io.StringIO()):
                (out/'STOP').write_text('stop');application.scan(a)
                self.assertEqual(json.loads((out/'STATE.json').read_text())['targets'],0)
                (out/'STOP').unlink();application.scan(a)
                self.assertEqual(json.loads((out/'STATE.json').read_text())['targets'],1)
                application.scan(a)
                self.assertEqual(json.loads((out/'STATE.json').read_text())['targets'],2)
                application.scan(a)
                c=sqlite3.connect(out/'APPLICATION.sqlite');self.assertEqual(c.execute('SELECT COUNT(*) FROM results').fetchone()[0],2);c.close()
                # Fresh output must fail if a target payload no longer matches
                # the source morphology, even though the source SHA is valid.
                r=sqlite3.connect(ready/'WSD_READY.sqlite');r.execute('UPDATE targets SET payload=? WHERE source_index=0',(pack({'raw_bareun':dict(raw,utt_id='0',pos='VV'),'dictionary_decision':{'status':'context_hold'}}),));r.commit();r.close()
                a.output=root/'tamper'
                with self.assertRaisesRegex(ValueError,'target_payload_correspondence'):application.scan(a)
if __name__=='__main__':unittest.main()

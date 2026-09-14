"""Crash/replay and coverage checks; no API, raw input, or release mutation."""
import csv,gzip,json,os,sqlite3,subprocess,sys,tempfile,unittest
from contextlib import closing
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/python'))
import apply_context_dictionary_full as app

class FakeDictionary:
    lex=None
    complete=True
    def close(self):pass
    units={}
    def __init__(self):self.calls=0
    def decide(self,v,m,previous):
        self.calls+=1
        return {'status':'context_hold','selected_group':None,'previous':[x.raw['id'] for x in previous],'ordinal':v.ordinal}

def fixture(root):
    src=root/'input';src.mkdir();name='year/source.csv';us=[];ms=[]
    for i in range(7):
        rows=0 if i==3 else 2
        us.append(dict(source_file=name,utt_id='u'+str(i),speaker_id='p',form='말은',response_morph_count=str(rows)))
        for k in range(rows):
            ms.append(dict(source_file=name,utt_id='u'+str(i),token_index='0',morph_index=str(k),token_surface='말은',token_begin_utf32='0',token_length_utf32='2',morph_surface='말' if k==0 else '은',pos='NNG' if k==0 else 'JX'))
    for fn,rows in [('utterances.csv.gz',us),('morphemes.csv.gz',ms)]:
        with gzip.open(src/fn,'wt',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    receipt={'source_file':name,'counts':{'utterances':len(us),'morphemes':len(ms)},'outputs':{fn:{'sha256':app.sha(src/fn),'bytes':(src/fn).stat().st_size} for fn in ['utterances.csv.gz','morphemes.csv.gz']}}
    app.atomic_json(src/'RECEIPT.json',receipt)
    ref={'source_file':name,'receipt_sha256':app.sha(src/'RECEIPT.json')}
    raw={'document':[{'id':'d1','utterance':[{'id':u['utt_id'],'form':u['form']} for u in us[:4]]+[{'id':'empty','form':''}]},{'id':'d2','utterance':[{'id':u['utt_id'],'form':u['form']} for u in us[4:]]}]}
    jp=root/'source.json';app.atomic_json(jp,raw)
    ref['json_binding']={'json_sha256':app.sha(jp),'json_relative':'source.json','json_utterances':8}
    app.atomic_json(root/'ref.json',ref)
    return src,ref,jp

def logical(db):
    with closing(sqlite3.connect(db)) as c:
        return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in ['utterances','morphemes','json_alignment','meta']}

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/context_dictionary_application_20260906/tests';parent.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.tmp.name)
        assert self.root.resolve().is_relative_to(parent.resolve())
        self.src,self.ref,self.jp=fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def apply(self,name='output',**kw):
        return app.apply_one(self.src,self.root/name,self.ref,'contract',FakeDictionary(),checkpoint=2,json_path=self.jp,**kw)
    def test_all_rows_raw_and_document_context(self):
        r,_=self.apply();self.assertEqual((r['counts']['utterances'],r['counts']['morphemes'],r['counts']['json_utterances']),(7,12,8))
        c=sqlite3.connect(self.root/'output/APPLICATION.sqlite')
        self.assertEqual(c.execute("SELECT analysis_ordinal,status FROM json_alignment WHERE utt_id='empty'").fetchone(),(None,'empty_JSON_utterance_preserved'))
        d={i:app.unpacked(p)['dictionary_decision'] for i,p in c.execute("SELECT utterance_ordinal,payload FROM morphemes WHERE pos='NNG'")}
        self.assertEqual(d[4]['previous'],[]);self.assertEqual(d[4]['ordinal'],5)
        self.assertEqual(d[6]['previous'],['u4','u5']);self.assertEqual(d[2]['previous'],['u0','u1'])
        self.assertEqual(c.execute('SELECT COUNT(*) FROM utterances WHERE morphemes=0').fetchone()[0],1);c.close()
    def test_hard_process_death_mid_transaction_and_after_commit(self):
        self.apply('baseline')
        for mode in ['row','committed']:
            command=[sys.executable,'-B',__file__,'crash',str(self.root),mode]
            p=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(p.returncode,91,p.stderr)
            partial=self.root/mode/'APPLICATION.building.sqlite'
            with closing(sqlite3.connect(partial)) as c:self.assertEqual(app.unit_counts(c)['utterances'],2)
            self.apply(mode)
            self.assertEqual(logical(self.root/'baseline/APPLICATION.sqlite'),logical(self.root/mode/'APPLICATION.sqlite'))
    def test_graceful_stop_resume(self):
        n=[0]
        def stop():n[0]+=1;return n[0]==4
        with self.assertRaises(app.StopRequested):self.apply(stop=stop)
        with closing(sqlite3.connect(self.root/'output/APPLICATION.building.sqlite')) as c:self.assertEqual(app.unit_counts(c)['utterances'],2)
        self.apply();self.apply('baseline')
        self.assertEqual(logical(self.root/'baseline/APPLICATION.sqlite'),logical(self.root/'output/APPLICATION.sqlite'))
    def test_completed_file_skips_decisions(self):
        self.apply();d=FakeDictionary()
        _,skipped=app.apply_one(self.src,self.root/'output',self.ref,'contract',d,json_path=self.jp)
        self.assertTrue(skipped);self.assertEqual(d.calls,0)
    def test_rename_before_receipt_recovers(self):
        self.apply();rp=self.root/'output/RECEIPT.json';rp.rename(rp.with_suffix('.saved'))
        _,skipped=self.apply();self.assertTrue(skipped);self.assertTrue(rp.exists())
    def test_changed_input_refused(self):
        self.apply()
        with (self.src/'utterances.csv.gz').open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'source data changed'):self.apply()
    def test_changed_json_refused(self):
        self.apply();self.jp.write_text('{}')
        with self.assertRaisesRegex(ValueError,'original JSON changed'):self.apply()
    def test_changed_contract_refused(self):
        with self.assertRaises(app.StopRequested):self.apply(stop=lambda:True)
        with self.assertRaisesRegex(ValueError,'contract changed'):app.apply_one(self.src,self.root/'output',self.ref,'different',FakeDictionary(),json_path=self.jp)
    def test_output_corruption_refused(self):
        self.apply()
        with (self.root/'output/APPLICATION.sqlite').open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'completed output changed'):self.apply()
    def test_os_lock_cross_process(self):
        lock=self.root/'RUN.lock'
        with app.RunLock(lock):
            p=subprocess.run([sys.executable,'-B',__file__,'lock',str(lock)],capture_output=True)
            self.assertEqual(p.returncode,92,p.stderr)
        with app.RunLock(lock):pass
    def test_path_escape_refused(self):
        with self.assertRaises(ValueError):app.path_under(self.root,'../escape')
    def test_cache_is_bounded_and_exact(self):
        c=sqlite3.connect(':memory:');c.execute('CREATE TABLE patterns(hash TEXT,group_id TEXT,label_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER)')
        c.execute("INSERT INTO patterns VALUES('a','g','label',3,2,1,2)")
        sql='SELECT group_id,label_kind,occurrences,documents,first_target,last_target FROM patterns WHERE hash=?'
        q=app.QueryCache(c,2)
        for h in ['a','b','a','c','a']:self.assertEqual(q.execute(sql,(h,)).fetchall(),c.execute(sql,(h,)).fetchall());self.assertLessEqual(len(q.items),2)
        q.close()
    def test_global_manifest_resume_and_contract_guard(self):
        cfg={'output_root':str(self.root/'production'),'input_root':str(self.root),'json_root':str(self.root),'minimum_free_gib':0,'checkpoint_utterances':2,'dictionary_cache_mib_per_source':1,'query_cache_entries_per_source':2,'expected_utterances':7,'expected_morphemes':12}
        refs=[{**self.ref,'relative':'input/RECEIPT.json'}];contract={'dictionary':{'release_manifest_sha256':'test'}}
        with patch.object(app,'Dictionary',FakeDictionary),patch('builtins.print'):
            app.run(cfg,refs,contract,resume=True)
            final=app.read(self.root/'production/FINAL_MANIFEST.json')
            self.assertEqual(final['status'],'complete');self.assertEqual(final['preserved_json_utterances'],8)
            self.assertEqual(len(final['output_receipts']),1)
            self.assertEqual(final['output_receipts'][0]['sha256'],app.sha(self.root/'production/input/RECEIPT.json'))
            app.run(cfg,refs,contract,resume=True)
            with self.assertRaisesRegex(ValueError,'달라졌습니다'):app.run(cfg,refs,{**contract,'changed':True},resume=True)
    def test_stale_running_status_uses_os_lock(self):
        app.atomic_json(self.root/'STATE.json',{'status':'running'})
        cfg={'output_root':str(self.root)}
        with patch('builtins.print'):
            self.assertEqual(app.status(cfg)['status'],'interrupted_resume_required')
            with app.RunLock(self.root/'RUN.lock'):self.assertTrue(app.status(cfg)['active_os_lock'])

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='crash':
        root=Path(sys.argv[2]);mode=sys.argv[3];ref=app.read(root/'ref.json')
        def kill(stage,ordinal,row):
            if (mode=='row' and stage=='row' and ordinal==3 and row==0) or (mode=='committed' and stage=='committed' and ordinal==1):os._exit(91)
        # u3 has no morphology, so crash in the first row of u2, after checkpoint u1.
        def hook(stage,ordinal,row):
            if mode=='row' and stage=='row' and ordinal==2 and row==0:os._exit(91)
            kill(stage,ordinal,row)
        app.apply_one(root/'input',root/mode,ref,'contract',FakeDictionary(),checkpoint=2,json_path=root/'source.json',hook=hook)
    elif len(sys.argv)>1 and sys.argv[1]=='lock':
        try:
            with app.RunLock(Path(sys.argv[2])):pass
        except app.BusyError:sys.exit(92)
    else:unittest.main()

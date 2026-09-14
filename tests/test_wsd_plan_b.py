"""Plan B failure-injection tests: no external calls or protected writes."""
import copy,json,os,sqlite3,subprocess,sys,tempfile,time,unittest,io,contextlib,datetime
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import wsd_b_plan as plan
import run_wsd_plan_b as run
from apply_context_dictionary_full import packed,unpacked,RunLock,BusyError

def fixture():
    c=sqlite3.connect(':memory:');c.execute('CREATE TABLE lexicon_keys(lemma TEXT,pos TEXT,entries_json TEXT)')
    c.execute('INSERT INTO lexicon_keys VALUES(?,?,?)',('배','NNG',json.dumps([{'target':'101','group':'G1'},{'target':'102','group':'G1'},{'target':'201','group':'G2'}])))
    form='배 배';r=dict(j=0,doc='D1',uid='u1',speaker='sp',form=form,raw=packed({'response_text':form}))
    ts=[]
    for i,b in enumerate([0,2]):
        raw=dict(utt_id='u1',token_surface='배',token_begin_utf32=str(b),token_length_utf32='1',morph_begin_utf32=str(b),morph_length_utf32='1',morph_surface='배',pos='NNG')
        ts.append(dict(id=f'0:0:{i}',sid=0,uo=0,ri=i,j=0,lemma='배',pos='NNG',groups=['G1','G2'],blob=packed({'raw_bareun':raw})))
    job=plan.make_job(0,0,[r],ts,(0,1,0,1))
    tokens=[dict(text={'begin_offset':b,'length':1,'content':'배'},morphemes=[dict(text={'begin_offset':b,'length':1,'content':'배'},tag='NNG',sense={'urimal_target_id':101 if b==0 else 201})]) for b in [0,2]]
    resp=dict(sentences=[dict(text={'begin_offset':0,'length':3,'content':form},tokens=tokens)])
    return c,[r],ts,job,resp

class PlanTests(unittest.TestCase):
    def test_repeated_lemma_exact_occurrence(self):
        c,rows,ts,j,r=fixture();d=plan.map_targets(c,j,r,ts,rows)
        self.assertEqual([v['selected_group'] for v in d],['G1','G2']);self.assertFalse(any(v['luna_eligible'] for v in d));c.close()
    def test_same_group_different_sense_finishes(self):
        c,rows,ts,j,r=fixture();r['sentences'][0]['tokens'][0]['morphemes'][0]['sense']['urimal_target_id']=102
        self.assertEqual(plan.map_targets(c,j,r,ts,rows)[0]['selected_group'],'G1');c.close()
    def test_no_sense_only_actual_hold_to_luna(self):
        c,rows,ts,j,r=fixture();del r['sentences'][0]['tokens'][0]['morphemes'][0]['sense']
        d=plan.map_targets(c,j,r,ts,rows);self.assertEqual(d[0]['status'],'group_hold');self.assertTrue(d[0]['luna_eligible']);c.close()
    def test_foreign_candidate_is_conflict(self):
        c,rows,ts,j,r=fixture();r['sentences'][0]['tokens'][0]['morphemes'][0]['sense']['urimal_target_id']=999
        d=plan.map_targets(c,j,r,ts,rows)[0];self.assertIsNone(d['selected_group']);self.assertEqual(d['status'],'group_conflict');c.close()
    def test_bad_geometry_never_luna(self):
        c,rows,ts,j,r=fixture();r['sentences'][0]['tokens'][0]['text']['begin_offset']=99
        d=plan.map_targets(c,j,r,ts,rows);self.assertTrue(all(x['status']=='mapping_hold' and not x['luna_eligible'] for x in d));c.close()
    def test_analysis_text_changed_holds(self):
        c,rows,ts,j,r=fixture();rows[0]['raw']=packed({'response_text':'배배'})
        self.assertTrue(all(x['status']=='mapping_hold' for x in plan.map_targets(c,j,r,ts,rows)));c.close()
    def test_duplicate_morph_never_inferred(self):
        c,rows,ts,j,r=fixture();tok=r['sentences'][0]['tokens'][0];tok['morphemes'].append(copy.deepcopy(tok['morphemes'][0]))
        self.assertEqual(plan.map_targets(c,j,r,ts,rows)[0]['status'],'mapping_hold');c.close()
    def test_targetless_trim_and_document_halo(self):
        rows=[dict(j=i,doc='a' if i<4 else 'b',uid=str(i),speaker='s',form='말',raw=None) for i in range(8)]
        ts=[dict(id=str(i),j=i) for i in [1,3,4,6]]
        iv=plan.intervals(rows,ts);self.assertEqual(iv,[(1,4,0,4),(4,7,4,8)])
        jobs=[plan.make_job(0,n,rows,ts,x) for n,x in enumerate(iv)]
        self.assertEqual([tid for j in jobs for tid in j['target_ids']],['1','3','4','6'])
        self.assertTrue(all(len({rows[m['json_ordinal']]['doc'] for m in j['mappings']})==1 for j in jobs))
    def test_long_utterance_never_truncated(self):
        rows=[dict(j=0,doc='d',uid='u',speaker='s',form='말'*500,raw=None)];ts=[dict(id='x',j=0)]
        self.assertEqual(len(plan.make_job(0,0,rows,ts,plan.intervals(rows,ts)[0])['text']),500)

class DurableTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.c=run.runtime(self.root);self.calls=0
    def tearDown(self):self.c.close();self.tmp.cleanup()
    def call(self,p):self.calls+=1;return {'sentences':[],'usage':{'input_tokens':10,'output_tokens':2}}
    def submit(self,hook=lambda x:None):return run.durable_call(self.c,'b:1:1','bareun',{'text':'a'},2,2,0,self.call,hook)
    def test_completed_response_reused_after_reopen(self):
        first=self.submit();self.c.close();self.c=run.runtime(self.root);run.recover(self.c)
        self.assertEqual(self.submit(),first);self.assertEqual(self.calls,1)
    def test_crash_before_send_never_retried(self):
        def hook(phase):
            if phase=='after_intent':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.submit(hook)
        run.recover(self.c);self.assertIsNone(self.submit());self.assertEqual(self.calls,0)
        self.assertEqual(run.usage(self.c)['reserved_or_consumed_credit_units'],2)
    def test_crash_after_provider_response_never_retried(self):
        def hook(phase):
            if phase=='after_response_before_save':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.submit(hook)
        run.recover(self.c);self.assertIsNone(self.submit());self.assertEqual(self.calls,1)
    def test_crash_after_durable_raw_is_recoverable(self):
        def hook(phase):
            if phase=='after_raw_saved':raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.submit(hook)
        run.recover(self.c);self.assertIsNotNone(self.submit());self.assertEqual(self.calls,1)
    def test_changed_request_fails(self):
        self.submit()
        with self.assertRaisesRegex(ValueError,'request_changed'):run.durable_call(self.c,'b:1:1','bareun',{'text':'b'},2,2,0,self.call)
    def test_tampered_response_fails(self):
        self.submit();self.c.execute("UPDATE attempts SET raw=?",(packed({'changed':True}),));self.c.commit()
        with self.assertRaisesRegex(ValueError,'sha_failed'):run.recover(self.c)
    def test_network_error_preserved_and_not_retried(self):
        def fail(p):self.calls+=1;raise TimeoutError()
        with self.assertRaises(RuntimeError):run.durable_call(self.c,'b:1:1','bareun',{'text':'a'},2,2,0,fail)
        self.assertIsNone(self.submit());self.assertEqual(self.calls,1)
    def test_os_lock_blocks_child_and_releases_after_termination(self):
        script="import sys,time;sys.path.insert(0,sys.argv[1]);from apply_context_dictionary_full import RunLock;from pathlib import Path\nwith RunLock(Path(sys.argv[2])):\n print('LOCKED',flush=True)\n time.sleep(30)"
        lock=self.root/'guard';child=subprocess.Popen([sys.executable,'-c',script,str(plan.ROOT/'scripts/python'),str(lock)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'LOCKED')
            with self.assertRaises(BusyError):
                with RunLock(lock):pass
        finally:child.terminate();child.wait(timeout=10);child.stdout.close()
        with RunLock(lock):pass
    def test_atomic_mapping_commit_no_duplicate_targets(self):
        source,rows,ts,j,r=fixture();run.durable_call(self.c,j['id'],'bareun',j,2,1,0,lambda p:r)
        run.map_commit(self.c,source,j,rows,ts,r)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],2)
        self.assertEqual(dict(self.c.execute('SELECT key,value FROM metrics'))['decision:bareun_group_resolved'],2)
        with self.assertRaises(sqlite3.IntegrityError):run.map_commit(self.c,source,j,rows,ts,r)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],2);source.close()
    def test_luna_reservation_survives_uncertainty(self):
        def fail(p):raise TimeoutError()
        with self.assertRaises(RuntimeError):run.durable_call(self.c,'l:b:1:1','luna',{},0,0,9000000000,fail)
        self.assertEqual(run.usage(self.c)['luna_reserved_nusd'],9000000000)
        self.assertTrue(run.luna_can_reserve(run.usage(self.c),1000000000,run.CAP_NUSD))
        self.assertFalse(run.luna_can_reserve(run.usage(self.c),1000000001,run.CAP_NUSD))
        with self.assertRaises(ValueError):run.luna_can_reserve(run.usage(self.c),1,run.CAP_NUSD+1)
    def test_luna_missing_usage_retains_entire_reservation(self):
        run.durable_call(self.c,'l:q','luna',{},0,0,10000,lambda p:{'status':'completed'})
        with self.assertRaises(ValueError):run.luna_commit(self.c,'l:q',{}, {'status':'completed'})
        self.assertEqual(run.usage(self.c)['luna_reserved_nusd'],10000)
    def test_luna_group_validation_and_usage(self):
        req={'request_id':'q','targets':[{'target_id':'t','candidate_groups':['G']}],'context':[{'utt_id':'u'}]}
        raw={'status':'completed','usage':{'input_tokens':10,'output_tokens':10},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'request_id':'q','decisions':[{'target_id':'t','selected_group':'G','evidence_utt_ids':['u'],'reason':'context'}]})}]}]}
        run.durable_call(self.c,'l:q','luna',{},0,0,100000,lambda p:raw);run.luna_commit(self.c,'l:q',req,raw)
        self.assertEqual(run.usage(self.c)['luna_reserved_nusd'],0);self.assertEqual(run.usage(self.c)['luna_charged_nusd'],14500)
    def test_luna_invalid_decisions_are_preserved_holds(self):
        req={'request_id':'q','targets':[{'target_id':'t','candidate_groups':['G']}],'context':[{'utt_id':'u'}]}
        raw={'status':'completed','usage':{'input_tokens':1,'output_tokens':1},'output':[]}
        run.durable_call(self.c,'l:q','luna',{},0,0,10000,lambda p:raw);run.luna_commit(self.c,'l:q',req,raw)
        self.assertEqual(self.c.execute('SELECT status FROM luna_decisions').fetchone()[0],'luna_response_hold')

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ready=self.root/'ready';self.ready.mkdir();self.out=self.root/'out';self.out.mkdir()
        source,rows,ts,j,r=fixture();source.close();self.response=r
        c=sqlite3.connect(self.ready/'WSD_READY.sqlite')
        c.executescript('CREATE TABLE contexts(source_index,json_ordinal,document_id,utt_id,speaker_id,form,raw_bareun);CREATE TABLE targets(source_index,utterance_ordinal,row_ordinal,json_ordinal,lemma,pos,candidate_groups,payload);CREATE TABLE lexicon_keys(lemma,pos,entries_json);')
        c.execute('INSERT INTO lexicon_keys VALUES(?,?,?)',('배','NNG',json.dumps([{'target':'101','group':'G1'},{'target':'201','group':'G2'}])))
        p=sqlite3.connect(self.out/'PLAN.sqlite');p.execute('CREATE TABLE requests(id,sid,number,payload,sha,words,targets)')
        for sid in range(2):
            c.execute('INSERT INTO contexts VALUES(?,?,?,?,?,?,?)',(sid,0,'D1','u1','sp','배 배',rows[0]['raw']))
            local=[]
            for t in ts:
                tt={**t,'sid':sid,'id':f'{sid}:0:{t["ri"]}'};local.append(tt)
                c.execute('INSERT INTO targets VALUES(?,?,?,?,?,?,?,?)',(sid,0,t['ri'],0,'배','NNG',json.dumps(['G1','G2']),t['blob']))
            job=plan.make_job(sid,0,rows,local,(0,1,0,1));p.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?)',(job['id'],sid,0,packed(job),run.digest(run.canonical(job)),2,2))
        c.commit();c.close();p.commit();p.close();(self.out/'PLAN_MANIFEST.json').write_text('{}')
        self.m={'plan_sha256':'test','counts':{'reused_targets':0,'targets':4,'new_targets':4,'transmitted_eojeol':4}}
        self.a={'valid_until':(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=1)).isoformat(),'wsd_eojeol_per_credit':1,'maximum_credit_units':10,'luna_cap_nusd':run.CAP_NUSD}
        self.calls=0
    def tearDown(self):self.tmp.cleanup()
    def invoke(self,call,resume=False,max_calls=50):
        with patch.object(run,'OUT',self.out),patch.object(run,'READY',self.ready),patch.object(run,'bareun_client',return_value=call),patch.object(run,'space_check'),patch.object(run,'awake',contextlib.nullcontext),patch.object(run,'stop_requested',side_effect=lambda:(self.out/'STOP.request').exists()),contextlib.redirect_stdout(io.StringIO()):
            return run.run(self.a,self.m,max_calls,'bareun',resume)
    def test_safe_stop_then_resume_without_resending(self):
        def call(job):
            self.calls+=1
            if self.calls==1:(self.out/'STOP.request').write_text('{}')
            return self.response
        first=self.invoke(call);self.assertEqual(first['status'],'paused_by_user');self.assertEqual(self.calls,1)
        last=self.invoke(call,resume=True);self.assertEqual(last['status'],'bareun_pass_complete');self.assertEqual(self.calls,2)
        self.assertEqual(last['bareun_mapped_targets'],4)
        self.invoke(call,resume=True);self.assertEqual(self.calls,2)
    def test_session_cap_retains_first_production_results(self):
        def call(job):self.calls+=1;return self.response
        first=self.invoke(call,max_calls=1);self.assertEqual(first['status'],'paused_session_limit')
        with patch.object(run,'OUT',self.out):
            quote=run.submission_preview(self.m,self.a,50)
            self.assertEqual((quote['next_new_calls'],quote['next_targets'],quote['next_transmitted_eojeol']),(1,2,2))
        last=self.invoke(call,resume=True,max_calls=1);self.assertEqual(self.calls,2);self.assertEqual(last['bareun_mapped_targets'],4)
    def test_quota_stop_before_next_call(self):
        self.a['maximum_credit_units']=2
        def call(job):self.calls+=1;return self.response
        state=self.invoke(call);self.assertEqual(state['status'],'paused_credit_cap');self.assertEqual(self.calls,1)
    def test_live_input_change_stops_before_next_call(self):
        def call(job):
            self.calls+=1;p=self.ready/'WSD_READY.sqlite';os.utime(p,ns=(time.time_ns(),time.time_ns()+2000000000));return self.response
        with self.assertRaisesRegex(ValueError,'frozen_input_changed'):self.invoke(call)
        self.assertEqual(self.calls,1)

if __name__=='__main__':unittest.main()

import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts/python'))
import run_seoul_bareun as m

def job(n):
    return dict(request_id=f'job{n}',source_file='s01m16f1',text='가다',text_sha256=str(n),eojeol=1,
        spans=[dict(utt_id=f'u{n}',start=0,end=2,time_start=1,time_end=2)])

RESPONSE=json.dumps(dict(sentences=[dict(tokens=[dict(text=dict(content='가다',beginOffset=0,length=2),
    morphemes=[dict(text=dict(content='가다',beginOffset=0,length=2),tag='VV',sense=dict(senseNo='1',urimalTargetId='test'))])])])).encode()

class RunnerTests(unittest.TestCase):
    def env(self,tmp):
        root=Path(tmp);plan=root/'plan';plan.mkdir();(plan/'REQUESTS.jsonl').write_text('test')
        return patch.multiple(m,OUT=root/'out',PLAN=plan,BASE=root)
    def test_resume_does_not_resend_completed(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            calls=[]
            def call(q,k):calls.append(q['request_id']);return RESPONSE
            a=m.execute([job(1),job(2)],'test',1,call)
            self.assertEqual(a['status'],'paused_request_limit')
            b=m.execute([job(1),job(2)],'test',0,call)
            self.assertEqual(b['status'],'completed');self.assertEqual(calls,['job1','job2'])
    def test_uncertain_timeout_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            calls=[]
            def call(q,k):calls.append(1);raise TimeoutError()
            m.execute([job(1)],'test',0,call)
            b=m.execute([job(1)],'test',0,call)
            self.assertEqual(b['status'],'paused_uncertain_request');self.assertEqual(len(calls),1)
    def test_cross_utterance_token_is_held(self):
        q=job(1);q['spans'][0]['end']=1
        r=m.project(q,json.loads(RESPONSE));self.assertIn('mapping_hold',r['errors'])
        self.assertEqual(r['rows'][0]['utt_id'],'')
    def add_hold(self,q):
        ip=m.OUT/'intents'/f"{q['request_id']}.json"
        m.save(ip,dict(request_id=q['request_id'],text_sha256=q['text_sha256'],eojeol=q['eojeol']))
        h={k:q[k] for k in ('request_id','text_sha256','eojeol','source_file','spans')}
        h.update(disposition='uncertain_no_retry',intent_sha256=m.sha(ip))
        m.save(m.OUT/'REVIEWED_UNCERTAIN_HOLDS.json',dict(holds=[h]))
        return ip
    def test_reviewed_hold_skipped_accounted_and_exported(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            ip=self.add_hold(job(1));before=m.sha(ip);calls=[]
            def call(q,k):calls.append(q['request_id']);return RESPONSE
            r=m.execute([job(1),job(2)],'test',0,call)
            self.assertEqual(calls,['job2']);self.assertEqual(m.sha(ip),before)
            self.assertEqual(r['status'],'completed_with_request_holds')
            self.assertEqual((r['completed_requests'],r['held_uncertain_requests'],r['attempted_eojeol']),(1,1,2))
            self.assertEqual(json.loads((m.OUT/'request_holds.json').read_text('utf-8'))[0]['utt_id'],'u1')
            self.assertEqual(m.execute([job(1),job(2)],'test',0,call)['completed_requests'],1)
            self.assertEqual(calls,['job2'])
    def test_changed_hold_intent_fails_before_api(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            ip=self.add_hold(job(1));ip.write_text('{}')
            with self.assertRaisesRegex(AssertionError,'held_intent_changed'):
                m.execute([job(1)],'test',0,lambda q,k:self.fail('unexpected API'))
    def test_unreviewed_timeout_still_stops_after_reviewed_hold(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            self.add_hold(job(1));calls=[]
            def call(q,k):calls.append(q['request_id']);raise TimeoutError()
            m.execute([job(1),job(2)],'test',0,call)
            r=m.execute([job(1),job(2)],'test',0,call)
            self.assertEqual(r['status'],'paused_uncertain_request');self.assertEqual(calls,['job2'])
    def test_provider_omission_is_explicitly_preserved(self):
        q=job(1);response=json.loads(RESPONSE);t=response['sentences'][0]['tokens'][0]
        t['text']['content']='가';t['text']['length']=1
        r=m.project(q,response)
        self.assertEqual(r['errors'],[])
        self.assertEqual(r['source_gaps'][0]['character'],'다')
        self.assertEqual(r['source_gaps'][0]['utt_id'],'u1')
    def test_stop_after_call_preserves_result(self):
        with tempfile.TemporaryDirectory() as tmp,self.env(tmp):
            calls=[]
            def call(q,k):calls.append(1);(m.OUT/'STOP').touch();return RESPONSE
            r=m.execute([job(1),job(2)],'test',0,call)
            self.assertEqual(r['status'],'paused_user_stop');self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()

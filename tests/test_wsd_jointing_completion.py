from collections import Counter
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_wsd_jointing_completion import run, inventory, request_ref, build_ledger
from run_wsd_conversation_pilot import make_jobs, canonical, digest, atomic, read_json
from connectrpc.code import Code
from connectrpc.errors import ConnectError


def fixture():
    rows=[dict(utt_id=f'C.{i}',source_row_index=str(i),speaker_id='S',form='abc '*12+'abc')
          for i in range(16)]
    jobs=[j for j in make_jobs(rows) if j['mode']=='split']
    contract=dict(reused={},max_attempts_per_job=2,max_new_calls=2*len(jobs),
                  max_new_chars=2*sum(len(j['text']) for j in jobs),session_seconds=3600,
                  retry_delay_seconds=0,consecutive_failed_jobs_stop=3,
                  requests=list(map(request_ref,jobs)))
    return rows,jobs,contract


def response(job):
    tokens=[]
    for m in job['mappings']:
        b,e=m['begin_utf32'],m['end_utf32']
        t=dict(begin_offset=b,length=e-b,content=job['text'][b:e])
        tokens.append(dict(text=copy.deepcopy(t),morphemes=[dict(text=copy.deepcopy(t),tag='NNG')]))
    return dict(sentences=[dict(text=dict(begin_offset=0,length=len(job['text']),content=job['text']),tokens=tokens)])


class CompletionTests(unittest.TestCase):
    def execute(self,root,rows,jobs,contract,call,reused=None,**kwargs):
        return run(root,rows,jobs,contract,reused or {},call,check_storage=lambda:None,
                   sleep=lambda _:None,**kwargs)

    def test_success_restart_no_duplicate_calls(self):
        rows,jobs,c=fixture()
        calls=[]
        def call(j): calls.append(j['id']); return response(j)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            a=self.execute(root,rows,jobs,c,call)
            self.assertEqual(a['statuses'],{'candidate_mapping_verified':len(rows)})
            b=self.execute(root,rows,jobs,c,call)
            self.assertEqual(a['new_calls'],b['new_calls'])
            self.assertEqual(len(calls),len(jobs))

    def test_retry_then_continue_after_exhausted_one_job(self):
        rows,jobs,c=fixture()
        calls=Counter()
        def call(j):
            calls[j['id']]+=1
            if j['id']==jobs[0]['id'] or (j['id']==jobs[1]['id'] and calls[j['id']]==1):
                raise ConnectError(Code.UNAVAILABLE,'synthetic')
            return response(j)
        with tempfile.TemporaryDirectory() as d:
            state=self.execute(Path(d),rows,jobs,c,call)
            self.assertEqual(state['status'],'completed_with_holds')
            self.assertGreater(state['statuses']['api_failed'],0)
            self.assertEqual(state['saved_requests'],len(jobs)-1)
            self.assertEqual(calls[jobs[0]['id']],2)
            self.assertEqual(calls[jobs[1]['id']],2)
            self.assertEqual(sum(state['statuses'].values()),len(rows))

    def test_three_failed_jobs_pause_not_infinite_retry(self):
        rows,jobs,c=fixture()
        def call(j): raise ConnectError(Code.DEADLINE_EXCEEDED,'synthetic')
        with tempfile.TemporaryDirectory() as d:
            state=self.execute(Path(d),rows,jobs,c,call)
            self.assertEqual(state['stop_reason'],'consecutive_api_failures')
            self.assertEqual(state['new_calls'],6)

    def test_non_retryable_error_pause_once(self):
        rows,jobs,c=fixture()
        def call(j): raise ConnectError(Code.UNAUTHENTICATED,'synthetic')
        with tempfile.TemporaryDirectory() as d:
            state=self.execute(Path(d),rows,jobs,c,call)
            self.assertEqual(state['stop_reason'],'non_retryable_api_error')
            self.assertEqual(state['new_calls'],1)

    def test_uncertain_intent_no_retry(self):
        rows,jobs,c=fixture()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=root/jobs[0]['id']; folder.mkdir()
            atomic(folder/'attempt_1.intent.json',dict(contract_sha256=digest(canonical(c)),
                                                       request=request_ref(jobs[0]),attempt=1))
            state=self.execute(root,rows,jobs,c,lambda j:self.fail('must not call'))
            self.assertEqual(state['stop_reason'],'uncertain_prior_transmission_no_auto_retry')

    def test_reuse_no_transmission_and_mapping_hold_continue(self):
        rows,jobs,c=fixture()
        reused={j['id']:response(j) for j in jobs}
        c['reused']={name:{} for name in reused}
        # Preserve a deliberately bad token extent without changing later jobs.
        reused[jobs[0]['id']]['sentences'][0]['tokens'][0]['morphemes'][0]['text']['length']+=1
        with tempfile.TemporaryDirectory() as d:
            state=self.execute(Path(d),rows,jobs,c,lambda j:self.fail('must not call'),reused)
            self.assertEqual(state['new_calls'],0)
            self.assertEqual(state['status'],'completed_with_holds')
            self.assertEqual(sum(state['statuses'].values()),len(rows))

    def test_budget_persists_and_tampering_fails(self):
        rows,jobs,c=fixture()
        c['max_new_calls']=1
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            state=self.execute(root,rows,jobs,c,response)
            self.assertEqual(state['new_calls'],1)
            self.assertEqual(state['stop_reason'],'persistent_budget_limit')
            state=self.execute(root,rows,jobs,c,lambda j:self.fail('budget must persist'))
            self.assertEqual(state['new_calls'],1)
            rp=root/jobs[0]['id']/'attempt_1.result.json'
            saved=read_json(rp); saved['response']['sentences']=[]; atomic(rp,saved)
            with self.assertRaises(ValueError): self.execute(root,rows,jobs,c,response)

    def test_time_limit_prevents_call(self):
        rows,jobs,c=fixture()
        ticks=iter([0,4000])
        with tempfile.TemporaryDirectory() as d:
            state=self.execute(Path(d),rows,jobs,c,lambda j:self.fail('no time remaining'),
                               monotonic=lambda:next(ticks))
            self.assertEqual(state['stop_reason'],'session_time_limit')
            self.assertEqual(state['new_calls'],0)

    def test_duplicate_core_rejected(self):
        rows,jobs,c=fixture()
        with self.assertRaises(ValueError): build_ledger(rows,jobs+[jobs[0]],{}, {})


if __name__=='__main__': unittest.main()

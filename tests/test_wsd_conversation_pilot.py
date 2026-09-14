import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_wsd_conversation_pilot import make_jobs,audit_jobs,summarize,obtain,inventory
from run_wsd_context_comparison import atomic
from connectrpc.code import Code
from connectrpc.errors import ConnectError


def rows():
    return [dict(utt_id=f'CONV.{i+1}',source_row_index=str(i+1),speaker_id=str(i%2),
                 form=('가나다😀'*12)+str(i)) for i in range(10)]


class ConversationTests(unittest.TestCase):
    def test_complete_core_coverage_with_both_context_edges(self):
        source=rows()
        jobs=make_jobs(source)
        audit_jobs(source,jobs)
        owners=[m['utt_id'] for j in jobs[1:] for m in j['mappings'] if m['role']=='core']
        self.assertEqual(owners,[r['utt_id'] for r in source])
        self.assertTrue(any(m['role']=='context' for j in jobs for m in j['mappings']))
        self.assertEqual(jobs[0]['max_attempts'],1)
        self.assertEqual(jobs[0]['timeout_ms'],600000)

    def test_duplicate_or_missing_core_rejected(self):
        source=rows()
        jobs=make_jobs(source)
        with self.assertRaises(ValueError): audit_jobs(source,jobs+jobs[1:2])
        with self.assertRaises(ValueError): audit_jobs(source,jobs[:-1])

    def test_oversize_utterance_not_silently_truncated(self):
        source=rows()
        source[0]['form']='가'*500
        with self.assertRaises(ValueError): make_jobs(source)

    def test_failed_owner_does_not_use_context_as_fallback(self):
        source=rows()
        jobs=make_jobs(source)
        report,ledger,merged=summarize(source,jobs,{}, {'whole':{'status':'failed'}})
        self.assertEqual(len(ledger),len(source))
        self.assertEqual(report['statuses'],{'api_missing':len(source)})
        self.assertFalse(report['split_mapping_passed'])
        self.assertFalse(merged)

    @patch('run_wsd_conversation_pilot.storage')
    def test_whole_no_retry_and_saved_result_reused(self,_):
        with tempfile.TemporaryDirectory() as directory:
            j=make_jobs(rows())[0]
            calls=[]
            def call(job):
                calls.append(job['id'])
                raise ConnectError(Code.UNAVAILABLE,'secret')
            for _ in range(2): obtain(Path(directory),j,'contract',call)
            self.assertEqual(calls,['whole'])

    @patch('run_wsd_conversation_pilot.storage')
    def test_split_retry_limited_and_result_reused(self,_):
        with tempfile.TemporaryDirectory() as directory:
            j=make_jobs(rows())[1]
            calls=[]
            def call(job):
                calls.append(job['id'])
                if len(calls)==1: raise ConnectError(Code.UNAVAILABLE,'secret')
                return {'sentences':[]}
            obtain(Path(directory),j,'contract',call,sleep=lambda _:None)
            obtain(Path(directory),j,'contract',call)
            self.assertEqual(len(calls),2)
            self.assertEqual(inventory(Path(directory))[0],2)

    def test_uncertain_call_preserved(self):
        from run_wsd_conversation_pilot import ref
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            j=make_jobs(rows())[0]
            (root/j['id']).mkdir()
            atomic(root/j['id']/'attempt_1.intent.json',dict(binding=dict(contract_sha256='c',job=ref(j)),chars=len(j['text'])))
            result,error=obtain(root,j,'c',lambda _:self.fail('no call allowed'))
            self.assertIsNone(result)
            self.assertEqual(error['status'],'uncertain_attempt_do_not_retry')

    @patch('run_wsd_conversation_pilot.MAX_CALLS',0)
    def test_budget_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            _,error=obtain(Path(directory),make_jobs(rows())[0],'c',lambda _:self.fail('no call allowed'))
            self.assertEqual(error['status'],'budget_stop')


if __name__=='__main__': unittest.main()

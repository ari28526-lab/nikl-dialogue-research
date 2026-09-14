from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from audit_wsd_jointing_completion import audit
from run_wsd_jointing_completion import run
from run_wsd_conversation_pilot import read_json,atomic
from test_wsd_jointing_completion import fixture,response
from connectrpc.code import Code
from connectrpc.errors import ConnectError


class CompletionAuditTests(unittest.TestCase):
    def execute(self,root,rows,jobs,c,call,reused=None):
        return run(root,rows,jobs,c,reused or {},call,check_storage=lambda:None,sleep=lambda _:None)

    def test_success_and_ledger_tampering(self):
        rows,jobs,c=fixture()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.execute(root,rows,jobs,c,response)
            result,_,_=audit(root,rows,jobs,c,{})
            self.assertTrue(result['integrity_passed'])
            self.assertTrue(result['all_source_mapping_verified'])
            self.assertFalse(result['semantic_quality_verified'])
            data=read_json(root/'UTTERANCE_LEDGER.json');data.pop();atomic(root/'UTTERANCE_LEDGER.json',data)
            with self.assertRaises(ValueError):audit(root,rows,jobs,c,{})

    def test_failed_one_job_stays_in_completed_ledger(self):
        rows,jobs,c=fixture()
        def call(j):
            if j['id']==jobs[0]['id']:raise ConnectError(Code.UNAVAILABLE,'synthetic')
            return response(j)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.execute(root,rows,jobs,c,call)
            result,_,_=audit(root,rows,jobs,c,{})
            self.assertTrue(result['integrity_passed'])
            self.assertFalse(result['all_api_responses_available'])
            self.assertEqual(result['new_calls'],len(jobs)+1)

    def test_reused_response_not_transmitted(self):
        rows,jobs,c=fixture()
        reused={jobs[0]['id']:response(jobs[0])}
        c['reused']={jobs[0]['id']:{}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.execute(root,rows,jobs,c,response,reused)
            result,_,_=audit(root,rows,jobs,c,reused)
            self.assertEqual(result['new_calls'],len(jobs)-1)
            self.assertEqual(result['reused_requests'],1)

    def test_orphan_artifact_and_paused_state_rejected(self):
        rows,jobs,c=fixture()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.execute(root,rows,jobs,c,response)
            atomic(root/jobs[0]['id']/'unexpected.json',{})
            with self.assertRaises(ValueError):audit(root,rows,jobs,c,{})
            state=read_json(root/'STATE.json');state['status']='paused';atomic(root/'STATE.json',state)
            with self.assertRaises(ValueError):audit(root,rows,jobs,c,{})


if __name__=='__main__':unittest.main()

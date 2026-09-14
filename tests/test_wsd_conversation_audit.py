import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_wsd_conversation_pilot import make_jobs,execute,atomic,read_json
from audit_wsd_conversation_pilot import audit


def source():
    return [dict(utt_id=f'C.{i}',source_row_index=str(i+1),speaker_id=str(i%2),form='가'*45) for i in range(10)]


def response(job):
    text=job['text']
    tokens=[]
    for mapping in job['mappings']:
        begin,end=mapping['begin_utf32'],mapping['end_utf32']
        t=dict(content=text[begin:end],begin_offset=begin,length=end-begin)
        tokens.append(dict(text=t,morphemes=[dict(text=t,tag='NNG')]))
    return dict(sentences=[dict(text=dict(content=text,begin_offset=0,length=len(text)),tokens=tokens)])


class AuditTests(unittest.TestCase):
    @patch('run_wsd_conversation_pilot.storage')
    def test_failed_whole_does_not_imply_dialogue_equivalence(self,_):
        from connectrpc.code import Code
        from connectrpc.errors import ConnectError
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=source()
            jobs=make_jobs(rows)
            def call(job):
                if job['id']=='whole': raise ConnectError(Code.UNAVAILABLE,'synthetic')
                return response(job)
            execute(root,rows,jobs,{},call)
            result=audit(root,rows,jobs,{})
            self.assertTrue(result['split_analysis_passed'])
            self.assertFalse(result['whole_response_available'])
            self.assertEqual(result['whole_vs_split']['compared_utterance_pairs'],0)
            self.assertFalse(result['production_ready'])

    @patch('run_wsd_conversation_pilot.storage')
    def test_complete_and_detect_ledger_tampering(self,_):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=source()
            jobs=make_jobs(rows)
            execute(root,rows,jobs,{},response)
            result=audit(root,rows,jobs,{})
            self.assertTrue(result['split_analysis_passed'])
            self.assertEqual(result['whole_vs_split']['compared_utterance_pairs'],10)
            self.assertGreater(result['overlap']['compared_utterance_pairs'],0)
            ledger=read_json(root/'UTTERANCE_LEDGER.json')
            ledger.pop()
            atomic(root/'UTTERANCE_LEDGER.json',ledger)
            with self.assertRaises(ValueError): audit(root,rows,jobs,{})

    @patch('run_wsd_conversation_pilot.storage')
    def test_detect_response_corruption(self,_):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            rows=source()
            jobs=make_jobs(rows)
            execute(root,rows,jobs,{},response)
            result=read_json(root/'whole/RESULT.json')
            result['response']['sentences']=[]
            atomic(root/'whole/RESULT.json',result)
            with self.assertRaises(ValueError): audit(root,rows,jobs,{})


if __name__=='__main__': unittest.main()

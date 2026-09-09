import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from wsd_candidate_response import validate

class Tests(unittest.TestCase):
    def setUp(self):
        self.request={'request_id':'0:0','context':[{'utt_id':'u1'}],'targets':[{'target_id':'0:0:0','candidate_groups':['1','2']},{'target_id':'0:1:0','candidate_groups':['4','5']}]}
        self.response={'request_id':'0:0','decisions':[{'target_id':'0:0:0','selected_group':'1','evidence_utt_ids':['u1'],'reason':'문맥 근거'},{'target_id':'0:1:0','selected_group':None,'evidence_utt_ids':[],'reason':'근거 부족'}]}
    def test_choice_and_abstention(self):
        r=validate(self.request,self.response);self.assertEqual(r['decisions'][1]['status'],'abstained');self.assertFalse(r['semantic_accuracy_validated'])
    def test_invented_group(self):
        self.response['decisions'][0]['selected_group']='999'
        with self.assertRaises(ValueError):validate(self.request,self.response)
    def test_missing_target(self):
        self.response['decisions'].pop()
        with self.assertRaises(ValueError):validate(self.request,self.response)
    def test_duplicate_target(self):
        self.response['decisions'].append(copy.deepcopy(self.response['decisions'][0]))
        with self.assertRaises(ValueError):validate(self.request,self.response)
    def test_unknown_evidence(self):
        self.response['decisions'][0]['evidence_utt_ids']=['another_conversation']
        with self.assertRaises(ValueError):validate(self.request,self.response)
    def test_missing_evidence_for_choice(self):
        self.response['decisions'][0]['evidence_utt_ids']=[]
        with self.assertRaises(ValueError):validate(self.request,self.response)
    def test_wrong_request(self):
        self.response['request_id']='other'
        with self.assertRaises(ValueError):validate(self.request,self.response)

if __name__=='__main__':unittest.main()

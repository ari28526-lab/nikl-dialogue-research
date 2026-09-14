import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from wsd_b_plan import intervals
from measure_wsd_pos_scope import SCOPES

class ScopeSemantics(unittest.TestCase):
    def test_removing_an_adverb_target_does_not_remove_shared_context(self):
        rows=[{'doc':'a','form':'아주 좋은 날이다'},{'doc':'a','form':'오늘은 비가 온다'}]
        both=[{'j':0},{'j':0},{'j':1}];restricted=[{'j':0},{'j':1}]
        self.assertEqual(intervals(rows,both),intervals(rows,restricted))
    def test_targetless_document_can_be_removed_without_crossing_boundary(self):
        rows=[{'doc':'a','form':'어 그래'},{'doc':'b','form':'비가 온다'}]
        self.assertEqual(len(intervals(rows,[{'j':0},{'j':1}])),2)
        self.assertEqual(intervals(rows,[{'j':1}]),[(1,2,1,2)])
    def test_selected_adjective_scope_excludes_determiners_and_proper_nouns(self):
        self.assertEqual(SCOPES['nng_vv_va'],{'NNG','VV','VA'})
        self.assertNotIn('MM',SCOPES['nng_vv_va'])
        self.assertNotIn('NNP',SCOPES['nng_vv_va'])
if __name__=='__main__':unittest.main()

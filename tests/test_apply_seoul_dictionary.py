import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import apply_seoul_dictionary as m

def row(token=0,mi=0,request='r1',sentence=0,begin=0):
    return dict(request_id=request,source_file='s01m16f1',utt_id='seoul:s01m16f1:t7:i1',sentence_index=sentence,
        token_index=token,morph_index=mi,token_text='가',morph='가',pos='NNG',token_begin_in_utterance=begin,
        token_end_in_utterance=begin+1,mapping_status='verified_token',urimal_target_id='10')
class Lex:
    pairs={}
    def analyze(self,*a):return dict(entries=[dict(target='10',group='g1',state='compatible')],groups=['g1'],common_classes=[])
class Dict:
    lex=Lex()
    def __init__(self):self.contexts=[]
    def decide(self,v,x,previous):
        self.contexts.append([q.ordinal for q in previous])
        return dict(status='morphology_singleton_machine_link',selected_group='g1',candidate_groups=['g1'])
class Supplement:
    def matched_patterns(self,*a):return []
class Evidence:
    def put(self,*a):return 'evidence'

class Tests(unittest.TestCase):
    def test_composite_ids_preserve_token_and_morph_resets(self):
        d={'source_file':'s01m16f1','speaker_metadata':{'speaker_id':'s01'}}
        a=row();b=row(request='r2',begin=2)
        v,anchors=m.sentence_view(d,dict(interval_index=1,text='가 가'),[a,b],Lex())
        self.assertEqual(len(anchors),2);self.assertEqual(v.ids,[1,2]);self.assertEqual(len(v.targets),2)
    def test_duplicate_and_bad_offset_fail(self):
        d={'source_file':'s01m16f1','speaker_metadata':{'speaker_id':'s01'}};u=dict(interval_index=1,text='가')
        with self.assertRaisesRegex(AssertionError,'duplicate_morph_anchor'):m.sentence_view(d,u,[row(),row()],Lex())
        with self.assertRaisesRegex(AssertionError,'token_source_mismatch'):m.sentence_view(d,dict(u,text='나'),[row()],Lex())
    def test_exact_target_agrees_conflict_and_missing_remain_distinct(self):
        a=Lex().analyze();r=row()
        self.assertEqual(m.compare(a,r,dict(selected_group='g1'))['status'],'same_homonym_group')
        self.assertEqual(m.compare(a,r,dict(selected_group='g2'))['status'],'group_conflict')
        r['urimal_target_id']=None
        self.assertEqual(m.compare(a,r,dict(selected_group='g1'))['status'],'dictionary_proposal_bareun_unmapped')
        self.assertIsNone(m.compare(a,r,dict(selected_group='g1'))['final_selected_group'])
    def test_unknown_compatibility_is_not_verified_mapping(self):
        a=Lex().analyze();a['entries'][0]['state']='unknown'
        self.assertIsNone(m.compare(a,row(),dict(selected_group='g1'))['bareun_group'])
    def test_marker_boundary_and_coverage_gap_suppress_inference(self):
        intervals=[dict(interval_index=i,start=i,end=i+1,text=t) for i,t in enumerate(['가','<IVER>','가','가'],1)]
        rows=[]
        for i in [1,3,4]:
            r=row(request='r'+str(i));r['utt_id']=f'seoul:s01m16f1:t7:i{i}';rows.append(r)
        source=dict(source_file='s01m16f1',speaker_metadata={'speaker_id':'s01'},interviewer_metadata={},
            tiers=[dict(tier_index=7,intervals=intervals)],morphology=rows,
            source_gaps=[{'utt_id':'seoul:s01m16f1:t7:i3'}],request_holds=[])
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'source.json';p.write_text(json.dumps(source),encoding='utf-8');d=Dict()
            result=m.apply_source(p,d,Supplement(),Evidence(),lambda *a:{'eojeol_evidence':{},'annotated_contexts':[]})
        self.assertEqual(d.contexts,[[],[],[]]);self.assertEqual(len(result['results']),3)
        gap=result['results'][1];self.assertIsNone(gap['dictionary']['selected_group'])
        self.assertEqual(gap['dictionary']['proposal_before_gap_hold'],'g1')
        self.assertEqual(gap['bareun'],rows[1])

if __name__=='__main__':unittest.main()

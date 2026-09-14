import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from build_native_frequency_v1 import selection,sentence,native_list,morph_key,annotation_holds
from frequency_units_v1 import events

class NativeFrequencyTest(unittest.TestCase):
 def test_null_empty_utterance_is_retained_with_zero_tokens(self):
  s=dict(id='synthetic.1',form='',word=None,morpheme=None,WSD=[])
  ts,c=sentence(s,{})
  self.assertEqual(list(events(s['form'],ts)),[])
  self.assertEqual(len(list(annotation_holds(s))),2)
  self.assertEqual(native_list(s,morph_key(s)),[])
 def test_transcribed_null_morphology_keeps_raw_eojeols_as_hold(self):
  s=dict(id='synthetic.2',form='집 안',word=[dict(id=1,form='집',begin=0,end=1)],morpheme=None,WSD=None)
  ts,c=sentence(s,{});rows=list(events(s['form'],ts))
  self.assertEqual(sum(u=='surface_eojeol' for u,*rest in rows),2)
  eo=[r for r in rows if r[0]=='eojeol' and r[1]=='collapsed']
  self.assertEqual(len(eo),2)
  self.assertTrue(all('ANALYSIS_UNAVAILABLE' in r[2] for r in eo))
 def test_invalid_nonlist_is_not_silently_zero(self):
  with self.assertRaises(ValueError):native_list({'morpheme':'bad'},'morpheme')
 def test_no_double_count_or_identical_sentence_dedup(self):
  rows=[['LS2020_spoken','1','SARW1.1',2,'abc'],['MP_spoken','1','SARW1',2,'abc'],['MP_spoken','2','SARW2',2,'abc'],['MP_spoken','3','SARW3',1,'xyz'],['LS2020_spoken','2','SARW3.1',2,'different']]
  s=selection(rows)
  self.assertEqual(s[('MP_spoken','1')][0],'exact_document_duplicate')
  self.assertEqual(s[('MP_spoken','2')][0],'included')
  self.assertEqual(s[('MP_spoken','3')][0],'partial_overlap_hold')
 def test_scope_and_special_sense(self):
  s=dict(form='먹고',word=[dict(id=1,form='먹고',begin=0,end=2)],morpheme=[dict(id=1,form='먹',label='VV',word_id=1,position=1),dict(id=2,form='고',label='EC',word_id=1,position=2)],WSD=[dict(word='먹',pos='VV',word_id=1,sense_id=888)])
  ts,c=sentence(s,{})
  self.assertEqual(c[('VV','native_annotations')],1)
  self.assertEqual(c[('EC','native_annotations')],0)
  self.assertIsNone(ts[0]['morphs'][0]['group'])
  self.assertEqual(sum(1 for u,m,*_ in events(s['form'],ts) if u=='morpheme' and m=='collapsed'),2)

if __name__=='__main__':unittest.main()

import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from seoul_frequency_semantics_v2 import select
from frequency_units_v1 import events
def row(st,b=None,d=None,**kw):return dict(comparison=dict(status=st,bareun_group=b,dictionary_group=d,final_selected_group=None,human_verified=False),**kw)
class Semantics(unittest.TestCase):
 def test_agreement_uses_machine_result_even_without_human_final(self):
  self.assertEqual(select(row('same_homonym_group','12','12')),('12','bareun_dictionary_agreement'))
 def test_single_sources_keep_distinct_basis(self):
  self.assertEqual(select(row('bareun_group_dictionary_undecided','12')),('12','bareun_only'))
  self.assertEqual(select(row('dictionary_proposal_bareun_unmapped',d='12')),('12','dictionary_only_candidate'))
 def test_conflict_unknown_and_gap_stay_unresolved(self):
  for r in [row('group_conflict','1','2'),row('both_unresolved_or_unmapped'),row('not_lexical_target'),row('same_homonym_group','1','1',source_gap_in_utterance=True)]:self.assertIsNone(select(r)[0])
 def test_inconsistent_status_and_bad_group_fail(self):
  for r in [row('same_homonym_group','1','2'),row('unknown'),row('bareun_group_dictionary_undecided','0')]:
   with self.assertRaises((AssertionError,ValueError)):select(r)
 def test_homonyms_split_with_collapsed_total_unchanged(self):
  counts={}
  for g in ['1','2','1',None]:
   for u,mode,base,sense,q in events('눈',[dict(surface='눈',start=0,end=1,morphs=[dict(lemma='눈',pos='NNG',group=g)])]):
    if u=='morpheme':counts[(mode,sense)]=counts.get((mode,sense),0)+1
  self.assertEqual(counts,{('collapsed',''):4,('split','urimal:1'):2,('split','urimal:2'):1,('split','?'):1})
if __name__=='__main__':unittest.main()

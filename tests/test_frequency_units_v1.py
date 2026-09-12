import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from frequency_units_v1 import *
def morph(s,p,g=None):return dict(lemma=s,pos=p,group=g)
class Units(unittest.TestCase):
    def test_inflection_not_extra_ending(self):
        t=dict(surface='먹었다',start=0,end=3,morphs=[morph('먹','VV','1'),morph('었','EP'),morph('다','EF')])
        e=list(events('먹었다',[t]))
        self.assertIn(('word','collapsed',js(['먹다','VV']),'','atomic_lexeme'),e)
        self.assertEqual(sum(x[0]=='morpheme' and x[1]=='collapsed' for x in e),3)
    def test_derivation_is_distinct_unknown_whole_sense(self):
        a=list(lexical_words([morph('사랑','NNG','1'),morph('하','XSV'),morph('었','EP')]))
        self.assertEqual(a[0][:3],('사랑하다','VV','?'))
        self.assertEqual(list(lexical_words([morph('살리','VV')]))[0][0],'살리다')
    def test_auxiliary_and_compound(self):
        self.assertEqual([x[0] for x in lexical_words([morph('먹','VV'),morph('어','EC'),morph('보','VX')])],['먹다','보다'])
        self.assertEqual(list(lexical_words([morph('학교','NNG'),morph('생활','NNG')]))[0][0],'학교생활')
    def test_pos_and_homonym_distinction(self):
        t=dict(surface='눈',start=0,end=1,morphs=[morph('눈','NNG','123')]);e=list(events('눈',[t]))
        self.assertIn(('morpheme','split',js(['눈','NNG']),'urimal:123','machine_link'),e)
        self.assertNotEqual(js(['눈','NNG']),js(['눈','VV']))
    def test_unjoined_raw_eojeols_never_disappear(self):
        t=dict(surface='집 안',start=0,end=3,morphs=[morph('집안','NNG')]);e=list(events('집 안',[t]))
        self.assertEqual(sum(x[0]=='eojeol' and x[1]=='collapsed' for x in e),2)
        self.assertTrue(all('ANALYSIS_UNAVAILABLE' in x[2] for x in e if x[0]=='eojeol'))
    def test_surface_only_and_split_reconcile(self):
        t=dict(surface='눈은',start=0,end=2,morphs=[morph('눈','NNG'),morph('은','JX')]);e=list(events('눈은',[t]))
        self.assertEqual(sum(x[0]=='eojeol' and x[1]=='collapsed' for x in e),sum(x[0]=='eojeol' and x[1]=='split' for x in e))
        self.assertEqual(aligned_span('눈은',10,12,'눈은',10),(0,2))
if __name__=='__main__':unittest.main()

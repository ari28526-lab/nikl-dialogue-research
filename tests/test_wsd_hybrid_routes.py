import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from compare_wsd_hybrid_routes import blocks

class HybridBlocksTests(unittest.TestCase):
    def test_targets_once_with_context_across_core_edges(self):
        rows=[(0,i,'a','가나다') for i in range(8)];ts={1:2,2:1,7:3}
        result=blocks(rows,ts,core_chars=7,max_utts=2)
        self.assertEqual(sum(r[4] for r in result),6)
        for j in ts:self.assertEqual(sum(a<=j<b for a,b,*_ in result),1)
        self.assertTrue(any(a<i for i,e,a,b,*_ in result))

    def test_document_boundary_never_crossed(self):
        rows=[(0,0,'a','가'),(0,1,'a','나'),(0,2,'b','다'),(0,3,'b','라')]
        for i,e,a,b,*_ in blocks(rows,{1:1,2:1}):
            self.assertEqual(len({r[2] for r in rows[a:b]}),1)

    def test_long_utterance_not_truncated(self):
        rows=[(0,0,'a','가'*400)]
        result=blocks(rows,{0:1})
        self.assertEqual(result[0][5],400)
        self.assertEqual(result[0][:4],(0,1,0,1))

    def test_targetless_core_skipped_but_context_can_remain(self):
        rows=[(0,0,'a','앞'),(0,1,'a',''),(0,2,'a','표적'),(0,3,'a','뒤')]
        result=blocks(rows,{2:1},max_utts=1)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][:4],(2,3,1,4))

if __name__=='__main__':unittest.main()

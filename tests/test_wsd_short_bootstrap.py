from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_wsd_short_bootstrap import select_ids,make_jobs,interleave,combine_ledger,elapsed_clock
from prepare_wsd_short_production import make_record


class BootstrapTests(unittest.TestCase):
    def test_six_year_size_strata_and_unique_selection(self):
        rows=[dict(conversation_id=f'C{y}_{i}',year=str(y),input_chars=i*100)
              for y in range(2020,2026) for i in range(10)]
        selected=select_ids(rows)
        self.assertEqual(len(selected),12)
        self.assertTrue(all(f'C{y}_5' in selected and f'C{y}_9' in selected for y in range(2020,2026)))
        with self.assertRaises(ValueError):select_ids(rows[:10])

    def test_round_robin_does_not_starve_other_years(self):
        self.assertEqual(interleave([[1,2,3],[4],[5,6]]),[1,4,5,2,6,3])

    def test_input_hold_retained_without_api_job(self):
        rows=[dict(utt_id=f'C.{i}',source_row_index=str(i+1),speaker_id='S',form=t)
              for i,t in enumerate(['abc','x'*401,'def'])]
        record=make_record(rows,'C',dict(relative='files/NIKL_DIALOGUE_2020_v1.4/C/RECEIPT.json'))
        jobs,holds=make_jobs(record,rows)
        self.assertEqual(len(holds),1)
        self.assertEqual(holds[0]['status'],'hold_oversize_utterance')
        ledger=[dict(utt_id=m['utt_id'],status='pending') for j in jobs for m in j['mappings'] if m['role']=='core']
        result=combine_ledger(rows,ledger,holds)
        self.assertEqual([r['utt_id'] for r in result],[r['utt_id'] for r in rows])
        self.assertEqual(len(result),3)
        with self.assertRaises(ValueError):combine_ledger(rows,ledger+ledger,holds)

    def test_restart_clock_does_not_reset_grant(self):
        clock=elapsed_clock(100,monotonic=lambda:20,wall=lambda:3701)
        self.assertEqual(clock(),0)
        self.assertEqual(clock(),3601)

    def test_empty_groups_and_empty_holds(self):
        self.assertEqual(interleave([]),[])
        self.assertEqual(combine_ledger([],[],[]),[])


if __name__=='__main__':unittest.main()

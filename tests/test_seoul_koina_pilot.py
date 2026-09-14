import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_seoul_koina_pilot import interval_index,raw_point_flags
class Tests(unittest.TestCase):
    def test_boundary_belongs_to_following_interval(self):
        self.assertEqual([interval_index([1.,2.,3.],t) for t in [0.,.999,1.,2.,3.]],[0,0,1,2,2])
    def test_degenerate_momel_output_is_not_silently_clipped_to_valid(self):
        self.assertIn('nonpositive_f0',raw_point_flags(0,0,201,150,150))
        flags=raw_point_flags(4000,497.517,201,150,150)
        self.assertIn('outside_input_frame_span',flags);self.assertIn('outside_recording_corrected_f0_range',flags)
    def test_internal_finite_point_vs_extrapolated_endpoint(self):
        self.assertEqual(raw_point_flags(175.559,219.378,401,140,220),[])
        self.assertIn('outside_input_frame_span',raw_point_flags(-175.559,150,401,140,220))
        self.assertEqual(raw_point_flags(float('nan'),150,401,140,220),['nonfinite'])
if __name__=='__main__':unittest.main()

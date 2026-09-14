import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from run_seoul_koina_clock_v2 import frame_bounds,point_quality,parse_model

class Tests(unittest.TestCase):
    def test_real_frame_centers_not_zero_origin_indices(self):
        times=[.035+i*.01 for i in range(20)]
        start,stop=frame_bounds(times,.10,.15)
        self.assertEqual((start,stop),(7,12))
        self.assertTrue(all(.10<=t<.15 for t in times[start:stop]))
        self.assertAlmostEqual(times[start],.105)

    def test_half_open_boundary_and_empty_segment(self):
        self.assertEqual(frame_bounds([.1,.2,.3],.1,.3),(0,2))
        self.assertEqual(frame_bounds([.1,.2,.3],.11,.19),(1,1))

    def test_known_parabolic_endpoint_is_preserved_as_extrapolation(self):
        self.assertEqual(point_quality(-500,210,161,0,3,150,250),('boundary_extrapolation',[]))
        self.assertEqual(point_quality(500,250,161,1,3,150,250),('internal_target',[]))
        self.assertEqual(point_quality(2700,56.4,161,2,3,150,250),('boundary_extrapolation',['outside_recording_filtered_f0_range']))

    def test_degenerate_output_not_promoted(self):
        self.assertIn('nonpositive_f0',point_quality(0,0,201,0,2,150,150)[1])
        self.assertIn('outside_recording_filtered_f0_range',point_quality(4000,497,201,1,2,150,150)[1])
        self.assertEqual(point_quality(float('nan'),150,20,0,1,100,200),('invalid',['nonfinite']))

    def test_nonendpoint_extrapolation_is_not_regular_boundary(self):
        kind,flags=point_quality(-10,150,100,1,3,100,200)
        self.assertEqual(kind,'outside_input_span');self.assertIn('nonendpoint_outside_input',flags)

    def test_malformed_model_fails_closed(self):
        with self.assertRaises(AssertionError):parse_model('100 200 extra')
        self.assertEqual(parse_model('100 200\n\n'),[(100.,200.)])

if __name__=='__main__':unittest.main()

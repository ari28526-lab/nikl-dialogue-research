import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from seoul_boundary_core import map_syllables,classify,vowel_feature

class BoundaryGuards(unittest.TestCase):
    def test_no_pitch_gap_as_pause(self):
        grid={'tonal_change_semitones':1,'annotated_silence_seconds':.12}
        self.assertEqual(classify({'terminal_change_st':3},[],grid),'no_boundary_evidence')
        self.assertEqual(classify({'terminal_change_st':None,'annotated_silence_seconds':2},[],grid),'no_boundary_evidence')

    def test_holds_override_positive_cues(self):
        m={'terminal_change_st':4,'annotated_silence_seconds':1}
        g={'tonal_change_semitones':2,'annotated_silence_seconds':.3}
        self.assertEqual(classify(m,['speaker_unknown'],g),'not_evaluable')
        self.assertEqual(classify(m,[],g),'IP_candidate')

    def test_ap_requires_multiple_cues(self):
        g={'tonal_change_semitones':1,'annotated_silence_seconds':.2}
        m={'ap_context_eligible':True,'pre_final_rise_st':3,'next_initial_rise_st':3,'boundary_fall_st':3}
        self.assertEqual(classify(m,[],g),'AP_candidate')
        m['boundary_fall_st']=None
        self.assertEqual(classify(m,[],g),'no_boundary_evidence')

    def test_exact_syllable_edges_and_no_forced_mapping(self):
        w={'start':0,'end':.3,'text':'가나'}
        p=dict(w);r={**w,'text':'k0aa-nnaa'}
        phones=[dict(start=a,end=b,text=t) for a,b,t in [(0,.05,'k0'),(.05,.15,'aa'),(.15,.2,'nn'),(.2,.3,'aa')]]
        result,reason=map_syllables(w,p,r,phones,[x['end'] for x in phones],{'aa'})
        self.assertEqual([s['start'] for s in result],[0,.15])
        self.assertEqual([s['vowel_start'] for s in result],[.05,.2])
        r['text']='k0aa-mmaa'
        self.assertEqual(map_syllables(w,p,r,phones,[x['end'] for x in phones],{'aa'})[1],'roman_phone_sequence_mismatch')

    def test_no_interpolation_over_unvoiced_gap(self):
        p={'frame_min_count':3,'minimum_voiced_fraction_in_vowel':.5,'maximum_adjacent_f0_jump_semitones':7}
        s={'vowel_start':10,'vowel_end':10.1}
        times=[10+i*.01 for i in range(10)]
        v=vowel_feature(s,times,[100,100,100,0,0,0,0,300,300,300],p)
        self.assertEqual(v['max_adjacent_jump_st'],0)
        self.assertEqual(v['voiced_frames'],6)
        self.assertAlmostEqual(v['voiced_fraction'],.6)

if __name__=='__main__':unittest.main()

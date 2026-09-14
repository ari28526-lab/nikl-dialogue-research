import sys,unittest,tempfile,json
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from repair_seoul_scope import speech_view,save

class Tests(unittest.TestCase):
    def test_status_sharing_retry_and_manifest_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'STATE.json'
            with patch('repair_seoul_scope.bareun.save',side_effect=[PermissionError('sharing'),None]) as writer,patch('repair_seoul_scope.time.sleep'):
                self.assertTrue(save(p,{'n':1}));self.assertEqual(writer.call_count,2)
            with patch('repair_seoul_scope.bareun.save',side_effect=PermissionError('sharing')),patch('repair_seoul_scope.time.sleep'):
                self.assertFalse(save(p,{'n':2}))
                with self.assertRaises(PermissionError):save(Path(td)/'CONTRACT.json',{})
    def test_laughter_transcript_retained_at_original_coordinates(self):
        raw='<LAUGH-그래서 네>';v=speech_view(raw)
        self.assertEqual(v['status'],'annotated_speech')
        self.assertEqual(v['analysis_text'].strip(),'그래서 네')
        self.assertEqual(len(raw),len(v['analysis_text']))
        self.assertEqual(v['analysis_text'].index('그래서'),raw.index('그래서'))
    def test_mixed_noise_preserves_both_sides(self):
        raw='어쨌든 <VOCNOISE> 그래서';v=speech_view(raw)
        self.assertEqual(v['status'],'annotated_speech')
        self.assertEqual(v['analysis_text'].split(),['어쨌든','그래서'])
        self.assertEqual(v['analysis_text'].index('그래서'),raw.index('그래서'))
    def test_pure_markers_have_no_fake_text(self):
        for x in ['<LAUGH>','<IVER>','<PRIVATE.INFO>','<SIL> <NOISE>']:
            self.assertEqual(speech_view(x)['status'],'marker_only')
            self.assertFalse(speech_view(x)['analysis_text'].strip())
    def test_unknown_or_malformed_annotations_are_held(self):
        for x in ['<UNFAMILIAR-말>','<LAUGH-말','앞 <LAUGH-말>>']:
            self.assertEqual(speech_view(x)['status'],'annotation_review_hold')
    def test_ordinary_text_is_unchanged(self):
        raw='  원문  그대로. '
        self.assertEqual(speech_view(raw)['analysis_text'],raw)
        self.assertEqual(speech_view(raw)['status'],'ordinary_speech')

if __name__=='__main__':unittest.main()

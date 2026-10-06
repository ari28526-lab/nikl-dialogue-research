import json
from pathlib import Path
import sys,tempfile,unittest,wave
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import audit_delivery_audio_scope as m

class AudioTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def pair(self):
        pcm=self.root/'sample.pcm';pcm.write_bytes(b'\x01\x00'*20);wav=self.root/'sample.wav'
        with wave.open(str(wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.read_bytes())
        return dict(kind='pcm_wav',pcm=str(pcm),wav=str(wav))
    def test_payload_equality_actual_wav(self):
        result=m.probe(self.pair());self.assertTrue(result['payload_equal']);self.assertFalse(result['full_coverage_verified'])
    def test_payload_mismatch(self):
        request=self.pair();Path(request['pcm']).write_bytes(b'changed')
        self.assertFalse(m.probe(request)['payload_equal'])
    def test_no_recursive_discovery(self):
        (self.root/'pcm').mkdir();(self.root/'pcm/nested.pdf').write_bytes(b'x')
        (self.root/'official.pdf').write_bytes(b'x')
        result=m.probe(dict(kind='document_directory',path=str(self.root)))
        self.assertEqual(len(result['document_candidates']),1);self.assertFalse(result['reviewed'])
    def test_sample_bound(self):
        with patch.object(m,'MAX_BYTES',1):
            with self.assertRaises(ValueError):m.probe(self.pair())
    def test_real_child_probe(self):
        result=m.isolated(self.pair(),10);self.assertEqual(result['status'],'listed_pair_checked')
    def test_child_timeout(self):
        import subprocess
        from unittest.mock import Mock
        child=Mock(pid=123);child.wait.side_effect=[subprocess.TimeoutExpired('child',1),None]
        with patch.object(m.subprocess,'Popen',return_value=child):
            result=m.isolated({},1);self.assertEqual(result['status'],'probe_timeout');self.assertTrue(result['exit_confirmed'])
    def test_termination_wait_is_also_bounded(self):
        import subprocess
        from unittest.mock import Mock
        child=Mock(pid=123);child.wait.side_effect=subprocess.TimeoutExpired('child',1)
        with patch.object(m.subprocess,'Popen',return_value=child):
            result=m.isolated({},1)
        self.assertFalse(result['exit_confirmed']);self.assertEqual(child.wait.call_args.kwargs['timeout'],2)
    def test_timeout_does_not_claim_missing_or_retry_other_roots(self):
        plan=dict(document_directories=[dict(year=y,path='declared') for y in range(2021,2026)])
        with patch.object(m,'isolated',return_value=dict(status='probe_timeout')) as child:
            result=m.build(plan,dict(full_coverage_verified=False,pairs=[]),self.root/'receipt.json')
        self.assertEqual(child.call_count,1);self.assertFalse(result['official_2021_2025_scope_reviewed'])
        self.assertFalse(result['delivery_complete'])
    def test_no_receipt_overwrite(self):
        plan=dict(document_directories=[dict(year=y,path='declared') for y in range(2021,2026)])
        p=self.root/'receipt.json';p.write_text('old')
        with patch.object(m,'isolated',return_value=dict(status='probe_timeout')):
            with self.assertRaises(ValueError):m.build(plan,dict(full_coverage_verified=False,pairs=[]),p)
        self.assertEqual(p.read_text(),'old')

if __name__=='__main__':unittest.main()

import sys
import json
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_delivery_final_incremental_manifest as m

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.plan=dict(schema='final_incremental_plan.v1',roots=['metadata/control_io_v1','recovery_20261002_reboot'],pins={},dependency_states=[])
        for rel in self.plan['roots']:(self.root/rel).mkdir(parents=True)
        (self.root/'metadata/control_io_v1/POLICY.json').write_text('{}')
        (self.root/'metadata/control_io_v1/STATE.json').write_text('live')
        (self.root/'recovery_20261002_reboot/STATE.json').write_text('archived')
    def tearDown(self):self.temp.cleanup()
    def test_archive_controls_included_live_excluded(self):
        rows=m.inventory(self.root,self.plan)
        self.assertEqual([r['path'] for r in rows],['metadata/control_io_v1/POLICY.json','recovery_20261002_reboot/STATE.json'])
    def test_frozen_tamper(self):
        rel='metadata/control_io_v1/POLICY.json';self.plan['pins'][rel]=m.sha(self.root/rel)
        m.preflight(self.root,self.plan);(self.root/rel).write_text('changed')
        with self.assertRaises(ValueError):m.preflight(self.root,self.plan)
    def test_corpus_walk_rejected(self):
        self.plan['roots']=['latest_release']
        with self.assertRaises(ValueError):m.preflight(self.root,self.plan)
    def test_escape(self):
        for rel in ['../bad','C:/bad']:
            with self.assertRaises(ValueError):m.safe(self.root,rel)
    def test_payload_rejected(self):
        (self.root/'metadata/control_io_v1/payload.sqlite').write_bytes(b'x')
        with self.assertRaises(ValueError):m.inventory(self.root,self.plan)
    def test_file_bound(self):
        from unittest.mock import patch
        with patch.object(m,'MAX_FILE',1):
            with self.assertRaises(ValueError):m.inventory(self.root,self.plan)
    def test_missing_receipt_rejected(self):
        with self.assertRaises(FileNotFoundError):m.bindings(self.root)
    def test_atomic_readback(self):
        p=self.root/'test.json';m.save(p,dict(value='한글'));self.assertEqual(m.read(p),dict(value='한글'))
    def test_completion_scope_and_readback(self):
        from unittest.mock import patch
        out=self.root/'audit';out.mkdir()
        with patch.object(m,'bindings',return_value={'fixed':'receipt'}):
            result=m.build(self.root,out,self.plan)
        self.assertFalse(result['delivery_complete']);self.assertFalse(result['full_delivery_acceptance'])
        self.assertEqual(result['manifest_sha256'],m.sha(out/'MANIFEST.json'))
    def test_mutation_during_audit(self):
        from unittest.mock import patch
        out=self.root/'audit';out.mkdir()
        with patch.object(m,'bindings',side_effect=[{'fixed':1},{'fixed':2}]):
            with self.assertRaises(ValueError):m.build(self.root,out,self.plan)
    def fixture(self):
        def put(rel,value):
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);m.save(p,value);return m.sha(p)
        put('COPY_FINAL.json',dict(status='declared_scope_copied_sha_verified',files=15580294,bytes=832706074044,sample=False))
        put('metadata/addon_integrity_v1/FINAL.json',dict(status='addon_files_sha_verified',sample=False,manifest_sha256='prior-large-audit'))
        put('metadata/reopen_queries_v1/FINAL.json',dict(status='bounded_reopen_queries_verified',sample=True,python_r_equal=True,physical_relocation=True))
        evidence=put('metadata/acceptance_evidence_v1/FINAL.json',dict(status='receipt_chain_verified_with_remaining_acceptance',sample=False))
        filehash=put('research_tools_v3/examples.json',{'preserved':True})
        bundle=put('research_tools_v3/BUNDLE_MANIFEST.json',dict(files=[dict(path='examples.json',sha256=filehash)]))
        put(m.DEPENDENCY,dict(status='completed_state_guide_generated',sample=False,receipt_chain_sha256=evidence,manifest_sha256=bundle))
    def test_receipt_binding_and_actual_guide_tamper(self):
        self.fixture();self.assertEqual(m.bindings(self.root)['prior_addon_manifest_sha256'],'prior-large-audit')
        (self.root/'research_tools_v3/examples.json').write_text('{}')
        with self.assertRaises(ValueError):m.bindings(self.root)
    def test_full_copy_cannot_be_sample(self):
        self.fixture();p=self.root/'COPY_FINAL.json';value=m.read(p);value['sample']=True;m.save(p,value)
        with self.assertRaises(ValueError):m.bindings(self.root)

if __name__=='__main__':unittest.main()

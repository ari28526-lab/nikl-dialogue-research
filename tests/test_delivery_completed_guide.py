import copy
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
from unittest import TestCase,main
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_delivery_completed_guide as m


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.scripts.append(tag)
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href')


class Guide(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'package';self.root.mkdir();self.out=Path(self.temp.name)/'guide'
        self.plan=dict(schema='delivery_acceptance_evidence.v1',roles={r:'datasets/'+r for r in m.ROLES},sources={},frozen_metadata={})
        example=dict(id='E',title='<script>alert(1)</script>',how_to_read='후보 ≠ 정답',source_table='morphemes',
            source_key={'utterance_ordinal':0},payload={'selected_group':None,'human_gold':False},
            package_database_path='datasets/context_original_databases/APPLICATION.sqlite')
        self.examples=dict(created_at='2026-09-26T21:21:18+09:00',examples=[dict(example,id='E'+str(i)) for i in range(7)])
        self.sources=dict(sources=[dict(role='dictionary',package_path='datasets/used_dictionary/DB'+str(i)+'.sqlite',bytes=0,sha256='0'*64) for i in range(49)])
        manifest=dict(files=[])
        for name,value in [('examples.json',self.examples),('source_inventory.json',self.sources)]:
            rel='supplement_reader/'+name;path=self.root/m.V2/rel;m.save(path,value)
            manifest['files'].append(dict(path=rel,sha256=m.read(path)[1]))
        manifest['files'].extend(dict(path='other_'+str(i),sha256='0'*64) for i in range(26))
        p=self.root/m.V2/'BUNDLE_MANIFEST.json';m.save(p,manifest)
        self.plan['frozen_metadata'][m.V2+'/BUNDLE_MANIFEST.json']=m.read(p)[1]
        self.copy=dict(status='declared_scope_copied_sha_verified',files=15580294,bytes=832706074044)
        self.reopen=dict(status='bounded_reopen_queries_verified',sample=True,python_r_equal=True,physical_relocation=True)
        self.semantic=dict(status='semantic_links_complete_with_explicit_scope_gaps',sample=False,counts=dict(
            modu_utterances=5157997,modu_derived=4286046,modu_no_mfa_alignment=817310,modu_empty_source_not_analyzed=54641,
            seoul_interviews=40,seoul_segments=240,seoul_utterances=128313))

    def evidence(self):
        bound={m.V2+'/BUNDLE_MANIFEST.json':self.plan['frozen_metadata'][m.V2+'/BUNDLE_MANIFEST.json']}
        for rel,obj in [('COPY_FINAL.json',self.copy),('metadata/reopen_queries_v1/FINAL.json',self.reopen),('metadata/semantic_links/FINAL.json',self.semantic)]:
            m.save(self.root/rel,obj);bound[rel]=m.read(self.root/rel)[1]
        value=dict(status='receipt_chain_verified_with_remaining_acceptance',sample=False,delivery_complete=False,
            full_delivery_acceptance=False,receipt_sha256=bound,
            remaining_acceptance=[dict(id='final_guide',requirement='Guide'),dict(id='audio_scope',requirement='Audio')])
        m.save(self.root/m.DEPENDENCY,value);return value

    def test_pilot_preserves_samples_and_counts(self):
        result=m.build(self.root,self.out,self.plan,pilot=True)
        self.assertTrue(result['sample']);self.assertFalse(result['delivery_complete'])
        self.assertEqual(m.read(self.out/'examples.json')[0],self.examples)
        self.assertEqual(m.read(self.out/'source_inventory.json')[0],self.sources)
        cat=m.read(self.out/'DATASET_CATALOG.json')[0]
        self.assertFalse(cat['receipt_chain_verified']);self.assertEqual(cat['counts'],m.COUNTS)
        self.assertEqual(cat['preserved_example_created_at'],self.examples['created_at'])

    def test_html_escapes_stored_text_and_relative_links(self):
        m.build(self.root,self.out,self.plan,pilot=True);html=(self.out/'index.html').read_text(encoding='utf-8')
        parser=Links();parser.feed(html)
        self.assertEqual(parser.scripts,[]);self.assertIn('&lt;script&gt;',html)
        self.assertTrue(all(not p.startswith(('file:','F:','http')) for p in parser.links))
        self.assertIn('selected_group',html);self.assertIn('의미 후보',html)

    def test_missing_evidence_cannot_publish_completed_guide(self):
        with self.assertRaises(FileNotFoundError):m.build(self.root,self.out,self.plan)
        self.assertFalse((self.out/'BUNDLE_MANIFEST.json').exists())

    def test_completed_guide_requires_real_targets(self):
        self.evidence()
        with self.assertRaisesRegex(ValueError,'target missing'):m.build(self.root,self.out,self.plan)

    def test_completed_component_still_not_delivery(self):
        self.evidence()
        for path in self.plan['roles'].values():(self.root/path).mkdir(parents=True)
        for item in self.examples['examples']+self.sources['sources']:
            rel=item.get('package_path',item.get('package_database_path'));p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
        result=m.build(self.root,self.out,self.plan)
        self.assertFalse(result['sample']);self.assertFalse(result['delivery_complete'])
        catalog=m.read(self.out/'DATASET_CATALOG.json')[0]
        self.assertEqual([x['id'] for x in catalog['remaining_acceptance']],['audio_scope'])
        self.assertFalse((self.root/'DELIVERY_FINAL.json').exists())

    def test_sample_or_wrong_counts_cannot_claim_completion(self):
        for kind in ['sample','count','reopen']:
            value=self.evidence()
            if kind=='sample':value['sample']=True;m.save(self.root/m.DEPENDENCY,value)
            if kind=='count':
                self.semantic['counts']['modu_derived']=4286045;self.evidence()
            if kind=='reopen':
                self.semantic['counts']['modu_derived']=4286046;self.reopen['sample']=False;self.evidence()
            with self.assertRaises(ValueError):m.verify_evidence(self.root,self.plan)

    def test_frozen_v2_untouched_and_source_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError,'v2 cannot'):m.build(self.root,self.root/m.V2/'new',self.plan,pilot=True)
        self.assertFalse((self.root/m.V2/'new').exists())
        m.save(self.root/m.V2/'supplement_reader/examples.json',{})
        with self.assertRaisesRegex(ValueError,'metadata changed'):m.inputs(self.root,self.plan)

    def test_metadata_retry_is_bounded_and_no_stale_fallback(self):
        p=self.root/'state.json';m.save(p,{'status':'running'})
        real=Path.read_bytes;calls=[]
        def once(path):
            calls.append(path)
            if len(calls)==1:raise PermissionError('shared')
            return real(path)
        with patch.object(Path,'read_bytes',once),patch.object(m.time,'sleep'):
            self.assertEqual(m.read(p)[0],{'status':'running'});self.assertEqual(len(calls),2)
        with patch.object(Path,'read_bytes',side_effect=PermissionError('persistent')) as mocked,patch.object(m.time,'sleep'):
            with self.assertRaises(PermissionError):m.read(p)
            self.assertEqual(mocked.call_count,8)

    def test_unsafe_paths_and_large_payload_refused(self):
        for rel in ['../escape','C:/escape','a//b','a\\b','/abs']:
            with self.assertRaises(ValueError):m.safe(self.root,rel)
        p=self.root/'large'
        with p.open('wb') as f:f.truncate(m.MAX_BYTES+1)
        with self.assertRaisesRegex(ValueError,'Metadata limit'):m.read(p,False)


if __name__=='__main__':main()

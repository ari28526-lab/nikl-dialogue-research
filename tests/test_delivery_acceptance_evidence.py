import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import audit_delivery_acceptance_evidence as m


def skeleton(expected):
    obj={}
    for keys,value in expected.items():
        cur=obj
        for k in keys[:-1]: cur=cur.setdefault(k,{})
        cur[keys[-1]]=value
    return obj


class EvidenceAudit(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        roles={s[0]:'source/'+s[0] for s in m.SPECS.values()}
        while len(roles)<25: roles['fixture_'+str(len(roles))]='source/fixture_'+str(len(roles))
        self.plan=dict(schema='delivery_acceptance_evidence.v1',roles=roles,sources={},frozen_metadata={},copy_config_sha256='a'*64)
        self.values={name:skeleton(spec) for name,(_,_,spec) in m.SPECS.items()}
        self.values['seoul_interviews']['receipts']={}
        base=roles[m.PROD]+'/discourse_json/seoul_interviews'
        for i in range(40):
            key='interview_'+str(i); rel=base+'/'+key+'.receipt.json'
            self.write(rel,dict(ordinal=i));self.values['seoul_interviews']['receipts'][key]=self.sha(rel)
        for name in ['context','supplement','csv','tabular','discourse_parquet','supplement_parquet',
                     'seoul_morphology','seoul_dictionary','modu_morphology','modu_textgrid','seoul_discourse','modu_discourse','seoul_interviews',
                     'comparison','saved_review','production']:
            role,rel,_=m.SPECS[name]
            parent={'supplement':'context','csv':'supplement','tabular':'csv','discourse_parquet':'tabular','supplement_parquet':'discourse_parquet'}.get(name)
            if parent:
                digest=self.plan['sources'][parent]['sha256']
                if name=='supplement':self.values[name]['dependency']['final_sha256']=digest
                else:self.values[name]['dependency_sha256']=digest
            if name=='production':
                self.values[name]['artifacts']=[dict(path=m.SPECS[n][1],sha256=self.plan['sources'][n]['sha256']) for n in
                    ['seoul_morphology','seoul_dictionary','modu_morphology','modu_textgrid','seoul_discourse','modu_discourse']]
            path=roles[role]+'/'+rel;self.write(path,self.values[name]);self.plan['sources'][name]=dict(path=path,sha256=self.sha(path))
        for rel in ['CONTRACT.json','INVENTORY.json',*[d+'/CONTRACT.json' for d in [m.SEM,m.HIST,m.GUIDE,m.ADDON,m.REOPEN]],
                    'research_tools_v2/BUNDLE_MANIFEST.json',m.REOPEN+'/QUERY_PLAN.json']:
            value={}
            if rel=='CONTRACT.json':value=dict(config_sha256='a'*64,config=dict(roots=[dict(role=k,destination=v) for k,v in roles.items()]))
            if rel=='INVENTORY.json':value=dict(status='source_inventory_complete',files=15580294,bytes=832706074044)
            self.write(rel,value);self.plan['frozen_metadata'][rel]=self.sha(rel)
        self.dynamic={rel:skeleton(expected) for rel,expected in m.DYNAMIC.items()}
        for rel,value in self.dynamic.items():
            if rel=='COPY_FINAL.json':value.update(inventory_sha256=self.sha('INVENTORY.json'),ledger_sha256='b'*64)
            if rel==m.HIST+'/FINAL.json':
                self.write(m.HIST+'/DEPENDENCIES.json',dict(copy_final_sha256=self.sha('COPY_FINAL.json'),semantic_final_sha256=self.sha(m.SEM+'/FINAL.json')))
            required={m.GUIDE:['COPY_FINAL.json',m.SEM+'/FINAL.json',m.HIST+'/FINAL.json'],
                      m.ADDON:['COPY_FINAL.json',m.SEM+'/FINAL.json',m.HIST+'/FINAL.json',m.GUIDE+'/FINAL.json'],
                      m.REOPEN:['COPY_FINAL.json',m.ADDON+'/FINAL.json']}
            stage=rel.rsplit('/',1)[0]
            if stage in required:value['dependencies']={r:self.sha(r) for r in required[stage]}
            if stage==m.GUIDE:value.update(bundle_manifest_sha256=self.sha('research_tools_v2/BUNDLE_MANIFEST.json'),references=[{}]*56)
            if stage==m.ADDON:
                self.write(m.ADDON+'/SHA256_MANIFEST.jsonl',dict(fixture=True));self.write(m.ADDON+'/INVENTORY.json',{})
                value.update(roots=[m.SEM,m.HIST,m.GUIDE,'research_tools_v2'],manifest_sha256=self.sha(m.ADDON+'/SHA256_MANIFEST.jsonl'),inventory_sha256=self.sha(m.ADDON+'/INVENTORY.json'))
            if stage==m.REOPEN:
                evidence={}
                for name in ['PYTHON_QUERY.json','RELOCATED_PYTHON_QUERY.json','R_QUERY.json']:
                    self.write(stage+'/'+name,dict(cases=[]));evidence[name]=self.sha(stage+'/'+name)
                self.write(stage+'/DEPENDENCIES.json',value['dependencies'])
                value.update(evidence=evidence,plan_sha256=self.sha(stage+'/QUERY_PLAN.json'),contract_sha256=self.sha(stage+'/CONTRACT.json'))
            self.write(rel,value)

    def write(self,rel,value):m.save(m.safe(self.root,rel),value)
    def sha(self,rel):return m.metadata(m.safe(self.root,rel),False)[1]
    def audit(self):return m.audit(self.root,self.plan)

    def test_chain_does_not_claim_delivery(self):
        result=self.audit()
        self.assertFalse(result['delivery_complete']);self.assertFalse(result['full_delivery_acceptance'])
        self.assertEqual(len(result['remaining_acceptance']),5)
        self.assertGreater(result['receipts_hashed'],65)
        self.assertFalse((self.root/'DELIVERY_FINAL.json').exists())

    def test_pending_is_not_completed(self):
        (self.root/m.REOPEN/'FINAL.json').unlink()
        self.assertEqual(m.missing(self.root,self.plan),[m.REOPEN+'/FINAL.json'])
        with self.assertRaises(FileNotFoundError):self.audit()

    def test_tampered_pinned_source(self):
        self.write(self.plan['sources']['modu_textgrid']['path'],dict(status='complete'))
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):self.audit()

    def test_dynamic_count_and_bool_type(self):
        for value in [4286045,True]:
            obj=copy.deepcopy(self.dynamic[m.SEM+'/FINAL.json']);obj['counts']['modu_derived']=value
            self.write(m.SEM+'/FINAL.json',obj)
            with self.assertRaisesRegex(ValueError,'unexpected counts.modu_derived'):self.audit()

    def test_sample_cannot_replace_full_index(self):
        obj=copy.deepcopy(self.dynamic[m.HIST+'/FINAL.json']);obj['sample']=True;self.write(m.HIST+'/FINAL.json',obj)
        with self.assertRaisesRegex(ValueError,'unexpected sample'):self.audit()

    def test_reopen_cannot_be_promoted_to_full_corpus(self):
        obj=copy.deepcopy(self.dynamic[m.REOPEN+'/FINAL.json']);obj['sample']=False;self.write(m.REOPEN+'/FINAL.json',obj)
        with self.assertRaisesRegex(ValueError,'unexpected sample'):self.audit()

    def test_dependency_changed(self):
        obj=copy.deepcopy(self.dynamic[m.GUIDE+'/FINAL.json']);obj['dependencies']['COPY_FINAL.json']='0'*64
        self.write(m.GUIDE+'/FINAL.json',obj)
        with self.assertRaisesRegex(ValueError,'dependency binding differs'):self.audit()

    def test_production_artifact_missing_even_if_repin(self):
        obj=copy.deepcopy(self.values['production']);obj['artifacts'].pop()
        rel=self.plan['sources']['production']['path'];self.write(rel,obj);self.plan['sources']['production']['sha256']=self.sha(rel)
        with self.assertRaisesRegex(ValueError,'six-artifact'):self.audit()

    def test_interview_receipt_tampered(self):
        rel=self.plan['roles'][m.PROD]+'/discourse_json/seoul_interviews/interview_0.receipt.json'
        self.write(rel,dict(ordinal=999))
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):self.audit()

    def test_query_evidence_changed(self):
        self.write(m.REOPEN+'/R_QUERY.json',dict(cases=['changed']))
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):self.audit()

    def test_path_escape_and_duplicate_mapping(self):
        for rel in ['../escape','C:/escape','/escape','a\\b','a//b','a/./b']:
            with self.assertRaises(ValueError):m.safe(self.root,rel)
        plan=copy.deepcopy(self.plan);plan['roles']['fixture_15']=plan['roles'][m.PROD]
        with self.assertRaises(ValueError):m.validate_plan(plan)

    def test_metadata_limit_blocks_payload_hash(self):
        p=self.root/'too_large'
        with p.open('wb') as f:f.truncate(m.MAX_BYTES+1)
        with self.assertRaisesRegex(ValueError,'size/type'):m.metadata(p,False)


if __name__=='__main__':unittest.main()

"""Audited release selection, tamper checks and group-level dictionary lookup."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
import analysis_release as a
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/variation_review'))
from build_release_data import rebind


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work/release_tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.catalog = self.root / 'catalog.json'
        self.analysis = self.root / 'analysis'
        self.analysis.mkdir()
        self.audit = self.root / 'audit.json'
        self.dictionary = self.root / 'dictionary.sqlite'
        self.receipt = self.root / 'dictionary.receipt.json'
        with sqlite3.connect(self.dictionary) as db:
            db.execute('CREATE TABLE entries(target,group_id,lemma,word,pos,definition)')
            db.executemany('INSERT INTO entries VALUES(?,?,?,?,?,?)', [
                ('1','10','가상','가상','명사','첫 뜻'),
                ('2','10','가상','가상','명사','같은 동형어의 세부 뜻'),
                ('3','20','가상','가상','명사','다른 동형어'),
            ])
        db.close()
        self.write(self.receipt, dict(status='complete',release_date='test',
                   database_sha256=a.sha(self.dictionary),bytes=self.dictionary.stat().st_size))
        self.write(self.analysis/'CONTRACT.json',dict(config=dict(max_requests=2,
                   version_provenance=dict(requested_release='test'))))
        contract_hash=hashlib.sha256(json.dumps(
            a.read(self.analysis/'CONTRACT.json'),ensure_ascii=False,
            sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.write(self.analysis/'FULL_FINAL.json',dict(status='complete_with_explicit_coverage_reviews',
                   contract_sha256=contract_hash,counts=dict(seoul_sources=1,modu_sources=1)))
        self.write(self.audit,dict(status='passed_complete_baseline',contract_sha256=contract_hash,
                   full_final_sha256=a.sha(self.analysis/'FULL_FINAL.json'),audited_requests=2))
        for corpus in ('seoul','modu'):
            folder=self.analysis/'full'/corpus/'sample'
            folder.mkdir(parents=True)
            with gzip.open(folder/'discourse.json.gz','wt',encoding='utf8') as stream:
                json.dump(dict(utterances=[dict(utterance_id='u1',analysis=dict(morphemes=[
                    dict(morph_surface='가상',pos='NNG')]))]),stream)
            self.write(folder/'RECEIPT.json',dict(binding=dict(contract_sha256=contract_hash,
                       source_file='sample'),outputs={'discourse.json.gz':dict(
                       sha256=a.sha(folder/'discourse.json.gz'),
                       bytes=(folder/'discourse.json.gz').stat().st_size)}))

    def tearDown(self):
        self.temp.cleanup()

    def write(self,path,value):
        path.write_text(json.dumps(value),encoding='utf8')

    def register(self):
        return a.register(self.catalog,'test',self.analysis,self.audit,self.dictionary,self.receipt)

    def test_group_lookup_and_selected_context(self):
        release=self.register()
        result=a.dictionary_groups(release,'가상','NNG','2')
        self.assertEqual(len(result['candidate_groups']),2)
        self.assertEqual(result['machine_group_id'],'10')
        self.assertEqual(len(result['candidate_groups'][0]['entries']),2)
        self.assertEqual(a.context(self.catalog,'test','modu','sample','u1')['selected_release'],'test')

    def test_audit_required(self):
        self.write(self.audit,dict(status='pending'))
        with self.assertRaises(ValueError):self.register()
        self.assertFalse(self.catalog.exists())

    def test_changed_receipt_rejected(self):
        self.register()
        self.write(self.analysis/'full/modu/sample/RECEIPT.json',{})
        with self.assertRaises(ValueError):a.context(self.catalog,'test','modu','sample','u1')

    def test_immutable_catalog(self):
        self.register()
        with self.assertRaises(FileExistsError):self.register()

    def test_changed_dictionary_rejected(self):
        release=self.register()
        with self.dictionary.open('ab') as stream:stream.write(b'x')
        with self.assertRaises(ValueError):a.dictionary_groups(release,'가상')

    def test_search_keeps_release_and_source_identity(self):
        self.register()
        result=a.search(self.catalog,'test','modu','가상','NNG',limit=1)
        self.assertEqual(result['rows'][0]['source'],'sample')
        self.assertEqual(result['rows'][0]['utterance_id'],'u1')
        self.assertTrue(result['stopped_at_limit'])

    def test_rebinding_changes_identity_and_does_not_inherit_decision(self):
        card=dict(occurrence_id='old',text='가상',target_begin=0,target_end=2,
                  lemma='가상',provisional_pos='NNG',selected_group='10',
                  assistant_proposal={'proposed_group':'10'},alternatives={})
        utterance=dict(original=dict(form='가상'),analysis=dict(morphemes=[
            dict(morph_begin_utf32=0,morph_length_utf32=2,morph_surface='가상',pos='NNG')]))
        with patch('build_release_data.releases.dictionary_groups',
                   return_value=dict(candidate_groups=[dict(group_id='20')])):
            result,groups,matched=rebind(card,utterance,'new',dict(dictionary_release='test'))
        self.assertTrue(matched)
        self.assertNotEqual(result['occurrence_id'],'old')
        self.assertIsNone(result['selected_group'])
        self.assertIsNone(result['assistant_proposal'])
        self.assertEqual(result['candidate_group_ids'],['20'])

    def test_changed_morphology_holds_dictionary_binding(self):
        card=dict(occurrence_id='old',text='가상',target_begin=0,target_end=2,
                  lemma='가상',provisional_pos='NNG',alternatives={})
        utterance=dict(original=dict(form='가상'),analysis=dict(morphemes=[]))
        result,groups,matched=rebind(card,utterance,'new',dict(dictionary_release='test'))
        self.assertFalse(matched)
        self.assertEqual(groups['candidate_groups'],[])


if __name__ == '__main__':
    unittest.main()

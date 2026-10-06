import csv
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/python'))
import build_delivery_semantic_links as m
import query_delivery_links as q


def fixture(base):
    root = base / 'package'; root.mkdir()
    role_names = ['current_cloud_20260926', 'modu_base_and_alignment', 'raw_transcripts_and_references',
                  'historical_context_export_20260928', 'modu_clips_and_recovered_ids', 'seoul_research_metadata']
    roles = {r:dict(role=r, source='F:/fixture/' + r, destination='data/' + r) for r in role_names}
    m.save(root/'CONTRACT.json',dict(config=dict(roots=list(roles.values()))))
    ledger = sqlite3.connect(root/'COPY_LEDGER.sqlite')
    ledger.execute('CREATE TABLE files(relative TEXT UNIQUE COLLATE NOCASE,bytes INTEGER,sha256 TEXT,copied INTEGER)')

    def put(role, sub, value, kind='bytes'):
        rel=roles[role]['destination']+'/'+sub; p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        if kind=='json':m.save(p,value)
        elif kind=='csv':
            with gzip.open(p,'wt',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(value[0]));w.writeheader();w.writerows(value)
        else:p.write_bytes(value)
        digest=m.sha(p);ledger.execute('INSERT INTO files VALUES(?,?,?,1)',(rel,p.stat().st_size,digest));return digest
    prod='current_cloud_20260926';source='NIKL_DIALOGUE_2020_v1.4/S.csv'
    analysis='modu/morphology/files/NIKL_DIALOGUE_2020_v1.4/S/analysis.json.gz'
    analysis_sha=put(prod,analysis,{},'json')
    put(prod,str(Path(analysis).parent).replace('\\','/')+'/morphemes.csv.gz',b'fixture')
    raw='NIKL_DIALOGUE_2020_v1.4/NIKL_DIALOGUE_2020_v1.4/S.json'
    raw_sha=put('raw_transcripts_and_references','dialogue_json/'+raw,{},'json')
    for name in ['word_intervals_mfa.csv.gz','phone_intervals_mfa.csv.gz','utterance_alignment.csv.gz','excluded_utterances.csv.gz','TABLES_MANIFEST.json']:
        put('modu_base_and_alignment','alignment/2020/'+name,b'fixture')
    for name in ['utterances.json.gz','morphemes.json.gz','json_alignment.json.gz','RECEIPT.json']:
        put('historical_context_export_20260928','files/NIKL_DIALOGUE_2020_v1.4/S/'+name,b'fixture')
    put('seoul_research_metadata','recordings.csv',b'source_file,wav_path,textgrid_path\n')
    tg='modu/alignment_textgrids_v1/textgrids/2020/S/S.1.TextGrid';tgsha=put(prod,tg,b'five-tier-fixture')
    put('modu_clips_and_recovered_ids','analysis_resolved_2020/S/S.1.wav',b'clip-fixture')
    native=[];links=[]
    for i,(uid,form,status) in enumerate([('S.1','가','response_saved'),('S.2','','empty_source_not_analyzed'),('S.3','나','response_saved_with_coverage_review')],1):
        response=dict(utt_id=uid,source_file=source,source_row_index=str(i),form=form)
        native.append(dict(utterance_id=uid,turn_order=i,original=dict(id=uid,form=form,start=i,end=i+0.5,speaker_id='speaker'),analysis=dict(status=status,input_and_response=response)))
        if form:
            links.append(dict(utt_id=uid,source_file=source,source_row_index=str(i),source_form_sha256=hashlib.sha256(form.encode()).hexdigest(),
                analysis_json=analysis,morphology_csv=str(Path(analysis).parent).replace('\\','/')+'/morphemes.csv.gz',
                word_alignment_table='F:/fixture/modu_base_and_alignment/alignment/2020/word_intervals_mfa.csv.gz',
                status='derived' if i==1 else 'no_mfa_alignment',textgrid_path=tg if i==1 else '',textgrid_sha256=tgsha if i==1 else '',token_to_word_mapping='not_established'))
    linkrel='modu/alignment_textgrids_v1/receipts/S/ANALYSIS_LINKS.csv.gz'
    linksha=put(prod,linkrel,links,'csv')
    put(prod,'modu/alignment_textgrids_v1/LINK_INDEX.csv.gz',[dict(source_file=source,links_relative=linkrel,sha256=linksha)],'csv')
    d=dict(discourse_id='S',utterances=native,provenance=dict(analysis_relative=analysis,analysis_sha256=analysis_sha,raw_relative=raw,raw_sha256=raw_sha))
    ds=put(prod,'discourse_json/modu/2020/S/S.json',d,'json')
    ledger.commit();ledger.close()
    return root,[dict(corpus='modu',year='2020',path='modu/2020/S/S.json',sha256=ds,expected_records=3)]


class SemanticLinksTests(unittest.TestCase):
    def test_roundtrip_resume_and_relocated_context(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,entries=fixture(base);out=root/'semantic_links';out.mkdir()
            p=m.Package(root)
            try:
                f=m.build(p,out,entries,sample=True)
                self.assertEqual(f['counts']['modu_empty_source_not_analyzed'],1)
                self.assertEqual(f['counts']['modu_no_mfa_alignment'],1)
                m.build(p,out,entries,sample=True)
            finally:p.db.close()
            relocated=base/'relocated';shutil.copytree(root,relocated)
            # The reader receives only the relocated package; all references are relative.
            result=q.context(relocated,relocated/'semantic_links','modu','S.2',2,True)
            self.assertEqual([r['utterance_id'] for r in result['utterances']],['S.1','S.2','S.3'])
            self.assertEqual(result['links'][1]['clip_status'],'not_in_declared_copy_scope')
            self.assertEqual(result['links'][2]['analysis_status'],'response_saved_with_coverage_review')
            source=q.safe(relocated,result['source_discourse']['path']);source.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                q.context(relocated,relocated/'semantic_links','modu','S.2')

    def test_missing_aligned_clip_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root,entries=fixture(Path(temp));out=root/'semantic_links';out.mkdir()
            with closing(sqlite3.connect(root/'COPY_LEDGER.sqlite')) as db:
                db.execute("DELETE FROM files WHERE relative LIKE '%.wav'");db.commit()
            p=m.Package(root)
            try:
                with self.assertRaisesRegex(ValueError,'no verified clip'):m.build(p,out,entries,True)
            finally:p.db.close()

    def test_path_and_sha_guards(self):
        for rel in ['../a','F:/a','/a','a\\b']:
            with self.assertRaises(ValueError):m.relative(rel)
        with tempfile.TemporaryDirectory() as temp:
            root,_=fixture(Path(temp));p=m.Package(root)
            try:
                with self.assertRaises(ValueError):p.ref('seoul_research_metadata','recordings.csv','incorrect')
            finally:p.db.close()

    def test_full_scope_cannot_be_satisfied_by_sample(self):
        with self.assertRaises(ValueError):m.totals_check(m.Counter(modu_utterances=3),False)


if __name__=='__main__':unittest.main()

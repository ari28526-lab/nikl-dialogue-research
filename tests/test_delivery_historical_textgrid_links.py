from contextlib import closing
import csv
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import build_delivery_historical_textgrid_links as m
import query_delivery_historical_textgrid as q
c=m.common


def fixture(root):
    roles=[dict(role=r,source='X:/old/'+r,destination='history/'+r) for r in m.STORAGE.values()]
    c.save(root/'CONTRACT.json',dict(config=dict(roots=roles)))
    db=sqlite3.connect(root/'COPY_LEDGER.sqlite')
    db.execute('CREATE TABLE files(relative TEXT UNIQUE COLLATE NOCASE,bytes INTEGER,sha256 TEXT,copied INTEGER)')
    primary='history/old_textgrids_primary/'
    def add(rel,data):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        db.execute('INSERT INTO files VALUES(?,?,?,1)',(rel,len(data),c.sha(p)))
        return c.sha(p)
    rows=[]
    for uid,storage in [('S.1','external_d'),('S.2','local_c')]:
        rel='textgrids/2020/S/'+uid+'.TextGrid';data=b'old label'
        digest=add('history/'+m.STORAGE[storage]+'/'+rel,data)
        rows.append(dict(utt_id=uid,status='derived',storage_id=storage,derived_relative=rel,bytes=len(data),sha256=digest))
    rows.append(dict(utt_id='S.3',status='no_mfa_alignment',storage_id='',derived_relative='',bytes=0,sha256=''))
    inv='shards/S/OUTPUT_INVENTORY.tsv.gz';path=root/primary/inv;path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    invhash=add(primary+inv,path.read_bytes())
    key='files/S/RECEIPT.json';recpath='shards/S/SHARD_RECEIPT.json'
    rec=dict(status='completed',source_file='S.csv',bareun_receipt_relative=key,bareun_receipt_sha256='a'*64,
        output_inventory_relative=inv,output_inventory_sha256=invhash,counts=dict(utterances=3,derived=2,no_mfa_alignment=1))
    rhash=add(primary+recpath,json.dumps(rec).encode('utf-8'))
    add(primary+'SHARD_RECEIPT_INVENTORY.tsv',f'{key}\t{"a"*64}\texternal_d\t{recpath}\t{rhash}\n'.encode())
    db.commit();db.close()
    index=root/'metadata/semantic_links/UTTERANCE_INDEX.sqlite';index.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(index)) as s:
        s.execute('CREATE TABLE utterances(corpus TEXT,utterance_id TEXT,discourse_id TEXT,PRIMARY KEY(corpus,utterance_id))')
        s.executemany('INSERT INTO utterances VALUES(?,?,?)',[('modu','S.'+str(i),'S') for i in range(1,5)]);s.commit()
    return index


class HistoryTests(unittest.TestCase):
    def test_resume_relocate_missing_history_and_payload_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'package';root.mkdir();idx=fixture(root);out=root/'metadata/historical_textgrid_links'
            pkg=c.Package(root)
            try:
                a=m.build(pkg,out,idx,sample_limit=1);b=m.build(pkg,out,idx,sample_limit=1)
                self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['counts']['derived'],2)
            finally:pkg.db.close()
            moved=Path(d)/'moved';shutil.copytree(root,moved)
            result=q.query(moved,'S.2',True);self.assertIn('old_textgrids_spill',result['textgrid']['path'])
            self.assertEqual(q.query(moved,'S.3')['status'],'no_mfa_alignment')
            self.assertEqual(q.query(moved,'S.4')['status'],'no_historical_analysis_record')
            with self.assertRaisesRegex(ValueError,'Unknown'):q.query(moved,'S.5')
            (moved/result['textgrid']['path']).write_bytes(b'bad label')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):q.query(moved,'S.2',True)

    def test_resume_index_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);idx=fixture(root);out=root/'metadata/historical_textgrid_links';pkg=c.Package(root)
            try:
                m.build(pkg,out,idx,sample_limit=1)
                with closing(sqlite3.connect(out/'HISTORICAL_TEXTGRID_INDEX.sqlite')) as db:
                    db.execute("UPDATE links SET discourse_id='bad' WHERE utterance_id='S.1'");db.commit()
                with self.assertRaisesRegex(ValueError,'resume binding'):m.build(pkg,out,idx,sample_limit=1)
            finally:pkg.db.close()

    def test_unknown_native_or_bad_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);idx=fixture(root);out=root/'metadata/historical_textgrid_links';pkg=c.Package(root)
            try:
                with closing(sqlite3.connect(idx)) as db:db.execute("DELETE FROM utterances WHERE utterance_id='S.1'");db.commit()
                with self.assertRaisesRegex(ValueError,'missing from native'):m.build(pkg,out,idx,sample_limit=1)
            finally:pkg.db.close()


if __name__=='__main__':unittest.main()

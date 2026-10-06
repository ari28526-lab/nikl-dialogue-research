import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
import test_delivery_morphology_revision as fixture
import query_delivery_parquet as query
import regenerate_delivery_morphology_shard as m


class RMorphologyTests(unittest.TestCase):
    def setUp(self):
        fixture.MorphologyTests.setUp(self)
        fixture.MorphologyTests.applied(self)
        self.mirror=self.root/'base_mirror'
        folder=self.mirror/'version=bareun_3.2/corpus=modu/year=2020/table=morphemes/group-0001';folder.mkdir(parents=True)
        table=m.pq.ParquetFile(self.base/'export/morphemes.parquet').read()
        rows=table.to_pylist();outside=dict(rows[0],_source_csv='other/morphemes.csv.gz',utt_id='outside',pos='VV')
        m.pq.write_table(m.pa.Table.from_pylist([rows[0],outside],schema=table.schema),folder/'part-0001.parquet')
        moved=self.base/'relocated';shutil.copytree(self.root,moved);self.root=moved;self.mirror=self.root/'base_mirror'
    def tearDown(self):self.temp.cleanup()
    def test_independent_R_selected_aggregation_after_relocation(self):
        script=Path(__file__).resolve().parents[1]/'scripts/R/query_delivery_morphology_revision.R'
        out=self.base/'R-query.json'
        library=Path(os.environ.get('DELIVERY_R_LIBRARY',
            str(Path(__file__).resolve().parents[1]/'work/r_delivery_library')))
        env=os.environ.copy()
        for key in ('LC_ALL','LC_CTYPE','LANG'):env[key]=''
        rscript=os.environ.get('DELIVERY_RSCRIPT') or shutil.which('Rscript') or r'C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe'
        if not Path(rscript).is_file():self.skipTest('Rscript is required for independent R aggregation')
        cmd=[rscript,str(script),sys.executable,str(self.root),str(self.mirror),'r1_tables',str(out),str(library)]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(out.read_text(encoding='utf-8'))
        expected=query.query(self.mirror,'bareun_3.2',package=self.root,revision='r1_tables')
        for key in ('rows','counts','selected_keys','selected_revision','files'):self.assertEqual(actual[key],expected[key])
        self.assertEqual(actual['counts'],{'NNG':3,'VV':1})


if __name__=='__main__':unittest.main()

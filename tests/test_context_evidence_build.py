"""Data-construction tests: provenance recovery and explicit native label separation."""
import json, sqlite3, sys, tempfile, unittest, zipfile, zlib
from unittest.mock import patch
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from build_context_evidence import corpus, schema, sejong, sentence_patterns, urimal
from compile_context_dictionary import binding,compile_unit

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name);self.c=sqlite3.connect(':memory:');schema(self.c)
    def tearDown(self):self.c.close();self.t.cleanup()
    def test_native_labels_full_morphology_context_and_relations(self):
        s={'id':'s1','form':'a b','word':[{'id':1},{'id':2}],'MP':[{'id':1,'word_id':1,'form':'a','label':'NNG'},{'id':2,'word_id':1,'form':'j','label':'JKO'},{'id':3,'word_id':2,'form':'b','label':'VV'}],'WSD':[{'form':'a','pos':'NNG','word_id':1,'sense_id':'777','begin':0,'end':1}],'SRL':[{'predicate':{'lemma':'b'},'argument':[{'label':'ARG1','word_id':[1]}]}]}
        p=self.p/'corpus.json';p.write_text(json.dumps({'document':[{'id':'d1','sentence':[s,{'id':'s2','form':'no WSD','word':[],'MP':[]}]}]}),encoding='utf-8')
        co=Counter();corpus(self.c,[p],co,{'id':'test'})
        self.assertEqual(co['sentences'],2);self.assertEqual(co['morphemes_preserved'],3)
        a=self.c.execute('SELECT native_code,word_pattern,raw FROM occurrences').fetchone()
        self.assertEqual(a[0],'777');self.assertIn('JKO',a[1]);self.assertEqual(json.loads(zlib.decompress(a[2])),s['WSD'][0])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM relations').fetchone()[0],1)
        self.assertEqual(json.loads(zlib.decompress(self.c.execute('SELECT raw FROM sentences WHERE native_id="s1"').fetchone()[0])),s)
    def test_duplicate_words_fail(self):
        with self.assertRaisesRegex(ValueError,'duplicate_word_id'):sentence_patterns({'word':[{'id':1},{'id':1}]})
    def test_special_and_incompatible_entries_never_link(self):
        cs=[{'group':'g1','sense_no':'001','state':'compatible'},{'group':'g2','sense_no':'001','state':'incompatible'}]
        state,rows=binding(cs,'001');self.assertEqual(state,'snapshot_code_match_candidate');self.assertEqual([x['group'] for x in rows],['g1'])
        self.assertEqual(binding(cs,'777')[1],[])
        cs[1]['state']='compatible';self.assertEqual(binding(cs,'001')[0],'multiple_snapshot_groups')
    def test_complete_dictionary_keeps_competing_native_codes(self):
        src=sqlite3.connect(self.p/'test.sqlite');schema(src)
        sentences=[]
        for i,code in enumerate(['001','002']):
            sentences.append({'id':str(i),'form':'a b','word':[{'id':1},{'id':2}],'MP':[{'word_id':1,'form':'a','label':'NNG'},{'word_id':2,'form':'b','label':'NNG'}],'WSD':[{'form':'a','pos':'NNG','sense_id':code,'word_id':1}]})
        p=self.p/'input.json';p.write_text(json.dumps({'document':[{'id':'d','sentence':sentences}]}),encoding='utf-8')
        corpus(src,[p],Counter(),{'id':'test'});src.commit();src.close()
        lex=sqlite3.connect(self.p/'urimalsaem.sqlite');lex.execute('CREATE TABLE entries(target TEXT,group_id TEXT,sense_no TEXT,word TEXT,lemma TEXT,pos TEXT,definition TEXT)')
        lex.executemany('INSERT INTO entries VALUES(?,?,?,?,?,?,?)',[('t1','g1','001','a','a','명사','one'),('t2','g2','002','a','a','명사','two')]);lex.commit();lex.close()
        with patch('compile_context_dictionary.OUT',self.p):compile_unit('test')
        check=sqlite3.connect(self.p/'test.dictionary.sqlite')
        self.assertEqual(check.execute('SELECT COUNT(*) FROM patterns').fetchone()[0],2)
        self.assertEqual(check.execute('SELECT SUM(occurrences) FROM bindings').fetchone()[0],2)
        self.assertEqual(check.execute('SELECT COUNT(DISTINCT native_code) FROM patterns').fetchone()[0],2);check.close()
    def test_sejong_relation_fields_and_xml_recovery(self):
        xml=b'<superEntry><orth>a b</orth><entry n="1"><head_grp><col_b>b</col_b><col_c>a</col_c></head_grp><sense n="1"><sem_grp><sel_rst arg="X">human</sel_rst></sem_grp><syn_grp><frame_grp><frame>X b</frame><eg>example</eg></frame_grp></syn_grp></sense></entry></superEntry>'
        p=self.p/'x.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('x.xml',xml);z.writestr('bad.xml',b'<broken>')
        co=Counter();sejong(self.c,[p],co)
        a=self.c.execute('SELECT base,collocate,fields_json FROM collocations').fetchone()
        self.assertEqual(a[:2],('b','a'));self.assertIn('sel_rst',a[2]);self.assertEqual(co['xml_parse_issues'],1)
        self.assertEqual(zlib.decompress(self.c.execute('SELECT raw FROM members WHERE name="x.xml"').fetchone()[0]),xml)

if __name__=='__main__':unittest.main()

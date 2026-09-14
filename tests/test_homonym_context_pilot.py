import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from homonym_context_core import (ArrayStream, candidates, lexicon_index, native_mapping,
    document_extract, build_dictionary, apply_dictionary, feature_inventory)
from run_homonym_context_pilot import Run, atomic, read, sha, exclusive, guard_held, verify_output, select_documents


def sentence(sid='D.1', form='배를 탔다'):
    return dict(id=sid,form=form,
        word=[dict(id=1,form='배를',begin=0,end=2),dict(id=2,form='탔다',begin=3,end=5)],
        MP=[dict(id=1,form='배',label='NNG',word_id=1,position=1),
            dict(id=2,form='를',label='JKO',word_id=1,position=2),
            dict(id=3,form='타',label='VV',word_id=2,position=1),
            dict(id=4,form='았',label='EP',word_id=2,position=2),
            dict(id=5,form='다',label='EF',word_id=2,position=3)],
        WSD=[dict(form='배',pos='NNG',sense_id='002',word_id=1,begin=0,end=1)])


def entries():
    return [dict(target_code=10,group_code=100,wordinfo={'word':'배'},senseinfo={'pos':'명사','sense_no':'001'}),
            dict(target_code=11,group_code=200,wordinfo={'word':'배'},senseinfo={'pos':'명사','sense_no':'002'}),
            dict(target_code=12,group_code=200,wordinfo={'word':'배'},senseinfo={'pos':'명사','sense_no':'003'})]


def bundle(sid='D.1'):
    return document_extract('source',dict(id=sid.split('.')[0],sentence=[sentence(sid)]),lexicon_index(entries()))


class StreamTests(unittest.TestCase):
    def parse(self, text, path=['document'], chunk=2):
        return list(ArrayStream(io.StringIO(text),chunk=chunk).items(path))

    def test_tiny_chunks_unicode_numbers_and_nested_container(self):
        obj={'channel':{'item':[{'word':'눈','number':1234}, {'n':-12.35e4}]},'meta':[1,2]}
        self.assertEqual(self.parse(json.dumps(obj,ensure_ascii=False),['channel','item']),obj['channel']['item'])

    def test_duplicate_nested_keys_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.parse('{"document":[{"x":1,"x":2}]}')

    def test_truncation_and_trailing_content_rejected(self):
        for text in ['{"document":[{}]', '{"document":[{},]}', '{"document":[]}x', '{"document":[],}', '{"other":[]}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_memory_guard(self):
        with self.assertRaisesRegex(ValueError,'memory_guard'):
            list(ArrayStream(io.StringIO('{"document":["'+'x'*100+'"]}'),chunk=3,max_chars=20).items(['document']))


class LinguisticTests(unittest.TestCase):
    def test_subsenses_collapse_and_homonyms_stay_separate(self):
        cs=candidates(lexicon_index(entries()),'배','NNG')
        self.assertEqual({e['group_code'] for e in cs},{100,200})
        self.assertEqual(native_mapping({'sense_id':'003'},cs)['group'],200)
        self.assertEqual(len(cs),3)

    def test_special_codes_not_used_as_labels(self):
        for v in ['777','888','999',True,1.0,[], 'abc']:
            self.assertIsNone(native_mapping({'sense_id':v},entries())['group'])

    def test_all_morphemes_and_raw_optional_layers_preserved(self):
        s=sentence();s['DP']=[{'word_id':[]}];s['ZA']={'bad':'source_shape'}
        doc={'id':'D','metadata':{'topic':'test'},'sentence':[s]}
        b=document_extract('s',doc,lexicon_index(entries()))
        self.assertEqual(len(b['morphemes']),5)
        self.assertEqual(b['raw_document'],doc)
        self.assertEqual(b['native_annotations'][0]['state'],'linked')
        self.assertTrue(any(p['family']=='K17' for p in b['morphemes'][0]['patterns']))

    def test_no_wsd_sentence_still_preserved(self):
        s=sentence();del s['WSD']
        b=document_extract('s',{'id':'D','sentence':[s]},lexicon_index(entries()))
        self.assertEqual(len(b['morphemes']),5)
        self.assertEqual(b['native_annotations'],[])

    def test_float_boolean_and_negative_coordinates_hold(self):
        for v in [True,0.0,'0',-1]:
            s=sentence();s['WSD'][0]['begin']=v
            b=document_extract('s',{'id':'D','sentence':[s]},lexicon_index(entries()))
            self.assertIsNone(b['native_annotations'][0]['target_id'])

    def test_invalid_pos_and_mp_position_do_not_crash_or_drop(self):
        s=sentence();s['WSD'][0]['pos']=[];s['MP'][0]['position']=1.1
        b=document_extract('s',{'id':'D','sentence':[s]},lexicon_index(entries()))
        self.assertEqual(len(b['morphemes']),5)
        self.assertEqual(b['native_annotations'][0]['state'],'annotation_schema_hold')

    def test_zero_width_and_compound_are_explicit_holds(self):
        s=sentence();s['WSD'][0]['end']=0
        b=document_extract('s',{'id':'D','sentence':[s]},lexicon_index(entries()))
        self.assertEqual(b['native_annotations'][0]['state'],'zero_width_native_span_hold')
        s=sentence();s['WSD'][0]['form']='배타'
        b=document_extract('s',{'id':'D','sentence':[s]},lexicon_index(entries()))
        self.assertEqual(b['native_annotations'][0]['state'],'compound_or_ambiguous_mp_span_hold')

    def test_same_context_new_document_prediction_without_gold_access(self):
        train=bundle('TRAIN.1');check=bundle('CHECK.1')
        dictionary=build_dictionary([train])
        check['native_annotations']=[]
        result=apply_dictionary(check,dictionary)
        self.assertEqual(result[0]['selected_group'],200)
        self.assertEqual(result[0]['method'],'context_dictionary')
        self.assertEqual(len(result),5)

    def test_competing_homonyms_produce_conflict(self):
        a=bundle('A.1');b=bundle('B.1')
        b['native_annotations'][0]['mapping']['group']=100
        result=apply_dictionary(bundle('C.1'),build_dictionary([a,b]))
        self.assertEqual(result[0]['state'],'context_conflict')
        self.assertIsNone(result[0]['selected_group'])

    def test_every_pattern_reports_implementation_state(self):
        self.assertEqual(set(feature_inventory()),{f'K{i:02d}' for i in range(1,33)})
        self.assertEqual(sum(v['status']=='implemented_mp_candidate' for v in feature_inventory().values()),5)

    def test_duplicate_sentence_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            document_extract('s',{'id':'D','sentence':[sentence(),sentence()]},{})


class ContinuationTests(unittest.TestCase):
    def test_completed_units_skip_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Run(Path(temp),{});r.pulse=lambda *a,**k:None
            self.assertEqual(r.unit('x.json',{'sha':'a'},lambda:{'x':1}),{'x':1})
            self.assertEqual(r.unit('x.json',{'sha':'a'},lambda:self.fail('rerun')),{'x':1})
            with self.assertRaisesRegex(RuntimeError,'changed'):
                r.unit('x.json',{'sha':'b'},lambda:{})
            atomic(Path(temp)/'x.json',{'x':2})
            with self.assertRaisesRegex(RuntimeError,'changed'):
                r.unit('x.json',{'sha':'a'},lambda:{})

    def test_uncommitted_data_recovered_only_if_same(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Run(Path(temp),{});r.pulse=lambda *a,**k:None
            atomic(Path(temp)/'x.json',{'a':1})
            self.assertEqual(r.unit('x.json',{},lambda:{'a':1}),{'a':1})
            atomic(Path(temp)/'y.json',{'a':1})
            with self.assertRaisesRegex(RuntimeError,'differs'):
                r.unit('y.json',{},lambda:{'a':2})
            self.assertEqual(read(Path(temp)/'y.json'),{'a':1})

    def test_exception_does_not_commit_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Run(Path(temp),{});r.pulse=lambda *a,**k:None
            def fail():raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):r.unit('x.json',{},fail)
            self.assertFalse((Path(temp)/'x.json.receipt.json').exists())
            self.assertEqual(r.unit('x.json',{},lambda:{'ok':True}),{'ok':True})

    def test_selection_groups_and_prefix_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source.json'
            atomic(p,{'document':[{'id':x,'sentence':[]} for x in ['A.1','A.2','B.1','C.1']]})
            result=select_documents(p,{'documents_per_source':3,'maximum_documents_scanned_per_source':10},lambda:None)
            self.assertEqual([d['original_group'] for d in result['documents']],['A','B','C'])
            self.assertEqual(result['scanned_prefix_documents'],4)
            self.assertIn('prefix',result['source_parse_scope'])

    def test_empty_audit_never_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,'empty'):
                verify_output(Path(temp),[])

    @unittest.skipUnless(sys.platform=='win32','Windows file lock')
    def test_guard_blocks_second_process_and_recovers(self):
        with tempfile.TemporaryDirectory() as temp:
            with exclusive(Path(temp)):
                script='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from run_homonym_context_pilot import guard_held;print(guard_held(Path(sys.argv[2])))'
                out=subprocess.check_output([sys.executable,'-c',script,str(Path(__file__).resolve().parents[1]/'scripts/python'),temp],text=True)
                self.assertEqual(out.strip(),'True')
            self.assertFalse(guard_held(Path(temp)))


if __name__=='__main__':unittest.main()

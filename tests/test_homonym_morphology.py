"""Counterexamples for morphological linking and bounded context evidence."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from homonym_context_core import lexicon_index, document_extract, build_dictionary, apply_dictionary
from homonym_morphology import analyze_candidates, structure_features


def entry(tid,group,word,pos,definition):
    return dict(target_code=tid,group_code=group,wordinfo={'word':word},
                senseinfo={'pos':pos,'definition':definition,'sense_no':'001'})


def sent(words, sid='D.1'):
    """words = [(surface, [(lemma, pos), ...]), ...]."""
    form=' '.join(w[0] for w in words); ws=[];mp=[];offset=0
    for wid,(surface,parts) in enumerate(words,1):
        ws.append(dict(id=wid,form=surface,begin=offset,end=offset+len(surface)))
        offset+=len(surface)+1
        for position,(lemma,pos) in enumerate(parts,1):
            mp.append(dict(id=len(mp)+1,form=lemma,label=pos,word_id=wid,position=position))
    return dict(id=sid,form=form,word=ws,MP=mp)


def derive(sentence, entries):
    return document_extract('test',{'id':'D','sentence':[sentence]},lexicon_index(entries),morphology_first=True)


class MorphologyTests(unittest.TestCase):
    def test_verb_suffix_restoration_and_derived_pos(self):
        es=[entry(1,10,'-하','접사','아래의 뜻을 더하는 접미사.'),
            entry(2,20,'-하다','접사','동사를 만드는 접미사.'),
            entry(3,20,'-하다','접사','형용사를 만드는 접미사.'),
            entry(4,30,'하다','동사','행동하다.')]
        b=derive(sent([('이용해서',[('이용','NNG'),('하','XSV'),('아서','EC')])]),es)
        d=apply_dictionary(b,[])[1]
        self.assertEqual(d['selected_group'],20)
        self.assertEqual(d['method'],'morphology_single_group')
        self.assertEqual(b['morphemes'][1]['candidate_entry_ids'],[2])
        b2=derive(sent([('건강해서',[('건강','NNG'),('하','XSA'),('아서','EC')])]),es)
        self.assertEqual(b2['morphemes'][1]['candidate_entry_ids'],[3])
        standalone=derive(sent([('하다',[('하','VV'),('다','EF')])]),es)
        self.assertEqual(apply_dictionary(standalone,[])[0]['selected_group'],30)

    def test_prefix_suffix_direction_and_nominal_ha(self):
        es=[entry(1,10,'들-','접사','야생의 뜻을 더하는 접두사.'),
            entry(2,20,'-들','접사','복수의 뜻을 더하는 접미사.'),
            entry(3,30,'-하','접사','환경의 뜻을 더하는 접미사.')]
        b=derive(sent([('어른들',[('어른','NNG'),('들','XSN')])]),es)
        self.assertEqual(apply_dictionary(b,[])[1]['selected_group'],20)
        p=derive(sent([('들꽃',[('들','XPN'),('꽃','NNG')])]),es)
        self.assertEqual(apply_dictionary(p,[])[0]['selected_group'],10)
        n=derive(sent([('식민지하',[('식민지','NNG'),('하','XSN')])]),es)
        self.assertEqual(apply_dictionary(n,[])[1]['selected_group'],30)

    def test_unknown_metadata_and_missing_base_never_force_link(self):
        es=[entry(1,10,'-하다','접사','의미 정보 없음')]
        b=derive(sent([('이용하다',[('이용','NNG'),('하','XSV'),('다','EF')])]),es)
        self.assertIsNone(apply_dictionary(b,[])[1]['selected_group'])
        self.assertEqual(b['morphemes'][1]['candidates'],[10])
        es=[entry(2,20,'-하다','접사','동사를 만드는 접미사.')]
        b=derive(sent([('하다',[('하','XSV'),('다','EF')])]),es)
        self.assertEqual(apply_dictionary(b,[])[0]['state'],'morphology_structure_hold')

    def test_dependent_noun_uses_entry_pos_but_retains_homonym_alternatives(self):
        es=[entry(1,10,'수','명사','수컷.'),entry(2,20,'수','의존 명사','가능성.'),
            entry(3,30,'수','의존 명사','세는 단위.')]
        b=derive(sent([('수',[('수','NNB')])]),es)
        self.assertEqual(b['morphemes'][0]['candidates'],[20,30])
        self.assertIsNone(apply_dictionary(b,[])[0]['selected_group'])

    def test_normalized_patterns_retain_particles_and_all_original_morphs(self):
        a=derive(sent([('배를',[('배','NNG'),('를','JKO')]),('탔다',[('타','VV'),('았','EP'),('다','EF')])]),[])
        b=derive(sent([('배를',[('배','NNG'),('를','JKO')]),('타요',[('타','VV'),('요','EF')])]),[])
        c=derive(sent([('배가',[('배','NNG'),('가','JKS')]),('타요',[('타','VV'),('요','EF')])]),[])
        ids=lambda x:{p['id'] for p in x['morphemes'][0]['patterns'] if p['family']=='M01'}
        self.assertTrue(ids(a)&ids(b));self.assertFalse(ids(b)&ids(c))
        self.assertEqual(len(a['morphemes']),5)
        self.assertTrue(any(m['form']=='았' for p in a['morphemes'][0]['patterns'] if p['family']=='M01' for m in p['evidence']['original_mp']))

    def test_conflicting_patterns_remain_unselected(self):
        es=[entry(1,10,'배','명사','배1'),entry(2,20,'배','명사','배2')]
        b=derive(sent([('배를',[('배','NNG'),('를','JKO')]),('타요',[('타','VV'),('요','EF')])]),es)
        p=b['morphemes'][0]['patterns'][0]
        self.assertEqual(apply_dictionary(b,[dict(id=p['id'],groups={'10':{},'20':{}})])[0]['state'],'context_conflict')

    def test_food_compound_and_eat_window_do_not_read_gold(self):
        es=[entry(1,10,'새우','명사','진흙.'),entry(2,20,'새우','명사','식용하는 동물.'),
            entry(3,30,'버섯-탕','명사','버섯을 넣어 끓인 국.'),entry(4,40,'먹다','동사','음식 따위를 입을 통하여 들여보내다.')]
        b=derive(sent([('새우버섯탕',[('새우','NNG'),('버섯탕','NNG')])]),es)
        b['native_annotations']=[{'fake_gold':10}]
        d=apply_dictionary(b,[],semantic_index=lexicon_index(es))[0]
        self.assertEqual(d['selected_group'],20)
        self.assertEqual(d['method'],'dictionary_food_compound')
        self.assertEqual(d['context_evidence']['anchors'][0]['lemma'],'버섯탕')
        # Neighboring 먹다 is visible as a suggestion and is never enough by itself.
        b=derive(sent([('새우',[('새우','NNG')])]),es)
        b['raw_document']['sentence'].append(sent([('먹었다',[('먹','VV'),('었','EP'),('다','EF')])],'D.2'))
        d=apply_dictionary(b,[],semantic_index=lexicon_index(es))[0]
        self.assertIsNone(d['selected_group']);self.assertEqual(d['context_evidence']['proposed_group'],20)
        self.assertEqual(d['context_evidence']['anchors'][0]['offset'],1)
        b['raw_document']['sentence']=b['raw_document']['sentence'][:1]
        self.assertEqual(apply_dictionary(b,[],semantic_index=lexicon_index(es))[0]['context_evidence']['anchors'],[])

    def test_food_rule_is_reusable_and_ambiguous_food_groups_stay_open(self):
        for lemma,dish in [('밤','죽'),('배','주스'),('게','탕')]:
            with self.subTest(lemma=lemma):
                es=[entry(1,10,lemma,'명사','음식과 무관한 별도 항목.'),
                    entry(2,20,lemma,'명사','식용하는 재료.'),entry(3,30,dish,'명사','끓인 국.')]
                # Negative definition deliberately avoids matching the broad food keyword.
                es[0]['senseinfo']['definition']='별도 동형어 항목.'
                b=derive(sent([(lemma+dish,[(lemma,'NNG'),(dish,'NNG')])]),es)
                self.assertEqual(apply_dictionary(b,[],semantic_index=lexicon_index(es))[0]['selected_group'],20)
                es.append(entry(4,40,lemma,'명사','식용하는 다른 재료.'))
                b=derive(sent([(lemma+dish,[(lemma,'NNG'),(dish,'NNG')])]),es)
                self.assertIsNone(apply_dictionary(b,[],semantic_index=lexicon_index(es))[0]['selected_group'])


if __name__=='__main__':unittest.main()

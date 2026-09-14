import json,sys,unittest
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/python'))
from context_full_features import Sentence,extract,za_links,signature
from context_full_lexicon import RX
from context_full_use import Dictionary
import sqlite3

class FakeLex:
    pairs=defaultdict(list,{'먹':[('밥',1)]})
    def analyze(self,lemma,pos):return {'common_classes':['FOOD'] if lemma in {'밥','버섯탕'} else [],'groups':['x']}

def sent(words,mid='s',speaker='a',**kw):
    form=' '.join(''.join(f for f,p in ms) for ms in words);mp=[];ws=[];i=0;begin=0
    for wi,ms in enumerate(words,1):
        text=''.join(f for f,p in ms);ws.append({'id':wi,'form':text,'begin':begin,'end':begin+len(text)});begin+=len(text)+1
        for pos,(f,p) in enumerate(ms,1):i+=1;mp.append({'id':i,'form':f,'label':p,'word_id':wi,'position':pos})
    return {'id':mid,'speaker_id':speaker,'form':form,'word':ws,'MP':mp,**kw}

class FeatureTests(unittest.TestCase):
    def test_exact_and_generalized_preserve_case_and_boundaries(self):
        s=sent([[('배','NNG'),('를','JKO')],[('아주','MAG')],[('먹','VV'),('었','EP'),('다','EF')]])
        v=Sentence(s,0,FakeLex());fs=extract(v,v.targets[0]);keys=[json.loads(k) for fam,k,kind in fs.values()]
        self.assertTrue(any(k[1]=='K01' and 'JKO' in str(k) for k in keys))
        self.assertTrue(any(k[1]=='K05' for k in keys))
        s2=sent([[('배','NNG'),('가','JKS')],[('아주','MAG')],[('먹','VV'),('었','EP'),('다','EF')]])
        v2=Sentence(s2,0,FakeLex());self.assertNotEqual(set(fs),set(extract(v2,v2.targets[0])))
    def test_compound_class_does_not_invent_morphemes(self):
        v=Sentence(sent([[('새우','NNG'),('버섯탕','NNG')]]),0,FakeLex());fs=extract(v,v.targets[0])
        kk=[json.loads(k) for fam,k,kind in fs.values() if fam=='K24_compound']
        self.assertEqual(len(kk),1);self.assertIn('<CLASS>',str(kk));self.assertEqual(v.seq[1],[['새우','NNG'],['버섯탕','NNG']])
    def test_invalid_relations_do_not_remove_MP_features(self):
        s=sent([[('배','NNG')],[('먹','VV')]],DP=[{'word_id':True,'head':2,'label':'NP'},{'word_id':1,'head':1,'label':'NP'}],SRL=[{'predicate':{'word_id':100},'argument':[]}])
        v=Sentence(s,0,FakeLex());fs=extract(v,v.targets[0]);self.assertTrue(any(f=='K01' for f,k,t in fs.values()));self.assertIn('DP_cycle',v.issues);self.assertIn('invalid_SRL_predicate',v.issues)
    def test_native_SRL_span_is_not_head_without_DP(self):
        s=sent([[('큰','MM')],[('배','NNG')],[('타','VV')]],SRL=[{'predicate':{'word_id':3},'argument':[{'label':'THM','word_id':[1,2]}]}])
        v=Sentence(s,0,FakeLex());fs=extract(v,next(m for m in v.targets if m['form']=='배'))
        self.assertTrue(any(f=='K22' and 'span_member' in k for f,k,t in fs.values()));self.assertFalse(any(f=='K23' for f,k,t in fs.values()))
    def test_ZA_requires_real_span_and_same_document(self):
        a=sent([[('밥','NNG')]],mid='a');b=sent([[('먹','VV')]],mid='b',ZA=[{'predicate':{'sentence_id':'b','word_id':1},'ellipsis':[{'restored':{'type':'object'},'antecedent':[{'sentence_id':'a','form':'밥','begin':0,'end':1},{'sentence_id':'missing','form':'#','begin':'','end':''}]}]}])
        views=[Sentence(a,0,FakeLex()),Sentence(b,1,FakeLex())];links,issues=za_links(views)
        self.assertEqual(issues['resolved_ZA_links'],1);self.assertEqual(issues['unresolved_or_invalid_ZA_antecedent'],1);self.assertIn(('a',1),links)
    def test_quotation_stays_in_condition_key(self):
        v=Sentence(sent([[('배','NNG')],[('라고','EC')],[('말하','VV')]]),0,FakeLex());fs=extract(v,v.targets[0]);self.assertTrue(all(json.loads(k)[-1][1] for f,k,t in fs.values()))
    def test_food_definition_cue_does_not_treat_any_food_mention_as_food(self):
        self.assertIsNone(RX['FOOD'].search('음식을 담는 그릇.'));self.assertIsNotNone(RX['FOOD'].search('버섯을 넣고 끓인 국.'))

class DecisionTests(unittest.TestCase):
    def dictionary(self,groups):
        class L(FakeLex):
            bygroup={}
            def analyze(self,lemma,pos):return {'groups':groups,'uncertain':[],'entries':[],'common_classes':[]}
        d=Dictionary.__new__(Dictionary);d.lex=L();d.units={};return d
    def test_morphology_singleton_wins_before_context(self):
        d=self.dictionary(['g']);v=Sentence(sent([[('배','NNG')]]),0,d.lex)
        self.assertEqual(d.decide(v,v.targets[0])['selected_group'],'g')
    def test_observed_competitors_hold_even_when_one_is_frequent(self):
        d=self.dictionary(['g1','g2']);v=Sentence(sent([[('배','NNG')],[('타','VV')]]),0,d.lex);m=v.targets[0]
        f=next((h,k) for h,(fam,k,t) in extract(v,m).items() if fam=='K03')
        c=sqlite3.connect(':memory:');c.execute('CREATE TABLE patterns(hash BLOB,group_id TEXT,label_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER)')
        c.executemany('INSERT INTO patterns VALUES(?,?,?,?,?,?,?)',[(f[0],'g1','native_snapshot_candidate',100,10,1,2),(f[0],'g2','native_snapshot_candidate',1,1,3,3)])
        d.units={'source':c};r=d.decide(v,m);self.assertIsNone(r['selected_group']);self.assertEqual(r['status'],'context_conflict');c.close()
    def test_repeated_machine_labels_cannot_become_native_support(self):
        d=self.dictionary(['g1','g2']);v=Sentence(sent([[('배','NNG')],[('타','VV')]]),0,d.lex);m=v.targets[0]
        h=next(h for h,(f,k,t) in extract(v,m).items() if f=='K03');c=sqlite3.connect(':memory:');c.execute('CREATE TABLE patterns(hash BLOB,group_id TEXT,label_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER)')
        c.execute('INSERT INTO patterns VALUES(?,?,?,?,?,?,?)',(h,'g1','morphology_machine',999,99,1,9));d.units={'source':c};self.assertIsNone(d.decide(v,m)['selected_group']);c.close()

    def test_context_free_ambiguity_does_not_veto_specific_context(self):
        d=self.dictionary(['g1','g2']);v=Sentence(sent([[('배','NNG')],[('먹','VV')]]),0,d.lex);m=v.targets[0]
        fs=extract(v,m);exact=next(h for h,(f,k,t) in fs.items() if f=='K03');weak=next(h for h,(f,k,t) in fs.items() if f=='K01')
        c=sqlite3.connect(':memory:');c.execute('CREATE TABLE patterns(hash BLOB,group_id TEXT,label_kind TEXT,occurrences INTEGER,documents INTEGER,first_target INTEGER,last_target INTEGER)')
        c.executemany('INSERT INTO patterns VALUES(?,?,?,?,?,?,?)',[(exact,'g1','native_snapshot_candidate',5,3,1,5),(weak,'g1','native_snapshot_candidate',100,10,1,10),(weak,'g2','native_snapshot_candidate',100,10,11,20)])
        d.units={'source':c};self.assertEqual(d.decide(v,m)['selected_group'],'g1');d.complete=False;self.assertIsNone(d.decide(v,m)['selected_group'])
        d.complete=True;d.verify_document_texts=True
        c.executescript("CREATE TABLE targets(id INTEGER PRIMARY KEY,document_id INTEGER); CREATE TABLE document_identity(id INTEGER PRIMARY KEY,text_hash TEXT); INSERT INTO targets VALUES(1,1),(5,2); INSERT INTO document_identity VALUES(1,'same'),(2,'same');")
        self.assertIsNone(d.decide(v,m)['selected_group'])
        c.execute("UPDATE document_identity SET text_hash='different' WHERE id=2")
        self.assertEqual(d.decide(v,m)['selected_group'],'g1');c.close()

    def test_ambiguous_anchor_cannot_circularly_select_food(self):
        d=self.dictionary(['food','other'])
        class L(FakeLex):
            bygroup={}
            def analyze(self,lemma,pos):return {'groups':['food','other'] if lemma=='배' else ['anchor_food','anchor_other'],'uncertain':[],'entries':[],'common_classes':[]}
        d.lex=L();d.food_hierarchy={'food':[{'path':'/food/'}],'anchor_food':[{'path':'/anchor_food/'}]}
        v=Sentence(sent([[('배','NNG'),('꿀','NNG')]]),0,d.lex);self.assertIsNone(d.decide(v,v.targets[0])['selected_group'])
        d.food_hierarchy['anchor_other']=[{'path':'/anchor_other/'}]
        self.assertEqual(d.decide(v,v.targets[0])['selected_group'],'food')

if __name__=='__main__':unittest.main()

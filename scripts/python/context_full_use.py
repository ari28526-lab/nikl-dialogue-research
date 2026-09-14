"""Usable dictionary interface: morphology first, evidence, machine choice or hold."""
import argparse,csv,gzip,json,sqlite3
from collections import Counter,defaultdict
from pathlib import Path
from context_full_lexicon import BASE,FULL,ROOT,SOURCES,Lexicon,ro,unpack
from context_full_features import Sentence,extract,za_links,signature,VERSION
from homonym_morphology import structure_features
from build_context_evidence import sha,js

STRONG={'K02','K03','K04','K05','K06','K07','K08','K09','K10','K11','K12','K13','K14','K15','K17','K18','K19','K20','K21','K22','K23','K25','K26','K28','K29','K31_ZA'}
POLICY={'minimum_native_occurrences':3,'minimum_source_documents':2,'document_proof':'first and last support point to two different full-document text hashes','allow_observed_competing_groups':False,'allow_unmapped_support_for_machine_choice':False,'conflict_scope':'concrete lexical, morphological or native relation families; context-free K01 and abstract/weak families are informational','meaning':'operational evidence floor, not a calibrated accuracy threshold'}

class Dictionary:
    def __init__(self):
        self.lex=Lexicon();self.units={n:ro(FULL/(n+'.sqlite')) for n in SOURCES if (FULL/(n+'.receipt.json')).exists()}
        self.complete=len(self.units)==len(SOURCES)
        self.verify_document_texts=True
        self.food_hierarchy=defaultdict(list)
        if (FULL/'semantic_graph.receipt.json').exists():
            graph=ro(FULL/'semantic_graph.sqlite')
            for group,root,target,depth,path in graph.execute("SELECT group_id,root,target,depth,path FROM proposals WHERE class='FOOD'"):
                self.food_hierarchy[group].append({'basis':'typed_dictionary_hierarchy_candidate','root_entry':root,'entry':target,'depth':depth,'path':path})
            graph.close()
    def close(self):
        for c in self.units.values():c.close()
        self.lex.close()
    def food_basis(self,group):
        result=[]
        if 'FOOD' in self.lex.bygroup.get(group,set()):result.append({'basis':'dictionary_definition_cue_candidate','group':group})
        result.extend(getattr(self,'food_hierarchy',{}).get(group,[]));return result
    def common_food_basis(self,lemma,pos):
        a=self.lex.analyze(lemma,pos)
        if a.get('uncertain') or not a['groups']:return []
        bygroup={g:self.food_basis(g) for g in a['groups']}
        return [{'group':g,'evidence':ev} for g,ev in bygroup.items()] if all(bygroup.values()) else []
    def decide(self,v,m,previous=()):
        ana=self.lex.analyze(m['form'],m['label']);groups=ana['groups'];st=structure_features(v.mp[m['word_id']],m)
        result={'lemma':m['form'],'pos':m['label'],'candidate_groups':groups,'selected_group':None,'proposed_groups':[],'status':'context_hold','reason':'후보를 구별할 충분한 문맥 조건을 찾지 못했습니다.','evidence':[],'native_morphology_source':v.raw.get('_analysis_source','provided_morphology'),'human_gold':False,'api_called':False}
        if st['issues']:result.update(status='structure_hold',reason='접사 위치나 구성의 확인이 필요합니다.',structure_issues=st['issues']);return result
        if not groups:result.update(status='no_dictionary_entry',reason='맞는 사전 항목이 없어 원형과 문맥을 보존합니다.');return result
        if ana['uncertain']:result.update(status='dictionary_metadata_hold',reason='사전 품사 또는 접사 기능 정보가 충분하지 않습니다.');return result
        if len(groups)==1:result.update(status='morphology_singleton_machine_link',selected_group=groups[0],reason='품사·접사 기능·구성에 맞는 사전 그룹이 하나입니다.');return result
        # Explicit compound class condition, never a fabricated suffix segmentation.
        foods=[g for g in groups if self.food_basis(g)]
        anchors=[x for x in v.mp[m['word_id']] if x['id']!=m['id'] and self.common_food_basis(x['form'],x['label'])]
        if len(foods)==1 and anchors and not v.guard[1]:
            result.update(status='dictionary_compound_class_machine_link',selected_group=foods[0],reason='같은 어절의 다른 구성 성분에 음식 단서가 있고, 표적의 음식 관련 후보는 하나입니다.',evidence=[{'family':'K24_compound','target_group':foods[0],'target_class_evidence':self.food_basis(foods[0]),'anchor':a['form'],'anchor_class_evidence':self.common_food_basis(a['form'],a['label']),'basis':'definition_or_typed_hierarchy_candidate_not_gold','policy':'same_word_other_constituent_all_anchor_groups_food'} for a in anchors]);return result
        feats=extract(v,m,previous)
        links,_=za_links([*previous,v])
        for link in links.get((v.raw['id'],m['word_id']),[]):
            key=[VERSION,'K31_ZA',m['form'],m['label'],m['position'],link,v.guard];feats[signature(key)]=('K31_ZA',js(key),'native_ZA_validated_span')
        qualified=set();observed=set();concrete_observed=set();all_evidence=[];hard_conflict=False
        for h,(family,key,kind) in feats.items():
            for name,c in self.units.items():
                rr=c.execute('SELECT group_id,label_kind,occurrences,documents,first_target,last_target FROM patterns WHERE hash=?',(h,)).fetchall()
                if not rr:continue
                totals=Counter();unmapped=0;docmax=defaultdict(int);example={}
                for group,label,n,nd,first,last in rr:
                    if label=='native_snapshot_candidate' and group in groups:totals[group]+=n;docmax[group]=max(docmax[group],nd);example[group]=[first,last]
                    else:unmapped+=n
                observed.update(totals)
                if family in STRONG:
                    concrete_observed.update(totals)
                    if len(totals)>1:hard_conflict=True
                for g,n in totals.items():
                    usable=family in STRONG and len(totals)==1 and unmapped==0 and n>=POLICY['minimum_native_occurrences'] and docmax[g]>=POLICY['minimum_source_documents']
                    doc_proof=[]
                    if usable and getattr(self,'verify_document_texts',False):
                        doc_proof=[{'document_id':did,'text_sha256':th} for did,th in c.execute('SELECT DISTINCT d.id,d.text_hash FROM targets t JOIN document_identity d ON d.id=t.document_id WHERE t.id IN (?,?)',example[g])]
                        usable=len({p['text_sha256'] for p in doc_proof})>=2
                    if usable:qualified.add(g)
                    all_evidence.append({'source':name,'family':family,'pattern_hash':h.hex(),'condition':json.loads(key),'group':g,'occurrences':n,'source_documents':docmax[g],'distinct_document_text_proof':doc_proof,'competing_groups':dict(totals),'unmapped_or_unannotated':unmapped,'qualifies_operational_floor':usable,'example_target_ids':example[g],'relation_kind':kind})
        result['evidence']=sorted(all_evidence,key=lambda e:(not e['qualifies_operational_floor'],-e['source_documents'],-e['occurrences']))[:12]
        result['matched_evidence_records']=len(all_evidence);result['proposed_groups']=sorted(observed)
        if len(qualified)==1 and not hard_conflict and concrete_observed.issubset(qualified) and not v.guard[1] and getattr(self,'complete',True):
            result.update(status='context_supported_machine_link',selected_group=next(iter(qualified)),reason='여러 원문서에서 확인된 구체 문맥이 한 후보를 지지하고, 일치한 구체 조건의 경쟁 의미는 관찰되지 않았습니다.')
        elif hard_conflict or len(qualified)>1:result.update(status='context_conflict',reason='일치하는 문맥 조건에서 서로 다른 의미가 관찰되어 후보를 유지합니다.')
        elif observed:result.update(reason='지지 용례는 있지만 독립 문서 지지나 번호·문맥 조건이 충분하지 않아 제안으로 남깁니다.')
        # Dialogue function from definitions is available even when native WSD omits IC.
        responses=[g for g in groups if 'RESPONSE' in self.lex.bygroup.get(g,set())]
        if m['label']=='IC' and len(responses)==1 and previous and not v.guard[1]:
            q=previous[-1];switch=q.raw.get('speaker_id') is not None and v.raw.get('speaker_id') is not None and q.raw['speaker_id']!=v.raw['speaker_id']
            question='?' in q.raw.get('form','')
            if switch and question and len(v.ids)<=5 and result['selected_group'] is None:
                result.update(status='dialogue_function_proposal',proposed_groups=sorted(set(result['proposed_groups'])|set(responses)),reason='화자가 바뀐 짧은 응답이며 사전의 대답 용법 후보가 있습니다. 대화 기능에 따른 제안으로 남깁니다.')
        return result

    def lookup(self,lemma,pos,limit=5):
        ana=self.lex.analyze(lemma,pos);groups=ana['groups'];out={'lemma':lemma,'pos':pos,'morphology':ana,'dictionary_entries':[],'dictionary_frames':[],'classes':[],'sources':{},'sejong':[],'policy':POLICY,'source_coverage':{'available':list(self.units),'missing':[n for n in SOURCES if n not in self.units]}}
        for g in groups:
            out['classes'].extend({'group':g,'target':tid,'class':cl,'basis':basis,'evidence':ev} for tid,cl,basis,ev in self.lex.sem.execute('SELECT target,class,basis,evidence FROM classes WHERE group_id=?',(g,)))
            for tid,sense,word,p,definition,raw in self.lex.lex.execute('SELECT target,sense_no,word,pos,definition,raw FROM entries WHERE group_id=?',(g,)):
                native=unpack(raw)['senseinfo'];out['dictionary_entries'].append({'group':g,'entry':tid,'sense_no':sense,'word':word,'pos':p,'definition':definition,'examples':native.get('example_info',[]),'relations':native.get('relation_info',[])})
            out['dictionary_frames'].extend({'group':g,'entry':tid,'kind':kind,'native':json.loads(value)} for tid,kind,value in self.lex.sem.execute('SELECT target,kind,text FROM dictionary_frames WHERE group_id=?',(g,)))
        for name,c in self.units.items():
            rows=c.execute('SELECT family,group_id,label_kind,occurrences,documents,first_target,key_json FROM patterns WHERE lemma=? AND pos=? ORDER BY documents DESC,occurrences DESC LIMIT ?',(lemma,pos,limit)).fetchall()
            out['sources'][name]=[{'family':f,'group':g,'label_kind':k,'occurrences':n,'documents':nd,'example_target_id':tid,'condition':json.loads(key)} for f,g,k,n,nd,tid,key in rows]
        # Keep the previously explored frequency and crosswalk resources usable.
        background=ro(BASE/'MP_background.sqlite')
        out['MP_background']=[{'source_id':si,'genre':{1:'written',2:'spoken'}.get(si),'frequency':n,'usage':'genre background, not the WSD pattern denominator'} for si,n in background.execute('SELECT source_id,frequency FROM frequencies WHERE form=? AND pos=?',(lemma,pos))];background.close()
        cross=ro(BASE/'lexicon_and_crosswalk.sqlite');forms={lemma,*[e['word'].replace('-','').replace('^','') for e in ana['entries']]}
        out['existing_lexicon_records']=[{'source_id':si,'record_id':rid,'native_record':unpack(raw),'state':'existing_analysis_not_promoted_to_gold'} for form in sorted(forms) for rid,si,raw in cross.execute('SELECT id,source_id,raw FROM records WHERE lemma=? LIMIT 20',(form,))];cross.close()
        for partner,cid in self.lex.pairs.get(lemma,[])[:limit]:
            row=self.lex.sem.execute('SELECT orth,fields_json FROM sejong_pairs WHERE id=?',(cid,)).fetchone();out['sejong'].append({'id':cid,'partner':partner,'orth':row[0],'fields':json.loads(row[1])})
        if (FULL/'semantic_graph.receipt.json').exists():
            graph=ro(FULL/'semantic_graph.sqlite');out['typed_hierarchy_proposals']=[]
            for g in groups:out['typed_hierarchy_proposals'].extend({'group':g,'class':cl,'seed_entry':root,'entry':target,'depth':depth,'path':path,'state':state} for cl,root,target,depth,path,state in graph.execute('SELECT class,root,target,depth,path,state FROM proposals WHERE group_id=?',(g,)))
            graph.close()
        if (FULL/'catalog.receipt.json').exists():
            cat=ro(FULL/'catalog.sqlite');out['lexical_distributions']=[dict(zip(['source','group','label_kind','occurrences','source_documents','first_target','last_target'],r)) for r in cat.execute('SELECT source,group_id,label_kind,occurrences,source_documents,first_target,last_target FROM lexical_distribution WHERE lemma=? AND pos=?',(lemma,pos))];cat.close()
        return out

    def example(self,source,target_id):
        c=self.units[source];r=c.execute('SELECT sentence_id,document_id,morph_id FROM targets WHERE id=?',(target_id,)).fetchone()
        if not r:raise ValueError('target_missing')
        sid,did,mid=r;b=ro(BASE/(source+'.sqlite'));ordinal=b.execute('SELECT ordinal FROM sentences WHERE id=?',(sid,)).fetchone()[0]
        rows=b.execute('SELECT id,ordinal,raw FROM sentences WHERE document_id=? AND ordinal BETWEEN ? AND ? ORDER BY ordinal',(did,ordinal-3,ordinal+3)).fetchall();b.close()
        return {'source':source,'target_id':target_id,'morph_id':mid,'target_sentence_id':sid,'context':[{'database_sentence_id':i,'ordinal':o,'original':unpack(raw)} for i,o,raw in rows]}

    def search(self,text,limit=5):
        literal='"'+text.replace('"','""')+'"';result={}
        for name,c in self.units.items():result[name]=[dict(zip(['sentence_id','document_id','native_id','text'],r)) for r in c.execute('SELECT sentence_id,document_id,native_id,text FROM utterance_search WHERE utterance_search MATCH ? LIMIT ?',(literal,limit))]
        return result

def bareun_check(path,output):
    path=Path(path);rp=path.parent/'RECEIPT.json';receipt=json.loads(rp.read_text(encoding='utf-8'));before=sha(path)
    if receipt.get('with_sense') is not False or receipt.get('status')!='completed' or receipt['outputs'][path.name]['sha256']!=before:raise ValueError('existing_Bareun_receipt_mismatch')
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    up=path.parent/'utterances.csv.gz'
    if sha(up)!=receipt['outputs'][up.name]['sha256']:raise ValueError('utterance_receipt_mismatch')
    with gzip.open(up,'rt',encoding='utf-8-sig',newline='') as f:utts=list(csv.DictReader(f))
    by=defaultdict(list)
    for r in rows:by[r['utt_id']].append(r)
    dictionary=Dictionary();views=[];result=[];counts=Counter()
    try:
        for ordinal,u in enumerate(utts):
            ur=by[u['utt_id']];wordrows={};mp=[]
            for r in ur:
                wi=int(r['token_index']);mi=int(r['morph_index']);begin=int(r['token_begin_utf32'])
                wordrows[wi]={'id':wi,'form':r['token_surface'],'begin':begin,'end':begin+int(r['token_length_utf32'])}
                mp.append({'id':mi,'form':r['morph_surface'],'label':r['pos'],'word_id':wi})
            raw={'id':u['utt_id'],'form':u.get('form',u.get('input_form','')),'speaker_id':u.get('speaker_id'),'word':list(wordrows.values()),'MP':mp,'_analysis_source':'existing_Bareun_v3.1'}
            v=Sentence(raw,ordinal,dictionary.lex);lookup={m['id']:m for m in v.targets}
            for r in ur:
                m=lookup.get(int(r['morph_index']))
                decision=dictionary.decide(v,m,views[-3:]) if m else {'status':'functional_or_other_preserved','selected_group':None}
                counts[decision['status']]+=1;result.append({'source_identity':{k:r[k] for k in ['source_file','utt_id','token_index','morph_index']},'raw_bareun':r,'dictionary_decision':decision})
            views.append(v)
        if len(result)!=len(rows) or len(rows)!=receipt['counts']['morphemes'] or sha(path)!=before:raise ValueError('preservation_check_failed')
        with Path(output).open('w',encoding='utf-8') as f:
            for r in result:f.write(js(r)+'\n')
        report={'status':'passed','source_sha256':before,'existing_receipt_sha256':sha(rp),'input_morphemes':len(rows),'utterances':len(utts),'counts':dict(counts),'output_sha256':sha(output),'api_called':False,'accuracy_evaluation':False,'policy':POLICY}
        Path(str(output)+'.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report
    finally:dictionary.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lemma');ap.add_argument('--pos');ap.add_argument('--search');ap.add_argument('--bareun-file');ap.add_argument('--source',choices=SOURCES);ap.add_argument('--target-id',type=int);ap.add_argument('--output',required=True);a=ap.parse_args()
    modes=sum(bool(x) for x in [a.lemma,a.search,a.bareun_file,a.source])
    if modes!=1 or (a.lemma and not a.pos) or (a.source and a.target_id is None):ap.error('choose lemma+pos, search, bareun-file, or source+target-id')
    if a.bareun_file:r=bareun_check(a.bareun_file,a.output)
    else:
        d=Dictionary()
        try:r=d.example(a.source,a.target_id) if a.source else d.search(a.search) if a.search else d.lookup(a.lemma,a.pos)
        finally:d.close()
        Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(js({'output':a.output,'status':r.get('status','written')}))
if __name__=='__main__':main()

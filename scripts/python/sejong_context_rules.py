"""Context-conditioned machine rules reviewed against Sejong examples and current definitions.

These are explicit research predictions, not user judgments or a global historical
number crosswalk. Every application still requires independent exact contexts.
"""
RULES = [
 ('degree','가장','MAG','01','11084','여럿 가운데 어느 것보다 정도가 높거나 세게.', ['0:107:4','0:439:0']),
 ('present','지금','MAG','03','867431','말하는 바로 이때에.', ['0:48:0','4:251:0']),
 ('become','되','VV','01','250997','어떤 일이 가능하거나 받아들여지다.', ['0:199:3','1:51:6']),
 ('case','경우','NNG','03','56331','놓여 있는 조건이나 놓이게 된 형편이나 사정.', ['8:91:3','8:188:4']),
 ('think','생각','NNG','01','496776','사물을 헤아리고 판단하는 작용.', ['0:136:5','0:346:2']),
 ('occur','들','VV','01','259978','의식이 회복되거나 어떤 생각이나 느낌이 일다.', ['0:92:7','1:204:12']),
 ('ability','수','NNB','02','540667','어떤 일을 할 만한 능력이나 어떤 일이 일어날 가능성.', ['0:475:5','10:85:5']),
 ('regarding','대하','VV','02','226037','대상이나 상대로 삼다.', ['1:220:3','1:242:7']),
 ('example','예','NNG','08','669434','본보기가 될 만한 사물.', ['3:428:0','3:453:3']),
 ('trip','여행','NNG','02','652782','일이나 유람을 목적으로 다른 고장이나 외국에 가는 일.', ['0:61:1']),
 ('ride','타','VV','02','955145','탈것이나 짐승의 등 따위에 몸을 얹다.', ['0:76:2']),
 ('inside','안','NNG','01','609907','어떤 물체나 공간의 둘러싸인 가에서 가운데로 향한 쪽. 또는 그런 곳이나 부분.', ['1:71:2']),
 ('amount','정도','NNG','11','822736','그만큼가량의 분량.', ['0:135:10']),
]

def guard(rule,pattern):
    """Require the reviewed semantic construction, not only matching a label."""
    name=rule[0];_,family,at,mi,words=pattern['condition']
    target=words[at];left=words[at-1] if at else [];right=words[at+1] if at+1<len(words) else []
    lf=left[0][0] if left else '';rf=right[0][0] if right else ''
    if name in {'degree','present'}:return True
    if name=='become':return any(p=='EC' and f in {'게','아야','어야','여야'} for f,p in left)
    if name=='case':return lf=='같' and any(p=='ETM' for f,p in left)
    if name=='think':return rf in {'하','들','나'} and any(p in {'JKO','JKS'} for f,p in target)
    if name=='occur':return lf in {'생각','느낌'} and any(p=='JKS' for f,p in left)
    if name=='ability':return any(p=='ETM' and f in {'ㄹ','을'} for f,p in left) and rf in {'있','없'}
    if name=='regarding':return any(p=='JKB' and f=='에' for f,p in left)
    if name=='example':return rf=='들' and ['를','JKO'] in target
    if name=='trip':return lf=='유럽'
    if name=='ride':return lf in {'관광버스','버스','기차','비행기','택시','지하철'} and any(p=='JKO' for f,p in left)
    if name=='inside':return lf=='손바닥' and ['에','JKB'] in target
    if name=='amount':return any(p=='NNB' and f in {'개','명','번','시간','년','개월','분'} for f,p in left)
    return False

def decide(x,proof):
    if x['category']!='context_supported_definition_pending':return None
    if x['prior_status']=='context_conflict':return None
    # A quote can mention a word without using its dictionary meaning.
    if any(q in x['form'] for q in ['"','“','”','‘','’']):return None
    found=[]
    for rule in RULES:
        rid,lemma,pos,native,group,definition,seeds=rule
        if (x['lemma'],x['pos'])!=(lemma,pos) or group not in x['candidate_groups']:continue
        for p in x['patterns']:
            if set(p['native_distribution'])!={native}:continue
            if p['source_files']<2 or p['observations']<3 or not guard(rule,p):continue
            independent=proof(p)
            if len(independent)<2:continue
            found.append({'rule':rid,'group':group,'definition':definition,'pattern_hash':p['hash'],'native_code':native,'independent_support':independent})
    if len({v['group'] for v in found})!=1:return None
    return {'selected_group':found[0]['group'],'status':'sejong_context_rule_machine_link','human_gold':False,'api_called':False,'evidence':found}

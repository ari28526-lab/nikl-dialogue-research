"""Bounded dictionary-grounded food cues; retain uncertain surrounding homonyms."""
import re
from homonym_context_core import NOUNS, sentence_view, markers
from homonym_morphology import analyze_candidates, structure_features

# These are inspectable dictionary-definition cues, not a complete semantic ontology.
FOOD = re.compile(r'식용|음식|끓인 국|끓여 만든 국|먹을 수 있도록 만든|먹고 마시는|먹을 때에|음식을 먹는')


def food_entries(entries):
    return [e for e in entries if FOOD.search(e.get('senseinfo',{}).get('definition',''))]


def food_context(bundle, row, index, max_turns=3):
    raw = bundle['raw_document']['sentence']
    at = next(i for i,s in enumerate(raw) if s['id']==row['sentence_id'])
    target = row['raw']
    entry_ids = set(row.get('candidate_entry_ids',[]))
    target_entries = {e['target_code']:e for v in index.values() for e in v if e['target_code'] in entry_ids}
    food = food_entries(target_entries.values())
    food_groups = sorted({e['group_code'] for e in food})
    anchors=[]
    for offset in [0]+[v for distance in range(1,max_turns+1) for v in (-distance,distance)]:
        if not 0 <= at+offset < len(raw): continue
        s=raw[at+offset];words,morphs,issues=sentence_view(s)
        if issues: continue
        for wid,ms in morphs.items():
            for m in ms:
                if offset==0 and m['id']==target['id']: continue
                kind=None;ids=[];unambiguous=False
                if m['label'] in NOUNS:
                    analysis=analyze_candidates(index,m['form'],m['label'],structure_features(ms,m))
                    candidates=[e for e in index.get(m['form'],[]) if e['target_code'] in analysis['candidate_entry_ids']]
                    foods=food_entries(candidates)
                    if foods:
                        kind='food_dictionary';ids=[e['target_code'] for e in foods]
                        unambiguous=(bool(analysis['candidate_groups']) and not analysis['uncertain_groups'] and
                                     set(analysis['candidate_groups'])=={e['group_code'] for e in foods})
                elif m['form']=='먹' and m['label']=='VV':
                    kind='eat_verb';ids=[e['target_code'] for e in index.get('먹다',[]) if '음식 따위를 입을 통하여' in e.get('senseinfo',{}).get('definition','')]
                if kind:
                    anchors.append(dict(kind=kind,lemma=m['form'],pos=m['label'],sentence_id=s['id'],
                        sentence_form=s['form'],word_id=wid,word_form=words[wid]['form'],
                        offset=offset,entry_ids=ids,unambiguous=unambiguous,
                        same_word=offset==0 and wid==target['word_id'],
                        markers=markers([x for v in morphs.values() for x in v])))
    direct=[a for a in anchors if a['kind']=='food_dictionary' and a['unambiguous'] and a['same_word'] and not a['markers']['quote_form']]
    local=[a for a in anchors if a['kind']=='food_dictionary' and a['unambiguous'] and a['offset']==0 and not a['markers']['quote_form']]
    nearby=[a for a in anchors if a['kind']=='food_dictionary' and a['unambiguous'] and not a['markers']['quote_form']]
    eat=[a for a in anchors if a['kind']=='eat_verb' and not a['markers']['quote_form']]
    group=food_groups[0] if len(food_groups)==1 else None
    # Cross-turn co-occurrence supplies suggestions, not an assumed syntactic relation.
    stage='same_word_food' if direct else 'same_sentence_food' if local else 'neighboring_food_or_eat' if nearby or eat else 'no_food_support'
    selected=group if group is not None and direct else None
    proposed=group if group is not None and (local or nearby or eat) else None
    return dict(selected_group=selected,proposed_group=proposed,stage=stage,anchors=anchors,
        candidate_food_groups=food_groups,target_definition_entry_ids=[e['target_code'] for e in food],
        window_previous=max_turns,window_next=max_turns,boundary='same_internal_document',
        relation='compound_co_members_or_context_cooccurrence_not_dependency',
        automatic_adoption=False,rule='food_definition_and_compound_v1',
        limitations='Dictionary keyword evidence is provisional; nearby eat may be figurative and never alone forces a group.')

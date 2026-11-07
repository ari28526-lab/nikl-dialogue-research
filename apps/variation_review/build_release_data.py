"""Rebind selected review cases to an audited analysis and dictionary release."""
import argparse
import copy
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/python'))
import analysis_release as releases
from annotation_protocol import digest


def rebind(card, utterance, version, dictionary):
    result = copy.deepcopy(card)
    original = utterance['original']
    rows = utterance['analysis']['morphemes']
    begin, end = card['target_begin'], card['target_end']
    text_matches = original.get('form') == card['text']
    overlapping = [row for row in rows
                   if row['morph_begin_utf32'] < end
                   and row['morph_begin_utf32'] + row['morph_length_utf32'] > begin]
    exact = [row for row in overlapping
             if row['morph_begin_utf32'] == begin
             and row['morph_length_utf32'] == end - begin
             and row.get('morph_surface', row.get('morph')) == card['lemma']
             and row['pos'] == card['provisional_pos']]
    matched = text_matches and len(exact) == 1
    result.update(
        parent_occurrence_id=card['occurrence_id'],
        occurrence_id=digest([version, card['occurrence_id']]),
        analysis_version=version, dictionary_version=dictionary['dictionary_release'],
        selected_analysis_text=original.get('form'),
        release_mapping='exact_surface_and_morphology' if matched else 'requires_morphology_review',
        assistant_proposal=None, selected_group=None, saved_machine_group=None,
        existing_judgment_id=None,
        alternatives=dict(before=card.get('alternatives', {}).get('after', []),
                          after=[[row['morph_begin_utf32'], row['morph_length_utf32'],
                                  row.get('morph_surface', row.get('morph')), row['pos']]
                                 for row in overlapping] if text_matches else []),
        morphology_gate='machine_analysis_requires_researcher_review',
        audio_verified=False,
    )
    if matched:
        groups = releases.dictionary_groups(dictionary, card['lemma'], card['provisional_pos'])
    else:
        groups = dict(candidate_groups=[])
        result['evidence_flags'] = list(result.get('evidence_flags', [])) + ['new_analysis_mapping_hold']
    result['candidate_group_ids'] = [row['group_id'] for row in groups['candidate_groups']]
    result['content_hash'] = digest({key:value for key,value in result.items() if key != 'content_hash'})
    return result, groups, matched


def build(dataset, catalog, version, output):
    source = releases.read(dataset)
    release = releases.read(catalog)['releases'][version]
    if output.exists():
        raise FileExistsError('A review snapshot already exists')
    cards, dictionary, counts = [], {}, Counter()
    by_source = {}
    for card in source['cards']:
        by_source.setdefault(card['source'], []).append(card)
    for identity, group in by_source.items():
        _, documents = releases.selected_source(catalog, version, 'modu', identity)
        utterances = {}
        for document in documents:
            for utterance in document['utterances']:
                uid = utterance['utterance_id']
                if uid in utterances:
                    raise ValueError('Ambiguous source utterance ID')
                utterances[uid] = utterance
        for card in group:
            if card['uid'] not in utterances:
                raise ValueError('Review occurrence is absent from the new release')
            new, groups, matched = rebind(card, utterances[card['uid']], version, release)
            # Candidate sets depend on this occurrence's verified coordinate mapping.
            new['question_group_id'] = digest([new['occurrence_id'], 'dictionary_candidates'])
            new['content_hash'] = digest({k:v for k,v in new.items() if k != 'content_hash'})
            cards.append(new)
            dictionary[new['question_group_id']] = groups
            counts['matched' if matched else 'mapping_hold'] += 1
    value = dict(
        schema='variation_workbench_dataset.v1', cards=cards, dictionary=dictionary,
        dictionary_version=release['dictionary_release'], analysis_version=version,
        guideline_version='group_id_review_v1',
        scope=f'{version}로 다시 연결한 기존 선택 검토 표본 {len(cards)}건',
        issues=['형태·문자 범위 대응 보류 사례는 사전 후보 선택 전에 형태 검토가 필요합니다.']
               if counts['mapping_hold'] else [],
        parent_dataset_sha256=releases.sha(dataset), analysis_catalog_sha256=releases.sha(catalog),
        grouping_note='동형이의어 Group ID 중심의 출현별 검토',
        mapping_counts=dict(counts),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False)
    return counts


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    print(json.dumps(dict(build(args.dataset,args.catalog,args.version,args.output))))

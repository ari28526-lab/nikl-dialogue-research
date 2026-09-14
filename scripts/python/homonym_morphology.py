"""Auditable MP-first dictionary compatibility; no WSD labels or user judgments."""
from homonym_context_core import POS, PREDS, NOUNS, clean_word, integer

VERSION = 'mp_first_v1'
AFFIXES = {'XPN', 'XSN', 'XSV', 'XSA'}


def citation_forms(lemma, pos):
    if pos in PREDS | {'XSV', 'XSA'}:
        return list(dict.fromkeys([lemma, lemma if lemma.endswith('다') else lemma + '다']))
    return [lemma]


def structure_features(ms, target):
    """Retain constituents and functional morphology, without inventing a parse."""
    ms = sorted(ms, key=lambda x: x['position'])
    at = next(i for i, m in enumerate(ms) if m['id'] == target['id'])
    before, after = ms[:at], ms[at+1:]
    issues = []
    if target['label'] in {'XSN', 'XSV', 'XSA'}:
        if not before or before[-1]['label'].startswith(('J', 'E', 'S')):
            issues.append('suffix_base_missing_or_incompatible')
    if target['label'] == 'XPN' and (not after or after[0]['label'].startswith(('J', 'E', 'S'))):
        issues.append('prefix_base_missing_or_incompatible')
    return dict(target_pos=target['label'], target_position=target['position'],
                before=before, after=after, word_morphemes=ms,
                particles=[m for m in ms if m['label'].startswith('J')],
                endings=[m for m in ms if m['label'].startswith('E')],
                issues=issues, state='structure_hold' if issues else 'native_mp_conditioned',
                source_analysis_is_gold=False)


def entry_compatibility(entry, lemma, pos):
    si, wi = entry.get('senseinfo', {}), entry.get('wordinfo', {})
    ep, word = si.get('pos'), wi.get('word', '')
    definition = si.get('definition', '')
    reasons, unknown = [], []
    allowed = ['의존 명사'] if pos == 'NNB' else POS.get(pos, [])
    if not ep:
        unknown.append('dictionary_pos_unspecified')
    elif ep not in allowed:
        reasons.append('dictionary_pos_incompatible')
    if pos in AFFIXES:
        prefix = ('접두사' in definition) or (word.endswith('-') and not word.startswith('-'))
        suffix = ('접미사' in definition) or (word.startswith('-') and not word.endswith('-'))
        direction = 'unknown' if prefix == suffix else 'prefix' if prefix else 'suffix'
        wanted = 'prefix' if pos == 'XPN' else 'suffix'
        if direction == 'unknown':
            unknown.append('affix_direction_unspecified_or_conflicting')
        elif direction != wanted:
            reasons.append('affix_direction_incompatible')
        # The dictionary stores conjugating derivational suffixes in citation form.
        if pos in {'XSV', 'XSA'} and clean_word(word) != citation_forms(lemma, pos)[-1]:
            reasons.append('derivational_citation_form_incompatible')
        if pos == 'XSN' and clean_word(word).endswith('다'):
            reasons.append('nominal_suffix_citation_form_incompatible')
        categories = set()
        if '동사나 형용사를 만드는' in definition or '동사 또는 형용사를 만드는' in definition:
            categories.update(['XSV', 'XSA'])
        for phrase, label in [('동사를 만드는', 'XSV'), ('형용사를 만드는', 'XSA'), ('명사를 만드는', 'XSN')]:
            if phrase in definition:
                categories.add(label)
        if categories and pos in {'XSV', 'XSA', 'XSN'} and pos not in categories:
            reasons.append('derived_pos_incompatible')
        elif pos in {'XSV', 'XSA'} and not categories:
            unknown.append('derived_pos_unspecified')
    return dict(state='incompatible' if reasons else 'unknown' if unknown else 'compatible',
                reasons=reasons, uncertainties=unknown)


def analyze_candidates(index, lemma, pos, structure=None):
    examined = {}
    for form in citation_forms(lemma, pos):
        for e in index.get(form, []):
            if integer(e.get('group_code')) and integer(e.get('target_code')):
                examined[e['target_code']] = e
    evidence, kept = [], []
    for tid, e in sorted(examined.items()):
        check = entry_compatibility(e, lemma, pos)
        evidence.append(dict(entry_id=tid, group=e['group_code'], word=e['wordinfo']['word'],
                             dictionary_pos=e.get('senseinfo', {}).get('pos'), **check))
        if check['state'] != 'incompatible':
            kept.append(e)
    groups = sorted({e['group_code'] for e in kept})
    compatible_groups = {e['group'] for e in evidence if e['state'] == 'compatible'}
    uncertain_groups = sorted({e['group'] for e in evidence if e['state'] == 'unknown'} - compatible_groups)
    structure_ok = structure is not None and not structure['issues']
    return dict(version=VERSION, lemma=lemma, pos=pos, lookup_forms=citation_forms(lemma, pos),
                all_groups=sorted({e['group_code'] for e in examined.values()}),
                candidate_groups=groups, candidate_entry_ids=sorted(e['target_code'] for e in kept),
                excluded_groups=sorted({e['group_code'] for e in examined.values()} - set(groups)),
                uncertain_groups=uncertain_groups, entry_checks=evidence,
                structure=structure, singleton_eligible=structure_ok and len(groups) == 1 and not uncertain_groups,
                state='structure_hold' if not structure_ok else 'no_compatible_entry' if not groups else
                      'dictionary_metadata_hold' if uncertain_groups else 'compatible_candidates')


def normalized_patterns(sent, target, words, morphs):
    """Constituent sequences retaining J forms and clause types; E detail in evidence.

    Never emit a context-free single lexical lemma as a disambiguation feature.
    Negation and quotation stay in the key. Word order and target position stay fixed.
    """
    from homonym_context_core import digest, LEXICAL, markers
    ids = list(words); at = ids.index(target['word_id']); result = {}
    for width in (1, 2, 3):
        for left in range(max(0, at-width+1), min(at, len(ids)-width)+1):
            span = ids[left:left+width]; ms = [m for w in span for m in morphs[w]]
            if sum(m['label'] in LEXICAL for m in ms) < 2:
                continue
            sequence = []
            for wid in span:
                parts = []
                for m in morphs[wid]:
                    p, f = m['label'], m['form']
                    if p in LEXICAL or p.startswith('J'):
                        parts.append([f, p])
                    elif p in {'EC', 'ETM', 'ETN'}:
                        parts.append(['<ENDING>', p])
                sequence.append(parts)
            flags = markers(ms)
            key = ['M01', target['form'], target['label'], at-left, target['position'], sequence, flags]
            pid = digest(key)
            result[pid] = dict(id=pid, family='M01', key=key,
                evidence=dict(word_ids=span, original_mp=ms, relation='ordered_mp_not_dependency',
                              normalized_only=['EP', 'EF', 'EC', 'ETM', 'ETN', 'punctuation'],
                              markers=flags))
    return list(result.values())

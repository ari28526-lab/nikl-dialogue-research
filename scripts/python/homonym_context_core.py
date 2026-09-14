"""JSON-only context dictionary pilot. Pure functions; no API or audio dependency."""
from collections import Counter, defaultdict
import hashlib
import json
import re


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate_json_key')
        result[k] = v
    return result


class ArrayStream:
    """Stream an array at an exact object path; validate all consumed JSON.

    A caller stopping early must report prefix-only parsing. Full SHA != full parse.
    """
    def __init__(self, handle, pulse=lambda: None, chunk=65536, max_chars=16000000):
        self.handle, self.pulse = handle, pulse
        self.chunk, self.max_chars = chunk, max_chars
        self.buf, self.pos, self.eof = '', 0, False
        self.decoder = json.JSONDecoder(object_pairs_hook=unique_object)

    def more(self):
        self.buf = self.buf[self.pos:]
        self.pos = 0
        part = self.handle.read(self.chunk)
        self.eof = not part
        self.buf += part
        self.pulse()
        if len(self.buf) > self.max_chars:
            raise ValueError('json_value_memory_guard')

    def peek(self):
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos].isspace():
                self.pos += 1
            if self.pos < len(self.buf):
                return self.buf[self.pos]
            if self.eof:
                return ''
            self.more()

    def take(self, char):
        if self.peek() != char:
            raise ValueError('invalid_json_delimiter')
        self.pos += 1

    def value(self):
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buf, self.pos)
                if end == len(self.buf) and not self.eof:
                    self.more()
                    continue
                self.pos = end
                return value
            except json.JSONDecodeError:
                if self.eof:
                    raise ValueError('invalid_or_truncated_json') from None
                self.more()

    def array_at(self, path):
        if not path:
            self.take('[')
            if self.peek() != ']':
                while True:
                    yield self.value()
                    if self.peek() == ']':
                        break
                    self.take(',')
            self.take(']')
            return
        self.take('{')
        seen, found = set(), False
        if self.peek() != '}':
            while True:
                key = self.value()
                if not isinstance(key, str) or key in seen:
                    raise ValueError('duplicate_or_invalid_container_key')
                seen.add(key)
                self.take(':')
                if key == path[0]:
                    found = True
                    yield from self.array_at(path[1:])
                else:
                    self.value()
                if self.peek() == '}':
                    break
                self.take(',')
        self.take('}')
        if not found:
            raise ValueError('required_array_missing')

    def items(self, path):
        yield from self.array_at(path)
        if self.peek():
            raise ValueError('trailing_json_content')


NOUNS = {'NNG', 'NNP', 'NNB', 'NP', 'NR'}
PREDS = {'VV', 'VA', 'VX', 'VCP', 'VCN'}
LEXICAL = NOUNS | PREDS | {'MAG', 'MAJ', 'MM', 'IC', 'XR', 'XPN', 'XSN', 'XSV', 'XSA'}
SPECIAL = {'777': 'form_not_registered', '888': 'sense_not_registered',
           '999': 'annotation_spelling_error', '000': 'unverified_zero_code'}
POS = {'NNG': ['명사'], 'NNP': ['명사'], 'NNB': ['의존 명사', '명사'],
       'NP': ['대명사'], 'NR': ['수사'], 'VV': ['동사'], 'VA': ['형용사'],
       'VX': ['보조 동사', '보조 형용사'], 'VCP': ['서술격 조사'],
       'VCN': ['형용사'], 'MAG': ['부사'], 'MAJ': ['부사'], 'MM': ['관형사'],
       'IC': ['감탄사'], 'XPN': ['접사'], 'XSN': ['접사'], 'XSV': ['접사'], 'XSA': ['접사']}


def integer(v):
    return type(v) is int


def code(v):
    if integer(v) and 0 <= v <= 999:
        return f'{v:03d}'
    if isinstance(v, str) and re.fullmatch(r'[0-9]{1,3}', v):
        return v.zfill(3)
    return None


def clean_word(v):
    return v.replace('-', '').replace('^', '') if isinstance(v, str) else ''


def lookup_forms(lemma, pos):
    values = [lemma]
    if pos in PREDS | {'XSV', 'XSA'}:
        values.append(lemma + '다')
    return values


def lexicon_index(entries):
    result = defaultdict(list)
    for entry in entries:
        result[clean_word(entry['wordinfo'].get('word'))].append(entry)
    return result


def candidates(index, lemma, pos):
    found = {}
    for form in lookup_forms(lemma, pos):
        for entry in index.get(form, []):
            si = entry.get('senseinfo', {})
            if si.get('pos') not in POS.get(pos, []):
                continue
            if integer(entry.get('group_code')) and integer(entry.get('target_code')):
                found[entry['target_code']] = entry
    return list(found.values())


def native_mapping(annotation, entries):
    c = code(annotation.get('sense_id'))
    if c in SPECIAL:
        return dict(state=SPECIAL[c], group=None, native_code=c, matched_ids=[])
    if c is None:
        return dict(state='invalid_native_code', group=None, native_code=None, matched_ids=[])
    matches = [e for e in entries if code(e.get('senseinfo', {}).get('sense_no')) == c]
    groups = {e['group_code'] for e in matches}
    return dict(state='snapshot_code_match_candidate' if len(groups) == 1 else 'mapping_hold',
                group=next(iter(groups)) if len(groups) == 1 else None,
                native_code=c, matched_ids=sorted(e['target_code'] for e in matches))


def sentence_view(sent):
    """Validate MP coordinates without coercing strings/floats/bools into indices."""
    words, mp = sent.get('word'), sent.get('MP', sent.get('morpheme'))
    issues, by_word, morphs = [], {}, defaultdict(list)
    if not isinstance(sent.get('id'), str) or not isinstance(sent.get('form'), str):
        return {}, {}, ['sentence_identity_schema']
    if not isinstance(words, list) or not isinstance(mp, list):
        return {}, {}, ['word_or_mp_schema']
    last = -1
    for w in words:
        if not isinstance(w, dict) or not all(integer(w.get(k)) for k in ['id', 'begin', 'end']):
            issues.append('word_coordinate_type')
            continue
        b, e, wid = w['begin'], w['end'], w['id']
        if wid in by_word or not 0 <= b < e <= len(sent['form']) or b < last or sent['form'][b:e] != w.get('form'):
            issues.append('word_geometry')
        by_word[wid] = w
        last = e
    mids, positions = set(), set()
    for m in mp:
        if not isinstance(m, dict) or not all(integer(m.get(k)) for k in ['id', 'word_id', 'position']):
            issues.append('mp_coordinate_type')
            continue
        if not isinstance(m.get('form'), str) or not isinstance(m.get('label'), str):
            issues.append('mp_value_type')
            continue
        key = (m['word_id'], m['position'])
        if m['id'] in mids or key in positions or m['word_id'] not in by_word or m['position'] < 1:
            issues.append('mp_identity_or_position')
        mids.add(m['id']); positions.add(key)
        morphs[m['word_id']].append(m)
    for wid, ms in morphs.items():
        ms.sort(key=lambda m: m['position'])
        if [m['position'] for m in ms] != list(range(1, len(ms)+1)):
            issues.append('mp_position_gap')
    if any(not morphs[w] for w in by_word):
        issues.append('word_without_mp')
    return by_word, morphs, sorted(set(issues))


def markers(ms):
    pairs = [(m['form'], m['label']) for m in ms]
    return dict(negation_form=any(f in {'안', '못', '않', '아니', '없'} for f, p in pairs),
                quote_form=any(p in {'SS', 'SSO', 'SSC'} or f in {'라고', '다고', '냐고', '자고'} for f, p in pairs),
                clause_form=any(p in {'EC', 'ETM', 'ETN', 'EF'} for f, p in pairs),
                auxiliary_form=any(p == 'VX' for f, p in pairs),
                coordination_form=any(p == 'JC' for f, p in pairs),
                scope_status='surface_markers_only')


def patterns_for(sent, m, words, morphs, max_words=3, max_distance=12):
    """MP-only keys. Gold DP/SRL never leak into deployment features."""
    ids = list(words)
    wi = ids.index(m['word_id'])
    lemma, pos = m['form'], m['label']
    result = {}

    def add(family, detail, evidence):
        key = [family, lemma, pos, detail]
        pid = digest(key)
        result[pid] = dict(id=pid, family=family, key=key, evidence=evidence)

    def seq(wids):
        return [[(x['form'], x['label']) for x in morphs[w]] for w in wids]

    add('K01', [m['position'], seq([m['word_id']])], dict(word_ids=[m['word_id']], morph_id=m['id']))
    for width in range(2, max_words+1):
        for left in range(max(0, wi-width+1), min(wi, len(ids)-width)+1):
            span = ids[left:left+width]
            add('K03', [wi-left, m['position'], seq(span)], dict(word_ids=span))
            add('K02', [wi-left, m['position'], [words[w]['form'] for w in span]], dict(word_ids=span))
    particles = [(x['form'], x['label']) for x in morphs[m['word_id']] if x['label'].startswith('J')]
    anchor_pos = PREDS if pos in NOUNS else NOUNS
    eligible = []
    for ai, wid in enumerate(ids):
        distance = ai-wi
        if not 0 < abs(distance) <= max_distance:
            continue
        for anchor in morphs[wid]:
            if anchor['label'] in anchor_pos:
                eligible.append((abs(distance), distance, wid, anchor))
    # Keep bounded closest lexical anchors on both sides; full source retained.
    for direction in [-1, 1]:
        for _, distance, aw, anchor in sorted((x for x in eligible if x[1]*direction > 0), key=lambda x: (x[0], x[3]['position']))[:2]:
            lo, hi = sorted([wi, ids.index(aw)])
            span = ids[lo:hi+1]
            flags = markers([x for w in span for x in morphs[w]])
            bucket = '1' if abs(distance) == 1 else '2-4' if abs(distance) <= 4 else '5-12'
            detail = [particles, anchor['form'], anchor['label'], direction, bucket, flags]
            evidence = dict(word_ids=span, target_morph_id=m['id'], anchor_morph_id=anchor['id'],
                            exact_word_distance=distance, between_mp=seq(ids[lo+1:hi]),
                            relation='linear_cooccurrence_not_dependency', markers=flags)
            add('K17', detail, evidence)
            if abs(distance) <= 5:
                add('K05', [particles, anchor['form'], anchor['label'], distance, flags], evidence)
    return list(result.values())


def document_extract(source, doc, index, pulse=lambda: None, *, morphology_first=False):
    by_id = {e['target_code']:e for values in index.values() for e in values} if morphology_first else {}
    sentences = doc.get('sentence')
    if not isinstance(doc.get('id'), str) or not isinstance(sentences, list):
        raise ValueError('document_schema')
    sids = [s.get('id') if isinstance(s, dict) else None for s in sentences]
    if any(not isinstance(s, str) for s in sids) or len(set(sids)) != len(sids):
        raise ValueError('duplicate_or_invalid_sentence_id')
    observations, registry, units = [], [], []
    for si, sent in enumerate(sentences):
        pulse()
        words, morphs, issues = sentence_view(sent)
        mp = sent.get('MP', sent.get('morpheme'))
        annotations = sent.get('WSD')
        units.append(dict(id=sent['id'], ordinal=si, previous=sids[si-1] if si else None,
                          next=sids[si+1] if si+1 < len(sids) else None,
                          speaker_state='present' if 'speaker_id' in sent else 'source_absent',
                          issues=issues, raw_mp_count=len(mp) if isinstance(mp, list) else None,
                          raw_wsd_count=len(annotations) if isinstance(annotations, list) else None,
                          optional_layers={k: ('source_absent' if k not in sent else 'raw_preserved_not_interpreted') for k in ['DP', 'SRL', 'ZA']}))
        if isinstance(mp, list):
            for mi, m in enumerate(mp):
                oid = digest([source, doc['id'], sent['id'], 'MP', mi])
                row = dict(id=oid, sentence_id=sent['id'], mp_index=mi, raw=m,
                           status='word_mp_hold' if issues else 'not_lexical_target', patterns=[])
                if not issues and m['label'] in LEXICAL:
                    cs = candidates(index, m['form'], m['label'])
                    if morphology_first:
                        from homonym_morphology import analyze_candidates, structure_features, normalized_patterns
                        analysis = analyze_candidates(index, m['form'], m['label'],
                            structure_features(morphs[m['word_id']], m))
                        cs = [by_id[tid] for tid in analysis['candidate_entry_ids']]
                        row['morphology'] = analysis
                    row.update(status='lexical_target', candidates=sorted({e['group_code'] for e in cs}),
                               candidate_entry_ids=sorted(e['target_code'] for e in cs),
                               patterns=patterns_for(sent, m, words, morphs),
                               structure=dict(word_morph_ids=[v['id'] for v in morphs[m['word_id']]],
                                              state='native_segmentation_not_research_gold'))
                    if morphology_first:
                        row['patterns'].extend(normalized_patterns(sent, m, words, morphs))
                registry.append(row)
        if isinstance(annotations, list):
            for ai, a in enumerate(annotations):
                row = dict(id=digest([source, doc['id'], sent['id'], 'WSD', ai]), sentence_id=sent['id'],
                           annotation_index=ai, raw=a, state='annotation_schema_hold', target_id=None)
                if isinstance(a, dict) and isinstance(a.get('form', a.get('word')), str) and isinstance(a.get('pos'), str):
                    lemma, pos = a.get('form', a.get('word')), a['pos']
                    cs = candidates(index, lemma, pos)
                    if morphology_first:
                        from homonym_morphology import analyze_candidates
                        eligible = analyze_candidates(index, lemma, pos)['candidate_entry_ids']
                        cs = [by_id[tid] for tid in eligible]
                    row.update(lemma=lemma, pos=pos, mapping=native_mapping(a, cs), state='position_or_mp_hold')
                    wid, b, e = a.get('word_id'), a.get('begin'), a.get('end')
                    if not issues and all(integer(x) for x in [wid, b, e]) and wid in words:
                        w = words[wid]
                        matches = [mi for mi, m in enumerate(mp) if m['word_id'] == wid and (m['form'], m['label']) == (lemma, pos)]
                        if w['begin'] <= b < e <= w['end'] and len(matches) == 1:
                            row.update(state='linked', target_id=digest([source, doc['id'], sent['id'], 'MP', matches[0]]))
                        elif b == e and w['begin'] <= b <= w['end']:
                            row['state'] = 'zero_width_native_span_hold'
                        elif len(matches) != 1:
                            row['state'] = 'compound_or_ambiguous_mp_span_hold'
                observations.append(row)
    return dict(source=source, document_id=doc['id'], raw_document=doc, sentences=units,
                morphemes=registry, native_annotations=observations,
                schema='homonym_context_document.v1', audio_required=False)


def build_dictionary(documents):
    counts, seen = {}, set()
    for bundle in documents:
        registry = {r['id']: r for r in bundle['morphemes']}
        # Avoid several annotations voting for the same MP occurrence.
        labels = defaultdict(set)
        for a in bundle['native_annotations']:
            if a['state'] == 'linked' and a['mapping']['group'] is not None:
                labels[a['target_id']].add(a['mapping']['group'])
        for oid, groups in labels.items():
            if len(groups) != 1:
                continue
            group = next(iter(groups)); row = registry[oid]
            sent = next(s for s in bundle['raw_document']['sentence'] if s['id'] == row['sentence_id'])
            for p in row['patterns']:
                entry = counts.setdefault(p['id'], dict(id=p['id'], family=p['family'], key=p['key'], groups={}))
                g = entry['groups'].setdefault(str(group), dict(occurrences=0, source_counts={},
                      document_ids=[], unique_context_hashes=[], evidence_ids=[]))
                event = (p['id'], group, oid)
                if event in seen:
                    continue
                seen.add(event); g['occurrences'] += 1
                g['source_counts'][bundle['source']] = g['source_counts'].get(bundle['source'], 0)+1
                g['document_ids'].append(bundle['document_id'])
                g['unique_context_hashes'].append(digest(sent['form']))
                g['evidence_ids'].append(oid)
    for entry in counts.values():
        for g in entry['groups'].values():
            g['document_ids'] = sorted(set(g['document_ids']))
            g['unique_context_hashes'] = sorted(set(g['unique_context_hashes']))
        entry['state'] = 'conflicting_evidence' if len(entry['groups']) > 1 else 'observed_single_group_not_validated'
    return sorted(counts.values(), key=lambda e: e['id'])


def apply_dictionary(bundle, dictionary, *, semantic_index=None):
    index = {e['id']: e for e in dictionary}
    decisions = []
    for row in bundle['morphemes']:
        out = dict(target_id=row['id'], sentence_id=row['sentence_id'], selected_group=None,
                   state=row['status'], method='none', supporting_pattern_ids=[], automatic_adoption=False)
        if row['status'] == 'lexical_target':
            cs = set(row['candidates'])
            morphology = row.get('morphology')
            if morphology:
                out['morphology'] = morphology
                if morphology['state'] == 'structure_hold':
                    out.update(candidate_groups=sorted(cs), conflicting_pattern_ids=[], state='morphology_structure_hold')
                    decisions.append(out)
                    continue
            support, conflicts = defaultdict(list), []
            for p in row['patterns']:
                entry = index.get(p['id'])
                if not entry:
                    continue
                groups = set(map(int, entry['groups']))
                if not groups <= cs or len(groups) != 1:
                    conflicts.append(p['id'])
                else:
                    support[next(iter(groups))].append(p['id'])
            out['candidate_groups'] = sorted(cs)
            out['conflicting_pattern_ids'] = conflicts
            if len(support) == 1 and not conflicts:
                g = next(iter(support))
                out.update(selected_group=g, state='selected_machine_candidate', method='context_dictionary',
                           supporting_pattern_ids=sorted(support[g]))
            elif len(support) > 1 or conflicts:
                out['state'] = 'context_conflict'
            elif len(cs) == 1:
                if morphology and not morphology['singleton_eligible']:
                    out['state'] = 'morphology_metadata_hold'
                else:
                    out.update(selected_group=next(iter(cs)), state='selected_machine_candidate',
                               method='morphology_single_group' if morphology else 'snapshot_single_group')
            else:
                out['state'] = 'no_dictionary_candidate' if not cs else 'insufficient_context_evidence'
            if semantic_index is not None and len(cs) > 1 and out['state'] == 'insufficient_context_evidence':
                from homonym_food_context import food_context
                context = food_context(bundle, row, semantic_index)
                out['context_evidence'] = context
                if context['selected_group'] is not None:
                    out.update(selected_group=context['selected_group'], state='selected_machine_candidate',
                               method='dictionary_food_compound')
        decisions.append(out)
    return decisions


def feature_inventory():
    implemented = {'K01', 'K02', 'K03', 'K05', 'K17'}
    return {f'K{i:02d}': dict(status='implemented_mp_candidate' if f'K{i:02d}' in implemented else 'raw_preserved_not_implemented',
                note='bounded pilot; no claim of complete family coverage') for i in range(1, 33)}

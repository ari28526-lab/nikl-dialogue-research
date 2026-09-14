"""Standard-library streaming JSON and native-annotation collocation extraction.

No network, re-tagging or automatic sense adoption. Native namespaces stay separate.
"""
import hashlib
import json
from collections import defaultdict

NOUNS = {'NNG', 'NNP', 'NNB', 'NP', 'NR'}
PREDICATES = {'VV', 'VA', 'VX', 'VCP', 'VCN'}
TARGETS = NOUNS | PREDICATES
SPECIAL = {'0', '777', '888', '999'}


def canonical(x):
    return json.dumps(x, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def digest(x):
    return hashlib.sha256(x.encode('utf-8')).hexdigest()


class JsonStream:
    """Parse a root JSON object, streaming one document array item at a time."""
    def __init__(self, handle, chunk=262144, max_value=134217728):
        self.handle, self.chunk, self.max_value = handle, chunk, max_value
        self.buf, self.pos, self.eof = '', 0, False
        self.decoder = json.JSONDecoder()

    def more(self):
        self.buf = self.buf[self.pos:]
        self.pos = 0
        part = self.handle.read(self.chunk)
        self.eof = not part
        self.buf += part
        if len(self.buf) > self.max_value:
            raise ValueError('json_document_exceeds_memory_guard')

    def peek(self):
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos].isspace():
                self.pos += 1
            if self.pos < len(self.buf):
                return self.buf[self.pos]
            if self.eof:
                return ''
            self.more()

    def take(self, expected):
        if self.peek() != expected:
            raise ValueError('invalid_json_delimiter')
        self.pos += 1

    def value(self):
        self.peek()
        while True:
            try:
                val, end = self.decoder.raw_decode(self.buf, self.pos)
                # A number can be a partial token at a chunk boundary.
                if end == len(self.buf) and not self.eof:
                    self.more()
                    continue
                self.pos = end
                return val
            except json.JSONDecodeError:
                if self.eof:
                    raise ValueError('invalid_or_truncated_json') from None
                self.more()

    def documents(self):
        self.take('{')
        keys, found = set(), False
        while self.peek() != '}':
            key = self.value()
            if not isinstance(key, str) or key in keys:
                raise ValueError('invalid_or_duplicate_root_key')
            keys.add(key)
            self.take(':')
            if key == 'document':
                found = True
                self.take('[')
                if self.peek() != ']':
                    while True:
                        doc = self.value()
                        if not isinstance(doc, dict):
                            raise ValueError('document_not_object')
                        yield doc
                        if self.peek() == ']':
                            break
                        self.take(',')
                self.take(']')
            else:
                self.value()
            if self.peek() == '}':
                break
            self.take(',')
            if self.peek() == '}':
                raise ValueError('trailing_root_comma')
        self.take('}')
        if self.peek() or not found:
            raise ValueError('invalid_root_or_trailing_content')


def split_group(doc_id):
    group = str(doc_id).split('.')[0]
    if not group:
        raise ValueError('empty_document_id')
    return group, ('test' if int(digest(group)[:8], 16) % 5 == 0 else 'train')


def sense_code(value):
    text = str(value).strip()
    if not text.isascii() or not text.isdigit():
        return None
    code = str(int(text))
    return code if code not in SPECIAL else None


def extract_sentence(sent):
    """One row per native WSD annotation, even if unusable; no source text emitted."""
    if not isinstance(sent.get('id'), str) or not isinstance(sent.get('form'), str):
        raise ValueError('sentence_identity_schema')
    wsd = sent.get('WSD')
    words, mp = sent.get('word'), sent.get('MP', sent.get('morpheme'))
    if not all(isinstance(x, list) for x in (wsd, words, mp)):
        raise ValueError('sentence_annotation_schema')
    text = sent['form']
    by_word, morphs = {}, defaultdict(list)
    geometry_ok = True
    previous_end = -1
    for w in words:
        try:
            wid, b, e = int(w['id']), int(w['begin']), int(w['end'])
            if wid in by_word or not 0 <= b < e <= len(text) or b < previous_end or text[b:e] != w['form']:
                geometry_ok = False
            by_word[wid] = w
            previous_end = e
        except (KeyError, ValueError, TypeError):
            geometry_ok = False
    for m in mp:
        try:
            wid = int(m['word_id'])
            if wid not in by_word or not isinstance(m['form'], str) or not isinstance(m['label'], str):
                geometry_ok = False
            morphs[wid].append(m)
        except (KeyError, ValueError, TypeError):
            geometry_ok = False
    for ms in morphs.values():
        ms.sort(key=lambda m: int(m.get('position', m.get('id', 0))))
    word_order = {wid: i for i, wid in enumerate(by_word)}
    predicates = [(wid, m['form'], m['label']) for wid, ms in morphs.items()
                  for m in ms if m.get('label') in PREDICATES]
    dp = defaultdict(list)
    for edge in sent.get('DP', []):
        dp[int(edge['word_id'])].append(edge)
    out = []
    for index, annotation in enumerate(wsd):
        lemma = annotation.get('form', annotation.get('word', ''))
        pos = annotation.get('pos', '')
        code = sense_code(annotation.get('sense_id', ''))
        row = dict(index=index, lemma=lemma, pos=pos, sense=code, status='candidate', patterns=[])
        if code is None:
            row['status'] = 'special_or_invalid_sense'
        elif pos not in TARGETS:
            row['status'] = 'outside_initial_lexical_scope'
        elif not geometry_ok:
            row['status'] = 'hold_word_geometry'
        else:
            try:
                wid = int(annotation['word_id'])
                b, e = int(annotation['begin']), int(annotation['end'])
                word = by_word[wid]
                matches = [m for m in morphs[wid] if (m['form'], m['label']) == (lemma, pos)]
                if not int(word['begin']) <= b < e <= int(word['end']) or len(matches) != 1:
                    raise ValueError('ambiguous_native_link')
                particles = tuple((m['form'], m['label']) for m in morphs[wid] if m['label'].startswith('J'))
                base = [lemma, pos, particles]
                patterns = set()
                ids = list(by_word)
                target_i = word_order[wid]
                # Native MP sequences, not raw two-word exact-text matching.
                # Every complete 2..5-eojeol span containing the target is kept.
                for width in range(2,6):
                    for left in range(max(0,target_i-width+1),min(target_i,len(ids)-width)+1):
                        span=ids[left:left+width]
                        if any(not morphs[i] for i in span):
                            continue
                        signature=[[(m['form'],m['label']) for m in morphs[i]] for i in span]
                        patterns.add(canonical(['mp_sequence',lemma,pos,target_i-left,signature]))
                # Target-anchored grammatical shell: retain function/auxiliary
                # material while abstracting other open-class lexical items.
                for width in (3,5,7):
                    left=max(0,target_i-width//2)
                    right=min(len(ids),left+width)
                    span=ids[left:right]
                    if len(span)<2 or any(not morphs[i] for i in span):
                        continue
                    shell=[]
                    for i in span:
                        shell.append([(m['form'] if i==wid or m['label'].startswith(('J','E')) or m['label'] in {'VX','NNB','VCP','VCN'} or m['form'] in {'안','못','않','없'} else '<'+m['label']+'>',m['label']) for m in morphs[i]])
                    patterns.add(canonical(['grammatical_shell',lemma,pos,target_i-left,shell]))
                for pw, pl, pp in predicates:
                    distance = word_order[pw] - word_order[wid]
                    if 0 < abs(distance) <= 5:
                        patterns.add(canonical(['nearby_predicate', *base, pl, pp, distance]))
                    for edge in dp.get(wid, []):
                        if int(edge['head']) == pw and pw != wid:
                            patterns.add(canonical(['direct_dp', *base, pl, pp, edge['label']]))
                # Gapped lexical anchor: nearest predicate or nominal on each
                # side, up to 12 eojeol. This is co-occurrence, not dependency.
                anchors=[(w,m['form'],m['label']) for w,ms in morphs.items() for m in ms
                         if m['label'] in (PREDICATES if pos in NOUNS else NOUNS)]
                for direction in (-1,1):
                    candidates=[(word_order[w]-target_i,w,l,p) for w,l,p in anchors
                                if 0<(word_order[w]-target_i)*direction<=12]
                    if candidates:
                        nearest=min(abs(c[0]) for c in candidates)
                        for distance,aw,al,ap in candidates:
                            if abs(distance)==nearest:
                                bucket='1' if nearest==1 else '2-4' if nearest<=4 else '5-12'
                                patterns.add(canonical(['gapped_anchor',*base,al,ap,direction,bucket]))
                # Explicit upward DP paths only; retain the edge labels and
                # distinguish a mediated path from a direct argument relation.
                current,visited,labels=wid,{wid},[]
                for depth in range(1,4):
                    edges=dp.get(current,[])
                    if len(edges)!=1:
                        break
                    edge=edges[0]
                    head=int(edge['head'])
                    if head in visited or head not in by_word:
                        break
                    visited.add(head)
                    labels.append(edge['label'])
                    for m in morphs[head]:
                        if m['label'] in TARGETS:
                            patterns.add(canonical(['dp_ancestor',*base,m['form'],m['label'],labels.copy()]))
                    current=head
                for frame in sent.get('SRL', []):
                    predicate = frame['predicate']
                    pw = int(predicate['word_id'])
                    pms = [(pl, pp) for w, pl, pp in predicates if w == pw]
                    for arg in frame.get('argument', []):
                        arg_ids = arg['word_id'] if isinstance(arg['word_id'], list) else [arg['word_id']]
                        if wid in [int(i) for i in arg_ids]:
                            for pl, pp in pms:
                                patterns.add(canonical(['srl_span_member', *base, pl, pp, arg['label']]))
                row['patterns'] = sorted(patterns)
                if not patterns:
                    row['status'] = 'no_pattern'
            except (KeyError, ValueError, TypeError):
                row['status'] = 'hold_wsd_mp_link'
        out.append(row)
    return out

"""Conservative evidence features; never a gold K-ToBI annotation."""
import bisect
import math
import re
import statistics

def lexical(text):
    return bool(text.strip()) and '<' not in text and '>' not in text

def map_syllables(word, pron, roman, phones, phone_ends, vowels):
    if not all(lexical(x['text']) for x in [word, pron, roman]):
        return [], 'nonlexical_or_marker'
    start = bisect.bisect_right(phone_ends, word['start'] + 1e-8)
    ps = []
    for p in phones[start:]:
        if p['start'] >= word['end'] - 1e-8:
            break
        ps.append(p)
    if not ps or abs(ps[0]['start']-word['start'])>1e-7 or abs(ps[-1]['end']-word['end'])>1e-7:
        return [], 'phone_word_edge_mismatch'
    if any(not lexical(p['text']) for p in ps):
        return [], 'phone_marker'
    chunks = roman['text'].strip().split('-')
    if len(chunks) != len(re.findall('[가-힣]', pron['text'])):
        return [], 'roman_hangul_syllable_count_mismatch'
    if ''.join(chunks) != ''.join(p['text'] for p in ps):
        return [], 'roman_phone_sequence_mismatch'
    result=[]; pos=0
    for chunk in chunks:
        used=[]; combined=''
        while pos<len(ps) and len(combined)<len(chunk):
            used.append(ps[pos]); combined+=ps[pos]['text']; pos+=1
        if combined!=chunk:
            return [], 'syllable_phone_edge_mismatch'
        vs=[p for p in used if p['text'] in vowels]
        if len(vs)!=1:
            return [], 'vowel_mapping_unresolved'
        result.append(dict(start=used[0]['start'],end=used[-1]['end'],onset=used[0]['text'],
                           vowel_code=vs[0]['text'],vowel_start=vs[0]['start'],vowel_end=vs[0]['end']))
    if pos!=len(ps):
        return [], 'unconsumed_phones'
    return result, 'mapped_by_exact_annotation_correspondence'

def semitones(a,b):
    return 12*math.log2(b/a) if a and b and a>0 and b>0 else None

def vowel_feature(s, times, pitches, params):
    a=bisect.bisect_left(times,s['vowel_start']); b=bisect.bisect_left(times,s['vowel_end'])
    paired=list(zip(times[a:b],pitches[a:b])); valid=[(t,f) for t,f in paired if f>0 and math.isfinite(f)]
    frac=len(valid)/len(paired) if paired else 0
    mid=(s['vowel_start']+s['vowel_end'])/2
    left=[f for t,f in valid if t<mid]; right=[f for t,f in valid if t>=mid]
    # Check jumps only between consecutive actual voiced frames, never across a gap.
    jumps=[abs(semitones(f,g)) for (t,f),(u,g) in zip(paired,paired[1:]) if f>0 and g>0 and u-t<0.015]
    good=len(valid)>=params['frame_min_count'] and frac>=params['minimum_voiced_fraction_in_vowel']
    jump=max(jumps,default=0)
    return dict(median_hz=statistics.median([f for t,f in valid]) if good else None,
                terminal_change_st=semitones(statistics.median(left),statistics.median(right))
                if good and len(left)>=params['frame_min_count'] and len(right)>=params['frame_min_count'] else None,
                voiced_fraction=frac,voiced_frames=len(valid),frame_count=len(paired),
                max_adjacent_jump_st=jump,quality_ok=good and jump<=params['maximum_adjacent_f0_jump_semitones'])

def classify(metrics, hard_holds, grid):
    if hard_holds:
        return 'not_evaluable'
    change=metrics.get('terminal_change_st')
    pause=metrics.get('annotated_silence_seconds',0)
    if change is not None and abs(change)>=grid['tonal_change_semitones'] and pause>=grid['annotated_silence_seconds']:
        return 'IP_candidate'
    cues=[metrics.get(k) for k in ('pre_final_rise_st','next_initial_rise_st','boundary_fall_st')]
    if metrics.get('ap_context_eligible') and all(x is not None and x>=grid['tonal_change_semitones'] for x in cues):
        return 'AP_candidate'
    return 'no_boundary_evidence'

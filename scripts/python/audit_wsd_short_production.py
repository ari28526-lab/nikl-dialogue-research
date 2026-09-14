"""Independent frozen-input and contiguous-core audit of the short-window plan."""
from collections import Counter
import gzip
import json
import time

from prepare_wsd_short_production import (ROOT, DEST, OLD_PLAN, load_source, read_json,
    digest, canonical, atomic, normalize)


def check_record(record,rows):
    counts=Counter(conversations=1,utterances=len(rows),windows=len(record['windows']))
    texts=[normalize(r['form']) for r in rows]
    counts['input_chars']=sum(map(len,texts))
    for t in texts:
        n=len(t)
        label='0' if n==0 else '1_80' if n<=80 else '81_220' if n<=220 else '221_400' if n<=400 else 'over_400'
        counts['utterance_chars_'+label]+=1
    cursor=0
    for w in record['windows']:
        a,b,l,r=(w[k] for k in ('core_start','core_end','context_start','context_end'))
        if not (a==cursor and 0<=l<=a<b<=r<=len(rows) and a-l<=1 and r-b<=1):
            raise ValueError('core_partition_or_context_range')
        core=' '.join(texts[a:b])
        if b-a>1 and len(core)>220:raise ValueError('multi_utterance_core_over_limit')
        if b<len(rows) and len(core)+1+len(texts[b])<=220:raise ValueError('core_not_greedy')
        expected_left=a-1 if a and len(core)+1+len(texts[a-1])<=400 else a
        left_core=' '.join(texts[expected_left:b])
        expected_right=b+1 if b<len(rows) and len(left_core)+1+len(texts[b])<=400 else b
        if l!=expected_left or r!=expected_right:raise ValueError('neighbor_selection_changed')
        request=' '.join(texts[l:r])
        state='hold_oversize_utterance' if len(request)>400 else 'hold_empty_text' if not request.strip() else 'planned'
        if (w['status']!=state or w['request_chars']!=len(request) or w['request_eojeol']!=len(request.split())
                or w['request_sha256']!=digest(request.encode())):
            raise ValueError('request_content_or_status_changed')
        left_omitted=a>0 and l==a
        right_omitted=b<len(rows) and r==b
        if w['left_context_omitted']!=left_omitted or w['right_context_omitted']!=right_omitted:
            raise ValueError('omitted_context_flag_changed')
        mappings=[]
        offset=0
        for i in range(l,r):
            row=rows[i];text=texts[i]
            # Normalization is length preserving; verify against original form.
            if len(text)!=len(row['form']):raise ValueError('normalization_changed_length')
            mappings.append(dict(utt_id=row['utt_id'],source_row_index=int(row['source_row_index']),
                                 speaker_id=row['speaker_id'],begin_utf32=offset,end_utf32=offset+len(text),
                                 role='core' if a<=i<b else 'context',
                                 line_separator_replacements=sum(c in '\r\n\v\f\x85\u2028\u2029' for c in row['form'])))
            offset+=len(text)+1
        if digest(canonical(mappings))!=w['mapping_sha256']:raise ValueError('mapping_hash_changed')
        counts[state+'_windows']+=1
        counts[state+'_utterances']+=b-a
        counts['context_edges_omitted']+=int(left_omitted)+int(right_omitted)
        if state=='planned':
            counts['planned_request_chars']+=len(request)
            counts['planned_request_eojeol']+=len(request.split())
        cursor=b
    if cursor!=len(rows) or dict(counts)!=record['counts']:raise ValueError('record_count_mismatch')
    if record['source_order_sha256']!=digest(canonical([r['utt_id'] for r in rows])):
        raise ValueError('source_order_changed')
    if record['max_utterance_chars']!=max(map(len,texts),default=0):raise ValueError('max_length_changed')
    return counts


def main():
    final=DEST/'final'
    contract=read_json(final/'CONTRACT.json')
    report=read_json(final/'REPORT.json')
    path=final/report.get('plan_file','conversations.jsonl.gz')
    if digest(path.read_bytes())!=report['plan_sha256'] or digest(canonical(contract))!=report['contract_sha256']:
        raise ValueError('plan_artifact_changed')
    refs_path=OLD_PLAN/'SOURCE_REFERENCES.json'
    if digest(refs_path.read_bytes())!=contract['source_references_sha256']:
        raise ValueError('source_references_changed')
    refs=read_json(refs_path)['sources']
    started=time.monotonic();totals=Counter();years={};seen=set()
    with gzip.open(path,'rt',encoding='utf-8') as handle:
        for i,ref in enumerate(refs,1):
            line=handle.readline()
            if not line:raise ValueError('missing_conversation_record')
            record=json.loads(line)
            if record['source']!=ref:raise ValueError('source_reference_changed')
            rows,conversation=load_source(ref)
            if record['conversation_id']!=conversation or conversation in seen:raise ValueError('conversation_identity')
            seen.add(conversation)
            c=check_record(record,rows)
            totals.update(c);years.setdefault(record['year'],Counter()).update(c)
            if i%1000==0 or i==len(refs):
                print(json.dumps(dict(status='auditing_offline_plan',conversations=i,total=len(refs),
                                      elapsed_seconds=round(time.monotonic()-started,2))),flush=True)
        if handle.readline():raise ValueError('extra_conversation_record')
    if dict(totals)!=report['counts'] or {k:dict(v) for k,v in years.items()}!=report['years']:
        raise ValueError('full_counts_changed')
    if totals['utterances']!=5103356 or totals['conversations']!=17156:
        raise ValueError('full_scope_incomplete')
    result=dict(schema='wsd_short_production_plan_audit.v1',passed=True,counts=dict(totals),
                plan_sha256=report['plan_sha256'],contract_sha256=report['contract_sha256'],
                frozen_input_rehashed=True,independent_core_coverage=True,zero_drop=True,
                api_called=False,production_ready=False,elapsed_seconds=round(time.monotonic()-started,3))
    atomic(ROOT/'outputs/reports/AUDIT_wsd_short_production_plan_20260905.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

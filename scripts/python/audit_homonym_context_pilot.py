"""Read-only independent output and standalone-export audit; no source rewriting."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(root):
    receipt=read(root/'FINAL_RECEIPT.json')
    issues=[]
    for name,h in receipt['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file() or sha(p)!=h:
            issues.append('file_sha:'+name)
    expected={}
    for p in (root/'sources').glob('*.json'):
        if p.name.endswith('.receipt.json'):continue
        selection=read(p)
        for d in selection['documents']:
            expected[(p.stem,d['document']['id'])]=d
    docs={}
    for name in receipt['files']:
        if not name.startswith('documents/') or name.endswith('.receipt.json'):continue
        b=read(root/name); key=(b['source'],b['document_id']);docs[key]=b
        if key not in expected or b['raw_document']!=expected[key]['document']:
            issues.append('raw_document_changed:'+str(key))
        if b['split']!=expected[key]['split']:
            issues.append('split_changed:'+str(key))
        raw_mp=[m for s in b['raw_document']['sentence'] for m in s.get('MP',s.get('morpheme',[]))]
        raw_wsd=[a for s in b['raw_document']['sentence'] for a in s.get('WSD',[])]
        if [m['raw'] for m in b['morphemes']]!=raw_mp or [a['raw'] for a in b['native_annotations']]!=raw_wsd:
            issues.append('raw_annotation_loss:'+str(key))
    if not expected or set(docs)!=set(expected):issues.append('document_inventory_mismatch')
    train_groups={b['original_group'] for b in docs.values() if b['split']=='train'}
    check_groups={b['original_group'] for b in docs.values() if b['split']=='check'}
    if train_groups & check_groups:issues.append('group_leak')
    pat={p['id']:p for p in read(root/'CONTEXT_DICTIONARY.json')['patterns']}
    train_ids={m['id'] for b in docs.values() if b['split']=='train' for m in b['morphemes']}
    for entry in pat.values():
        for g in entry['groups'].values():
            if not set(g['evidence_ids'])<=train_ids:issues.append('nontraining_pattern_evidence')
    states=Counter();multi=selected_multi=0
    for name in receipt['files']:
        if not name.startswith('applications/') or name.endswith('.receipt.json'):continue
        a=read(root/name);b=docs[(a['source'],a['document_id'])]
        if b['split']!='check':issues.append('application_not_holdout')
        if {r['target_id'] for r in a['decisions']}!={m['id'] for m in b['morphemes']} or len(a['decisions'])!=len(b['morphemes']):
            issues.append('application_identity_or_count')
        for d in a['decisions']:
            states[d['state']]+=1
            multi+=len(d.get('candidate_groups',[]))>1
            selected_multi+=len(d.get('candidate_groups',[]))>1 and d['selected_group'] is not None
            if d['selected_group'] is not None and d['selected_group'] not in d['candidate_groups']:
                issues.append('selected_outside_candidates')
            for pid in d['supporting_pattern_ids']:
                if set(pat[pid]['groups'])!={str(d['selected_group'])}:issues.append('unsupported_selected_group')
    ex=read(root/'RESEARCH_JSON'/'MANIFEST.json')
    if len(ex['files'])!=len(expected):issues.append('standalone_count')
    for item in ex['files']:
        p=root/'RESEARCH_JSON'/item['file']
        if sha(p)!=item['sha256']:issues.append('standalone_sha')
        e=read(p);b=e['document']
        if b!=docs[(b['source'],b['document_id'])]:issues.append('standalone_document_changed')
        entry_ids={v['target_code'] for v in e['lexicon_entries']}
        required={v for m in b['morphemes'] for v in m.get('candidate_entry_ids',[])}
        if not required<=entry_ids:issues.append('standalone_dictionary_reference')
        required_e={v for row in e['context_dictionary_evidence'] for g in row['groups'].values() for v in g['evidence_ids']}
        if not required_e<=set(e['source_examples']):issues.append('standalone_evidence_reference')
    return dict(passed=not issues,issues=issues,registered_core_files=len(receipt['files']),
                documents=len(docs),standalone_files=len(ex['files']),application_states=dict(states),
                multiple_candidates=multi,multiple_selected=selected_multi,
                scope='raw_preservation_identity_evidence_and_sha_not_semantic_gold')


if __name__=='__main__':
    root=data_path('homonym_review_source')
    result=audit(root)
    print(json.dumps(result,ensure_ascii=True))
    raise SystemExit(0 if result['passed'] else 1)

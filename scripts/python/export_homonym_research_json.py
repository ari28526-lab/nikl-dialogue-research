"""Export independent per-document research JSON from a completed pilot.

Only creates RESEARCH_JSON under the completed pilot. Never changes core outputs.
"""
from collections import Counter
import argparse
import json
from pathlib import Path
import re

from homonym_context_core import digest, feature_inventory
from run_homonym_context_pilot import read, sha, atomic, DEFAULT_CONFIG


def export(root):
    receipt=read(root/'FINAL_RECEIPT.json')
    if not receipt['audit']['passed'] or receipt['status']!='completed_pilot_pending_research_review':
        raise RuntimeError('completed_pilot_required')
    for name,expected in receipt['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or sha(p)!=expected:
            raise RuntimeError('pilot_output_changed')
    lex=read(root/'LEXICON.json')
    patterns={e['id']:e for e in read(root/'CONTEXT_DICTIONARY.json')['patterns']}
    docs=[read(root/name) for name in sorted(receipt['files'])
          if name.startswith('documents/') and name.endswith('.json') and not name.endswith('.receipt.json')]
    if len(docs)!=receipt['audit']['documents'] or any(b.get('schema')!='homonym_context_document.v1' for b in docs):
        raise RuntimeError('document_export_inventory_mismatch')
    evidence={}
    for b in docs:
        ss={s['id']:s for s in b['raw_document']['sentence']}
        for m in b['morphemes']:
            evidence[m['id']]=dict(source=b['source'],document_id=b['document_id'],
                sentence_id=m['sentence_id'],mp_index=m['mp_index'],raw_sentence=ss[m['sentence_id']],
                original_source_sha256=b['source_sha256'])
    outputs=[]
    for b in docs:
        ids={e for m in b['morphemes'] for e in m.get('candidate_entry_ids',[])}
        decisions=[]
        if b['split']=='check':
            app=read(root/'applications'/(digest([b['source'],b['document_id']])+'.json'))
            decisions=app['decisions']
        pids={pid for d in decisions for pid in d.get('supporting_pattern_ids',[])+d.get('conflicting_pattern_ids',[])}
        selected_patterns=[patterns[p] for p in sorted(pids)]
        evidence_ids={eid for p in selected_patterns for g in p['groups'].values() for eid in g['evidence_ids']}
        payload=dict(schema='standalone_homonym_research_document.v1',audio_required=False,
            purpose='homonym context and morphological research; not realization labels',
            automatic_adoption=False,source_role=b['split'],document=b,
            lexicon_entries=[e for e in lex['entries'] if e['target_code'] in ids],
            decisions=decisions,context_dictionary_evidence=selected_patterns,
            source_examples={eid:evidence[eid] for eid in sorted(evidence_ids)},
            feature_implementation=feature_inventory(),
            coverage=dict(sentences=len(b['sentences']),morphemes=len(b['morphemes']),
                          decision_states=dict(Counter(d['state'] for d in decisions))),
            cautions=['native dictionary mappings are snapshot candidates',
                'check results use native MP; not verified Bareun transfer',
                'raw optional syntax/dialogue layers retained, not fully interpreted',
                'training documents contain evidence, not independent predictions'])
        lex_ids={e['target_code'] for e in payload['lexicon_entries']}
        if ids!=lex_ids or not evidence_ids<=evidence.keys():
            raise RuntimeError('dangling_export_reference')
        if decisions and {d['target_id'] for d in decisions}!={m['id'] for m in b['morphemes']}:
            raise RuntimeError('export_decision_loss')
        name=re.sub(r'[^A-Za-z0-9_.-]','_',b['source']+'__'+b['document_id'])+'.json'
        target=root/'RESEARCH_JSON'/name
        if target.exists():
            if digest(read(target))!=digest(payload):
                raise RuntimeError('existing_export_differs')
        else:
            atomic(target,payload)
        outputs.append(dict(file=name,bytes=target.stat().st_size,sha256=sha(target),
                            role=b['split'],sentences=len(b['sentences']),morphemes=len(b['morphemes'])))
    manifest=dict(schema='standalone_research_exports.v1',files=outputs,
        source_receipt_sha256=sha(root/'FINAL_RECEIPT.json'),exporter_sha256=sha(Path(__file__)),
        api_called=False,audio_required=False,internal_research_data_not_public_release=True)
    mp=root/'RESEARCH_JSON'/'MANIFEST.json'
    if mp.exists() and digest(read(mp))!=digest(manifest):
        raise RuntimeError('existing_export_manifest_differs')
    if not mp.exists():atomic(mp,manifest)
    print(json.dumps(dict(files=len(outputs),bytes=sum(f['bytes'] for f in outputs),reference_check='passed'),ensure_ascii=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    root=Path(read(DEFAULT_CONFIG)['output_root'])
    if a.preflight_only:
        print(json.dumps(dict(completed_receipt=(root/'FINAL_RECEIPT.json').exists(),output=str(root/'RESEARCH_JSON'))))
    else:export(root)

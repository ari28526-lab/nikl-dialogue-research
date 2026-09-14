"""Apply MP-first linkage to the six frozen pilot documents in a new namespace."""
import argparse
from collections import Counter
from pathlib import Path
from research_paths import data_path, drive_root, resolve_legacy_path, qc_diagnostics

from homonym_context_core import document_extract, lexicon_index, build_dictionary, apply_dictionary
from homonym_morphology import VERSION
from run_homonym_context_pilot import read, sha, atomic

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = data_path('homonym_review_source')
DEFAULT_OUTPUT = REPO/'outputs/pilots/homonym_morphology_20260906'


def run(source, output):
    if output.exists():
        raise RuntimeError('output_exists_use_new_namespace')
    receipt_path = source/'FINAL_RECEIPT.json'
    receipt = read(receipt_path)
    if not receipt.get('audit', {}).get('passed'):
        raise RuntimeError('source_audit_not_passed')
    names = [n for n in receipt['files'] if n in {'LEXICON.json', 'CONTEXT_DICTIONARY.json'} or
             (n.startswith(('documents/', 'applications/')) and not n.endswith('.receipt.json'))]
    frozen_hashes = {n:sha(source/n) for n in names}
    if any(frozen_hashes[n] != receipt['files'][n] for n in names):
        raise RuntimeError('frozen_input_changed')
    index = lexicon_index(read(source/'LEXICON.json')['entries'])
    old_docs = [read(source/n) for n in names if n.startswith('documents/')]
    if len(old_docs) != 6 or Counter(d['split'] for d in old_docs) != {'train':4, 'check':2}:
        raise RuntimeError('unexpected_pilot_scope')
    bundles = []
    for old in old_docs:
        b = document_extract(old['source'], old['raw_document'], index, morphology_first=True)
        b['split'] = old['split']; b['schema'] = 'homonym_morphology_document.v1'
        if [m['id'] for m in b['morphemes']] != [m['id'] for m in old['morphemes']]:
            raise RuntimeError('morpheme_identity_changed')
        if b['raw_document'] != old['raw_document']:
            raise RuntimeError('raw_document_changed')
        bundles.append(b)
    dictionary = build_dictionary([b for b in bundles if b['split'] == 'train'])
    old_decisions = {d['target_id']:d for n in names if n.startswith('applications/')
                     for d in read(source/n)['decisions']}
    new_decisions = [d for b in bundles if b['split'] == 'check' for d in apply_dictionary(b, dictionary, semantic_index=index)]
    if set(old_decisions) != {d['target_id'] for d in new_decisions}:
        raise RuntimeError('decision_identity_changed')
    comparison = []
    for d in new_decisions:
        old = old_decisions[d['target_id']]
        comparison.append(dict(target_id=d['target_id'], old_candidates=old.get('candidate_groups', []),
            new_candidates=d.get('candidate_groups', []), old_group=old['selected_group'],
            new_group=d['selected_group'], old_method=old['method'], new_method=d['method'],
            state=d['state'], morphology=d.get('morphology'),
            context_evidence=d.get('context_evidence'),
            supporting_pattern_ids=d['supporting_pattern_ids']))
    # Compare candidate retention against provisional native mappings, never call this accuracy.
    mapping_removed = []
    mapping_count = 0
    for old, b in zip(old_docs, bundles):
        registry = {m['id']:m for m in b['morphemes']}
        for a in old['native_annotations']:
            group = a.get('mapping', {}).get('group')
            if a.get('state') == 'linked' and group is not None:
                mapping_count += 1
                if group not in registry[a['target_id']].get('candidates', []):
                    mapping_removed.append(dict(target_id=a['target_id'], group=group, split=b['split']))
    originally_multiple = [c for c in comparison if len(c['old_candidates']) > 1]
    summary = dict(schema='homonym_morphology_comparison.v1', version=VERSION,
        source_receipt_sha256=sha(receipt_path), input_sha256=frozen_hashes,
        documents=len(bundles), sentences=sum(len(b['sentences']) for b in bundles),
        morphemes=sum(len(b['morphemes']) for b in bundles), zero_drop=True,
        check_decisions=len(new_decisions), patterns=len(dictionary),
        original_multiple_count=len(originally_multiple),
        original_multiple_selected_before=sum(c['old_group'] is not None for c in originally_multiple),
        original_multiple_selected_after=sum(c['new_group'] is not None for c in originally_multiple),
        original_multiple_methods=dict(Counter(c['new_method'] for c in originally_multiple)),
        changed_prior_selections=[dict(target_id=c['target_id'], old_group=c['old_group'],new_group=c['new_group'])
            for c in comparison if c['old_group'] is not None and c['new_group'] != c['old_group']],
        provisional_native_mapping_count=mapping_count, excluded_provisional_mappings=mapping_removed,
        user_judgments_used_for_prediction=False, check_wsd_used_for_prediction=False,
        api_called=False, automatic_adoption=False, accuracy_established=False)
    if any(sha(source/n) != frozen_hashes[n] for n in names):
        raise RuntimeError('frozen_input_changed_during_comparison')
    output.mkdir(parents=True)
    for i,b in enumerate(bundles):
        atomic(output/f'documents/{i:02d}.json',b)
    atomic(output/'CONTEXT_DICTIONARY.json',dict(schema='mp_first_context_dictionary.v1',patterns=dictionary))
    atomic(output/'DECISIONS.json',dict(schema='mp_first_decisions.v1',decisions=new_decisions))
    atomic(output/'COMPARISON.json',dict(schema=summary['schema'],rows=comparison))
    summary['files']={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*.json')}
    summary['code_sha256']={n:sha(REPO/'scripts/python'/n) for n in
                          ['homonym_context_core.py','homonym_morphology.py','homonym_food_context.py','run_homonym_morphology_comparison.py']}
    atomic(output/'SUMMARY.json',summary)
    print({k:v for k,v in summary.items() if k not in ['files','code_sha256','input_sha256','changed_prior_selections','excluded_provisional_mappings']})
    print('changed_prior_selections',len(summary['changed_prior_selections']),
          'excluded_provisional_mappings',len(mapping_removed))
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    a=p.parse_args(); run(a.source,a.output)

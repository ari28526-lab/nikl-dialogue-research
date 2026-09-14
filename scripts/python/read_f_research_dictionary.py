"""Bind unchanged dictionary interfaces to the explicit local snapshot, read-only."""
import json, sys
from pathlib import Path

def open_dictionary():
    package=Path(__file__).resolve().parent
    catalog=json.loads((package/'CATALOG.json').read_text(encoding='utf-8'))
    if catalog['status']!='copied_sha_verified' or not catalog['sejong_supplement_actually_used']:
        raise ValueError('Unverified dictionary snapshot')
    sys.path.insert(0,str(package/'04_CODE'))
    import build_context_evidence
    build_context_evidence.OUT=package/'01_BASE'
    build_context_evidence.ROOT=package
    import context_full_lexicon
    context_full_lexicon.BASE=package/'01_BASE'
    context_full_lexicon.FULL=package/'01_BASE'
    import build_sejong_supplement
    build_sejong_supplement.ROOT=package/'02_SEJONG'
    import sejong_supplement
    return sejong_supplement.supplemented_dictionary(package/'02_SEJONG')

if __name__=='__main__':
    d=open_dictionary()
    try:
        r=d.lex.analyze('맛','NNG')
        print(json.dumps(dict(status='read_only_lookup_passed',base_open=True,sejong_supplement_open=d.sejong.c is not None,definition_bridge_open=d.sejong.bridge is not None,context_patterns_open=d.sejong.patterns is not None,candidate_groups=len(r['groups']),api_called=False,human_semantic_correctness_claimed=False)))
    finally:d.close()

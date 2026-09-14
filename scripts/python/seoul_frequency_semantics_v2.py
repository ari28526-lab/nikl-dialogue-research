"""Reuse Seoul machine WSD without promoting it to human gold. No API calls."""
import gzip,json
from frequency_sources_v1 import seoul_utterances as original_utterances

POLICY='seoul_machine_draft_v2_agreement_then_single_available_conflicts_hold'
def select(r):
 c=r['comparison'];st=c['status'];b=c.get('bareun_group');d=c.get('dictionary_group')
 def valid(g):return g is not None and str(g).isdigit() and int(g)>0
 for g in (b,d):
  if g is not None and not valid(g):raise ValueError('Invalid homonym group')
 b=str(b) if b is not None else None;d=str(d) if d is not None else None
 if st=='same_homonym_group':
  assert b is not None and b==d;g=b;basis='bareun_dictionary_agreement'
 elif st=='bareun_group_dictionary_undecided':
  assert b is not None and d is None;g=b;basis='bareun_only'
 elif st=='dictionary_proposal_bareun_unmapped':
  assert b is None and d is not None;g=d;basis='dictionary_only_candidate'
 elif st=='group_conflict':
  assert b is not None and d is not None and b!=d;g=None;basis='conflict_hold'
 elif st in {'both_unresolved_or_unmapped','not_lexical_target'}:
  assert b is None and d is None;g=None;basis=st
 else:raise ValueError('Unknown comparison status: '+st)
 if r.get('source_gap_in_utterance'):
  g=None;basis='source_gap_hold'
 return g,basis

def prepare(source):
 with gzip.open(source['path'],'rt',encoding='utf-8') as f:raw=json.load(f)
 by={};ledger=[]
 for ordinal,r in enumerate(raw['results']):
  m=r['bareun'];c=r['comparison'];key=(m['utt_id'],m['request_id'],m['sentence_index'],m['token_index'])
  g,basis=select(r);by.setdefault(key,[]).append((m['morph'],m['pos'],g,basis))
  ledger.append((source['source_id'],ordinal,m['utt_id'],str(m['request_id']),m['sentence_index'],m['token_index'],m['morph'],m['pos'],c['status'],c.get('bareun_group'),c.get('dictionary_group'),g,basis,0))
 def rows():
  seen=0
  for u in original_utterances(source):
   for t in u['tokens']:
    records=by.pop((u['utt_id'],*t['token_index']))
    assert len(records)==len(t['morphs'])
    for m,(lemma,pos,g,basis) in zip(t['morphs'],records):
     assert (m['lemma'],m['pos'])==(lemma,pos)
     m['group']=g;m['semantic_basis']=basis;m['human_verified']=False;seen+=1
   yield u
  assert not by and seen==len(ledger)
 return rows(),ledger

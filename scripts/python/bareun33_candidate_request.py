"""Prepare one census-selected context without transport or semantic updates.

The caller verifies complete census/source receipts and supplies the global
candidate-primary frequency lookup. Parent context IDs, not derived IDs, govern
prior-response reuse and uncertain-call quarantine.
"""
import copy
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def prepare(original, selected_ids, targets, expected_parent_sha, frequency,
            prior_context_states):
    if digest(original) != expected_parent_sha:
        raise ValueError('parent_request_changed')
    parent_id = original['request_id']
    ids = list(selected_ids)
    owners = original['target_ids']
    by_id = {t['target_id']: t for t in targets}
    if (not ids or len(set(ids)) != len(ids) or len(set(owners)) != len(owners)
            or len(by_id) != len(targets) or not set(ids) <= set(owners)
            or not set(ids) <= set(by_id)):
        raise ValueError('candidate_target_ownership')
    # Preserve parent target ordering so identity cannot change with input order.
    ids = [tid for tid in owners if tid in set(ids)]
    priorities = {}
    scores = []
    for tid in ids:
        target = by_id[tid]
        priority = target['priority']
        if priority not in {'primary', 'dialect_later'}:
            raise ValueError('unknown_priority')
        if original['target_priorities'][tid] != priority:
            raise ValueError('parent_priority_changed')
        priorities[tid] = priority
        if priority == 'primary':
            n = frequency(target['lemma'], target['pos'])
            if type(n) is not int or n <= 0:
                raise ValueError('missing_global_candidate_frequency')
            scores.append(n)
    prior = prior_context_states.get(parent_id)
    if prior not in {None, 'response_verified', 'uncertain_no_retry'}:
        raise ValueError('unrecognized_prior_context_state')
    disposition = ('reuse_saved_response' if prior == 'response_verified' else
                   'quarantine_no_retry' if prior == 'uncertain_no_retry' else
                   'ready_for_runner_validation')
    job = copy.deepcopy(original)
    job['parent_request_id'] = parent_id
    job['target_ids'] = ids
    job['target_priorities'] = priorities
    job['request_id'] = 'candidate_first:' + digest([parent_id, ids])
    return dict(job=job, disposition=disposition,
                sort_key=[0 if scores else 1, -max(scores, default=0), parent_id],
                primary_targets=len(scores), dialect_targets=len(ids)-len(scores),
                parent_request_sha256=expected_parent_sha,
                context_preserved=True, transport_authorized=False)

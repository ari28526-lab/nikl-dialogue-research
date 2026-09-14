"""Bounded 18-pair short-context pilot, isolated from production.

Maximum 40 new calls including at most one retry per request. Durable attempts
are counted across restarts. An uncertain interrupted attempt is never retried.
"""
import argparse
import json
from pathlib import Path
import time

from diagnose_wsd_context_request import safe_error
from diagnose_wsd_short_context import crop, DEST as PREVIOUS
from review_wsd_short_context import compare_exact
from run_wsd_context_comparison import (ROOT, OUTPUT, MANIFEST, prepare, read_json,
    digest, canonical, atomic, exclusive, storage, project, live_client)

DEST = OUTPUT.with_name(OUTPUT.name + '_short_pilot')
TOKEN = 'BAREUN_SHORT_CONTEXT_PILOT_20260905'
MAX_CALLS = 40
MAX_CHARS = 12000
SESSION_SECONDS = 900
RETRYABLE = {'UNAVAILABLE', 'DEADLINE_EXCEEDED'}


def build_jobs(jobs):
    selected = []
    for i in range(18):
        solo = dict(next(j for j in jobs if j['id'] == f'{i:02d}_standalone'))
        original = next(j for j in jobs if j['id'] == f'{i:02d}_context')
        context = dict(crop(original, 300), id=f'{i:02d}_context', pair=i, mode='context')
        context['context_added'] = context['text_sha256'] != solo['text_sha256']
        selected.extend([solo, context])
    if len(selected) != 36 or any(len(j['text']) > 300 for j in selected):
        raise ValueError('pilot_size_contract')
    return selected


def job_ref(job):
    return dict(id=job['id'], request_sha256=job['text_sha256'], chars=len(job['text']),
                mapping_sha256=digest(canonical(job['mappings'])))


def verify_result(value, binding):
    if value['binding'] != binding or value['response_sha256'] != digest(canonical(value['response'])):
        raise ValueError('result_integrity')
    return value


def attempt_inventory(root):
    attempts = [read_json(p) for p in root.glob('*/attempt_*.intent.json')]
    return len(attempts), sum(a['chars'] for a in attempts)


def acquire(root, job, binding, call, reused=None, sleep=time.sleep):
    folder = root/job['id']
    folder.mkdir(exist_ok=True)
    result_path = folder/'RESULT.json'
    if result_path.exists():
        return verify_result(read_json(result_path), binding), None
    if reused is not None:
        if list(folder.glob('attempt_*.intent.json')):
            raise ValueError('reuse_conflicts_with_attempt')
        value = dict(binding=binding, response=reused['response'],
                     response_sha256=digest(canonical(reused['response'])),
                     elapsed_seconds=reused['elapsed_seconds'], origin='verified_prior_response',
                     source_result_sha256=reused['source_result_sha256'])
        atomic(result_path, value)
        return value, None
    for attempt in (1, 2):
        intent_path = folder/f'attempt_{attempt}.intent.json'
        attempt_result = folder/f'attempt_{attempt}.result.json'
        error_path = folder/f'attempt_{attempt}.error.json'
        if intent_path.exists():
            if read_json(intent_path) != dict(binding=binding, chars=len(job['text'])):
                raise ValueError('attempt_binding_changed')
            if attempt_result.exists():
                value = verify_result(read_json(attempt_result), binding)
                atomic(result_path, value)
                return value, None
            if not error_path.exists():
                return None, dict(status='paused_uncertain_attempt', retry_automatically=False)
            error = read_json(error_path)
            if error.get('error_code') not in RETRYABLE or attempt == 2:
                return None, error
            continue
        # Refuse an orphan error/result rather than issuing an untracked call.
        if attempt_result.exists() or error_path.exists():
            raise ValueError('orphan_attempt_artifact')
        count, chars = attempt_inventory(root)
        if count >= MAX_CALLS or chars+len(job['text']) > MAX_CHARS:
            return None, dict(status='paused_call_budget')
        if attempt == 2:
            sleep(10)
        storage()
        atomic(intent_path, dict(binding=binding, chars=len(job['text'])))
        started = time.monotonic()
        try:
            response = call(job['text'])
        except Exception as exc:
            error = dict(status='api_failure', elapsed_seconds=round(time.monotonic()-started, 3),
                         **safe_error(exc))
            atomic(error_path, error)
            if error['error_code'] not in RETRYABLE or attempt == 2:
                return None, error
            continue
        value = dict(binding=binding, response=response, response_sha256=digest(canonical(response)),
                     elapsed_seconds=round(time.monotonic()-started, 3), origin='new_api_call')
        atomic(attempt_result, value)
        atomic(result_path, value)
        return value, None
    raise ValueError('unreachable_attempt_state')


def run(root, jobs, contract, call, reusable=None):
    reusable = reusable or {}
    with exclusive(root):
        path = root/'CONTRACT.json'
        if path.exists() and read_json(path) != contract:
            raise ValueError('pilot_contract_changed')
        if not path.exists():
            atomic(path, contract)
        started, failures = time.monotonic(), 0
        completed, projections = [], {}
        stop = None
        for job in jobs:
            if time.monotonic()-started > SESSION_SECONDS:
                stop = dict(status='paused_session_budget')
                break
            binding = dict(contract_sha256=digest(canonical(contract)), job=job_ref(job))
            atomic(root/'STATE.json', dict(status='running', completed_jobs=len(completed),
                                          total_jobs=len(jobs), current_job=job['id'],
                                          calls_attempted=attempt_inventory(root)[0]))
            result, error = acquire(root, job, binding, call, reusable.get(job['id']))
            if error:
                failures += 1
                completed.append(dict(id=job['id'], status='failed', error=error))
                if (error.get('error_code') not in RETRYABLE or failures >= 3):
                    stop = error
                    break
                continue
            failures = 0
            projection = project(result['response'], job['text'], job['mappings'])
            atomic(root/job['id']/'PROJECTION.json', projection)
            projections[job['id']] = projection
            completed.append(dict(id=job['id'], status='saved', chars=len(job['text']),
                                  elapsed_seconds=result['elapsed_seconds'], origin=result['origin'],
                                  held_units=len(projection['held'])))
        pairs = []
        for i in sorted({j['pair'] for j in jobs}):
            a, b = f'{i:02d}_standalone', f'{i:02d}_context'
            if a not in projections or b not in projections:
                pairs.append(dict(pair=i, status='incomplete_api_pair'))
                continue
            target = next(j for j in jobs if j['id'] == a)['target_utt_id']
            rows = [[m for m in projections[name]['assigned'] if m['utt_id'] == target] for name in (a, b)]
            held = sum(len(projections[name]['held']) for name in (a, b))
            if held or not all(rows):
                pairs.append(dict(pair=i, status='hold_projection', held_units=held))
            else:
                pairs.append(dict(pair=i, status='reviewed', **compare_exact(*rows)))
        report = dict(status='paused' if stop else 'completed_pending_review', stop_reason=stop,
                      jobs=completed, pairs=pairs, calls_attempted=attempt_inventory(root)[0],
                      request_chars_attempted=attempt_inventory(root)[1],
                      total_jobs=len(jobs), production_ready=False, semantic_improvement_established=False)
        atomic(root/'REPORT.json', report)
        atomic(root/'STATE.json', dict(status=report['status'], completed_jobs=len(completed),
                                      saved_jobs=sum(j['status']=='saved' for j in completed),
                                      calls_attempted=report['calls_attempted'], stop_reason=stop,
                                      failed_jobs=sum(j['status']=='failed' for j in completed)))
        print(json.dumps(report), flush=True)
        return 0 if not stop and all(j['status']=='saved' for j in completed) else 1


def preflight():
    jobs, original, free = prepare()
    selected = build_jobs(jobs)
    prior = read_json(PREVIOUS/'CONTRACT.json')
    if prior['original'] != original:
        raise ValueError('prior_contract_changed')
    reusable = {}
    for new_id, old_id in (('00_standalone', 'control'), ('00_context', 'context_300')):
        job = next(j for j in selected if j['id'] == new_id)
        ref = next(j for j in prior['jobs'] if j['id'] == old_id)
        if ref['sha256'] != job['text_sha256'] or ref['chars'] != len(job['text']):
            raise ValueError('prior_request_changed')
        path = PREVIOUS/old_id/'RESULT.json'
        result = verify_result(read_json(path), dict(batch=prior, request_sha256=job['text_sha256']))
        reusable[new_id] = dict(result, source_result_sha256=digest(path.read_bytes()))
    dependencies = ['run_wsd_short_context_pilot.py', 'diagnose_wsd_short_context.py',
                    'diagnose_wsd_context_request.py', 'review_wsd_short_context.py']
    contract = dict(schema='wsd_short_context_18pairs.v1', original=original,
                    jobs=[job_ref(j) for j in selected], max_calls=MAX_CALLS, max_chars=MAX_CHARS,
                    max_attempts_per_job=2, retry_wait_seconds=10,
                    prior_results={k:v['source_result_sha256'] for k,v in reusable.items()},
                    dependencies={p:digest((ROOT/'scripts/python'/p).read_bytes()) for p in dependencies})
    if (DEST/'CONTRACT.json').exists() and read_json(DEST/'CONTRACT.json') != contract:
        raise ValueError('existing_contract_changed')
    print(json.dumps(dict(status='preflight_passed', total_jobs=len(selected), reused=len(reusable),
                          max_new_calls=MAX_CALLS, initial_new_calls=len(selected)-len(reusable),
                          new_request_chars=sum(len(j['text']) for j in selected if j['id'] not in reusable),
                          no_added_context=[j['id'] for j in selected if j.get('context_added') is False],
                          free_gib=free, api_called=False)), flush=True)
    return selected, contract, reusable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approval-token', default='')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        if args.execute:
            raise ValueError('conflicting_modes')
        print(json.dumps(read_json(DEST/'STATE.json') if (DEST/'STATE.json').exists() else {'status':'not_started'}))
        return 0
    if args.execute and args.approval_token != TOKEN:
        raise ValueError('bounded_pilot_approval_required')
    print(json.dumps(dict(status='verifying_inputs_no_api')), flush=True)
    selected, contract, reusable = preflight()
    if not args.execute:
        return 0
    client, call = live_client(read_json(ROOT/'config/bareun_wsd_full_f_20260905.json'))
    try:
        return run(DEST, selected, contract, call, reusable)
    finally:
        client.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='pilot_stopped', **safe_error(exc))), flush=True)
        raise SystemExit(1) from None

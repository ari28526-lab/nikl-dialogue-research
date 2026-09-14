"""At most three new WSD calls: fresh control, <=300 and <=600 character contexts.

Whole utterances only. No automatic retry, no production or source mutation.
"""
import argparse
import json
from pathlib import Path

from diagnose_wsd_context_request import run_one, safe_error
from run_wsd_context_comparison import (ROOT, OUTPUT, prepare, digest, canonical,
    read_json, atomic, exclusive, project, live_client)

DEST = OUTPUT.with_name(OUTPUT.name + '_short_context_three')
TOKEN = 'BAREUN_SHORT_CONTEXT_3_CALLS_20260905'


def crop(job, cap):
    maps = job['mappings']
    targets = [i for i, m in enumerate(maps) if m['utt_id'] == job['target_utt_id']]
    if len(targets) != 1:
        raise ValueError('target_not_unique')
    lo = hi = targets[0]
    if maps[hi]['end_utf32'] - maps[lo]['begin_utf32'] > cap:
        raise ValueError('target_exceeds_cap')
    while True:
        options = []
        if lo > 0:
            options.append((maps[hi]['end_utf32'] - maps[lo-1]['begin_utf32'], lo-1, hi))
        if hi+1 < len(maps):
            options.append((maps[hi+1]['end_utf32'] - maps[lo]['begin_utf32'], lo, hi+1))
        options = [x for x in options if x[0] <= cap]
        if not options:
            break
        _, lo, hi = min(options)
    begin, end = maps[lo]['begin_utf32'], maps[hi]['end_utf32']
    text = job['text'][begin:end]
    mappings = [dict(m, begin_utf32=m['begin_utf32']-begin,
                     end_utf32=m['end_utf32']-begin) for m in maps[lo:hi+1]]
    return dict(id='context_'+str(cap), text=text, text_sha256=digest(text.encode()),
                mappings=mappings, target_utt_id=job['target_utt_id'], cap=cap)


def select_jobs(jobs):
    control = dict(next(j for j in jobs if j['id'] == '00_standalone'), id='control')
    context = next(j for j in jobs if j['id'] == '00_context')
    selected = [control]
    for cap in (300, 600):
        item = crop(context, cap)
        if item['text_sha256'] not in {j['text_sha256'] for j in selected}:
            selected.append(item)
    if len(selected) < 2 or sum(len(j['text']) for j in selected) > 1500:
        raise ValueError('no_distinct_context_or_budget_exceeded')
    return selected


def run_batch(root, binding, jobs, call):
    with exclusive(root):
        contract = root/'CONTRACT.json'
        if contract.exists() and read_json(contract) != binding:
            raise ValueError('short_context_contract_changed')
        if (root/'STARTED.json').exists():
            state = read_json(root/'STATE.json') if (root/'STATE.json').exists() else {}
            print(json.dumps(dict(status='already_attempted_no_new_calls', previous=state)), flush=True)
            return 1
        atomic(contract, binding)
        atomic(root/'STARTED.json', dict(max_new_calls=len(jobs)))
        reports = []
        for job in jobs:
            atomic(root/'STATE.json', dict(status='running_bounded_diagnostic', current_job=job['id'],
                                          completed_jobs=reports, max_new_calls=len(jobs)))
            result = run_one(root/job['id'], dict(batch=binding, request_sha256=job['text_sha256']),
                             job['text'], call)
            if result is None:
                error = read_json(root/job['id']/'STATE.json')
                reports.append(dict(id=job['id'], chars=len(job['text']), outcome='failed', error=error))
                # A failing short control cannot support a length comparison.
                # Only a distinct larger-context experiment may follow UNAVAILABLE.
                if job['id'] == 'control' or error.get('error_code') != 'UNAVAILABLE':
                    break
            else:
                projection = project(result['response'], job['text'], job['mappings'])
                atomic(root/job['id']/'PROJECTION.json', projection)
                reports.append(dict(id=job['id'], chars=len(job['text']), outcome='response_saved',
                                    elapsed_seconds=result['elapsed_seconds'],
                                    held_units=len(projection['held'])))
        state = dict(status='bounded_diagnostic_finished_pending_review', jobs=reports,
                     max_new_calls=len(jobs), production_resumed=False,
                     semantic_improvement_established=False, retry_automatically=False)
        atomic(root/'STATE.json', state)
        print(json.dumps(state), flush=True)
        return 0 if all(r['outcome'] == 'response_saved' for r in reports) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approval-token', default='')
    args = parser.parse_args()
    if args.execute and args.approval_token != TOKEN:
        raise ValueError('three_call_approval_required')
    print(json.dumps(dict(status='verifying_frozen_inputs_no_api')), flush=True)
    jobs, original, free = prepare()
    if read_json(OUTPUT/'CONTRACT.json') != original:
        raise ValueError('original_contract_changed')
    selected = select_jobs(jobs)
    binding = dict(schema='wsd_short_context_diagnostic.v1', original=original,
                   code_sha256=digest(Path(__file__).read_bytes()),
                   helper_sha256=digest((ROOT/'scripts/python/diagnose_wsd_context_request.py').read_bytes()),
                   jobs=[dict(id=j['id'], chars=len(j['text']), sha256=j['text_sha256']) for j in selected],
                   max_new_calls=len(selected), whole_utterances_only=True)
    if (DEST/'CONTRACT.json').exists() and read_json(DEST/'CONTRACT.json') != binding:
        raise ValueError('existing_diagnostic_contract_changed')
    print(json.dumps(dict(status='preflight_passed', jobs=binding['jobs'], free_gib=free,
                          max_new_calls=len(selected), api_called=False)), flush=True)
    if not args.execute:
        return 0
    client, call = live_client(read_json(ROOT/'config/bareun_wsd_full_f_20260905.json'))
    try:
        return run_batch(DEST, binding, selected, call)
    finally:
        client.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='short_context_stopped', **safe_error(exc))), flush=True)
        raise SystemExit(1) from None

"""One explicitly authorized diagnostic retry; never resume the 36-call pilot.

The original call may have been charged. Preserve its intent/result and bind
this separate diagnostic to the original contract and exact request hash.
"""
import argparse
import json
from pathlib import Path
import time

from run_wsd_context_comparison import (ROOT, OUTPUT, prepare, storage, digest, canonical,
                                        read_json, atomic, exclusive, project, compare, live_client)

DIAGNOSTIC = OUTPUT.with_name(OUTPUT.name + '_diagnostic_one')
TOKEN = 'BAREUN_CONTEXT_DIAGNOSTIC_ONE_CALL_20260905'
CODES = {'CANCELED', 'UNKNOWN', 'INVALID_ARGUMENT', 'DEADLINE_EXCEEDED', 'NOT_FOUND',
         'ALREADY_EXISTS', 'PERMISSION_DENIED', 'RESOURCE_EXHAUSTED', 'FAILED_PRECONDITION',
         'ABORTED', 'OUT_OF_RANGE', 'UNIMPLEMENTED', 'INTERNAL', 'UNAVAILABLE', 'DATA_LOSS',
         'UNAUTHENTICATED'}


def safe_error(exc):
    """Emit only known enum/flags. Never serialize error text, details or headers."""
    code = getattr(getattr(exc, 'code', None), 'name', None)
    message = getattr(exc, 'message', '')
    message = message.lower() if isinstance(message, str) else ''
    return dict(error_type=type(exc).__name__, error_code=code if code in CODES else 'UNCLASSIFIED',
                gateway_timeout_hint='gateway timeout' in message or 'gateway_timeout' in message,
                http_504_hint='504' in message,
                raw_error_stored=False, retry_automatically=False)


def run_one(root, binding, text, call):
    with exclusive(root):
        contract_path = root/'CONTRACT.json'
        if contract_path.exists() and read_json(contract_path) != binding:
            raise ValueError('diagnostic_contract_changed')
        if not contract_path.exists():
            atomic(contract_path, binding)
        result_path = root/'RESULT.json'
        if result_path.exists():
            result = read_json(result_path)
            if result['binding'] != binding or result['response_sha256'] != digest(canonical(result['response'])):
                raise ValueError('diagnostic_result_integrity')
            return result
        if (root/'INTENT.json').exists():
            print(json.dumps(read_json(root/'STATE.json') if (root/'STATE.json').exists()
                             else {'status': 'prior_diagnostic_uncertain_do_not_retry'}))
            return None
        storage()
        atomic(root/'INTENT.json', dict(binding=binding, max_api_calls=1))
        atomic(root/'STATE.json', dict(status='calling_one_diagnostic', max_api_calls=1))
        started = time.monotonic()
        try:
            response = call(text)
        except Exception as exc:
            state = dict(status='diagnostic_failed_no_retry', elapsed_seconds=round(time.monotonic()-started, 3),
                         **safe_error(exc))
            atomic(root/'STATE.json', state)
            print(json.dumps(state), flush=True)
            return None
        result = dict(binding=binding, response=response, response_sha256=digest(canonical(response)),
                      elapsed_seconds=round(time.monotonic()-started, 3))
        atomic(result_path, result)
        atomic(root/'STATE.json', dict(status='response_saved_pending_comparison', elapsed_seconds=result['elapsed_seconds']))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approval-token', default='')
    args = parser.parse_args()
    jobs, contract, free = prepare()
    original = read_json(OUTPUT/'CONTRACT.json')
    if original != contract:
        raise ValueError('original_pilot_contract_changed')
    context = next(j for j in jobs if j['id'] == '00_context')
    standalone = next(j for j in jobs if j['id'] == '00_standalone')
    intent = read_json(OUTPUT/'00_context.intent.json')
    if intent != dict(contract_sha256=digest(canonical(original)), request_sha256=context['text_sha256']):
        raise ValueError('original_intent_changed')
    if (OUTPUT/'00_context.result.json').exists():
        raise ValueError('original_response_already_available_no_retry_needed')
    saved = read_json(OUTPUT/'00_standalone.result.json')
    if (saved['request_sha256'] != standalone['text_sha256'] or
            saved['contract_sha256'] != digest(canonical(original)) or
            saved['response_sha256'] != digest(canonical(saved['response']))):
        raise ValueError('original_standalone_integrity')
    binding = dict(original_contract_sha256=digest(canonical(original)), request_sha256=context['text_sha256'],
                   diagnostic_code_sha256=digest(Path(__file__).read_bytes()), max_api_calls=1)
    print(json.dumps(dict(status='diagnostic_preflight_passed', max_new_calls=1, request_chars=len(context['text']),
                          previous_response_reused=True, free_gib=free, api_called=False)), flush=True)
    if not args.execute:
        return 0
    if args.approval_token != TOKEN:
        raise ValueError('one_diagnostic_token_required')
    client, call = live_client(read_json(ROOT/'config/bareun_wsd_full_f_20260905.json'))
    try:
        result = run_one(DIAGNOSTIC, binding, context['text'], call)
    finally:
        client.close()
    if result is None:
        return 1
    items = []
    for job, response, seconds in ((standalone, saved['response'], saved['elapsed_seconds']),
                                    (context, result['response'], result['elapsed_seconds'])):
        items.append(dict(id=job['id'], pair=0, mode=job['mode'], target_utt_id=job['target_utt_id'],
                          elapsed_seconds=seconds, projection=project(response, job['text'], job['mappings'])))
    atomic(DIAGNOSTIC/'PROJECTIONS.json', items)
    atomic(DIAGNOSTIC/'COMPARISON.json', compare(items))
    state = dict(status='diagnostic_completed_pending_review', new_calls_at_most=1,
                 semantic_improvement_established=False, production_resumed=False)
    atomic(DIAGNOSTIC/'STATE.json', state)
    print(json.dumps(state), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='diagnostic_stopped', **safe_error(exc))))
        raise SystemExit(1) from None

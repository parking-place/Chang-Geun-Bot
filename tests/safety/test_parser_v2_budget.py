import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from changgeun_inference.contracts_v2 import ParseCall, RootRequest
from changgeun_inference.ledger import Ledger, LedgerError
from changgeun_inference.ledger_v2 import ParserLedger


def root(identifier='root'):
    now = time.time()
    return RootRequest(request_id=identifier, scope_hash='a' * 64,
                       original_hash='b' * 64, config_hash='c' * 64,
                       created_at=now, expires_at=now + 35)


def call(root_request, operation, *, pass_id=None, stage_index=None, suffix=''):
    kwargs = dict(root=root_request, call_id=f'{operation}-{pass_id or "llm"}-{suffix}',
                  operation=operation, pass_id=pass_id, stage_index=stage_index, state={})
    if operation in {'rewrite', 'full_parse'}:
        kwargs['output_schema'] = {'type': 'object', 'properties': {}}
    else:
        kwargs['questions'] = {'q': {'type': 'choice', 'instructions': 'choose',
                                    'criteria': {'a': 'A', '__NONE__': 'None'}}}
    return ParseCall(**kwargs)


def ledger(tmp_path):
    return ParserLedger(Ledger(tmp_path / 'gateway.sqlite', tmp_path / 'owners.sqlite'))


def reserve_finish(book, request, *, cost=0, run='same-run', limit=3000):
    number = book.reserve(request, run_id=run, max_jev_run_calls=limit,
                          llm_cost_micro_usd=cost)
    book.mark_attempted(request)
    book.finish(request, {'attempt_no': number})
    return number


def test_exact_eight_slots_and_shared_jev_run_budget(tmp_path):
    book = ledger(tmp_path)
    request = root()
    ordered = [call(request, 'command_select', pass_id='initial', stage_index=1),
               call(request, 'argument_select', pass_id='initial', stage_index=2),
               call(request, 'context_select', pass_id='initial', stage_index=3),
               call(request, 'rewrite'),
               call(request, 'command_select', pass_id='after_rewrite', stage_index=1),
               call(request, 'argument_select', pass_id='after_rewrite', stage_index=2),
               call(request, 'context_select', pass_id='after_rewrite', stage_index=3),
               call(request, 'full_parse')]
    assert [reserve_finish(book, item, cost=100_000 if item.operation in {
        'rewrite', 'full_parse'} else 0) for item in ordered] == list(range(1, 9))
    assert book.usage('same-run')['jev_run_reserved'] == 6
    assert book.usage('same-run')['gpt_reserved_micro_usd'] == 200_000
    with pytest.raises(LedgerError, match='root_budget_exhausted'):
        book.reserve(call(request, 'full_parse', suffix='again'), run_id='same-run',
                     max_jev_run_calls=3000, llm_cost_micro_usd=100_000)


def test_unknown_dispatch_consumes_slot_and_restart_cannot_reuse(tmp_path):
    book = ledger(tmp_path)
    request = root()
    first = call(request, 'command_select', pass_id='initial', stage_index=1)
    assert book.reserve(first, run_id='same-run', max_jev_run_calls=3000) == 1
    book.mark_attempted(first)
    restarted = ledger(tmp_path)
    with pytest.raises(LedgerError, match='dispatch_unknown_or_failed'):
        restarted.lookup(first)
    with pytest.raises(LedgerError, match='previous_run_request_conflict'):
        restarted.reserve(call(request, 'argument_select', pass_id='initial', stage_index=2),
                          run_id='new-run', max_jev_run_calls=3000)
    assert restarted.usage('same-run')['jev_run_reserved'] == 1


def test_gpt_one_dollar_limit_is_durable_and_not_refunded(tmp_path):
    book = ledger(tmp_path)
    request = root()
    reserve_finish(book, call(request, 'command_select', pass_id='initial', stage_index=1))
    reserve_finish(book, call(request, 'rewrite'), cost=700_000)
    with pytest.raises(LedgerError, match='gpt_validation_budget_exhausted'):
        book.reserve(call(request, 'full_parse'), run_id='same-run',
                     max_jev_run_calls=3000, llm_cost_micro_usd=400_000)
    assert ledger(tmp_path).usage('same-run')['gpt_reserved_micro_usd'] == 700_000
    reserve_finish(book, call(request, 'full_parse'), cost=300_000)
    assert ledger(tmp_path).usage('same-run')['gpt_reserved_micro_usd'] == 1_000_000


def test_concurrent_duplicate_and_cancel_fail_closed(tmp_path):
    book = ledger(tmp_path)
    request = root()
    first = call(request, 'command_select', pass_id='initial', stage_index=1)
    def attempt():
        try:
            return book.reserve(first, run_id='same-run', max_jev_run_calls=3000)
        except LedgerError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert results.count(1) == 1
    assert book.usage('same-run')['jev_run_reserved'] == 1
    book.cancel(request.request_id)
    with pytest.raises(LedgerError, match='root_cancelled'):
        book.finish(first, {'ok': True})


def test_pass_order_and_late_deadline(tmp_path):
    book = ledger(tmp_path)
    request = root()
    first = call(request, 'command_select', pass_id='initial', stage_index=1)
    reserve_finish(book, first)
    with pytest.raises(LedgerError, match='rewrite_required'):
        book.reserve(call(request, 'command_select', pass_id='after_rewrite', stage_index=1),
                     run_id='same-run', max_jev_run_calls=3000)
    expired = RootRequest(request_id='expired', scope_hash='a' * 64,
                          original_hash='b' * 64, config_hash='c' * 64,
                          created_at=1.0, expires_at=36.0)
    with pytest.raises(LedgerError, match='deadline_expired'):
        book.reserve(call(expired, 'command_select', pass_id='initial', stage_index=1),
                     run_id='same-run', max_jev_run_calls=3000)

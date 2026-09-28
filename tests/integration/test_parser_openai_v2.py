import json
import time

import httpx
import pytest

from changgeun.parser.llm_schema import rewrite_schema
from changgeun_inference.contracts_v2 import ParseCall, RootRequest, TokenUsage
from changgeun_inference.ledger import Ledger
from changgeun_inference.ledger_v2 import ParserLedger
from changgeun_inference.llm_profiles import LLMProfile, profile_from_environment
from changgeun_inference.openai_v2 import OpenAIResponsesProvider, ParserProviderRouter
from changgeun_inference.service_v2 import ParserService


def calls():
    now = time.time()
    root = RootRequest(request_id='root', scope_hash='a' * 64,
                       original_hash='b' * 64, config_hash='c' * 64,
                       created_at=now, expires_at=now + 35)
    first = ParseCall(root=root, call_id='first', operation='command_select',
                      pass_id='initial', stage_index=1, state={}, questions={
                          'q': {'type': 'choice', 'instructions': 'choose',
                                'criteria': {'a': 'A', 'b': 'B'}}})
    rewrite = ParseCall(root=root, call_id='rewrite', operation='rewrite', state={
        'original_message': '운동 목록 이름 바꿔줘'}, output_schema=rewrite_schema())
    return first, rewrite


def profile():
    return LLMProfile('gpt-5-nano', 'gpt-5-nano', api_key='test-only')


def success(body):
    return httpx.Response(200, json={
        'status': 'completed', 'model': 'gpt-5-nano',
        'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(body)}]}],
        'usage': {'input_tokens': 150, 'output_tokens': 60, 'total_tokens': 210,
                  'input_tokens_details': {'cached_tokens': 10},
                  'output_tokens_details': {'reasoning_tokens': 20}},
    })


@pytest.mark.asyncio
async def test_responses_payload_is_strict_stateless_and_single_attempt():
    seen = []
    expected = {'status': 'rewritten', 'rewritten_text': '운동 재생목록 이름을 바꿔줘',
                'unresolved_references': [], 'question': None}
    def route(request):
        seen.append(json.loads(request.content))
        assert request.url.path == '/v1/responses'
        return success(expected)
    provider = OpenAIResponsesProvider(profile(), transport=httpx.MockTransport(route))
    try:
        _, rewrite = calls()
        result, usage, model = await provider.parse(rewrite, 5)
    finally:
        await provider.close()
    assert result == expected and usage.input_tokens == 150 and model == 'gpt-5-nano'
    assert len(seen) == 1
    assert seen[0]['store'] is False and 'tools' not in seen[0]
    assert seen[0]['model'] == 'gpt-5-nano'
    assert seen[0]['text']['format']['strict'] is True
    assert seen[0]['reasoning'] == {'effort': 'minimal'}
    assert seen[0]['max_output_tokens'] == 1024


@pytest.mark.asyncio
async def test_refusal_preserves_usage_and_durable_cost(tmp_path):
    def route(_request):
        return httpx.Response(200, json={
            'status': 'completed', 'model': 'gpt-5-nano',
            'output': [{'type': 'message', 'content': [
                {'type': 'refusal', 'refusal': 'refused'}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120},
        })
    provider = OpenAIResponsesProvider(profile(), transport=httpx.MockTransport(route))
    book = ParserLedger(Ledger(tmp_path / 'ledger.sqlite', tmp_path / 'owners.sqlite'))
    first, rewrite = calls()
    book.reserve(first, run_id='same-run', max_jev_run_calls=3000)
    book.finish(first, {'ok': True})
    router = ParserProviderRouter(None, provider)
    service = ParserService(router, book, config_hash='c' * 64, run_id='same-run',
                            max_jev_run_calls=3000, llm_reservation=router.quote,
                            llm_actual=profile().actual_micro_usd)
    try:
        result = await service.parse(rewrite)
    finally:
        await provider.close()
    assert result['status'] == 'refused' and result['usage']['input_tokens'] == 100
    assert book.usage('same-run')['gpt_actual_micro_usd'] > 0
    assert book.usage('same-run')['gpt_unknown_cost_calls'] == 0
    assert book.usage('same-run')['gpt_reserved_micro_usd'] < 1_000_000


@pytest.mark.asyncio
async def test_reasoning_only_incomplete_is_charged_without_retry(tmp_path):
    calls_seen = 0

    def route(_request):
        nonlocal calls_seen
        calls_seen += 1
        return httpx.Response(200, json={
            'status': 'incomplete', 'model': 'gpt-5-nano', 'output': [],
            'usage': {'input_tokens': 200, 'output_tokens': 1024,
                      'total_tokens': 1224,
                      'output_tokens_details': {'reasoning_tokens': 1024}},
        })

    selected = profile()
    provider = OpenAIResponsesProvider(selected, transport=httpx.MockTransport(route))
    book = ParserLedger(Ledger(tmp_path / 'ledger.sqlite', tmp_path / 'owners.sqlite'))
    first, rewrite = calls()
    book.reserve(first, run_id='same-run', max_jev_run_calls=3000)
    book.finish(first, {'ok': True})
    router = ParserProviderRouter(None, provider)
    service = ParserService(router, book, config_hash='c' * 64, run_id='same-run',
                            max_jev_run_calls=3000, llm_reservation=router.quote,
                            llm_actual=selected.actual_micro_usd)
    try:
        result = await service.parse(rewrite)
    finally:
        await provider.close()
    assert calls_seen == 1
    assert result['status'] == 'incomplete' and result['result'] is None
    assert result['usage']['reasoning_tokens'] == 1024
    assert book.usage('same-run')['gpt_actual_micro_usd'] == 420


def test_profiles_fail_closed_and_quote_stays_below_dollar():
    assert profile_from_environment({'LLM_FALLBACK': 'disabled'}).enabled is False
    for environment in ({'LLM_FALLBACK': 'luna'}, {'LLM_FALLBACK': ''}, {},
                        {'OPENAI_FALLBACK_MODEL': 'legacy', 'OPENAI_API_KEY': 'x'}):
        with pytest.raises(ValueError):
            profile_from_environment(environment)
    selected = profile_from_environment({'OPENAI_API_KEY': 'test-only'})
    assert selected.model_id == 'gpt-5-nano'
    _, rewrite = calls()
    provider = OpenAIResponsesProvider(selected)
    assert 0 < provider.quote(rewrite) < 1_000_000
    assert selected.actual_micro_usd(TokenUsage()) is None

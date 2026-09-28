import asyncio
import time

import httpx
import pytest

from changgeun_inference.contracts_v2 import ParseCall, RootRequest, TokenUsage
from changgeun_inference.ledger import Ledger
from changgeun_inference.ledger_v2 import ParserLedger
from changgeun_inference.providers import MockProvider
from changgeun_inference.server import create_app
from changgeun_inference.service import DecisionService, ServiceError
from changgeun_inference.service_v2 import ParserService


class RecordingProvider:
    def __init__(self, delay=0):
        self.calls = 0
        self.delay = delay

    async def parse(self, call, timeout):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return {'q': {'type': 'choice', 'choice': 'a'}}, TokenUsage(), 'mock'


def request():
    now = time.time()
    root = RootRequest(request_id='root', scope_hash='a' * 64,
                       original_hash='b' * 64, config_hash='c' * 64,
                       created_at=now, expires_at=now + 35)
    return ParseCall(root=root, call_id='initial-1', operation='command_select',
                     pass_id='initial', stage_index=1, state={}, questions={
                         'q': {'type': 'choice', 'instructions': 'choose',
                               'criteria': {'a': 'A', '__NONE__': 'None'}}})


def service(tmp_path, provider):
    ledger = ParserLedger(Ledger(tmp_path / 'ledger.sqlite', tmp_path / 'owners.sqlite'))
    return ParserService(provider, ledger, config_hash='c' * 64, run_id='same-run',
                         max_jev_run_calls=3000)


@pytest.mark.asyncio
async def test_concurrent_identical_call_joins_and_replay_costs_zero(tmp_path):
    provider = RecordingProvider(0.02)
    parser = service(tmp_path, provider)
    call = request()
    first, joined = await asyncio.gather(parser.parse(call), parser.parse(call))
    assert provider.calls == 1
    assert {first['cache_hit'], joined['cache_hit']} == {False, True}
    assert (await parser.parse(call))['cache_hit'] is True
    assert parser.ledger.usage('same-run')['jev_run_reserved'] == 1


@pytest.mark.asyncio
async def test_cancel_prevents_late_response_and_new_call(tmp_path):
    provider = RecordingProvider(0.05)
    parser = service(tmp_path, provider)
    call = request()
    pending = asyncio.create_task(parser.parse(call))
    await asyncio.sleep(0.01)
    parser.cancel(call.root.request_id)
    with pytest.raises(ServiceError, match='root_cancelled'):
        await pending
    with pytest.raises(ServiceError, match='root_cancelled'):
        await parser.parse(call)


@pytest.mark.asyncio
async def test_authenticated_v2_route_is_opt_in_and_v1_health_stays_available(tmp_path):
    provider = RecordingProvider()
    parser = service(tmp_path, provider)
    old = DecisionService(MockProvider(), parser.ledger.legacy, provider_name='mock',
                          profile_id='test', config_hash='c' * 64, run_id='same-run')
    token = 'a' * 40
    app = create_app(old, token, parser)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        assert (await client.post('/v2/parse', json=request().model_dump())).status_code == 401
        headers = {'Authorization': f'Bearer {token}'}
        health = await client.get('/health', headers=headers)
        assert health.status_code == 200 and health.json()['provider'] == 'mock'
        response = await client.post('/v2/parse', json=request().model_dump(), headers=headers)
        assert response.status_code == 200 and response.json()['attempt_no'] == 1
        assert (await client.get('/v2/usage', headers=headers)).json()[
            'gpt_limit_micro_usd'] == 1_000_000

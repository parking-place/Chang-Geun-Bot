import json

import httpx
import pytest

from changgeun.parser.contracts import ParseError
from changgeun.parser.gateway import ParserSession
from changgeun.parser.trace import SafeTraceRecorder, TraceStore


class FakeGateway:
    def __init__(self, transport):
        self.config_hash = 'c' * 64
        self.base_url = 'https://internal.test'
        self.token = 'test-token'
        self._closed = False
        self._credential_version = (1, 1)
        self.client = httpx.AsyncClient(transport=transport, follow_redirects=False)

    def _file_version(self):
        return (1, 1)

    async def _http(self):
        return self.client

    async def _bounded_json(self, response):
        return json.loads(await response.aread())


@pytest.mark.asyncio
async def test_v2_call_and_cancel_share_one_immutable_root():
    seen = []
    def route(request):
        body = json.loads(request.content)
        seen.append((request.url.path, body))
        if request.url.path == '/v2/cancel':
            return httpx.Response(200, json={'status': 'cancelled'})
        return httpx.Response(200, json={
            'schema_version': 'parser-api-v2', 'request_id': body['root']['request_id'],
            'call_id': body['call_id'], 'operation': body['operation'],
            'status': 'completed', 'result': {'answers': {'q': {'choice': 'a'}}},
        })
    gateway = FakeGateway(httpx.MockTransport(route))
    try:
        session = ParserSession(gateway, request_id='root', scope_hash='a' * 64,
                                original_text='원문')
        answer = await session.call('command_select', {'message': '원문'},
                                    pass_id='initial', stage_index=1,
                                    questions={'q': {'type': 'choice',
                                                     'instructions': 'choose',
                                                     'criteria': {'a': 'A', 'b': 'B'}}})
        await session.cancel()
    finally:
        await gateway.client.aclose()
    assert answer['answers']['q']['choice'] == 'a'
    assert seen[0][1]['root']['request_id'] == seen[1][1]['request_id']
    assert seen[0][1]['root']['original_hash'] != '원문'


@pytest.mark.asyncio
async def test_response_binding_mismatch_is_rejected():
    gateway = FakeGateway(httpx.MockTransport(lambda _request: httpx.Response(200, json={
        'schema_version': 'parser-api-v2', 'request_id': 'another',
        'call_id': 'wrong', 'operation': 'command_select',
        'status': 'completed', 'result': {},
    })))
    try:
        session = ParserSession(gateway, request_id='root', scope_hash='a' * 64,
                                original_text='원문')
        with pytest.raises(ParseError, match='gateway_response_binding_mismatch'):
            await session.call('command_select', {'message': '원문'},
                               pass_id='initial', stage_index=1, questions={})
    finally:
        await gateway.client.aclose()


@pytest.mark.asyncio
async def test_v2_observer_records_one_call_and_failure_usage(tmp_path):
    def route(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={
            'schema_version': 'parser-api-v2', 'request_id': body['root']['request_id'],
            'call_id': body['call_id'], 'operation': body['operation'],
            'attempt_no': 1, 'remote_attempted': True, 'status': 'refused',
            'result': None, 'usage': {'input_tokens': 8, 'output_tokens': 2},
        })
    gateway = FakeGateway(httpx.MockTransport(route))
    trace = SafeTraceRecorder(TraceStore(tmp_path / 'private' / 'v2.sqlite3'))
    trace.begin('root', 'guild', 'actor', 'channel', 'synthetic request')
    try:
        session = ParserSession(gateway, request_id='root', scope_hash='a' * 64,
                                original_text='synthetic request', trace=trace)
        with pytest.raises(ParseError, match='gateway_provider_failed'):
            await session.call('command_select', {'message': 'synthetic request'},
                               pass_id='initial', stage_index=1, questions={})
    finally:
        await gateway.client.aclose()
    rows = trace.store.calls('root')
    assert len(rows) == 1
    assert rows[0]['status'] == 'refused'
    assert trace.store.usage_summary('guild')['known_input_tokens'] == 8

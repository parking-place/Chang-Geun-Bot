import json
import time

import httpx
import pytest

from changgeun_inference.contracts_v2 import ParseCall, RootRequest
from changgeun_inference.providers_v2 import HostedParserProvider, validate_answers


def call():
    now = time.time()
    root = RootRequest(request_id='root', scope_hash='a' * 64,
                       original_hash='b' * 64, config_hash='c' * 64,
                       created_at=now, expires_at=now + 35)
    return ParseCall(root=root, call_id='first', operation='command_select',
                     pass_id='initial', stage_index=1, state={'message': '목록 보여줘'},
                     questions={
                         'kind': {'type': 'choice', 'instructions': '입력 성격',
                                  'criteria': {'single': '명령', 'none': '비명령'}},
                         'explicit': {'type': 'noul', 'instructions': '실제 명령인가?'}})


@pytest.mark.asyncio
async def test_batched_choice_and_noul_one_http_call():
    requests = []
    def response(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'model': 'jev-test',
            'answers': {
                'kind': {'type': 'choice', 'choice': 'single',
                         'probabilities': {'single': 0.94, 'none': 0.06},
                         'confidence': 0.9},
                'explicit': {'type': 'noul', 'noul': 0.97},
            },
            'usage': {'input_tokens': 40, 'output_tokens': 12},
        })
    provider = HostedParserProvider('https://api.typesafe.ai/v1/systemone',
                                    'jev-latest', 'dummy', transport=httpx.MockTransport(response))
    try:
        result, usage, model = await provider.parse(call(), 5)
    finally:
        await provider.close()
    assert len(requests) == 1
    assert set(requests[0]['questions']) == {'kind', 'explicit'}
    assert 'criteria' not in requests[0]['questions']['explicit']
    assert result['answers']['explicit'] == {'type': 'noul', 'noul': 0.97}
    assert result['answers']['kind']['confidence'] == 0.9
    assert usage.input_tokens == 40 and usage.output_tokens == 12
    assert usage.total_tokens is None and model == 'jev-test'


def test_answer_membership_and_distribution_fail_closed():
    questions = call().questions
    good_noul = {'type': 'noul', 'noul': 0.8}
    with pytest.raises(ValueError, match='provider_choice_out_of_scope'):
        validate_answers(questions, {'kind': {
            'type': 'choice', 'choice': 'invented',
            'probabilities': {'single': 1.0, 'none': 0.0}, 'confidence': 1.0,
        }, 'explicit': good_noul})
    with pytest.raises(ValueError, match='provider_question_mismatch'):
        validate_answers(questions, {'kind': {}})

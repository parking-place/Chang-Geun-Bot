import sys

import httpx
import pytest

from changgeun_inference import server


@pytest.mark.asyncio
async def test_explicit_disabled_parser_startup_preserves_legacy_routes(tmp_path, monkeypatch):
    profile = tmp_path / 'profile.yaml'
    profile.write_text('''profile_id: eval-test
provider: jev-api
api_schema_version: "1.2"
automatic_provider_retries: 0
automatic_fallback: false
max_provider_calls_per_request: 3
hosted:
  endpoint: https://api.typesafe.ai/v1/systemone
  model: test-model
  api_key_env: JEV_HOSTED_API_KEY
  max_calls_per_run: 20
  run_purpose: development-evaluation
''')
    token = tmp_path / 'token'
    token.write_text('t' * 40)
    monkeypatch.setenv('JEV_HOSTED_API_KEY', 'test-key')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    captured = []
    monkeypatch.setattr('uvicorn.run', lambda app, **kwargs: captured.append(app))
    common = ['gateway', '--profile', str(profile), '--ledger', str(tmp_path / 'ledger'),
              '--run-id', 'existing-run', '--tombstones', str(tmp_path / 'owners'),
              '--token-file', str(token)]
    monkeypatch.setattr(sys, 'argv', common)
    server.main()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=captured[-1]),
                                base_url='http://test') as client:
        response = await client.get('/health', headers={'Authorization': 'Bearer ' + 't' * 40})
        assert response.status_code == 200
        assert response.json()['parser_v2_ready'] is False
        assert (await client.post('/v2/parse', headers={
            'Authorization': 'Bearer ' + 't' * 40}, json={})).status_code == 404

    monkeypatch.setattr(sys, 'argv', common + ['--parser-v2', '--llm-fallback', 'disabled'])
    server.main()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=captured[-1]),
                                base_url='http://test') as client:
        headers = {'Authorization': 'Bearer ' + 't' * 40}
        assert (await client.get('/health', headers=headers)).json()['parser_v2_ready'] is True
        usage = await client.get('/v2/usage', headers=headers)
        assert usage.status_code == 200
        assert usage.json()['gpt_reserved_micro_usd'] == 0
        assert (await client.get('/v2/usage')).status_code == 401

    monkeypatch.setattr(sys, 'argv', common + ['--parser-v2', '--llm-fallback',
                                             'gpt-5-nano'])
    with pytest.raises(ValueError, match='OpenAI key missing'):
        server.main()
    assert len(captured) == 2

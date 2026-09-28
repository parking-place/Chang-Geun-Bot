import asyncio
import ssl

import httpx
import pytest

from changgeun.domain.models import DomainError
from changgeun.nlp.client import GatewayClient


def config_for(tmp_path):
    token = tmp_path / "token"
    token.write_text("x" * 32)
    return {
        "provider": "jev-api",
        "profile_id": "test-jev-api",
        "config_hash": "a" * 64,
        "base_url": "https://gateway.invalid",
        "token_file": str(token),
        "ca_file": ssl.get_default_verify_paths().cafile,
    }


@pytest.mark.asyncio
async def test_health_singleflight_cache_binding_and_client_close(tmp_path):
    config = config_for(tmp_path)
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "ready": True,
                "provider": config["provider"],
                "profile_id": config["profile_id"],
                "config_hash": config["config_hash"],
            },
        )

    client = GatewayClient(config, transport=httpx.MockTransport(handle))
    await asyncio.gather(*(client.ready() for _ in range(5)))
    assert calls == ["/health"]
    cached_client = client._client
    await client.ready()
    assert calls == ["/health"] and client._client is cached_client
    client.config_hash = "b" * 64
    with pytest.raises(DomainError, match="inference_profile_mismatch"):
        await client.ready()
    assert calls == ["/health", "/health"]
    await client.close()
    assert cached_client.is_closed
    with pytest.raises(DomainError, match="inference_temporarily_unavailable"):
        await client.ready()


@pytest.mark.asyncio
async def test_parser_profile_startup_readiness_requires_exact_v2(tmp_path):
    config = config_for(tmp_path)
    state = {"parser_v2_ready": True, "parser_llm_profile": "disabled"}

    def handle(request):
        return httpx.Response(200, json={
            "ready": True, "provider": config["provider"],
            "profile_id": config["profile_id"],
            "config_hash": config["config_hash"], **state,
        })

    client = GatewayClient(config, transport=httpx.MockTransport(handle))
    await client.parser_ready("disabled")
    state["parser_v2_ready"] = False
    with pytest.raises(DomainError, match="inference_profile_mismatch"):
        await client.parser_ready("disabled")
    state.update(parser_v2_ready=True, parser_llm_profile="gpt-5-nano")
    with pytest.raises(DomainError, match="inference_profile_mismatch"):
        await client.parser_ready("disabled")
    await client.close()


@pytest.mark.asyncio
async def test_streaming_response_rejects_over_limit_before_remaining_chunks(tmp_path):
    chunks = []

    class Oversize(httpx.AsyncByteStream):
        async def __aiter__(self):
            for number in range(4):
                chunks.append(number)
                yield b"x" * 32768

        async def aclose(self):
            pass

    client = GatewayClient(
        config_for(tmp_path),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Oversize())),
    )
    with pytest.raises(DomainError, match="inference_response_too_large"):
        await client.choose({"request_id": "one", "stage_index": 1}, 1)
    assert chunks == [0, 1, 2]
    await client.close()


@pytest.mark.asyncio
async def test_three_transient_failures_block_new_attempt_without_probe(tmp_path):
    attempts = []

    def handle(request):
        attempts.append(request.url.path)
        return httpx.Response(503)

    client = GatewayClient(config_for(tmp_path), transport=httpx.MockTransport(handle))
    for _ in range(3):
        with pytest.raises(httpx.HTTPStatusError):
            await client.choose({"request_id": "one", "stage_index": 1}, 1)
    with pytest.raises(DomainError, match="inference_temporarily_unavailable"):
        await client.choose({"request_id": "two", "stage_index": 1}, 1)
    assert attempts == ["/v1/decide"] * 3
    assert 0 < client._blocked_until - __import__("time").monotonic() <= 5
    await client.close()


@pytest.mark.asyncio
async def test_nontransient_failure_resets_transient_streak(tmp_path):
    codes = iter((503, 400, 503, 503, 400))
    client = GatewayClient(
        config_for(tmp_path),
        transport=httpx.MockTransport(lambda request: httpx.Response(next(codes))),
    )
    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            await client.choose({"request_id": "one", "stage_index": 1}, 1)
    assert client._blocked_until == 0
    await client.close()


@pytest.mark.parametrize(
    "corrupted",
    ["task", "context_snapshot_id", "candidate_set_id", "config_hash", "request_id", "stage_index"],
)
@pytest.mark.asyncio
async def test_response_from_other_snapshot_task_or_stage_is_never_accepted(tmp_path, corrupted):
    token = tmp_path / "token"
    token.write_text("x" * 32)
    payload = {
        "schema_version": "1.2",
        "provider": "jev-api",
        "profile_id": "test-jev-api",
        "config_hash": "a" * 64,
        "request_id": "one",
        "stage_index": 1,
        "task": "classify_intent",
        "context_snapshot_id": "snapshot",
        "candidate_set_id": "candidates",
    }
    result = {
        **payload,
        "selected_id": "play",
        "probabilities": {"play": 1.0, "clarify": 0.0},
        "usage": {
            "provider_calls": 1,
            "questions": 1,
            "request_provider_calls_total": 1,
            "request_questions_total": 1,
            "request_stages_total": 1,
            "forward_passes": None,
            "request_forward_passes_total": None,
            "forward_passes_source": "unavailable",
        },
    }
    result[corrupted] = 2 if corrupted == "stage_index" else "different"
    config = {
        **payload,
        "base_url": "https://gateway.invalid",
        "token_file": str(token),
        "ca_file": ssl.get_default_verify_paths().cafile,
    }
    client = GatewayClient(
        config, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result))
    )
    with pytest.raises(DomainError, match="inference_response_binding_mismatch"):
        await client.choose(payload, 1)


@pytest.mark.parametrize("provider", ["local-openjev", "mock", "other-api"])
def test_discord_client_refuses_non_hosted_provider_without_reading_secrets(provider):
    # Check selection before touching the token/CA file or making any network request.
    with pytest.raises(ValueError, match="Jev API only"):
        GatewayClient({"provider": provider})

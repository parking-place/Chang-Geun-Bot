import ssl

import httpx
import pytest

from changgeun.domain.models import DomainError
from changgeun.nlp.client import GatewayClient


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

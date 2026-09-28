import asyncio
import time

import httpx
import pytest
from pydantic import ValidationError

from changgeun_inference.contracts import Candidate, DecisionRequest
from changgeun_inference.ledger import Ledger, LedgerError
from changgeun_inference.providers import HostedProvider, MockProvider
from changgeun_inference.server import create_app
from changgeun_inference.service import DecisionService, ServiceError


def request(stage=1, request_id="request", **kwargs):
    fields = dict(
        schema_version="1.2",
        provider="mock",
        profile_id="test-mock",
        config_hash="a" * 64,
        request_id=request_id,
        stage_index=stage,
        task=("classify_intent", "select_action", "resolve_context")[stage - 1],
        request_expires_at=time.time() + 12,
        remaining_timeout_ms=4000,
        context_snapshot_id="snapshot",
        candidate_set_id=f"candidates-{stage}",
        utterance="노동요 틀어줘",
        context={},
        prompt_version="test-v1",
        candidates=[
            Candidate(id="play", description="재생 요청"),
            Candidate(id="clarify", description="불명확"),
        ],
    )
    fields.update(kwargs)
    return DecisionRequest(**fields)


@pytest.fixture
def service(tmp_path):
    provider = MockProvider("play")
    return DecisionService(
        provider,
        Ledger(tmp_path / "ledger.db"),
        provider_name="mock",
        profile_id="test-mock",
        config_hash="a" * 64,
        run_id="run-1",
        max_run_calls=20,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stage_index": 4},
        {"stage_index": 2},
        {"schema_version": "1.1"},
        {"extra": "untrusted"},
        {"utterance": "x" * 501},
        {"remaining_timeout_ms": 12001},
        {"request_expires_at": float("nan")},
        {
            "candidates": [
                Candidate(id="play", description="only"),
                Candidate(id="other", description="no clarify"),
            ]
        },
    ],
)
def test_strict_schema(kwargs):
    with pytest.raises(ValidationError):
        request(**kwargs)


@pytest.mark.asyncio
async def test_three_stages_and_per_stage_usage(service):
    first = request()
    for stage in (1, 2, 3):
        current = request(stage, request_expires_at=first.request_expires_at)
        result = await service.decide(current)
        assert result["usage"]["provider_calls"] == 1
        assert result["usage"]["request_provider_calls_total"] == stage
        assert result["usage"]["forward_passes"] is None
        assert result["task"] == current.task
        assert result["context_snapshot_id"] == current.context_snapshot_id
        assert result["candidate_set_id"] == current.candidate_set_id
    assert service.provider.calls == 3


@pytest.mark.asyncio
async def test_simultaneous_duplicates_join_and_restart_reuses_result(service):
    service.provider.delay = 0.05
    command = request()
    results = await asyncio.gather(*(service.decide(command) for _ in range(4)))
    assert all(r["selected_id"] == results[0]["selected_id"] for r in results)
    assert sum(r["usage"]["provider_calls"] for r in results) == 1
    assert service.provider.calls == 1
    restarted = DecisionService(
        service.provider,
        Ledger(service.ledger.path),
        provider_name="mock",
        profile_id="test-mock",
        config_hash="a" * 64,
        run_id="new-run",
    )
    cached = await restarted.decide(command)
    assert cached["selected_id"] == results[0]["selected_id"]
    assert cached["usage"]["provider_calls"] == 0
    assert service.provider.calls == 1


@pytest.mark.asyncio
async def test_body_and_profile_conflict_do_not_dispatch(service):
    command = request()
    await service.decide(command)
    with pytest.raises(ServiceError, match="binding_conflict"):
        await service.decide(command.model_copy(update={"utterance": "다른 요청"}))
    with pytest.raises(ServiceError, match="profile_binding_mismatch"):
        await service.decide(command.model_copy(update={"provider": "jev-api"}))
    assert service.provider.calls == 1


def test_crash_tombstone_never_refunds_or_redispatches(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    command = request()
    ledger.reserve(command, "run", 20)
    restarted = Ledger(ledger.path)
    with pytest.raises(LedgerError, match="unknown_or_failed"):
        restarted.lookup(command)
    with pytest.raises(LedgerError, match="stage_order_or_budget"):
        restarted.reserve(command, "new-run", 20)


def test_independent_profile_ledgers_share_non_resettable_request_ownership(tmp_path):
    registry = tmp_path / "tombstones.db"
    first = Ledger(tmp_path / "a" / "ledger.db", registry)
    second = Ledger(tmp_path / "b" / "ledger.db", registry)
    command = request()
    first.reserve(command, "run-a", 20)
    with pytest.raises(LedgerError, match="previous_run_request_conflict"):
        second.reserve(command, "run-b", 20)


@pytest.mark.asyncio
async def test_stage_two_cannot_start_request(service):
    with pytest.raises(ServiceError, match="stage_order_violation"):
        await service.decide(request(2))
    assert service.provider.calls == 0


@pytest.mark.asyncio
async def test_run_budget_counts_all_requests(service):
    service.max_run_calls = 2
    await service.decide(request(request_id="1"))
    await service.decide(request(request_id="2"))
    with pytest.raises(ServiceError, match="run_budget_exhausted"):
        await service.decide(request(request_id="3"))
    assert service.provider.calls == 2


@pytest.mark.asyncio
async def test_late_calculation_holds_slot_and_never_returns_success(service):
    service.provider.delay = 0.15
    slow = request(request_id="slow", remaining_timeout_ms=20)
    with pytest.raises(ServiceError, match="stage_timeout"):
        await service.decide(slow)
    # Second short deadline expires while the prior CPU-equivalent call still runs.
    queued = request(request_id="queued", remaining_timeout_ms=20)
    with pytest.raises(ServiceError, match="stage_timeout"):
        await service.decide(queued)
    assert service.provider.calls == 1
    await service.drain()
    with pytest.raises(LedgerError, match="unknown_or_failed"):
        service.ledger.lookup(slow)
    assert service.provider.calls == 1


@pytest.mark.asyncio
async def test_cancelled_http_waiter_does_not_cancel_dispatch(service):
    service.provider.delay = 0.05
    command = request()
    waiter = asyncio.create_task(service.decide(command))
    await asyncio.sleep(0.01)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert service.slot.locked() and service.pending == 1
    await service.drain()
    assert service.provider.calls == 1


@pytest.mark.asyncio
async def test_pending_limit(service):
    service.provider.delay = 0.05
    tasks = [asyncio.create_task(service.decide(request(request_id=str(i)))) for i in range(5)]
    await asyncio.sleep(0.01)
    with pytest.raises(ServiceError, match="queue_full"):
        await service.decide(request(request_id="sixth"))
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_auth_health_does_not_call_provider(service):
    app = create_app(service, "x" * 32)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.get("/health")).status_code == 401
        assert (
            await client.get("/health", headers={"Authorization": "Bearer " + "x" * 32})
        ).status_code == 200
        assert (await client.post("/v1/decide", json=request().model_dump())).status_code == 401
    assert service.provider.calls == 0


@pytest.mark.asyncio
async def test_authenticated_usage_is_read_only_and_shared_run(service):
    app = create_app(service, "x" * 32)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.get("/v1/usage")).status_code == 401
        response = await client.get(
            "/v1/usage", headers={"Authorization": "Bearer " + "x" * 32}
        )
        assert response.status_code == 200
        assert response.json() == {
            "scope": "shared_run",
            "provider": "mock",
            "profile_id": "test-mock",
            "config_hash": "a" * 64,
            "reserved_calls": 0,
            "limit": 20,
        }
    assert service.provider.calls == 0


@pytest.mark.asyncio
async def test_auth_precedes_parsing_and_chunked_bodies_are_bounded(service):
    app = create_app(service, "x" * 32)

    async def chunks():
        for _ in range(5):
            yield b"x" * 10000

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.post("/v1/decide", content=b"invalid-json")).status_code == 401
        assert (
            await client.post(
                "/v1/decide", content=chunks(), headers={"Authorization": "Bearer " + "x" * 32}
            )
        ).status_code == 413
        assert (
            await client.post(
                "/v1/decide",
                content=b"invalid-json",
                headers={"Authorization": "Bearer " + "x" * 32},
            )
        ).status_code == 422
    assert service.provider.calls == 0


@pytest.mark.parametrize("status", [429, 500, 502, 503, 307])
@pytest.mark.asyncio
async def test_hosted_errors_and_redirects_are_one_dispatch(status):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(status, headers={"Location": "https://untrusted.invalid/"})

    provider = HostedProvider(
        "https://api.typesafe.ai/v1/systemone",
        "jev-latest",
        "test-key",
        transport=httpx.MockTransport(handle),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.decide(request(), 1)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_hosted_forward_provenance_always_null():
    def handle(req):
        return httpx.Response(
            200,
            json={
                "model": "jev-latest",
                "answers": {
                    "decision": {
                        "type": "choice",
                        "choice": "play",
                        "probabilities": {"play": 0.9, "clarify": 0.1},
                    }
                },
                "usage": {"forward_passes": 999},
            },
        )

    provider = HostedProvider(
        "https://api.typesafe.ai/v1/systemone",
        "jev-latest",
        "test-key",
        transport=httpx.MockTransport(handle),
    )
    result = await provider.decide(request(), 1)
    assert result.forward_passes is None
    assert result.model_revision is None
    first_client = provider._client
    await provider.decide(request(request_id="other"), 1)
    assert provider._client is first_client
    await provider.close()
    assert first_client.is_closed


@pytest.mark.asyncio
async def test_hosted_streaming_cap_stops_before_last_chunk():
    chunks = []

    class Oversize(httpx.AsyncByteStream):
        async def __aiter__(self):
            for number in range(4):
                chunks.append(number)
                yield b"x" * 32768

        async def aclose(self):
            pass

    provider = HostedProvider(
        "https://api.typesafe.ai/v1/systemone",
        "jev-latest",
        "test-key",
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=Oversize())),
    )
    with pytest.raises(ValueError, match="provider response too large"):
        await provider.decide(request(), 1)
    assert chunks == [0, 1, 2]
    await provider.close()

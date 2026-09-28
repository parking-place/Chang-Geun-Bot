import time

import pytest

from changgeun.nlp.command_registry import (
    COMMANDS,
    GROUPS,
    CommandSelector,
    direct_candidates,
    safe_utterance,
    structured_alias,
)
from changgeun.nlp.pipeline import Selection


class Port:
    provider, profile_id, config_hash = "mock", "test-mock", "a" * 64

    def __init__(self, replies):
        self.replies = list(replies)
        self.payloads = []

    async def choose(self, payload, timeout):
        self.payloads.append(payload)
        chosen = self.replies.pop(0)
        ids = [item["id"] for item in payload["candidates"]]
        return Selection(
            chosen,
            {key: 0.99 if key == chosen else 0.01 / (len(ids) - 1) for key in ids},
            payload["stage_index"],
        )


def test_public_command_coverage_and_candidate_limits():
    assert {item.identifier for item in COMMANDS} == {f"C{n:02d}" for n in range(1, 48)}
    assert len(COMMANDS) == len({item.identifier for item in COMMANDS})
    assert {item.group for item in COMMANDS} == set(GROUPS) | {"entry"}
    assert all(sum(item.group == group for item in COMMANDS) <= 9 for group in GROUPS)


def test_distinct_references_and_youtube_links_hide_identifiers():
    sample = (
        "<#123456789012345678> 말고 <#223456789012345678>에서 "
        "youtube.com/watch?v=aqz-KE-bpKQ 틀어줘"
    )
    sanitized = safe_utterance(sample)
    assert "[채널1]" in sanitized and "[채널2]" in sanitized and "[영상ID1]" in sanitized
    assert "123456789012345678" not in sanitized and "aqz-KE-bpKQ" not in sanitized


def test_exact_aliases_are_zero_call_and_recovery_is_admin_only():
    assert structured_alias("현재곡", allow_admin=False).command.identifier == "C31"
    assert structured_alias("현재곡", allow_admin=False).trace is None
    assert structured_alias("주시 켜기", allow_admin=False) is None
    recovery = structured_alias("주시 켜기", allow_admin=True, admin_only=True)
    assert recovery is not None and recovery.command.identifier == "C43"
    assert structured_alias("현재곡", allow_admin=True, admin_only=True) is None
    assert structured_alias("주시 켜줘", allow_admin=True, admin_only=True) is None
    assert structured_alias("정지", allow_admin=False, allow_dj=False) is None


@pytest.mark.asyncio
async def test_closed_two_stage_selection_with_one_budget():
    port = Port(["playlists", "C04"])
    selector = CommandSelector(port, confidence=0.8, margin=0.1, prompt_version="v5")
    checks = []

    async def recheck():
        checks.append(1)

    result = await selector.select(
        "운동용을 없애줘", "request-1", started_at=time.monotonic(), recheck=recheck
    )
    assert result.command.identifier == "C04"
    assert result.trace.provider_calls == 2 and result.trace.stages == 2
    assert [p["stage_index"] for p in port.payloads] == [1, 2]
    assert all(p["request_id"] == "request-1" for p in port.payloads)
    assert len(checks) == 4
    assert result.expires_at <= time.time() + 12


@pytest.mark.asyncio
async def test_soft_direct_selection_requires_second_matching_judgment():
    class SoftPort(Port):
        async def choose(self, payload, timeout):
            self.payloads.append(payload)
            chosen = self.replies.pop(0)
            ids = [item["id"] for item in payload["candidates"]]
            return Selection(
                chosen,
                {key: 0.7 if key == chosen else 0.3 / (len(ids) - 1) for key in ids},
                payload["stage_index"],
            )

    async def recheck():
        return None

    agreed = SoftPort(["C04", "C04"])
    selector = CommandSelector(agreed, confidence=0.8, margin=0.1, prompt_version="v5")
    result = await selector.select(
        "운동용 목록 삭제해줘", "request-soft", started_at=time.monotonic(),
        recheck=recheck,
    )
    assert result is not None and result.trace.provider_calls == 2
    disputed = SoftPort(["C04", "clarify"])
    assert await CommandSelector(
        disputed, confidence=0.8, margin=0.1, prompt_version="v5"
    ).select(
        "운동용 목록 삭제해줘", "request-disputed", started_at=time.monotonic(),
        recheck=recheck,
    ) is None


@pytest.mark.asyncio
async def test_direct_retrieval_still_requires_jev_selection():
    assert set(direct_candidates("운동용 목록 삭제해줘", allow_admin=False)) == {"C04"}
    port = Port(["C04"])
    selector = CommandSelector(port, confidence=0.8, margin=0.1, prompt_version="v5")

    async def recheck():
        pass

    result = await selector.select(
        "운동용 목록 삭제해줘", "request-3", started_at=time.monotonic(), recheck=recheck
    )
    assert result.command.identifier == "C04"
    assert result.trace.provider_calls == 1
    assert len(port.payloads) == 1


@pytest.mark.asyncio
async def test_admin_recovery_never_offers_music_command():
    port = Port(["non_command"])
    selector = CommandSelector(port, confidence=0.8, margin=0.1, prompt_version="v5")

    async def recheck():
        pass

    result = await selector.select(
        "노래 틀어줘", "request-2", started_at=time.monotonic(), recheck=recheck,
        admin_only=True,
    )
    assert result is None
    assert port.payloads == []


@pytest.mark.asyncio
async def test_admin_recovery_refuses_mixed_music_and_settings_without_call():
    port = Port([])
    selector = CommandSelector(port, confidence=0.8, margin=0.1, prompt_version="v5")

    async def recheck():
        return None

    assert await selector.select(
        "주시 켜고 노래 틀어줘", "request-mixed", started_at=time.monotonic(),
        recheck=recheck, admin_only=True, allow_admin=True,
    ) is None
    assert port.payloads == []


@pytest.mark.asyncio
async def test_non_dj_candidates_exclude_mutations_before_gateway():
    port = Port(["C01"])
    selector = CommandSelector(port, confidence=0.8, margin=0.1, prompt_version="v5")

    async def recheck():
        return None

    result = await selector.select(
        "목록 보여줘", "request-4", started_at=time.monotonic(),
        recheck=recheck, allow_dj=False,
    )
    assert result.command.identifier == "C01"
    assert "C04" not in {row["id"] for row in port.payloads[0]["candidates"]}

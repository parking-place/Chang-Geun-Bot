import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.discord_adapter.natural import (
    AdminOpen,
    PrivateReadOpen,
    _name,
    _new_name,
    _query,
    dispatch,
)
from changgeun.discord_adapter.prefix import MessageLedger
from changgeun.domain.models import Action, Actor, InferenceTrace, Policy
from changgeun.nlp.command_registry import COMMANDS, CommandDecision


class Followup:
    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append((content, kwargs))


@pytest.fixture
def setup(tmp_path):
    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"3"}), frozenset({"4"}))
    client = ChangGeunClient(BotConfig(tmp_path / "db.sqlite", policy, tmp_path / "audio", {}))
    actor = Actor("1", "10", frozenset({"2"}), "3", "4", "4", manage_guild=True)
    entry = SimpleNamespace(id=100, followup=Followup())
    client.submit_plan = capture = type("Capture", (), {"__call__": lambda self, *a, **k: None})()

    async def submit(*args, **kwargs):
        capture.plan = args[1]

    client.submit_plan = submit
    return client, actor, entry, capture


def decision(identifier):
    command = next(item for item in COMMANDS if item.identifier == identifier)
    return CommandDecision(
        command,
        InferenceTrace("mock", "test-mock", "a" * 64, 2, 2, 2, None, "unavailable"),
        time.time() + 12,
    )


def test_korean_name_and_search_slots_keep_user_values():
    assert _name("운동용이라는 빈 목록 만들어줘") == "운동용"
    assert _new_name("운동용 목록 이름을 달리기로 바꿔줘", "바꿔") == "달리기"
    assert _new_name("운동용을 주말 운동이라는 목록으로 복사해줘", "복사") == "주말 운동"
    assert _query("유튜브에서 봄 노래 찾아서 틀어줘", True) == "봄 노래"


@pytest.mark.asyncio
async def test_natural_queue_and_volume_use_trusted_plans(setup):
    client, actor, entry, capture = setup
    await dispatch(client, entry, actor, decision("C16"), "지금 대기열 보여줘")
    assert capture.plan.action == Action.QUEUE_SHOW
    assert capture.plan.inference.provider_calls == 2
    await dispatch(client, entry, actor, decision("C28"), "볼륨을 35퍼센트로 해줘")
    assert capture.plan.action == Action.PLAYBACK_VOLUME
    assert capture.plan.arguments == {"percent": 35}


@pytest.mark.asyncio
async def test_admin_prefix_only_offers_private_component(setup):
    client, actor, entry, capture = setup
    await dispatch(client, entry, actor, decision("C47"), "사용량 보여줘")
    assert not hasattr(capture, "plan")
    content, options = entry.followup.sent[0]
    assert "사용량" not in content and "관리 요청" in content
    assert isinstance(options["view"], AdminOpen)


@pytest.mark.asyncio
async def test_playlist_delete_resolves_database_id(setup):
    client, actor, entry, capture = setup
    with client.db.transaction() as conn:
        conn.execute(
            "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
            ("1", "list-1", "운동용", "운동용"),
        )
    await dispatch(client, entry, actor, decision("C04"), "운동용 목록 삭제해줘")
    assert capture.plan.action == Action.PLAYLIST_DELETE
    assert capture.plan.arguments == {"playlist_id": "list-1"}


@pytest.mark.asyncio
async def test_excluded_playlist_is_never_played(setup):
    client, actor, entry, capture = setup
    with client.db.transaction() as conn:
        for identifier, name in (("excluded", "운동용"), ("chosen", "휴식용")):
            conn.execute(
                "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                ("1", identifier, name, name),
            )
    await dispatch(
        client, entry, replace(actor, voice_channel_id="4"), decision("C23"),
        "운동용 말고 휴식용 목록 틀어줘",
    )
    assert capture.plan.action == Action.PLAYLIST_PLAY
    assert capture.plan.arguments["playlist_id"] == "chosen"


@pytest.mark.asyncio
async def test_private_read_does_not_post_result_to_public_reply(setup):
    client, actor, entry, _ = setup
    await dispatch(client, entry, actor, decision("C33"), "제안함")
    content, options = entry.followup.sent[0]
    assert "조회했어" in content and "제안" not in content
    assert isinstance(options["view"], PrivateReadOpen)


@pytest.mark.asyncio
async def test_text_cancel_uses_owned_active_request_without_provider(setup):
    client, actor, _, _ = setup
    request = MessageLedger(client.db).admit(
        actor.guild_id, actor.text_channel_id, "original", actor.user_id,
        "목록 삭제", "a" * 64, time.time(),
    )
    assert request is not None
    replies = []

    async def reply(content, **kwargs):
        replies.append(content)

    message = SimpleNamespace(
        guild=SimpleNamespace(id=1), channel=SimpleNamespace(id=3),
        author=SimpleNamespace(id=10), reference=None, reply=reply,
    )
    await client.cancel_prefix_text(message)
    assert replies == ["진행 요청을 취소했어."]
    with client.db.connect() as conn:
        assert conn.execute(
            "SELECT state FROM message_requests WHERE request_id=?", (request,)
        ).fetchone()[0] == "cancelled"

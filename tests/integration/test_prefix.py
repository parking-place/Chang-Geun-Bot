import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from changgeun.application.executor import Executor
from changgeun.discord_adapter.mention import MentionEntry
from changgeun.discord_adapter.prefix import MessageLedger, parse_prefix
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.storage.database import Database


@pytest.mark.parametrize(
    "content,expected",
    [
        ("!!창근아 노동요 틀어줘", "노동요 틀어줘"),
        ("!!창근아\t목록 보여줘", "목록 보여줘"),
        ("!!창근아\r\n목록\n보여줘", "목록\n보여줘"),
        ("!!창근아", ""),
        ("!!창근아   ", ""),
        (" !!창근아 정지", None),
        ("!!창근아노동요", None),
        ("!!창근아님", None),
        ("!!창근아, 정지", None),
        ("안녕 !!창근아 정지", None),
        ("> !!창근아 정지", None),
        ("```!!창근아 정지```", None),
        ("！！창근아 정지", None),
        ("!!창근\u200b아 정지", None),
        ("!!창근아\u00a0정지", None),
    ],
)
def test_exact_prefix(content, expected):
    assert parse_prefix(content) == expected


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "messages.db")
    db.ensure_guild("1")
    actor = Actor("1", "10", frozenset({"dj"}), "20", "30", "30")
    policy = Policy(frozenset({"1"}), frozenset({"dj"}), frozenset({"20"}), frozenset({"30"}))
    return db, MessageLedger(db), actor, Executor(db, policy)


def admit(ledger, message="100", text="목록 보여줘"):
    return ledger.admit("1", "20", message, "10", text, "a" * 64, time.time())


def test_durable_concurrent_duplicate_no_text(env):
    db, ledger, _, _ = env
    with ThreadPoolExecutor(4) as pool:
        values = list(pool.map(lambda _: admit(ledger), range(4)))
    assert sum(v is not None for v in values) == 1
    assert admit(MessageLedger(Database(db.path))) is None
    with db.connect() as conn:
        row = dict(conn.execute("SELECT * FROM message_requests").fetchone())
    assert "목록" not in str(row)
    assert row["request_id"] != row["message_id"]


def test_stale_future_message_not_admitted(env):
    _, ledger, _, _ = env
    assert ledger.admit("1", "20", "100", "10", "목록", "a" * 64, 10, now=41) is None
    assert ledger.admit("1", "20", "100", "10", "목록", "a" * 64, 50, now=41) is None


def test_cancel_before_commit_denies_executor(env):
    db, ledger, actor, executor = env
    request = admit(ledger)
    assert ledger.cancel("1", "20", {"100"}) == {request}
    with pytest.raises(DomainError, match="message_request_cancelled"):
        executor.execute(
            ActionPlan(request, "1", "10", Action.PLAYLIST_CREATE, {"name": "새벽"}), actor
        )
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM playlists").fetchone()[0] == 0


def test_committed_delete_does_not_undo(env):
    db, ledger, actor, executor = env
    request = admit(ledger)
    plan = ActionPlan(request, "1", "10", Action.PLAYLIST_CREATE, {"name": "새벽"})
    result = executor.execute(plan, actor)
    assert ledger.cancel("1", "20", {"100"}) == set()
    assert executor.execute(plan, actor) == result
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM playlists").fetchone()[0] == 1


def test_cancel_waiting_invalidates_confirmation(env):
    db, ledger, actor, executor = env
    playlist = executor.execute(
        ActionPlan("create", "1", "10", Action.PLAYLIST_CREATE, {"name": "새벽"}), actor
    )["playlist_id"]
    request = admit(ledger)
    plan = ActionPlan(
        request, "1", "10", Action.PLAYLIST_DELETE, {"playlist_id": playlist}, {playlist: 0}
    )
    token = executor.preview(plan, actor)
    ledger.cancel("1", "20", {"100"})
    with pytest.raises(DomainError, match="message_request_cancelled"):
        executor.execute(plan, actor, confirmation=token)
    with db.connect() as conn:
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 1


def test_recovery_does_not_redispatch_or_reply(env):
    _, ledger, actor, executor = env
    request = admit(ledger)
    assert ledger.reserve_response(request)
    ledger.recover()
    assert admit(ledger) is None
    assert not ledger.reserve_response(request)
    with pytest.raises(DomainError, match="message_request_cancelled"):
        executor.execute(ActionPlan(request, "1", "10", Action.QUEUE_SHOW), actor)


@pytest.mark.asyncio
async def test_public_reply_once_then_edit(env):
    _, ledger, _, _ = env
    request = admit(ledger)
    reply = SimpleNamespace(id=200, edit=AsyncMock())
    message = SimpleNamespace(
        id=100,
        author=SimpleNamespace(id=10),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=20),
        reply=AsyncMock(return_value=reply),
    )
    entry = MentionEntry(message, ledger, request)
    await entry.response.defer(ephemeral=True)
    await entry.followup.send("완료", ephemeral=True)
    assert message.reply.await_count == 1
    assert reply.edit.await_count == 1
    assert "ephemeral" not in message.reply.call_args.kwargs
    assert not message.reply.call_args.kwargs["mention_author"]


@pytest.mark.asyncio
async def test_response_lost_not_sent_again(env):
    _, ledger, _, _ = env
    request = admit(ledger)
    message = SimpleNamespace(
        id=100,
        author=SimpleNamespace(id=10),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=20),
        reply=AsyncMock(side_effect=OSError("lost")),
    )
    entry = MentionEntry(message, ledger, request)
    with pytest.raises(OSError):
        await entry.followup.send("접수")
    with pytest.raises(DomainError, match="message_response_unknown"):
        await entry.followup.send("다시")
    assert message.reply.await_count == 1


def test_own_response_edit_keeps_request_but_delete_cancels(env):
    _, ledger, _, _ = env
    request = admit(ledger)
    ledger.record_response(request, "200")
    assert ledger.cancel("1", "20", {"200"}, include_responses=False) == set()
    assert ledger.cancel("1", "20", {"200"}) == {request}


def test_cancelled_message_blocks_registration_subrequest(env):
    _, ledger, actor, executor = env
    request = admit(ledger)
    ledger.cancel("1", "20", {"100"})
    with pytest.raises(DomainError, match="message_request_cancelled"):
        executor.execute(
            ActionPlan(
                request + ".register",
                "1",
                "10",
                Action.CATALOG_REGISTER,
                {"source_type": "youtube", "external_id": "ABCDEFGHIJK", "title": "public video"},
            ),
            actor,
        )

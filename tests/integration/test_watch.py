"""Watch settings/provenance/approval regressions, isolated on DiscordBotLXC."""

import asyncio
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from changgeun.application.executor import Executor
from changgeun.application.watch import (
    AdminGrant,
    WatchStore,
    admission_valid,
    bind_source,
)
from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.discord_adapter.prefix import MessageLedger, PrefixConfig
from changgeun.discord_adapter.watch import WatchConfirmation, admin, inspect, invoke, normal_text
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.nlp.pipeline import Pipeline, Selection
from changgeun.playback.persistence import load_session, save_session
from changgeun.playback.state import PlaybackState
from changgeun.storage.database import Database


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "watch.db")
    db.ensure_guild("1")
    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"20"}), frozenset({"30"}))
    actor = Actor("1", "10", frozenset({"2"}), "21", "30", "30")
    store = WatchStore(db)
    store.seed("1", ["21", "22"], True)
    return db, store, actor, policy, Executor(db, policy)


def change(env, action, channel=None, request=None, expected=None):
    _, store, *_ = env
    return store.change(
        AdminGrant("1", "10", time.time()),
        request or str(uuid.uuid4()),
        action,
        channel,
        store.state("1")["revision"] if expected is None else expected,
    )


def prefix(env, channel="21"):
    db, _, actor, *_ = env
    request = MessageLedger(db).admit(
        "1", channel, str(uuid.uuid4()), actor.user_id, "목록 보여줘", "a" * 64, time.time()
    )
    return request


def plan(env, request, action=Action.PLAYLIST_CREATE, args=None):
    args = {"name": str(uuid.uuid4())} if args is None else args
    with env[0].connect() as conn:
        state = conn.execute(
            "SELECT version,generation FROM sessions WHERE guild_id='1'"
        ).fetchone()
        versions = {}
        if action.value.startswith(("queue.", "playback.", "voice.")) or action in {
            Action.TRACK_PLAY,
            Action.PLAYLIST_PLAY,
        }:
            versions["queue"] = state[0]
        if args.get("playlist_id"):
            versions[args["playlist_id"]] = conn.execute(
                "SELECT version FROM playlists WHERE id=?", (args["playlist_id"],)
            ).fetchone()[0]
    return ActionPlan(
        request,
        "1",
        "10",
        action,
        args,
        versions,
        origin="natural_language",
        execution_generation=state[1],
    )


def track(env, name="tone"):
    *_, executor = env
    actor = replace(env[2], text_channel_id="20")
    return executor.execute(
        ActionPlan(
            str(uuid.uuid4()),
            "1",
            "10",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": name, "title": name},
        ),
        actor,
    )["track_id"]


def enqueue(env, source="prefix", channel="21", name="tone"):
    db, _, actor, _, executor = env
    identifier = track(env, name)
    current = replace(actor, text_channel_id=channel)
    request = prefix(env, channel) if source == "prefix" else str(uuid.uuid4())
    if source != "prefix":
        with db.transaction() as conn:
            bind_source(conn, "1", request, "10", channel, "slash")
    executor.execute(plan(env, request, Action.QUEUE_ENQUEUE, {"track_ids": [identifier]}), current)
    with db.connect() as conn:
        return conn.execute(
            "SELECT id FROM queue_entries WHERE track_id=?", (identifier,)
        ).fetchone()[0]


def test_seed_restart_empty_disabled_never_repopulated(env):
    db, store, *_ = env
    change(env, "remove", "21")
    change(env, "remove", "22")
    reopened = WatchStore(Database(db.path))
    reopened.seed("1", ["21", "22"], True)
    assert reopened.channels("1") == [] and not reopened.state("1")["enabled"]
    change(env, "add", "21")
    assert not store.state("1")["enabled"]


def test_seed_failed_mutations_denied(env):
    db, _, *_ = env
    db.ensure_guild("99")
    store = WatchStore(db)
    with pytest.raises(DomainError, match="watch_seed_required"):
        store.change(AdminGrant("99", "10", time.time()), "x", "add", "21", 0)


def test_noop_dedup_and_conflicting_body(env):
    _, store, *_ = env
    request = prefix(env)
    first = change(env, "add", "21", "repeat")
    assert not first["changed"] and first["revision"] == 0
    assert change(env, "add", "21", "repeat", expected=999) == first
    with pytest.raises(DomainError, match="request_body_conflict"):
        change(env, "remove", "21", "repeat")
    env[4].execute(plan(env, request), env[2])
    assert store.state("1")["revision"] == 0


def test_revision_conflict_never_applies_stale_confirmation(env):
    change(env, "add", "23")
    with pytest.raises(DomainError, match="watch_revision_conflict"):
        change(env, "remove", "21", expected=0)
    assert "21" in env[1].channels("1")


def test_two_admins_one_revision_single_commit(env):
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(change, env, "add", c, None, 0) for c in ["23", "24"]]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result()["changed"])
            except DomainError as exc:
                assert exc.code == "watch_revision_conflict"
    assert outcomes == [True] and len(env[1].channels("1")) == 3


def test_channel_limit_and_guild_isolation(env):
    for i in range(23, 41):
        change(env, "add", str(i))
    assert len(env[1].channels("1")) == 20
    with pytest.raises(DomainError, match="watch_channel_limit"):
        change(env, "add", "41")
    env[0].ensure_guild("9")
    env[1].seed("9", ["21"], True)
    change(env, "remove", "21")
    assert env[1].channels("9") == ["21"]


def test_commit_failure_rolls_back_every_table(env, monkeypatch):
    from contextlib import contextmanager

    db, store, *_ = env
    original = db.transaction

    @contextmanager
    def broken():
        with original() as conn:
            yield conn
            raise OSError("simulated precommit crash")

    monkeypatch.setattr(db, "transaction", broken)
    with pytest.raises(OSError):
        change(env, "remove", "21")
    assert store.channels("1") == ["21", "22"] and store.state("1")["revision"] == 0
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM watch_change_events").fetchone()[0] == 0


def test_lost_response_retry_not_second_effect(env):
    result = change(env, "remove", "21", "lost")
    assert change(env, "remove", "21", "lost", expected=0) == result
    with env[0].connect() as conn:
        assert conn.execute("SELECT count(*) FROM watch_change_events").fetchone()[0] == 1


def test_old_grant_not_valid(env):
    with pytest.raises(DomainError, match="permissions_unavailable"):
        env[1].change(AdminGrant("1", "10", time.time() - 6), "old", "add", "23", 0)


def test_static_policy_settings_json_independent(env):
    actor = replace(env[2], text_channel_id="20", manage_guild=True)
    env[4].execute(
        ActionPlan(
            "settings",
            "1",
            "10",
            Action.SETTINGS_UPDATE,
            {"settings": {"recent_exclusion_days": 20}},
        ),
        actor,
    )
    assert env[1].channels("1") == ["21", "22"]


def test_dynamic_prefix_and_forged_origin_and_identity(env):
    request = prefix(env)
    assert env[4].execute(plan(env, request), env[2])["playlist_id"]
    with pytest.raises(DomainError, match="text_channel_not_allowed"):
        env[4].execute(plan(env, "fake", Action.PLAYLIST_LIST), env[2])
    with pytest.raises(DomainError, match="identity_mismatch"):
        env[4].execute(plan(env, request), replace(env[2], text_channel_id="22"))
    with pytest.raises(DomainError):
        env[4].execute(replace(plan(env, request), actor_id="11"), replace(env[2], user_id="11"))


@pytest.mark.parametrize("operation", ["remove", "disable"])
def test_revocation_blocks_root_child_and_confirmation(env, operation):
    request = prefix(env)
    playlist = env[4].execute(
        ActionPlan("create", "1", "10", Action.PLAYLIST_CREATE, {"name": "safe"}),
        replace(env[2], text_channel_id="20"),
    )["playlist_id"]
    delete = plan(env, request, Action.PLAYLIST_DELETE, {"playlist_id": playlist})
    token = env[4].preview(delete, env[2])
    change(env, operation, "21" if operation == "remove" else None)
    for command in [delete, replace(delete, request_id=request + ".register")]:
        with pytest.raises(DomainError):
            env[4].execute(command, env[2], confirmation=token)
    with env[0].connect() as conn:
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 1
        assert conn.execute("SELECT deleted_at FROM playlists").fetchone()[0] is None


def test_unrelated_change_keeps_inflight_and_admission(env):
    request = prefix(env)
    entry = enqueue(env)
    change(env, "add", "23")
    change(env, "remove", "22")
    assert env[4].execute(plan(env, request), env[2])["playlist_id"]
    with env[0].connect() as conn:
        assert admission_valid(conn, "1", entry)


def test_readd_or_reenable_never_revives_old_request(env):
    request = prefix(env)
    change(env, "remove", "21")
    change(env, "add", "21")
    with pytest.raises(DomainError):
        env[4].execute(plan(env, request), env[2])
    assert env[4].execute(plan(env, prefix(env)), env[2])["playlist_id"]


def test_affected_approvals_kept_in_queue_other_origins_preserved(env):
    first = enqueue(env, name="revoked")
    other = enqueue(env, channel="22", name="other")
    slash = enqueue(env, source="slash", channel="20", name="slash")
    change(env, "remove", "21")
    with env[0].connect() as conn:
        session = load_session(conn, "1")
        assert [e.id for e in session.queue] == [first, other, slash]
        assert not admission_valid(conn, "1", first)
        assert admission_valid(conn, "1", other) and admission_valid(conn, "1", slash)
        session.state = PlaybackState.IDLE
        session.start()
        assert session.current.id == other
        assert session.failed_tracks == 0


def test_started_pause_resume_kept_but_repeat_cannot_restart_revoked(env):
    first = enqueue(env)
    with env[0].transaction() as conn:
        session = load_session(conn, "1")
        session.state = PlaybackState.IDLE
        session.start()
        session.resolved(session.generation)
        session.repeat = "one"
        save_session(conn, "1", session)
        conn.execute("UPDATE audio_admissions SET started=1")
    change(env, "disable")
    with env[0].transaction() as conn:
        session = load_session(conn, "1")
        session.pause()
        session.resume()
        assert session.current.id == first
        session.finished(session.generation)
        assert session.state == PlaybackState.IDLE and session.current is None
        assert [e.id for e in session.queue] == [first]


def test_reapproval_reuses_queue_entry(env):
    entry = enqueue(env)
    identifier = track(env)
    change(env, "remove", "21")
    change(env, "add", "21")
    result = env[4].execute(
        plan(env, prefix(env), Action.TRACK_PLAY, {"track_id": identifier, "channel_id": "30"}),
        env[2],
    )
    assert result["reused_entry_id"] == entry
    with env[0].connect() as conn:
        assert admission_valid(conn, "1", entry)
        assert conn.execute("SELECT count(*) FROM audio_admissions").fetchone()[0] == 1


def test_reapproval_selects_exact_duplicate_entry_without_queue_copy(env):
    first = enqueue(env)
    identifier = track(env)
    env[4].execute(
        plan(
            env,
            prefix(env),
            Action.QUEUE_ENQUEUE,
            {"track_ids": [identifier], "allow_duplicates": True},
        ),
        env[2],
    )
    with env[0].connect() as conn:
        ids = [row[0] for row in conn.execute("SELECT id FROM queue_entries ORDER BY position")]
    assert len(ids) == 2 and ids[0] == first
    second = ids[1]
    change(env, "remove", "21")
    change(env, "add", "21")
    result = env[4].execute(
        plan(
            env,
            prefix(env),
            Action.TRACK_PLAY,
            {"track_id": identifier, "entry_id": second, "channel_id": "30"},
        ),
        env[2],
    )
    assert result["reused_entry_id"] == second
    with env[0].connect() as conn:
        assert not admission_valid(conn, "1", first)
        assert admission_valid(conn, "1", second)
        assert conn.execute("SELECT count(*) FROM queue_entries").fetchone()[0] == 2

    with pytest.raises(DomainError, match="version_conflict"):
        env[4].execute(
            plan(
                env,
                prefix(env),
                Action.TRACK_PLAY,
                {"track_id": identifier, "entry_id": "deleted", "channel_id": "30"},
            ),
            env[2],
        )


def test_permission_loss_recovery_new_generation(env):
    request = prefix(env)
    assert env[1].health("1", "21", False) == [request]
    env[1].health("1", "21", True)
    with pytest.raises(DomainError):
        env[4].execute(plan(env, request), env[2])
    assert env[4].execute(plan(env, prefix(env)), env[2])["playlist_id"]


def test_recover_pending_never_redispatches(env):
    request = prefix(env)
    MessageLedger(env[0]).recover()
    env[1].recover()
    with pytest.raises(DomainError):
        env[4].execute(plan(env, request), env[2])


def test_migration_preserves_old_checksums_unknown_approvals_require_new_request(tmp_path):
    db_path = tmp_path / "old.db"
    import hashlib

    migrations = (
        Path(__import__("changgeun.storage.database", fromlist=["Database"]).__file__).parent
        / "migrations"
    )
    with sqlite3.connect(db_path) as conn:
        for file in sorted(migrations.glob("*.sql"))[:5]:
            text = file.read_text()
            conn.executescript(text)
            conn.execute(
                "INSERT INTO schema_migrations VALUES(?,?)",
                (int(file.name[:4]), hashlib.sha256(text.encode()).hexdigest()),
            )
        conn.execute("INSERT INTO audio_admissions VALUES('1','old','10','21','unproved',0)")
    db = Database(db_path)
    WatchStore(db).seed("1", ["21"], True)
    with db.connect() as conn:
        assert not admission_valid(conn, "1", "old")
        assert conn.execute("SELECT origin FROM audio_admissions").fetchone()[0] == "legacy_unknown"
        assert len(conn.execute("SELECT * FROM schema_migrations").fetchall()) == 6


def test_legacy_prefix_backfill_requires_matching_ledger(env):
    db, store, *_ = env
    # Simulate a pre-seed legacy row, preserving unknown provenance separately.
    db.ensure_guild("9")
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO message_requests(guild_id,channel_id,message_id,request_id,actor_id,"
            "body_hash,policy_hash,created_at,expires_at) "
            "VALUES('9','21','m','r','10','hash','policy',0,1)"
        )
        conn.execute(
            "INSERT INTO audio_admissions(guild_id,entry_id,actor_id,"
            "text_channel_id,request_id,created_at) VALUES('9','valid','10','21','r',0)"
        )
        conn.execute(
            "INSERT INTO audio_admissions(guild_id,entry_id,actor_id,"
            "text_channel_id,request_id,created_at) VALUES('9','wrong','11','21','r',0)"
        )
    store.seed("9", ["21"], True)
    with db.connect() as conn:
        assert admission_valid(conn, "9", "valid")
        assert not admission_valid(conn, "9", "wrong")


def test_100_setting_vs_execution_interleavings_no_late_effect(env):
    # Synthetic isolated DB race; no Discord spam, no paid inference.
    for i in range(100):
        if "21" not in env[1].channels("1"):
            change(env, "add", "21")
        request = prefix(env)
        name = "race" + str(i)
        with ThreadPoolExecutor(2) as pool:
            execution = pool.submit(env[4].execute, plan(env, request, args={"name": name}), env[2])
            removal = pool.submit(change, env, "remove", "21")
            removal.result()
            try:
                result = execution.result()
                assert result["playlist_id"]
            except DomainError as exc:
                assert exc.code in {"message_request_cancelled", "watch_request_revoked"}
        with env[0].connect() as conn:
            source = conn.execute(
                "SELECT state FROM message_requests WHERE request_id=?", (request,)
            ).fetchone()[0]
            count = conn.execute("SELECT count(*) FROM playlists WHERE name=?", (name,)).fetchone()[
                0
            ]
            assert count == (source == "committed")


class Port:
    provider, profile_id, config_hash = "mock", "test-mock", "a" * 64

    def __init__(self, env):
        self.env, self.calls = env, 0

    async def choose(self, payload, timeout):
        self.calls += 1
        change(self.env, "remove", "21")
        choice = payload["candidates"][0]["id"]
        ids = [c["id"] for c in payload["candidates"]]
        return Selection(
            choice, {i: 0.99 if i == choice else 0.01 / (len(ids) - 1) for i in ids}, self.calls
        )


@pytest.mark.asyncio
async def test_dynamic_channel_multicandidate_uses_proven_request_policy(env):
    db, _, actor, policy, executor = env
    for name in ("새벽 노동요", "새벽 작업곡"):
        executor.execute(
            ActionPlan(
                str(uuid.uuid4()),
                actor.guild_id,
                actor.user_id,
                Action.PLAYLIST_CREATE,
                {"name": name},
            ),
            replace(actor, text_channel_id="20"),
        )

    class ChoosingPort:
        provider, profile_id, config_hash = "mock", "test-mock", "a" * 64

        def __init__(self):
            self.calls = 0

        async def choose(self, payload, timeout):
            self.calls += 1
            selected = "play_request" if payload["stage_index"] == 1 else "c1"
            ids = [item["id"] for item in payload["candidates"]]
            return Selection(
                selected,
                {item: 0.99 if item == selected else 0.01 / (len(ids) - 1) for item in ids},
                self.calls,
            )

    port = ChoosingPort()
    route = Pipeline(db, policy, port, confidence=0.7, margin=0.1, prompt_version="mock-v1")
    request = MessageLedger(db).admit(
        actor.guild_id,
        actor.text_channel_id,
        str(uuid.uuid4()),
        actor.user_id,
        "새벽 노동요 혹은 새벽 작업곡 재생해줘",
        "a" * 64,
        time.time(),
    )
    result = await route.interpret(
        "새벽 노동요 혹은 새벽 작업곡 재생해줘", actor, request_id=request
    )
    assert result is not None and result.action == Action.PLAYLIST_PLAY
    assert port.calls == 2


@pytest.mark.asyncio
async def test_multicandidate_watch_revocation_before_second_dispatch(env):
    db, _, actor, policy, executor = env
    for name in ("새벽 노동요", "새벽 작업곡"):
        executor.execute(
            ActionPlan(
                str(uuid.uuid4()), actor.guild_id, actor.user_id,
                Action.PLAYLIST_CREATE, {"name": name},
            ),
            replace(actor, text_channel_id="20"),
        )

    class ChoosingPort:
        provider, profile_id, config_hash = "mock", "test-mock", "a" * 64

        def __init__(self):
            self.calls = 0

        async def choose(self, payload, timeout):
            self.calls += 1
            ids = [item["id"] for item in payload["candidates"]]
            selected = "play_request" if payload["stage_index"] == 1 else "c1"
            return Selection(
                selected,
                {item: 0.99 if item == selected else 0.01 / (len(ids) - 1) for item in ids},
                self.calls,
            )

    port = ChoosingPort()
    route = Pipeline(db, policy, port, confidence=0.7, margin=0.1, prompt_version="mock-v1")
    request = MessageLedger(db).admit(
        actor.guild_id, actor.text_channel_id, str(uuid.uuid4()), actor.user_id,
        "새벽 노동요 혹은 새벽 작업곡 재생해줘", "a" * 64, time.time(),
    )

    async def revoke():
        change(env, "remove", actor.text_channel_id)
        return actor

    with pytest.raises(DomainError, match="watch_request_revoked"):
        await route.interpret(
            "새벽 노동요 혹은 새벽 작업곡 재생해줘",
            actor,
            request_id=request,
            refresh_actor=revoke,
        )
    assert port.calls == 1


@pytest.mark.asyncio
async def test_inference_result_after_revocation_never_commits_or_dispatches_again(env):
    port = Port(env)
    pipeline = Pipeline(env[0], env[3], port, confidence=0.7, margin=0.1, prompt_version="mock-v1")
    request = prefix(env)
    with pytest.raises(DomainError):
        await pipeline.interpret("목록 보여줘", env[2], request_id=request)
    assert port.calls == 1
    with env[0].connect() as conn:
        assert conn.execute("SELECT count(*) FROM command_requests").fetchone()[0] == 0


@pytest.fixture
def client(tmp_path):
    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"20"}), frozenset({"30"}))
    bot = ChangGeunClient(
        BotConfig(
            tmp_path / "client.db",
            policy,
            tmp_path,
            {},
            prefix=PrefixConfig(True, frozenset({"21", "22"})),
        )
    )
    bot.watch.seed("1", ["21", "22"], True)
    bot.is_ready = lambda: True
    return bot


def interaction(user=10, channel=99, identifier=None):
    return SimpleNamespace(
        id=identifier or int(uuid.uuid4().int % 10**15),
        user=SimpleNamespace(id=user),
        guild_id=1,
        guild=SimpleNamespace(id=1, fetch_member=AsyncMock()),
        channel_id=channel,
        response=SimpleNamespace(
            defer=AsyncMock(), send_message=AsyncMock(), edit_message=AsyncMock()
        ),
        followup=SimpleNamespace(send=AsyncMock()),
    )


@pytest.fixture
def management(monkeypatch):
    async def fresh(client, current):
        if current.user.id != 10:
            raise DomainError("administrator_required")
        return AdminGrant("1", "10", time.time())

    monkeypatch.setattr("changgeun.discord_adapter.watch.admin", fresh)
    target = SimpleNamespace(
        name="watch", permissions_for=lambda _: SimpleNamespace(view_channel=True)
    )
    checked = AsyncMock(return_value=("ok", target))
    monkeypatch.setattr("changgeun.discord_adapter.watch.inspect", checked)
    return checked


def test_six_commands_guild_manage_permission(client):
    group = client.tree.get_command("주시")
    assert group.guild_only and group.default_permissions.manage_guild
    assert {c.name for c in group.commands} == {"추가", "제거", "목록", "켜기", "끄기", "점검"}


@pytest.mark.asyncio
async def test_add_from_outside_static_policy_and_no_jev(client, management):
    current = interaction()
    await invoke(client, current, "add")
    assert "99" in client.watch.channels("1")
    assert client.config.policy.text_channel_ids == frozenset({"20"})
    assert client.gateway is None
    current.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    assert current.followup.send.call_args.kwargs["ephemeral"]


@pytest.mark.asyncio
async def test_diagnostic_omitted_all_and_missing_permission_no_mutation(client, management):
    before = client.watch.state("1")
    management.return_value = ("view", None)
    current = interaction()
    await invoke(client, current, "inspect")
    assert management.await_count == 2
    assert "보기 부족" in current.followup.send.call_args.args[0]
    assert before == client.watch.state("1")


@pytest.mark.asyncio
async def test_remove_deleted_registered_channel_confirmation(client, management):
    current = interaction()
    await invoke(client, current, "remove", "<#21>")
    view = current.followup.send.call_args.kwargs["view"]
    assert isinstance(view, WatchConfirmation) and "21" in client.watch.channels("1")
    client.watch_cooldowns.clear()
    await view.children[0].callback(interaction())
    assert "21" not in client.watch.channels("1")
    assert management.await_count == 0


@pytest.mark.asyncio
async def test_foreign_confirmation_user_and_revoked_admin_denied(client, management):
    current = interaction()
    await invoke(client, current, "disable")
    view = current.followup.send.call_args.kwargs["view"]
    await view.children[0].callback(interaction(user=11))
    assert client.watch.state("1")["enabled"]
    client.watch_cooldowns.clear()
    view.grant = replace(view.grant, actor="11")
    await view.children[0].callback(interaction(user=11))
    assert client.watch.state("1")["enabled"]


@pytest.mark.asyncio
async def test_confirmation_expiry_and_stale_revision(client, management):
    current = interaction()
    await invoke(client, current, "disable")
    view = current.followup.send.call_args.kwargs["view"]
    client.watch.change(AdminGrant("1", "10", time.time()), "add", "add", "23", 0)
    client.watch_cooldowns.clear()
    reply = interaction()
    await view.children[0].callback(reply)
    assert "바뀌었어" in reply.followup.send.call_args.args[0]
    assert client.watch.state("1")["enabled"]
    expired = WatchConfirmation(
        client, AdminGrant("1", "10", time.time()), "disable", None, 1, "expired"
    )
    expired.deadline = 0
    await expired.children[0].callback(interaction())
    assert client.watch.state("1")["enabled"]


@pytest.mark.asyncio
async def test_preview_estimate_completion_actual_counts_include_new_request(client, management):
    current = interaction()
    await invoke(client, current, "disable")
    view = current.followup.send.call_args.kwargs["view"]
    MessageLedger(client.db).admit("1", "21", "m", "10", "text", "hash", time.time())
    client.watch_cooldowns.clear()
    reply = interaction()
    await view.children[0].callback(reply)
    assert "실제 취소 요청 1개" in reply.followup.send.call_args.args[0]


@pytest.mark.asyncio
async def test_deployment_off_cannot_enable_empty_stays_off(client, management):
    client.watch.change(AdminGrant("1", "10", time.time()), "off", "disable", None, 0)
    client.config = replace(client.config, prefix=PrefixConfig(False))
    current = interaction()
    await invoke(client, current, "enable")
    assert (
        not client.watch.state("1")["enabled"] and "준비" in current.followup.send.call_args.args[0]
    )


@pytest.mark.asyncio
async def test_management_cooldown_and_inspection_limit(client, management):
    first = interaction()
    await invoke(client, first, "list")
    second = interaction()
    await invoke(client, second, "list")
    assert "2초" in second.followup.send.call_args.args[0]
    assert management.await_count == 2


@pytest.mark.parametrize(
    "owner,manage,expected", [(True, False, True), (False, True, True), (False, False, False)]
)
@pytest.mark.asyncio
async def test_admin_latest_roles_not_dj(client, owner, manage, expected):
    current = interaction()
    member = SimpleNamespace(id=10, guild_permissions=SimpleNamespace(manage_guild=manage))
    channel = Mock(spec=discord.TextChannel)
    channel.type = discord.ChannelType.text
    channel.guild = current.guild
    channel.permissions_for.return_value = SimpleNamespace(view_channel=True)
    current.guild.owner_id = 10 if owner else 11
    current.guild.me = object()
    current.guild.fetch_member = AsyncMock(return_value=member)
    current.guild.fetch_channel = AsyncMock(return_value=channel)
    if expected:
        assert (await admin(client, current)).actor == "10"
    else:
        with pytest.raises(DomainError, match="administrator_required"):
            await admin(client, current)
    assert current.guild.fetch_member.await_count == 1


@pytest.mark.parametrize(
    "kind",
    [
        discord.ChannelType.news,
        discord.ChannelType.public_thread,
        discord.ChannelType.forum,
        discord.ChannelType.voice,
    ],
)
def test_only_general_text_channels(kind):
    channel = Mock(spec=discord.TextChannel)
    channel.type, channel.guild = kind, SimpleNamespace(id=1)
    assert not normal_text(channel, "1")


@pytest.mark.asyncio
async def test_inspect_reports_real_permission_failure_without_mutation(client):
    client._connection.user = SimpleNamespace(id=777)
    guild = SimpleNamespace(id=1, fetch_member=AsyncMock(return_value=object()))
    channel = Mock(spec=discord.TextChannel)
    channel.type, channel.guild = discord.ChannelType.text, guild
    channel.permissions_for.return_value = SimpleNamespace(
        view_channel=True, send_messages=False, read_message_history=True
    )
    guild.fetch_channel = AsyncMock(return_value=channel)
    assert (await inspect(client, guild, "21"))[0] == "send"
    assert client.watch.state("1")["revision"] == 0


@pytest.mark.parametrize("boundary", ["before_prepare", "after_prepare", "before_voice_play"])
@pytest.mark.asyncio
async def test_revocation_at_audio_boundaries_preserves_queue_and_no_failure(env, boundary):
    from changgeun.discord_adapter.runtime import AudioRuntime
    from changgeun.providers.youtube_audio import MediaResolver

    entry = enqueue(env)
    with env[0].transaction() as conn:
        session = load_session(conn, "1")
        session.state = PlaybackState.IDLE
        session.start()
        save_session(conn, "1", session)
        generation = session.generation
    voice = Mock(spec=discord.VoiceClient)
    voice.is_connected.return_value = True
    client = SimpleNamespace(get_guild=lambda _: SimpleNamespace(voice_client=voice))
    resolver = Mock(spec=MediaResolver)
    raw = Mock(spec=discord.AudioSource)
    raw.is_opus.return_value = False
    calls = 0

    async def validate(guild, current):
        nonlocal calls
        calls += 1
        with env[0].connect() as conn:
            if not admission_valid(conn, guild, current):
                raise DomainError("watch_admission_expired")
        if boundary == "before_voice_play" and calls == 2:
            change(env, "remove", "21")

    async def prepare(*args):
        if boundary == "after_prepare":
            change(env, "remove", "21")
        return raw

    resolver.prepare = AsyncMock(side_effect=prepare)
    runtime = AudioRuntime(client, env[0], resolver, AsyncMock(), validate)
    runtime.loop = asyncio.get_running_loop()
    if boundary == "before_prepare":
        change(env, "remove", "21")
    await runtime._start_audio("1", generation)
    assert not voice.play.called
    with env[0].connect() as conn:
        session = load_session(conn, "1")
        assert session.failed_tracks == 0 and session.state == PlaybackState.IDLE
        assert [e.id for e in session.queue] == [entry]
    if boundary != "before_prepare":
        raw.cleanup.assert_called()


@pytest.mark.asyncio
async def test_queue_render_exposes_expiry_and_unrelated_audio_starts(env):
    from changgeun.discord_adapter.runtime import AudioRuntime
    from changgeun.providers.youtube_audio import MediaResolver

    expired = enqueue(env, name="expired")
    valid = enqueue(env, source="slash", channel="20", name="valid")
    change(env, "remove", "21")
    actor = replace(env[2], text_channel_id="20")
    command = plan(env, "read", Action.QUEUE_SHOW, {})
    rendered = ChangGeunClient.render(Action.QUEUE_SHOW, env[4].execute(command, actor))
    assert "승인 만료" in rendered
    with env[0].transaction() as conn:
        session = load_session(conn, "1")
        session.state = PlaybackState.IDLE
        session.start()
        assert session.current.id == valid and session.queue[0].id == expired
        save_session(conn, "1", session)
        generation = session.generation
    voice = Mock(spec=discord.VoiceClient)
    voice.is_connected.return_value = True
    client = SimpleNamespace(get_guild=lambda _: SimpleNamespace(voice_client=voice))
    resolver = Mock(spec=MediaResolver)
    raw = Mock(spec=discord.AudioSource)
    raw.is_opus.return_value = False
    resolver.prepare = AsyncMock(return_value=raw)
    runtime = AudioRuntime(client, env[0], resolver, AsyncMock())
    runtime.loop = asyncio.get_running_loop()
    await runtime._start_audio("1", generation)
    voice.play.assert_called_once()
    with env[0].connect() as conn:
        assert (
            conn.execute(
                "SELECT started FROM audio_admissions WHERE entry_id=?", (valid,)
            ).fetchone()[0]
            == 1
        )

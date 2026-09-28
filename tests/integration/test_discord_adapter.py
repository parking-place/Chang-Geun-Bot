import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace

import discord
import pytest

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import (
    ChangGeunClient,
    ConfirmationView,
    PageView,
    PlaybackView,
    help_text,
    natural_failure,
)
from changgeun.domain.models import Action, Actor, DomainError, Policy
from changgeun.providers.media import ApprovedAudioResolver


class Response:
    def __init__(self, events):
        self.events, self.done = events, False

    async def defer(self, **kwargs):
        self.events.append("deferred")
        self.done = True

    def is_done(self):
        return self.done

    async def send_message(self, content, **kwargs):
        self.events.append(content)
        self.done = True

    async def edit_message(self, **kwargs):
        self.events.append(kwargs)


class Followup:
    def __init__(self, events):
        self.events = events

    async def send(self, content, **kwargs):
        self.events.append((content, kwargs))


def interaction(identifier=100, user=10, component=False):
    events = []
    return SimpleNamespace(
        id=identifier,
        user=SimpleNamespace(id=user),
        guild_id=1,
        channel_id=3,
        type=discord.InteractionType.component
        if component
        else discord.InteractionType.application_command,
        response=Response(events),
        followup=Followup(events),
        events=events,
    )


@pytest.fixture
def client(tmp_path):
    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"3"}), frozenset({"4"}))
    config = BotConfig(tmp_path / "db.sqlite", policy, tmp_path / "audio", {})
    bot = ChangGeunClient(config)
    actor = Actor("1", "10", frozenset({"2"}), "3", "4", "4")

    async def fresh(current):
        await asyncio.sleep(0.01)
        current.events.append("roles_fetched")
        return replace(actor, user_id=str(current.user.id))

    bot.fresh_actor = fresh
    return bot


@pytest.mark.asyncio
async def test_v2_keeps_disabled_watch_recovery_admin_only(client, monkeypatch):
    parsed, dispatched = [], []

    async def parse(*args):
        parsed.append(args)

    async def dispatch(_client, _entry, _actor, choice, _text):
        dispatched.append(choice.command.identifier)

    async def fresh(entry):
        return Actor("1", str(entry.user.id), frozenset({"2"}), "3", "4", "4",
                     manage_guild=True)

    client.parser_v2 = SimpleNamespace(parse=parse)
    client.fresh_actor = fresh
    monkeypatch.setattr("changgeun.discord_adapter.client.dispatch_natural", dispatch)
    await client.natural_input(interaction(identifier=110), "주시 목록",
                               admin_only=True, quiet=True)
    await client.natural_input(interaction(identifier=111), "현재곡",
                               admin_only=True, quiet=True)
    assert parsed == [] and dispatched == ["C42"]
    await client.natural_input(interaction(identifier=112), "목록 보여줘")
    assert len(parsed) == 1 and dispatched == ["C42"]


def test_role_and_channel_help_does_not_expose_management_or_other_channels(client):
    policy = client.config.policy
    guest = Actor("1", "10", frozenset(), "3", None, None)
    dj = replace(guest, role_ids=frozenset({"2"}))
    admin = replace(guest, manage_guild=True)
    assert "/곡제안" in help_text(
        guest, policy, youtube_audio=False, prefix_enabled=True, watched_here=False
    )
    assert "/주시" not in help_text(
        guest, policy, youtube_audio=False, prefix_enabled=True, watched_here=False
    )
    assert "/재생" in help_text(
        dj, policy, youtube_audio=False, prefix_enabled=True, watched_here=True
    )
    assert "!!창근아" in help_text(
        dj, policy, youtube_audio=False, prefix_enabled=True, watched_here=True
    )
    assert "/주시 목록" in help_text(
        admin, policy, youtube_audio=False, prefix_enabled=True, watched_here=False
    )
    assert "/주시" not in help_text(
        None, policy, youtube_audio=False, prefix_enabled=True, watched_here=True
    )
    assert "/주시" not in help_text(
        replace(admin, text_channel_id="9"),
        policy,
        youtube_audio=False,
        prefix_enabled=True,
        watched_here=True,
    )


def test_recent_history_is_thirty_days_capped_at_one_hundred_and_readable(client):
    actor = Actor("1", "10", frozenset({"2"}), "3", "4", "4")
    track = client.executor.execute(
        client.make_plan(
            actor,
            "history-track",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "history", "title": "같은 제목"},
        ),
        actor,
    )["track_id"]
    now = time.time()
    with client.db.transaction() as conn:
        for number in range(105):
            conn.execute(
                "INSERT INTO playback_history VALUES(?,?,?,?)",
                (
                    "1",
                    f"entry-{number}",
                    track,
                    now - number if number < 100 else now - 31 * 86400,
                ),
            )
    guest = replace(actor, role_ids=frozenset())
    result = client.executor.execute(
        client.make_plan(guest, "history-list", Action.HISTORY_LIST, {}), guest
    )
    assert len(result["history"]) == 100
    assert result["history"][0]["track_id"] == track
    assert len({row["history_id"] for row in result["history"]}) == 100
    page = PageView(client, guest, Action.HISTORY_LIST, {}, result)
    assert "총 100건" in page.render()
    assert any(item.label == "최근곡 재생" for item in page.children)


@pytest.mark.asyncio
async def test_read_pages_bind_actor_and_reject_changed_snapshot(client):
    actor = await client.fresh_actor(interaction())
    with client.db.transaction() as conn:
        for number in range(26):
            conn.execute(
                "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                ("1", f"list-{number}", f"목록 {number:02d}", f"목록 {number:02d}"),
            )
    result = client.executor.execute(
        client.make_plan(actor, "read", Action.PLAYLIST_LIST, {}), actor
    )
    page = PageView(client, actor, Action.PLAYLIST_LIST, {}, result)
    assert "총 26건 · 1/3페이지" in page.render()
    await page.move(interaction(102, user=20, component=True), 1)
    assert page.page == 0
    current = interaction(103, component=True)
    await page.move(current, 1)
    assert page.page == 1 and "2/3페이지" in current.events[-1]["content"]
    # The button's freshness read must not consume the mutation interaction ID.
    client.executor.execute(
        client.make_plan(actor, "103", Action.PLAYLIST_CREATE, {"name": "새 목록"}), actor
    )
    with client.db.transaction() as conn:
        conn.execute("UPDATE playlists SET deleted_at=1 WHERE id='list-0'")
    current = interaction(104, component=True)
    await page.move(current, 1)
    assert page.page == 1
    assert "다시 실행" in current.events[-1]


@pytest.mark.asyncio
async def test_proposals_beyond_twenty_five_and_current_status(client):
    actor = await client.fresh_actor(interaction())
    playlist = client.executor.execute(
        client.make_plan(actor, "p", Action.PLAYLIST_CREATE, {"name": "대기 목록"}), actor
    )["playlist_id"]
    track = client.executor.execute(
        client.make_plan(
            actor,
            "t",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "tone", "title": "시험음"},
        ),
        actor,
    )["track_id"]
    with client.db.transaction() as conn:
        for number in range(27):
            conn.execute(
                "INSERT INTO proposals(guild_id,id,actor_id,playlist_id,track_id,created_at) "
                "VALUES(?,?,?,?,?,?)",
                ("1", f"proposal-{number}", "10", playlist, track, float(number)),
            )
    result = client.executor.execute(
        client.make_plan(actor, "read-proposals", Action.PROPOSAL_LIST, {}), actor
    )
    assert len(result["proposals"]) == 27
    page = PageView(client, actor, Action.PROPOSAL_LIST, {}, result)
    page.page = 2
    assert "총 27건 · 3/3페이지" in page.render()
    current = interaction(105)
    await client.current_status(current)
    assert "상태: 연결 안 됨" in current.events[-1][0]
    assert "볼륨 30%" in current.events[-1][0]


def test_natural_error_is_bounded_and_does_not_echo_upstream_body():
    assert natural_failure(DomainError("dj_required"))[0] == "permission"
    assert natural_failure(DomainError("watch_request_revoked"))[0] == "revoked"
    category, message = natural_failure(RuntimeError("secret value and user message"))
    assert category == "unknown"
    assert "secret" not in message and "user message" not in message


@pytest.mark.asyncio
async def test_playlist_play_handler_binds_queue_and_preserves_saved_entries(client, tmp_path):
    actor = await client.fresh_actor(interaction())
    root = tmp_path / "audio"
    root.mkdir()
    (root / "tone.wav").write_bytes(b"approved fixture")
    client.audio.resolver = ApprovedAudioResolver(root, {"tone": "tone.wav"})
    track = client.executor.execute(
        client.make_plan(
            actor,
            "register",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "tone", "title": "시험음"},
        ),
        actor,
    )["track_id"]
    playlist = client.executor.execute(
        client.make_plan(actor, "create", Action.PLAYLIST_CREATE, {"name": "시험 목록"}), actor
    )["playlist_id"]
    client.executor.execute(
        client.make_plan(
            actor, "add", Action.PLAYLIST_ADD, {"playlist_id": playlist, "track_ids": [track]}
        ),
        actor,
    )
    applied = []

    async def audio(guild, action, result):
        applied.append((guild, action, result))

    client.audio.apply = audio
    await client.play_input(interaction(), None, "시험 목록")
    with client.db.transaction() as conn:
        assert conn.execute("SELECT track_id FROM queue_entries").fetchone()[0] == track
        assert conn.execute("SELECT track_id FROM playlist_entries").fetchone()[0] == track
        assert conn.execute("SELECT start_after_connect FROM sessions").fetchone()[0] == 1
    assert applied[0][1] == Action.PLAYLIST_PLAY


@pytest.mark.asyncio
async def test_slash_bare_youtube_url_uses_single_video_plan_before_catalog_lookup(client):
    captured = []

    async def submit(entry, command, **kwargs):
        captured.append(command)

    client.submit_plan = submit
    await client.play_input(interaction(), "youtube.com/watch?v=GD_rjpO7CIQ", None)
    assert len(captured) == 1
    assert captured[0].action == Action.TRACK_PLAY
    assert captured[0].arguments == {"track_id": "youtube:GD_rjpO7CIQ", "channel_id": "4"}
    with client.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM queue_entries").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_missing_audio_mapping_rejects_playlist_before_queue_changes(client):
    actor = await client.fresh_actor(interaction())
    track = client.executor.execute(
        client.make_plan(
            actor,
            "register",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "missing", "title": "누락"},
        ),
        actor,
    )["track_id"]
    playlist = client.executor.execute(
        client.make_plan(actor, "create", Action.PLAYLIST_CREATE, {"name": "누락 목록"}), actor
    )["playlist_id"]
    client.executor.execute(
        client.make_plan(
            actor, "add", Action.PLAYLIST_ADD, {"playlist_id": playlist, "track_ids": [track]}
        ),
        actor,
    )
    await client.play_input(interaction(), None, "누락 목록")
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM queue_entries").fetchone()[0] == 0
        assert conn.execute("SELECT generation FROM sessions").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_defer_precedes_slow_role_query_and_mutation(client):
    current = interaction()
    command = client.tree.get_command("목록").get_command("생성")
    await command.callback(current, 이름="실제 핸들러 시험")
    assert current.events[:2] == ["deferred", "roles_fetched"]
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_non_dj_slash_and_public_buttons_cannot_mutate(client):
    async def non_dj(current):
        return Actor("1", str(current.user.id), frozenset(), "3", "4", "4")

    client.fresh_actor = non_dj
    current = interaction()
    command = client.tree.get_command("목록").get_command("생성")
    await command.callback(current, 이름="금지")
    button = next(b for b in PlaybackView(client).children if b.label == "정지")
    await button.callback(interaction(101, component=True))
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0
        assert conn.execute("SELECT generation FROM sessions").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_confirmation_button_fresh_roles_and_other_user_denied(client):
    actor = await client.fresh_actor(interaction())
    create = client.make_plan(actor, "create", Action.PLAYLIST_CREATE, {"name": "목록"})
    playlist = client.executor.execute(create, actor)["playlist_id"]
    delete = client.make_plan(actor, "delete", Action.PLAYLIST_DELETE, {"playlist_id": playlist})
    token = client.executor.preview(delete, actor)
    view = ConfirmationView(client, delete, token)
    await view.children[0].callback(interaction(101, user=20, component=True))
    with client.db.transaction() as conn:
        assert conn.execute("SELECT deleted_at FROM playlists").fetchone()[0] is None

    async def revoked(current):
        return replace(actor, role_ids=frozenset())

    client.fresh_actor = revoked
    await view.children[0].callback(interaction(102, component=True))
    with client.db.transaction() as conn:
        assert conn.execute("SELECT deleted_at FROM playlists").fetchone()[0] is None


@pytest.mark.asyncio
async def test_external_unknown_attempt_is_not_repeated(client):
    actor = await client.fresh_actor(interaction())
    plan = client.make_plan(actor, "join", Action.VOICE_JOIN, {"channel_id": "4"})
    result = client.executor.execute(plan, actor)
    calls = []

    async def fail(guild, action, result):
        calls.append(action)
        raise RuntimeError("unknown external result")

    client.audio._apply = fail
    with pytest.raises(RuntimeError):
        await client.audio.apply("1", Action.VOICE_JOIN, result)
    await client.audio.apply("1", Action.VOICE_JOIN, result)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_restart_invalidates_pending_confirmation_and_preserves_data(client):
    actor = await client.fresh_actor(interaction())
    plan = client.make_plan(actor, "create", Action.PLAYLIST_CREATE, {"name": "목록"})
    playlist = client.executor.execute(plan, actor)["playlist_id"]
    delete = client.make_plan(actor, "delete", Action.PLAYLIST_DELETE, {"playlist_id": playlist})
    client.executor.preview(delete, actor)
    client.audio.recover(client.config.policy.guild_ids)
    with client.db.transaction() as conn:
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 1
        assert conn.execute("SELECT desired_state FROM sessions").fetchone()[0] == "disconnected"


@pytest.mark.asyncio
async def test_youtube_registration_uses_official_duration_and_rechecks_roles(
    client, monkeypatch, tmp_path
):
    from changgeun.providers.media import Metadata

    key = tmp_path / "key"
    key.write_text("synthetic-key")
    key.chmod(0o600)
    client.config = replace(client.config, youtube_key_file=key)
    calls = []

    class MetadataPort:
        async def videos(self, ids):
            calls.append(ids)
            return {ids[0]: Metadata(ids[0], "공식 제목", "출처", 123)}

    monkeypatch.setattr(client, "youtube_api", lambda: MetadataPort())
    current = interaction()
    await (
        client.tree.get_command("곡")
        .get_command("등록")
        .callback(current, 링크="https://www.youtube.com/watch?v=ABCDEFGHIJK")
    )
    assert calls == [["ABCDEFGHIJK"]]
    with client.db.transaction() as conn:
        import json

        row = conn.execute("SELECT title,metadata_json FROM tracks").fetchone()
        assert row[0] == "공식 제목" and json.loads(row[1])["duration_seconds"] == 123
    assert current.events.count("roles_fetched") >= 2


@pytest.mark.asyncio
async def test_non_dj_import_does_not_read_file_or_call_external_api(client, monkeypatch):
    async def denied(current):
        return Actor("1", "10", frozenset(), "3")

    client.fresh_actor = denied

    class Attachment:
        size = 100

        async def read(self):
            raise AssertionError("unauthorized file read")

    def forbidden():
        raise AssertionError("unauthorized external request")

    monkeypatch.setattr(client, "youtube_api", forbidden)
    current = interaction()
    await (
        client.tree.get_command("목록")
        .get_command("가져오기")
        .callback(current, 이름="금지", 파일=Attachment())
    )
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_json_import_shows_confirmation_before_any_list_change(client):
    class Attachment:
        size = 200

        async def read(self):
            return (
                b'{"schema_version":1,"tracks":[{"source_type":"youtube",'
                b'"external_id":"ABCDEFGHIJK","title":"reference"}]}'
            )

    current = interaction()
    await (
        client.tree.get_command("목록")
        .get_command("가져오기")
        .callback(current, 이름="참조 목록", 파일=Attachment())
    )
    view = current.events[-1][1]["view"]
    assert isinstance(view, ConfirmationView)
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0
    await view.children[0].callback(interaction(101, component=True))
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_undo_handler_prompts_and_changes_only_after_confirmation(client):
    actor = await client.fresh_actor(interaction())
    playlist = client.executor.execute(
        client.make_plan(actor, "create", Action.PLAYLIST_CREATE, {"name": "원래 이름"}), actor
    )["playlist_id"]
    client.executor.execute(
        client.make_plan(
            actor, "rename", Action.PLAYLIST_RENAME, {"playlist_id": playlist, "name": "새 이름"}
        ),
        actor,
    )
    current = interaction()
    await client.tree.get_command("되돌리기").callback(current)
    view = current.events[-1][1]["view"]
    assert isinstance(view, ConfirmationView)
    with client.db.transaction() as conn:
        assert conn.execute("SELECT name FROM playlists").fetchone()[0] == "새 이름"
    await view.children[0].callback(interaction(101, component=True))
    with client.db.transaction() as conn:
        assert conn.execute("SELECT name FROM playlists").fetchone()[0] == "원래 이름"
        assert conn.execute("SELECT version FROM playlists").fetchone()[0] == 2


@pytest.mark.asyncio
async def test_registration_role_revoked_during_external_lookup_cannot_store(
    client, monkeypatch, tmp_path
):
    from changgeun.providers.media import Metadata

    key = tmp_path / "key"
    key.write_text("synthetic-key")
    key.chmod(0o600)
    client.config = replace(client.config, youtube_key_file=key)

    class MetadataPort:
        async def videos(self, ids):
            async def revoked(current):
                return Actor("1", "10", frozenset(), "3")

            client.fresh_actor = revoked
            return {ids[0]: Metadata(ids[0], "참조", "출처", 123)}

    monkeypatch.setattr(client, "youtube_api", lambda: MetadataPort())
    await (
        client.tree.get_command("곡")
        .get_command("등록")
        .callback(interaction(), 링크="https://www.youtube.com/watch?v=ABCDEFGHIJK")
    )
    with client.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0


@pytest.mark.parametrize(
    "content,expected",
    [
        ("<@777> 목록 보여줘", "목록 보여줘"),
        ("<@!777> 대기열 보여줘", "대기열 보여줘"),
        ("창근아 목록 보여줘", None),
        ("<@888> 목록 보여줘", None),
        ("본문에 <@777> 목록 보여줘", None),
    ],
)
@pytest.mark.asyncio
async def test_explicit_mention_routes_to_same_natural_entry(client, content, expected):
    client._connection.user = SimpleNamespace(id=777)
    seen = []

    async def natural(entry, text):
        seen.append((entry.guild_id, entry.channel_id, entry.user.id, text))

    client.natural_input = natural
    message = SimpleNamespace(
        webhook_id=None,
        type=discord.MessageType.default,
        id=123,
        content=content,
        author=SimpleNamespace(id=10, bot=False),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=3),
    )
    await client.on_message(message)
    assert seen == ([] if expected is None else [(1, 3, 10, expected)])
    assert client.intents.message_content is False


@pytest.mark.parametrize("guild,channel,bot", [(2, 3, False), (1, 9, False), (1, 3, True)])
@pytest.mark.asyncio
async def test_mention_outside_scope_or_from_bot_is_ignored(client, guild, channel, bot):
    client._connection.user = SimpleNamespace(id=777)

    async def forbidden(entry, text):
        raise AssertionError("out of scope mention dispatched")

    client.natural_input = forbidden
    await client.on_message(
        SimpleNamespace(
            webhook_id=None,
            type=discord.MessageType.default,
            id=123,
            content="<@777> 목록 보여줘",
            author=SimpleNamespace(id=10, bot=bot),
            guild=SimpleNamespace(id=guild),
            channel=SimpleNamespace(id=channel),
        )
    )


@pytest.mark.parametrize(
    "content,channel_id,kind,bot,webhook,expected",
    [
        ("!!창근아 목록 보여줘", 3, discord.ChannelType.text, False, None, True),
        ("!!창근아 목록 보여줘", 5, discord.ChannelType.text, False, None, True),
        ("!!창근아 목록 보여줘", 9, discord.ChannelType.text, False, None, False),
        ("!!창근아 목록 보여줘", 3, discord.ChannelType.news, False, None, False),
        ("!!창근아 목록 보여줘", 3, discord.ChannelType.text, True, None, False),
        ("!!창근아 목록 보여줘", 3, discord.ChannelType.text, False, 999, False),
        (" !!창근아 목록 보여줘", 3, discord.ChannelType.text, False, None, False),
        ("!!창근아목록 보여줘", 3, discord.ChannelType.text, False, None, False),
    ],
)
@pytest.mark.asyncio
async def test_prefix_real_channel_types_and_opaque_identity(
    tmp_path, content, channel_id, kind, bot, webhook, expected
):
    import datetime
    from unittest.mock import Mock

    from changgeun.discord_adapter.prefix import PrefixConfig

    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"3", "5"}), frozenset({"4"}))
    config = BotConfig(
        tmp_path / "prefix.db",
        policy,
        tmp_path,
        {},
        prefix=PrefixConfig(True, frozenset({"3", "5"})),
    )
    client = ChangGeunClient(config)
    client._connection.user = SimpleNamespace(id=777)
    client.prefix_ready = True
    client.watch.seed("1", ["3", "5"], True)
    channel = Mock(spec=discord.TextChannel)
    channel.id, channel.type = channel_id, kind
    channel.permissions_for.return_value = SimpleNamespace(
        view_channel=True, send_messages=True, read_message_history=True
    )
    message = SimpleNamespace(
        webhook_id=webhook,
        type=discord.MessageType.default,
        id=123,
        content=content,
        author=SimpleNamespace(id=10, bot=bot),
        guild=SimpleNamespace(id=1, me=object()),
        channel=channel,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    seen = []

    async def natural(entry, body):
        seen.append((entry.request_id, body))

    client.natural_input = natural
    await client.on_message(message)
    assert bool(seen) == expected
    if expected:
        assert seen[0][0] != "123"
        assert seen[0][1] == "목록 보여줘"
        assert client.intents.message_content


@pytest.mark.asyncio
async def test_search_requires_user_selection_and_never_autoplays(client):
    from unittest.mock import AsyncMock

    from changgeun.providers.media import Metadata

    client.config = replace(client.config, youtube_audio_enabled=True)
    api = SimpleNamespace(
        search=AsyncMock(
            return_value=[
                Metadata("ABCDEFGHIJK", "첫 번째 영상", "creator", 100),
                Metadata("ZYXWVUTSRQP", "너무 긴 영상", "creator", 1801),
            ]
        )
    )
    client.youtube_api = lambda: api
    entry = interaction()
    await client.search_play_input(entry, "시험 검색")
    sent = [item for item in entry.events if isinstance(item, tuple)]
    view = sent[-1][1]["view"]
    assert view.identifiers == ("ABCDEFGHIJK",)
    with client.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM queue_entries").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM tracks").fetchone()[0] == 0
    foreign = interaction(101, user=11, component=True)
    await view.children[0].callback(foreign)
    assert "요청한 사람만" in foreign.events[-1]
    assert not view.used

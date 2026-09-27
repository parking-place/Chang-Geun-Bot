import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from changgeun.application.executor import Executor
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.storage.database import Database


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "test.db")
    db.ensure_guild("1")
    db.ensure_guild("2")
    actor = Actor("1", "10", frozenset({"dj"}), "text", "voice", "voice")
    policy = Policy(
        frozenset({"1", "2"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"})
    )
    return db, actor, Executor(db, policy)


def plan(actor, action, args=None, versions=None, request="r", **kwargs):
    return ActionPlan(
        request, actor.guild_id, actor.user_id, action, args or {}, versions or {}, **kwargs
    )


def register(executor, actor, n=1):
    return [
        executor.execute(
            plan(
                actor,
                Action.CATALOG_REGISTER,
                {"source_type": "fixture", "external_id": str(i), "title": f"곡 {i}"},
                request=f"register-{i}",
            ),
            actor,
        )["track_id"]
        for i in range(n)
    ]


def create(executor, actor):
    return executor.execute(
        plan(actor, Action.PLAYLIST_CREATE, {"name": "노동요"}, request="create"), actor
    )["playlist_id"]


def entries(db, playlist):
    conn = db.connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM playlist_entries "
                "WHERE guild_id='1' AND playlist_id=? ORDER BY position",
                (playlist,),
            )
        ]
    finally:
        conn.close()


def test_migrations_reapply_and_reject_corrupt(tmp_path):
    path = tmp_path / "test.db"
    Database(path)
    Database(path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE schema_migrations SET checksum='bad'")
    conn.commit()
    conn.close()
    with pytest.raises(DomainError, match="migration_checksum"):
        Database(path)


def test_unknown_database_is_preserved(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE important_data(value TEXT)")
    conn.close()
    with pytest.raises(DomainError, match="unknown_database_schema"):
        Database(path)


def test_restart_empty_playlist_and_unique_name(env):
    db, actor, executor = env
    create(executor, actor)
    reopened = Executor(Database(db.path), executor.policy)
    assert len(reopened.execute(plan(actor, Action.PLAYLIST_LIST), actor)["playlists"]) == 1
    with pytest.raises(DomainError, match="constraint_conflict"):
        executor.execute(
            plan(actor, Action.PLAYLIST_CREATE, {"name": "  노동요 "}, request="collision"), actor
        )


def test_composite_foreign_key_blocks_cross_guild(env):
    db, actor, executor = env
    track = register(executor, actor)[0]
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO queue_entries VALUES('2','entry',?,0)", (track,))


def test_stable_entries_and_queue_independent(env):
    db, actor, executor = env
    tracks = register(executor, actor, 3)
    playlist = create(executor, actor)
    executor.execute(
        plan(
            actor,
            Action.PLAYLIST_ADD,
            {"playlist_id": playlist, "track_ids": tracks},
            {playlist: 0},
            "add",
        ),
        actor,
    )
    original = entries(db, playlist)
    assert len({r["id"] for r in original} | set(tracks)) == 6
    executor.execute(
        plan(actor, Action.QUEUE_ENQUEUE, {"track_ids": tracks}, {"queue": 0}, "enqueue"), actor
    )
    executor.execute(
        plan(
            actor,
            Action.PLAYLIST_MOVE,
            {"playlist_id": playlist, "entry_id": original[2]["id"], "position": 0},
            {playlist: 1},
            "move",
        ),
        actor,
    )
    assert [r["track_id"] for r in entries(db, playlist)] == [tracks[2], tracks[0], tracks[1]]
    queue = executor.execute(plan(actor, Action.QUEUE_SHOW, request="show"), actor)
    assert [r["track_id"] for r in queue["entries"]] == tracks
    assert all(r["id"] not in {p["id"] for p in original} for r in queue["entries"])


def test_concurrent_duplicate_mutates_once_and_body_conflict(env):
    db, actor, executor = env
    command = plan(actor, Action.PLAYLIST_CREATE, {"name": "한번"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: executor.execute(command, actor), range(4)))
    assert all(r == results[0] for r in results)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM change_events").fetchone()[0] == 1
    with pytest.raises(DomainError, match="request_body_conflict"):
        executor.execute(replace(command, arguments={"name": "다름"}), actor)


def test_valid_confirmation_has_its_own_deadline_and_rechecks_authority(env):
    _, actor, executor = env
    now = [100.0]
    executor.clock = lambda: now[0]
    playlist = create(executor, actor)
    command = plan(
        actor,
        Action.PLAYLIST_DELETE,
        {"playlist_id": playlist},
        {playlist: 0},
        "delete",
        origin="natural_language",
        expires_at=112.0,
    )
    token = executor.preview(command, actor)
    now[0] = 113.0
    with pytest.raises(DomainError, match="dj_required"):
        executor.execute(command, replace(actor, role_ids=frozenset()), confirmation=token)
    executor.execute(command, actor, confirmation=token)


def test_arbitrary_confirmation_cannot_extend_read_deadline(env):
    _, actor, executor = env
    command = plan(actor, Action.QUEUE_SHOW, expires_at=1)
    with pytest.raises(DomainError, match="execution_deadline_expired"):
        executor.execute(command, actor, confirmation="unrelated-token")


def test_failure_rolls_back_change_audit_and_result(env):
    db, actor, executor = env

    def fail():
        raise RuntimeError("injected")

    executor.before_commit = fail
    with pytest.raises(RuntimeError, match="injected"):
        create(executor, actor)
    with db.transaction() as conn:
        for table in ("playlists", "command_requests", "change_events"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_confirmation_expiry_role_change_and_version_conflict(env):
    db, actor, executor = env
    playlist = create(executor, actor)
    command = plan(
        actor, Action.PLAYLIST_DELETE, {"playlist_id": playlist}, {playlist: 0}, "delete"
    )
    token = executor.preview(command, actor)
    with pytest.raises(DomainError, match="dj_required"):
        executor.execute(command, replace(actor, role_ids=frozenset()), confirmation=token)
    with pytest.raises(DomainError, match="confirmation_mismatch"):
        executor.execute(replace(command, request_id="other"), actor, confirmation=token)
    executor.execute(
        plan(
            actor,
            Action.PLAYLIST_RENAME,
            {"playlist_id": playlist, "name": "새 이름"},
            {playlist: 0},
            "rename",
        ),
        actor,
    )
    with pytest.raises(DomainError, match="version_conflict"):
        executor.execute(command, actor, confirmation=token)
    command = replace(command, expected_versions={playlist: 1})
    executor.clock = lambda: 1000
    token = executor.preview(command, actor)
    executor.clock = lambda: 1060
    with pytest.raises(DomainError, match="confirmation_expired"):
        executor.execute(command, actor, confirmation=token)


def test_confirmed_delete_replay_and_name_reuse(env):
    db, actor, executor = env
    playlist = create(executor, actor)
    command = plan(
        actor, Action.PLAYLIST_DELETE, {"playlist_id": playlist}, {playlist: 0}, "delete"
    )
    token = executor.preview(command, actor)
    result = executor.execute(command, actor, confirmation=token)
    assert executor.execute(command, actor, confirmation=token) == result
    executor.execute(plan(actor, Action.PLAYLIST_CREATE, {"name": "노동요"}, request="new"), actor)
    with pytest.raises(DomainError, match="constraint_conflict"):
        executor.execute(
            plan(
                actor, Action.PLAYLIST_RESTORE, {"playlist_id": playlist}, {playlist: 1}, "restore"
            ),
            actor,
        )


def test_stale_position_does_not_change_new_target(env):
    db, actor, executor = env
    playlist = create(executor, actor)
    executor.execute(
        plan(
            actor,
            Action.PLAYLIST_ADD,
            {"playlist_id": playlist, "track_ids": register(executor, actor, 3)},
            {playlist: 0},
            "add",
        ),
        actor,
    )
    rows = entries(db, playlist)
    executor.execute(
        plan(
            actor,
            Action.PLAYLIST_MOVE,
            {"playlist_id": playlist, "entry_id": rows[2]["id"], "position": 0},
            {playlist: 1},
            "move",
        ),
        actor,
    )
    with pytest.raises(DomainError, match="version_conflict"):
        executor.execute(
            plan(
                actor,
                Action.PLAYLIST_REMOVE,
                {"playlist_id": playlist, "entry_id": rows[2]["id"]},
                {playlist: 1},
                "remove",
            ),
            actor,
        )
    assert len(entries(db, playlist)) == 3


def test_backup_keeps_data_and_foreign_keys(env, tmp_path):
    db, actor, executor = env
    create(executor, actor)
    backup = tmp_path / "backup.db"
    db.backup(backup)
    restored = Database(backup)
    with restored.transaction() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 1


def test_extra_arguments_and_missing_expected_version_are_rejected(env):
    db, actor, executor = env
    with pytest.raises(DomainError, match="invalid_arguments"):
        executor.execute(plan(actor, Action.PLAYLIST_CREATE, {"name": "x", "dj": True}), actor)
    playlist = create(executor, actor)
    with pytest.raises(DomainError, match="expected_version_required"):
        executor.execute(
            plan(
                actor,
                Action.PLAYLIST_RENAME,
                {"playlist_id": playlist, "name": "y"},
                request="rename",
            ),
            actor,
        )


def test_youtube_single_play_requires_explicit_source_and_admits_its_owner(env):
    db, actor, executor = env
    track = executor.execute(
        plan(
            actor,
            Action.CATALOG_REGISTER,
            {"source_type": "youtube", "external_id": "ABCDEFGHIJK", "title": "public video"},
            request="video",
        ),
        actor,
    )["track_id"]
    command = plan(
        actor,
        Action.TRACK_PLAY,
        {"track_id": track, "channel_id": "voice"},
        {"queue": 0},
        request="play-video",
    )
    with pytest.raises(DomainError, match="audio_source_not_approved"):
        executor.execute(command, actor)
    enabled = Executor(db, executor.policy, youtube_audio_enabled=True)
    result = enabled.execute(command, actor)
    assert result["desired_state"] == "connecting"
    assert enabled.execute(command, actor) == result
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM queue_entries").fetchone()[0] == 1
        admission = conn.execute("SELECT actor_id,text_channel_id FROM audio_admissions").fetchone()
        assert tuple(admission) == ("10", "text")


def test_explicit_single_video_starts_before_preserved_idle_queue(env):
    db, actor, executor = env
    old = executor.execute(
        plan(
            actor,
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "old", "title": "기존 목록 음원"},
            request="old",
        ),
        actor,
    )["track_id"]
    executor.execute(
        plan(actor, Action.QUEUE_ENQUEUE, {"track_ids": [old]}, {"queue": 0}, request="queued-old"),
        actor,
    )
    video = executor.execute(
        plan(
            actor,
            Action.CATALOG_REGISTER,
            {"source_type": "youtube", "external_id": "ABCDEFGHIJK", "title": "지정 영상"},
            request="new-video",
        ),
        actor,
    )["track_id"]
    enabled = Executor(db, executor.policy, youtube_audio_enabled=True)
    result = enabled.execute(
        plan(
            actor,
            Action.TRACK_PLAY,
            {"track_id": video, "channel_id": "voice"},
            {"queue": 1},
            request="play-new",
        ),
        actor,
    )
    assert result["start_requested"] and not result["queued"]
    assert result["requested_title"] == "지정 영상"
    with db.connect() as conn:
        assert [
            r[0] for r in conn.execute("SELECT track_id FROM queue_entries ORDER BY position")
        ] == [video, old]


def test_append_during_resolution_does_not_restart_current_entry(env):
    db, actor, executor = env
    tracks = register(executor, actor, 2)
    executor.execute(
        plan(actor, Action.QUEUE_ENQUEUE, {"track_ids": [tracks[0]]}, {"queue": 0}, request="q"),
        actor,
    )
    with db.transaction() as conn:
        conn.execute(
            "UPDATE sessions SET desired_state='resolving',current_entry_id='current',"
            "current_track_id=?,generation=10 WHERE guild_id='1'",
            (tracks[0],),
        )
        conn.execute("DELETE FROM queue_entries")
        conn.execute("UPDATE tracks SET source_type='approved_audio' WHERE id=?", (tracks[1],))
    result = executor.execute(
        plan(
            actor,
            Action.TRACK_PLAY,
            {"track_id": tracks[1], "channel_id": "voice"},
            {"queue": 1},
            request="append",
        ),
        actor,
    )
    assert result["queued"] and not result["start_requested"]
    assert result["generation"] == 10
    with db.connect() as conn:
        assert conn.execute("SELECT current_track_id FROM sessions").fetchone()[0] == tracks[0]


@pytest.mark.parametrize("state", ["disconnected", "idle"])
def test_explicit_play_reuses_stopped_queue_entry_with_fresh_admission(env, state):
    db, actor, executor = env
    track = executor.execute(
        plan(
            actor,
            Action.CATALOG_REGISTER,
            {"source_type": "youtube", "external_id": "ABCDEFGHIJK", "title": "지정 영상"},
            request="register-video",
        ),
        actor,
    )["track_id"]
    enabled = Executor(db, executor.policy, youtube_audio_enabled=True)
    enabled.execute(
        plan(
            actor, Action.QUEUE_ENQUEUE, {"track_ids": [track]}, {"queue": 0}, request="queue-video"
        ),
        actor,
    )
    with db.transaction() as conn:
        entry = conn.execute("SELECT id FROM queue_entries").fetchone()[0]
        conn.execute("UPDATE sessions SET desired_state=?", (state,))
    requester = replace(actor, user_id="20")
    command = plan(
        requester,
        Action.TRACK_PLAY,
        {"track_id": track, "channel_id": "voice"},
        {"queue": 1},
        request="replay-video",
    )
    result = enabled.execute(command, requester)
    assert result["start_requested"] and result["reused_entry_id"] == entry
    assert enabled.execute(command, requester) == result
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM queue_entries").fetchone()[0] <= 1
        admission = conn.execute("SELECT actor_id,request_id FROM audio_admissions").fetchone()
        assert tuple(admission) == ("20", "replay-video")

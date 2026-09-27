from dataclasses import replace

import pytest

from changgeun.application.executor import Executor
from changgeun.application.undo import prepare
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.storage.database import Database


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "undo.db")
    db.ensure_guild("1")
    actor = Actor("1", "10", frozenset({"dj"}), "text", "voice", "voice")
    executor = Executor(
        db, Policy(frozenset({"1"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"}))
    )
    track = executor.execute(
        ActionPlan(
            "track",
            "1",
            "10",
            Action.CATALOG_REGISTER,
            {"source_type": "approved_audio", "external_id": "tone", "title": "시험음"},
        ),
        actor,
    )["track_id"]
    playlist = executor.execute(
        ActionPlan("list", "1", "10", Action.PLAYLIST_CREATE, {"name": "목록"}), actor
    )["playlist_id"]
    return db, actor, executor, track, playlist


def edit(env, action=Action.PLAYLIST_ADD, request="edit", versions=None, args=None):
    db, actor, executor, track, playlist = env
    executor.execute(
        ActionPlan(
            request,
            "1",
            "10",
            action,
            args if args is not None else {"playlist_id": playlist, "track_ids": [track]},
            versions if versions is not None else {playlist: 0},
        ),
        actor,
    )
    with db.transaction() as conn:
        return conn.execute(
            "SELECT id FROM change_events WHERE request_id=?", (request,)
        ).fetchone()[0]


def undo_plan(env, event):
    with env[0].transaction() as conn:
        target, version = prepare(conn, "1", event)
    return ActionPlan("undo", "1", "10", Action.EDIT_UNDO, {"event_id": event}, {target: version})


def test_undo_is_confirmed_once_audited_and_version_monotonic(env):
    db, actor, executor, _, playlist = env
    event = edit(env)
    plan = undo_plan(env, event)
    with pytest.raises(DomainError, match="confirmation_required"):
        executor.execute(plan, actor)
    token = executor.preview(plan, actor)
    result = executor.execute(plan, actor, confirmation=token)
    assert executor.execute(plan, actor, confirmation=token) == result
    assert result["version"] == 2
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 0
        assert (
            conn.execute("SELECT version FROM playlists WHERE id=?", (playlist,)).fetchone()[0] == 2
        )
        assert conn.execute("SELECT COUNT(*) FROM edit_undos").fetchone()[0] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM change_events WHERE action='edit.undo'").fetchone()[
                0
            ]
            == 1
        )
    with pytest.raises(DomainError, match="undo_already_used"):
        executor.preview(replace(plan, request_id="another-undo"), actor)


def test_other_dj_edit_after_preview_blocks_undo_without_losing_entries(env):
    db, actor, executor, _, playlist = env
    plan = undo_plan(env, edit(env))
    token = executor.preview(plan, actor)
    executor.execute(
        ActionPlan(
            "other",
            "1",
            "20",
            Action.PLAYLIST_RENAME,
            {"playlist_id": playlist, "name": "다른 DJ 이름"},
            {playlist: 1},
        ),
        replace(actor, user_id="20"),
    )
    with pytest.raises(DomainError, match="undo_version_conflict"):
        executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM edit_undos").fetchone()[0] == 0


def test_queue_undo_requires_same_voice_and_never_rewinds_session(env):
    db, actor, executor, track, _ = env
    event = edit(env, Action.QUEUE_ENQUEUE, versions={"queue": 0}, args={"track_ids": [track]})
    plan = undo_plan(env, event)
    with pytest.raises(DomainError, match="same_voice_required"):
        executor.preview(plan, replace(actor, voice_channel_id=None))
    token = executor.preview(plan, actor)
    with db.transaction() as conn:
        conn.execute("UPDATE sessions SET generation=generation+1 WHERE guild_id='1'")
    with pytest.raises(DomainError, match="undo_version_conflict"):
        executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM queue_entries").fetchone()[0] == 1


def test_unrelated_playlist_edit_is_preserved(env):
    db, actor, executor, _, playlist = env
    plan = undo_plan(env, edit(env))
    token = executor.preview(plan, actor)
    other = executor.execute(
        ActionPlan("other", "1", "10", Action.PLAYLIST_CREATE, {"name": "다른 목록"}), actor
    )["playlist_id"]
    executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM playlists WHERE id=?", (other,)).fetchone()[0] == 1
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM playlists WHERE id=?", (playlist,)).fetchone()[0]
            == 1
        )


def test_role_revocation_blocks_confirmation(env):
    plan = undo_plan(env, edit(env))
    token = env[2].preview(plan, env[1])
    with pytest.raises(DomainError, match="dj_required"):
        env[2].execute(plan, replace(env[1], role_ids=frozenset()), confirmation=token)


def test_external_playback_and_created_list_are_not_undoable(env):
    with env[0].transaction() as conn:
        event = conn.execute("SELECT id FROM change_events WHERE request_id='list'").fetchone()[0]
    with pytest.raises(DomainError, match="undo_not_supported"):
        undo_plan(env, event)


def test_queue_undo_restores_only_pending_entries_with_new_version(env):
    db, actor, executor, track, _ = env
    event = edit(env, Action.QUEUE_ENQUEUE, versions={"queue": 0}, args={"track_ids": [track]})
    plan = undo_plan(env, event)
    result = executor.execute(plan, actor, confirmation=executor.preview(plan, actor))
    assert result["target"] == "queue" and result["version"] == 2
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM queue_entries").fetchone()[0] == 0
        session = conn.execute(
            "SELECT desired_state,current_track_id,generation FROM sessions"
        ).fetchone()
        assert tuple(session) == ("disconnected", None, 0)


def test_undo_restores_deleted_entry_ids_and_order(env):
    db, actor, executor, _, playlist = env
    edit(env)
    with db.transaction() as conn:
        original = dict(conn.execute("SELECT * FROM playlist_entries").fetchone())
    event = edit(
        env,
        Action.PLAYLIST_REMOVE,
        request="remove",
        versions={playlist: 1},
        args={"playlist_id": playlist, "entry_id": original["id"]},
    )
    plan = undo_plan(env, event)
    executor.execute(plan, actor, confirmation=executor.preview(plan, actor))
    with db.transaction() as conn:
        assert dict(conn.execute("SELECT * FROM playlist_entries").fetchone()) == original


def test_undo_failure_rolls_back_token_inverse_and_audit(env):
    db, actor, executor, _, _ = env
    plan = undo_plan(env, edit(env))
    token = executor.preview(plan, actor)

    def fail():
        raise RuntimeError("injected")

    executor.before_commit = fail
    with pytest.raises(RuntimeError, match="injected"):
        executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM edit_undos").fetchone()[0] == 0
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 0

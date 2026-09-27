from dataclasses import replace

import pytest

from changgeun.application.executor import Executor
from changgeun.application.generation import Rules, select
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.storage.database import Database


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "generation.db")
    db.ensure_guild("1")
    actor = Actor("1", "10", frozenset({"dj"}), "text")
    executor = Executor(
        db,
        Policy(frozenset({"1"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"})),
        clock=lambda: 1000000,
    )
    tracks = []
    for i in range(5):
        command = ActionPlan(
            f"register-{i}",
            "1",
            "10",
            Action.CATALOG_REGISTER,
            {
                "source_type": "approved_audio",
                "external_id": str(i),
                "title": f"곡{i}",
                "metadata": {"duration_seconds": 120 if i < 4 else None},
            },
        )
        track = executor.execute(command, actor)["track_id"]
        executor.execute(
            ActionPlan(
                f"tag-{i}",
                "1",
                "10",
                Action.CATALOG_ANNOTATE,
                {
                    "track_id": track,
                    "tags": ["새벽"] if i != 3 else ["강한 곡"],
                    "aliases": [],
                    "creator": "제작자",
                },
            ),
            actor,
        )
        tracks.append(track)
    return db, actor, executor, tracks


def generated_plan(env, rules=None):
    rules = Rules(count=3, seed=7) if rules is None else rules
    db, actor, _, _ = env
    conn = db.connect()
    try:
        result = select(conn, "1", rules, 1000000)
    finally:
        conn.close()
    return ActionPlan(
        "generate",
        "1",
        actor.user_id,
        Action.PLAYLIST_GENERATE,
        {
            "name": "새 목록",
            "rules": rules.serialize(),
            "track_ids": result.track_ids,
            "snapshot_hash": result.snapshot_hash,
            "reference_time": 1000000,
        },
    )


def test_same_snapshot_seed_and_rules_have_identical_selection(env):
    rules = Rules(include_tags=("새벽",), count=3, max_seconds=240, seed=11)
    conn = env[0].connect()
    try:
        first = select(conn, "1", rules, 1000000)
        assert first == select(conn, "1", rules, 1000000)
    finally:
        conn.close()
    assert len(first.track_ids) == 2
    assert first.known_seconds == 240 and first.unknown_durations == 0
    assert env[3][3] not in first.track_ids and env[3][4] not in first.track_ids


def test_recent_history_excludes_only_actual_recent_tracks(env):
    db, _, _, tracks = env
    with db.transaction() as conn:
        conn.execute("INSERT INTO playback_history VALUES('1','recent',?,?)", (tracks[0], 999999))
        conn.execute("INSERT INTO playback_history VALUES('1','old',?,?)", (tracks[1], 1))
        result = select(conn, "1", Rules(count=100), 1000000)
    assert tracks[0] not in result.track_ids and tracks[1] in result.track_ids
    assert len(result.track_ids) == 4


def test_small_generation_requires_confirmation_and_does_not_invent_shortage(env):
    db, actor, executor, _ = env
    command = generated_plan(env, Rules(include_tags=("새벽",), count=20))
    with pytest.raises(DomainError, match="confirmation_required"):
        executor.execute(command, actor)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0
    token = executor.preview(command, actor)
    result = executor.execute(command, actor, confirmation=token)
    assert result["count"] == 4
    assert executor.execute(command, actor, confirmation=token) == result
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 4


def test_annotation_change_after_preview_rejects_entire_generation(env):
    db, actor, executor, tracks = env
    command = generated_plan(env)
    token = executor.preview(command, actor)
    executor.execute(
        ActionPlan(
            "retag",
            "1",
            "10",
            Action.CATALOG_ANNOTATE,
            {"track_id": tracks[0], "aliases": [], "tags": ["새 표기"]},
        ),
        actor,
    )
    with pytest.raises(DomainError, match="generation_snapshot_conflict"):
        executor.execute(command, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0] == 0


def test_changed_selection_and_non_dj_are_rejected(env):
    command = generated_plan(env)
    with pytest.raises(DomainError, match="generation_snapshot_conflict"):
        env[2].preview(replace(command, arguments={**command.arguments, "track_ids": []}), env[1])
    with pytest.raises(DomainError, match="dj_required"):
        env[2].preview(command, replace(env[1], role_ids=frozenset()))


@pytest.mark.parametrize(
    "changes",
    [
        {"count": 0},
        {"count": 101},
        {"count": True},
        {"recent_days": -1},
        {"seed": True},
        {"max_seconds": 0},
        {"include_tags": ("",)},
    ],
)
def test_generation_limits_are_closed(changes):
    with pytest.raises(DomainError):
        replace(Rules(), **changes).validate()

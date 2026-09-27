import json
from dataclasses import replace

import pytest

from changgeun.application.executor import Executor
from changgeun.application.transfer import parse_export
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.storage.database import Database


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "transfer.db")
    db.ensure_guild("1")
    actor = Actor("1", "10", frozenset({"dj"}), "text")
    executor = Executor(
        db, Policy(frozenset({"1"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"}))
    )
    return db, actor, executor


def command(references, **changes):
    return ActionPlan(
        "import",
        "1",
        "10",
        Action.PLAYLIST_IMPORT,
        {
            "name": "가져온 목록",
            "references": references,
            "complete": True,
            "unavailable_count": 0,
            "accept_partial": False,
            **changes,
        },
    )


def reference(identifier="ABCDEFGHIJK", source="youtube"):
    return {
        "source_type": source,
        "external_id": identifier,
        "title": "참조 곡",
        "annotations": {"tags": ["새벽"], "aliases": ["별칭"], "creator": "제작자"},
    }


def confirmed(env, plan):
    _, actor, executor = env
    return executor.execute(plan, actor, confirmation=executor.preview(plan, actor))


def test_import_always_confirms_and_export_roundtrips_without_private_fields(env):
    db, actor, executor = env
    plan = command([reference()])
    with pytest.raises(DomainError, match="confirmation_required"):
        executor.execute(plan, actor)
    result = confirmed(env, plan)
    exported = executor.execute(
        ActionPlan(
            "export", "1", "10", Action.PLAYLIST_EXPORT, {"playlist_id": result["playlist_id"]}
        ),
        actor,
    )
    assert parse_export(json.dumps(exported).encode()) == [reference()]
    assert set(exported) == {"schema_version", "tracks"}
    assert executor.execute(plan, actor) == result
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 1


def test_partial_import_requires_explicit_consent_and_still_confirms(env):
    partial = command([reference()], complete=False, unavailable_count=2)
    with pytest.raises(DomainError, match="partial_import_requires_consent"):
        env[2].preview(partial, env[1])
    plan = replace(partial, arguments={**partial.arguments, "accept_partial": True})
    result = confirmed(env, plan)
    assert not result["complete"] and result["unavailable_count"] == 2


def test_duplicate_references_are_skipped_or_kept_only_when_requested(env):
    result = confirmed(env, command([reference(), reference()]))
    assert result["count"] == 1 and result["duplicate_references"] == 1
    other = replace(
        command([reference(), reference()], name="중복 보존", allow_duplicates=True),
        request_id="other",
    )
    assert confirmed(env, other)["count"] == 2


def test_unapproved_audio_rolls_back_entire_catalog_and_list(env):
    plan = command([reference(), reference("unregistered", "approved_audio")])
    token = env[2].preview(plan, env[1])
    with pytest.raises(DomainError, match="audio_source_not_approved"):
        env[2].execute(plan, env[1], confirmation=token)
    with env[0].transaction() as conn:
        for table in (
            "tracks",
            "playlists",
            "playlist_entries",
            "change_events",
            "command_requests",
        ):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_replace_rechecks_current_version_and_preserves_list_on_conflict(env):
    db, actor, executor = env
    identifier = confirmed(env, command([reference()]))["playlist_id"]
    plan = replace(
        command([reference("LMNOPQRSTUV")], playlist_id=identifier, replace=True),
        request_id="replace",
        expected_versions={identifier: 0},
    )
    token = executor.preview(plan, actor)
    executor.execute(
        ActionPlan(
            "rename",
            "1",
            "10",
            Action.PLAYLIST_RENAME,
            {"playlist_id": identifier, "name": "바뀐 목록"},
            {identifier: 0},
        ),
        actor,
    )
    with pytest.raises(DomainError, match="version_conflict"):
        executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM playlist_entries").fetchone()[0] == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"path": "/private/audio.wav"},
        {"token": "synthetic-secret"},
        {"guild_id": "1"},
        {"url": "https://untrusted.invalid"},
    ],
)
def test_portable_import_rejects_environment_and_credentials(extra):
    payload = {"schema_version": 1, "tracks": [{**reference(), **extra}]}
    with pytest.raises(DomainError, match="invalid_import_references"):
        parse_export(json.dumps(payload).encode())


def test_injected_failure_preserves_confirmation_and_rolls_back_all_changes(env):
    db, actor, executor = env
    plan = command([reference()])
    token = executor.preview(plan, actor)

    def fail():
        raise RuntimeError("injected")

    executor.before_commit = fail
    with pytest.raises(RuntimeError, match="injected"):
        executor.execute(plan, actor, confirmation=token)
    with db.transaction() as conn:
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
    executor.before_commit = None
    assert executor.execute(plan, actor, confirmation=token)["count"] == 1


def test_official_metadata_is_saved_atomically_and_not_accepted_from_portable_file(env):
    plan = command(
        [reference()],
        source_metadata={"ABCDEFGHIJK": {"source_author": "공식 출처", "duration_seconds": 123}},
    )
    confirmed(env, plan)
    with env[0].transaction() as conn:
        row = conn.execute("SELECT metadata_json,metadata_updated_at FROM tracks").fetchone()
        assert json.loads(row[0])["duration_seconds"] == 123 and row[1] > 0
    payload = {
        "schema_version": 1,
        "tracks": [
            {
                **reference(),
                "source_metadata": {"source_author": "임의 출처", "duration_seconds": 123},
            }
        ],
    }
    with pytest.raises(DomainError, match="invalid_import_references"):
        parse_export(json.dumps(payload).encode())


@pytest.mark.parametrize(
    "metadata",
    [
        {"outside": {"source_author": "출처", "duration_seconds": 1}},
        {"ABCDEFGHIJK": {"source_author": "출처", "duration_seconds": True}},
        {"ABCDEFGHIJK": {"source_author": "출처", "duration_seconds": 1, "url": "private"}},
    ],
)
def test_import_metadata_is_closed_and_bound_to_references(env, metadata):
    with pytest.raises(DomainError, match="invalid_import_metadata"):
        env[2].preview(command([reference()], source_metadata=metadata), env[1])

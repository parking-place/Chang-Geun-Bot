import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from changgeun.storage.database import Database

spec = importlib.util.spec_from_file_location(
    "backup_runtime", Path(__file__).resolve().parents[2] / "scripts/backup_runtime.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
BINDING = {"provider": "jev-api", "profile_id": "test-jev-api", "config_hash": "a" * 64}


@pytest.fixture
def snapshot(tmp_path):
    db = Database(tmp_path / "source.db")
    db.ensure_guild("1")
    with db.transaction() as conn:
        conn.execute("INSERT INTO confirmations VALUES('hash','1','10','plan',99999999999,0)")
        conn.execute(
            "UPDATE sessions SET desired_state='playing',voice_channel_id='4',"
            "generation=2,start_after_connect=1"
        )
    target = tmp_path / "snapshot"
    backup.snapshot(target, "bot", {"bot.db": db.path}, BINDING)
    return db, target


def test_live_snapshot_is_consistent_and_restores_without_autoplay_or_tokens(snapshot, tmp_path):
    original, source = snapshot
    with original.transaction() as conn:
        conn.execute("UPDATE sessions SET volume=60")
    result = backup.restore(source, tmp_path / "restored", BINDING)
    assert result["integrity"] == "PASS" and result["automatic_playback"] is False
    with sqlite3.connect(tmp_path / "restored/bot.db") as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 1
        session = conn.execute(
            "SELECT desired_state,voice_channel_id,generation,start_after_connect,volume "
            "FROM sessions"
        ).fetchone()
        assert session == ("disconnected", None, 3, 0, 30)
    with original.transaction() as conn:
        assert conn.execute("SELECT consumed FROM confirmations").fetchone()[0] == 0
        assert conn.execute("SELECT volume FROM sessions").fetchone()[0] == 60
    assert (tmp_path / "restored/bot.db").stat().st_mode & 0o077 == 0


def test_restore_refuses_existing_path_and_wrong_profile(snapshot, tmp_path):
    db, source = snapshot
    with pytest.raises(ValueError, match="new isolated"):
        backup.restore(source, db.path.parent, BINDING)
    with pytest.raises(ValueError, match="invalid backup binding"):
        backup.restore(source, tmp_path / "wrong", {**BINDING, "provider": "local-openjev"})
    with pytest.raises(ValueError, match="binding mismatch"):
        backup.restore(source, tmp_path / "other-run", {**BINDING, "profile_id": "other"})
    assert not (tmp_path / "wrong").exists()


def test_corrupt_file_fails_before_creating_restore_destination(snapshot, tmp_path):
    _, source = snapshot
    with (source / "bot.db").open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="checksum mismatch"):
        backup.restore(source, tmp_path / "restore", BINDING)
    assert not (tmp_path / "restore").exists()


def test_manifest_has_no_secret_paths_or_environment(snapshot):
    _, source = snapshot
    manifest = json.loads((source / "manifest.json").read_text())
    assert set(manifest) == {
        "format",
        "component",
        "api_schema_version",
        "binding",
        "created_at",
        "files",
    }
    assert set(manifest["files"]) == {"bot.db"}
    assert "token" not in json.dumps(manifest) and "source.db" not in json.dumps(manifest)

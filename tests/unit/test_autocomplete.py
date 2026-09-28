import json

from changgeun.discord_adapter.autocomplete import catalog_choices
from changgeun.storage.database import Database


def test_catalog_choices_are_guild_scoped_local_and_use_stable_ids(tmp_path):
    db = Database(tmp_path / "bot.db")
    db.ensure_guild("1")
    db.ensure_guild("2")
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
            ("1", "playlist-one", "새벽 작업곡", "새벽 작업곡"),
        )
        conn.execute(
            "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
            ("2", "private", "비밀 목록", "비밀 목록"),
        )
        conn.execute(
            "INSERT INTO playlists(guild_id,id,name,normalized_name,deleted_at) "
            "VALUES(?,?,?,?,?)",
            ("1", "deleted", "삭제 목록", "삭제 목록", 1),
        )
        conn.execute(
            "INSERT INTO tracks(guild_id,id,source_type,external_id,title,annotations_json) "
            "VALUES(?,?,?,?,?,?)",
            (
                "1",
                "track-one",
                "approved_audio",
                "one",
                "곡 제목",
                json.dumps({"aliases": ["별칭"]}),
            ),
        )
    assert catalog_choices(db, "1", "새벽", "playlist") == [
        ("새벽 작업곡", "playlist-one")
    ]
    assert catalog_choices(db, "1", "비밀", "playlist") == []
    assert catalog_choices(db, "1", "삭제", "playlist") == []
    assert catalog_choices(db, "1", "별칭", "track") == [("곡 제목", "track-one")]
    assert catalog_choices(db, "1", "x" * 101, "track") == []

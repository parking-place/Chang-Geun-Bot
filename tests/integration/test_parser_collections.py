from types import SimpleNamespace

import pytest

from changgeun.domain.models import Actor, Policy
from changgeun.parser.collections import (
    CollectionItem,
    SqliteCollections,
    discord_items,
    resolve_collection,
    snapshot,
)
from changgeun.parser.contracts import ParseError
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.storage.database import Database


def actor(guild='g'):
    return Actor(guild, 'u', frozenset({'dj'}), 'text')


def policy():
    return Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(), frozenset())


def spec(collection, argument='목록'):
    arg = ArgumentSpec(argument, 'string', True, source='collection', collection=collection)
    return CommandSpec('C03', 'test', 'test', (arg,), 'dj', 'read'), arg


def test_full_guild_list_opaque_tokens_and_revision(tmp_path):
    db = Database(tmp_path / 'catalog.sqlite')
    db.ensure_guild('g')
    db.ensure_guild('other')
    with db.transaction() as conn:
        for index in range(25):
            conn.execute('INSERT INTO playlists(guild_id,id,name,normalized_name) '
                         'VALUES(?,?,?,?)', ('g', f'p{index}', f'이름{index}', f'n{index}'))
        conn.execute('INSERT INTO playlists(guild_id,id,name,normalized_name) '
                     'VALUES(?,?,?,?)', ('other', 'secret', '비공개', 'secret'))
    command, arg = spec('playlists')
    first = resolve_collection(command, arg, actor(), policy(), db, root_id='root',
                               pass_id='initial', scope_hash='scope')
    assert first.complete and first.original_count == first.delivered_count == 25
    assert len(first.criteria()) == 28
    assert '비공개' not in repr(first.criteria())
    assert not set(first.criteria()).intersection({f'p{i}' for i in range(25)})
    selected = first.selections[-1]
    chosen = first.select(selected.token, root_id='root', pass_id='initial',
                          argument='목록', scope_hash='scope', revision=first.revision)
    assert chosen == selected.item
    with pytest.raises(ParseError, match='stale_collection'):
        first.select(selected.token, root_id='root', pass_id='after_rewrite',
                     argument='목록', scope_hash='scope', revision=first.revision)
    second = resolve_collection(command, arg, actor(), policy(), db, root_id='root',
                                pass_id='after_rewrite', scope_hash='scope')
    with pytest.raises(ParseError, match='foreign_selection'):
        second.select(selected.token, root_id='root', pass_id='after_rewrite',
                      argument='목록', scope_hash='scope', revision=second.revision)
    with db.transaction() as conn:
        conn.execute("UPDATE playlists SET version=1 WHERE guild_id='g' AND id='p0'")
    changed = SqliteCollections(db).items('playlists', 'g')
    assert snapshot(changed, collection_key='playlists', root_id='root', pass_id='initial',
                    argument='목록', scope_hash='scope').revision != first.revision


def test_overflow_and_empty_are_distinct_without_partial_delivery():
    binding = dict(collection_key='tracks', root_id='root', pass_id='initial',
                   argument='곡', scope_hash='scope')
    boundary = snapshot([CollectionItem(str(i), f'곡 {i}') for i in range(252)], **binding)
    assert len(boundary.criteria()) == 255
    with pytest.raises(ParseError, match='collection_overflow'):
        snapshot([CollectionItem(str(i), str(i)) for i in range(253)], **binding)
    with pytest.raises(ParseError, match='collection_overflow'):
        snapshot([CollectionItem('id', 'long name')], max_bytes=20, **binding)
    empty = snapshot([], **binding)
    assert empty.complete and empty.original_count == 0
    with pytest.raises(ParseError, match='collection_empty'):
        empty.criteria()
    with pytest.raises(ParseError, match='duplicate_collection_id'):
        snapshot([CollectionItem('id', 'a'), CollectionItem('id', 'b')], **binding)


def test_duplicate_tracks_are_distinct_entries_and_parent_is_required(tmp_path):
    db = Database(tmp_path / 'entries.sqlite')
    db.ensure_guild('g')
    with db.transaction() as conn:
        conn.execute("INSERT INTO tracks(guild_id,id,source_type,external_id,title) "
                     "VALUES('g','t','approved','t','RED')")
        conn.execute("INSERT INTO playlists(guild_id,id,name,normalized_name) "
                     "VALUES('g','p','운동','운동')")
        for index in range(2):
            conn.execute('INSERT INTO playlist_entries VALUES(?,?,?,?,?)',
                         ('g', 'p', f'e{index}', 't', index))
    with pytest.raises(ParseError, match='collection_scope_required'):
        SqliteCollections(db).items('playlist_entries', 'g')
    items = SqliteCollections(db).items('playlist_entries', 'g', parent_id='p')
    assert len(items) == 2 and {item.object_id for item in items} == {'e0', 'e1'}
    assert items[0].label == items[1].label == 'RED'
    assert [item.execution_value for item in items] == [1, 2]


def test_permission_revocation_and_channel_scope(tmp_path):
    db = Database(tmp_path / 'rights.sqlite')
    command, arg = spec('playlists')
    with pytest.raises(ParseError, match='command_not_allowed'):
        resolve_collection(command, arg, Actor('g', 'u', frozenset(), 'text'), policy(), db,
                           root_id='root', pass_id='initial', scope_hash='scope')
    member = SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=True))
    def channel(identifier, visible=True, connect=True):
        permissions = SimpleNamespace(view_channel=visible, send_messages=True, connect=connect)
        return SimpleNamespace(id=identifier, name=f'channel{identifier}', category=None,
                               permissions_for=lambda _member: permissions)
    guild = SimpleNamespace(id='g', text_channels=[channel(1), channel(2, False)],
                            voice_channels=[channel(3), channel(4, connect=False)])
    text_ids = [item.object_id for item in discord_items('text_channels', guild, member, policy())]
    voice_ids = [item.object_id for item in
                 discord_items('voice_channels', guild, member, policy())]
    assert text_ids == ['1']
    assert voice_ids == ['3']

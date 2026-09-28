"""Complete, permission-scoped actual lists for parser choice questions."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any

from changgeun.domain.models import Actor, Policy
from changgeun.parser.contracts import ParseError
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.storage.database import Database

SENTINELS = {"__MISSING__": "언급 없음", "__NO_MATCH__": "일치 없음",
             "__AMBIGUOUS__": "여러 항목"}
MAX_ITEMS = 255 - len(SENTINELS)


@dataclass(frozen=True)
class CollectionItem:
    object_id: str
    label: str
    detail: str = ""
    aliases: tuple[str, ...] = ()
    version: str = ""
    execution_value: str | int | None = None


@dataclass(frozen=True)
class Selection:
    token: str
    item: CollectionItem


@dataclass(frozen=True)
class CollectionSnapshot:
    snapshot_id: str
    collection_key: str
    root_id: str
    pass_id: str
    argument: str
    scope_hash: str
    revision: str
    original_count: int
    delivered_count: int
    complete: bool
    selections: tuple[Selection, ...]

    def criteria(self) -> dict[str, str]:
        if not self.complete or not self.selections:
            raise ParseError("collection_unavailable" if not self.complete else "collection_empty")
        return {**{entry.token: _description(entry.item) for entry in self.selections},
                **SENTINELS}

    def select(self, token: str, *, root_id: str, pass_id: str, argument: str,
               scope_hash: str, revision: str) -> CollectionItem:
        if (not self.complete or root_id != self.root_id or pass_id != self.pass_id
                or argument != self.argument or scope_hash != self.scope_hash
                or revision != self.revision):
            raise ParseError("stale_collection")
        if token in SENTINELS:
            raise ParseError("selection_sentinel")
        matches = [entry.item for entry in self.selections if entry.token == token]
        if len(matches) != 1:
            raise ParseError("foreign_selection")
        return matches[0]


def _description(item: CollectionItem) -> str:
    result = item.label
    if item.detail:
        result += f" · {item.detail}"
    if item.aliases:
        result += " · 별칭 " + ", ".join(item.aliases)
    return result


def _revision(items: list[CollectionItem]) -> str:
    return hashlib.sha256(json.dumps(
        [(row.object_id, row.label, row.detail, row.aliases, row.version,
          row.execution_value)
         for row in items], ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()


def snapshot(
    items: list[CollectionItem], *, collection_key: str, root_id: str,
    pass_id: str, argument: str, scope_hash: str, max_items: int = MAX_ITEMS,
    max_bytes: int = 150_000,
) -> CollectionSnapshot:
    """Reject overflow before asking a model; never send a partial list."""
    if not all((collection_key, root_id, pass_id, argument, scope_hash)):
        raise ParseError("invalid_collection_binding")
    if len(items) > min(max_items, MAX_ITEMS):
        raise ParseError("collection_overflow")
    if len({item.object_id for item in items}) != len(items):
        raise ParseError("duplicate_collection_id")
    if any(not item.object_id or not item.label or len(_description(item)) > 1000
           for item in items):
        raise ParseError("invalid_collection_item")
    ordered = sorted(items, key=lambda row: (row.label.casefold(), row.object_id))
    selections = tuple(Selection("s_" + secrets.token_urlsafe(15), item)
                       for item in ordered)
    criteria = {**{entry.token: _description(entry.item) for entry in selections},
                **SENTINELS}
    if len(json.dumps(criteria, ensure_ascii=False).encode()) > max_bytes:
        raise ParseError("collection_overflow")
    return CollectionSnapshot(
        secrets.token_urlsafe(18), collection_key, root_id, pass_id, argument,
        scope_hash, _revision(ordered), len(ordered), len(selections), True, selections,
    )


class SqliteCollections:
    """Read a single guild's entire list in one SQLite snapshot."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def items(self, collection: str, guild_id: str, *, parent_id: str | None = None
              ) -> list[CollectionItem]:
        if collection in {"playlist_entries"} and not parent_id:
            raise ParseError("collection_scope_required")
        statements = {
            "playlists": ("SELECT id,name,version FROM playlists WHERE guild_id=? "
                          "AND deleted_at IS NULL ORDER BY name,id", (guild_id,)),
            "tracks": ("SELECT id,title,annotations_json,metadata_updated_at "
                       "FROM tracks WHERE guild_id=? ORDER BY title,id", (guild_id,)),
            "playlist_entries": (
                "SELECT e.id,e.position,t.title,p.version FROM playlist_entries e "
                "JOIN tracks t ON t.guild_id=e.guild_id AND t.id=e.track_id "
                "JOIN playlists p ON p.guild_id=e.guild_id AND p.id=e.playlist_id "
                "WHERE e.guild_id=? AND e.playlist_id=? AND p.deleted_at IS NULL "
                "ORDER BY e.position,e.id", (guild_id, parent_id)),
            "queue_entries": (
                "SELECT e.id,e.position,t.title,s.generation FROM queue_entries e "
                "JOIN tracks t ON t.guild_id=e.guild_id AND t.id=e.track_id "
                "JOIN sessions s ON s.guild_id=e.guild_id WHERE e.guild_id=? "
                "ORDER BY e.position,e.id", (guild_id,)),
            "proposals": (
                "SELECT p.id,p.status,t.title FROM proposals p "
                "JOIN tracks t ON t.guild_id=p.guild_id AND t.id=p.track_id "
                "WHERE p.guild_id=? ORDER BY p.created_at,p.id", (guild_id,)),
            "changes": (
                "SELECT id,action,created_at FROM change_events WHERE guild_id=? "
                "ORDER BY created_at,id", (guild_id,)),
        }
        if collection not in statements:
            raise ParseError("unsupported_collection")
        statement, arguments = statements[collection]
        conn = self.db.connect()
        try:
            conn.execute("BEGIN")
            rows = conn.execute(statement, arguments).fetchall()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise ParseError("collection_fetch_failed") from exc
        finally:
            conn.close()
        result = []
        for row in rows:
            aliases: tuple[str, ...] = ()
            if collection == "tracks":
                try:
                    data = json.loads(row["annotations_json"])
                    aliases = tuple(v for v in data.get("aliases", ())
                                    if isinstance(v, str) and v)
                except (ValueError, TypeError, AttributeError) as exc:
                    raise ParseError("collection_fetch_failed") from exc
                label, detail, version = str(row["title"]), "곡", str(row["metadata_updated_at"])
            elif collection == "playlists":
                label, detail, version = str(row["name"]), "재생목록", str(row["version"])
            elif collection in {"playlist_entries", "queue_entries"}:
                label = str(row["title"])
                detail = f"{int(row['position']) + 1}번 · {collection}"
                version = str(row["version"] if collection == "playlist_entries" else
                              row["generation"])
            elif collection == "proposals":
                label, detail, version = str(row["title"]), str(row["status"]), ""
            else:
                label, detail, version = str(row["action"]), str(row["created_at"]), ""
            execution_value = (int(row["position"]) + 1
                               if collection in {"playlist_entries", "queue_entries"} else None)
            result.append(CollectionItem(str(row["id"]), label, detail, aliases,
                                         version, execution_value))
        return result


def discord_items(collection: str, guild: Any, member: Any,
                  policy: Policy) -> list[CollectionItem]:
    """Use Discord's current permission snapshot, never global channel inventory."""
    if guild is None or member is None:
        raise ParseError("collection_scope_required")
    if collection not in {"text_channels", "watched_channels", "voice_channels"}:
        raise ParseError("unsupported_collection")
    if collection == "watched_channels" and not member.guild_permissions.manage_guild:
        raise ParseError("command_not_allowed")
    channels = guild.voice_channels if collection == "voice_channels" else guild.text_channels
    result = []
    for channel in channels:
        rights = channel.permissions_for(member)
        allowed = (rights.view_channel and rights.connect if collection == "voice_channels"
                   else rights.view_channel and rights.send_messages)
        if not allowed:
            continue
        if collection == "voice_channels" and policy.voice_channel_ids and (
            str(channel.id) not in policy.voice_channel_ids
        ):
            continue
        result.append(CollectionItem(str(channel.id), str(channel.name),
                                     str(getattr(channel.category, "name", "") or "")))
    return result


def resolve_collection(
    spec: CommandSpec, argument: ArgumentSpec, actor: Actor, policy: Policy,
    db: Database, *, root_id: str, pass_id: str, scope_hash: str,
    parent_id: str | None = None, guild: Any = None, member: Any = None,
) -> CollectionSnapshot:
    if actor.guild_id not in policy.guild_ids or not spec.allowed(actor, policy):
        raise ParseError("command_not_allowed")
    if argument.collection is None:
        raise ParseError("unsupported_collection")
    if argument.collection in {"text_channels", "voice_channels", "watched_channels"}:
        if guild is None or str(guild.id) != actor.guild_id:
            raise ParseError("collection_scope_required")
        items = discord_items(argument.collection, guild, member, policy)
    else:
        items = SqliteCollections(db).items(argument.collection, actor.guild_id,
                                            parent_id=parent_id)
    return snapshot(items, collection_key=argument.collection, root_id=root_id,
                    pass_id=pass_id, argument=argument.name, scope_hash=scope_hash)

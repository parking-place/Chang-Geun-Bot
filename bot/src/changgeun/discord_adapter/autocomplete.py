"""Bounded, guild-scoped slash choices from the local catalog only."""

from __future__ import annotations

import json
import unicodedata

from changgeun.domain.models import DomainError, normalized_name
from changgeun.storage.database import Database


def catalog_choices(
    db: Database, guild: str, current: str, kind: str
) -> list[tuple[str, str]]:
    if kind not in {"playlist", "track"} or len(current) > 100:
        return []
    needle = " ".join(unicodedata.normalize("NFKC", current).casefold().split())
    conn = db.connect()
    try:
        if kind == "playlist":
            rows = conn.execute(
                "SELECT id,name FROM playlists WHERE guild_id=? AND deleted_at IS NULL",
                (guild,),
            ).fetchall()
            values: list[tuple[str, str, list[str]]] = [
                (str(row["id"]), str(row["name"]), []) for row in rows
            ]
        else:
            rows = conn.execute(
                "SELECT id,title,annotations_json FROM tracks WHERE guild_id=?", (guild,)
            ).fetchall()
            values = [
                (
                    str(row["id"]),
                    str(row["title"]),
                    json.loads(row["annotations_json"]).get("aliases", []),
                )
                for row in rows
            ]
    finally:
        conn.close()
    ranked: list[tuple[int, str, str]] = []
    for identifier, title, aliases in values:
        try:
            names = [normalized_name(title)] + [
                normalized_name(alias)
                for alias in aliases
                if isinstance(alias, str) and 1 <= len(alias) <= 100
            ]
        except (DomainError, ValueError, TypeError):
            continue
        if not needle or any(needle in name for name in names):
            rank = 0 if needle in names else 1 if any(
                name.startswith(needle) for name in names
            ) else 2
            ranked.append((rank, title, identifier))
    ranked.sort(key=lambda item: (item[0], item[1].casefold(), item[2]))
    return [(title[:100], identifier) for _, title, identifier in ranked[:25]]

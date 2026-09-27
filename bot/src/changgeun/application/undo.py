"""Reverse one unchanged playlist/queue edit; never rewind playback or catalog."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from changgeun.domain.models import Action, ActionPlan, DomainError

PLAYLIST_EDITS = frozenset(
    {
        Action.PLAYLIST_RENAME,
        Action.PLAYLIST_ADD,
        Action.PLAYLIST_REMOVE,
        Action.PLAYLIST_MOVE,
        Action.PLAYLIST_DELETE,
        Action.PLAYLIST_RESTORE,
    }
)
QUEUE_EDITS = frozenset(
    {Action.QUEUE_ENQUEUE, Action.QUEUE_REMOVE, Action.QUEUE_MOVE, Action.QUEUE_CLEAR}
)


def prepare(conn: sqlite3.Connection, guild: str, event_id: str) -> tuple[str, int]:
    _, before, after, queue = read_event(conn, guild, event_id)
    if queue:
        return "queue", after["sessions"][0]["version"]
    previous = {row["id"]: row for row in before["playlists"]}
    changed = [row for row in after["playlists"] if previous.get(row["id"]) != row]
    if len(changed) != 1 or changed[0]["id"] not in previous:
        raise DomainError("undo_not_supported")
    return changed[0]["id"], changed[0]["version"]


def read_event(
    conn: sqlite3.Connection, guild: str, event_id: str
) -> tuple[sqlite3.Row, dict[str, Any], dict[str, Any], bool]:
    row = conn.execute(
        "SELECT * FROM change_events WHERE guild_id=? AND id=?", (guild, event_id)
    ).fetchone()
    if not row:
        raise DomainError("undo_not_found")
    if conn.execute(
        "SELECT 1 FROM edit_undos WHERE guild_id=? AND event_id=?", (guild, event_id)
    ).fetchone():
        raise DomainError("undo_already_used")
    action = Action(row["action"])
    if action not in PLAYLIST_EDITS | QUEUE_EDITS:
        raise DomainError("undo_not_supported")
    return row, json.loads(row["before_json"]), json.loads(row["after_json"]), action in QUEUE_EDITS


def check(conn: sqlite3.Connection, plan: ActionPlan) -> None:
    _, _, after, queue = read_event(conn, plan.guild_id, plan.arguments["event_id"])
    target, version = prepare(conn, plan.guild_id, plan.arguments["event_id"])
    if plan.expected_versions != {target: version}:
        raise DomainError("undo_version_conflict")
    if queue:
        session = conn.execute(
            "SELECT * FROM sessions WHERE guild_id=?", (plan.guild_id,)
        ).fetchone()
        if not session or dict(session) != after["sessions"][0]:
            raise DomainError("undo_version_conflict")
        current = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM queue_entries WHERE guild_id=?", (plan.guild_id,)
            )
        ]
        expected = after["queue_entries"]
    else:
        playlist = conn.execute(
            "SELECT * FROM playlists WHERE guild_id=? AND id=?", (plan.guild_id, target)
        ).fetchone()
        expected_playlist = next(row for row in after["playlists"] if row["id"] == target)
        if not playlist or dict(playlist) != expected_playlist:
            raise DomainError("undo_version_conflict")
        current = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM playlist_entries WHERE guild_id=? AND playlist_id=?",
                (plan.guild_id, target),
            )
        ]
        expected = [row for row in after["playlist_entries"] if row["playlist_id"] == target]
    if sorted(current, key=lambda row: row["id"]) != sorted(expected, key=lambda row: row["id"]):
        raise DomainError("undo_version_conflict")


def apply(conn: sqlite3.Connection, plan: ActionPlan, now: float) -> dict[str, Any]:
    check(conn, plan)
    _, before, _, queue = read_event(conn, plan.guild_id, plan.arguments["event_id"])
    target, version = prepare(conn, plan.guild_id, plan.arguments["event_id"])
    if queue:
        conn.execute("DELETE FROM queue_entries WHERE guild_id=?", (plan.guild_id,))
        for row in before["queue_entries"]:
            conn.execute(
                "INSERT INTO queue_entries VALUES(?,?,?,?)",
                tuple(row[key] for key in ("guild_id", "id", "track_id", "position")),
            )
        conn.execute("UPDATE sessions SET version=version+1 WHERE guild_id=?", (plan.guild_id,))
    else:
        previous = next(row for row in before["playlists"] if row["id"] == target)
        conn.execute(
            "UPDATE playlists SET name=?,normalized_name=?,deleted_at=?,version=version+1 "
            "WHERE guild_id=? AND id=?",
            (
                previous["name"],
                previous["normalized_name"],
                previous["deleted_at"],
                plan.guild_id,
                target,
            ),
        )
        conn.execute(
            "DELETE FROM playlist_entries WHERE guild_id=? AND playlist_id=?",
            (plan.guild_id, target),
        )
        for row in before["playlist_entries"]:
            if row["playlist_id"] == target:
                conn.execute(
                    "INSERT INTO playlist_entries VALUES(?,?,?,?,?)",
                    tuple(
                        row[key]
                        for key in ("guild_id", "playlist_id", "id", "track_id", "position")
                    ),
                )
    conn.execute(
        "INSERT INTO edit_undos VALUES(?,?,?,?)",
        (plan.guild_id, plan.arguments["event_id"], plan.request_id, now),
    )
    return {"undone_event": plan.arguments["event_id"], "target": target, "version": version + 1}

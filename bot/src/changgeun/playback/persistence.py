"""Desired-state transitions share the command transaction, not external audio IO."""

from __future__ import annotations

import sqlite3
from typing import Any

from changgeun.application.watch import admission_valid
from changgeun.domain.models import Action, ActionPlan, DomainError
from changgeun.playback.state import Entry, PlaybackState, Session


def load_session(conn: sqlite3.Connection, guild: str) -> Session:
    row = conn.execute("SELECT * FROM sessions WHERE guild_id=?", (guild,)).fetchone()
    if not row:
        raise DomainError("session_not_found")
    current = (
        Entry(row["current_entry_id"], row["current_track_id"]) if row["current_entry_id"] else None
    )
    queue = [
        Entry(r["id"], r["track_id"])
        for r in conn.execute(
            "SELECT * FROM queue_entries WHERE guild_id=? ORDER BY position", (guild,)
        )
    ]
    return Session(
        state=PlaybackState(row["desired_state"]),
        generation=row["generation"],
        version=row["version"],
        current=current,
        queue=queue,
        volume=row["volume"],
        repeat=row["repeat_mode"],
        failed_tracks=row["failed_tracks"],
        retry_count=row["retry_count"],
        eligible_ids=frozenset(
            e.id
            for e in queue + ([current] if current else [])
            if admission_valid(conn, guild, e.id)
        ),
    )


def save_session(conn: sqlite3.Connection, guild: str, session: Session) -> None:
    conn.execute(
        "UPDATE sessions SET desired_state=?,generation=?,version=?,current_entry_id=?,"
        "current_track_id=?,volume=?,repeat_mode=?,failed_tracks=?,retry_count=? "
        "WHERE guild_id=?",
        (
            session.state.value,
            session.generation,
            session.version,
            session.current.id if session.current else None,
            session.current.track_id if session.current else None,
            session.volume,
            session.repeat,
            session.failed_tracks,
            session.retry_count,
            guild,
        ),
    )
    if session.current and session.state == PlaybackState.RESOLVING:
        conn.execute(
            "UPDATE audio_admissions SET started=0 WHERE guild_id=? AND entry_id=?",
            (guild, session.current.id),
        )
    conn.execute("DELETE FROM queue_entries WHERE guild_id=?", (guild,))
    for position, entry in enumerate(session.queue):
        conn.execute(
            "INSERT INTO queue_entries VALUES(?,?,?,?)", (guild, entry.id, entry.track_id, position)
        )


def apply_playback(conn: sqlite3.Connection, plan: ActionPlan) -> dict[str, Any]:
    session = load_session(conn, plan.guild_id)
    action, args = plan.action, plan.arguments
    if action in {Action.VOICE_JOIN, Action.VOICE_MOVE, Action.VOICE_LEAVE, Action.PLAYBACK_STOP}:
        conn.execute("UPDATE sessions SET start_after_connect=0 WHERE guild_id=?", (plan.guild_id,))
    if action == Action.VOICE_JOIN:
        session.join()
        conn.execute(
            "UPDATE sessions SET voice_channel_id=? WHERE guild_id=?",
            (args["channel_id"], plan.guild_id),
        )
    elif action == Action.VOICE_MOVE:
        session.stop(leave=True)
        session.join()
        conn.execute(
            "UPDATE sessions SET voice_channel_id=? WHERE guild_id=?",
            (args["channel_id"], plan.guild_id),
        )
    elif action == Action.VOICE_LEAVE:
        session.stop(leave=True)
        conn.execute("UPDATE sessions SET voice_channel_id=NULL WHERE guild_id=?", (plan.guild_id,))
    elif action == Action.PLAYBACK_START:
        session.failed_tracks = 0
        session.start()
    elif action == Action.PLAYBACK_PAUSE:
        session.pause()
    elif action == Action.PLAYBACK_RESUME:
        session.resume()
    elif action == Action.PLAYBACK_STOP:
        session.stop()
    elif action == Action.PLAYBACK_SKIP:
        session.skip()
    elif action == Action.PLAYBACK_VOLUME:
        volume = args["percent"]
        if type(volume) is not int or not 0 <= volume <= 100:
            raise DomainError("invalid_volume")
        session.volume = volume
        session.version += 1
    elif action == Action.PLAYBACK_REPEAT:
        if args["mode"] not in {"off", "one", "queue"}:
            raise DomainError("invalid_repeat_mode")
        session.repeat = args["mode"]
        session.version += 1
    elif action == Action.PLAYBACK_SHUFFLE:
        if type(args["seed"]) is not int:
            raise DomainError("invalid_shuffle_seed")
        session.shuffle(args["seed"])
    else:
        raise DomainError("unknown_playback_action")
    save_session(conn, plan.guild_id, session)
    return {
        "desired_state": session.state.value,
        "generation": session.generation,
        "queue_version": session.version,
    }

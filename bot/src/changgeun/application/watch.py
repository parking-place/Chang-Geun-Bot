"""Durable watch policy, trusted request provenance and atomic revocation.

No Discord calls, interaction tokens, message bodies or inference are stored here.
The adapter verifies Discord permissions before issuing a short-lived AdminGrant.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, cast

from changgeun.domain.models import Actor, DomainError, Policy, digest
from changgeun.storage.database import Database

MAX_CHANNELS = 20


@dataclass(frozen=True)
class AdminGrant:
    guild: str
    actor: str
    checked_at: float


def source_row(conn: sqlite3.Connection, guild: str, request: str) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT * FROM request_sources WHERE guild_id=? AND request_id=?",
            (guild, request.split(".", 1)[0]),
        ).fetchone(),
    )


def check_watch(
    conn: sqlite3.Connection, guild: str, channel: str, enable: int | None, generation: int | None
) -> None:
    row = conn.execute(
        "SELECT s.enabled,s.seed_applied,s.enable_generation,c.registered,"
        "c.channel_generation,c.healthy FROM watch_settings s JOIN watch_channels c "
        "ON c.guild_id=s.guild_id WHERE s.guild_id=? AND c.channel_id=?",
        (guild, channel),
    ).fetchone()
    if (
        not row
        or not all((row[0], row[1], row[3], row[5]))
        or (row[2], row[4]) != (enable, generation)
    ):
        raise DomainError("watch_request_revoked")


def policy_for_request(
    conn: sqlite3.Connection,
    policy: Policy,
    actor: Actor,
    request: str,
    *,
    prefix_enabled: bool = True,
) -> Policy:
    source = source_row(conn, actor.guild_id, request)
    if source is None:
        return policy
    if (source["actor_id"], source["channel_id"]) != (actor.user_id, actor.text_channel_id):
        raise DomainError("identity_mismatch")
    if source["revoked"]:
        raise DomainError("watch_request_revoked")
    if source["origin"] != "prefix":
        return policy
    if not prefix_enabled:
        raise DomainError("watch_unavailable")
    message = conn.execute(
        "SELECT 1 FROM message_requests WHERE guild_id=? AND request_id=? AND actor_id=? "
        "AND channel_id=? AND state IN ('running','waiting','committed')",
        (actor.guild_id, source["request_id"], actor.user_id, actor.text_channel_id),
    ).fetchone()
    if not message:
        raise DomainError("message_request_cancelled")
    check_watch(
        conn,
        actor.guild_id,
        actor.text_channel_id,
        source["enable_generation"],
        source["channel_generation"],
    )
    return replace(policy, text_channel_ids=policy.text_channel_ids | {actor.text_channel_id})


def bind_source(
    conn: sqlite3.Connection, guild: str, request: str, actor: str, channel: str, origin: str
) -> None:
    if origin not in {"slash", "mention", "prefix"}:
        raise DomainError("invalid_request_source")
    old = source_row(conn, guild, request)
    if old:
        if (old["actor_id"], old["channel_id"], old["origin"]) != (actor, channel, origin):
            raise DomainError("identity_mismatch")
        return
    enable = generation = revision = None
    if origin == "prefix":
        row = conn.execute(
            "SELECT s.enable_generation,c.channel_generation,s.revision FROM watch_settings s "
            "JOIN watch_channels c ON c.guild_id=s.guild_id WHERE s.guild_id=? "
            "AND c.channel_id=?",
            (guild, channel),
        ).fetchone()
        if not row:
            raise DomainError("watch_unavailable")
        enable, generation, revision = row
        check_watch(conn, guild, channel, enable, generation)
    conn.execute(
        "INSERT INTO request_sources VALUES(?,?,?,?,?,?,?,?,0)",
        (guild, request, actor, channel, origin, enable, generation, revision),
    )


def admission_valid(conn: sqlite3.Connection, guild: str, entry: str) -> bool:
    row = conn.execute(
        "SELECT * FROM audio_admissions WHERE guild_id=? AND entry_id=?", (guild, entry)
    ).fetchone()
    if not row:
        # Old isolated unit fixtures are unmanaged. Seeded product guilds require proof.
        return not bool(
            conn.execute("SELECT 1 FROM watch_settings WHERE guild_id=?", (guild,)).fetchone()
        )
    if row["revoked"] or row["origin"] == "legacy_unknown":
        return False
    if row["origin"] == "prefix":
        try:
            check_watch(
                conn,
                guild,
                row["text_channel_id"],
                row["enable_generation"],
                row["channel_generation"],
            )
        except DomainError:
            return False
    return True


class WatchStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def state(self, guild: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM watch_settings WHERE guild_id=?", (guild,)).fetchone()
            return dict(row) if row else {"enabled": 0, "revision": 0, "seed_applied": 0}

    def channels(self, guild: str) -> list[str]:
        with self.db.connect() as conn:
            return [
                r[0]
                for r in conn.execute(
                    "SELECT channel_id FROM watch_channels WHERE guild_id=? AND registered=1 "
                    "ORDER BY channel_id",
                    (guild,),
                )
            ]

    def history(self, guild: str, *, now: float | None = None) -> list[dict[str, Any]]:
        """Bounded, guild-scoped audit summary; never return message content."""
        cutoff = (time.time() if now is None else now) - 90 * 86400
        with self.db.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT action,channel_id,revision,requests_cancelled,"
                    "admissions_revoked,created_at FROM watch_change_events "
                    "WHERE guild_id=? AND created_at>=? "
                    "ORDER BY created_at DESC,id DESC LIMIT 100",
                    (guild, cutoff),
                )
            ]

    def usage(self, guild: str, *, now: float | None = None) -> dict[str, int | float]:
        """Local 24-hour counters. Gateway-wide dispatch is queried separately."""
        checked_at = time.time() if now is None else now
        cutoff = checked_at - 86400
        with self.db.connect() as conn:
            return {
                "checked_at": checked_at,
                "since": cutoff,
                "commands": int(
                    conn.execute(
                        "SELECT count(*) FROM command_requests WHERE guild_id=? AND created_at>=?",
                        (guild, cutoff),
                    ).fetchone()[0]
                ),
                "prefix_requests": int(
                    conn.execute(
                        "SELECT count(*) FROM message_requests WHERE guild_id=? AND created_at>=?",
                        (guild, cutoff),
                    ).fetchone()[0]
                ),
                "prefix_cancelled": int(
                    conn.execute(
                        "SELECT count(*) FROM message_requests WHERE guild_id=? AND created_at>=? "
                        "AND state='cancelled'",
                        (guild, cutoff),
                    ).fetchone()[0]
                ),
                "watch_changes": int(
                    conn.execute(
                        "SELECT count(*) FROM watch_change_events WHERE guild_id=? "
                        "AND created_at>=?",
                        (guild, cutoff),
                    ).fetchone()[0]
                ),
                "completed_tracks": int(
                    conn.execute(
                        "SELECT count(*) FROM playback_history WHERE guild_id=? AND played_at>=?",
                        (guild, cutoff),
                    ).fetchone()[0]
                ),
            }

    def seed(self, guild: str, channels: list[str], enabled: bool) -> None:
        if len(channels) > MAX_CHANNELS or len(set(channels)) != len(channels):
            raise DomainError("watch_channel_limit")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watch_settings(guild_id,updated_at) VALUES(?,?)",
                (guild, time.time()),
            )
            row = conn.execute(
                "SELECT seed_applied FROM watch_settings WHERE guild_id=?", (guild,)
            ).fetchone()
            if row[0]:
                return
            for channel in channels:
                conn.execute(
                    "INSERT INTO watch_channels VALUES(?,?,1,1,1,?)", (guild, channel, time.time())
                )
            conn.execute(
                "UPDATE watch_settings SET enabled=?,seed_applied=1,updated_at=? WHERE guild_id=?",
                (bool(channels) and enabled, time.time(), guild),
            )
            # Only the message ledger proves legacy prefix provenance.
            for old in conn.execute(
                "SELECT a.*,m.request_id AS root,m.channel_id AS source_channel, "
                "m.actor_id AS source_actor FROM audio_admissions a JOIN message_requests m "
                "ON m.guild_id=a.guild_id AND m.request_id=a.request_id "
                "WHERE a.guild_id=? AND a.origin='legacy_unknown'",
                (guild,),
            ).fetchall():
                if (
                    old["source_channel"] in channels
                    and old["source_actor"] == old["actor_id"]
                    and old["source_channel"] == old["text_channel_id"]
                    and enabled
                ):
                    conn.execute(
                        "UPDATE audio_admissions SET origin='prefix',revoked=0,"
                        "enable_generation=1,channel_generation=1 WHERE guild_id=? "
                        "AND entry_id=?",
                        (guild, old["entry_id"]),
                    )

    def counts(self, guild: str, channel: str | None) -> tuple[int, int]:
        with self.db.connect() as conn:
            return self._counts(conn, guild, channel)

    @staticmethod
    def _counts(conn: sqlite3.Connection, guild: str, channel: str | None) -> tuple[int, int]:
        requests = conn.execute(
            "SELECT count(*) FROM message_requests WHERE guild_id=? "
            "AND (? IS NULL OR channel_id=?) AND state IN ('running','waiting')",
            (guild, channel, channel),
        ).fetchone()[0]
        admissions = conn.execute(
            "SELECT count(*) FROM audio_admissions WHERE guild_id=? AND origin='prefix' "
            "AND revoked=0 AND started=0 AND (? IS NULL OR text_channel_id=?)",
            (guild, channel, channel),
        ).fetchone()[0]
        return requests, admissions

    @staticmethod
    def _revoke(conn: sqlite3.Connection, guild: str, channel: str | None) -> tuple[list[str], int]:
        requests = [
            r[0]
            for r in conn.execute(
                "SELECT request_id FROM message_requests WHERE guild_id=? "
                "AND (? IS NULL OR channel_id=?) AND state IN ('running','waiting')",
                (guild, channel, channel),
            )
        ]
        _, admissions = WatchStore._counts(conn, guild, channel)
        conn.execute(
            "UPDATE confirmations SET consumed=1 WHERE token_hash IN "
            "(SELECT confirmation_hash FROM message_requests WHERE guild_id=? "
            "AND (? IS NULL OR channel_id=?))",
            (guild, channel, channel),
        )
        conn.execute(
            "UPDATE message_requests SET state='cancelled' WHERE guild_id=? "
            "AND (? IS NULL OR channel_id=?) AND state IN ('running','waiting')",
            (guild, channel, channel),
        )
        conn.execute(
            "UPDATE request_sources SET revoked=1 WHERE guild_id=? AND origin='prefix' "
            "AND (? IS NULL OR channel_id=?)",
            (guild, channel, channel),
        )
        # Started streams keep playing; their next/repeated start still needs a fresh approval.
        conn.execute(
            "UPDATE audio_admissions SET revoked=1 WHERE guild_id=? AND origin='prefix' "
            "AND (? IS NULL OR text_channel_id=?)",
            (guild, channel, channel),
        )
        return requests, admissions

    def change(
        self, grant: AdminGrant, interaction: str, action: str, channel: str | None, expected: int
    ) -> dict[str, Any]:
        if not 0 <= time.time() - grant.checked_at <= 5:
            raise DomainError("permissions_unavailable")
        if action not in {"add", "remove", "enable", "disable"}:
            raise DomainError("invalid_arguments")
        if action in {"add", "remove"} and (channel is None or not channel.isdecimal()):
            raise DomainError("invalid_arguments")
        body = digest([grant.actor, action, channel])
        with self.db.transaction() as conn:
            if not 0 <= time.time() - grant.checked_at <= 5:
                raise DomainError("permissions_unavailable")
            old = conn.execute(
                "SELECT body_hash,result_json FROM watch_change_requests "
                "WHERE guild_id=? AND interaction_id=?",
                (grant.guild, interaction),
            ).fetchone()
            if old:
                if old[0] != body:
                    raise DomainError("request_body_conflict")
                return json.loads(old[1])  # type: ignore[no-any-return]
            state = conn.execute(
                "SELECT * FROM watch_settings WHERE guild_id=?", (grant.guild,)
            ).fetchone()
            if not state or not state["seed_applied"]:
                raise DomainError("watch_seed_required")
            if state["revision"] != expected:
                raise DomainError("watch_revision_conflict")
            registered = [
                r[0]
                for r in conn.execute(
                    "SELECT channel_id FROM watch_channels WHERE guild_id=? AND registered=1",
                    (grant.guild,),
                )
            ]
            no_op = (
                action == "add"
                and channel in registered
                or action == "remove"
                and channel not in registered
                or action == "enable"
                and bool(state["enabled"])
                or action == "disable"
                and not state["enabled"]
            )
            requests: list[str] = []
            admissions = 0
            if not no_op:
                now = time.time()
                if action == "add":
                    if len(registered) >= MAX_CHANNELS:
                        raise DomainError("watch_channel_limit")
                    conn.execute(
                        "INSERT INTO watch_channels VALUES(?,?,1,1,1,?) "
                        "ON CONFLICT(guild_id,channel_id) DO UPDATE SET registered=1, "
                        "healthy=1,channel_generation=channel_generation+1, "
                        "updated_at=excluded.updated_at",
                        (grant.guild, channel, now),
                    )
                elif action == "remove":
                    conn.execute(
                        "UPDATE watch_channels SET registered=0, "
                        "channel_generation=channel_generation+1,updated_at=? "
                        "WHERE guild_id=? AND channel_id=?",
                        (now, grant.guild, channel),
                    )
                    requests, admissions = self._revoke(conn, grant.guild, channel)
                    if len(registered) == 1:
                        conn.execute(
                            "UPDATE watch_settings SET enabled=0, "
                            "enable_generation=enable_generation+1 WHERE guild_id=?",
                            (grant.guild,),
                        )
                elif action == "enable":
                    if not registered:
                        raise DomainError("watch_empty")
                    conn.execute(
                        "UPDATE watch_settings SET enabled=1, "
                        "enable_generation=enable_generation+1 WHERE guild_id=?",
                        (grant.guild,),
                    )
                else:
                    conn.execute(
                        "UPDATE watch_settings SET enabled=0, "
                        "enable_generation=enable_generation+1 WHERE guild_id=?",
                        (grant.guild,),
                    )
                    requests, admissions = self._revoke(conn, grant.guild, None)
                conn.execute(
                    "UPDATE watch_settings SET revision=revision+1,updated_at=? WHERE guild_id=?",
                    (now, grant.guild),
                )
                conn.execute(
                    "INSERT INTO watch_change_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        grant.guild,
                        grant.actor,
                        action,
                        channel,
                        expected,
                        expected + 1,
                        len(requests),
                        admissions,
                        now,
                    ),
                )
            result = {
                "changed": not bool(no_op),
                "revision": expected + (not no_op),
                "cancelled": requests,
                "admissions_revoked": admissions,
            }
            conn.execute(
                "INSERT INTO watch_change_requests VALUES(?,?,?,?,?,?)",
                (grant.guild, interaction, grant.actor, body, json.dumps(result), time.time()),
            )
            return result

    def health(self, guild: str, channel: str, healthy: bool) -> list[str]:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT healthy FROM watch_channels WHERE guild_id=? "
                "AND channel_id=? AND registered=1",
                (guild, channel),
            ).fetchone()
            if not row or bool(row[0]) == healthy:
                return []
            conn.execute(
                "UPDATE watch_channels SET healthy=?,channel_generation=channel_generation+1 "
                "WHERE guild_id=? AND channel_id=?",
                (healthy, guild, channel),
            )
            requests, admissions = self._revoke(conn, guild, channel) if not healthy else ([], 0)
            state = conn.execute(
                "SELECT revision FROM watch_settings WHERE guild_id=?", (guild,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE watch_settings SET revision=revision+1,updated_at=? WHERE guild_id=?",
                (time.time(), guild),
            )
            conn.execute(
                "INSERT INTO watch_change_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    guild,
                    "system",
                    "health",
                    channel,
                    state,
                    state + 1,
                    len(requests),
                    admissions,
                    time.time(),
                ),
            )
            return requests

    def recover(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE request_sources SET revoked=1 WHERE origin='prefix' AND request_id IN "
                "(SELECT request_id FROM message_requests WHERE state IN "
                "('running','waiting','unknown','cancelled'))"
            )
            conn.execute(
                "DELETE FROM watch_change_events WHERE created_at<?", (time.time() - 90 * 86400,)
            )

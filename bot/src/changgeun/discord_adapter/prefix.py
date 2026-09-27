"""Exact wake word routing and durable admission; message text is never retained."""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from dataclasses import dataclass

from changgeun.application.watch import bind_source
from changgeun.domain.models import DomainError
from changgeun.storage.database import Database

PREFIX = "!!창근아"


@dataclass(frozen=True)
class PrefixConfig:
    enabled: bool = False
    channel_ids: frozenset[str] = frozenset()


def parse_prefix(content: str) -> str | None:
    content = content.replace("\r\n", "\n")
    if not content.startswith(PREFIX):
        return None
    rest = content[len(PREFIX) :]
    if rest and rest[0] not in " \t\n":
        return None
    return rest.strip(" \t\n")


def check_message(conn: sqlite3.Connection, guild: str, request: str) -> None:
    row = conn.execute(
        "SELECT state FROM message_requests WHERE guild_id=? AND request_id=?",
        (guild, request.split(".", 1)[0]),
    ).fetchone()
    if row and row[0] not in {"running", "waiting", "committed"}:
        raise DomainError("message_request_cancelled")


class MessageLedger:
    def __init__(self, db: Database) -> None:
        self.db = db

    def admit(
        self,
        guild: str,
        channel: str,
        message: str,
        actor: str,
        text: str,
        policy_hash: str,
        created: float,
        *,
        now: float | None = None,
    ) -> str | None:
        now = time.time() if now is None else now
        if not 0 <= now - created <= 30:
            return None
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT 1 FROM message_requests WHERE guild_id=? AND channel_id=? AND message_id=?",
                (guild, channel, message),
            ).fetchone()
            if existing:
                return None
            request = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO message_requests(guild_id,channel_id,message_id,request_id,actor_id,"
                "body_hash,policy_hash,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    guild,
                    channel,
                    message,
                    request,
                    actor,
                    hashlib.sha256(text.encode()).hexdigest(),
                    policy_hash,
                    now,
                    now + 12,
                ),
            )
            if conn.execute(
                "SELECT 1 FROM watch_settings WHERE guild_id=? AND seed_applied=1", (guild,)
            ).fetchone():
                bind_source(conn, guild, request, actor, channel, "prefix")
            return request

    def finish(self, request: str, state: str) -> None:
        if state not in {"finished", "failed", "waiting"}:
            raise ValueError("invalid message state")
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE message_requests SET state=? WHERE request_id=? AND state='running'",
                (state, request),
            )

    def cancel(
        self, guild: str, channel: str, messages: set[str], *, include_responses: bool = True
    ) -> set[str]:
        requests: set[str] = set()
        with self.db.transaction() as conn:
            for message in messages:
                row = conn.execute(
                    "SELECT request_id,confirmation_hash FROM message_requests "
                    "WHERE guild_id=? AND channel_id=? AND (message_id=? OR (? AND response_id=?)) "
                    "AND state IN ('running','waiting')",
                    (guild, channel, message, include_responses, message),
                ).fetchone()
                if not row:
                    continue
                requests.add(row[0])
                conn.execute(
                    "UPDATE message_requests SET state='cancelled' WHERE request_id=?", (row[0],)
                )
                if row[1]:
                    conn.execute(
                        "UPDATE confirmations SET consumed=1 WHERE token_hash=?", (row[1],)
                    )
        return requests

    def recover(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE confirmations SET consumed=1 WHERE token_hash IN "
                "(SELECT confirmation_hash FROM message_requests "
                "WHERE state IN ('running','waiting'))"
            )
            conn.execute(
                "UPDATE message_requests SET state='unknown' WHERE state IN ('running','waiting')"
            )
            conn.execute(
                "DELETE FROM message_requests WHERE created_at<?", (time.time() - 90 * 86400,)
            )

    def reserve_response(self, request: str) -> bool:
        with self.db.transaction() as conn:
            return (
                conn.execute(
                    "UPDATE message_requests SET response_state='reserved' "
                    "WHERE request_id=? AND response_state='new'",
                    (request,),
                ).rowcount
                == 1
            )

    def record_response(self, request: str, message: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE message_requests SET response_id=?,response_state='sent' "
                "WHERE request_id=?",
                (message, request),
            )

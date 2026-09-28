"""One-use in-memory typed followups and confirmations; restart invalidates all."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

from changgeun.parser.contracts import ParseError


@dataclass(frozen=True)
class PendingAction:
    kind: Literal["typed", "confirm"]
    root_id: str
    guild_id: str
    channel_id: str
    actor_id: str
    command_id: str
    argument: str | None
    expires_at: float
    payload: Any


class PendingStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, PendingAction] = {}

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def issue(self, *, kind: Literal["typed", "confirm"], root_id: str,
              guild_id: str, channel_id: str, actor_id: str, command_id: str,
              payload: Any, argument: str | None = None,
              now: float | None = None) -> str:
        if kind == "typed" and not argument:
            raise ParseError("missing_pending_argument")
        token = secrets.token_urlsafe(24)
        moment = time.monotonic() if now is None else now
        action = PendingAction(kind, root_id, guild_id, channel_id, actor_id,
                               command_id, argument, moment + (60 if kind == "typed" else 300),
                               payload)
        with self._lock:
            # A new request replaces this actor's unanswered question/preview.
            for old_key, old in tuple(self._items.items()):
                if (old.guild_id, old.channel_id, old.actor_id) == (
                    guild_id, channel_id, actor_id
                ):
                    del self._items[old_key]
            self._items[self._key(token)] = action
        return token

    def consume(self, token: str, *, kind: Literal["typed", "confirm"], root_id: str,
                guild_id: str, channel_id: str, actor_id: str,
                now: float | None = None) -> PendingAction:
        moment = time.monotonic() if now is None else now
        key = self._key(token)
        with self._lock:
            item = self._items.get(key)
            if item is None:
                raise ParseError("pending_unknown_or_used")
            if moment >= item.expires_at:
                del self._items[key]
                raise ParseError("pending_expired")
            if (kind, root_id, guild_id, channel_id, actor_id) != (
                item.kind, item.root_id, item.guild_id, item.channel_id, item.actor_id
            ):
                raise ParseError("pending_owner_mismatch")
            del self._items[key]
            return item

    def cancel(self, token: str, *, root_id: str, guild_id: str,
               channel_id: str, actor_id: str) -> bool:
        key = self._key(token)
        with self._lock:
            item = self._items.get(key)
            if item is None or (item.root_id, item.guild_id, item.channel_id,
                                item.actor_id) != (root_id, guild_id, channel_id, actor_id):
                return False
            del self._items[key]
            return True

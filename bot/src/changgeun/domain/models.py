"""Trusted command contracts; no Discord or inference imports."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DomainError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Action(StrEnum):
    PLAYLIST_CREATE = "playlist.create"
    PLAYLIST_GENERATE = "playlist.generate"
    PLAYLIST_IMPORT = "playlist.import"
    PLAYLIST_RENAME = "playlist.rename"
    PLAYLIST_DELETE = "playlist.delete"
    PLAYLIST_RESTORE = "playlist.restore"
    PLAYLIST_ADD = "playlist.add"
    PLAYLIST_REMOVE = "playlist.remove"
    PLAYLIST_MOVE = "playlist.move"
    PLAYLIST_COPY = "playlist.copy"
    PLAYLIST_EXPORT = "playlist.export"
    PLAYLIST_LIST = "playlist.list"
    PLAYLIST_PLAY = "playlist.play"
    TRACK_PLAY = "track.play"
    QUEUE_ENQUEUE = "queue.enqueue"
    QUEUE_REMOVE = "queue.remove"
    QUEUE_MOVE = "queue.move"
    QUEUE_CLEAR = "queue.clear"
    QUEUE_SAVE = "queue.save"
    QUEUE_SHOW = "queue.show"
    CATALOG_REGISTER = "catalog.register"
    CATALOG_SEARCH = "catalog.search"
    HISTORY_LIST = "history.list"
    CATALOG_ANNOTATE = "catalog.annotate"
    PROPOSAL_CREATE = "proposal.create"
    PROPOSAL_APPROVE = "proposal.approve"
    PROPOSAL_REJECT = "proposal.reject"
    PROPOSAL_LIST = "proposal.list"
    PLAYBACK_START = "playback.start"
    PLAYBACK_PAUSE = "playback.pause"
    PLAYBACK_RESUME = "playback.resume"
    PLAYBACK_SKIP = "playback.skip"
    PLAYBACK_STOP = "playback.stop"
    PLAYBACK_VOLUME = "playback.volume"
    PLAYBACK_REPEAT = "playback.repeat"
    PLAYBACK_SHUFFLE = "playback.shuffle"
    VOICE_JOIN = "voice.join"
    VOICE_MOVE = "voice.move"
    VOICE_LEAVE = "voice.leave"
    SETTINGS_UPDATE = "settings.update"
    EDIT_UNDO = "edit.undo"


READ_ACTIONS = frozenset(
    {
        Action.PLAYLIST_LIST,
        Action.PLAYLIST_EXPORT,
        Action.CATALOG_SEARCH,
        Action.HISTORY_LIST,
        Action.QUEUE_SHOW,
        Action.PROPOSAL_LIST,
    }
)
PLAYBACK_ACTIONS = frozenset(a for a in Action if a.value.startswith(("playback.", "voice."))) | {
    Action.PLAYLIST_PLAY,
    Action.TRACK_PLAY,
}
QUEUE_ACTIONS = frozenset(a for a in Action if a.value.startswith("queue."))


def normalized_name(value: str) -> str:
    value = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    if not value or len(value) > 100:
        raise DomainError("invalid_name")
    return value


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Actor:
    guild_id: str
    user_id: str
    role_ids: frozenset[str]
    text_channel_id: str
    voice_channel_id: str | None = None
    bot_voice_channel_id: str | None = None
    manage_guild: bool = False
    permissions_known: bool = True


@dataclass(frozen=True)
class Policy:
    guild_ids: frozenset[str]
    dj_role_ids: frozenset[str]
    text_channel_ids: frozenset[str]
    voice_channel_ids: frozenset[str]
    admin_dj_override: bool = False
    same_voice_required: bool = True
    allow_remote_voice_control: bool = False
    confirmation_ttl: int = 60
    bulk_threshold: int = 20


@dataclass(frozen=True)
class InferenceTrace:
    provider: str
    profile_id: str
    config_hash: str
    stages: int
    questions: int
    provider_calls: int
    forward_passes: int | None
    forward_passes_source: str

    def validate(self) -> None:
        if self.provider not in {"jev-api", "mock"} or not re.fullmatch(
            r"[a-f0-9]{64}", self.config_hash
        ):
            raise DomainError("invalid_inference_binding")
        if (
            not 1 <= self.stages <= 3
            or self.questions != self.stages
            or self.provider_calls != self.stages
        ):
            raise DomainError("invalid_inference_budget")
        if self.forward_passes is not None or self.forward_passes_source != "unavailable":
            raise DomainError("invalid_forward_provenance")


@dataclass(frozen=True)
class ActionPlan:
    request_id: str
    guild_id: str
    actor_id: str
    action: Action
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_versions: dict[str, int] = field(default_factory=dict)
    origin: str = "slash"
    execution_generation: int = 0
    expires_at: float | None = None
    inference: InferenceTrace | None = None

    def fingerprint(self) -> str:
        return digest(asdict(self))

    def validate(self) -> None:
        if not self.request_id or len(self.request_id) > 128:
            raise DomainError("invalid_request_id")
        if not self.guild_id.isdecimal() or not self.actor_id.isdecimal():
            raise DomainError("invalid_identity")
        if self.origin not in {"slash", "button", "natural_language"}:
            raise DomainError("invalid_origin")
        if not isinstance(self.action, Action):
            raise DomainError("unknown_action")
        if any(v < 0 for v in self.expected_versions.values()):
            raise DomainError("invalid_version")
        if self.expires_at is not None and not math.isfinite(self.expires_at):
            raise DomainError("invalid_deadline")
        if self.inference is not None:
            self.inference.validate()


def authorize(plan: ActionPlan, actor: Actor, policy: Policy) -> None:
    plan.validate()
    if (plan.guild_id, plan.actor_id) != (actor.guild_id, actor.user_id):
        raise DomainError("identity_mismatch")
    if not actor.permissions_known:
        raise DomainError("permissions_unavailable")
    if actor.guild_id not in policy.guild_ids:
        raise DomainError("guild_not_allowed")
    if actor.text_channel_id not in policy.text_channel_ids:
        raise DomainError("text_channel_not_allowed")
    if (
        plan.action in READ_ACTIONS - {Action.PROPOSAL_LIST}
        or plan.action == Action.PROPOSAL_CREATE
    ):
        return
    if plan.action == Action.SETTINGS_UPDATE:
        if not actor.manage_guild:
            raise DomainError("administrator_required")
        return
    is_dj = bool(actor.role_ids & policy.dj_role_ids)
    if not is_dj and not (policy.admin_dj_override and actor.manage_guild):
        raise DomainError("dj_required")
    if plan.action in PLAYBACK_ACTIONS | QUEUE_ACTIONS:
        target = (
            plan.arguments.get("channel_id")
            if plan.action
            in {Action.VOICE_JOIN, Action.VOICE_MOVE, Action.PLAYLIST_PLAY, Action.TRACK_PLAY}
            else actor.bot_voice_channel_id
        )
        if target is not None and target not in policy.voice_channel_ids:
            raise DomainError("voice_channel_not_allowed")
        if policy.same_voice_required and not policy.allow_remote_voice_control:
            required = target or actor.voice_channel_id
            if actor.voice_channel_id is None or actor.voice_channel_id != required:
                raise DomainError("same_voice_required")


def needs_confirmation(plan: ActionPlan, policy: Policy) -> bool:
    if plan.action in {
        Action.PLAYLIST_DELETE,
        Action.QUEUE_CLEAR,
        Action.PLAYLIST_GENERATE,
        Action.PLAYLIST_IMPORT,
        Action.EDIT_UNDO,
    }:
        return True
    if plan.origin == "natural_language" and plan.action in {
        Action.PLAYLIST_REMOVE,
        Action.QUEUE_REMOVE,
    }:
        return True
    if plan.action == Action.VOICE_MOVE:
        return True
    if plan.arguments.get("overwrite") or plan.arguments.get("replace"):
        return True
    return len(plan.arguments.get("track_ids", [])) >= policy.bulk_threshold

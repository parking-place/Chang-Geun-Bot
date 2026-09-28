"""One transactional executor for slash, button and natural-language plans."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

from changgeun.application import undo
from changgeun.application.generation import Rules, select
from changgeun.application.transfer import validate_references
from changgeun.application.watch import admission_valid, policy_for_request, source_row
from changgeun.discord_adapter.prefix import check_message
from changgeun.domain.models import (
    PLAYBACK_ACTIONS,
    READ_ACTIONS,
    Action,
    ActionPlan,
    Actor,
    DomainError,
    Policy,
    authorize,
    needs_confirmation,
    normalized_name,
)
from changgeun.playback.persistence import apply_playback, load_session, save_session
from changgeun.playback.state import PlaybackState
from changgeun.storage.database import Database

ARGUMENTS: dict[Action, tuple[set[str], set[str]]] = {
    Action.EDIT_UNDO: ({"event_id"}, set()),
    Action.PLAYLIST_CREATE: ({"name"}, set()),
    Action.PLAYLIST_GENERATE: (
        {"name", "rules", "track_ids", "snapshot_hash", "reference_time"},
        set(),
    ),
    Action.PLAYLIST_IMPORT: (
        {"name", "references", "complete", "unavailable_count", "accept_partial"},
        {"playlist_id", "replace", "allow_duplicates", "source_metadata"},
    ),
    Action.PLAYLIST_RENAME: ({"playlist_id", "name"}, set()),
    Action.PLAYLIST_DELETE: ({"playlist_id"}, set()),
    Action.PLAYLIST_RESTORE: ({"playlist_id"}, set()),
    Action.PLAYLIST_ADD: ({"playlist_id", "track_ids"}, {"allow_duplicates"}),
    Action.PLAYLIST_REMOVE: ({"playlist_id", "entry_id"}, set()),
    Action.PLAYLIST_MOVE: ({"playlist_id", "entry_id", "position"}, set()),
    Action.PLAYLIST_COPY: ({"playlist_id", "name"}, set()),
    Action.PLAYLIST_EXPORT: ({"playlist_id"}, set()),
    Action.PLAYLIST_LIST: (set(), set()),
    Action.PLAYLIST_PLAY: ({"playlist_id", "channel_id", "track_ids"}, {"allow_duplicates"}),
    Action.TRACK_PLAY: ({"track_id", "channel_id"}, {"entry_id"}),
    Action.CATALOG_REGISTER: ({"source_type", "external_id", "title"}, {"metadata"}),
    Action.CATALOG_SEARCH: ({"query"}, set()),
    Action.CATALOG_ANNOTATE: ({"track_id", "aliases", "tags"}, {"creator"}),
    Action.QUEUE_ENQUEUE: ({"track_ids"}, {"allow_duplicates"}),
    Action.QUEUE_REMOVE: ({"entry_id"}, set()),
    Action.QUEUE_MOVE: ({"entry_id", "position"}, set()),
    Action.QUEUE_CLEAR: (set(), set()),
    Action.QUEUE_SHOW: (set(), set()),
    Action.QUEUE_SAVE: ({"name"}, {"include_current"}),
    Action.PROPOSAL_CREATE: ({"playlist_id", "track_id"}, set()),
    Action.PROPOSAL_APPROVE: ({"proposal_id"}, set()),
    Action.PROPOSAL_REJECT: ({"proposal_id"}, set()),
    Action.PROPOSAL_LIST: (set(), set()),
    Action.SETTINGS_UPDATE: ({"settings"}, set()),
    Action.VOICE_JOIN: ({"channel_id"}, set()),
    Action.VOICE_MOVE: ({"channel_id"}, set()),
    Action.VOICE_LEAVE: (set(), set()),
    Action.PLAYBACK_START: (set(), set()),
    Action.PLAYBACK_PAUSE: (set(), set()),
    Action.PLAYBACK_RESUME: (set(), set()),
    Action.PLAYBACK_SKIP: (set(), set()),
    Action.PLAYBACK_STOP: (set(), set()),
    Action.PLAYBACK_VOLUME: ({"percent"}, set()),
    Action.PLAYBACK_REPEAT: ({"mode"}, set()),
    Action.PLAYBACK_SHUFFLE: ({"seed"}, set()),
}


def validate_arguments(plan: ActionPlan) -> None:
    if plan.action not in ARGUMENTS:
        raise DomainError("action_not_implemented")
    required, optional = ARGUMENTS[plan.action]
    if not required <= plan.arguments.keys() or plan.arguments.keys() - required - optional:
        raise DomainError("invalid_arguments")
    for key, value in plan.arguments.items():
        if key.endswith("_id") or key in {"name", "title", "source_type", "external_id", "query"}:
            if not isinstance(value, str) or not value or len(value) > 500:
                raise DomainError("invalid_arguments")
        if key in {"track_ids", "aliases", "tags"}:
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                raise DomainError("invalid_arguments")
            if len(value) > 500:
                raise DomainError("entry_limit")
        if (
            key in {"allow_duplicates", "include_current", "complete", "accept_partial", "replace"}
            and type(value) is not bool
        ):
            raise DomainError("invalid_arguments")
        if key == "position" and (type(value) is not int or value < 0):
            raise DomainError("invalid_position")
        if key in {"metadata", "settings"} and not isinstance(value, dict):
            raise DomainError("invalid_arguments")
    if plan.action == Action.PLAYLIST_IMPORT:
        validate_references(plan.arguments["references"])
        metadata = plan.arguments.get("source_metadata", {})
        if not isinstance(metadata, dict) or len(metadata) > 500:
            raise DomainError("invalid_import_metadata")
        references = {
            row["external_id"]
            for row in plan.arguments["references"]
            if row["source_type"] == "youtube"
        }
        for identifier, item in metadata.items():
            if (
                identifier not in references
                or not isinstance(item, dict)
                or set(item) != {"source_author", "duration_seconds"}
            ):
                raise DomainError("invalid_import_metadata")
            duration = item["duration_seconds"]
            if (
                not isinstance(item["source_author"], str)
                or len(item["source_author"]) > 200
                or (
                    duration is not None
                    and (type(duration) is not int or not 0 <= duration <= 604800)
                )
            ):
                raise DomainError("invalid_import_metadata")
        unavailable = plan.arguments["unavailable_count"]
        if type(unavailable) is not int or not 0 <= unavailable <= 500:
            raise DomainError("invalid_arguments")
        if (not plan.arguments["complete"] or unavailable) and not plan.arguments["accept_partial"]:
            raise DomainError("partial_import_requires_consent")
    if plan.action == Action.CATALOG_ANNOTATE:
        if any(len(plan.arguments[key]) > 20 for key in ("aliases", "tags")):
            raise DomainError("invalid_arguments")
        for value in plan.arguments["aliases"] + plan.arguments["tags"]:
            normalized_name(value)
        if "creator" in plan.arguments:
            if not isinstance(plan.arguments["creator"], str):
                raise DomainError("invalid_arguments")
            normalized_name(plan.arguments["creator"])


class Executor:
    def __init__(
        self,
        db: Database,
        policy: Policy,
        *,
        clock: Callable[[], float] = time.time,
        before_commit: Callable[[], None] | None = None,
        inference_binding: tuple[str, str, str] | None = None,
        youtube_audio_enabled: bool = False,
        prefix_enabled: bool = True,
    ) -> None:
        self.db, self.policy, self.clock = db, policy, clock
        self.prefix_enabled = prefix_enabled
        self.before_commit = before_commit
        self.inference_binding = inference_binding
        self.allowed_audio_sources = {"approved_audio"} | (
            {"youtube"} if youtube_audio_enabled else set()
        )

    def preview(self, plan: ActionPlan, actor: Actor) -> str:
        with self.db.connect() as auth_conn:
            authorize(
                plan,
                actor,
                policy_for_request(
                    auth_conn,
                    self.policy,
                    actor,
                    plan.request_id,
                    prefix_enabled=self.prefix_enabled,
                ),
            )
        validate_arguments(plan)
        if plan.expires_at is not None and plan.expires_at <= self.clock():
            raise DomainError("execution_deadline_expired")
        token = secrets.token_urlsafe(32)
        with self.db.transaction() as conn:
            check_message(conn, plan.guild_id, plan.request_id)
            authorize(
                plan,
                actor,
                policy_for_request(
                    conn, self.policy, actor, plan.request_id, prefix_enabled=self.prefix_enabled
                ),
            )
            self._authorize_undo(conn, plan, actor)
            self._check_versions(conn, plan)
            conn.execute(
                "INSERT INTO confirmations VALUES(?,?,?,?,?,0)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    plan.guild_id,
                    plan.actor_id,
                    plan.fingerprint(),
                    self.clock() + self.policy.confirmation_ttl,
                ),
            )
            conn.execute(
                "UPDATE message_requests SET state='waiting',confirmation_hash=? "
                "WHERE guild_id=? AND request_id=?",
                (hashlib.sha256(token.encode()).hexdigest(), plan.guild_id, plan.request_id),
            )
        return token

    def execute(
        self, plan: ActionPlan, actor: Actor, *, confirmation: str | None = None
    ) -> dict[str, Any]:
        # Caller obtains fresh Discord roles/voice state, including for confirmation.
        with self.db.connect() as auth_conn:
            authorize(
                plan,
                actor,
                policy_for_request(
                    auth_conn,
                    self.policy,
                    actor,
                    plan.request_id,
                    prefix_enabled=self.prefix_enabled,
                ),
            )
        validate_arguments(plan)
        if (
            plan.expires_at is not None
            and plan.expires_at <= self.clock()
            and (confirmation is None or not needs_confirmation(plan, self.policy))
        ):
            raise DomainError("execution_deadline_expired")
        try:
            with self.db.transaction() as conn:
                check_message(conn, plan.guild_id, plan.request_id)
                authorize(
                    plan,
                    actor,
                    policy_for_request(
                        conn,
                        self.policy,
                        actor,
                        plan.request_id,
                        prefix_enabled=self.prefix_enabled,
                    ),
                )
                self._authorize_undo(conn, plan, actor)
                existing = conn.execute(
                    "SELECT body_hash,result_json FROM command_requests "
                    "WHERE guild_id=? AND request_id=?",
                    (plan.guild_id, plan.request_id),
                ).fetchone()
                if existing:
                    if existing["body_hash"] != plan.fingerprint():
                        raise DomainError("request_body_conflict")
                    return json.loads(existing["result_json"])  # type: ignore[no-any-return]
                self._check_versions(conn, plan)
                if needs_confirmation(plan, self.policy):
                    self._consume_confirmation(conn, plan, confirmation)
                before = self._snapshot(conn, plan.guild_id)
                result = self._apply(conn, plan)
                if plan.action == Action.TRACK_PLAY and result.get("reused_entry_id"):
                    conn.execute(
                        "INSERT INTO audio_admissions(guild_id,entry_id,actor_id,"
                        "text_channel_id,request_id,created_at) VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(guild_id,entry_id) DO UPDATE SET "
                        "actor_id=excluded.actor_id,text_channel_id=excluded.text_channel_id,"
                        "request_id=excluded.request_id,created_at=excluded.created_at",
                        (
                            plan.guild_id,
                            result["reused_entry_id"],
                            plan.actor_id,
                            actor.text_channel_id,
                            plan.request_id,
                            self.clock(),
                        ),
                    )
                if plan.action in {Action.PLAYLIST_PLAY, Action.TRACK_PLAY, Action.QUEUE_ENQUEUE}:
                    prior = {row["id"] for row in before["queue_entries"]}
                    for row in conn.execute(
                        "SELECT id FROM queue_entries WHERE guild_id=?", (plan.guild_id,)
                    ):
                        if row[0] not in prior:
                            conn.execute(
                                "INSERT INTO audio_admissions(guild_id,entry_id,actor_id,"
                                "text_channel_id,request_id,created_at) VALUES(?,?,?,?,?,?)",
                                (
                                    plan.guild_id,
                                    row[0],
                                    plan.actor_id,
                                    actor.text_channel_id,
                                    plan.request_id,
                                    self.clock(),
                                ),
                            )
                    current = conn.execute(
                        "SELECT current_entry_id FROM sessions WHERE guild_id=?", (plan.guild_id,)
                    ).fetchone()[0]
                    if current and current != before["sessions"][0]["current_entry_id"]:
                        conn.execute(
                            "INSERT OR IGNORE INTO audio_admissions(guild_id,entry_id,actor_id,"
                            "text_channel_id,request_id,created_at) VALUES(?,?,?,?,?,?)",
                            (
                                plan.guild_id,
                                current,
                                plan.actor_id,
                                actor.text_channel_id,
                                plan.request_id,
                                self.clock(),
                            ),
                        )
                # Provenance is recorded inside the same command/admission transaction.
                source = source_row(conn, plan.guild_id, plan.request_id)
                conn.execute(
                    "UPDATE audio_admissions SET origin=?,enable_generation=?,channel_generation=?,"
                    "revoked=0,started=0 WHERE guild_id=? AND request_id=?",
                    (
                        source["origin"] if source else "structured",
                        source["enable_generation"] if source else None,
                        source["channel_generation"] if source else None,
                        plan.guild_id,
                        plan.request_id,
                    ),
                )
                after = self._snapshot(conn, plan.guild_id)
                if plan.action not in READ_ACTIONS:
                    conn.execute(
                        "INSERT INTO change_events VALUES(?,?,?,?,?,?,?,?)",
                        (
                            str(uuid.uuid4()),
                            plan.guild_id,
                            plan.actor_id,
                            plan.request_id,
                            plan.action.value,
                            json.dumps(before),
                            json.dumps(after),
                            self.clock(),
                        ),
                    )
                conn.execute(
                    "INSERT INTO command_requests VALUES(?,?,?,?,?,?)",
                    (
                        plan.guild_id,
                        plan.request_id,
                        plan.actor_id,
                        plan.fingerprint(),
                        json.dumps(result),
                        self.clock(),
                    ),
                )
                if self.before_commit:
                    self.before_commit()
                conn.execute(
                    "UPDATE message_requests SET state='committed' "
                    "WHERE guild_id=? AND request_id=?",
                    (plan.guild_id, plan.request_id),
                )
                return result
        except sqlite3.IntegrityError as exc:
            raise DomainError("constraint_conflict") from exc

    def _authorize_undo(self, conn: sqlite3.Connection, plan: ActionPlan, actor: Actor) -> None:
        if plan.action == Action.EDIT_UNDO:
            event = conn.execute(
                "SELECT action FROM change_events WHERE guild_id=? AND id=?",
                (plan.guild_id, plan.arguments["event_id"]),
            ).fetchone()
            if event and Action(event[0]) in undo.QUEUE_EDITS:
                authorize(
                    replace(plan, action=Action.QUEUE_CLEAR, arguments={}), actor, self.policy
                )

    def _consume_confirmation(
        self, conn: sqlite3.Connection, plan: ActionPlan, token: str | None
    ) -> None:
        if token is None:
            raise DomainError("confirmation_required")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = conn.execute(
            "SELECT * FROM confirmations WHERE token_hash=?", (token_hash,)
        ).fetchone()
        if not row or row["consumed"] or row["expires_at"] <= self.clock():
            raise DomainError("confirmation_expired")
        if (row["guild_id"], row["actor_id"], row["plan_hash"]) != (
            plan.guild_id,
            plan.actor_id,
            plan.fingerprint(),
        ):
            raise DomainError("confirmation_mismatch")
        conn.execute("UPDATE confirmations SET consumed=1 WHERE token_hash=?", (token_hash,))

    def _check_versions(self, conn: sqlite3.Connection, plan: ActionPlan) -> None:
        if plan.action == Action.EDIT_UNDO:
            undo.check(conn, plan)
        if plan.action == Action.PLAYLIST_GENERATE:
            reference = plan.arguments["reference_time"]
            if type(reference) not in {int, float} or not 0 <= self.clock() - reference <= 60:
                raise DomainError("generation_preview_expired")
            generated = select(conn, plan.guild_id, Rules.read(plan.arguments["rules"]), reference)
            if (
                generated.snapshot_hash != plan.arguments["snapshot_hash"]
                or generated.track_ids != plan.arguments["track_ids"]
            ):
                raise DomainError("generation_snapshot_conflict")
        if plan.inference is not None and self.inference_binding is not None:
            trace = plan.inference
            if (trace.provider, trace.profile_id, trace.config_hash) != self.inference_binding:
                raise DomainError("inference_profile_mismatch")
        if plan.origin == "natural_language":
            row = conn.execute(
                "SELECT generation FROM sessions WHERE guild_id=?", (plan.guild_id,)
            ).fetchone()
            if not row or row[0] != plan.execution_generation:
                raise DomainError("execution_generation_conflict")
        for target, expected in plan.expected_versions.items():
            table = "sessions" if target == "queue" else "playlists"
            query = f"SELECT version FROM {table} WHERE guild_id=?"
            args: tuple[Any, ...] = (plan.guild_id,)
            if table == "playlists":
                query += " AND id=?"
                args += (target,)
            row = conn.execute(query, args).fetchone()
            if not row or row[0] != expected:
                raise DomainError("version_conflict")
        target_id = plan.arguments.get("playlist_id")
        if target_id is not None and plan.action not in {
            Action.PLAYLIST_EXPORT,
            Action.PROPOSAL_CREATE,
        }:
            if target_id not in plan.expected_versions:
                raise DomainError("expected_version_required")
        if (
            plan.action
            in {
                Action.QUEUE_ENQUEUE,
                Action.QUEUE_REMOVE,
                Action.QUEUE_MOVE,
                Action.QUEUE_CLEAR,
                Action.QUEUE_SAVE,
            }
            | PLAYBACK_ACTIONS
        ):
            if "queue" not in plan.expected_versions:
                raise DomainError("expected_version_required")

    @staticmethod
    def _snapshot(conn: sqlite3.Connection, guild: str) -> dict[str, Any]:
        return {
            table: [
                dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE guild_id=?", (guild,))
            ]
            for table in (
                "tracks",
                "playlists",
                "playlist_entries",
                "sessions",
                "queue_entries",
                "proposals",
            )
        }

    @staticmethod
    def _playlist(
        conn: sqlite3.Connection, guild: str, identifier: str, *, deleted: bool = False
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM playlists WHERE guild_id=? AND id=?", (guild, identifier)
        ).fetchone()
        if not row or (row["deleted_at"] is not None) != deleted:
            raise DomainError("playlist_not_found")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _tracks_exist(conn: sqlite3.Connection, guild: str, tracks: list[str]) -> None:
        for track in tracks:
            if not conn.execute(
                "SELECT 1 FROM tracks WHERE guild_id=? AND id=?", (guild, track)
            ).fetchone():
                raise DomainError("track_not_found")

    @staticmethod
    def _reorder(conn: sqlite3.Connection, table: str, guild: str, ids: list[str]) -> None:
        # Positive temporary positions avoid unique/check collisions during moves.
        for i, identifier in enumerate(ids):
            conn.execute(
                f"UPDATE {table} SET position=? WHERE guild_id=? AND id=?",
                (10000 + i, guild, identifier),
            )
        for i, identifier in enumerate(ids):
            conn.execute(
                f"UPDATE {table} SET position=? WHERE guild_id=? AND id=?", (i, guild, identifier)
            )

    def _apply(self, conn: sqlite3.Connection, plan: ActionPlan) -> dict[str, Any]:
        guild, args, action = plan.guild_id, plan.arguments, plan.action
        if action == Action.EDIT_UNDO:
            return undo.apply(conn, plan, self.clock())
        if action == Action.PLAYLIST_IMPORT:
            tracks = []
            for reference in args["references"]:
                metadata = args.get("source_metadata", {}).get(reference["external_id"])
                existing = conn.execute(
                    "SELECT id FROM tracks WHERE guild_id=? AND source_type=? AND external_id=?",
                    (guild, reference["source_type"], reference["external_id"]),
                ).fetchone()
                if existing:
                    tracks.append(existing[0])
                    if metadata is not None:
                        conn.execute(
                            "UPDATE tracks SET metadata_json=?,metadata_updated_at=? "
                            "WHERE guild_id=? AND id=?",
                            (json.dumps(metadata), self.clock(), guild, existing[0]),
                        )
                else:
                    if reference["source_type"] == "approved_audio":
                        raise DomainError("audio_source_not_approved")
                    track = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO tracks(guild_id,id,source_type,external_id,"
                        "title,annotations_json) "
                        "VALUES(?,?,?,?,?,?)",
                        (
                            guild,
                            track,
                            reference["source_type"],
                            reference["external_id"],
                            reference["title"],
                            json.dumps(reference.get("annotations", {})),
                        ),
                    )
                    tracks.append(track)
                    if metadata is not None:
                        conn.execute(
                            "UPDATE tracks SET metadata_json=?,metadata_updated_at=? "
                            "WHERE guild_id=? AND id=?",
                            (json.dumps(metadata), self.clock(), guild, track),
                        )
            duplicates = len(tracks) - len(set(tracks))
            if not args.get("allow_duplicates", False):
                tracks = list(dict.fromkeys(tracks))
            identifier = args.get("playlist_id")
            if identifier is None:
                identifier = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                    (guild, identifier, args["name"], normalized_name(args["name"])),
                )
            else:
                self._playlist(conn, guild, identifier)
                if args.get("replace", False):
                    conn.execute(
                        "DELETE FROM playlist_entries WHERE guild_id=? AND playlist_id=?",
                        (guild, identifier),
                    )
                conn.execute(
                    "UPDATE playlists SET version=version+1 WHERE guild_id=? AND id=?",
                    (guild, identifier),
                )
            self._append(conn, guild, identifier, tracks, args.get("allow_duplicates", False))
            return {
                "playlist_id": identifier,
                "count": len(tracks),
                "duplicate_references": duplicates,
                "complete": args["complete"],
                "unavailable_count": args["unavailable_count"],
            }
        if action == Action.PLAYLIST_GENERATE:
            if not args["track_ids"]:
                raise DomainError("generation_no_matches")
            identifier = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                (guild, identifier, args["name"], normalized_name(args["name"])),
            )
            self._append(conn, guild, identifier, args["track_ids"], False)
            return {
                "playlist_id": identifier,
                "version": 0,
                "count": len(args["track_ids"]),
                "seed": args["rules"]["seed"],
            }
        if action in {Action.PLAYLIST_PLAY, Action.TRACK_PLAY}:
            if action == Action.PLAYLIST_PLAY:
                self._playlist(conn, guild, args["playlist_id"])
            tracks = (
                [args["track_id"]]
                if action == Action.TRACK_PLAY
                else [
                    r[0]
                    for r in conn.execute(
                        "SELECT track_id FROM playlist_entries "
                        "WHERE guild_id=? AND playlist_id=? ORDER BY position",
                        (guild, args["playlist_id"]),
                    )
                ]
            )
            if not tracks or (action == Action.PLAYLIST_PLAY and tracks != args["track_ids"]):
                raise DomainError("playlist_snapshot_conflict")
            for track_id in tracks:
                row = conn.execute(
                    "SELECT source_type FROM tracks WHERE guild_id=? AND id=?", (guild, track_id)
                ).fetchone()
                if not row or row[0] not in self.allowed_audio_sources:
                    raise DomainError("audio_source_not_approved")
            session = load_session(conn, guild)
            start_requested = session.state in {PlaybackState.DISCONNECTED, PlaybackState.IDLE}
            selected_entry = args.get("entry_id") if action == Action.TRACK_PLAY else None
            if selected_entry is not None:
                if not any(
                    entry.id == selected_entry and entry.track_id == tracks[0]
                    for entry in session.queue
                ):
                    raise DomainError("version_conflict")
                reused = selected_entry
            else:
                reused = (
                    next((entry.id for entry in session.queue if entry.track_id == tracks[0]), None)
                    if action == Action.TRACK_PLAY and start_requested
                    else None
                )
            if reused is None:
                self._append(conn, guild, None, tracks, args.get("allow_duplicates", False))
                session = load_session(conn, guild)
            if action == Action.TRACK_PLAY and session.state in {
                PlaybackState.DISCONNECTED,
                PlaybackState.IDLE,
            }:
                # An explicit single track starts first when idle; preserve earlier queued items.
                session.queue.sort(
                    key=lambda entry: entry.id != reused
                    if selected_entry is not None
                    else entry.track_id != args["track_id"]
                )
            # This command freshly approves its requested entries before admission rows are written.
            session.eligible_ids = (session.eligible_ids or frozenset()) | (
                {selected_entry}
                if selected_entry is not None
                else {e.id for e in session.queue if e.track_id in tracks}
            )
            session.version += 1
            if session.state == PlaybackState.DISCONNECTED:
                session.join()
                conn.execute(
                    "UPDATE sessions SET voice_channel_id=?,start_after_connect=1 WHERE guild_id=?",
                    (args["channel_id"], guild),
                )
            elif session.state == PlaybackState.IDLE:
                session.failed_tracks = 0
                session.start()
            save_session(conn, guild, session)
            return {
                "desired_state": session.state.value,
                "generation": session.generation,
                "queue_version": session.version,
                "effect_id": plan.request_id,
                "requested_title": conn.execute(
                    "SELECT title FROM tracks WHERE guild_id=? AND id=?", (guild, tracks[0])
                ).fetchone()[0],
                "queued": not start_requested,
                "start_requested": start_requested,
                "reused_entry_id": reused,
            }
        if action in PLAYBACK_ACTIONS:
            return {**apply_playback(conn, plan), "effect_id": plan.request_id}
        playlist_id = str(args.get("playlist_id", ""))
        if action == Action.PLAYLIST_LIST:
            return {
                "playlists": [
                    dict(r)
                    for r in conn.execute(
                        "SELECT id,name,version FROM playlists "
                        "WHERE guild_id=? AND deleted_at IS NULL "
                        "ORDER BY normalized_name",
                        (guild,),
                    )
                ]
            }
        if action == Action.CATALOG_REGISTER:
            if args["source_type"] not in {"youtube", "approved_audio", "fixture"}:
                raise DomainError("unsupported_source")
            existing = conn.execute(
                "SELECT id FROM tracks WHERE guild_id=? AND source_type=? AND external_id=?",
                (guild, args["source_type"], args["external_id"]),
            ).fetchone()
            if existing:
                return {"track_id": existing[0], "created": False}
            identifier = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO tracks(guild_id,id,source_type,external_id,title,metadata_json) "
                "VALUES(?,?,?,?,?,?)",
                (
                    guild,
                    identifier,
                    args["source_type"],
                    args["external_id"],
                    args["title"],
                    json.dumps(args.get("metadata", {})),
                ),
            )
            return {"track_id": identifier, "created": True}
        if action == Action.CATALOG_SEARCH:
            query = normalized_name(args["query"])
            rows = conn.execute("SELECT * FROM tracks WHERE guild_id=?", (guild,)).fetchall()
            return {
                "tracks": [
                    dict(r)
                    for r in rows
                    if query in normalized_name(r["title"])
                    or query in normalized_name(r["annotations_json"])
                ]
            }
        if action == Action.CATALOG_ANNOTATE:
            self._tracks_exist(conn, guild, [args["track_id"]])
            annotation = {k: args[k] for k in ("aliases", "tags", "creator") if k in args}
            conn.execute(
                "UPDATE tracks SET annotations_json=? WHERE guild_id=? AND id=?",
                (json.dumps(annotation), guild, args["track_id"]),
            )
            return {"updated": True}
        if action in {Action.PLAYLIST_CREATE, Action.PLAYLIST_COPY, Action.QUEUE_SAVE}:
            identifier = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                (guild, identifier, args["name"], normalized_name(args["name"])),
            )
            if action == Action.PLAYLIST_COPY:
                self._playlist(conn, guild, playlist_id)
                tracks = [
                    r[0]
                    for r in conn.execute(
                        "SELECT track_id FROM playlist_entries "
                        "WHERE guild_id=? AND playlist_id=? ORDER BY position",
                        (guild, playlist_id),
                    )
                ]
                self._append(conn, guild, identifier, tracks, True)
            if action == Action.QUEUE_SAVE:
                tracks = [
                    r[0]
                    for r in conn.execute(
                        "SELECT track_id FROM queue_entries WHERE guild_id=? ORDER BY position",
                        (guild,),
                    )
                ]
                if args.get("include_current"):
                    current = conn.execute(
                        "SELECT current_track_id FROM sessions WHERE guild_id=?", (guild,)
                    ).fetchone()[0]
                    if current:
                        tracks.insert(0, current)
                self._append(conn, guild, identifier, tracks, True)
            return {"playlist_id": identifier, "version": 0}
        if action == Action.PLAYLIST_RESTORE:
            deleted = self._playlist(conn, guild, playlist_id, deleted=True)
            if deleted["deleted_at"] + 30 * 86400 <= self.clock():
                raise DomainError("restore_expired")
            conn.execute(
                "UPDATE playlists SET deleted_at=NULL,version=version+1 WHERE guild_id=? AND id=?",
                (guild, playlist_id),
            )
            return {"restored": True}
        if action.value.startswith("playlist."):
            self._playlist(conn, guild, playlist_id)
            if action == Action.PLAYLIST_EXPORT:
                return {
                    "schema_version": 1,
                    "tracks": [
                        {
                            "source_type": r["source_type"],
                            "external_id": r["external_id"],
                            "title": r["title"],
                            "annotations": json.loads(r["annotations_json"]),
                        }
                        for r in conn.execute(
                            "SELECT t.source_type,t.external_id,t.title,t.annotations_json "
                            "FROM playlist_entries e "
                            "JOIN tracks t ON t.guild_id=e.guild_id AND t.id=e.track_id "
                            "WHERE e.guild_id=? AND e.playlist_id=? ORDER BY e.position",
                            (guild, playlist_id),
                        )
                    ],
                }
            if action == Action.PLAYLIST_RENAME:
                conn.execute(
                    "UPDATE playlists SET name=?,normalized_name=? WHERE guild_id=? AND id=?",
                    (args["name"], normalized_name(args["name"]), guild, playlist_id),
                )
            elif action == Action.PLAYLIST_DELETE:
                conn.execute(
                    "UPDATE playlists SET deleted_at=? WHERE guild_id=? AND id=?",
                    (self.clock(), guild, playlist_id),
                )
            elif action == Action.PLAYLIST_ADD:
                self._append(
                    conn, guild, playlist_id, args["track_ids"], args.get("allow_duplicates", False)
                )
            else:
                self._edit_entries(conn, guild, args, playlist_id)
            conn.execute(
                "UPDATE playlists SET version=version+1 WHERE guild_id=? AND id=?",
                (guild, playlist_id),
            )
            return {
                "playlist_id": playlist_id,
                "version": conn.execute(
                    "SELECT version FROM playlists WHERE guild_id=? AND id=?", (guild, playlist_id)
                ).fetchone()[0],
            }
        if action == Action.QUEUE_SHOW:
            session_data = dict(
                conn.execute("SELECT * FROM sessions WHERE guild_id=?", (guild,)).fetchone()
            )
            current_track = conn.execute(
                "SELECT title,source_type,external_id FROM tracks WHERE guild_id=? AND id=?",
                (guild, session_data["current_track_id"]),
            ).fetchone()
            session_data["current_title"] = current_track[0] if current_track else None
            session_data["current_source_type"] = current_track[1] if current_track else None
            session_data["current_external_id"] = current_track[2] if current_track else None
            entries = [
                dict(r)
                for r in conn.execute(
                    "SELECT q.*,t.title FROM queue_entries q JOIN tracks t "
                    "ON t.guild_id=q.guild_id AND t.id=q.track_id "
                    "WHERE q.guild_id=? ORDER BY position",
                    (guild,),
                )
            ]
            for entry in entries:
                entry["approval"] = (
                    "승인됨" if admission_valid(conn, guild, entry["id"]) else "승인 만료"
                )
            return {
                "session": session_data,
                "entries": entries,
            }
        if action in {
            Action.QUEUE_ENQUEUE,
            Action.QUEUE_REMOVE,
            Action.QUEUE_MOVE,
            Action.QUEUE_CLEAR,
        }:
            if action == Action.QUEUE_ENQUEUE:
                self._append(
                    conn, guild, None, args["track_ids"], args.get("allow_duplicates", False)
                )
            elif action == Action.QUEUE_CLEAR:
                conn.execute("DELETE FROM queue_entries WHERE guild_id=?", (guild,))
            else:
                self._edit_entries(conn, guild, args, None)
            conn.execute("UPDATE sessions SET version=version+1 WHERE guild_id=?", (guild,))
            return {
                "queue_version": conn.execute(
                    "SELECT version FROM sessions WHERE guild_id=?", (guild,)
                ).fetchone()[0]
            }
        if action == Action.PROPOSAL_CREATE:
            self._playlist(conn, guild, playlist_id)
            self._tracks_exist(conn, guild, [args["track_id"]])
            identifier = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO proposals VALUES(?,?,?,?,?,'pending',?)",
                (guild, identifier, plan.actor_id, playlist_id, args["track_id"], self.clock()),
            )
            return {"proposal_id": identifier}
        if action in {Action.PROPOSAL_APPROVE, Action.PROPOSAL_REJECT}:
            proposal = conn.execute(
                "SELECT * FROM proposals WHERE guild_id=? AND id=?", (guild, args["proposal_id"])
            ).fetchone()
            if not proposal or proposal["status"] != "pending":
                raise DomainError("proposal_not_pending")
            if action == Action.PROPOSAL_APPROVE:
                target = self._playlist(conn, guild, proposal["playlist_id"])
                if plan.expected_versions.get(target["id"]) != target["version"]:
                    raise DomainError("version_conflict")
                self._append(conn, guild, target["id"], [proposal["track_id"]], False)
                conn.execute(
                    "UPDATE playlists SET version=version+1 WHERE guild_id=? AND id=?",
                    (guild, target["id"]),
                )
            conn.execute(
                "UPDATE proposals SET status=? WHERE guild_id=? AND id=?",
                (
                    "approved" if action == Action.PROPOSAL_APPROVE else "rejected",
                    guild,
                    args["proposal_id"],
                ),
            )
            return {"updated": True}
        if action == Action.PROPOSAL_LIST:
            return {
                "proposals": [
                    dict(row)
                    for row in conn.execute(
                        "SELECT p.id,p.status,t.title,l.name FROM proposals p "
                        "JOIN tracks t ON t.guild_id=p.guild_id AND t.id=p.track_id "
                        "JOIN playlists l ON l.guild_id=p.guild_id AND l.id=p.playlist_id "
                        "WHERE p.guild_id=? AND p.status='pending' AND l.deleted_at IS NULL "
                        "ORDER BY p.created_at,p.id",
                        (guild,),
                    )
                ]
            }
        if action == Action.SETTINGS_UPDATE:
            if set(args["settings"]) - {"duplicates_allowed", "recent_exclusion_days"}:
                raise DomainError("unsupported_setting")
            conn.execute(
                "UPDATE guild_settings SET settings_json=?,version=version+1 WHERE guild_id=?",
                (json.dumps(args["settings"]), guild),
            )
            return {"updated": True}
        raise DomainError("action_not_implemented")

    def _append(
        self,
        conn: sqlite3.Connection,
        guild: str,
        playlist_id: str | None,
        tracks: list[str],
        allow_duplicates: bool,
    ) -> None:
        self._tracks_exist(conn, guild, tracks)
        table = "playlist_entries" if playlist_id else "queue_entries"
        clause = "guild_id=?" + (" AND playlist_id=?" if playlist_id else "")
        values = (guild, playlist_id) if playlist_id else (guild,)
        rows = conn.execute(
            f"SELECT track_id FROM {table} WHERE {clause} ORDER BY position", values
        ).fetchall()
        if len(rows) + len(tracks) > 500:
            raise DomainError("entry_limit")
        if not allow_duplicates and (
            len(set(tracks)) != len(tracks) or set(tracks) & {r[0] for r in rows}
        ):
            raise DomainError("duplicate_track")
        for i, track in enumerate(tracks, start=len(rows)):
            entry_id = str(uuid.uuid4())
            if playlist_id:
                conn.execute(
                    "INSERT INTO playlist_entries VALUES(?,?,?,?,?)",
                    (guild, playlist_id, entry_id, track, i),
                )
            else:
                conn.execute(
                    "INSERT INTO queue_entries VALUES(?,?,?,?)", (guild, entry_id, track, i)
                )

    def _edit_entries(
        self, conn: sqlite3.Connection, guild: str, args: dict[str, Any], playlist_id: str | None
    ) -> None:
        table = "playlist_entries" if playlist_id else "queue_entries"
        clause = "guild_id=?" + (" AND playlist_id=?" if playlist_id else "")
        values = (guild, playlist_id) if playlist_id else (guild,)
        ids = [
            r[0]
            for r in conn.execute(
                f"SELECT id FROM {table} WHERE {clause} ORDER BY position", values
            )
        ]
        identifier = args["entry_id"]
        if identifier not in ids:
            raise DomainError("entry_not_found")
        ids.remove(identifier)
        if "position" in args:
            if args["position"] > len(ids):
                raise DomainError("invalid_position")
            ids.insert(args["position"], identifier)
        else:
            conn.execute(f"DELETE FROM {table} WHERE guild_id=? AND id=?", (guild, identifier))
        self._reorder(conn, table, guild, ids)

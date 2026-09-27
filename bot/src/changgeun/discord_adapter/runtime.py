"""Async audio boundary. SQL never stays locked while Discord/FFmpeg is awaited."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import discord

from changgeun.application.watch import admission_valid
from changgeun.domain.models import Action, DomainError
from changgeun.playback.persistence import load_session, save_session
from changgeun.playback.state import PlaybackState
from changgeun.providers.media import ApprovedAudioResolver
from changgeun.providers.youtube_audio import MediaResolver
from changgeun.storage.database import Database


class AudioRuntime:
    def __init__(
        self,
        client: discord.Client,
        db: Database,
        resolver: ApprovedAudioResolver,
        notify: Callable[[str, str], Awaitable[None]],
        validate_entry: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self.client, self.db, self.resolver, self.notify = client, db, resolver, notify
        self.validate_entry = validate_entry
        self.loop: asyncio.AbstractEventLoop | None = None
        self.empty_since: dict[str, float] = {}
        self.state_since: dict[str, tuple[PlaybackState, float]] = {}
        self.preparing: dict[str, asyncio.Task[Any]] = {}

    def recover(self, guild_ids: frozenset[str]) -> None:
        with self.db.transaction() as conn:
            for guild in guild_ids:
                session = load_session(conn, guild)
                session.recover_restart()
                save_session(conn, guild, session)
                conn.execute(
                    "UPDATE sessions SET voice_channel_id=NULL,start_after_connect=0 "
                    "WHERE guild_id=?",
                    (guild,),
                )
                conn.execute("UPDATE confirmations SET consumed=1 WHERE guild_id=?", (guild,))

    def generation_current(self, guild: str, generation: int) -> bool:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT generation FROM sessions WHERE guild_id=?", (guild,)
            ).fetchone()
            return bool(row and row[0] == generation)
        finally:
            conn.close()

    async def apply(self, guild_id: str, action: Action, result: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT status FROM external_effects WHERE guild_id=? AND request_id=?",
                (guild_id, result["effect_id"]),
            ).fetchone()
            if existing:
                return  # Never repeat a completed or unknown external attempt.
            current = load_session(conn, guild_id)
            if (
                current.generation != result["generation"]
                or current.version != result["queue_version"]
            ):
                raise DomainError("execution_generation_conflict")
            conn.execute(
                "INSERT INTO external_effects VALUES(?,?,?,'claimed')",
                (guild_id, result["effect_id"], result["generation"]),
            )
        try:
            await self._apply(guild_id, action, result)
        except BaseException:
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE external_effects SET status='failed_or_unknown' "
                    "WHERE guild_id=? AND request_id=?",
                    (guild_id, result["effect_id"]),
                )
            raise
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE external_effects SET status='completed' WHERE guild_id=? AND request_id=?",
                (guild_id, result["effect_id"]),
            )

    async def _apply(self, guild_id: str, action: Action, result: dict[str, Any]) -> None:
        if action in {Action.VOICE_LEAVE, Action.PLAYBACK_STOP, Action.PLAYBACK_SKIP}:
            task = self.preparing.get(guild_id)
            if task and task is not asyncio.current_task():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        guild = self.client.get_guild(int(guild_id))
        if guild is None:
            raise DomainError("guild_unavailable")
        generation = result["generation"]
        if not self.generation_current(guild_id, generation):
            raise DomainError("execution_generation_conflict")
        if action in {Action.PLAYLIST_PLAY, Action.TRACK_PLAY} and not result.get(
            "start_requested", True
        ):
            return  # Append only; do not reconnect or prepare the current entry twice.
        self.loop = asyncio.get_running_loop()
        voice = guild.voice_client if isinstance(guild.voice_client, discord.VoiceClient) else None
        if action in {Action.VOICE_JOIN, Action.VOICE_MOVE} or (
            action in {Action.PLAYLIST_PLAY, Action.TRACK_PLAY}
            and result["desired_state"] == "connecting"
        ):
            conn = self.db.connect()
            try:
                channel_id = conn.execute(
                    "SELECT voice_channel_id FROM sessions WHERE guild_id=?", (guild_id,)
                ).fetchone()[0]
            finally:
                conn.close()
            channel = guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.VoiceChannel):
                raise DomainError("voice_channel_not_allowed")
            if guild.me is None:
                raise DomainError("permissions_unavailable")
            permissions = channel.permissions_for(guild.me)
            if not permissions.connect or not permissions.speak:
                raise DomainError("bot_voice_permissions_missing")
            try:
                if voice:
                    await voice.disconnect(force=True)
                connected: discord.VoiceClient = await channel.connect(
                    timeout=15, reconnect=False, cls=discord.VoiceClient
                )
                if not self.generation_current(guild_id, generation):
                    await connected.disconnect(force=True)
                    return
                with self.db.transaction() as conn:
                    session = load_session(conn, guild_id)
                    if session.connected(generation):
                        auto_start = conn.execute(
                            "SELECT start_after_connect FROM sessions WHERE guild_id=?", (guild_id,)
                        ).fetchone()[0]
                        if auto_start:
                            session.failed_tracks = 0
                            eligible = any(
                                e.id in (session.eligible_ids or frozenset()) for e in session.queue
                            )
                            if eligible:
                                session.start()
                            else:
                                auto_start = False
                            conn.execute(
                                "UPDATE sessions SET start_after_connect=0 WHERE guild_id=?",
                                (guild_id,),
                            )
                        conn.execute(
                            "UPDATE sessions SET start_after_connect=0 WHERE guild_id=?",
                            (guild_id,),
                        )
                        save_session(conn, guild_id, session)
                        next_generation = session.generation
                    else:
                        auto_start = False
                        next_generation = generation
                if auto_start:
                    await self._start_audio(guild_id, next_generation)
            except Exception:
                self._fail_connection(guild_id, generation)
                raise DomainError("voice_connection_failed") from None
            return
        if action in {Action.VOICE_LEAVE, Action.PLAYBACK_STOP, Action.PLAYBACK_SKIP} and voice:
            voice.stop()
        if action == Action.VOICE_LEAVE and voice:
            await voice.disconnect(force=True)
        elif action == Action.PLAYBACK_PAUSE and voice:
            voice.pause()
        elif action == Action.PLAYBACK_RESUME and voice:
            voice.resume()
        elif action == Action.PLAYBACK_VOLUME and voice:
            conn = self.db.connect()
            try:
                volume = conn.execute(
                    "SELECT volume FROM sessions WHERE guild_id=?", (guild_id,)
                ).fetchone()[0]
            finally:
                conn.close()
            if isinstance(voice.source, discord.PCMVolumeTransformer):
                voice.source.volume = volume / 100
        if action in {
            Action.PLAYBACK_START,
            Action.PLAYBACK_SKIP,
            Action.PLAYLIST_PLAY,
            Action.TRACK_PLAY,
        }:
            await self._start_audio(guild_id, generation)

    def _fail_connection(self, guild: str, generation: int) -> None:
        with self.db.transaction() as conn:
            session = load_session(conn, guild)
            if session.generation == generation:
                session.stop(leave=True)
                conn.execute("UPDATE sessions SET start_after_connect=0 WHERE guild_id=?", (guild,))
                save_session(conn, guild, session)

    async def _start_audio(self, guild_id: str, generation: int) -> None:
        guild = self.client.get_guild(int(guild_id))
        voice = (
            guild.voice_client
            if guild and isinstance(guild.voice_client, discord.VoiceClient)
            else None
        )
        if guild is None or voice is None or not voice.is_connected():
            self._fail_connection(guild_id, generation)
            raise DomainError("voice_not_connected")
        conn = self.db.connect()
        try:
            session = load_session(conn, guild_id)
            if session.generation != generation or session.state != PlaybackState.RESOLVING:
                return
            if session.current is None:
                return
            track = conn.execute(
                "SELECT source_type,external_id FROM tracks WHERE guild_id=? AND id=?",
                (guild_id, session.current.track_id),
            ).fetchone()
        finally:
            conn.close()
        try:
            task = asyncio.current_task()
            assert task is not None
            self.preparing[guild_id] = task
            entry_id = session.current.id

            async def prepare() -> discord.PCMVolumeTransformer[discord.AudioSource]:
                if self.validate_entry:
                    await self.validate_entry(guild_id, entry_id)
                if isinstance(self.resolver, MediaResolver):
                    prepared = await self.resolver.prepare(
                        track["source_type"], track["external_id"]
                    )
                else:
                    prepared = discord.FFmpegPCMAudio(
                        str(self.resolver.resolve(track["source_type"], track["external_id"])),
                        options="-vn -loglevel error",
                    )
                source = discord.PCMVolumeTransformer(prepared, volume=session.volume / 100)
                try:
                    if self.validate_entry:
                        await self.validate_entry(guild_id, entry_id)
                except BaseException:
                    source.cleanup()
                    raise
                return source

            async with asyncio.timeout(25):
                source = await prepare()
            if not self.generation_current(guild_id, generation):
                source.cleanup()
                return
            assert self.loop is not None
            loop = self.loop

            def after(error: Exception | None) -> None:
                asyncio.run_coroutine_threadsafe(
                    self._finished(guild_id, generation, failed=error is not None), loop
                )

            # The same SQLite write boundary serializes watch changes and actual voice.play.
            # No awaited I/O occurs between admission check, start and its committed marker.
            try:
                with self.db.transaction() as conn:
                    session = load_session(conn, guild_id)
                    if not session.resolved(generation):
                        source.cleanup()
                        return
                    if not admission_valid(conn, guild_id, entry_id):
                        raise DomainError("watch_admission_expired")
                    voice.play(source, after=after)
                    conn.execute(
                        "UPDATE audio_admissions SET started=1 WHERE guild_id=? AND entry_id=?",
                        (guild_id, entry_id),
                    )
                    save_session(conn, guild_id, session)
            except BaseException:
                source.cleanup()
                raise
        except DomainError as exc:
            if exc.code in {
                "watch_admission_expired",
                "watch_request_revoked",
                "audio_admission_missing",
            }:
                await self.expired(guild_id, generation)
            else:
                await self._finished(guild_id, generation, failed=True)
        except Exception:
            await self._finished(guild_id, generation, failed=True)
        finally:
            if self.preparing.get(guild_id) is asyncio.current_task():
                self.preparing.pop(guild_id, None)

    async def expired(self, guild: str, generation: int) -> None:
        """Keep the entry/order, skip revoked approvals without a media failure."""
        with self.db.transaction() as conn:
            session = load_session(conn, guild)
            if session.generation != generation or session.state != PlaybackState.RESOLVING:
                return
            session.stop()
            if any(e.id in (session.eligible_ids or frozenset()) for e in session.queue):
                session.start()
            save_session(conn, guild, session)
            next_generation = session.generation
            start_next = session.state == PlaybackState.RESOLVING
        if start_next:
            await self._start_audio(guild, next_generation)

    async def _finished(self, guild: str, generation: int, *, failed: bool) -> None:
        with self.db.transaction() as conn:
            session = load_session(conn, guild)
            completed_entry = session.current
            if failed:
                session.retry_count = 1
            if not session.finished(generation, failed=failed):
                return
            if completed_entry and not failed:
                conn.execute(
                    "INSERT INTO playback_history VALUES(?,?,?,?)",
                    (guild, completed_entry.id, completed_entry.track_id, time.time()),
                )
            save_session(conn, guild, session)
            next_generation = session.generation
            retry_or_next = session.state == PlaybackState.RESOLVING
            stopped = session.failed_tracks >= 3
        if stopped:
            await self.notify(guild, "세 곡 연속 재생에 실패해서 멈췄어. /대기열 보기로 확인해줘.")
        if retry_or_next:
            await self._start_audio(guild, next_generation)

    async def check_auto_leave(self, guild_ids: frozenset[str]) -> None:
        now = time.monotonic()
        for identifier in guild_ids:
            guild = self.client.get_guild(int(identifier))
            voice = (
                guild.voice_client
                if guild and isinstance(guild.voice_client, discord.VoiceClient)
                else None
            )
            if not voice or not isinstance(voice.channel, discord.VoiceChannel):
                continue
            listeners = sum(not member.bot for member in voice.channel.members)
            if listeners:
                self.empty_since.pop(identifier, None)
            else:
                self.empty_since.setdefault(identifier, now)
            with self.db.transaction() as conn:
                session = load_session(conn, identifier)
                last_state, since = self.state_since.get(identifier, (session.state, now))
                if last_state != session.state:
                    since = now
                self.state_since[identifier] = (session.state, since)
                due = session.auto_leave_due(
                    now=now,
                    empty_since=self.empty_since.get(identifier),
                    idle_since=since if session.state == PlaybackState.IDLE else None,
                    paused_since=since if session.state == PlaybackState.PAUSED else None,
                    listener_count=listeners,
                )
                if not due:
                    continue
                session.stop(leave=True)
                save_session(conn, identifier, session)
            voice.stop()
            await voice.disconnect(force=True)

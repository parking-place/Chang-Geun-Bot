"""Korean slash commands and buttons, all mutations use the trusted executor."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import random
import re
import sqlite3
import time
from collections import Counter
from dataclasses import replace
from typing import Any

import discord
import httpx
from discord import app_commands

from changgeun.application import undo
from changgeun.application.executor import Executor
from changgeun.application.generation import Rules, select
from changgeun.application.transfer import parse_export
from changgeun.application.watch import (
    WatchStore,
    admission_valid,
    bind_source,
    policy_for_request,
    source_row,
)
from changgeun.config import BotConfig
from changgeun.discord_adapter import watch as watch_commands
from changgeun.discord_adapter.mention import MentionEntry
from changgeun.discord_adapter.prefix import MessageLedger, parse_prefix
from changgeun.discord_adapter.runtime import AudioRuntime
from changgeun.domain.models import (
    PLAYBACK_ACTIONS,
    Action,
    ActionPlan,
    Actor,
    DomainError,
    Policy,
    normalized_name,
)
from changgeun.nlp.client import GatewayClient
from changgeun.nlp.pipeline import Pipeline
from changgeun.providers.media import YouTubeMetadata
from changgeun.providers.youtube import YouTubeData
from changgeun.providers.youtube_audio import MediaResolver
from changgeun.storage.database import Database

ERRORS = {
    "dj_required": "곡 편집과 재생 제어에는 DJ 역할이 필요해. 곡 제안은 보낼 수 있어.",
    "same_voice_required": "봇과 같은 허용 음성채널에 들어간 뒤 다시 요청해줘.",
    "version_conflict": "그동안 목록이나 대기열이 바뀌었어. 다시 선택해줘.",
    "constraint_conflict": "이름이나 곡 참조가 겹쳐서 저장하지 않았어.",
    "duplicate_track": "이미 있는 곡이야. 중복 허용을 선택하면 따로 추가할 수 있어.",
    "confirmation_expired": "확인 시간이 끝났어. 다시 요청해줘.",
    "confirmation_mismatch": "이 확인은 다른 요청에 사용할 수 없어.",
    "audio_source_not_approved": "링크는 저장할 수 있지만 현재 재생 소스로는 지원하지 않아.",
    "queue_empty": "대기열이 비어 있어. 먼저 곡이나 목록을 추가해줘.",
    "playlist_not_found": "목록을 찾지 못했어. /목록 보기에서 다시 골라줘.",
    "track_not_found": "곡을 찾지 못했어. /검색에서 골라줘.",
    "voice_connection_failed": "음성 연결에 실패했어. 채널 권한을 확인해줘.",
    "voice_not_connected": "먼저 /입장으로 음성채널에 들어가줘.",
    "not_playing": "지금 재생 중인 곡이 없어.",
    "not_paused": "지금 일시정지 상태가 아니야.",
    "no_current_track": "지금 선택된 현재곡이 없어.",
    "generation_no_matches": "조건에 맞는 등록 곡이 없어. 태그나 최근 제외 조건을 바꿔줘.",
    "generation_snapshot_conflict": "미리보기 이후 카탈로그나 재생 기록이 바뀌었어. 다시 생성해줘.",
    "generation_preview_expired": "목록 생성 미리보기가 만료됐어. 다시 생성해줘.",
    "invalid_generation_rules": "곡 수는 1~100, 최근 제외는 0~365일로 지정해줘.",
    "restore_expired": "삭제한 지 30일이 지나 이 목록을 복원할 수 없어.",
    "proposal_not_pending": "이미 처리됐거나 찾을 수 없는 제안이야.",
    "youtube_key_missing": (
        "YouTube 공식 API 키가 아직 설정되지 않았어. 링크 참조 등록은 사용할 수 있어."
    ),
    "youtube_quota_or_access": (
        "YouTube API 권한이나 할당량 때문에 읽지 못했어. 자동 재시도하지 않았어."
    ),
    "partial_import_requires_consent": (
        "일부만 읽은 목록이야. 부분읽기허용을 켜면 미리보기 후 성공 항목만 저장할 수 있어."
    ),
    "invalid_import_file": "이 봇이 내보낸 형식의 JSON 파일을 선택해줘.",
    "invalid_import_references": "곡 참조·태그나 파일 형식이 맞지 않아. 저장하지 않았어.",
    "youtube_unsupported": "길이를 확인할 수 있는 30분 이하 공개 영상만 재생할 수 있어.",
    "youtube_prepare_failed": "영상 오디오를 준비하지 못했어. 다른 공개 영상을 선택해줘.",
    "media_capacity": "오디오 준비 요청이 많아. 잠시 뒤 다시 요청해줘.",
    "watch_request_revoked": "주시 설정이 바뀌어 이 요청을 취소했어. 새 요청을 보내줘.",
    "queue_no_approval": "시작 가능한 승인이 없어. 원하는 곡을 새로 요청해줘.",
    "watch_admission_expired": "주시 재생 승인이 만료됐어. 원하는 곡을 새로 요청해줘.",
    "message_request_cancelled": "원문이 수정·삭제되어 이 요청을 취소했어.",
}


def safe(value: str) -> str:
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value))


def natural_failure(exc: Exception) -> tuple[str, str]:
    """Return a bounded category and safe next action, never an upstream body."""
    if isinstance(exc, DomainError):
        code = exc.code
        if code in {"guild_not_allowed", "text_channel_not_allowed", "watch_unavailable"}:
            return "channel", "이 채널에서는 사용할 수 없어. 허용된 채널이나 /도움말을 확인해줘."
        if code in {
            "dj_required",
            "same_voice_required",
            "voice_channel_not_allowed",
            "permissions_unavailable",
        }:
            return "permission", ERRORS.get(code, "권한과 음성채널을 확인한 뒤 다시 요청해줘.")
        if code in {
            "watch_request_revoked",
            "message_request_cancelled",
            "execution_generation_conflict",
        }:
            return (
                "revoked",
                "요청 중 상태가 바뀌어 실행하지 않았어. 현재 상태를 확인하고 새로 요청해줘.",
            )
        if code in {"user_cooldown", "inference_deadline", "execution_deadline_expired"}:
            return (
                "deadline",
                "요청을 제때 완료하지 못했어. 잠시 뒤 새로 요청하거나 슬래시 명령을 사용해줘.",
            )
        if code in {
            "inference_profile_mismatch",
            "inference_response_binding_mismatch",
            "inference_usage_mismatch",
            "inference_forward_provenance_mismatch",
            "invalid_inference_response",
            "inference_response_too_large",
        }:
            return "gateway", "자연어 판단을 안전하게 확인하지 못했어. 슬래시 명령을 사용해줘."
        return "invalid", "요청을 실행하지 않았어. 대상과 현재 상태를 확인해줘."
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 429:
            return "busy", "자연어 요청이 혼잡해. 잠시 뒤 새로 요청하거나 슬래시 명령을 사용해줘."
        return "gateway", "자연어 연결을 사용할 수 없어. 슬래시 명령을 사용해줘."
    if isinstance(exc, (TimeoutError, httpx.RequestError)):
        return "gateway", "자연어 연결이 지연되거나 끊겼어. 슬래시 명령을 사용해줘."
    return "unknown", "자연어 요청을 완료하지 못했어. 슬래시 명령을 사용해줘."


def help_text(
    actor: Actor | None,
    policy: Policy,
    *,
    youtube_audio: bool,
    prefix_enabled: bool,
    watched_here: bool,
) -> str:
    """Render only the commands and watch state visible from this channel."""
    if actor is None or actor.text_channel_id not in policy.text_channel_ids:
        return "이 채널에서는 사용법만 안내할게. 허용된 채널에서 /도움말을 다시 열어줘."
    lines = ["목록은 /목록 보기, 등록 곡은 /검색에서 확인할 수 있어."]
    if actor.role_ids & policy.dj_role_ids or policy.admin_dj_override and actor.manage_guild:
        lines.append("DJ는 /목록 생성 → /곡 등록 → /곡 추가로 목록을 만들고 /재생으로 틀 수 있어.")
    else:
        lines.append("곡을 추천하려면 /곡제안을 사용해줘. 재생·편집은 DJ에게 요청해줘.")
    if youtube_audio:
        lines.append(
            "공개 YouTube 영상(30분 이하)은 /재생 곡:링크로 틀 수 있어. https://는 생략해도 돼."
        )
    else:
        lines.append("YouTube 링크는 참조 저장, 음성 재생은 승인 음원을 지원해.")
    lines.append("자연어는 /부탁으로 한 가지 동작을 요청할 수 있어.")
    if prefix_enabled and watched_here:
        lines.append("이 채널에서는 ‘!!창근아 목록 보여줘’처럼 말해줘.")
    elif prefix_enabled:
        lines.append("이 채널의 접두어 주시는 켜져 있지 않아.")
    if actor.manage_guild:
        lines.append(
            "서버 관리자는 /주시 목록·점검으로 상태를 확인하고 "
            "/주시 추가·제거·켜기·끄기로 관리할 수 있어."
        )
    return "\n".join(lines)


class ConfirmationView(discord.ui.View):
    def __init__(self, client: ChangGeunClient, plan: ActionPlan, token: str) -> None:
        super().__init__(timeout=60)
        self.client, self.plan, self.token = client, plan, token

    @discord.ui.button(label="변경 확인", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.client.submit_plan(interaction, self.plan, confirmation=self.token)
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if str(interaction.user.id) != self.plan.actor_id:
            await interaction.response.send_message("요청한 사람만 취소할 수 있어.", ephemeral=True)
            return
        with self.client.db.transaction() as conn:
            conn.execute(
                "UPDATE confirmations SET consumed=1 WHERE token_hash=?",
                (hashlib.sha256(self.token.encode()).hexdigest(),),
            )
        await interaction.response.edit_message(content="변경을 취소했어.", view=None)
        self.stop()


class PlaybackView(discord.ui.View):
    def __init__(self, client: ChangGeunClient) -> None:
        super().__init__(timeout=300)
        self.client = client

    @discord.ui.button(label="일시정지", style=discord.ButtonStyle.secondary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button[Any]) -> None:
        await self.client.submit(interaction, Action.PLAYBACK_PAUSE)

    @discord.ui.button(label="계속", style=discord.ButtonStyle.primary)
    async def resume(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.client.submit(interaction, Action.PLAYBACK_RESUME)

    @discord.ui.button(label="넘기기", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button[Any]) -> None:
        await self.client.submit(interaction, Action.PLAYBACK_SKIP)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger)
    async def stop_playback(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.client.submit(interaction, Action.PLAYBACK_STOP)


class YouTubeSelection(discord.ui.View):
    def __init__(
        self,
        client: ChangGeunClient,
        actor: Actor,
        identifiers: list[str],
        descriptions: list[str],
        request_id: str,
        version: int,
        generation: int,
    ) -> None:
        super().__init__(timeout=60)
        self.client, self.actor, self.identifiers = client, actor, tuple(identifiers)
        self.request_id, self.version, self.generation = request_id, version, generation
        self.deadline = time.monotonic() + 60
        self.used = False

        class Picker(discord.ui.Select[Any]):
            async def callback(self, interaction: discord.Interaction) -> None:
                await selected(interaction)

        choice = Picker(
            placeholder="재생할 영상을 선택해줘",
            options=[
                discord.SelectOption(label=title[:100], value=str(i))
                for i, title in enumerate(descriptions)
            ],
        )

        async def selected(interaction: discord.Interaction) -> None:
            if (
                str(interaction.user.id),
                str(interaction.guild_id),
                str(interaction.channel_id),
            ) != (actor.user_id, actor.guild_id, actor.text_channel_id):
                await interaction.response.send_message(
                    "요청한 사람만 선택할 수 있어.", ephemeral=True
                )
                return
            if self.used or time.monotonic() >= self.deadline:
                await interaction.response.send_message(
                    "선택 시간이 끝났어. 다시 검색해줘.", ephemeral=True
                )
                return
            value = choice.values[0]
            if not value.isdecimal() or not 0 <= int(value) < len(self.identifiers):
                return
            self.used = True
            fresh = await client.fresh_actor(interaction)
            plan = ActionPlan(
                request_id + ".select",
                fresh.guild_id,
                fresh.user_id,
                Action.TRACK_PLAY,
                {
                    "track_id": "youtube:" + self.identifiers[int(value)],
                    "channel_id": actor.bot_voice_channel_id or actor.voice_channel_id,
                },
                {"queue": version},
                "button",
                generation,
                expires_at=time.time() + max(0, self.deadline - time.monotonic()),
            )
            await client.submit_plan(interaction, plan, actor=fresh)
            self.stop()

        self.add_item(choice)


class ChangGeunClient(discord.Client):
    def __init__(self, config: BotConfig) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        intents.messages = True
        intents.message_content = config.prefix.enabled
        super().__init__(
            intents=intents, max_messages=None, allowed_mentions=discord.AllowedMentions.none()
        )
        self.config = config
        self.db = Database(config.database_path)
        for guild in config.policy.guild_ids:
            self.db.ensure_guild(guild)
        self.executor = Executor(
            self.db,
            config.policy,
            youtube_audio_enabled=config.youtube_audio_enabled,
            prefix_enabled=config.prefix.enabled,
        )
        self.watch = WatchStore(self.db)
        self.watch_cooldowns: dict[tuple[str, str], float] = {}
        self.watch_diagnostics: set[str] = set()
        self.message_ledger = MessageLedger(self.db)
        self.message_tasks: dict[str, asyncio.Task[Any]] = {}
        self.message_owners: dict[str, tuple[str, str]] = {}
        self.message_cooldowns: dict[tuple[str, str], float] = {}
        self.prefix_ready = False
        self.prefix_status = "disabled"
        self.natural_failures: Counter[str] = Counter()
        self.tree = app_commands.CommandTree(self)
        self.audio = AudioRuntime(
            self,
            self.db,
            MediaResolver(
                config.audio_root,
                config.audio_mapping,
                config.youtube_audio_enabled,
                config.youtube_js_runtime,
            ),
            self.notify,
            self.validate_audio_entry,
        )
        self.timer_task: asyncio.Task[None] | None = None
        self.pipeline: Pipeline | None = None
        self.gateway: GatewayClient | None = None
        if config.inference is not None:
            decision = config.inference["decision"]
            self.gateway = GatewayClient(config.inference)
            self.executor.inference_binding = (
                self.gateway.provider,
                self.gateway.profile_id,
                self.gateway.config_hash,
            )
            self.pipeline = Pipeline(
                self.db,
                config.policy,
                self.gateway,
                confidence=decision["confidence_threshold"],
                margin=decision["margin_threshold"],
                prompt_version=decision["prompt_version"],
            )
        self._register_commands()
        watch_commands.register(self)

    async def setup_hook(self) -> None:
        self.message_ledger.recover()
        self.watch.recover()
        self.audio.recover(self.config.policy.guild_ids)
        for guild in self.config.policy.guild_ids:
            target = discord.Object(id=int(guild))
            self.tree.copy_global_to(guild=target)
            await self.tree.sync(guild=target)
        self.timer_task = asyncio.create_task(self._timers())

    async def close(self) -> None:
        tasks = list(
            {
                t
                for t in (*self.message_tasks.values(), *self.audio.preparing.values())
                if t is not asyncio.current_task()
            }
        )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.timer_task:
            self.timer_task.cancel()
            await asyncio.gather(self.timer_task, return_exceptions=True)
        self.audio.recover(self.config.policy.guild_ids)
        for voice in self.voice_clients:
            await voice.disconnect(force=True)
        if isinstance(self.audio.resolver, MediaResolver):
            await self.audio.resolver.close()
        await super().close()

    async def _timers(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await self.audio.check_auto_leave(self.config.policy.guild_ids)
            await asyncio.sleep(5)

    async def notify(self, guild: str, message: str) -> None:
        for channel_id in self.config.policy.text_channel_ids:
            channel = self.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel) and str(channel.guild.id) == guild:
                await channel.send(message)
                break

    async def fresh_actor(
        self, interaction: discord.Interaction | MentionEntry, *, request_id: str | None = None
    ) -> Actor:
        guild = interaction.guild
        if guild is None or str(guild.id) not in self.config.policy.guild_ids:
            raise DomainError("guild_not_allowed")
        request = request_id or (
            interaction.request_id if isinstance(interaction, MentionEntry) else None
        )
        with self.db.connect() as conn:
            source = source_row(conn, str(guild.id), request) if request else None
        prefix = source is not None and source["origin"] == "prefix"
        if not prefix and str(interaction.channel_id) not in self.config.policy.text_channel_ids:
            raise DomainError("text_channel_not_allowed")
        if prefix:
            if (
                not self.config.prefix.enabled
                or not self.intents.message_content
                or not self.is_ready()
            ):
                raise DomainError("watch_unavailable")
            code, _ = await watch_commands.inspect(self, guild, str(interaction.channel_id))
            await self.update_watch_health(str(guild.id), str(interaction.channel_id), code == "ok")
            if code != "ok":
                raise DomainError("watch_unavailable")
        try:
            member = await guild.fetch_member(interaction.user.id)
        except discord.HTTPException:
            raise DomainError("permissions_unavailable") from None
        voice_member = guild.get_member(member.id)
        voice_state = voice_member.voice if voice_member else None
        user_channel = voice_state.channel if voice_state else None
        bot_channel = guild.voice_client.channel if guild.voice_client else None
        actor = Actor(
            str(guild.id),
            str(member.id),
            frozenset(str(r.id) for r in member.roles),
            str(interaction.channel_id),
            str(user_channel.id) if user_channel else None,
            str(bot_channel.id)
            if isinstance(bot_channel, (discord.VoiceChannel, discord.StageChannel))
            else None,
            member.guild_permissions.manage_guild or member.id == guild.owner_id,
        )

        if request:
            with self.db.connect() as conn:
                policy_for_request(
                    conn,
                    self.config.policy,
                    actor,
                    request,
                    prefix_enabled=self.config.prefix.enabled,
                )
        if prefix:
            channel = await guild.fetch_channel(int(interaction.channel_id or 0))
            if (
                not watch_commands.normal_text(channel, str(guild.id))
                or not channel.permissions_for(member).view_channel
            ):
                raise DomainError("text_channel_not_allowed")
        return actor

    def request_policy(self, actor: Actor, request: str) -> Any:
        with self.db.connect() as conn:
            return policy_for_request(
                conn, self.config.policy, actor, request, prefix_enabled=self.config.prefix.enabled
            )

    async def validate_audio_entry(self, guild_id: str, entry_id: str) -> None:
        """Recheck the queued entry's own admission; its DJ need not remain in voice."""
        guild = self.get_guild(int(guild_id))
        if guild is None or guild_id not in self.config.policy.guild_ids:
            raise DomainError("guild_not_allowed")
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM audio_admissions WHERE guild_id=? AND entry_id=?",
                (guild_id, entry_id),
            ).fetchone()
            current = conn.execute(
                "SELECT s.current_entry_id,t.source_type FROM sessions s JOIN tracks t "
                "ON t.guild_id=s.guild_id AND t.id=s.current_track_id WHERE s.guild_id=?",
                (guild_id,),
            ).fetchone()
        if current is None or current[0] != entry_id:
            raise DomainError("execution_generation_conflict")
        with self.db.connect() as conn:
            if not admission_valid(conn, guild_id, entry_id):
                raise DomainError("watch_admission_expired")
        if row is None:
            raise DomainError("audio_admission_missing")
        if row["origin"] == "prefix":
            if (
                not self.config.prefix.enabled
                or not self.intents.message_content
                or not self.is_ready()
            ):
                raise DomainError("watch_admission_expired")
            code, _ = await watch_commands.inspect(self, guild, row["text_channel_id"])
            await self.update_watch_health(guild_id, row["text_channel_id"], code == "ok")
            if code != "ok":
                raise DomainError("watch_admission_expired")
        elif row["text_channel_id"] not in self.config.policy.text_channel_ids:
            raise DomainError("text_channel_not_allowed")
        channel = guild.get_channel(int(row["text_channel_id"]))
        member = await guild.fetch_member(int(row["actor_id"]))
        if (
            not isinstance(channel, discord.TextChannel)
            or not channel.permissions_for(member).view_channel
        ):
            raise DomainError("text_channel_not_allowed")
        if not ({str(role.id) for role in member.roles} & self.config.policy.dj_role_ids) and not (
            self.config.policy.admin_dj_override and member.guild_permissions.manage_guild
        ):
            raise DomainError("dj_required")
        voice = guild.voice_client
        if (
            voice is None
            or not isinstance(voice.channel, discord.VoiceChannel)
            or (str(voice.channel.id) not in self.config.policy.voice_channel_ids)
        ):
            raise DomainError("voice_channel_not_allowed")
        if guild.me is None or not voice.channel.permissions_for(guild.me).speak:
            raise DomainError("bot_voice_permissions_missing")

    def make_plan(
        self,
        actor: Actor,
        request_id: str,
        action: Action,
        arguments: dict[str, Any],
        *,
        origin: str = "slash",
        snapshot: sqlite3.Connection | None = None,
    ) -> ActionPlan:
        conn = snapshot or self.db.connect()
        try:
            session = conn.execute(
                "SELECT version,generation FROM sessions WHERE guild_id=?", (actor.guild_id,)
            ).fetchone()
            expected: dict[str, int] = {}
            if action == Action.EDIT_UNDO:
                target, version = undo.prepare(conn, actor.guild_id, arguments["event_id"])
                expected[target] = version
            playlist = arguments.get("playlist_id")
            if playlist:
                row = conn.execute(
                    "SELECT version FROM playlists WHERE guild_id=? AND id=?",
                    (actor.guild_id, playlist),
                ).fetchone()
                if not row:
                    raise DomainError("playlist_not_found")
                expected[playlist] = row[0]
            if action in PLAYBACK_ACTIONS or action.value.startswith("queue."):
                expected["queue"] = session[0]
            return ActionPlan(
                request_id,
                actor.guild_id,
                actor.user_id,
                action,
                arguments,
                expected,
                origin,
                session[1],
            )
        finally:
            if snapshot is None:
                conn.close()

    async def submit(
        self,
        interaction: discord.Interaction,
        action: Action,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            actor = await self.fresh_actor(interaction)
            plan = self.make_plan(
                actor,
                str(interaction.id),
                action,
                arguments or {},
                origin="button"
                if interaction.type == discord.InteractionType.component
                else "slash",
            )
            await self.submit_plan(interaction, plan, actor=actor)
        except DomainError as exc:
            await interaction.followup.send(
                ERRORS.get(exc.code, "요청 조건을 확인하고 다시 시도해줘."), ephemeral=True
            )

    async def submit_plan(
        self,
        interaction: discord.Interaction | MentionEntry,
        plan: ActionPlan,
        *,
        actor: Actor | None = None,
        confirmation: str | None = None,
    ) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if isinstance(interaction, MentionEntry):
                actor = actor or await self.fresh_actor(interaction, request_id=plan.request_id)
            else:
                # Confirmation components inherit the original server-recorded source.
                with self.db.connect() as conn:
                    original = source_row(conn, plan.guild_id, plan.request_id)
                actor = actor or await self.fresh_actor(
                    interaction,
                    **(
                        {"request_id": plan.request_id}
                        if original and original["origin"] == "prefix"
                        else {}
                    ),
                )
            if not isinstance(interaction, MentionEntry) or interaction.request_id is None:
                with self.db.transaction() as conn:
                    if source_row(conn, plan.guild_id, plan.request_id) is None:
                        bind_source(
                            conn,
                            plan.guild_id,
                            plan.request_id,
                            plan.actor_id,
                            actor.text_channel_id,
                            "mention" if isinstance(interaction, MentionEntry) else "slash",
                        )
            if plan.action == Action.TRACK_PLAY and plan.arguments["track_id"].startswith(
                "youtube:"
            ):
                if not self.config.youtube_audio_enabled:
                    raise DomainError("audio_source_not_approved")
                from changgeun.domain.models import authorize

                authorize(plan, actor, self.request_policy(actor, plan.request_id))
                identifier = plan.arguments["track_id"].split(":", 1)[1]
                metadata = (await self.youtube_api().videos([identifier])).get(identifier)
                if (
                    metadata is None
                    or metadata.duration_seconds is None
                    or not (0 < metadata.duration_seconds <= 1800)
                ):
                    raise DomainError("youtube_unsupported")
                actor = await self.fresh_actor(
                    interaction,
                    **(
                        {"request_id": plan.request_id}
                        if isinstance(interaction, MentionEntry) and interaction.request_id
                        else {}
                    ),
                )
                registration = replace(
                    self.make_plan(
                        actor,
                        plan.request_id + ".register",
                        Action.CATALOG_REGISTER,
                        {
                            "source_type": "youtube",
                            "external_id": identifier,
                            "title": metadata.title,
                            "metadata": {
                                "duration_seconds": metadata.duration_seconds,
                                "source_author": metadata.source_author,
                            },
                        },
                    ),
                    expires_at=plan.expires_at,
                )
                registered = self.executor.execute(registration, actor)
                plan = replace(
                    plan, arguments={**plan.arguments, "track_id": registered["track_id"]}
                )
            if plan.action == Action.TRACK_PLAY:
                with self.db.connect() as conn:
                    row = conn.execute(
                        "SELECT source_type,external_id FROM tracks WHERE guild_id=? AND id=?",
                        (plan.guild_id, plan.arguments["track_id"]),
                    ).fetchone()
                if row is None:
                    raise DomainError("track_not_found")
                self.audio.resolver.validate(row[0], row[1])
            if plan.action == Action.PLAYLIST_PLAY:
                conn = self.db.connect()
                try:
                    for track in plan.arguments.get("track_ids", []):
                        row = conn.execute(
                            "SELECT source_type,external_id FROM tracks WHERE guild_id=? AND id=?",
                            (plan.guild_id, track),
                        ).fetchone()
                        if row is None:
                            raise DomainError("track_not_found")
                        self.audio.resolver.validate(row[0], row[1])
                finally:
                    conn.close()
            result = self.executor.execute(plan, actor, confirmation=confirmation)
            if self.pipeline is not None:
                playlist = plan.arguments.get("playlist_id") or result.get("playlist_id")
                if playlist:
                    conn = self.db.connect()
                    try:
                        row = conn.execute(
                            "SELECT name FROM playlists "
                            "WHERE guild_id=? AND id=? AND deleted_at IS NULL",
                            (plan.guild_id, playlist),
                        ).fetchone()
                    finally:
                        conn.close()
                    if row:
                        self.pipeline.context.remember(actor, playlist, row[0])
            if plan.action in PLAYBACK_ACTIONS:
                await self.audio.apply(plan.guild_id, plan.action, result)
                if plan.action == Action.TRACK_PLAY and result["start_requested"]:
                    with self.db.connect() as conn:
                        current = conn.execute(
                            "SELECT current_track_id FROM sessions WHERE guild_id=?",
                            (plan.guild_id,),
                        ).fetchone()[0]
                    if current != plan.arguments["track_id"]:
                        raise DomainError("youtube_prepare_failed")
            content = self.render(plan.action, result)
            if plan.action == Action.PLAYLIST_EXPORT:
                await interaction.followup.send(
                    "곡 참조와 순서를 JSON 파일로 내보냈어.",
                    file=discord.File(
                        io.BytesIO(json.dumps(result, ensure_ascii=False, indent=2).encode()),
                        filename="playlist.json",
                    ),
                    ephemeral=True,
                )
            elif len(content) > 1900:
                await interaction.followup.send(
                    "결과가 길어서 전체 목록을 파일로 보냈어.",
                    file=discord.File(io.BytesIO(content.encode()), filename="list.txt"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(content, ephemeral=True)
        except DomainError as exc:
            if exc.code == "confirmation_required":
                token = self.executor.preview(plan, actor or await self.fresh_actor(interaction))
                preview = "선택한 항목을 변경할게. 60초 안에 확인해줘."
                if plan.action == Action.PLAYLIST_GENERATE:
                    preview = (
                        f"‘{safe(plan.arguments['name'])}’ 목록에 등록 곡 "
                        f"{len(plan.arguments['track_ids'])}개를 저장할게. "
                        f"요청은 {plan.arguments['rules']['count']}곡이야. "
                        "부족한 수량으로 저장하려면 확인해줘. 취소 후 조건을 바꿔도 돼."
                    )
                if plan.action == Action.PLAYLIST_IMPORT:
                    destination = (
                        "기존 항목을 교체해."
                        if plan.arguments.get("replace")
                        else "기존 항목에 추가하거나 새 목록을 만들어."
                    )
                    duplicates = (
                        "중복을 보존해."
                        if plan.arguments.get("allow_duplicates")
                        else "가져온 참조 내부의 중복을 제외해."
                    )
                    preview = (
                        f"‘{safe(plan.arguments['name'])}’에 "
                        f"{len(plan.arguments['references'])}개 참조를 가져올게. "
                        f"전체 읽기: {'완료' if plan.arguments['complete'] else '미완료'}, "
                        f"읽을 수 없는 항목: {plan.arguments['unavailable_count']}개. "
                        f"{destination} {duplicates} "
                        "지금 읽은 스냅샷만 저장하며 자동 동기화하지 않아. 확인해줘."
                    )
                await interaction.followup.send(
                    preview,
                    view=ConfirmationView(self, plan, token),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "요청 조건이 맞지 않아 실행하지 않았어. 다시 확인해줘."),
                    ephemeral=True,
                )

    @staticmethod
    def render(action: Action, result: dict[str, Any]) -> str:
        if action == Action.TRACK_PLAY:
            title = safe(result["requested_title"])
            return (
                f"대기열에 ‘{title}’을 추가했어. 현재곡은 계속 재생해."
                if result["queued"]
                else f"‘{title}’ 재생을 시작했어."
            )
        if action == Action.PROPOSAL_LIST:
            return "대기 중인 제안:\n" + (
                "\n".join(
                    f"{safe(p['id'])}: {safe(p['title'])} → {safe(p['name'])}"
                    for p in result["proposals"]
                )
                or "없어."
            )
        if action == Action.PROPOSAL_CREATE:
            return "제안을 보냈어. DJ가 승인하면 목록에 추가돼."
        if action == Action.PLAYLIST_GENERATE:
            return f"등록 카탈로그에서 {result['count']}곡으로 목록을 만들었어."
        if action == Action.PLAYLIST_IMPORT:
            return (
                f"{result['count']}개 참조를 저장했어. "
                f"원본 중복 참조는 {result['duplicate_references']}개였어. "
                "재생은 현재 활성화된 음원 소스 설정을 따라."
            )
        if action == Action.PLAYLIST_LIST:
            return "저장 목록:\n" + (
                "\n".join(safe(p["name"]) for p in result["playlists"])
                or "아직 없어. /목록 생성으로 만들어줘."
            )
        if action == Action.CATALOG_SEARCH:
            return "검색 결과:\n" + (
                "\n".join(safe(t["title"]) for t in result["tracks"]) or "찾은 곡이 없어."
            )
        if action == Action.QUEUE_SHOW:
            return (
                "현재곡: "
                + safe(result["session"].get("current_title") or "없어")
                + "\n대기열:\n"
                + (
                    "\n".join(
                        f"{i + 1}. {safe(e.get('title', '등록 곡'))} "
                        f"· {e.get('approval', '승인됨')}"
                        for i, e in enumerate(result["entries"])
                    )
                    or "비어 있어."
                )
            )
        if action == Action.PLAYLIST_EXPORT:
            return "목록 내보내기:\n" + "\n".join(
                safe(t["title"])
                + " — "
                + (
                    "https://www.youtube.com/watch?v=" + t["external_id"]
                    if t["source_type"] == "youtube"
                    else "승인 음원"
                )
                for t in result["tracks"]
            )
        if "desired_state" in result:
            return "재생 요청을 처리했어."
        return (
            "저장했어."
            if action not in {Action.PLAYLIST_REMOVE, Action.QUEUE_REMOVE, Action.PLAYLIST_DELETE}
            else "선택한 항목을 제거했어."
        )

    def resolve_playlist(self, guild: str, value: str) -> str:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT id FROM playlists WHERE guild_id=? AND deleted_at IS NULL "
                "AND (id=? OR normalized_name=?)",
                (guild, value, normalized_name(value)),
            ).fetchone()
            if not row:
                raise DomainError("playlist_not_found")
            return str(row[0])
        finally:
            conn.close()

    def youtube_api(self) -> YouTubeData:
        path = self.config.youtube_key_file
        if (
            path is None
            or not path.is_absolute()
            or not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o077
        ):
            raise DomainError("youtube_key_missing")
        return YouTubeData(path.read_text().strip())

    def resolve_track(self, guild: str, value: str) -> str:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id,title,annotations_json FROM tracks WHERE guild_id=?", (guild,)
            ).fetchall()
            matches = [
                r["id"]
                for r in rows
                if r["id"] == value
                or normalized_name(r["title"]) == normalized_name(value)
                or normalized_name(value)
                in [
                    normalized_name(a) for a in json.loads(r["annotations_json"]).get("aliases", [])
                ]
            ]
            if len(matches) != 1:
                raise DomainError("track_not_found")
            return str(matches[0])
        finally:
            conn.close()

    async def playlist_input(
        self,
        interaction: discord.Interaction,
        action: Action,
        playlist: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        try:
            if not interaction.guild_id:
                raise DomainError("guild_not_allowed")
            identifier = self.resolve_playlist(str(interaction.guild_id), playlist)
            await self.submit(interaction, action, {"playlist_id": identifier, **(extra or {})})
        except DomainError as exc:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    ERRORS.get(exc.code, "목록을 다시 선택해줘."), ephemeral=True
                )

    def _register_commands(self) -> None:
        tree = self.tree
        playlists = app_commands.Group(name="목록", description="저장 플레이리스트 관리")
        songs = app_commands.Group(name="곡", description="카탈로그와 저장 목록의 곡 편집")
        queue = app_commands.Group(name="대기열", description="현재 대기열 관리")
        proposals = app_commands.Group(name="제안", description="DJ의 곡 제안 승인·거절")
        tree.add_command(playlists)
        tree.add_command(songs)
        tree.add_command(queue)
        tree.add_command(proposals)

        @playlists.command(name="만들기", description="등록된 태그·곡 수로 목록 생성 미리보기")
        async def generate_playlist(
            interaction: discord.Interaction,
            이름: str,
            곡수: int = 20,
            태그: str = "",
            제외태그: str = "",
            제작자: str | None = None,
            최근제외일: int = 7,
            최대초: int | None = None,
            시드: int = 0,
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                rules = Rules(
                    tuple(tag.strip() for tag in 태그.split(",") if tag.strip()),
                    tuple(tag.strip() for tag in 제외태그.split(",") if tag.strip()),
                    제작자,
                    곡수,
                    최대초,
                    최근제외일,
                    시드,
                )
                reference = time.time()
                conn = self.db.connect()
                try:
                    result = select(conn, actor.guild_id, rules, reference)
                finally:
                    conn.close()
                plan = self.make_plan(
                    actor,
                    str(interaction.id),
                    Action.PLAYLIST_GENERATE,
                    {
                        "name": 이름,
                        "rules": rules.serialize(),
                        "track_ids": result.track_ids,
                        "snapshot_hash": result.snapshot_hash,
                        "reference_time": reference,
                    },
                )
                if not result.track_ids:
                    raise DomainError("generation_no_matches")
                await self.submit_plan(interaction, plan, actor=actor)
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "조건을 다시 확인해줘."), ephemeral=True
                )

        @playlists.command(
            name="가져오기", description="YouTube 공개 목록 또는 내보낸 JSON 참조 가져오기"
        )
        async def import_playlist(
            interaction: discord.Interaction,
            이름: str,
            링크: str | None = None,
            파일: discord.Attachment | None = None,
            기존목록: str | None = None,
            교체: bool = False,
            중복허용: bool = False,
            부분읽기허용: bool = False,
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                from changgeun.domain.models import authorize

                authorize(
                    self.make_plan(actor, str(interaction.id), Action.PLAYLIST_IMPORT, {}),
                    actor,
                    self.config.policy,
                )
                if (링크 is None) == (파일 is None):
                    raise DomainError("invalid_arguments")
                complete, unavailable = True, 0
                source_metadata = {}
                if 파일 is not None:
                    if 파일.size > 524288:
                        raise DomainError("import_file_too_large")
                    references = parse_export(await 파일.read())
                else:
                    snapshot = await self.youtube_api().playlist(링크 or "")
                    complete, unavailable = snapshot.complete, snapshot.unavailable_count
                    source_metadata = {
                        item.external_id: {
                            "source_author": item.source_author,
                            "duration_seconds": item.duration_seconds,
                        }
                        for item in snapshot.items
                    }
                    references = [
                        {
                            "source_type": "youtube",
                            "external_id": item.external_id,
                            "title": item.title,
                        }
                        for item in snapshot.items
                    ]
                actor = await self.fresh_actor(interaction)
                arguments: dict[str, Any] = {
                    "name": 이름,
                    "references": references,
                    "complete": complete,
                    "unavailable_count": unavailable,
                    "accept_partial": 부분읽기허용,
                    "allow_duplicates": 중복허용,
                    "replace": 교체,
                    "source_metadata": source_metadata,
                }
                if 기존목록 is not None:
                    arguments["playlist_id"] = self.resolve_playlist(actor.guild_id, 기존목록)
                elif 교체:
                    raise DomainError("invalid_arguments")
                plan = self.make_plan(actor, str(interaction.id), Action.PLAYLIST_IMPORT, arguments)
                await self.submit_plan(interaction, plan, actor=actor)
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "목록 링크·파일과 가져오기 조건을 확인해줘."),
                    ephemeral=True,
                )

        @tree.command(
            name="유튜브검색", description="공식 API로 YouTube 곡 참조 검색; 오디오 추출 없음"
        )
        async def youtube_search(interaction: discord.Interaction, 검색어: str) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                from changgeun.domain.models import authorize

                authorize(
                    self.make_plan(
                        actor, str(interaction.id), Action.CATALOG_SEARCH, {"query": 검색어}
                    ),
                    actor,
                    self.config.policy,
                )
                results = await self.youtube_api().search(검색어)
                text = "\n".join(
                    safe(item.title) + "\nhttps://www.youtube.com/watch?v=" + item.external_id
                    for item in results
                )
                await interaction.followup.send((text or "찾은 곡이 없어.")[:1900], ephemeral=True)
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "검색어와 공식 API 설정을 확인해줘."), ephemeral=True
                )

        @songs.command(name="표기", description="운영자 별칭·태그·제작자 표기 변경")
        async def annotate_song(
            interaction: discord.Interaction,
            곡: str,
            별칭: str = "",
            태그: str = "",
            제작자: str | None = None,
        ) -> None:
            try:
                track = self.resolve_track(str(interaction.guild_id), 곡)
                arguments: dict[str, Any] = {
                    "track_id": track,
                    "aliases": [value.strip() for value in 별칭.split(",") if value.strip()],
                    "tags": [value.strip() for value in 태그.split(",") if value.strip()],
                }
                if 제작자 is not None:
                    arguments["creator"] = 제작자
                await self.submit(interaction, Action.CATALOG_ANNOTATE, arguments)
            except DomainError:
                await interaction.response.send_message(
                    "곡 이름을 /검색에서 확인해줘.", ephemeral=True
                )

        @tree.command(name="곡제안", description="일반 멤버도 등록 곡을 목록에 제안할 수 있어")
        async def propose_song(interaction: discord.Interaction, 목록: str, 곡: str) -> None:
            try:
                track = self.resolve_track(str(interaction.guild_id), 곡)
                await self.playlist_input(
                    interaction, Action.PROPOSAL_CREATE, 목록, {"track_id": track}
                )
            except DomainError:
                await interaction.response.send_message(
                    "등록된 곡과 목록을 골라줘.", ephemeral=True
                )

        @tree.command(name="제안함", description="DJ가 대기 중인 곡 제안 조회")
        async def list_proposals(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.PROPOSAL_LIST)

        @tree.command(
            name="되돌리기", description="변경되지 않은 목록·큐 편집 하나를 확인 후 되돌려"
        )
        async def undo_edit(interaction: discord.Interaction, 변경: str | None = None) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                from changgeun.domain.models import authorize

                authorize(
                    ActionPlan(
                        str(interaction.id),
                        actor.guild_id,
                        actor.user_id,
                        Action.EDIT_UNDO,
                        {"event_id": "pending"},
                    ),
                    actor,
                    self.config.policy,
                )
                conn = self.db.connect()
                try:
                    event_id = 변경
                    if event_id is None:
                        actions = sorted(
                            action.value for action in undo.PLAYLIST_EDITS | undo.QUEUE_EDITS
                        )
                        marks = ",".join("?" for _ in actions)
                        row = conn.execute(
                            "SELECT e.id FROM change_events e WHERE e.guild_id=? "
                            f"AND e.action IN ({marks}) "
                            "AND NOT EXISTS(SELECT 1 FROM edit_undos u WHERE u.guild_id=e.guild_id "
                            "AND u.event_id=e.id) ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1",
                            (actor.guild_id, *actions),
                        ).fetchone()
                        if row is None:
                            raise DomainError("undo_not_found")
                        event_id = row[0]
                    plan = self.make_plan(
                        actor,
                        str(interaction.id),
                        Action.EDIT_UNDO,
                        {"event_id": event_id},
                        snapshot=conn,
                    )
                finally:
                    conn.close()
                await self.submit_plan(interaction, plan, actor=actor)
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(
                        exc.code, "되돌릴 편집이 없거나 이후에 변경됐어. 최신 상태를 확인해줘."
                    ),
                    ephemeral=True,
                )

        async def process_proposal(
            interaction: discord.Interaction, identifier: str, action: Action
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                conn = self.db.connect()
                try:
                    row = conn.execute(
                        "SELECT playlist_id FROM proposals WHERE guild_id=? AND id=?",
                        (actor.guild_id, identifier),
                    ).fetchone()
                    if row is None:
                        raise DomainError("proposal_not_pending")
                    version = conn.execute(
                        "SELECT version FROM playlists WHERE guild_id=? AND id=?",
                        (actor.guild_id, row[0]),
                    ).fetchone()
                finally:
                    conn.close()
                plan = self.make_plan(
                    actor, str(interaction.id), action, {"proposal_id": identifier}
                )
                plan = replace(plan, expected_versions={row[0]: version[0]})
                await self.submit_plan(interaction, plan, actor=actor)
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "제안을 다시 확인해줘."), ephemeral=True
                )

        @proposals.command(name="승인", description="DJ가 제안 곡을 저장 목록에 추가")
        async def approve_proposal(interaction: discord.Interaction, 제안번호: str) -> None:
            await process_proposal(interaction, 제안번호, Action.PROPOSAL_APPROVE)

        @proposals.command(name="거절", description="DJ가 곡 제안 거절")
        async def reject_proposal(interaction: discord.Interaction, 제안번호: str) -> None:
            await process_proposal(interaction, 제안번호, Action.PROPOSAL_REJECT)

        @tree.command(name="도움말", description="창근이 사용법과 현재 지원 범위")
        async def help_command(interaction: discord.Interaction) -> None:
            actor: Actor | None = None
            watched_here = False
            if (
                interaction.guild_id is not None
                and str(interaction.channel_id) in self.config.policy.text_channel_ids
            ):
                try:
                    actor = await self.fresh_actor(interaction)
                    state = self.watch.state(actor.guild_id)
                    watched_here = bool(
                        self.config.prefix.enabled
                        and state["enabled"]
                        and actor.text_channel_id in self.watch.channels(actor.guild_id)
                    )
                except DomainError:
                    pass
            await interaction.response.send_message(
                help_text(
                    actor,
                    self.config.policy,
                    youtube_audio=self.config.youtube_audio_enabled,
                    prefix_enabled=self.config.prefix.enabled,
                    watched_here=watched_here,
                ),
                ephemeral=True,
            )

        @playlists.command(name="보기", description="저장 목록 보기")
        async def list_playlists(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.PLAYLIST_LIST)

        @playlists.command(name="생성", description="빈 저장 목록 생성")
        async def create_playlist(interaction: discord.Interaction, 이름: str) -> None:
            await self.submit(interaction, Action.PLAYLIST_CREATE, {"name": 이름})

        @playlists.command(name="이름변경", description="목록 이름 변경")
        async def rename_playlist(interaction: discord.Interaction, 목록: str, 이름: str) -> None:
            await self.playlist_input(interaction, Action.PLAYLIST_RENAME, 목록, {"name": 이름})

        @playlists.command(name="삭제", description="목록 논리 삭제: 확인 필요")
        async def delete_playlist(interaction: discord.Interaction, 목록: str) -> None:
            await self.playlist_input(interaction, Action.PLAYLIST_DELETE, 목록)

        @playlists.command(name="복사", description="다른 이름으로 목록 복사")
        async def copy_playlist(interaction: discord.Interaction, 목록: str, 이름: str) -> None:
            await self.playlist_input(interaction, Action.PLAYLIST_COPY, 목록, {"name": 이름})

        @playlists.command(name="내보내기", description="곡 제목과 원본 참조 보기")
        async def export_playlist(interaction: discord.Interaction, 목록: str) -> None:
            await self.playlist_input(interaction, Action.PLAYLIST_EXPORT, 목록)

        @songs.command(name="등록", description="YouTube 링크를 카탈로그 참조로 등록")
        async def register_song(interaction: discord.Interaction, 링크: str) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                # Check DJ before external metadata IO.
                from changgeun.domain.models import authorize

                authorize(
                    self.make_plan(
                        actor,
                        str(interaction.id),
                        Action.CATALOG_REGISTER,
                        {"source_type": "youtube", "external_id": "pending", "title": "pending"},
                    ),
                    actor,
                    self.config.policy,
                )
                if self.config.youtube_key_file is None:
                    metadata = await YouTubeMetadata().fetch(링크)
                else:
                    from changgeun.providers.media import youtube_id

                    identifier = youtube_id(링크)
                    resolved = await self.youtube_api().videos([identifier])
                    if identifier not in resolved:
                        raise DomainError("youtube_metadata_failed")
                    metadata = resolved[identifier]
                actor = await self.fresh_actor(interaction)
                plan = self.make_plan(
                    actor,
                    str(interaction.id),
                    Action.CATALOG_REGISTER,
                    {
                        "source_type": "youtube",
                        "external_id": metadata.external_id,
                        "title": metadata.title,
                        "metadata": {
                            "source_author": metadata.source_author,
                            "duration_seconds": metadata.duration_seconds,
                        },
                    },
                )
                await self.submit_plan(interaction, plan, actor=actor)
            except Exception:
                await interaction.followup.send(
                    "링크나 권한을 확인해줘. 저장하지 않았어.", ephemeral=True
                )

        @songs.command(name="추가", description="카탈로그 곡을 저장 목록에 추가")
        async def add_song(
            interaction: discord.Interaction, 목록: str, 곡: str, 중복허용: bool = False
        ) -> None:
            try:
                track = self.resolve_track(str(interaction.guild_id), 곡)
                await self.playlist_input(
                    interaction,
                    Action.PLAYLIST_ADD,
                    목록,
                    {"track_ids": [track], "allow_duplicates": 중복허용},
                )
            except DomainError:
                await interaction.response.send_message(
                    "곡 이름을 /검색에서 확인해줘.", ephemeral=True
                )

        @songs.command(name="제거", description="저장 목록에서 번호로 선택한 항목 제거")
        async def remove_song(interaction: discord.Interaction, 목록: str, 번호: int) -> None:
            await self.edit_number(interaction, Action.PLAYLIST_REMOVE, 목록, 번호)

        @songs.command(name="이동", description="저장 목록 항목을 다른 위치로 이동")
        async def move_song(
            interaction: discord.Interaction, 목록: str, 번호: int, 위치: int
        ) -> None:
            await self.edit_number(interaction, Action.PLAYLIST_MOVE, 목록, 번호, 위치)

        @tree.command(name="검색", description="등록된 카탈로그에서 곡 검색")
        async def search(interaction: discord.Interaction, 검색어: str) -> None:
            await self.submit(interaction, Action.CATALOG_SEARCH, {"query": 검색어})

        @queue.command(name="보기", description="현재 대기열 보기")
        async def show_queue(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.QUEUE_SHOW)

        @queue.command(name="비우기", description="현재곡을 유지하고 대기 항목만 비우기")
        async def clear_queue(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.QUEUE_CLEAR)

        @queue.command(name="저장", description="대기열을 새 저장 목록으로 저장")
        async def save_queue(
            interaction: discord.Interaction, 이름: str, 현재곡포함: bool = False
        ) -> None:
            await self.submit(
                interaction, Action.QUEUE_SAVE, {"name": 이름, "include_current": 현재곡포함}
            )

        @queue.command(name="제거", description="대기 항목 번호로 제거")
        async def remove_queue(interaction: discord.Interaction, 번호: int) -> None:
            await self.edit_number(interaction, Action.QUEUE_REMOVE, None, 번호)

        @queue.command(name="이동", description="대기 항목을 다른 위치로 이동")
        async def move_queue(interaction: discord.Interaction, 번호: int, 위치: int) -> None:
            await self.edit_number(interaction, Action.QUEUE_MOVE, None, 번호, 위치)

        @tree.command(name="입장", description="허용 음성채널에 연결만 하기")
        async def join(
            interaction: discord.Interaction, 채널: discord.VoiceChannel | None = None
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                actor = await self.fresh_actor(interaction)
                target = str(채널.id) if 채널 else actor.voice_channel_id
                if not target:
                    raise DomainError("same_voice_required")
                action = (
                    Action.VOICE_MOVE
                    if actor.bot_voice_channel_id and actor.bot_voice_channel_id != target
                    else Action.VOICE_JOIN
                )
                await self.submit_plan(
                    interaction,
                    self.make_plan(actor, str(interaction.id), action, {"channel_id": target}),
                    actor=actor,
                )
            except DomainError as exc:
                await interaction.followup.send(
                    ERRORS.get(exc.code, "채널을 다시 선택해줘."), ephemeral=True
                )

        @tree.command(name="퇴장", description="현재곡을 보존하고 음성채널 떠나기")
        async def leave(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.VOICE_LEAVE)

        @tree.command(name="재생", description="곡 또는 저장 목록을 대기열에 추가하고 재생")
        async def play(
            interaction: discord.Interaction,
            곡: str | None = None,
            목록: str | None = None,
            검색어: str | None = None,
        ) -> None:
            if 검색어 is not None:
                if 곡 is not None or 목록 is not None:
                    await interaction.response.send_message(
                        "곡·목록·검색어 중 하나만 선택해줘.", ephemeral=True
                    )
                    return
                await self.search_play_input(interaction, 검색어)
                return
            await self.play_input(interaction, 곡, 목록)

        @tree.command(name="일시정지", description="현재 위치를 유지하고 일시정지")
        async def pause(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.PLAYBACK_PAUSE)

        @tree.command(name="계속", description="일시정지 위치에서 계속")
        async def resume(interaction: discord.Interaction) -> None:
            await self.continue_input(interaction)

        @tree.command(name="넘기기", description="현재곡을 반복하지 않고 다음곡으로")
        async def skip(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.PLAYBACK_SKIP)

        @tree.command(name="정지", description="현재 항목을 앞에 보존하고 정지")
        async def stop(interaction: discord.Interaction) -> None:
            await self.submit(interaction, Action.PLAYBACK_STOP)

        @tree.command(name="볼륨", description="음량 0~100 설정")
        async def volume(
            interaction: discord.Interaction, 값: app_commands.Range[int, 0, 100]
        ) -> None:
            await self.submit(interaction, Action.PLAYBACK_VOLUME, {"percent": 값})

        @tree.command(name="반복", description="끄기/한곡/대기열 순환")
        @app_commands.choices(
            모드=[
                app_commands.Choice(name="끄기", value="off"),
                app_commands.Choice(name="한곡", value="one"),
                app_commands.Choice(name="대기열", value="queue"),
            ]
        )
        async def repeat_mode(
            interaction: discord.Interaction, 모드: app_commands.Choice[str]
        ) -> None:
            await self.submit(interaction, Action.PLAYBACK_REPEAT, {"mode": 모드.value})

        @tree.command(name="셔플", description="대기 중인 항목만 섞기")
        async def shuffle(interaction: discord.Interaction) -> None:
            await self.submit(
                interaction, Action.PLAYBACK_SHUFFLE, {"seed": random.randrange(2**31)}
            )

        @tree.command(name="현재곡", description="현재 상태와 재생 제어 버튼")
        async def current(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                actor = await self.fresh_actor(interaction)
                result = self.executor.execute(
                    self.make_plan(actor, str(interaction.id), Action.QUEUE_SHOW, {}), actor
                )
                title = result["session"].get("current_title") or "현재곡 없음"
                await interaction.followup.send(
                    safe(title), view=PlaybackView(self), ephemeral=True
                )
            except DomainError:
                await interaction.followup.send("허용된 서버와 채널에서 사용해줘.", ephemeral=True)

        @tree.command(name="부탁", description="한국어로 한 가지 동작 요청")
        async def natural(interaction: discord.Interaction, 내용: str) -> None:
            await self.natural_input(interaction, 내용)

    async def edit_number(
        self,
        interaction: discord.Interaction,
        action: Action,
        playlist: str | None,
        number: int,
        position: int | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            actor = await self.fresh_actor(interaction)
            conn = self.db.connect()
            try:
                conn.execute("BEGIN")
                arguments: dict[str, Any] = {}
                if playlist is not None:
                    identifier = self.resolve_playlist(actor.guild_id, playlist)
                    arguments["playlist_id"] = identifier
                    entries = conn.execute(
                        "SELECT id FROM playlist_entries WHERE guild_id=? "
                        "AND playlist_id=? ORDER BY position",
                        (actor.guild_id, identifier),
                    ).fetchall()
                else:
                    entries = conn.execute(
                        "SELECT id FROM queue_entries WHERE guild_id=? ORDER BY position",
                        (actor.guild_id,),
                    ).fetchall()
                if number < 1 or number > len(entries):
                    raise DomainError("entry_not_found")
                arguments["entry_id"] = entries[number - 1][0]
                if position is not None:
                    arguments["position"] = position - 1
                plan = self.make_plan(actor, str(interaction.id), action, arguments, snapshot=conn)
            finally:
                conn.close()
            await self.submit_plan(interaction, plan, actor=actor)
        except DomainError:
            await interaction.followup.send("목록과 항목 번호를 다시 확인해줘.", ephemeral=True)

    async def search_play_input(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if not self.config.youtube_audio_enabled:
                raise DomainError("audio_source_not_approved")
            actor = await self.fresh_actor(interaction)
            if actor.voice_channel_id is None:
                raise DomainError("same_voice_required")
            from changgeun.domain.models import authorize

            probe = self.make_plan(
                actor,
                str(interaction.id),
                Action.TRACK_PLAY,
                {
                    "track_id": "pending",
                    "channel_id": actor.bot_voice_channel_id or actor.voice_channel_id,
                },
            )
            authorize(probe, actor, self.config.policy)
            results = [
                m
                for m in await self.youtube_api().search(query)
                if m.duration_seconds is not None and 0 < m.duration_seconds <= 1800
            ]
            if not results:
                raise DomainError("youtube_unsupported")
            view = YouTubeSelection(
                self,
                actor,
                [m.external_id for m in results],
                [m.title for m in results],
                str(interaction.id),
                probe.expected_versions["queue"],
                probe.execution_generation,
            )
            await interaction.followup.send(
                "재생할 영상을 골라줘. 60초 안에 선택할 수 있어.", view=view, ephemeral=True
            )
        except DomainError as exc:
            await interaction.followup.send(
                ERRORS.get(exc.code, "검색 조건을 확인해줘."), ephemeral=True
            )

    async def play_input(
        self, interaction: discord.Interaction, song: str | None, playlist: str | None
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if song is not None and playlist is not None:
                raise DomainError("invalid_arguments")
            actor = await self.fresh_actor(interaction)
            tracks: list[str] = []
            if song:
                if re.match(r"(?i)^(?:https?://|(?:(?:www\.|m\.)?youtube\.com|youtu\.be)/)", song):
                    from changgeun.providers.media import youtube_id

                    if not actor.voice_channel_id:
                        raise DomainError("same_voice_required")
                    plan = self.make_plan(
                        actor,
                        str(interaction.id),
                        Action.TRACK_PLAY,
                        {
                            "track_id": "youtube:" + youtube_id(song),
                            "channel_id": actor.bot_voice_channel_id or actor.voice_channel_id,
                        },
                    )
                    await self.submit_plan(interaction, plan, actor=actor)
                    return
                tracks = [self.resolve_track(actor.guild_id, song)]
                if actor.voice_channel_id:
                    plan = self.make_plan(
                        actor,
                        str(interaction.id),
                        Action.TRACK_PLAY,
                        {
                            "track_id": tracks[0],
                            "channel_id": actor.bot_voice_channel_id or actor.voice_channel_id,
                        },
                    )
                    await self.submit_plan(interaction, plan, actor=actor)
                    return
            elif playlist:
                identifier = self.resolve_playlist(actor.guild_id, playlist)
                conn = self.db.connect()
                try:
                    tracks = [
                        r[0]
                        for r in conn.execute(
                            "SELECT track_id FROM playlist_entries "
                            "WHERE guild_id=? AND playlist_id=? ORDER BY position",
                            (actor.guild_id, identifier),
                        )
                    ]
                finally:
                    conn.close()
                if not actor.voice_channel_id:
                    raise DomainError("same_voice_required")
                plan = self.make_plan(
                    actor,
                    str(interaction.id),
                    Action.PLAYLIST_PLAY,
                    {
                        "playlist_id": identifier,
                        "channel_id": actor.bot_voice_channel_id or actor.voice_channel_id,
                        "track_ids": tracks,
                    },
                )
                await self.submit_plan(interaction, plan, actor=actor)
                return
            if tracks:
                conn = self.db.connect()
                try:
                    for track in tracks:
                        row = conn.execute(
                            "SELECT source_type,external_id FROM tracks WHERE guild_id=? AND id=?",
                            (actor.guild_id, track),
                        ).fetchone()
                        self.audio.resolver.validate(row[0], row[1])
                finally:
                    conn.close()
                enqueue = self.make_plan(
                    actor,
                    str(interaction.id) + ".enqueue",
                    Action.QUEUE_ENQUEUE,
                    {"track_ids": tracks},
                )
                try:
                    self.executor.execute(enqueue, actor)
                except DomainError as exc:
                    if exc.code == "confirmation_required":
                        await self.submit_plan(interaction, enqueue, actor=actor)
                        return
                    raise
            elif song is None and playlist is None:
                await interaction.followup.send(
                    "/계속으로 일시정지를 풀거나, 재생할 곡·목록을 골라줘.", ephemeral=True
                )
                return
            if not actor.bot_voice_channel_id:
                if not actor.voice_channel_id:
                    raise DomainError("same_voice_required")
                join = self.make_plan(
                    actor,
                    str(interaction.id) + ".join",
                    Action.VOICE_JOIN,
                    {"channel_id": actor.voice_channel_id},
                )
                result = self.executor.execute(join, actor)
                await self.audio.apply(actor.guild_id, Action.VOICE_JOIN, result)
                actor = await self.fresh_actor(interaction)
            conn = self.db.connect()
            try:
                state = conn.execute(
                    "SELECT desired_state FROM sessions WHERE guild_id=?", (actor.guild_id,)
                ).fetchone()[0]
            finally:
                conn.close()
            if state == "idle":
                start = self.make_plan(
                    actor, str(interaction.id) + ".start", Action.PLAYBACK_START, {}
                )
                await self.submit_plan(interaction, start, actor=actor)
        except DomainError as exc:
            await interaction.followup.send(
                ERRORS.get(exc.code, "곡·목록과 음성채널을 확인해줘."), ephemeral=True
            )

    async def continue_input(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            actor = await self.fresh_actor(interaction)
            if actor.bot_voice_channel_id is None:
                if actor.voice_channel_id is None:
                    raise DomainError("same_voice_required")
                plan = self.make_plan(
                    actor,
                    str(interaction.id) + ".join",
                    Action.VOICE_JOIN,
                    {"channel_id": actor.voice_channel_id},
                )
                result = self.executor.execute(plan, actor)
                await self.audio.apply(actor.guild_id, plan.action, result)
                actor = await self.fresh_actor(interaction)
            conn = self.db.connect()
            try:
                state = conn.execute(
                    "SELECT desired_state FROM sessions WHERE guild_id=?", (actor.guild_id,)
                ).fetchone()[0]
            finally:
                conn.close()
            action = Action.PLAYBACK_RESUME if state == "paused" else Action.PLAYBACK_START
            plan = self.make_plan(actor, str(interaction.id), action, {})
            await self.submit_plan(interaction, plan, actor=actor)
        except DomainError as exc:
            await interaction.followup.send(
                ERRORS.get(exc.code, "현재 상태에서 재개할 수 없어."), ephemeral=True
            )

    async def natural_input(
        self, interaction: discord.Interaction | MentionEntry, text: str
    ) -> None:
        started = time.monotonic()
        await interaction.response.defer(ephemeral=True, thinking=True)
        if self.pipeline is None or self.gateway is None:
            await interaction.followup.send(
                "자연어 시험 연결을 준비 중이야. 슬래시 명령을 사용해줘.", ephemeral=True
            )
            return
        try:
            actor = await self.fresh_actor(interaction)
            if not isinstance(interaction, MentionEntry) or interaction.request_id is None:
                request = str(interaction.id)
                with self.db.transaction() as conn:
                    bind_source(
                        conn,
                        actor.guild_id,
                        request,
                        actor.user_id,
                        actor.text_channel_id,
                        "mention" if isinstance(interaction, MentionEntry) else "slash",
                    )
            else:
                request = interaction.request_id
            await self.gateway.ready()

            async def refresh() -> Actor:
                return await self.fresh_actor(interaction)

            plan = await self.pipeline.interpret(
                text,
                actor,
                started_at=started,
                refresh_actor=refresh,
                request_id=request,
            )
            if plan is None:
                await interaction.followup.send(
                    "어느 대상에 어떤 동작을 할지 구체적으로 알려줘. "
                    "슬래시 명령으로도 선택할 수 있어.",
                    ephemeral=True,
                )
                return
            actor = await self.fresh_actor(interaction)
            await self.submit_plan(interaction, plan, actor=actor)
        except Exception as exc:
            category, message = natural_failure(exc)
            self.natural_failures[category] += 1
            await interaction.followup.send(message, ephemeral=True)

    async def on_message(self, message: discord.Message) -> None:
        if (
            self.user is None
            or message.author.bot
            or message.webhook_id is not None
            or message.guild is None
            or str(message.guild.id) not in self.config.policy.guild_ids
        ):
            return
        if message.type not in {discord.MessageType.default, discord.MessageType.reply}:
            return
        watched = (
            self.config.prefix.enabled
            and self.prefix_ready
            and self.watch.state(str(message.guild.id))["enabled"]
            and str(message.channel.id) in self.watch.channels(str(message.guild.id))
        )
        body = parse_prefix(message.content) if watched else None
        if body is not None:
            if (
                not self.prefix_ready
                or not isinstance(message.channel, discord.TextChannel)
                or message.channel.type != discord.ChannelType.text
            ):
                return
            bot_member = message.guild.me
            if bot_member is None:
                return
            permissions = message.channel.permissions_for(bot_member)
            healthy = bool(
                permissions.view_channel
                and permissions.send_messages
                and permissions.read_message_history
            )
            await self.update_watch_health(str(message.guild.id), str(message.channel.id), healthy)
            if not healthy:
                return
            key = (str(message.guild.id), str(message.author.id))
            now = time.monotonic()
            if self.message_cooldowns.get(key, 0) > now:
                return
            self.message_cooldowns = {k: v for k, v in self.message_cooldowns.items() if v > now}
            self.message_cooldowns[key] = now + 2
            if len(self.message_tasks) >= 5 or any(
                owner == key for owner in self.message_owners.values()
            ):
                return
            policy_hash = hashlib.sha256(
                json.dumps(
                    {
                        "channels": self.watch.channels(str(message.guild.id)),
                        "revision": self.watch.state(str(message.guild.id))["revision"],
                        "guilds": sorted(self.config.policy.guild_ids),
                        "roles": sorted(self.config.policy.dj_role_ids),
                        "voices": sorted(self.config.policy.voice_channel_ids),
                        "youtube_audio": self.config.youtube_audio_enabled,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            request = self.message_ledger.admit(
                str(message.guild.id),
                str(message.channel.id),
                str(message.id),
                str(message.author.id),
                body,
                policy_hash,
                message.created_at.timestamp(),
            )
            if request is None:
                return
            entry = MentionEntry(message, self.message_ledger, request)
            task = asyncio.current_task()
            assert task is not None
            self.message_owners[request] = key
            self.message_tasks[request] = task
            try:
                if not body or len(body) > 500 or re.match(r"<@!?\d+>", body):
                    await entry.followup.send("‘!!창근아 목록 보여줘’처럼 1~500자로 부탁해.")
                else:
                    await self.natural_input(entry, body)
            finally:
                self.message_ledger.finish(request, "finished")
                self.message_tasks.pop(request, None)
                self.message_owners.pop(request, None)
            return
        if str(message.channel.id) not in self.config.policy.text_channel_ids:
            return
        matched = re.match(
            r"^\s*<@!?" + str(self.user.id) + r">\s*(.+)$", message.content, re.DOTALL
        )
        if matched:
            await self.natural_input(MentionEntry(message), matched[1].strip())

    async def on_ready(self) -> None:
        self.prefix_ready = bool(self.config.prefix.enabled and self.intents.message_content)
        self.prefix_status = "ready" if self.prefix_ready else "disabled"
        # Validate all initial IDs before any seed is committed. Existing DB values win.
        pending = [
            g for g in self.config.policy.guild_ids if not self.watch.state(g)["seed_applied"]
        ]
        seeds: dict[str, list[str]] = {g: [] for g in pending}
        try:
            for identifier in self.config.prefix.channel_ids if pending else []:
                channel = await self.fetch_channel(int(identifier))
                if (
                    not isinstance(channel, discord.TextChannel)
                    or channel.type != discord.ChannelType.text
                ):
                    raise DomainError("watch_seed_required")
                guild = str(channel.guild.id)
                if guild not in self.config.policy.guild_ids:
                    raise DomainError("watch_seed_required")
                code, _ = await watch_commands.inspect(self, channel.guild, identifier)
                if code != "ok":
                    raise DomainError("watch_seed_required")
                if guild in seeds:
                    seeds[guild].append(identifier)
            for guild, identifiers in seeds.items():
                self.watch.seed(guild, identifiers, self.config.prefix.enabled)
        except (DomainError, discord.HTTPException, TimeoutError):
            self.prefix_status = "seed_required"
        for guild in self.config.policy.guild_ids:
            target = self.get_guild(int(guild))
            if target:
                for identifier in self.watch.channels(guild):
                    code, _ = await watch_commands.inspect(self, target, identifier)
                    await self.update_watch_health(guild, identifier, code == "ok")
        self.write_prefix_status()

    async def cancel_watch_work(self, guild: str, requests: list[str]) -> None:
        for request in requests:
            task = self.message_tasks.get(request)
            if task and task is not asyncio.current_task():
                task.cancel()
        with self.db.connect() as conn:
            entry = conn.execute(
                "SELECT current_entry_id,desired_state,generation FROM sessions WHERE guild_id=?",
                (guild,),
            ).fetchone()
            expired = bool(
                entry
                and entry[1] == "resolving"
                and entry[0]
                and not admission_valid(conn, guild, entry[0])
            )
        if expired:
            task = self.audio.preparing.get(guild)
            if task and task is not asyncio.current_task():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await self.audio.expired(guild, entry[2])

    async def update_watch_health(self, guild: str, channel: str, healthy: bool) -> None:
        requests = self.watch.health(guild, channel, healthy)
        await self.cancel_watch_work(guild, requests)

    def write_prefix_status(self) -> None:
        path = self.config.database_path.parent / "prefix-status.json"
        path.write_text(
            json.dumps(
                {
                    "status": self.prefix_status,
                    "ready": self.prefix_ready,
                    "channel_count": sum(
                        len(self.watch.channels(g)) for g in self.config.policy.guild_ids
                    ),
                    "checked_at": time.time(),
                }
            )
        )
        path.chmod(0o600)

    async def on_disconnect(self) -> None:
        self.prefix_ready = False
        self.prefix_status = "disconnected"
        for guild in self.config.policy.guild_ids:
            for identifier in self.watch.channels(guild):
                await self.update_watch_health(guild, identifier, False)
        self.write_prefix_status()

    async def recheck_watch_guild(self, guild: discord.Guild) -> None:
        if str(guild.id) not in self.config.policy.guild_ids:
            return
        for identifier in self.watch.channels(str(guild.id)):
            code, _ = await watch_commands.inspect(self, guild, identifier)
            await self.update_watch_health(str(guild.id), identifier, code == "ok")

    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        await self.recheck_watch_guild(after.guild)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.update_watch_health(str(channel.guild.id), str(channel.id), False)

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        await self.recheck_watch_guild(after.guild)

    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.recheck_watch_guild(role.guild)

    async def _cancel_messages(
        self, guild: int | None, channel: int, messages: set[int], *, include_responses: bool = True
    ) -> None:
        if guild is None:
            return
        requests = self.message_ledger.cancel(
            str(guild),
            str(channel),
            {str(m) for m in messages},
            include_responses=include_responses,
        )
        for request in requests:
            task = self.message_tasks.get(request)
            if task is not None:
                task.cancel()

    async def on_raw_message_edit(self, event: discord.RawMessageUpdateEvent) -> None:
        if "content" in event.data:
            await self._cancel_messages(
                event.guild_id, event.channel_id, {event.message_id}, include_responses=False
            )

    async def on_raw_message_delete(self, event: discord.RawMessageDeleteEvent) -> None:
        await self._cancel_messages(event.guild_id, event.channel_id, {event.message_id})

    async def on_raw_bulk_message_delete(self, event: discord.RawBulkMessageDeleteEvent) -> None:
        await self._cancel_messages(event.guild_id, event.channel_id, event.message_ids)

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        if self.user and member.id == self.user.id and after.channel is None:
            with self.db.transaction() as conn:
                from changgeun.playback.persistence import load_session, save_session

                session = load_session(conn, str(member.guild.id))
                if session.state.value != "disconnected":
                    session.stop(leave=True)
                    save_session(conn, str(member.guild.id), session)

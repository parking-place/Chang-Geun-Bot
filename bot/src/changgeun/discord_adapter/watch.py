"""Administrator-only watch commands; never call the inference gateway."""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

import discord
import httpx
from discord import app_commands

from changgeun.application.watch import AdminGrant
from changgeun.domain.models import DomainError

if TYPE_CHECKING:
    from changgeun.discord_adapter.client import ChangGeunClient

HEALTH = {
    "ok": "정상",
    "missing": "삭제/찾을 수 없음",
    "type": "다른 유형",
    "view": "보기 부족",
    "send": "보내기 부족",
    "history": "답장 읽기 부족",
    "failed": "조회 일시 실패",
}
ERRORS = {
    "administrator_required": (
        "서버 소유자 또는 서버 관리 권한이 필요해. DJ 역할만으로는 바꿀 수 없어."
    ),
    "guild_not_allowed": "등록된 서버의 일반 텍스트 채널에서 사용해줘.",
    "text_channel_not_allowed": "접근할 수 있는 일반 텍스트 채널에서 사용해줘.",
    "permissions_unavailable": "최신 권한을 확인하지 못했어. 잠시 뒤 다시 요청해줘.",
    "watch_seed_required": "초기 설정 이관 필요. 운영자가 제한 설정과 채널 접근을 확인해야 해.",
    "watch_revision_conflict": "그동안 설정이 바뀌었어. 새 현황으로 다시 확인해줘.",
    "watch_channel_limit": "한 서버에 최대 20개 채널을 등록할 수 있어.",
    "watch_empty": "등록된 정상 채널이 없어. 채널을 추가하고 /주시 점검으로 확인해줘.",
    "watch_unavailable": (
        "운영자 허용 또는 메시지 본문 접근이 준비되지 않았어. /주시 점검으로 확인해줘."
    ),
    "watch_cooldown": "관리 명령은 2초 간격으로 사용해줘.",
    "watch_diagnostic_busy": "이 서버의 채널을 점검 중이야. 잠시 뒤 다시 요청해줘.",
    "invalid_arguments": "일반 텍스트 채널을 선택하거나 등록된 항목을 선택해줘.",
}


def normal_text(channel: Any, guild: str) -> bool:
    return (
        isinstance(channel, discord.TextChannel)
        and channel.type == discord.ChannelType.text
        and str(channel.guild.id) == guild
    )


def label(channel: Any, identifier: str) -> str:
    if channel is None:
        return "삭제됨/접근 불가 …" + identifier[-6:]
    return "#" + discord.utils.escape_mentions(discord.utils.escape_markdown(channel.name))[:100]


async def admin(client: ChangGeunClient, interaction: discord.Interaction) -> AdminGrant:
    guild = interaction.guild
    if guild is None or str(guild.id) not in client.config.policy.guild_ids:
        raise DomainError("guild_not_allowed")
    member = await guild.fetch_member(interaction.user.id)
    channel = await guild.fetch_channel(int(interaction.channel_id or 0))
    if not normal_text(channel, str(guild.id)) or guild.me is None:
        raise DomainError("text_channel_not_allowed")
    if (
        not channel.permissions_for(member).view_channel
        or not channel.permissions_for(guild.me).view_channel
    ):
        raise DomainError("text_channel_not_allowed")
    if not (member.id == guild.owner_id or member.guild_permissions.manage_guild):
        raise DomainError("administrator_required")
    return AdminGrant(str(guild.id), str(member.id), time.time())


async def inspect(
    client: ChangGeunClient, guild: discord.Guild, identifier: str
) -> tuple[str, Any]:
    try:
        channel = await guild.fetch_channel(int(identifier))
        if not normal_text(channel, str(guild.id)):
            return "type", channel
        if client.user is None:
            return "failed", channel
        bot = await guild.fetch_member(client.user.id)
        permissions = channel.permissions_for(bot)
        for name, code in [
            ("view_channel", "view"),
            ("send_messages", "send"),
            ("read_message_history", "history"),
        ]:
            if not getattr(permissions, name):
                return code, channel
        return "ok", channel
    except discord.NotFound:
        return "missing", None
    except (discord.HTTPException, TimeoutError):
        return "failed", None


class WatchConfirmation(discord.ui.View):
    def __init__(
        self,
        client: ChangGeunClient,
        grant: AdminGrant,
        action: str,
        channel: str | None,
        revision: int,
        request: str,
    ) -> None:
        super().__init__(timeout=60)
        self.client, self.grant, self.action = client, grant, action
        self.channel, self.revision, self.request = channel, revision, request
        self.deadline = time.monotonic() + 60
        self.used = False

    @discord.ui.button(label="확인", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if (
            self.used
            or time.monotonic() >= self.deadline
            or str(interaction.user.id) != self.grant.actor
            or str(interaction.guild_id) != self.grant.guild
        ):
            await interaction.response.send_message(
                "요청자만 60초 안에 확인할 수 있어.", ephemeral=True
            )
            return
        self.used = True
        # Original request ID makes lost/replayed confirmation a durable no-op.
        await invoke(
            self.client,
            interaction,
            self.action,
            self.channel,
            expected=self.revision,
            confirmed=True,
            request=self.request,
        )
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if (str(interaction.user.id), str(interaction.guild_id)) != (
            self.grant.actor,
            self.grant.guild,
        ):
            await interaction.response.send_message("요청자만 취소할 수 있어.", ephemeral=True)
            return
        self.used = True
        self.stop()
        await interaction.response.edit_message(content="설정을 바꾸지 않았어.", view=None)


class WatchPages(discord.ui.View):
    def __init__(
        self, client: ChangGeunClient, grant: AdminGrant, page: int, revision: int
    ) -> None:
        super().__init__(timeout=60)
        self.client, self.grant, self.page, self.revision = client, grant, page, revision
        self.deadline = time.monotonic() + 60

    async def move(self, interaction: discord.Interaction, offset: int) -> None:
        if time.monotonic() >= self.deadline or (
            str(interaction.user.id),
            str(interaction.guild_id),
        ) != (self.grant.actor, self.grant.guild):
            await interaction.response.send_message(
                "요청자만 페이지를 바꿀 수 있어.", ephemeral=True
            )
            return
        await invoke(
            self.client,
            interaction,
            "list",
            page=max(0, self.page + offset),
            expected=self.revision,
        )

    @discord.ui.button(label="이전")
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.move(interaction, -1)

    @discord.ui.button(label="다음")
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.move(interaction, 1)


class WatchHistoryPages(discord.ui.View):
    def __init__(self, client: ChangGeunClient, grant: AdminGrant, page: int) -> None:
        super().__init__(timeout=60)
        self.client, self.grant, self.page = client, grant, page

    async def move(self, interaction: discord.Interaction, offset: int) -> None:
        if (str(interaction.user.id), str(interaction.guild_id)) != (
            self.grant.actor,
            self.grant.guild,
        ):
            await interaction.response.send_message("요청자만 볼 수 있어.", ephemeral=True)
            return
        await invoke(self.client, interaction, "history", page=max(0, self.page + offset))

    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary)
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.move(interaction, -1)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        await self.move(interaction, 1)


async def show_usage(client: ChangGeunClient, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        async with asyncio.timeout(15):
            grant = await admin(client, interaction)
            local = client.watch.usage(grant.guild)
            shared = None
            if client.gateway is not None:
                try:
                    shared = await client.gateway.usage()
                except (DomainError, TimeoutError, OSError, httpx.HTTPError):
                    pass
            await admin(client, interaction)
            text = (
                f"이 서버 최근 24시간 · 확인 <t:{int(local['checked_at'])}:T>\n"
                f"구조화 처리 {local['commands']} · 접두어 요청 {local['prefix_requests']} "
                f"(취소 {local['prefix_cancelled']})\n"
                f"주시 변경 {local['watch_changes']} · 완료곡 {local['completed_tracks']}\n"
                "요청별 실패·가격·서버별 Jev 호출은 이 집계로 확인할 수 없어."
            )
            if shared is not None:
                text += (
                    f"\n중계 전체 개발 실행 예약 {shared['reserved_calls']}/{shared['limit']} "
                    "(이 서버 사용량 아님)"
                )
            else:
                text += "\n중계 전체 예약: 확인 불가"
            await interaction.followup.send(text, ephemeral=True)
    except (DomainError, discord.HTTPException, TimeoutError):
        await interaction.followup.send(
            "최신 관리자 권한이나 집계를 확인하지 못했어. 다시 시도해줘.", ephemeral=True
        )


async def invoke(
    client: ChangGeunClient,
    interaction: discord.Interaction,
    action: str,
    channel: str | None = None,
    *,
    expected: int | None = None,
    confirmed: bool = False,
    request: str | None = None,
    page: int = 0,
) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        async with asyncio.timeout(15):
            key = (str(interaction.guild_id), str(interaction.user.id))
            now = time.monotonic()
            if client.watch_cooldowns.get(key, 0) > now:
                raise DomainError("watch_cooldown")
            client.watch_cooldowns = {k: v for k, v in client.watch_cooldowns.items() if v > now}
            client.watch_cooldowns[key] = now + 2
            grant = await admin(client, interaction)
            guild = interaction.guild
            assert guild is not None
            state = client.watch.state(grant.guild)
            channels = client.watch.channels(grant.guild)
            if action == "history":
                events = client.watch.history(grant.guild)
                page = min(page, max(0, (len(events) - 1) // 10))
                names = {
                    "add": "추가",
                    "remove": "제거",
                    "enable": "켜기",
                    "disable": "끄기",
                    "health": "접근 상태 변경",
                }
                lines = [
                    f"<t:{int(row['created_at'])}:f> · {names.get(row['action'], '변경')} "
                    f"r{row['revision']} · 취소 {row['requests_cancelled']} "
                    f"· 승인 만료 {row['admissions_revoked']}"
                    for row in events[page * 10 : (page + 1) * 10]
                ]
                await admin(client, interaction)
                history_view: discord.ui.View | None = (
                    WatchHistoryPages(client, grant, page) if len(events) > 10 else None
                )
                text = "주시 변경 이력 · 최근 90일/최대 100건\n" + (
                    "\n".join(lines) or "변경 이력이 없어."
                )
                if history_view is not None:
                    await interaction.followup.send(text, view=history_view, ephemeral=True)
                else:
                    await interaction.followup.send(text, ephemeral=True)
                return
            if action in {"list", "inspect"}:
                if expected is not None and expected != state["revision"]:
                    raise DomainError("watch_revision_conflict")
                if action == "inspect" and grant.guild in client.watch_diagnostics:
                    raise DomainError("watch_diagnostic_busy")
                if action == "inspect":
                    client.watch_diagnostics.add(grant.guild)
                try:
                    identifiers = [channel] if channel else channels
                    if action == "list":
                        page = min(page, max(0, (len(identifiers) - 1) // 10))
                        identifiers = identifiers[page * 10 : (page + 1) * 10]
                    semaphore = asyncio.Semaphore(4)

                    async def probe(identifier: str) -> str:
                        async with semaphore:
                            code, target = await inspect(client, guild, identifier)
                            return label(target, identifier) + " — " + HEALTH[code]

                    lines = await asyncio.gather(*(probe(i) for i in identifiers))
                finally:
                    if action == "inspect":
                        client.watch_diagnostics.discard(grant.guild)
                # Recheck authority after network work; diagnostics never mutate settings.
                await admin(client, interaction)
                gateway_state = (
                    "연결 준비됨"
                    if client.intents.message_content and client.is_ready()
                    else "확인 필요"
                )
                text = (
                    f"주시 {'켜짐' if state['enabled'] else '꺼짐'} · 등록 {len(channels)}/20\n"
                    f"초기 이관: {'완료' if state['seed_applied'] else '필요'}\n"
                    f"운영자 허용: {'켜짐' if client.config.prefix.enabled else '꺼짐'} · "
                    f"본문 Gateway: {gateway_state}\n"
                    "Portal 토글은 봇이 직접 조회하거나 변경할 수 없어.\n"
                    + ("\n".join(lines) or "등록된 채널 없음")
                    + f"\n확인 시각: <t:{int(time.time())}:T>"
                )
                view = (
                    WatchPages(client, grant, page, state["revision"])
                    if action == "list" and len(channels) > 10
                    else None
                )
                if view is not None:
                    await interaction.followup.send(text, view=view, ephemeral=True)
                else:
                    await interaction.followup.send(text, ephemeral=True)
                return
            if not state["seed_applied"]:
                raise DomainError("watch_seed_required")
            if action in {"add", "remove"}:
                channel = channel or str(interaction.channel_id)
                matched = re.fullmatch(r"(?:<#(\d+)>|(\d+))", channel)
                if not matched:
                    raise DomainError("invalid_arguments")
                channel = matched[1] or matched[2]
            if action == "add":
                code, target = await inspect(client, guild, channel or "")
                member = await guild.fetch_member(interaction.user.id)
                if code != "ok" or not target.permissions_for(member).view_channel:
                    raise DomainError("text_channel_not_allowed")
            if action == "enable" and not state["enabled"]:
                if (
                    not client.config.prefix.enabled
                    or not client.intents.message_content
                    or not client.is_ready()
                ):
                    raise DomainError("watch_unavailable")
                healthy = False
                for identifier in channels:
                    code, _ = await inspect(client, guild, identifier)
                    await client.update_watch_health(grant.guild, identifier, code == "ok")
                    healthy |= code == "ok"
                if not healthy:
                    raise DomainError("watch_empty")
                state = client.watch.state(grant.guild)
            revision = state["revision"] if expected is None else expected
            needs_confirmation = (
                action == "remove"
                and channel in channels
                or action == "disable"
                and state["enabled"]
            )
            if needs_confirmation and not confirmed:
                requests, admissions = client.watch.counts(grant.guild, channel)
                confirmation_view = WatchConfirmation(
                    client, grant, action, channel, revision, str(interaction.id)
                )
                await interaction.followup.send(
                    f"{'이 채널을 제거' if action == 'remove' else '주시를 중지'}할까? "
                    f"현재 예상: 진행 요청 {requests}개 취소, 시작 전 {admissions}곡 승인 만료. "
                    "확인 전 같은 범위에 추가된 요청과 곡도 포함해. 현재곡은 계속 재생해. "
                    "60초 안에 확인해줘.",
                    view=confirmation_view,
                    ephemeral=True,
                )
                return
            # Fresh permissions are issued immediately before the transaction.
            grant = await admin(client, interaction)
            result = client.watch.change(
                grant, request or str(interaction.id), action, channel, revision
            )
            await client.cancel_watch_work(grant.guild, result["cancelled"])
            new_state = client.watch.state(grant.guild)
            if not result["changed"]:
                text = "이미 같은 상태야. 설정을 바꾸지 않았어."
            elif action == "add":
                text = "채널을 등록했어. " + (
                    "이제 !!창근아에 반응할게."
                    if new_state["enabled"]
                    else "주시는 꺼져 있어. /주시 켜기로 시작해줘."
                )
            elif action == "enable":
                text = "주시를 켰어. 정상 채널에서 !!창근아에 반응할게."
            else:
                text = (
                    f"설정을 저장했어. 실제 취소 요청 {len(result['cancelled'])}개, "
                    f"시작 전 승인 만료 {result['admissions_revoked']}곡. 현재곡은 계속 재생해."
                )
                if not client.watch.channels(grant.guild):
                    text += " 등록된 채널이 없어 주시도 껐어. 추가한 뒤 /주시 켜기로 시작해줘."
                elif action == "disable":
                    text += " 채널 목록은 보관했어."
            client.write_prefix_status()
            await interaction.followup.send(text, ephemeral=True)
    except DomainError as exc:
        await interaction.followup.send(
            ERRORS.get(exc.code, "저장 조건을 확인해줘. /주시 목록으로 상태를 확인할 수 있어."),
            ephemeral=True,
        )
    except (discord.HTTPException, TimeoutError):
        await interaction.followup.send(
            "조회나 응답을 완료하지 못했어. /주시 목록으로 저장 상태를 확인해줘.", ephemeral=True
        )


def register(client: ChangGeunClient) -> None:
    group = app_commands.Group(
        name="주시",
        description="!!창근아 반응 채널 관리",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @group.command(name="추가", description="!!창근아 반응 채널 등록 (생략하면 현재 채널)")
    async def add(
        interaction: discord.Interaction, 채널: discord.TextChannel | None = None
    ) -> None:
        await invoke(client, interaction, "add", str(채널.id) if 채널 else None)

    @group.command(name="제거", description="등록 채널 제거 (생략하면 현재 채널)")
    async def remove(interaction: discord.Interaction, 채널: str | None = None) -> None:
        await invoke(client, interaction, "remove", 채널)

    @remove.autocomplete("채널")
    async def complete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            async with asyncio.timeout(2):
                grant = await admin(client, interaction)
            guild = interaction.guild
            assert guild is not None
            return [
                app_commands.Choice(name=label(guild.get_channel(int(i)), i), value=i)
                for i in client.watch.channels(grant.guild)
                if current in label(guild.get_channel(int(i)), i) or current in i
            ][:20]
        except (DomainError, discord.HTTPException, TimeoutError):
            return []

    @group.command(name="목록", description="주시 채널과 활성 상태 보기")
    async def listing(interaction: discord.Interaction) -> None:
        await invoke(client, interaction, "list")

    @group.command(name="켜기", description="등록된 정상 채널의 !!창근아 반응 켜기")
    async def enable(interaction: discord.Interaction) -> None:
        await invoke(client, interaction, "enable")

    @group.command(name="끄기", description="채널 목록을 보관하고 !!창근아 반응 끄기")
    async def disable(interaction: discord.Interaction) -> None:
        await invoke(client, interaction, "disable")

    @group.command(name="점검", description="선택한 채널 또는 등록 목록 전체 점검")
    async def diagnostic(
        interaction: discord.Interaction, 채널: discord.TextChannel | None = None
    ) -> None:
        await invoke(client, interaction, "inspect", str(채널.id) if 채널 else None)

    @group.command(name="이력", description="최근 90일 주시 변경 이력 보기")
    async def history(interaction: discord.Interaction) -> None:
        await invoke(client, interaction, "history")

    client.tree.add_command(group)

    operations = app_commands.Group(
        name="운영",
        description="서버 관리자 운영 정보",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @operations.command(name="사용량", description="이 서버 처리와 중계 전체 예약 현황")
    async def usage(interaction: discord.Interaction) -> None:
        await show_usage(client, interaction)

    client.tree.add_command(operations)

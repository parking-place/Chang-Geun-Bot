"""Opt-in Discord adapter for validated parser drafts; never a second executor."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import discord

from changgeun.discord_adapter.mention import MentionEntry
from changgeun.domain.models import DomainError
from changgeun.parser.contracts import ParseError
from changgeun.parser.followup import TypedQuestion, answer_typed
from changgeun.parser.gateway import ParserSession
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.normalizer import InputNormalizer, NormalizedInput
from changgeun.parser.orchestrator import ParserOrchestrator
from changgeun.parser.pending import PendingStore
from changgeun.parser.validation import DraftValidator, TrustedContext, ValidatedCommand

if TYPE_CHECKING:
    from changgeun.discord_adapter.client import ChangGeunClient
    from changgeun.domain.models import Actor


class _DeferredResponse:
    def __init__(self, entry: discord.Interaction) -> None:
        self.entry = entry

    def is_done(self) -> bool:
        return self.entry.response.is_done()

    async def defer(self, **kwargs: Any) -> None:
        if not self.entry.response.is_done():
            await self.entry.response.defer(**kwargs)

    async def send_message(self, content: str, **kwargs: Any) -> Any:
        if self.entry.response.is_done():
            return await self.entry.followup.send(content, **kwargs)
        return await self.entry.response.send_message(content, **kwargs)


class _DeferredEntry:
    def __init__(self, entry: discord.Interaction) -> None:
        self.entry = entry
        self.response = _DeferredResponse(entry)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.entry, name)


class _BoundMentionEntry(MentionEntry):
    """Preserve prefix authorization while using the admitted request's idempotency key."""

    def __init__(self, source: MentionEntry, root_id: str) -> None:
        self.__dict__.update(source.__dict__)
        self.request_id = root_id
        self.__dict__["id"] = root_id


@dataclass(frozen=True)
class _Confirmation:
    validated: ValidatedCommand
    source: discord.Interaction | MentionEntry
    entry: discord.Interaction | MentionEntry | _DeferredEntry
    view: NormalizedInput
    root_id: str
    pass_id: str
    scope_hash: str
    validator: DraftValidator
    guild: discord.Guild
    contexts: dict[str, TrustedContext] | None = None


@dataclass(frozen=True)
class _TypedContext:
    source: discord.Interaction | MentionEntry
    entry: discord.Interaction | MentionEntry | _DeferredEntry
    view: NormalizedInput
    root_id: str
    pass_id: str
    scope_hash: str
    validator: DraftValidator
    guild: discord.Guild
    actor_id: str
    channel_id: str


class _TypedModal(discord.ui.Modal):
    def __init__(self, bridge: ParserV2Bridge, token: str, context: _TypedContext,
                 label: str, max_length: int) -> None:
        super().__init__(title="명령에 필요한 값 입력", timeout=60)
        self.bridge, self.token, self.context = bridge, token, context
        self.answer: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=label[:45], max_length=min(max_length, 4000)
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        context = self.context
        try:
            action = self.bridge.pending.consume(
                self.token, kind="typed", root_id=context.root_id,
                guild_id=str(interaction.guild_id), channel_id=str(interaction.channel_id),
                actor_id=str(interaction.user.id),
            )
            spec = self.bridge.client.command_service.specs[action.command_id]
            draft, trusted = answer_typed(
                action, str(self.answer.value), spec,
                guild_id=str(interaction.guild_id), channel_id=str(interaction.channel_id),
                actor_id=str(interaction.user.id),
            )
            await interaction.response.defer(ephemeral=True, thinking=True)
            fresh = await self.bridge.client.fresh_actor(context.source)
            contexts = {trusted.context_id: trusted}
            checked = context.validator.validate(
                draft, context.view, fresh, root_id=context.root_id,
                pass_id=context.pass_id, scope_hash=context.scope_hash,
                watch_allowed=True, guild=context.guild,
                member=await context.guild.fetch_member(interaction.user.id),
                contexts=contexts,
            )
            await self.bridge._deliver(
                checked, context.source, context.entry, context.view,
                context.root_id, context.pass_id, context.scope_hash,
                context.validator, context.guild, contexts,
            )
            await interaction.followup.send("답변을 반영했어.", ephemeral=True)
        except (ParseError, DomainError, discord.HTTPException):
            message = "답변이나 요청 상태가 맞지 않아 실행하지 않았어. 새로 요청해줘."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)


class _TypedView(discord.ui.View):
    def __init__(self, bridge: ParserV2Bridge, token: str, context: _TypedContext,
                 label: str, max_length: int) -> None:
        super().__init__(timeout=60)
        self.bridge, self.token, self.context = bridge, token, context
        self.label, self.max_length = label, max_length

    @discord.ui.button(label="값 입력", style=discord.ButtonStyle.primary)
    async def type_answer(self, interaction: discord.Interaction,
                          button: discord.ui.Button[Any]) -> None:
        if (str(interaction.guild_id), str(interaction.channel_id),
                str(interaction.user.id)) != (
                    str(self.context.guild.id), self.context.channel_id,
                    self.context.actor_id):
            await interaction.response.send_message("요청자만 답할 수 있어.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _TypedModal(self.bridge, self.token, self.context, self.label, self.max_length)
        )


class _ConfirmView(discord.ui.View):
    def __init__(self, bridge: ParserV2Bridge, token: str, action: _Confirmation) -> None:
        super().__init__(timeout=300)
        self.bridge, self.token, self.action = bridge, token, action

    @discord.ui.button(label="명령 실행 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction,
                      button: discord.ui.Button[Any]) -> None:
        action = self.action
        consumed = False
        try:
            self.bridge.pending.consume(
                self.token, kind="confirm", root_id=action.root_id,
                guild_id=str(interaction.guild_id), channel_id=str(interaction.channel_id),
                actor_id=str(interaction.user.id),
            )
            consumed = True
            await interaction.response.defer(ephemeral=True, thinking=True)
            fresh = await self.bridge.client.fresh_actor(action.source)
            await action.validator.invoke(
                action.validated, action.entry, fresh, action.view,
                root_id=action.root_id, pass_id=action.pass_id,
                scope_hash=action.scope_hash, watch_allowed=True,
                confirmation_consumed=True, guild=action.guild,
                member=await action.guild.fetch_member(interaction.user.id),
                contexts=action.contexts,
            )
            await interaction.followup.send("확인한 명령을 처리했어.", ephemeral=True)
        except (ParseError, DomainError, discord.HTTPException):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "요청이나 대상 상태가 달라져 실행하지 않았어. 새로 요청해줘.", ephemeral=True)
            else:
                await interaction.followup.send(
                    "요청이나 대상 상태가 달라져 실행하지 않았어. 새로 요청해줘.", ephemeral=True)
        finally:
            if consumed:
                self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction,
                     button: discord.ui.Button[Any]) -> None:
        if not self.bridge.pending.cancel(
            self.token, root_id=self.action.root_id,
            guild_id=str(interaction.guild_id), channel_id=str(interaction.channel_id),
            actor_id=str(interaction.user.id),
        ):
            await interaction.response.send_message("이 요청은 이미 종료됐어.", ephemeral=True)
            return
        await interaction.response.edit_message(content="명령을 취소했어.", view=None)
        self.stop()


class ParserV2Bridge:
    def __init__(self, client: ChangGeunClient) -> None:
        self.client = client
        self.pending = PendingStore()

    async def parse(self, source: discord.Interaction | MentionEntry, text: str,
                    actor: Actor, request_id: str) -> None:
        client = self.client
        if client.gateway is None:
            raise ParseError("gateway_not_configured")
        await client.gateway.ready()
        view = InputNormalizer().normalize(text)
        scope_hash = hashlib.sha256(
            f"{actor.guild_id}:{actor.text_channel_id}:{actor.user_id}".encode()
        ).hexdigest()
        session = ParserSession(client.gateway, request_id=request_id,
                                scope_hash=scope_hash, original_text=text)
        interpreter = JevInterpreter(client.command_service, session, client.db,
                                     client.config.policy)
        orchestrator = ParserOrchestrator(
            interpreter, session, client.command_service, client.db, client.config.policy,
            llm_enabled=client.config.parser_llm_fallback == "gpt-5-nano",
        )
        guild = source.guild
        if guild is None:
            raise ParseError("guild_not_allowed")
        member = await guild.fetch_member(source.user.id)
        outcome = await orchestrator.parse(
            view, actor, root_id=request_id, scope_hash=scope_hash,
            expires_at=session.root["expires_at"], guild=guild, member=member,
        )
        if outcome.status == "clarify" and outcome.draft is not None and (
            len(outcome.missing) == 1
        ):
            partial = outcome.draft
            spec = client.command_service.specs[partial.command_id]
            if spec.private and isinstance(source, MentionEntry):
                await source.followup.send("개인 결과는 슬래시 명령에서 확인해줘.", ephemeral=True)
                return
            missing = outcome.missing[0]
            argument = next(item for item in spec.arguments if item.name == missing)
            pass_id = ("after_rewrite" if partial.parser_source == "jev_after_rewrite"
                       else "initial")
            snapshot = next((item for item in orchestrator.snapshots.values()
                             if item.argument == missing and item.pass_id == pass_id
                             and item.root_id == request_id), None)
            typed_entry: discord.Interaction | MentionEntry | _DeferredEntry = (
                _BoundMentionEntry(source, request_id) if isinstance(source, MentionEntry)
                else _DeferredEntry(source)
            )
            validator = DraftValidator(client.command_service, client.db,
                                       client.config.policy, orchestrator.snapshots)
            context = _TypedContext(source, typed_entry, view, request_id, pass_id,
                                    scope_hash, validator, guild, actor.user_id,
                                    actor.text_channel_id)
            token = self.pending.issue(
                kind="typed", root_id=request_id, guild_id=actor.guild_id,
                channel_id=actor.text_channel_id, actor_id=actor.user_id,
                command_id=partial.command_id,
                argument=missing, payload=TypedQuestion(partial, snapshot),
            )
            await source.followup.send(
                f"{discord.utils.escape_markdown(spec.name)} 명령의 "
                f"{discord.utils.escape_markdown(missing)} 값을 입력해줘.",
                view=_TypedView(self, token, context, missing, argument.max_length),
                ephemeral=True,
            )
            return
        if outcome.status != "parsed" or outcome.draft is None:
            await source.followup.send(
                "대상이나 값을 확정하지 못했어. 더 구체적으로 말하거나 슬래시 명령을 사용해줘.",
                ephemeral=True,
            )
            return
        draft = outcome.draft
        spec = client.command_service.specs[draft.command_id]
        if spec.private and isinstance(source, MentionEntry):
            await source.followup.send("개인 결과는 슬래시 명령에서 확인해줘.", ephemeral=True)
            return
        pass_id = ("after_rewrite" if draft.parser_source == "jev_after_rewrite"
                   else "full_parse" if draft.parser_source == "llm_full_parse"
                   else "initial")
        validator = DraftValidator(client.command_service, client.db,
                                   client.config.policy, orchestrator.snapshots)
        checked = validator.validate(
            draft, view, actor, root_id=request_id, pass_id=pass_id,
            scope_hash=scope_hash, watch_allowed=True, guild=guild, member=member,
        )
        entry: discord.Interaction | MentionEntry | _DeferredEntry = (
            _BoundMentionEntry(source, request_id) if isinstance(source, MentionEntry)
            else _DeferredEntry(source)
        )
        await self._deliver(checked, source, entry, view, request_id, pass_id,
                            scope_hash, validator, guild)

    async def _deliver(
        self, checked: ValidatedCommand, source: discord.Interaction | MentionEntry,
        entry: discord.Interaction | MentionEntry | _DeferredEntry,
        view: NormalizedInput, request_id: str, pass_id: str, scope_hash: str,
        validator: DraftValidator, guild: discord.Guild,
        contexts: dict[str, TrustedContext] | None = None,
    ) -> None:
        spec = self.client.command_service.specs[checked.draft.command_id]
        if checked.requires_confirmation:
            action = _Confirmation(checked, source, entry, view, request_id, pass_id,
                                   scope_hash, validator, guild, contexts)
            token = self.pending.issue(
                kind="confirm", root_id=request_id, guild_id=checked.guild_id,
                channel_id=str(source.channel_id), actor_id=checked.actor_id,
                command_id=checked.draft.command_id, payload=action,
            )
            preview = f"{discord.utils.escape_markdown(spec.name)} 명령을 실행할까?"
            await source.followup.send(preview, view=_ConfirmView(self, token, action),
                                       ephemeral=True)
            return
        fresh = await self.client.fresh_actor(source)
        await validator.invoke(
            checked, entry, fresh, view, root_id=request_id, pass_id=pass_id,
            scope_hash=scope_hash, watch_allowed=True, confirmation_consumed=False,
            guild=guild, member=await guild.fetch_member(source.user.id),
            contexts=contexts,
        )

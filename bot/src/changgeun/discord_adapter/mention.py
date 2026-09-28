"""Explicit mention entry point using the same authorization and executor as slash."""

from __future__ import annotations

import asyncio
from typing import Any

import discord

from changgeun.discord_adapter.prefix import MessageLedger
from changgeun.domain.models import DomainError


class MessageResponse:
    def __init__(self, message: discord.Message, followup: MessageFollowup) -> None:
        self.message = message
        self.followup = followup
        self.done = False
        self.pending_view: discord.ui.View | None = None

    def is_done(self) -> bool:
        return self.done

    async def defer(self, **kwargs: Any) -> None:
        if self.done:
            return
        self.done = True
        if self.followup.ledger is not None:
            await self.followup.send("요청을 확인하고 있어.", view=self.pending_view)
        else:
            await self.message.channel.typing()


class MessageFollowup:
    def __init__(
        self,
        message: discord.Message,
        ledger: MessageLedger | None = None,
        request_id: str | None = None,
    ) -> None:
        self.message = message
        self.ledger, self.request_id = ledger, request_id
        self.result: discord.Message | None = None
        self.lock = asyncio.Lock()

    async def send(self, content: str, **kwargs: Any) -> discord.Message:
        # Message replies are public; Discord ephemeral responses require interactions.
        kwargs.pop("ephemeral", None)
        async with self.lock:
            if self.ledger is not None and self.request_id is not None:
                if not self.ledger.response_allowed(self.request_id):
                    raise DomainError("message_request_cancelled")
            kwargs.setdefault("view", None)
            if self.result is not None:
                file = kwargs.pop("file", None)
                if file is not None:
                    kwargs["attachments"] = [file]
                return await self.result.edit(
                    content=content, allowed_mentions=discord.AllowedMentions.none(), **kwargs
                )
            if self.ledger is not None and self.request_id is not None:
                if not self.ledger.reserve_response(self.request_id):
                    raise DomainError("message_response_unknown")
            self.result = await self.message.reply(
                content,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                **kwargs,
            )
            if self.ledger is not None and self.request_id is not None:
                self.ledger.record_response(self.request_id, str(self.result.id))
            return self.result


class MentionEntry:
    def __init__(
        self,
        message: discord.Message,
        ledger: MessageLedger | None = None,
        request_id: str | None = None,
    ) -> None:
        self.message = message
        self.id = message.id
        self.user = message.author
        self.guild = message.guild
        self.guild_id = message.guild.id if message.guild else None
        self.channel_id = message.channel.id
        self.type = discord.InteractionType.application_command
        self.request_id = request_id
        self.followup = MessageFollowup(message, ledger, request_id)
        self.response = MessageResponse(message, self.followup)

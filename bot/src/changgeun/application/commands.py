"""Closed, typed command service; handler identity comes only from trusted code."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from changgeun.domain.models import Actor, Policy
from changgeun.parser.contracts import ParseError
from changgeun.parser.registry import CommandSpec

Handler = Callable[[Any, dict[str, Any]], Awaitable[None]]


class CommandService:
    def __init__(self, specs: dict[str, CommandSpec], handlers: dict[str, Handler]) -> None:
        if specs.keys() != handlers.keys():
            raise ValueError("command/handler inventory mismatch")
        self.specs, self.handlers = specs, handlers

    async def invoke(
        self, identifier: str, arguments: dict[str, Any], entry: Any,
        actor: Actor, policy: Policy,
    ) -> None:
        spec = self.specs.get(identifier)
        if spec is None or not spec.allowed(actor, policy):
            raise ParseError("command_not_allowed")
        values = spec.validate(arguments)
        await self.handlers[identifier](entry, values)

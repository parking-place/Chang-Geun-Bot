"""Use live slash parameter definitions as the public schema's single source."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from discord import app_commands

from changgeun.application.commands import CommandService, Handler
from changgeun.nlp.command_registry import COMMANDS
from changgeun.parser.contracts import ParseError
from changgeun.parser.registry import ArgumentSpec, CommandSpec, permission, risk


def argument(identifier: str, p: Any) -> ArgumentSpec:
    name, kind = p.name, p.type.name
    source, collection, dependency = "source_span", None, None
    minimum, maximum = p.min_value, p.max_value
    if name in {"목록", "기존목록"}:
        source, collection = "collection", "playlists"
    elif name == "곡":
        source, collection = "collection", "tracks"
    elif name == "채널":
        source = "collection"
        collection = ("voice_channels" if identifier == "C21" else
                      "watched_channels" if identifier == "C41" else "text_channels")
    elif name == "번호":
        source = "collection"
        collection = "playlist_entries" if identifier in {"C12", "C13"} else "queue_entries"
        dependency = "목록" if collection == "playlist_entries" else None
    elif name == "제안번호":
        source, collection = "collection", "proposals"
    elif name == "변경":
        source, collection = "collection", "changes"
    elif name == "파일":
        source, collection = "collection", "attachments"
    elif name == "링크":
        source = "url"
    elif kind in {"boolean", "integer"} or p.choices:
        source = "registry_options" if kind == "boolean" or p.choices else "number"
    limits = {"곡수": (1, 100), "최근제외일": (0, 365), "최대초": (1, 86400),
              "번호": (1, 10000), "위치": (1, 10000), "시드": (0, 2**31-1)}
    if name in limits:
        minimum, maximum = limits[name]
    if p.required:
        default = None
    else:
        default = p.default
    return ArgumentSpec(
        name, kind, p.required, default, source, collection, dependency,
        minimum, maximum, 2048 if name == "링크" else 1000 if name in {"별칭", "태그", "제외태그"}
        else 100, tuple(str(c.value) for c in p.choices),
        f"{name}: {p.description}" if p.description != "…" else name,
    )


def build_service(tree: app_commands.CommandTree[Any]) -> CommandService:
    commands = {command.qualified_name: command for command in tree.walk_commands()
                if isinstance(command, app_commands.Command)}
    expected = {item.label for item in COMMANDS}
    if commands.keys() != expected:
        raise ValueError("public slash inventory differs from closed command registry")
    specs: dict[str, CommandSpec] = {}
    handlers: dict[str, Handler] = {}
    for item in COMMANDS:
        command = commands[item.label]
        specs[item.identifier] = CommandSpec(
            item.identifier, item.label, item.description,
            tuple(argument(item.identifier, p) for p in command.parameters),
            permission(item.identifier), risk(item.identifier),
            item.identifier in {"C33", "C36"} or int(item.identifier[1:]) >= 40,
        )
        handlers[item.identifier] = callback_handler(command)
    return CommandService(specs, handlers)


def callback_handler(command: app_commands.Command[Any, ..., Any]) -> Handler:
    async def invoke(entry: Any, values: dict[str, Any]) -> None:
        kwargs = dict(values)
        for p in command.parameters:
            value = kwargs[p.name]
            if value is None:
                continue
            if p.choices:
                choice = next((c for c in p.choices if c.value == value), None)
                if choice is None:
                    raise ParseError("invalid_enum")
                kwargs[p.name] = choice
            elif p.type.name == "channel":
                channel = entry.guild.get_channel(int(value)) if entry.guild else None
                if channel is None:
                    raise ParseError("channel_unavailable")
                kwargs[p.name] = channel
            elif p.type.name == "attachment":
                attachments = getattr(getattr(entry, "message", None), "attachments", ())
                attachment = next((a for a in attachments if str(a.id) == value), None)
                if attachment is None:
                    raise ParseError("attachment_unavailable")
                kwargs[p.name] = attachment
        callback = cast(Callable[..., Awaitable[None]], command.callback)
        await callback(entry, **kwargs)
    return invoke

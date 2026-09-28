"""Resolve one pending answer deterministically, without a model call."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from changgeun.parser.collections import CollectionSnapshot
from changgeun.parser.contracts import CommandDraft, Evidence, ParseError
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.pending import PendingAction
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.parser.validation import TrustedContext
from changgeun.parser.values import numbers


@dataclass(frozen=True)
class TypedQuestion:
    draft: CommandDraft
    snapshot: CollectionSnapshot | None = None


def answer_typed(
    action: PendingAction, answer: str, spec: CommandSpec, *,
    guild_id: str, channel_id: str, actor_id: str,
) -> tuple[CommandDraft, TrustedContext]:
    """The caller must atomically consume the pending token before calling this."""
    if (action.kind != "typed" or action.command_id != spec.identifier
            or action.guild_id != guild_id or action.channel_id != channel_id
            or action.actor_id != actor_id or not isinstance(action.payload, TypedQuestion)
            or action.payload.draft.command_id != spec.identifier):
        raise ParseError("pending_context_mismatch")
    arg = next((item for item in spec.arguments if item.name == action.argument), None)
    if arg is None or not isinstance(answer, str):
        raise ParseError("pending_argument_mismatch")
    value, selection_id = _value(answer.strip(), arg, action.payload.snapshot)
    arg.validate(value)
    context_id = secrets.token_urlsafe(24)
    context = TrustedContext(context_id, action.root_id, guild_id, channel_id,
                             actor_id, spec.identifier, arg.name, value, selection_id)
    draft = action.payload.draft
    arguments = {**draft.arguments, arg.name: value}
    evidence = {**draft.evidence, arg.name: Evidence(
        "collection" if selection_id else "context",
        snapshot_id=action.payload.snapshot.snapshot_id
        if selection_id and action.payload.snapshot else None,
        selection_id=selection_id, context_id=context_id,
    )}
    return CommandDraft(draft.command_id, arguments, evidence,
                        draft.parser_source, draft.llm_assisted), context


def _value(text: str, arg: ArgumentSpec,
           snapshot: CollectionSnapshot | None) -> tuple[Any, str | None]:
    if not text:
        raise ParseError("empty_typed_answer")
    if arg.collection:
        if snapshot is None or snapshot.collection_key != arg.collection or not snapshot.complete:
            raise ParseError("pending_collection_missing")
        matches = [item for item in snapshot.selections if text == item.item.label
                   or text == item.token]
        if text.isdecimal() and 1 <= int(text) <= len(snapshot.selections):
            matches = [snapshot.selections[int(text) - 1]]
        if len(matches) != 1:
            raise ParseError("typed_choice_ambiguous" if matches else "typed_choice_unknown")
        selected = matches[0]
        value = (selected.item.execution_value if selected.item.execution_value is not None
                 else selected.item.object_id)
        return value, selected.token
    if arg.kind == "integer":
        view = InputNormalizer().normalize(text)
        parsed_numbers = numbers(view)
        if len(parsed_numbers) != 1 or parsed_numbers[0].evidence.raw != text:
            raise ParseError("invalid_integer")
        return parsed_numbers[0].value, None
    if arg.kind == "boolean":
        if text in {"예", "네", "켜", "켜기", "true"}:
            return True, None
        if text in {"아니요", "아니", "꺼", "끄기", "false"}:
            return False, None
        raise ParseError("invalid_boolean")
    if arg.kind in {"string", "channel", "attachment"}:
        if arg.choices and text not in arg.choices:
            raise ParseError("invalid_enum")
        return text, None
    raise ParseError("unsupported_argument_type")

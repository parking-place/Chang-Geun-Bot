"""The single fresh authorization and provenance gate before command callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.collections import CollectionSnapshot, resolve_collection
from changgeun.parser.contracts import CommandDraft, Evidence, ParseError
from changgeun.parser.normalizer import NormalizedInput
from changgeun.parser.registry import ArgumentSpec
from changgeun.parser.values import numbers
from changgeun.storage.database import Database


@dataclass(frozen=True)
class ValidatedCommand:
    draft: CommandDraft
    arguments: dict[str, Any]
    guild_id: str
    actor_id: str
    requires_confirmation: bool


@dataclass(frozen=True)
class TrustedContext:
    """A value supplied by a bound, one-use UI/typed answer, never by a model."""

    context_id: str
    root_id: str
    guild_id: str
    channel_id: str
    actor_id: str
    command_id: str
    argument: str
    value: Any
    selection_id: str | None = None


class DraftValidator:
    def __init__(self, service: CommandService, db: Database, policy: Policy,
                 snapshots: dict[str, CollectionSnapshot]) -> None:
        self.service, self.db, self.policy, self.snapshots = service, db, policy, snapshots

    def validate(
        self, draft: CommandDraft, view: NormalizedInput, actor: Actor, *,
        root_id: str, pass_id: str, scope_hash: str, watch_allowed: bool,
        guild: Any = None, member: Any = None,
        contexts: dict[str, TrustedContext] | None = None,
    ) -> ValidatedCommand:
        if not watch_allowed or actor.guild_id not in self.policy.guild_ids:
            raise ParseError("channel_not_allowed")
        spec = self.service.specs.get(draft.command_id)
        if spec is None or not spec.allowed(actor, self.policy):
            raise ParseError("command_not_allowed")
        if draft.command_id == "C39":
            raise ParseError("recursive_parser_command")
        values = spec.validate(draft.arguments)
        if set(draft.evidence) - {argument.name for argument in spec.arguments}:
            raise ParseError("unknown_evidence")
        for argument in spec.arguments:
            supplied = argument.name in draft.arguments
            proof = draft.evidence.get(argument.name)
            value = values[argument.name]
            if not supplied:
                if argument.required:
                    raise ParseError("missing_argument")
                if proof is not None and proof.source != "default":
                    raise ParseError("untrusted_default")
                continue
            if proof is None:
                raise ParseError("missing_evidence")
            if proof.source == "default":
                raise ParseError("untrusted_default")
            trusted = None
            if proof.context_id is not None:
                trusted = (contexts or {}).get(proof.context_id)
                if (trusted is None or proof.context_id != trusted.context_id
                        or (trusted.root_id, trusted.guild_id, trusted.channel_id,
                            trusted.actor_id, trusted.command_id, trusted.argument) != (
                                root_id, actor.guild_id, actor.text_channel_id,
                                actor.user_id, draft.command_id, argument.name)
                        or type(trusted.value) is not type(value) or trusted.value != value
                        or (proof.selection_id is not None
                            and proof.selection_id != trusted.selection_id)):
                    raise ParseError("foreign_context")
            if argument.collection:
                self._collection(argument, value, proof, view, actor, spec, root_id=root_id,
                                 pass_id=pass_id, scope_hash=scope_hash,
                                 values=values, guild=guild, member=member,
                                 trusted=trusted)
            elif proof.source == "context" and trusted is not None:
                pass
            elif proof.source == "span":
                if not view.verify(proof):
                    raise ParseError("source_mismatch")
                if argument.kind == "integer":
                    if not any(candidate.value == value and candidate.evidence == proof
                               for candidate in numbers(view)):
                        raise ParseError("number_source_mismatch")
                elif not isinstance(value, str) or value != proof.raw:
                    raise ParseError("source_mismatch")
            elif proof.source == "deterministic":
                # Enum/boolean references still need a literal source in the request.
                if argument.source != "registry_options" or not proof.raw or (
                    proof.raw not in view.original_text
                ):
                    raise ParseError("unproven_deterministic_value")
            else:
                raise ParseError("unsupported_evidence")
        return ValidatedCommand(draft, values, actor.guild_id, actor.user_id,
                                spec.risk != "read")

    def _collection(
        self, argument: ArgumentSpec, value: Any, proof: Evidence,
        view: NormalizedInput, actor: Actor,
        spec: Any, *, root_id: str, pass_id: str, scope_hash: str,
        values: dict[str, Any], guild: Any, member: Any,
        trusted: TrustedContext | None,
    ) -> None:
        if proof.source != "collection" or not proof.snapshot_id or not proof.selection_id:
            raise ParseError("missing_collection_evidence")
        snapshot = self.snapshots.get(proof.snapshot_id)
        if snapshot is None or snapshot.collection_key != argument.collection:
            raise ParseError("foreign_selection")
        selected = snapshot.select(
            proof.selection_id, root_id=root_id, pass_id=pass_id,
            argument=argument.name, scope_hash=scope_hash, revision=snapshot.revision,
        )
        expected = (selected.execution_value if selected.execution_value is not None
                    else selected.object_id)
        if expected != value:
            raise ParseError("selection_value_mismatch")
        mentioned = (selected.label in view.original_text
                     or any(alias in view.original_text for alias in selected.aliases)
                     or f"<#{selected.object_id}>" in view.original_text)
        if argument.kind == "integer" and isinstance(expected, int):
            mentioned = mentioned or any(candidate.value == expected
                                         for candidate in numbers(view))
        if not mentioned and trusted is None:
            raise ParseError("collection_not_mentioned")
        parent_id = values.get(argument.depends_on) if argument.depends_on else None
        current = resolve_collection(
            spec, argument, actor, self.policy, self.db, root_id=root_id,
            pass_id=pass_id, scope_hash=scope_hash, parent_id=parent_id,
            guild=guild, member=member,
        )
        if current.revision != snapshot.revision or selected.object_id not in {
            item.item.object_id for item in current.selections
        }:
            raise ParseError("stale_collection")

    async def invoke(
        self, validated: ValidatedCommand, entry: Any, fresh_actor: Actor,
        view: NormalizedInput, *, root_id: str, pass_id: str, scope_hash: str,
        watch_allowed: bool, confirmation_consumed: bool,
        guild: Any = None, member: Any = None,
        contexts: dict[str, TrustedContext] | None = None,
    ) -> None:
        if (fresh_actor.guild_id != validated.guild_id
                or fresh_actor.user_id != validated.actor_id):
            raise ParseError("actor_changed")
        if validated.requires_confirmation and not confirmation_consumed:
            raise ParseError("confirmation_required")
        fresh = self.validate(validated.draft, view, fresh_actor, root_id=root_id,
                              pass_id=pass_id, scope_hash=scope_hash,
                              watch_allowed=watch_allowed, guild=guild, member=member,
                              contexts=contexts)
        if fresh.arguments != validated.arguments:
            raise ParseError("stale_command")
        await self.service.invoke(validated.draft.command_id, fresh.arguments,
                                  entry, fresh_actor, self.policy)

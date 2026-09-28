"""Finite interpretation-only recovery; every path yields one unexecuted draft."""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

import httpx

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.collections import CollectionSnapshot, resolve_collection
from changgeun.parser.contracts import (
    CommandDraft,
    Evidence,
    ModelPort,
    ParseError,
    ParserOutcome,
    TracePort,
)
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.llm_schema import (
    full_parse_schema,
    rewrite_schema,
    validate_full_output,
    validate_rewrite_output,
)
from changgeun.parser.normalizer import NormalizedInput
from changgeun.parser.registry import CommandSpec
from changgeun.parser.values import numbers
from changgeun.storage.database import Database

_NUMBERS = re.compile(r"\d+(?:초|곡|번|개)?")
_CONTROL = ("말고", "아니", "않", " 안 ", "제외", "모두", "전부", "전체", "모든")
_TERMINAL_FAILURES = frozenset({
    "collection_overflow", "collection_empty", "collection_fetch_failed",
    "collection_scope_required", "command_not_allowed", "unsupported_collection",
    "source_mismatch", "invalid_source_range", "invalid_invocation", "deadline_expired",
    "root_cancelled", "invalid_jev_response", "foreign_jev_selection",
})


class RewritePolicyValidator:
    def check(self, view: NormalizedInput, output: dict[str, Any]) -> str | None:
        parsed = validate_rewrite_output(output)
        status, rewrite = parsed["status"], parsed["rewritten_text"]
        if status == "unchanged":
            if rewrite != view.normalized_text:
                raise ParseError("rewrite_unchanged_mismatch")
            return None
        if status != "rewritten":
            return None
        if not isinstance(rewrite, str) or len(rewrite) > 2000:
            raise ParseError("rewrite_length")
        if rewrite == view.normalized_text:
            return None
        for span in view.protected_spans:
            literal = view.original_text[span.start:span.end]
            if literal and rewrite.count(literal) < view.original_text.count(literal):
                raise ParseError("rewrite_literal_changed")
        if Counter(_NUMBERS.findall(view.normalized_text)) != Counter(
            _NUMBERS.findall(rewrite)
        ):
            raise ParseError("rewrite_quantity_changed")
        for marker in _CONTROL:
            if (marker in f" {view.normalized_text} ") != (marker in f" {rewrite} "):
                raise ParseError("rewrite_control_changed")
        return rewrite


class ParserOrchestrator:
    def __init__(
        self, interpreter: JevInterpreter, model: ModelPort,
        commands: CommandService, db: Database, policy: Policy, *,
        llm_enabled: bool, fallback_on_jev_unavailable: bool = False,
        trace: TracePort | None = None, attachments: tuple[Any, ...] = (),
    ) -> None:
        self.interpreter, self.model, self.commands = interpreter, model, commands
        self.db, self.policy, self.trace = db, policy, trace
        self.attachments = attachments
        self.llm_enabled = llm_enabled
        self.fallback_on_jev_unavailable = fallback_on_jev_unavailable
        self.rewrite_validator = RewritePolicyValidator()
        self.cancelled = False
        self.snapshots: dict[str, CollectionSnapshot] = getattr(interpreter, "snapshots", {})

    async def cancel(self) -> None:
        self.cancelled = True
        await self.model.cancel()

    def _check(self, expires_at: float) -> None:
        if self.cancelled:
            raise ParseError("root_cancelled")
        if time.time() >= expires_at:
            raise ParseError("deadline_expired")

    def _event(self, request_id: str, name: str, **data: Any) -> None:
        if self.trace is not None:
            self.trace.event(request_id, name, data)

    @staticmethod
    def _jev_unavailable(exc: Exception) -> bool:
        return isinstance(exc, httpx.RequestError) or (
            isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in {429, 500, 502, 503, 504, 529}
        )

    async def parse(
        self, view: NormalizedInput, actor: Actor, *, root_id: str,
        scope_hash: str, expires_at: float, guild: Any = None, member: Any = None,
    ) -> ParserOutcome:
        try:
            self._check(expires_at)
            try:
                initial = await self.interpreter.interpret(
                    view, actor, root_id=root_id, pass_id="initial", scope_hash=scope_hash,
                    guild=guild, member=member,
                )
            except Exception as exc:
                if not self._jev_unavailable(exc):
                    return ParserOutcome("failed", code="jev_configuration_or_schema_error")
                self._event(root_id, "stage.skipped", reason="JEV_UNAVAILABLE")
                if not (self.llm_enabled and self.fallback_on_jev_unavailable):
                    return ParserOutcome("failed", code="jev_unavailable")
                self._check(expires_at)
                return await self._full_parse(view, actor, root_id=root_id,
                                              scope_hash=scope_hash, expires_at=expires_at,
                                              guild=guild, member=member)
            self._check(expires_at)
            if initial.status != "failed":
                return initial
            if initial.code in _TERMINAL_FAILURES or not self.llm_enabled:
                return initial
            try:
                raw_rewrite = await self.model.call(
                    "rewrite", {"original_message": view.original_text,
                                "normalized_message": view.normalized_text,
                                "initial_failure": initial.code},
                    output_schema=rewrite_schema(),
                )
                self._check(expires_at)
                status = raw_rewrite.get("status")
                rewrite = self.rewrite_validator.check(view, raw_rewrite)
            except ParseError as exc:
                self._event(root_id, "stage.skipped", reason=exc.code)
                rewrite, status = None, "rewrite_invalid"
            except Exception:
                return ParserOutcome("failed", code="llm_rewrite_unavailable")
            if status == "needs_clarification":
                return ParserOutcome("clarify", code="rewrite_needs_clarification")
            if status == "unsupported":
                return ParserOutcome("unsupported", code="rewrite_unsupported")
            if status == "multiple_intents":
                return ParserOutcome("multiple", code="rewrite_multiple")
            if rewrite is not None:
                try:
                    self._check(expires_at)
                    after = await self.interpreter.interpret(
                        view, actor, root_id=root_id, pass_id="after_rewrite",
                        scope_hash=scope_hash, rewritten_text=rewrite,
                        guild=guild, member=member,
                    )
                except Exception as exc:
                    if self._jev_unavailable(exc):
                        return ParserOutcome("failed", code="jev_unavailable_after_rewrite")
                    return ParserOutcome("failed", code="jev_configuration_or_schema_error")
                self._check(expires_at)
                prior_command = initial.options.get("selected_command")
                if (after.draft is not None and prior_command is not None
                        and after.draft.command_id != prior_command):
                    return ParserOutcome("clarify", code="interpretation_conflict")
                if after.status == "parsed" and after.draft is not None:
                    draft = after.draft
                    return ParserOutcome("parsed", CommandDraft(
                        draft.command_id, draft.arguments, draft.evidence,
                        parser_source="jev_after_rewrite", llm_assisted=True,
                    ))
                if after.status != "failed" or after.code in _TERMINAL_FAILURES:
                    if after.draft is not None:
                        draft = after.draft
                        return ParserOutcome(
                            after.status, CommandDraft(draft.command_id, draft.arguments,
                                                       draft.evidence,
                                                       parser_source="jev_after_rewrite",
                                                       llm_assisted=True),
                            code=after.code, missing=after.missing, options=after.options,
                        )
                    return after
            else:
                self._event(root_id, "stage.skipped", reason="unchanged_or_invalid_rewrite")
            self._check(expires_at)
            return await self._full_parse(
                view, actor, root_id=root_id, scope_hash=scope_hash,
                expires_at=expires_at, rewritten_text=rewrite,
                confirmed_command=initial.options.get("selected_command"),
                guild=guild, member=member,
            )
        except ParseError as exc:
            return ParserOutcome("cancelled" if exc.code == "root_cancelled" else "failed",
                                 code=exc.code)

    async def _full_parse(
        self, view: NormalizedInput, actor: Actor, *, root_id: str,
        scope_hash: str, expires_at: float, rewritten_text: str | None = None,
        confirmed_command: str | None = None, guild: Any = None, member: Any = None,
    ) -> ParserOutcome:
        self._check(expires_at)
        allowed = {key: spec for key, spec in self.commands.specs.items()
                   if key != "C39" and actor.guild_id in self.policy.guild_ids
                   and spec.allowed(actor, self.policy)}
        scope = "repair_arguments" if confirmed_command in allowed else "reparse"
        proposed = ({confirmed_command: allowed[confirmed_command]}
                    if scope == "repair_arguments" and confirmed_command else allowed)
        selected: dict[str, CommandSpec] = {}
        collections: dict[tuple[str, str], CollectionSnapshot] = {}
        unavailable: dict[str, str] = {}
        try:
            for identifier, spec in proposed.items():
                prepared: dict[tuple[str, str], CollectionSnapshot] = {}
                try:
                    for argument in spec.arguments:
                        if argument.collection and not argument.depends_on:
                            self._check(expires_at)
                            item = resolve_collection(
                                spec, argument, actor, self.policy, self.db,
                                root_id=root_id, pass_id="full_parse",
                                scope_hash=scope_hash, guild=guild, member=member,
                                attachments=self.attachments,
                            )
                            if argument.required and not item.selections:
                                raise ParseError("collection_empty")
                            prepared[(identifier, argument.name)] = item
                except ParseError as exc:
                    if (scope == "repair_arguments" or exc.code not in {
                        "collection_empty", "collection_overflow", "collection_scope_required",
                    }):
                        raise
                    unavailable[identifier] = exc.code
                    continue
                selected[identifier] = spec
                collections.update(prepared)
                for item in prepared.values():
                    self.snapshots[item.snapshot_id] = item
            if not selected:
                return ParserOutcome("clarify", code="no_available_commands")
            schema = full_parse_schema(selected, collections=collections, scope=scope,
                                       command_id=confirmed_command)
        except ParseError as exc:
            return ParserOutcome("clarify", code=exc.code)
        state = {"original_message": view.original_text,
                 "normalized_message": view.normalized_text,
                 "rewritten_message": rewritten_text,
                 "scope": scope,
                 "allowed_commands": {key: spec.description for key, spec in selected.items()},
                 "unavailable_commands": unavailable,
                 "collections": {f"{key[0]}:{key[1]}": item.criteria()
                                 for key, item in collections.items() if item.selections}}
        try:
            output = await self.model.call("full_parse", state, output_schema=schema)
            self._check(expires_at)
            output = validate_full_output(output, commands=selected, collections=collections)
        except ParseError as exc:
            return ParserOutcome("failed", code=exc.code)
        except Exception:
            return ParserOutcome("failed", code="llm_full_parse_unavailable")
        if output["status"] != "parsed":
            if output["status"] == "needs_clarification":
                return ParserOutcome("clarify", code="full_needs_clarification")
            if output["status"] == "multiple_intents":
                return ParserOutcome("multiple", code="full_multiple_intents")
            return ParserOutcome("unsupported", code="full_unsupported")
        plan = output["plan"]
        spec = selected[plan["command"]]
        arguments: dict[str, Any] = {}
        evidence: dict[str, Evidence] = {}
        for argument in spec.arguments:
            value = plan["arguments"][argument.name]
            if value is None:
                if argument.required:
                    return ParserOutcome("clarify", code="missing_argument",
                                         missing=(argument.name,))
                # Only an absent argument may receive a code-owned default.
                # In particular, false and zero must remain explicit values.
                continue
            elif argument.collection:
                if value["query"] is not None:
                    return ParserOutcome("clarify", code="unresolved_reference",
                                         missing=(argument.name,))
                collection = collections.get((spec.identifier, argument.name))
                if collection is None:
                    return ParserOutcome("clarify", code="collection_dependency_unresolved",
                                         missing=(argument.name,))
                chosen_item = collection.select(value["candidate_id"], root_id=root_id,
                                                pass_id="full_parse", argument=argument.name,
                                                scope_hash=scope_hash, revision=collection.revision)
                arguments[argument.name] = (
                    chosen_item.execution_value if chosen_item.execution_value is not None
                    else chosen_item.object_id
                )
                evidence[argument.name] = Evidence("collection", snapshot_id=collection.snapshot_id,
                                                   selection_id=value["candidate_id"])
            elif argument.kind == "integer":
                matches = [candidate for candidate in numbers(view) if candidate.value == value]
                if len(matches) != 1:
                    return ParserOutcome("clarify", code="number_source_ambiguous",
                                         missing=(argument.name,))
                arguments[argument.name], evidence[argument.name] = value, matches[0].evidence
            elif isinstance(value, str):
                if view.original_text.count(value) != 1:
                    return ParserOutcome("clarify", code="source_ambiguous",
                                         missing=(argument.name,))
                start = view.original_text.index(value)
                arguments[argument.name], evidence[argument.name] = value, Evidence(
                    "span", value, start, start + len(value))
            else:
                arguments[argument.name], evidence[argument.name] = value, Evidence("deterministic")
        return ParserOutcome("parsed", CommandDraft(
            spec.identifier, arguments, evidence, parser_source="llm_full_parse",
            llm_assisted=True,
        ))

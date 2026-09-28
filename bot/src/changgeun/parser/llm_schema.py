"""Provider-neutral strict output contracts from trusted command specifications."""

from __future__ import annotations

from typing import Any

from changgeun.parser.collections import CollectionSnapshot
from changgeun.parser.contracts import ParseError
from changgeun.parser.registry import ArgumentSpec, CommandSpec


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def rewrite_schema() -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": [
                "rewritten", "unchanged", "needs_clarification", "unsupported",
                "multiple_intents",
            ]},
            "rewritten_text": {"type": ["string", "null"]},
            "unresolved_references": {"type": "array", "items": {"type": "string"}},
            "question": {"type": ["string", "null"]},
        },
        "required": ["status", "rewritten_text", "unresolved_references", "question"],
    }


def _argument_schema(argument: ArgumentSpec,
                     collection: CollectionSnapshot | None) -> dict[str, Any]:
    if argument.collection:
        if collection is None:
            if not argument.depends_on:
                raise ParseError("collection_required_for_llm")
            ids: list[str] = []  # Parent is not known until this parse completes.
        else:
            if not collection.complete:
                raise ParseError("collection_required_for_llm")
            if not collection.selections:
                if not argument.required:
                    return {"type": "null"}
                raise ParseError("collection_required_for_llm")
            ids = [selection.token for selection in collection.selections]
        return _nullable({
            "type": "object", "additionalProperties": False,
            "properties": {
                "candidate_id": {"type": ["string", "null"], "enum": [*ids, None]},
                "query": {"type": ["string", "null"]},
            },
            "required": ["candidate_id", "query"],
        })
    if argument.kind == "integer":
        base: dict[str, Any] = {"type": "integer"}
    elif argument.kind == "boolean":
        base = {"type": "boolean"}
    else:
        base = {"type": "string"}
        if argument.choices:
            base["enum"] = list(argument.choices)
    return _nullable(base)


def full_parse_schema(
    commands: dict[str, CommandSpec], *,
    collections: dict[tuple[str, str], CollectionSnapshot],
    scope: str = "reparse", command_id: str | None = None,
) -> dict[str, Any]:
    if scope not in {"reparse", "repair_arguments"}:
        raise ParseError("invalid_llm_scope")
    if scope == "repair_arguments":
        if command_id not in commands:
            raise ParseError("missing_repair_command")
        chosen = {command_id: commands[command_id]}
    else:
        chosen = commands
    if not chosen or "C39" in chosen:
        raise ParseError("invalid_llm_commands")
    branches = []
    for identifier, command in chosen.items():
        arguments = {
            argument.name: _argument_schema(
                argument, collections.get((identifier, argument.name)))
            for argument in command.arguments
        }
        branches.append({
            "type": "object", "additionalProperties": False,
            "properties": {
                "command": {"type": "string", "enum": [identifier]},
                "arguments": {"type": "object", "additionalProperties": False,
                              "properties": arguments, "required": list(arguments)},
            },
            "required": ["command", "arguments"],
        })
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": [
                "parsed", "needs_clarification", "unsupported", "multiple_intents",
            ]},
            "plan": {"anyOf": [*branches, {"type": "null"}]},
            "unresolved_arguments": {"type": "array", "items": {"type": "string"}},
            "question": {"type": ["string", "null"]},
        },
        "required": ["status", "plan", "unresolved_arguments", "question"],
    }


def validate_rewrite_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(rewrite_schema()["properties"]):
        raise ParseError("invalid_rewrite_output")
    status = value["status"]
    if status not in rewrite_schema()["properties"]["status"]["enum"]:
        raise ParseError("invalid_rewrite_output")
    text, unresolved, question = (value["rewritten_text"],
                                  value["unresolved_references"], value["question"])
    if (not isinstance(unresolved, list) or any(not isinstance(item, str)
                                                for item in unresolved)
            or (question is not None and not isinstance(question, str))):
        raise ParseError("invalid_rewrite_output")
    if status == "rewritten":
        if not isinstance(text, str) or not text.strip() or unresolved or question is not None:
            raise ParseError("invalid_rewrite_output")
    elif status == "unchanged":
        if not isinstance(text, str):
            raise ParseError("invalid_rewrite_output")
    elif text is not None:
        raise ParseError("invalid_rewrite_output")
    return value


def validate_full_output(value: Any, *, commands: dict[str, CommandSpec],
                         collections: dict[tuple[str, str], CollectionSnapshot]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "status", "plan", "unresolved_arguments", "question"
    }:
        raise ParseError("invalid_full_parse_output")
    status, plan = value["status"], value["plan"]
    if status not in {"parsed", "needs_clarification", "unsupported", "multiple_intents"}:
        raise ParseError("invalid_full_parse_output")
    if (not isinstance(value["unresolved_arguments"], list)
            or not all(isinstance(item, str) for item in value["unresolved_arguments"])):
        raise ParseError("invalid_full_parse_output")
    if value["question"] is not None and not isinstance(value["question"], str):
        raise ParseError("invalid_full_parse_output")
    if status != "parsed":
        if plan is not None:
            raise ParseError("invalid_full_parse_output")
        return value
    if (not isinstance(plan, dict) or set(plan) != {"command", "arguments"}
            or plan["command"] not in commands
            or not isinstance(plan["arguments"], dict)
            or value["unresolved_arguments"] or value["question"] is not None):
        raise ParseError("invalid_full_parse_output")
    spec = commands[plan["command"]]
    if set(plan["arguments"]) != {argument.name for argument in spec.arguments}:
        raise ParseError("invalid_full_parse_output")
    for argument in spec.arguments:
        value_arg = plan["arguments"][argument.name]
        if value_arg is None:
            if argument.required:
                raise ParseError("missing_argument")
            continue
        if argument.collection:
            collection = collections.get((spec.identifier, argument.name))
            if not isinstance(value_arg, dict) or set(value_arg) != {
                "candidate_id", "query"
            }:
                raise ParseError("invalid_full_parse_output")
            candidate, query = value_arg["candidate_id"], value_arg["query"]
            if (candidate is None) == (query is None):
                raise ParseError("invalid_reference")
            if candidate is not None and (collection is None or candidate not in {
                entry.token for entry in collection.selections
            }):
                raise ParseError("foreign_selection")
            if query is not None and (not isinstance(query, str) or not query.strip()):
                raise ParseError("invalid_reference")
        else:
            argument.validate(value_arg)
    return value

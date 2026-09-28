"""Typed public command contracts built from the registered slash definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from changgeun.domain.models import Actor, Policy
from changgeun.nlp.command_registry import PUBLIC_WITHOUT_DJ, READ_COMMANDS
from changgeun.parser.contracts import ParseError


@dataclass(frozen=True)
class ArgumentSpec:
    name: str
    kind: str
    required: bool
    default: Any = None
    source: str = "source_span"
    collection: str | None = None
    depends_on: str | None = None
    minimum: int | None = None
    maximum: int | None = None
    max_length: int = 100
    choices: tuple[str, ...] = ()
    description: str = ""

    def validate(self, value: Any) -> None:
        if value is None:
            if self.required:
                raise ParseError("missing_argument")
            return
        if self.kind == "integer":
            if type(value) is not int:
                raise ParseError("invalid_integer")
            if ((self.minimum is not None and value < self.minimum)
                    or (self.maximum is not None and value > self.maximum)):
                raise ParseError("argument_out_of_range")
        elif self.kind == "boolean":
            if type(value) is not bool:
                raise ParseError("invalid_boolean")
        elif self.kind in {"string", "channel", "attachment"}:
            if not isinstance(value, str) or len(value) > self.max_length:
                raise ParseError("invalid_text")
            if self.required and not value:
                raise ParseError("missing_argument")
        else:
            raise ParseError("unsupported_argument_type")
        if self.choices and value not in self.choices:
            raise ParseError("invalid_enum")


@dataclass(frozen=True)
class CommandSpec:
    identifier: str
    name: str
    description: str
    arguments: tuple[ArgumentSpec, ...]
    permission: str
    risk: str
    private: bool = False

    def allowed(self, actor: Actor, policy: Policy) -> bool:
        if self.identifier == "C39" or not actor.permissions_known:
            return False
        if self.permission == "admin":
            return actor.manage_guild
        return self.permission == "public" or bool(actor.role_ids & policy.dj_role_ids) or (
            policy.admin_dj_override and actor.manage_guild
        )

    def validate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        specs = {a.name: a for a in self.arguments}
        if set(arguments) - specs.keys():
            raise ParseError("unknown_argument")
        result = {}
        for name, spec in specs.items():
            value = arguments.get(name, spec.default)
            spec.validate(value)
            result[name] = value
        if self.identifier == "C23" and sum(result[k] is not None
                                           for k in ("곡", "목록", "검색어")) != 1:
            raise ParseError("play_target_required")
        if self.identifier == "C08":
            if (result["링크"] is None) == (result["파일"] is None):
                raise ParseError("import_source_required")
            if result["교체"] and result["기존목록"] is None:
                raise ParseError("replace_target_required")
        return result

    def describe(self) -> dict[str, Any]:
        return asdict(self)


def permission(identifier: str) -> str:
    return ("admin" if int(identifier[1:]) >= 40 else
            "public" if identifier in PUBLIC_WITHOUT_DJ else "dj")


def risk(identifier: str) -> str:
    return "read" if identifier in READ_COMMANDS else "write"

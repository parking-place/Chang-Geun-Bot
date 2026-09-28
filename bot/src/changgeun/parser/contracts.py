"""Provider-independent parser ports and provenance; no provider SDK types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


class ParseError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Evidence:
    source: Literal["span", "collection", "deterministic", "default", "context"]
    raw: str = ""
    start: int | None = None
    end: int | None = None
    snapshot_id: str | None = None
    selection_id: str | None = None
    context_id: str | None = None


@dataclass(frozen=True)
class CommandDraft:
    command_id: str
    arguments: dict[str, Any]
    evidence: dict[str, Evidence]
    parser_source: str = "jev_initial"
    llm_assisted: bool = False


@dataclass(frozen=True)
class ParserOutcome:
    status: Literal["parsed", "clarify", "unsupported", "multiple", "failed", "cancelled"]
    draft: CommandDraft | None = None
    code: str | None = None
    missing: tuple[str, ...] = ()
    options: dict[str, str] = field(default_factory=dict)


class ModelPort(Protocol):
    async def call(
        self, operation: str, state: dict[str, Any], *,
        pass_id: str | None = None, stage_index: int | None = None,
        questions: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def cancel(self) -> None: ...


class TracePort(Protocol):
    def event(self, request_id: str, name: str, data: dict[str, Any]) -> None: ...

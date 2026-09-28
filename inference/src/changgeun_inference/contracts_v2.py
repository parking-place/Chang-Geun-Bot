"""Explicit parser-api-v2 wire contract; API 1.2 remains unchanged."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Operation = Literal[
    "command_select", "argument_select", "context_select", "rewrite", "full_parse"
]
PassId = Literal["initial", "after_rewrite"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RootRequest(StrictModel):
    schema_version: Literal["parser-api-v2"] = "parser-api-v2"
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    scope_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    original_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: float
    expires_at: float

    @model_validator(mode="after")
    def deadline(self) -> RootRequest:
        if not all(math.isfinite(x) for x in (self.created_at, self.expires_at)):
            raise ValueError("nonfinite deadline")
        if not 0 < self.expires_at - self.created_at <= 35.001:
            raise ValueError("root deadline exceeds 35 seconds")
        return self


class Question(StrictModel):
    type: Literal["choice", "noul"]
    instructions: str = Field(min_length=1, max_length=2000)
    criteria: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded(self) -> Question:
        if self.type == "choice" and not 2 <= len(self.criteria) <= 255:
            raise ValueError("choice requires 2..255 options including sentinels")
        if self.type == "noul" and self.criteria:
            raise ValueError("noul does not accept criteria")
        if any(not k or len(k) > 128 or not v or len(v) > 1000
               for k, v in self.criteria.items()):
            raise ValueError("invalid criterion")
        return self


class ParseCall(StrictModel):
    root: RootRequest
    call_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    operation: Operation
    pass_id: PassId | None = None
    stage_index: int | None = Field(default=None, ge=1, le=3)
    state: dict[str, Any]
    questions: dict[str, Question] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def operation_contract(self) -> ParseCall:
        if self.operation in {"rewrite", "full_parse"}:
            if self.pass_id is not None or self.stage_index is not None or self.questions:
                raise ValueError("LLM call cannot carry Jev pass/questions")
            if not self.output_schema or self.output_schema.get("type") != "object":
                raise ValueError("LLM requires an object output schema")
        else:
            stages = {"command_select": 1, "argument_select": 2, "context_select": 3}
            if self.pass_id is None or self.stage_index != stages[self.operation]:
                raise ValueError("Jev pass/stage mismatch")
            if not 1 <= len(self.questions) <= 256 or self.output_schema is not None:
                raise ValueError("invalid Jev questions/schema")
        if any(not k or len(k) > 128 for k in self.questions):
            raise ValueError("invalid question key")
        try:
            encoded = json.dumps(self.model_dump(), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("non-JSON payload") from exc
        if len(encoded.encode()) > 196608:
            raise ValueError("parser payload too large")
        return self


class TokenUsage(StrictModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def subsets(self) -> TokenUsage:
        for part, whole in ((self.cached_input_tokens, self.input_tokens),
                            (self.reasoning_tokens, self.output_tokens)):
            if part is not None and whole is not None and part > whole:
                raise ValueError("token subset exceeds total")
        if (self.input_tokens is not None and self.output_tokens is not None
                and self.total_tokens is not None
                and self.total_tokens != self.input_tokens + self.output_tokens):
            raise ValueError("token total mismatch")
        return self


class CallResponse(StrictModel):
    schema_version: Literal["parser-api-v2"] = "parser-api-v2"
    request_id: str
    call_id: str
    operation: Operation
    attempt_no: int = Field(ge=1, le=8)
    remote_attempted: bool
    status: Literal["completed", "refused", "incomplete", "invalid_output", "failed"]
    result: dict[str, Any] | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str | None = None
    error_code: str | None = None
    cache_hit: bool = False

    @model_validator(mode="after")
    def result_status(self) -> CallResponse:
        if (self.status == "completed") != (self.result is not None):
            raise ValueError("only completed responses have a result")
        return self

"""API 1.2: a question can choose only from server-supplied candidates."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=200)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal["1.2"]
    provider: Literal["jev-api", "mock"]
    profile_id: str = Field(min_length=1, max_length=64)
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(min_length=1, max_length=128)
    stage_index: int = Field(ge=1, le=3)
    task: Literal["classify_intent", "select_action", "resolve_context"]
    request_expires_at: float
    remaining_timeout_ms: int = Field(gt=0, le=12000)
    context_snapshot_id: str = Field(min_length=1, max_length=128)
    candidate_set_id: str = Field(min_length=1, max_length=128)
    utterance: str = Field(min_length=1, max_length=500)
    context: dict[str, str] = Field(default_factory=dict)
    candidates: list[Candidate] = Field(min_length=2, max_length=12)
    prompt_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_stage(self) -> DecisionRequest:
        expected = ("classify_intent", "select_action", "resolve_context")[self.stage_index - 1]
        if self.task != expected or not math.isfinite(self.request_expires_at):
            raise ValueError("invalid stage/deadline")
        ids = [c.id for c in self.candidates]
        if len(set(ids)) != len(ids) or "clarify" not in ids:
            raise ValueError("unique candidates including clarify required")
        if len(self.context) > 12 or any(
            len(k) > 64 or len(v) > 200 for k, v in self.context.items()
        ):
            raise ValueError("context too large")
        if self.stage_index == 3 and self.remaining_timeout_ms < 1000:
            raise ValueError("insufficient stage-three budget")
        return self


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selected_id: str
    probabilities: dict[str, float]
    input_tokens: int | None = None
    model: str | None = None
    model_revision: str | None = None
    forward_passes: int | None = None

    def validate_candidates(self, request: DecisionRequest) -> None:
        allowed = {c.id for c in request.candidates}
        if self.selected_id not in allowed or set(self.probabilities) != allowed:
            raise ValueError("provider returned unknown candidate")
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in self.probabilities.values()):
            raise ValueError("invalid probability")
        if not math.isclose(sum(self.probabilities.values()), 1, abs_tol=0.02):
            raise ValueError("probabilities do not sum to one")


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.2"] = "1.2"
    provider: Literal["jev-api", "mock"]
    profile_id: str = Field(min_length=1, max_length=64)
    config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(min_length=1, max_length=128)
    stage_index: int = Field(ge=1, le=3)
    task: Literal["classify_intent", "select_action", "resolve_context"]
    context_snapshot_id: str = Field(min_length=1, max_length=128)
    candidate_set_id: str = Field(min_length=1, max_length=128)
    selected_id: str
    probabilities: dict[str, float]
    usage: dict[str, Any]
    provenance: dict[str, Any]
